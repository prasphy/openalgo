from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for, abort
from database.strategy_db import (
    Strategy, StrategySymbolMapping, db_session,
    create_strategy, add_symbol_mapping, get_strategy_by_webhook_id,
    get_symbol_mappings, get_all_strategies, delete_strategy,
    update_strategy_times, delete_symbol_mapping, bulk_add_symbol_mappings,
    toggle_strategy, get_strategy, get_user_strategies, create_custom_strategy,
    update_strategy_config
)
from database.symbol import enhanced_search_symbols
from database.auth_db import get_api_key_for_tradingview
from utils.session import check_session_validity, is_session_valid
from limiter import limiter
import json
from datetime import datetime, time
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from utils.logging import get_logger
import requests
import os
import uuid
import time as time_module
import queue
import threading
from collections import deque
from time import time
import re

logger = get_logger(__name__)

# Rate limiting configuration
WEBHOOK_RATE_LIMIT = os.getenv("WEBHOOK_RATE_LIMIT", "100 per minute")
STRATEGY_RATE_LIMIT = os.getenv("STRATEGY_RATE_LIMIT", "200 per minute")
CUSTOM_STRATEGY_RATE_LIMIT = os.getenv("CUSTOM_STRATEGY_RATE_LIMIT", "50 per minute")

strategy_bp = Blueprint('strategy_bp', __name__, url_prefix='/strategy')

# Initialize scheduler for time-based controls
scheduler = BackgroundScheduler(
    timezone=pytz.timezone('Asia/Kolkata'),
    job_defaults={
        'coalesce': True,
        'misfire_grace_time': 300,
        'max_instances': 1
    }
)
scheduler.start()

# Get base URL from environment or default to localhost
BASE_URL = os.getenv('HOST_SERVER', 'http://127.0.0.1:5000')

# Valid exchanges
VALID_EXCHANGES = ['NSE', 'BSE', 'NFO', 'CDS', 'BFO', 'BCD', 'MCX', 'NCDEX']

# Product types per exchange
EXCHANGE_PRODUCTS = {
    'NSE': ['MIS', 'CNC'],
    'BSE': ['MIS', 'CNC'],
    'NFO': ['MIS', 'NRML'],
    'CDS': ['MIS', 'NRML'],
    'BFO': ['MIS', 'NRML'],
    'BCD': ['MIS', 'NRML'],
    'MCX': ['MIS', 'NRML'],
    'NCDEX': ['MIS', 'NRML']
}

# Default values
DEFAULT_EXCHANGE = 'NSE'
DEFAULT_PRODUCT = 'MIS'

# Separate queues for different order types
regular_order_queue = queue.Queue()  # For placeorder (up to 10/sec)
smart_order_queue = queue.Queue()    # For placesmartorder (1/sec)

# Order processor state
order_processor_running = False
order_processor_lock = threading.Lock()

# Rate limiting state for regular orders
last_regular_orders = deque(maxlen=10)  # Track last 10 regular order timestamps

def process_orders():
    """Background task to process orders from both queues with rate limiting"""
    global order_processor_running
    
    while True:
        try:
            # Process smart orders first (1 per second)
            try:
                smart_order = smart_order_queue.get_nowait()
                if smart_order is None:  # Poison pill
                    break
                
                try:
                    response = requests.post(f'{BASE_URL}/api/v1/placesmartorder', json=smart_order['payload'])
                    if response.ok:
                        logger.info(f'Smart order placed for {smart_order["payload"]["symbol"]} in strategy {smart_order["payload"]["strategy"]}')
                    else:
                        logger.error(f'Error placing smart order for {smart_order["payload"]["symbol"]}: {response.text}')
                except Exception as e:
                    logger.error(f'Error placing smart order: {str(e)}')
                
                # Always wait 1 second after smart order
                time_module.sleep(1)
                continue  # Start next iteration
                
            except queue.Empty:
                pass  # No smart orders, continue to regular orders
            
            # Process regular orders (up to 10 per second)
            now = time()
            
            # Clean up old timestamps
            while last_regular_orders and now - last_regular_orders[0] > 1:
                last_regular_orders.popleft()
            
            # Process regular orders if under rate limit
            if len(last_regular_orders) < 10:
                try:
                    regular_order = regular_order_queue.get_nowait()
                    if regular_order is None:  # Poison pill
                        break
                    
                    try:
                        response = requests.post(f'{BASE_URL}/api/v1/placeorder', json=regular_order['payload'])
                        if response.ok:
                            logger.info(f'Regular order placed for {regular_order["payload"]["symbol"]} in strategy {regular_order["payload"]["strategy"]}')
                            last_regular_orders.append(now)
                        else:
                            logger.error(f'Error placing regular order for {regular_order["payload"]["symbol"]}: {response.text}')
                    except Exception as e:
                        logger.error(f'Error placing regular order: {str(e)}')
                    
                except queue.Empty:
                    pass  # No regular orders
            
            # Small sleep to prevent CPU spinning
            time_module.sleep(0.1)
            
        except Exception as e:
            logger.error(f'Error in order processor: {str(e)}')
            time_module.sleep(1)  # Sleep on error to prevent rapid retries

def ensure_order_processor():
    """Ensure the order processor is running"""
    global order_processor_running
    with order_processor_lock:
        if not order_processor_running:
            threading.Thread(target=process_orders, daemon=True).start()
            order_processor_running = True

def queue_order(endpoint, payload):
    """Add order to appropriate queue"""
    ensure_order_processor()
    if endpoint == 'placesmartorder':
        smart_order_queue.put({'payload': payload})
    else:
        regular_order_queue.put({'payload': payload})

def validate_strategy_times(start_time, end_time, squareoff_time):
    """Validate strategy time settings"""
    try:
        if not all([start_time, end_time, squareoff_time]):
            return False, "All time fields are required"
        
        # Convert strings to time objects for comparison
        start = datetime.strptime(start_time, '%H:%M').time()
        end = datetime.strptime(end_time, '%H:%M').time()
        squareoff = datetime.strptime(squareoff_time, '%H:%M').time()
        
        # Market hours validation (9:15 AM to 3:30 PM)
        market_open = datetime.strptime('09:15', '%H:%M').time()
        market_close = datetime.strptime('15:30', '%H:%M').time()
        
        if start < market_open:
            return False, "Start time cannot be before market open (9:15)"
        if end > market_close:
            return False, "End time cannot be after market close (15:30)"
        if squareoff > market_close:
            return False, "Square off time cannot be after market close (15:30)"
        if start >= end:
            return False, "Start time must be before end time"
        if squareoff < start:
            return False, "Square off time must be after start time"
        if squareoff < end:
            return False, "Square off time must be after end time"
        
        return True, None
        
    except ValueError:
        return False, "Invalid time format. Use HH:MM format"

def validate_strategy_name(name):
    """Validate strategy name format"""
    if not name:
        return False, "Strategy name is required"
    
    # Check length
    if len(name) < 3 or len(name) > 50:
        return False, "Strategy name must be between 3 and 50 characters"
    
    # Check characters
    if not re.match(r'^[A-Za-z0-9\s\-_]+$', name):
        return False, "Strategy name can only contain letters, numbers, spaces, hyphens and underscores"
    
    return True, None

def schedule_squareoff(strategy_id):
    """Schedule squareoff for intraday strategy"""
    strategy = get_strategy(strategy_id)
    if not strategy or not strategy.is_intraday or not strategy.squareoff_time:
        return
    
    try:
        hours, minutes = map(int, strategy.squareoff_time.split(':'))
        job_id = f'squareoff_{strategy_id}'
        
        # Remove existing job if any
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # Add new job
        scheduler.add_job(
            squareoff_positions,
            'cron',
            hour=hours,
            minute=minutes,
            args=[strategy_id],
            id=job_id,
            timezone=pytz.timezone('Asia/Kolkata')
        )
        logger.info(f'Scheduled squareoff for strategy {strategy_id} at {hours}:{minutes}')
    except Exception as e:
        logger.error(f'Error scheduling squareoff for strategy {strategy_id}: {str(e)}')

def squareoff_positions(strategy_id):
    """Square off all positions for intraday strategy"""
    try:
        strategy = get_strategy(strategy_id)
        if not strategy or not strategy.is_intraday:
            return
        
        # Get API key for authentication
        api_key = get_api_key_for_tradingview(strategy.user_id)
        if not api_key:
            logger.error(f'No API key found for strategy {strategy_id}')
            return
            
        # Get all symbol mappings
        mappings = get_symbol_mappings(strategy_id)
        
        for mapping in mappings:
            # Use placesmartorder with quantity=0 and position_size=0 for squareoff
            payload = {
                'apikey': api_key,
                'symbol': mapping.symbol,
                'exchange': mapping.exchange,
                'product': mapping.product_type,
                'strategy': strategy.name,
                'action': 'SELL',  # Direction doesn't matter for closing
                'pricetype': 'MARKET',
                'quantity': '0',
                'position_size': '0',  # This will close the position
                'price': '0',
                'trigger_price': '0',
                'disclosed_quantity': '0'
            }
            
            # Queue the order instead of executing directly
            queue_order('placesmartorder', payload)
            
    except Exception as e:
        logger.error(f'Error in squareoff_positions for strategy {strategy_id}: {str(e)}')

@strategy_bp.route('/')
def index():
    """List all strategies"""
    if not is_session_valid():
        return redirect(url_for('auth.login'))
    
    user_id = session.get('user')  
    if not user_id:
        flash('Please login to continue', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        logger.info(f"Fetching strategies for user: {user_id}")
        strategies = get_user_strategies(user_id)
        return render_template('strategy/index.html', strategies=strategies)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        flash('Error loading strategies', 'error')
        return redirect(url_for('dashboard_bp.index'))

@strategy_bp.route('/new', methods=['GET', 'POST'])
@check_session_validity
@limiter.limit(STRATEGY_RATE_LIMIT)
def new_strategy():
    """Create new strategy"""
    if request.method == 'POST':
        try:
            # Get user_id from session
            user_id = session.get('user')
            if not user_id:
                logger.error("No user_id found in session")
                flash('Session expired. Please login again.', 'error')
                return redirect(url_for('auth.login'))
            
            logger.info(f"Creating strategy for user: {user_id}")

            # Get form data
            platform = request.form.get('platform', '').strip()
            name = request.form.get('name', '').strip()

            # Validate platform
            if not platform:
                flash('Please select a platform', 'error')
                return redirect(url_for('strategy_bp.new_strategy'))

            # Handle custom strategy creation
            if platform == 'custom':
                return handle_custom_strategy_creation(user_id, name)

            # Create prefixed strategy name for non-custom strategies
            name = f"{platform}_{name}"

            # Get other form data
            strategy_type = request.form.get('type')
            trading_mode = request.form.get('trading_mode', 'LONG')  # Default to LONG
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            squareoff_time = request.form.get('squareoff_time')
            
            # Validate strategy name
            if not validate_strategy_name(name):
                flash('Invalid strategy name. Use only letters, numbers, spaces, hyphens, and underscores', 'error')
                return redirect(url_for('strategy_bp.new_strategy'))
            
            # Validate times for intraday strategy
            is_intraday = strategy_type == 'intraday'
            if is_intraday:
                if not validate_strategy_times(start_time, end_time, squareoff_time):
                    flash('Invalid trading times. End time must be after start time and before square off time', 'error')
                    return redirect(url_for('strategy_bp.new_strategy'))
            else:
                start_time = end_time = squareoff_time = None
            
            # Generate webhook ID
            webhook_id = str(uuid.uuid4())
            
            # Create strategy with user ID
            strategy = create_strategy(
                name=name,
                webhook_id=webhook_id,
                user_id=user_id,  # Use username from session
                is_intraday=is_intraday,
                trading_mode=trading_mode,
                start_time=start_time,
                end_time=end_time,
                squareoff_time=squareoff_time,
                platform=platform
            )
            
            if strategy:
                flash('Strategy created successfully!', 'success')
                if strategy.is_intraday:
                    schedule_squareoff(strategy.id)
                return redirect(url_for('strategy_bp.configure_symbols', strategy_id=strategy.id))
            else:
                flash('Error creating strategy', 'error')
                return redirect(url_for('strategy_bp.new_strategy'))
                
        except Exception as e:
            logger.error(f'Error creating strategy: {str(e)}')
            flash('Error creating strategy', 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
    
    # For GET request, get available custom strategies
    try:
        from custom_strategies import StrategyLoader
        loader = StrategyLoader()
        available_strategies = loader.get_strategy_list()
    except Exception as e:
        logger.error(f"Error loading custom strategies: {str(e)}")
        available_strategies = []
    
    return render_template('strategy/new_strategy.html', custom_strategies=available_strategies)

def handle_custom_strategy_creation(user_id, name):
    """Handle creation of custom strategy"""
    try:
        # Get custom strategy specific form data
        strategy_file = request.form.get('strategy_file', '').strip()
        strategy_category = request.form.get('strategy_category', 'user_strategies').strip()
        execution_mode = request.form.get('execution_mode', 'immediate').strip()
        
        # Get strategy configuration parameters
        strategy_config = {}
        for key, value in request.form.items():
            if key.startswith('config_'):
                config_key = key[7:]  # Remove 'config_' prefix
                strategy_config[config_key] = value
        
        # Get schedule configuration if execution mode is 'schedule'
        schedule_config = None
        if execution_mode == 'schedule':
            schedule_config = {
                'interval_type': request.form.get('schedule_interval_type', 'minutes'),
                'interval_value': int(request.form.get('schedule_interval_value', 5)),
                'time': request.form.get('schedule_time', '09:30')
            }
        
        # Validate custom strategy fields
        if not strategy_file:
            flash('Please select a custom strategy file', 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
        
        if not name:
            flash('Strategy name is required', 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
        
        # Validate strategy name
        valid, error_msg = validate_strategy_name(name)
        if not valid:
            flash(error_msg, 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
        
        # Validate the strategy file exists and is valid
        from custom_strategies import StrategyLoader, StrategyValidator
        loader = StrategyLoader()
        validator = StrategyValidator()
        
        # Check if strategy file exists
        strategy_class = loader.load_strategy(
            strategy_file.replace('.py', ''), 
            strategy_category
        )
        
        if not strategy_class:
            flash(f'Invalid strategy file: {strategy_file}', 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
        
        # Validate the strategy class
        if not loader.validate_strategy(strategy_class):
            flash('Strategy class validation failed', 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
        
        # Generate webhook ID
        webhook_id = str(uuid.uuid4())
        
        # Create custom strategy
        strategy = create_custom_strategy(
            name=name,
            webhook_id=webhook_id,
            user_id=user_id,
            strategy_file=strategy_file,
            strategy_category=strategy_category,
            execution_mode=execution_mode,
            schedule_config=schedule_config,
            strategy_config=strategy_config
        )
        
        if strategy:
            flash('Custom strategy created successfully!', 'success')
            
            # If it's a scheduled strategy, set up the schedule
            if execution_mode == 'schedule':
                try:
                    from custom_strategies import get_strategy_executor
                    executor = get_strategy_executor()
                    executor.schedule_strategy_execution(strategy.id, schedule_config)
                except Exception as e:
                    logger.error(f"Error scheduling strategy: {str(e)}")
                    flash('Strategy created but scheduling failed', 'warning')
            
            return redirect(url_for('strategy_bp.view_strategy', strategy_id=strategy.id))
        else:
            flash('Error creating custom strategy', 'error')
            return redirect(url_for('strategy_bp.new_strategy'))
            
    except Exception as e:
        logger.error(f'Error creating custom strategy: {str(e)}')
        flash(f'Error creating custom strategy: {str(e)}', 'error')
        return redirect(url_for('strategy_bp.new_strategy'))

@strategy_bp.route('/<int:strategy_id>')
def view_strategy(strategy_id):
    """View strategy details"""
    if not is_session_valid():
        return redirect(url_for('auth.login'))
    
    strategy = get_strategy(strategy_id)
    if not strategy:
        flash('Strategy not found', 'error')
        return redirect(url_for('strategy_bp.index'))
    
    if strategy.user_id != session.get('user'):
        flash('Unauthorized access', 'error')
        return redirect(url_for('strategy_bp.index'))
    
    symbol_mappings = get_symbol_mappings(strategy_id)
    
    # Get execution history for custom strategies
    execution_history = []
    if strategy.strategy_type == 'custom':
        try:
            from custom_strategies import get_strategy_executor
            executor = get_strategy_executor()
            execution_history = executor.get_execution_history(strategy_id, limit=10)
        except Exception as e:
            logger.error(f"Error getting execution history: {str(e)}")
    
    return render_template('strategy/view_strategy.html', 
                         strategy=strategy,
                         symbol_mappings=symbol_mappings,
                         execution_history=execution_history)

@strategy_bp.route('/toggle/<int:strategy_id>', methods=['POST'])
def toggle_strategy_route(strategy_id):
    """Toggle strategy active status"""
    if not is_session_valid():
        return redirect(url_for('auth.login'))
        
    try:
        strategy = toggle_strategy(strategy_id)
        if strategy:
            if strategy.is_active:
                # Schedule squareoff if being activated
                schedule_squareoff(strategy_id)
                
                # For custom strategies with scheduled execution, start the schedule
                if strategy.strategy_type == 'custom' and strategy.execution_mode == 'schedule':
                    try:
                        from custom_strategies import get_strategy_executor
                        executor = get_strategy_executor()
                        if strategy.schedule_config:
                            executor.schedule_strategy_execution(strategy_id, strategy.schedule_config)
                    except Exception as e:
                        logger.error(f"Error scheduling custom strategy: {str(e)}")
                
                flash('Strategy activated successfully', 'success')
            else:
                # Remove squareoff job if being deactivated
                try:
                    scheduler.remove_job(f'squareoff_{strategy_id}')
                except Exception:
                    pass
                
                # For custom strategies, cancel scheduled execution
                if strategy.strategy_type == 'custom':
                    try:
                        from custom_strategies import get_strategy_executor
                        executor = get_strategy_executor()
                        executor.cancel_scheduled_strategy(strategy_id)
                    except Exception as e:
                        logger.error(f"Error cancelling custom strategy schedule: {str(e)}")
                
                flash('Strategy deactivated successfully', 'success')
            
            return redirect(url_for('strategy_bp.view_strategy', strategy_id=strategy_id))
        else:
            flash('Error toggling strategy: Strategy not found', 'error')
            return redirect(url_for('strategy_bp.index'))
    except Exception as e:
        flash(f'Error toggling strategy: {str(e)}', 'error')
        return redirect(url_for('strategy_bp.index'))

@strategy_bp.route('/<int:strategy_id>/delete', methods=['POST'])
@check_session_validity
@limiter.limit(STRATEGY_RATE_LIMIT)
def delete_strategy_route(strategy_id):
    """Delete strategy"""
    user_id = session.get('user')
    if not user_id:
        return jsonify({'status': 'error', 'error': 'Session expired'}), 401
        
    strategy = get_strategy(strategy_id)
    if not strategy:
        return jsonify({'status': 'error', 'error': 'Strategy not found'}), 404
    
    # Check if strategy belongs to user
    if strategy.user_id != user_id:
        return jsonify({'status': 'error', 'error': 'Unauthorized'}), 403
    
    try:
        # Remove squareoff job if exists
        try:
            scheduler.remove_job(f'squareoff_{strategy_id}')
        except Exception:
            pass
        
        # For custom strategies, cancel scheduled execution
        if strategy.strategy_type == 'custom':
            try:
                from custom_strategies import get_strategy_executor
                executor = get_strategy_executor()
                executor.cancel_scheduled_strategy(strategy_id)
            except Exception as e:
                logger.error(f"Error cancelling custom strategy schedule: {str(e)}")
            
        if delete_strategy(strategy_id):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'error': 'Failed to delete strategy'}), 500
    except Exception as e:
        logger.error(f'Error deleting strategy {strategy_id}: {str(e)}')
        return jsonify({'status': 'error', 'error': str(e)}), 500

@strategy_bp.route('/<int:strategy_id>/configure', methods=['GET', 'POST'])
@check_session_validity
@limiter.limit(STRATEGY_RATE_LIMIT)
def configure_symbols(strategy_id):
    """Configure symbols for strategy"""
    user_id = session.get('user')
    if not user_id:
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('auth.login'))
        
    strategy = get_strategy(strategy_id)
    if not strategy:
        abort(404)
    
    # Check if strategy belongs to user
    if strategy.user_id != user_id:
        abort(403)
    
    if request.method == 'POST':
        try:
            # Get data from either JSON or form
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            logger.info(f"Received data: {data}")
            
            # Handle bulk symbols
            if 'symbols' in data:
                symbols_text = data.get('symbols')
                mappings = []
                
                for line in symbols_text.strip().split('\n'):
                    if not line.strip():
                        continue
                    
                    parts = line.strip().split(',')
                    if len(parts) != 4:
                        raise ValueError(f'Invalid format in line: {line}')
                    
                    symbol, exchange, quantity, product = parts
                    if exchange not in VALID_EXCHANGES:
                        raise ValueError(f'Invalid exchange: {exchange}')
                    
                    mappings.append({
                        'symbol': symbol.strip(),
                        'exchange': exchange.strip(),
                        'quantity': int(quantity),
                        'product_type': product.strip()
                    })
                
                if mappings:
                    bulk_add_symbol_mappings(strategy_id, mappings)
                    return jsonify({'status': 'success'})
            
            # Handle single symbol
            else:
                symbol = data.get('symbol')
                exchange = data.get('exchange')
                quantity = data.get('quantity')
                product_type = data.get('product_type')
                
                logger.info(f"Processing single symbol: symbol={symbol}, exchange={exchange}, quantity={quantity}, product_type={product_type}")
                
                if not all([symbol, exchange, quantity, product_type]):
                    missing = []
                    if not symbol: missing.append('symbol')
                    if not exchange: missing.append('exchange')
                    if not quantity: missing.append('quantity')
                    if not product_type: missing.append('product_type')
                    raise ValueError(f'Missing required fields: {", ".join(missing)}')
                
                if exchange not in VALID_EXCHANGES:
                    raise ValueError(f'Invalid exchange: {exchange}')
                
                try:
                    quantity = int(quantity)
                except ValueError:
                    raise ValueError('Quantity must be a valid number')
                
                if quantity <= 0:
                    raise ValueError('Quantity must be greater than 0')
                
                mapping = add_symbol_mapping(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    exchange=exchange,
                    quantity=quantity,
                    product_type=product_type
                )
                
                if mapping:
                    return jsonify({'status': 'success'})
                else:
                    raise ValueError('Failed to add symbol mapping')
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f'Error configuring symbols: {error_msg}')
            return jsonify({'status': 'error', 'error': error_msg}), 400
    
    symbol_mappings = get_symbol_mappings(strategy_id)
    return render_template('strategy/configure_symbols.html', 
                         strategy=strategy, 
                         symbol_mappings=symbol_mappings,
                         exchanges=VALID_EXCHANGES)

@strategy_bp.route('/<int:strategy_id>/symbol/<int:mapping_id>/delete', methods=['POST'])
@check_session_validity
@limiter.limit(STRATEGY_RATE_LIMIT)
def delete_symbol(strategy_id, mapping_id):
    """Delete symbol mapping"""
    username = session.get('user')
    if not username:
        return jsonify({'status': 'error', 'error': 'Session expired'}), 401
        
    strategy = get_strategy(strategy_id)
    if not strategy or strategy.user_id != username:
        return jsonify({'status': 'error', 'error': 'Strategy not found'}), 404
    
    try:
        if delete_symbol_mapping(mapping_id):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'error': 'Symbol mapping not found'}), 404
    except Exception as e:
        logger.error(f'Error deleting symbol mapping: {str(e)}')
        return jsonify({'status': 'error', 'error': str(e)}), 400

@strategy_bp.route('/search')
@check_session_validity
def search_symbols():
    """Search symbols endpoint"""
    query = request.args.get('q', '').strip()
    exchange = request.args.get('exchange')
    
    if not query:
        return jsonify({'results': []})
    
    results = enhanced_search_symbols(query, exchange)
    return jsonify({
        'results': [{
            'symbol': result.symbol,
            'name': result.name,
            'exchange': result.exchange
        } for result in results]
    })

# Custom Strategy Execution Endpoints

@strategy_bp.route('/execute/<webhook_id>', methods=['POST'])
@limiter.limit(CUSTOM_STRATEGY_RATE_LIMIT)
def execute_custom_strategy(webhook_id):
    """Execute custom strategy endpoint"""
    try:
        # Get strategy by webhook ID
        strategy = get_strategy_by_webhook_id(webhook_id)
        if not strategy:
            return jsonify({'error': 'Invalid webhook ID'}), 404
        
        # Check if it's a custom strategy
        if strategy.strategy_type != 'custom':
            return jsonify({'error': 'Not a custom strategy'}), 400
        
        # Check if strategy is active
        if not strategy.is_active:
            return jsonify({'error': 'Strategy is inactive'}), 400
        
        # Get execution mode from query parameters or use strategy default
        execution_mode = request.args.get('mode', strategy.execution_mode)
        
        # Validate execution mode
        if execution_mode not in ['immediate', 'queue', 'schedule']:
            return jsonify({'error': 'Invalid execution mode'}), 400
        
        # Get additional parameters from request
        strategy_params = request.json if request.is_json else {}
        
        # Import and get strategy executor
        from custom_strategies import get_strategy_executor
        executor = get_strategy_executor()
        
        # Execute based on mode
        if execution_mode == 'immediate':
            result = executor.execute_strategy_immediate(
                strategy.id, 
                strategy_params=strategy_params
            )
            
            if result.success:
                # Process the signals - place orders for returned symbols
                order_results = process_strategy_signals(strategy, result.signals)
                
                return jsonify({
                    'status': 'success',
                    'message': f'Strategy executed successfully',
                    'signals': result.signals,
                    'execution_time': result.execution_time,
                    'orders_placed': len(order_results),
                    'execution_logs': result.logs
                }), 200
            else:
                return jsonify({
                    'status': 'error',
                    'error': result.error,
                    'execution_logs': result.logs
                }), 500
                
        elif execution_mode == 'queue':
            success = executor.execute_strategy_queue(
                strategy.id,
                strategy_params=strategy_params
            )
            
            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Strategy queued for execution'
                }), 202
            else:
                return jsonify({
                    'status': 'error',
                    'error': 'Failed to queue strategy'
                }), 500
                
        elif execution_mode == 'schedule':
            # Get schedule configuration from request or use strategy default
            schedule_config = strategy_params.get('schedule_config', strategy.schedule_config)
            
            if not schedule_config:
                return jsonify({
                    'status': 'error',
                    'error': 'Schedule configuration required'
                }), 400
            
            success = executor.schedule_strategy_execution(strategy.id, schedule_config)
            
            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Strategy scheduled for execution',
                    'schedule_config': schedule_config
                }), 200
            else:
                return jsonify({
                    'status': 'error',
                    'error': 'Failed to schedule strategy'
                }), 500
                
    except Exception as e:
        logger.error(f'Error executing custom strategy {webhook_id}: {str(e)}')
        return jsonify({
            'status': 'error',
            'error': 'Internal server error'
        }), 500

def process_strategy_signals(strategy, signals):
    """Process trading signals from custom strategy"""
    try:
        if not signals:
            return []
        
        # Get API key for the user
        api_key = get_api_key_for_tradingview(strategy.user_id)
        if not api_key:
            logger.error(f'No API key found for strategy {strategy.id}')
            return []
        
        # Get symbol mappings for the strategy
        mappings = get_symbol_mappings(strategy.id)
        symbol_map = {mapping.symbol: mapping for mapping in mappings}
        
        order_results = []
        
        for symbol in signals:
            # Check if we have a mapping for this symbol
            if symbol not in symbol_map:
                logger.warning(f'No mapping found for symbol {symbol} in strategy {strategy.id}')
                continue
            
            mapping = symbol_map[symbol]
            
            # Prepare order payload
            payload = {
                'apikey': api_key,
                'symbol': mapping.symbol,
                'exchange': mapping.exchange,
                'product': mapping.product_type,
                'strategy': strategy.name,
                'action': 'BUY',  # Default action, can be customized
                'quantity': str(mapping.quantity),
                'pricetype': 'MARKET',
                'price': '0',
                'trigger_price': '0',
                'disclosed_quantity': '0'
            }
            
            # Queue the order
            queue_order('placeorder', payload)
            order_results.append({
                'symbol': symbol,
                'action': 'BUY',
                'quantity': mapping.quantity,
                'status': 'queued'
            })
            
            logger.info(f'Queued order for {symbol} from custom strategy {strategy.name}')
        
        return order_results
        
    except Exception as e:
        logger.error(f'Error processing strategy signals: {str(e)}')
        return []

@strategy_bp.route('/custom/available', methods=['GET'])
@check_session_validity
def get_available_custom_strategies():
    """Get list of available custom strategies"""
    try:
        from custom_strategies import StrategyLoader
        loader = StrategyLoader()
        strategies = loader.get_strategy_list()
        
        return jsonify({
            'status': 'success',
            'strategies': strategies
        }), 200
        
    except Exception as e:
        logger.error(f'Error getting available custom strategies: {str(e)}')
        return jsonify({
            'status': 'error',
            'error': 'Failed to load available strategies'
        }), 500

@strategy_bp.route('/custom/<int:strategy_id>/status', methods=['GET'])
@check_session_validity
def get_custom_strategy_status(strategy_id):
    """Get execution status for custom strategy"""
    try:
        # Check if user owns the strategy
        user_id = session.get('user')
        strategy = get_strategy(strategy_id)
        
        if not strategy or strategy.user_id != user_id:
            return jsonify({'error': 'Strategy not found'}), 404
        
        if strategy.strategy_type != 'custom':
            return jsonify({'error': 'Not a custom strategy'}), 400
        
        # Get execution status
        from custom_strategies import get_strategy_executor
        executor = get_strategy_executor()
        
        execution_history = executor.get_execution_history(strategy_id, limit=10)
        queue_status = executor.get_queue_status()
        
        return jsonify({
            'status': 'success',
            'strategy_id': strategy_id,
            'is_active': strategy.is_active,
            'execution_mode': strategy.execution_mode,
            'recent_executions': [
                {
                    'timestamp': result.timestamp.isoformat(),
                    'success': result.success,
                    'signals': result.signals,
                    'error': result.error,
                    'execution_time': result.execution_time
                }
                for result in execution_history
            ],
            'queue_status': queue_status
        }), 200
        
    except Exception as e:
        logger.error(f'Error getting custom strategy status: {str(e)}')
        return jsonify({
            'status': 'error',
            'error': 'Failed to get strategy status'
        }), 500

@strategy_bp.route('/webhook/<webhook_id>', methods=['POST'])
@limiter.limit(WEBHOOK_RATE_LIMIT)
def webhook(webhook_id):
    """Handle webhook from trading platform"""
    try:
        strategy = get_strategy_by_webhook_id(webhook_id)
        if not strategy:
            return jsonify({'error': 'Invalid webhook ID'}), 404
        
        if not strategy.is_active:
            return jsonify({'error': 'Strategy is inactive'}), 400
        
        # Handle custom strategy webhook
        if strategy.strategy_type == 'custom':
            # For custom strategies, trigger execution via the custom strategy endpoint
            return execute_custom_strategy(webhook_id)
        
        # Continue with existing webhook logic for traditional strategies
        # Check trading hours for intraday strategies
        if strategy.is_intraday:
            now = datetime.now(pytz.timezone('Asia/Kolkata'))
            current_time = now.strftime('%H:%M')
            
            # Determine if this is an entry or exit order
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data received'}), 400
            
            action = data['action'].upper()
            position_size = int(data.get('position_size', 0))
            
            is_exit_order = False
            if strategy.trading_mode == 'LONG':
                is_exit_order = action == 'SELL'
            elif strategy.trading_mode == 'SHORT':
                is_exit_order = action == 'BUY'
            else:  # BOTH mode
                is_exit_order = position_size == 0
            
            # For entry orders, check if within entry time window
            if not is_exit_order:
                if strategy.start_time and current_time < strategy.start_time:
                    return jsonify({'error': 'Entry orders not allowed before start time'}), 400
                
                if strategy.end_time and current_time > strategy.end_time:
                    return jsonify({'error': 'Entry orders not allowed after end time'}), 400
            
            # For exit orders, check if within exit time window (up to square off time)
            else:
                if strategy.start_time and current_time < strategy.start_time:
                    return jsonify({'error': 'Exit orders not allowed before start time'}), 400
                
                if strategy.squareoff_time and current_time > strategy.squareoff_time:
                    return jsonify({'error': 'Exit orders not allowed after square off time'}), 400
        
        # Parse webhook data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        # Validate required fields
        required_fields = ['symbol', 'action']
        if strategy.trading_mode == 'BOTH':
            required_fields.append('position_size')
            
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
            
        # Validate action based on trading mode
        action = data['action'].upper()
        position_size = int(data.get('position_size', 0))
        
        if strategy.trading_mode == 'LONG':
            if action not in ['BUY', 'SELL']:
                return jsonify({'error': 'Invalid action for LONG mode. Use BUY to enter, SELL to exit'}), 400
            use_smart_order = action == 'SELL'
        elif strategy.trading_mode == 'SHORT':
            if action not in ['BUY', 'SELL']:
                return jsonify({'error': 'Invalid action for SHORT mode. Use SELL to enter, BUY to exit'}), 400
            use_smart_order = action == 'BUY'
        else:  # BOTH mode
            if action not in ['BUY', 'SELL']:
                return jsonify({'error': 'Invalid action. Use BUY or SELL'}), 400
            
            # Validate position size based on action
            if action == 'BUY' and position_size < 0:
                return jsonify({'error': 'For BUY orders in BOTH mode, position_size must be >= 0'}), 400
            if action == 'SELL' and position_size > 0:
                return jsonify({'error': 'For SELL orders in BOTH mode, position_size must be <= 0'}), 400
            
            # Smart order logic:
            # - BUY with position_size=0 means exit SHORT position
            # - SELL with position_size=0 means exit LONG position
            use_smart_order = position_size == 0
            
        # Get symbol mapping
        mapping = next((m for m in get_symbol_mappings(strategy.id) if m.symbol == data['symbol']), None)
        if not mapping:
            return jsonify({'error': f'No mapping found for symbol {data["symbol"]}'}), 400
            
        # Get API key from database
        api_key = get_api_key_for_tradingview(strategy.user_id)
        if not api_key:
            logger.error(f'No API key found for user {strategy.user_id}')
            return jsonify({'error': 'No API key found'}), 401

        # Prepare order payload
        payload = {
            'apikey': api_key,
            'symbol': mapping.symbol,
            'exchange': mapping.exchange,
            'product': mapping.product_type,
            'strategy': strategy.name,
            'action': action,
            'pricetype': 'MARKET'
        }
        
        # Set quantity based on order type
        if strategy.trading_mode == 'BOTH':
            # For BOTH mode, always use placesmartorder with direct position size
            # Set quantity to 0 if position_size is 0 (for exits)
            quantity = '0' if position_size == 0 else str(mapping.quantity)
            payload.update({
                'quantity': quantity,
                'position_size': str(position_size),  # Use position_size directly from webhook data
                'price': '0',
                'trigger_price': '0',
                'disclosed_quantity': '0'
            })
            endpoint = 'placesmartorder'
        else:
            # For LONG/SHORT modes, keep existing logic
            if use_smart_order:
                payload.update({
                    'quantity': '0',
                    'position_size': '0',  # This will close the position
                    'price': '0',
                    'trigger_price': '0',
                    'disclosed_quantity': '0'
                })
                endpoint = 'placesmartorder'
            else:
                # For regular orders, use absolute value of position_size if provided, otherwise use mapping quantity
                quantity = abs(position_size) if position_size != 0 else mapping.quantity
                payload.update({
                    'quantity': str(quantity)
                })
                endpoint = 'placeorder'
            
        # Queue the order
        queue_order(endpoint, payload)
        return jsonify({'message': f'Order queued successfully for {data["symbol"]}'}), 200
            
    except Exception as e:
        logger.error(f'Error processing webhook: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500
