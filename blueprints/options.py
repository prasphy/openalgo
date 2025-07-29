from flask import Blueprint, jsonify, request, render_template, session, redirect, url_for, Response
from database.auth_db import get_auth_token
from utils.session import check_session_validity
from utils.logging import get_logger
import json

logger = get_logger(__name__)

# Define the blueprint
options_bp = Blueprint('options_bp', __name__, url_prefix='/')

@options_bp.route('/options-terminal')
@check_session_validity
def options_terminal():
    """Render the Options Trading Terminal page"""
    try:
        # Check if user has proper role access (Administrator or Pro Trader)
        user_role = session.get('user_role')
        if user_role and user_role not in ['Administrator', 'Pro Trader']:
            logger.warning(f"User {session.get('user')} with role {user_role} attempted to access Options Terminal")
            return redirect(url_for('dashboard_bp.dashboard'))
        
        # Get broker information from session
        broker = session.get('broker')
        login_username = session.get('user')
        
        if not broker:
            logger.error("Broker not set in session")
            return redirect(url_for('dashboard_bp.dashboard'))
        
        # Get auth token for potential API calls
        auth_token = get_auth_token(login_username)
        
        if auth_token is None:
            logger.warning(f"No auth token found for user {login_username}")
            return redirect(url_for('auth.logout'))
        
        # Initialize default data for the options terminal
        market_data = {
            'underlying_price': 21832.15,
            'pcr_value': 0.87,
            'max_pain': 21800,
            'implied_volatility': 18.45
        }
        
        # Pass any necessary data to the template
        template_data = {
            'broker': broker,
            'market_data': market_data,
            'user': login_username,
            'user_role': user_role
        }
        
        logger.info(f"Options Terminal accessed by user {login_username} with broker {broker}")
        return render_template('options_terminal.html', **template_data)
        
    except Exception as e:
        logger.error(f"Error in options_terminal route: {str(e)}")
        return redirect(url_for('dashboard_bp.dashboard'))

@options_bp.route('/api/options/chain-data', methods=['GET'])
@check_session_validity
def get_options_chain():
    """API endpoint to fetch options chain data"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        expiry = request.args.get('expiry')
        strike_range = request.args.get('range', '20')
        
        # For now, return mock data - this would be replaced with actual broker API calls
        mock_chain_data = {
            'status': 'success',
            'symbol': symbol,
            'expiry': expiry,
            'underlying_price': 21832.15,
            'options': [
                {
                    'strike': 21700,
                    'call': {
                        'oi': 15420,
                        'volume': 2450,
                        'iv': 22.15,
                        'ltp': 145.30,
                        'bid': 144.50,
                        'ask': 146.10,
                        'change': 8.25
                    },
                    'put': {
                        'oi': 45680,
                        'volume': 8920,
                        'iv': 28.40,
                        'ltp': 22.55,
                        'bid': 22.30,
                        'ask': 22.80,
                        'change': -3.45
                    }
                },
                {
                    'strike': 21750,
                    'call': {
                        'oi': 18750,
                        'volume': 3200,
                        'iv': 20.85,
                        'ltp': 165.80,
                        'bid': 165.00,
                        'ask': 166.60,
                        'change': 12.40
                    },
                    'put': {
                        'oi': 52100,
                        'volume': 12340,
                        'iv': 26.20,
                        'ltp': 28.65,
                        'bid': 28.40,
                        'ask': 28.90,
                        'change': -2.15
                    }
                },
                {
                    'strike': 21800,
                    'call': {
                        'oi': 22890,
                        'volume': 4850,
                        'iv': 19.75,
                        'ltp': 188.45,
                        'bid': 187.60,
                        'ask': 189.30,
                        'change': 15.80
                    },
                    'put': {
                        'oi': 68450,
                        'volume': 15670,
                        'iv': 24.80,
                        'ltp': 36.45,
                        'bid': 36.20,
                        'ask': 36.70,
                        'change': -1.25
                    }
                }
            ]
        }
        
        return jsonify(mock_chain_data)
        
    except Exception as e:
        logger.error(f"Error in get_options_chain: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error fetching options chain: {str(e)}'
        }), 500

@options_bp.route('/api/options/place-order', methods=['POST'])
@check_session_validity
def place_options_order():
    """API endpoint to place options orders"""
    try:
        # Get data from request
        data = request.json
        symbol = data.get('symbol')
        order_type = data.get('type')
        quantity = data.get('quantity')
        price_type = data.get('priceType')
        price = data.get('price')
        
        if not all([symbol, order_type, quantity, price_type]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameters'
            }), 400
        
        # Get auth token from session
        login_username = session['user']
        auth_token = get_auth_token(login_username)
        broker_name = session.get('broker')
        
        if not auth_token or not broker_name:
            return jsonify({
                'status': 'error',
                'message': 'Authentication error'
            }), 401
        
        # For now, return a mock success response
        # In production, this would integrate with the actual broker API
        mock_response = {
            'status': 'success',
            'message': f'Options order placed successfully for {symbol}',
            'orderid': f'OPT{abs(hash(symbol + str(quantity)))%10000:04d}',
            'details': {
                'symbol': symbol,
                'type': order_type,
                'quantity': quantity,
                'price_type': price_type,
                'price': price if price_type == 'LIMIT' else 'MARKET'
            }
        }
        
        logger.info(f"Options order placed by {login_username}: {symbol} {order_type} {quantity}")
        return jsonify(mock_response)
        
    except Exception as e:
        logger.error(f"Error in place_options_order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error placing order: {str(e)}'
        }), 500

@options_bp.route('/api/options/greeks', methods=['GET'])
@check_session_validity
def get_option_greeks():
    """API endpoint to fetch option Greeks for a specific option"""
    try:
        symbol = request.args.get('symbol')
        
        if not symbol:
            return jsonify({
                'status': 'error',
                'message': 'Symbol parameter required'
            }), 400
        
        # Mock Greeks data - in production, this would be calculated or fetched from broker
        mock_greeks = {
            'status': 'success',
            'symbol': symbol,
            'greeks': {
                'delta': round(0.3 + (hash(symbol) % 100) / 100 * 0.7, 3),
                'gamma': round(0.05 + (hash(symbol) % 50) / 1000, 3),
                'theta': round(-0.02 - (hash(symbol) % 30) / 1000, 3),
                'vega': round(0.1 + (hash(symbol) % 40) / 1000, 3),
                'rho': round(0.01 + (hash(symbol) % 20) / 10000, 4)
            },
            'last_updated': '2024-01-15T10:30:00+05:30'
        }
        
        return jsonify(mock_greeks)
        
    except Exception as e:
        logger.error(f"Error in get_option_greeks: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error fetching Greeks: {str(e)}'
        }), 500

@options_bp.route('/api/options/market-data', methods=['GET'])
@check_session_validity
def get_market_data():
    """API endpoint to fetch market overview data"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        
        # Mock market data - in production, this would be fetched from real market feeds
        mock_market_data = {
            'status': 'success',
            'symbol': symbol,
            'data': {
                'underlying_price': 21832.15,
                'change': 124.30,
                'change_percent': 0.57,
                'pcr_value': 0.87,
                'max_pain': 21800,
                'implied_volatility': 18.45,
                'support_levels': [21750, 21700, 21650],
                'resistance_levels': [21900, 21950, 22000]
            },
            'last_updated': '2024-01-15T10:30:00+05:30'
        }
        
        return jsonify(mock_market_data)
        
    except Exception as e:
        logger.error(f"Error in get_market_data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error fetching market data: {str(e)}'
        }), 500

@options_bp.route('/api/options/strategies', methods=['GET'])
@check_session_validity
def get_option_strategies():
    """API endpoint to fetch available option strategies"""
    try:
        strategies = {
            'status': 'success',
            'strategies': [
                {
                    'id': 'long-straddle',
                    'name': 'Long Straddle',
                    'description': 'Buy call and put at the same strike price',
                    'category': 'volatility',
                    'legs': [
                        {'action': 'BUY', 'type': 'CALL', 'strike_offset': 0},
                        {'action': 'BUY', 'type': 'PUT', 'strike_offset': 0}
                    ]
                },
                {
                    'id': 'long-strangle',
                    'name': 'Long Strangle',
                    'description': 'Buy call and put at different strike prices',
                    'category': 'volatility',
                    'legs': [
                        {'action': 'BUY', 'type': 'CALL', 'strike_offset': 50},
                        {'action': 'BUY', 'type': 'PUT', 'strike_offset': -50}
                    ]
                },
                {
                    'id': 'iron-condor',
                    'name': 'Iron Condor',
                    'description': 'Sell call and put spreads for range-bound markets',
                    'category': 'income',
                    'legs': [
                        {'action': 'BUY', 'type': 'PUT', 'strike_offset': -100},
                        {'action': 'SELL', 'type': 'PUT', 'strike_offset': -50},
                        {'action': 'SELL', 'type': 'CALL', 'strike_offset': 50},
                        {'action': 'BUY', 'type': 'CALL', 'strike_offset': 100}
                    ]
                },
                {
                    'id': 'bull-call-spread',
                    'name': 'Bull Call Spread',
                    'description': 'Buy lower strike call, sell higher strike call',
                    'category': 'directional',
                    'legs': [
                        {'action': 'BUY', 'type': 'CALL', 'strike_offset': 0},
                        {'action': 'SELL', 'type': 'CALL', 'strike_offset': 50}
                    ]
                }
            ]
        }
        
        return jsonify(strategies)
        
    except Exception as e:
        logger.error(f"Error in get_option_strategies: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error fetching strategies: {str(e)}'
        }), 500