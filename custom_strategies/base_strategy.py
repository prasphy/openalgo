"""
Base Strategy Class for Custom Strategies

All custom strategies must inherit from this base class and implement
the execute() method.
"""

import requests
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Base class for all custom trading strategies.
    
    This class provides access to OpenAlgo APIs and defines the interface
    that all custom strategies must implement.
    """
    
    def __init__(self, api_key: str, strategy_config: Dict[str, Any], base_url: str = "http://127.0.0.1:5000"):
        """
        Initialize the strategy with API key and configuration.
        
        Args:
            api_key: OpenAlgo API key for authentication
            strategy_config: Dictionary containing strategy configuration
            base_url: Base URL for OpenAlgo API endpoints
        """
        self.api_key = api_key
        self.config = strategy_config
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
    def _make_api_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a request to OpenAlgo API.
        
        Args:
            endpoint: API endpoint (e.g., '/api/v1/quotes')
            data: Request payload
            
        Returns:
            API response as dictionary
            
        Raises:
            Exception: If API request fails
        """
        try:
            url = f"{self.base_url}{endpoint}"
            data['apikey'] = self.api_key
            
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            self.logger.error(f"API request failed for {endpoint}: {str(e)}")
            raise Exception(f"API request failed: {str(e)}")
    
    def get_quotes(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """
        Get real-time quotes for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            exchange: Exchange code (e.g., 'NSE', 'BSE')
            
        Returns:
            Quote data including LTP, bid/ask prices, etc.
        """
        data = {
            'symbol': symbol,
            'exchange': exchange
        }
        return self._make_api_request('/api/v1/quotes', data)
    
    def get_history(self, symbol: str, exchange: str, interval: str, 
                   start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            interval: Time interval ('1m', '5m', '15m', '30m', '1h', '1d')
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            
        Returns:
            Historical OHLCV data
        """
        data = {
            'symbol': symbol,
            'exchange': exchange,
            'interval': interval,
            'start_date': start_date,
            'end_date': end_date
        }
        return self._make_api_request('/api/v1/history', data)
    
    def get_depth(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """
        Get market depth for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            
        Returns:
            Market depth with bid/ask levels
        """
        data = {
            'symbol': symbol,
            'exchange': exchange
        }
        return self._make_api_request('/api/v1/depth', data)
    
    def search_symbols(self, query: str, exchange: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for symbols.
        
        Args:
            query: Search query
            exchange: Optional exchange filter
            
        Returns:
            List of matching symbols
        """
        data = {
            'query': query
        }
        if exchange:
            data['exchange'] = exchange
            
        return self._make_api_request('/api/v1/search', data)
    
    def get_symbol_info(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """
        Get detailed symbol information.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            
        Returns:
            Symbol information including token, lot size, etc.
        """
        data = {
            'symbol': symbol,
            'exchange': exchange
        }
        return self._make_api_request('/api/v1/symbol', data)
    
    def get_funds(self) -> Dict[str, Any]:
        """
        Get account funds and margin information.
        
        Returns:
            Account balance and margin details
        """
        data = {}
        return self._make_api_request('/api/v1/funds', data)
    
    def get_positions(self) -> Dict[str, Any]:
        """
        Get current positions.
        
        Returns:
            List of current positions
        """
        data = {}
        return self._make_api_request('/api/v1/positionbook', data)
    
    def get_orderbook(self) -> Dict[str, Any]:
        """
        Get order book.
        
        Returns:
            List of orders
        """
        data = {}
        return self._make_api_request('/api/v1/orderbook', data)
    
    def log_info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def log_warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def log_error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    @abstractmethod
    def execute(self) -> List[str]:
        """
        Execute the strategy logic.
        
        This method must be implemented by all custom strategies.
        It should contain the main trading logic and return a list
        of symbols that should be traded.
        
        Returns:
            List of symbols to trade based on strategy signals
        """
        pass
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
    
    def validate_symbol_list(self, symbols: List[str]) -> List[str]:
        """
        Validate and filter symbol list.
        
        Args:
            symbols: List of symbols to validate
            
        Returns:
            Validated list of symbols
        """
        if not isinstance(symbols, list):
            raise ValueError("Strategy must return a list of symbols")
        
        valid_symbols = []
        for symbol in symbols:
            if isinstance(symbol, str) and symbol.strip():
                valid_symbols.append(symbol.strip().upper())
        
        return valid_symbols