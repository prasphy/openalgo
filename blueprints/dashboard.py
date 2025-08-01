from flask import Blueprint, render_template, session, redirect, url_for, g, jsonify, request
from database.auth_db import get_auth_token
from importlib import import_module
from utils.session import check_session_validity
import multiprocessing
import sys
from utils.logging import get_logger

logger = get_logger(__name__)

def dynamic_import(broker):
    try:
        module_path = f'broker.{broker}.api.funds'
        module = import_module(module_path)
        get_margin_data = getattr(module, 'get_margin_data')
        return get_margin_data
    except ImportError as e:
        logger.error(f"Error importing module: {e}")
        return None

dashboard_bp = Blueprint('dashboard_bp', __name__, url_prefix='/')
scalper_process = None

@dashboard_bp.route('/dashboard')
@check_session_validity
def dashboard():
    login_username = session['user']
    AUTH_TOKEN = get_auth_token(login_username)
    
    if AUTH_TOKEN is None:
        logger.warning(f"No auth token found for user {login_username}")
        return redirect(url_for('auth.logout'))

    broker = session.get('broker')
    if not broker:
        logger.error("Broker not set in session")
        return "Broker not set in session", 400
    
    # Use TradingDataService instead of direct broker API calls
    try:
        from services.trading_data_service import get_dashboard_data
        success, dashboard_data, status_code = get_dashboard_data(login_username, broker, AUTH_TOKEN)
        
        if not success:
            logger.error(f"Error retrieving dashboard data: {dashboard_data.get('message', 'Unknown error')}")
            if status_code == 401:
                return redirect(url_for('auth.logout'))
            return "Error retrieving dashboard data", status_code
            
        # Extract dashboard data from response
        data = dashboard_data.get('data', {})
        positions = data.get('positions', [])
        balance = data.get('balance', {})
        open_orders_count = data.get('open_orders_count', 0)
        recent_trades = data.get('recent_trades', [])
        total_pnl = data.get('total_pnl', 0.0)
        
        # Format margin data for UI compatibility
        margin_data = {
            'availablecash': str(balance.get('available_cash', '0.00')),
            'collateral': str(balance.get('collateral', '0.00')),
            'utiliseddebits': str(balance.get('utilised_debits', '0.00')),
            'total_pnl': str(total_pnl)
        }
        
        # Check if margin_data is empty (authentication failed)
        if not margin_data:
            logger.error(f"Failed to get margin data for user {login_username} - authentication may have expired")
            return redirect(url_for('auth.logout'))
        
        # Check if all values are zero (likely authentication error)
        if (margin_data.get('availablecash') == '0.00' and
            margin_data.get('collateral') == '0.00' and
            margin_data.get('utiliseddebits') == '0.00'):
            logger.warning(f"All margin data values are zero for user {login_username} - possible authentication issue")
        
        # Prepare dashboard data for template
        dashboard_template_data = {
            'margin_data': margin_data,
            'positions': positions,
            'open_orders_count': open_orders_count,
            'recent_trades': recent_trades
        }
        
        return render_template('dashboard.html', **dashboard_template_data)
        
    except Exception as e:
        logger.error(f"Error in dashboard endpoint: {str(e)}")
        return "Error retrieving dashboard data", 500
