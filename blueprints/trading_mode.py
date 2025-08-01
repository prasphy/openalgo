"""
Trading mode management blueprint.

This module provides API endpoints and utilities for managing and checking
the current trading mode (live vs paper).
"""

import os
from flask import Blueprint, jsonify, request
from services.trading_service_factory import (
    get_current_trading_mode, 
    is_paper_trading_enabled, 
    is_live_trading_enabled,
    TradingServiceFactory
)
from database.auth_db import verify_api_key
from limiter import limiter
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Create blueprint
trading_mode_bp = Blueprint('trading_mode', __name__, url_prefix='/api/v1')


@trading_mode_bp.route('/trading_mode', methods=['GET'])
@limiter.limit("10 per minute")
def get_trading_mode():
    """
    Get current trading mode information.
    
    Returns:
        JSON response with current trading mode and status
    """
    try:
        current_mode = get_current_trading_mode()
        is_paper = is_paper_trading_enabled()
        is_live = is_live_trading_enabled()
        
        # Get additional configuration info for paper mode
        config_info = {}
        if is_paper:
            config_info = {
                'paper_database_url': os.getenv('PAPER_TRADING_DATABASE_URL', 'sqlite:///db/paper_trading.db'),
                'default_balance': os.getenv('PAPER_DEFAULT_BALANCE', '50000.00'),
                'default_currency': os.getenv('PAPER_DEFAULT_CURRENCY', 'INR'),
                'cached_services': TradingServiceFactory.get_service_count()
            }
        
        response_data = {
            'status': 'success',
            'trading_mode': current_mode,
            'is_paper_trading': is_paper,
            'is_live_trading': is_live,
            'environment_variable': 'OPENALGO_TRADING_MODE',
            'message': f'Currently in {current_mode.upper()} trading mode',
            'config': config_info,
            'warning': '⚠️ No real money will be used in paper trading mode' if is_paper else '⚠️ CAUTION: Real money trading is active!'
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting trading mode: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get trading mode: {str(e)}'
        }), 500


@trading_mode_bp.route('/trading_mode/check', methods=['POST'])
@limiter.limit("5 per minute")
def check_user_trading_mode():
    """
    Check trading mode for authenticated user with API key.
    
    Returns:
        JSON response with trading mode and user-specific information
    """
    try:
        # Get API key from request
        api_key = request.json.get('apikey') if request.json else None
        if not api_key:
            return jsonify({
                'status': 'error',
                'message': 'API key required'
            }), 400
        
        # Verify API key
        user_id = verify_api_key(api_key)
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'Invalid API key'
            }), 403
        
        current_mode = get_current_trading_mode()
        is_paper = is_paper_trading_enabled()
        
        # Get user-specific info
        user_info = {
            'user_id': user_id,
            'trading_mode': current_mode,
            'is_paper_trading': is_paper
        }
        
        # Add paper trading specific info
        if is_paper:
            try:
                from database.paper_trading_db import get_account_statistics
                stats = get_account_statistics(user_id)
                user_info['paper_account_stats'] = stats
            except Exception as e:
                logger.warning(f"Could not get paper account stats: {e}")
                user_info['paper_account_stats'] = {}
        
        return jsonify({
            'status': 'success',
            'data': user_info,
            'message': f'User {user_id} is in {current_mode.upper()} trading mode'
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking user trading mode: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to check trading mode: {str(e)}'
        }), 500


@trading_mode_bp.route('/trading_mode/switch_info', methods=['GET'])
@limiter.limit("5 per minute")
def get_mode_switch_info():
    """
    Get information about how to switch trading modes.
    
    Returns:
        JSON response with instructions for switching modes
    """
    try:
        current_mode = get_current_trading_mode()
        opposite_mode = 'live' if current_mode == 'paper' else 'paper'
        
        instructions = {
            'current_mode': current_mode,
            'to_switch_to': opposite_mode,
            'steps': [
                'Stop the OpenAlgo application',
                f'Edit your .env file',
                f'Change OPENALGO_TRADING_MODE from "{current_mode}" to "{opposite_mode}"',
                'Save the .env file',
                'Restart the OpenAlgo application',
                f'Verify the mode change using GET /api/v1/trading_mode'
            ],
            'env_file_example': f'OPENALGO_TRADING_MODE={opposite_mode}',
            'warnings': {
                'paper_to_live': [
                    '⚠️ DANGER: Switching to live mode will use REAL MONEY',
                    '⚠️ Ensure you have proper risk management in place',
                    '⚠️ Test your strategies thoroughly in paper mode first'
                ] if current_mode == 'paper' else [],
                'live_to_paper': [
                    '✅ Safe: Paper mode uses simulated money only',
                    '✅ Good for testing strategies and learning',
                    '✅ All existing API endpoints work identically'
                ] if current_mode == 'live' else []
            },
            'restart_required': True,
            'data_isolation': 'Paper and live trading data are completely separate'
        }
        
        return jsonify({
            'status': 'success',
            'data': instructions,
            'message': f'Instructions to switch from {current_mode} to {opposite_mode} mode'
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting switch info: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get switch info: {str(e)}'
        }), 500


@trading_mode_bp.route('/trading_mode/clear_cache', methods=['POST'])
@limiter.limit("2 per minute")
def clear_trading_service_cache():
    """
    Clear the trading service cache (admin function).
    
    This can be useful when switching modes or troubleshooting.
    """
    try:
        # Get API key from request
        api_key = request.json.get('apikey') if request.json else None
        if not api_key:
            return jsonify({
                'status': 'error',
                'message': 'API key required'
            }), 400
        
        # Verify API key
        user_id = verify_api_key(api_key)
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'Invalid API key'
            }), 403
        
        # Clear cache
        cached_count = TradingServiceFactory.get_service_count()
        TradingServiceFactory.clear_cache()
        
        logger.info(f"Trading service cache cleared by user {user_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Cleared {cached_count} cached trading services',
            'cleared_services': cached_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear cache: {str(e)}'
        }), 500