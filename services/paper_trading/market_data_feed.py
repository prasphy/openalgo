"""
Market data feed for paper trading.

This module integrates with live broker APIs to fetch real-time market data
for paper trading simulation. It provides price caching and fallback mechanisms
to ensure reliable market data availability.
"""

import importlib
import threading
import time
from decimal import Decimal
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from cachetools import TTLCache
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


class MarketDataFeed:
    """
    Market data feed for paper trading simulation.
    
    This class integrates with live broker APIs for real-time prices while
    providing caching and fallback mechanisms for reliable data access.
    """
    
    def __init__(self, broker: str, auth_token: str):
        """
        Initialize market data feed.
        
        Args:
            broker: Broker name (e.g., 'zerodha', 'angel', 'upstox')
            auth_token: Authentication token for broker API
        """
        self.broker = broker
        self.auth_token = auth_token
        self._lock = threading.Lock()
        
        # Price cache with 5-second TTL to reduce API calls
        self.price_cache = TTLCache(maxsize=1000, ttl=5)
        
        # Mock data for testing when broker API is unavailable
        self.use_mock_data = False
        self.mock_prices = {
            'RELIANCE-NSE': 2450.50,
            'TCS-NSE': 3850.25,
            'INFY-NSE': 1780.75,
            'HDFCBANK-NSE': 1650.30,
            'ICICIBANK-NSE': 980.45,
            'SBIN-NSE': 590.20,
            'ITC-NSE': 470.85,
            'HINDUNILVR-NSE': 2650.40,
            'LT-NSE': 3420.15,
            'BAJFINANCE-NSE': 6850.90
        }
        
        # Import broker module for API access
        self.broker_module = self._import_broker_module()
    
    def _import_broker_module(self) -> Optional[Any]:
        """
        Import broker-specific module for API access.
        
        Returns:
            Broker module or None if import fails
        """
        try:
            module_path = f'broker.{self.broker}.api.order_api'
            return importlib.import_module(module_path)
        except ImportError as e:
            logger.warning(f"Failed to import broker module for {self.broker}: {e}")
            logger.warning("Falling back to mock market data")
            self.use_mock_data = True
            return None
    
    def get_live_price(self, symbol: str, exchange: str) -> Optional[Decimal]:
        """
        Get current live price for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            
        Returns:
            Current price as Decimal or None if unavailable
        """
        cache_key = f"{symbol}-{exchange}"
        
        # Check cache first
        with self._lock:
            if cache_key in self.price_cache:
                cached_price = self.price_cache[cache_key]
                logger.debug(f"Retrieved cached price for {cache_key}: {cached_price}")
                return cached_price
        
        # Fetch fresh price
        price = self._fetch_price_from_api(symbol, exchange)
        
        if price is not None:
            # Cache the price
            with self._lock:
                self.price_cache[cache_key] = price
                logger.debug(f"Cached new price for {cache_key}: {price}")
        
        return price
    
    def _fetch_price_from_api(self, symbol: str, exchange: str) -> Optional[Decimal]:
        """
        Fetch price from broker API.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            
        Returns:
            Current price as Decimal or None if unavailable
        """
        if self.use_mock_data or not self.broker_module:
            return self._get_mock_price(symbol, exchange)
        
        try:
            # Try to get quotes from broker API
            if hasattr(self.broker_module, 'get_quotes'):
                quotes_data = self.broker_module.get_quotes(self.auth_token, symbol, exchange)
                
                # Extract LTP from quotes response
                if isinstance(quotes_data, dict):
                    # Different brokers have different response formats
                    price = self._extract_price_from_quotes(quotes_data)
                    if price is not None:
                        return Decimal(str(price))
            
            # Fallback to mock data if API fails
            logger.warning(f"Failed to get live price for {symbol}-{exchange}, using mock data")
            return self._get_mock_price(symbol, exchange)
            
        except Exception as e:
            logger.error(f"Error fetching price from {self.broker} API: {e}")
            return self._get_mock_price(symbol, exchange)
    
    def _extract_price_from_quotes(self, quotes_data: Dict[str, Any]) -> Optional[float]:
        """
        Extract price from broker quotes response.
        
        Args:
            quotes_data: Quotes response from broker API
            
        Returns:
            Extracted price or None
        """
        # Common price field names across different brokers
        price_fields = ['ltp', 'last_price', 'lastPrice', 'last_traded_price', 'close']
        
        for field in price_fields:
            if field in quotes_data and quotes_data[field] is not None:
                try:
                    return float(quotes_data[field])
                except (ValueError, TypeError):
                    continue
        
        # Try nested data structures
        if 'data' in quotes_data and isinstance(quotes_data['data'], dict):
            for field in price_fields:
                if field in quotes_data['data'] and quotes_data['data'][field] is not None:
                    try:
                        return float(quotes_data['data'][field])
                    except (ValueError, TypeError):
                        continue
        
        return None
    
    def _get_mock_price(self, symbol: str, exchange: str) -> Decimal:
        """
        Get mock price for testing purposes.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            
        Returns:
            Mock price as Decimal
        """
        cache_key = f"{symbol}-{exchange}"
        base_price = self.mock_prices.get(cache_key, 1000.0)
        
        # Add some realistic price movement (±2% random variation)
        import random
        variation = random.uniform(-0.02, 0.02)
        current_price = base_price * (1 + variation)
        
        # Update mock price for next call to simulate market movement
        self.mock_prices[cache_key] = current_price
        
        return Decimal(f"{current_price:.2f}")
    
    def get_price_with_retry(self, symbol: str, exchange: str, max_retries: int = 3) -> Optional[Decimal]:
        """
        Get price with retry mechanism.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            max_retries: Maximum number of retry attempts
            
        Returns:
            Current price as Decimal or None if all attempts fail
        """
        for attempt in range(max_retries):
            price = self.get_live_price(symbol, exchange)
            if price is not None:
                return price
            
            if attempt < max_retries - 1:
                # Wait briefly before retry
                time.sleep(0.5)
                logger.debug(f"Retrying price fetch for {symbol}-{exchange} (attempt {attempt + 2})")
        
        logger.error(f"Failed to get price for {symbol}-{exchange} after {max_retries} attempts")
        return None
    
    def bulk_get_prices(self, symbols: list) -> Dict[str, Optional[Decimal]]:
        """
        Get prices for multiple symbols efficiently.
        
        Args:
            symbols: List of (symbol, exchange) tuples
            
        Returns:
            Dictionary mapping "symbol-exchange" to prices
        """
        results = {}
        
        for symbol, exchange in symbols:
            cache_key = f"{symbol}-{exchange}"
            price = self.get_live_price(symbol, exchange)
            results[cache_key] = price
        
        return results
    
    def clear_cache(self):
        """Clear the price cache"""
        with self._lock:
            self.price_cache.clear()
            logger.info("Market data cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        with self._lock:
            return {
                'cache_size': len(self.price_cache),
                'max_size': self.price_cache.maxsize,
                'ttl': self.price_cache.ttl,
                'cached_symbols': list(self.price_cache.keys()),
                'using_mock_data': self.use_mock_data
            }
    
    def update_auth_token(self, new_auth_token: str):
        """
        Update authentication token.
        
        Args:
            new_auth_token: New authentication token
        """
        self.auth_token = new_auth_token
        self.clear_cache()  # Clear cache as auth context changed
        logger.info(f"Updated auth token for market data feed")


class MockMarketDataFeed(MarketDataFeed):
    """
    Mock market data feed for testing purposes.
    
    This class provides predictable price data for unit tests and development.
    """
    
    def __init__(self, broker: str = "mock", auth_token: str = "mock_token"):
        """Initialize mock market data feed"""
        super().__init__(broker, auth_token)
        self.use_mock_data = True
        self.broker_module = None
        
        # Predefined test prices
        self.mock_prices = {
            'RELIANCE-NSE': 2450.50,
            'TCS-NSE': 3850.25,
            'INFY-NSE': 1780.75,
            'TESTSTOCK-NSE': 100.00,
            'VOLATILE-NSE': 500.00
        }
    
    def set_price(self, symbol: str, exchange: str, price: float):
        """
        Set a specific price for testing.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            price: Price to set
        """
        cache_key = f"{symbol}-{exchange}"
        self.mock_prices[cache_key] = price
        
        # Also update cache
        with self._lock:
            self.price_cache[cache_key] = Decimal(str(price))
    
    def simulate_price_movement(self, symbol: str, exchange: str, percentage_change: float):
        """
        Simulate price movement for testing.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            percentage_change: Percentage change (e.g., 0.05 for 5% increase)
        """
        cache_key = f"{symbol}-{exchange}"
        current_price = self.mock_prices.get(cache_key, 100.0)
        new_price = current_price * (1 + percentage_change)
        self.set_price(symbol, exchange, new_price)