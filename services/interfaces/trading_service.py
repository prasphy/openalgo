"""
Trading service interface definition.

This module defines the abstract interface that all trading service implementations
must follow. It ensures that both live broker services and paper trading
services provide consistent method signatures and return types.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional


class TradingServiceError(Exception):
    """Base exception for trading service errors"""
    pass


class ITradingService(ABC):
    """
    Abstract interface for trading services.
    
    This interface defines the contract that all trading service implementations
    must follow. It ensures that both live broker services and paper trading
    services provide consistent method signatures and return types.
    
    All methods return a tuple of (success: bool, response_data: dict, status_code: int)
    to maintain consistency with the existing OpenAlgo API response format.
    """

    def __init__(self, user_id: str, broker: str):
        """
        Initialize the trading service.
        
        Args:
            user_id: Unique identifier for the user
            broker: Broker name (e.g., 'zerodha', 'angel', 'upstox')
        """
        self.user_id = user_id
        self.broker = broker

    @abstractmethod
    def place_order(self, order_data: Dict[str, Any], auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Place a trading order.
        
        Args:
            order_data: Order details containing symbol, exchange, action, quantity, etc.
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing order ID and status
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_positions(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get current trading positions.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing positions list
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_open_orders(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get currently open/pending orders.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing open orders list
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_trade_history(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get trade execution history.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing trade history
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Cancel a pending order.
        
        Args:
            order_id: Unique identifier of the order to cancel
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing cancellation status
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_account_balance(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get account balance and fund information.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing balance information
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_open_position(self, symbol: str, exchange: str, product: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get quantity of a specific open position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            product: Product type (MIS, CNC, NRML)
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing position quantity
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def modify_order(self, order_id: str, order_data: Dict[str, Any], auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Modify an existing order.
        
        Args:
            order_id: Unique identifier of the order to modify
            order_data: New order parameters
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing modification status
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str, exchange: str, product: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Close a specific position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            product: Product type (MIS, CNC, NRML)
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing closure status
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def close_all_positions(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Close all open positions.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing closure status
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def cancel_all_orders(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Cancel all pending orders.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing cancellation status
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_holdings(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get investment holdings.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing holdings information
            - HTTP status code (int)
        """
        pass

    @abstractmethod
    def get_order_history(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get complete order history.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing order history
            - HTTP status code (int)
        """
        pass

    # Additional abstract methods for paper trading specific functionality
    def reset_account(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Reset paper trading account (optional - only for paper trading).
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing reset status
            - HTTP status code (int)
        """
        return False, {'status': 'error', 'message': 'Not supported by this implementation'}, 501

    def get_trading_statistics(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get trading statistics (optional - enhanced for paper trading).
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing statistics
            - HTTP status code (int)
        """
        return False, {'status': 'error', 'message': 'Not supported by this implementation'}, 501