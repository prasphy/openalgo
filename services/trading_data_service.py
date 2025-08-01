"""
Trading data service for UI data retrieval.

This module implements the TradingDataService class that provides
data retrieval methods for all UI pages. It uses the TradingServiceFactory
to get the appropriate trading service instance based on the current mode
(paper trading or live trading).
"""

import logging
from typing import Dict, Any, Tuple, Optional
from services.trading_service_factory import get_trading_service
from services.interfaces.trading_service import ITradingService
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


class TradingDataServiceError(Exception):
    """Base exception for trading data service errors"""
    pass


class TradingDataService:
    """
    Service class for retrieving trading data for UI pages.
    
    This service provides methods to retrieve data for all major UI pages
    including positions, orderbook, tradebook, and dashboard. It automatically
    uses either paper trading or live trading services based on the current
    trading mode configuration.
    """
    
    def __init__(self, user_id: str, broker: str):
        """
        Initialize trading data service.
        
        Args:
            user_id: Unique identifier for the user
            broker: Broker name (e.g., 'zerodha', 'angel', 'upstox')
        """
        self.user_id = user_id
        self.broker = broker
        self.trading_service: Optional[ITradingService] = None
        
        # Initialize the trading service
        try:
            self.trading_service = get_trading_service(user_id, broker)
            logger.info(f"Initialized trading data service for user {user_id} with broker {broker}")
        except Exception as e:
            logger.error(f"Failed to initialize trading service: {e}")
            raise TradingDataServiceError(f"Failed to initialize trading service: {e}")
    
    def _ensure_trading_service(self):
        """
        Ensure trading service is available.
        
        Raises:
            TradingDataServiceError: If trading service is not available
        """
        if self.trading_service is None:
            raise TradingDataServiceError("Trading service not initialized")
    
    def get_positions_data(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get positions data for positions page.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing positions list and summary
            - HTTP status code (int)
        """
        try:
            self._ensure_trading_service()
            
            success, response_data, status_code = self.trading_service.get_positions(auth_token)
            
            if success:
                logger.info(f"Retrieved positions data for user {self.user_id}")
                return success, response_data, status_code
            else:
                logger.warning(f"Failed to retrieve positions data for user {self.user_id}: {response_data.get('message', 'Unknown error')}")
                return success, response_data, status_code
                
        except Exception as e:
            logger.error(f"Error retrieving positions data for user {self.user_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to retrieve positions data: {str(e)}'
            }, 500
    
    def get_orderbook_data(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get orderbook data for orderbook page.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing open orders list
            - HTTP status code (int)
        """
        try:
            self._ensure_trading_service()
            
            # Get open orders (active orders)
            success, response_data, status_code = self.trading_service.get_open_orders(auth_token)
            
            if success:
                logger.info(f"Retrieved orderbook data for user {self.user_id}")
                return success, response_data, status_code
            else:
                logger.warning(f"Failed to retrieve orderbook data for user {self.user_id}: {response_data.get('message', 'Unknown error')}")
                return success, response_data, status_code
                
        except Exception as e:
            logger.error(f"Error retrieving orderbook data for user {self.user_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to retrieve orderbook data: {str(e)}'
            }, 500
    
    def get_tradebook_data(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get tradebook data for tradebook page.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing trade history
            - HTTP status code (int)
        """
        try:
            self._ensure_trading_service()
            
            # Get trade history
            success, response_data, status_code = self.trading_service.get_trade_history(auth_token)
            
            if success:
                logger.info(f"Retrieved tradebook data for user {self.user_id}")
                return success, response_data, status_code
            else:
                logger.warning(f"Failed to retrieve tradebook data for user {self.user_id}: {response_data.get('message', 'Unknown error')}")
                return success, response_data, status_code
                
        except Exception as e:
            logger.error(f"Error retrieving tradebook data for user {self.user_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to retrieve tradebook data: {str(e)}'
            }, 500
    
    def get_dashboard_data(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get dashboard data for main dashboard page.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing dashboard summary information
            - HTTP status code (int)
        """
        try:
            self._ensure_trading_service()
            
            # Collect data from multiple sources for dashboard
            dashboard_data = {}
            
            # Get positions summary
            pos_success, pos_data, pos_status = self.trading_service.get_positions(auth_token)
            if pos_success:
                dashboard_data['positions'] = pos_data.get('data', [])
                dashboard_data['total_pnl'] = pos_data.get('total_pnl', 0.0)
            else:
                dashboard_data['positions'] = []
                dashboard_data['total_pnl'] = 0.0
                logger.warning(f"Failed to get positions for dashboard: {pos_data.get('message', 'Unknown error')}")
            
            # Get account balance
            bal_success, bal_data, bal_status = self.trading_service.get_account_balance(auth_token)
            if bal_success:
                dashboard_data['balance'] = bal_data.get('data', {})
            else:
                dashboard_data['balance'] = {}
                logger.warning(f"Failed to get account balance for dashboard: {bal_data.get('message', 'Unknown error')}")
            
            # Get open orders count
            ord_success, ord_data, ord_status = self.trading_service.get_open_orders(auth_token)
            if ord_success:
                dashboard_data['open_orders_count'] = len(ord_data.get('data', []))
            else:
                dashboard_data['open_orders_count'] = 0
                logger.warning(f"Failed to get open orders for dashboard: {ord_data.get('message', 'Unknown error')}")
            
            # Get recent trades (last 5)
            trade_success, trade_data, trade_status = self.trading_service.get_trade_history(auth_token)
            if trade_success:
                # Get last 5 trades
                all_trades = trade_data.get('data', [])
                dashboard_data['recent_trades'] = all_trades[:5] if isinstance(all_trades, list) else []
            else:
                dashboard_data['recent_trades'] = []
                logger.warning(f"Failed to get recent trades for dashboard: {trade_data.get('message', 'Unknown error')}")
            
            logger.info(f"Retrieved dashboard data for user {self.user_id}")
            return True, {
                'status': 'success',
                'data': dashboard_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error retrieving dashboard data for user {self.user_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to retrieve dashboard data: {str(e)}'
            }, 500
    
    def get_account_balance_data(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get account balance data.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing balance information
            - HTTP status code (int)
        """
        try:
            self._ensure_trading_service()
            
            success, response_data, status_code = self.trading_service.get_account_balance(auth_token)
            
            if success:
                logger.info(f"Retrieved account balance data for user {self.user_id}")
                return success, response_data, status_code
            else:
                logger.warning(f"Failed to retrieve account balance data for user {self.user_id}: {response_data.get('message', 'Unknown error')}")
                return success, response_data, status_code
                
        except Exception as e:
            logger.error(f"Error retrieving account balance data for user {self.user_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to retrieve account balance data: {str(e)}'
            }, 500
    
    def get_holdings_data(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get holdings data.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing holdings information
            - HTTP status code (int)
        """
        try:
            self._ensure_trading_service()
            
            success, response_data, status_code = self.trading_service.get_holdings(auth_token)
            
            if success:
                logger.info(f"Retrieved holdings data for user {self.user_id}")
                return success, response_data, status_code
            else:
                logger.warning(f"Failed to retrieve holdings data for user {self.user_id}: {response_data.get('message', 'Unknown error')}")
                return success, response_data, status_code
                
        except Exception as e:
            logger.error(f"Error retrieving holdings data for user {self.user_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to retrieve holdings data: {str(e)}'
            }, 500


# Convenience functions for easier integration
def get_trading_data_service(user_id: str, broker: str) -> TradingDataService:
    """
    Convenience function to get a trading data service instance.
    
    Args:
        user_id: User identifier
        broker: Broker name
        
    Returns:
        TradingDataService: Trading data service instance
    """
    return TradingDataService(user_id, broker)


def get_positions_data(user_id: str, broker: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
    """
    Convenience function to get positions data.
    
    Args:
        user_id: User identifier
        broker: Broker name
        auth_token: Authentication token
        
    Returns:
        Tuple containing:
        - Success status (bool)
        - Response data (dict)
        - HTTP status code (int)
    """
    service = TradingDataService(user_id, broker)
    return service.get_positions_data(auth_token)


def get_orderbook_data(user_id: str, broker: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
    """
    Convenience function to get orderbook data.
    
    Args:
        user_id: User identifier
        broker: Broker name
        auth_token: Authentication token
        
    Returns:
        Tuple containing:
        - Success status (bool)
        - Response data (dict)
        - HTTP status code (int)
    """
    service = TradingDataService(user_id, broker)
    return service.get_orderbook_data(auth_token)


def get_tradebook_data(user_id: str, broker: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
    """
    Convenience function to get tradebook data.
    
    Args:
        user_id: User identifier
        broker: Broker name
        auth_token: Authentication token
        
    Returns:
        Tuple containing:
        - Success status (bool)
        - Response data (dict)
        - HTTP status code (int)
    """
    service = TradingDataService(user_id, broker)
    return service.get_tradebook_data(auth_token)


def get_dashboard_data(user_id: str, broker: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
    """
    Convenience function to get dashboard data.
    
    Args:
        user_id: User identifier
        broker: Broker name
        auth_token: Authentication token
        
    Returns:
        Tuple containing:
        - Success status (bool)
        - Response data (dict)
        - HTTP status code (int)
    """
    service = TradingDataService(user_id, broker)
    return service.get_dashboard_data(auth_token)


def get_holdings_data(user_id: str, broker: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
    """
    Convenience function to get holdings data.
    
    Args:
        user_id: User identifier
        broker: Broker name
        auth_token: Authentication token
        
    Returns:
        Tuple containing:
        - Success status (bool)
        - Response data (dict)
        - HTTP status code (int)
    """
    service = TradingDataService(user_id, broker)
    return service.get_holdings_data(auth_token)