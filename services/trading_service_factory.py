"""
Trading service factory for dependency injection.

This module implements the factory pattern with dependency injection,
allowing the application to switch between live and paper trading modes
based on the TRADING_MODE environment variable without any code changes
in the business logic layer.
"""

import os
import threading
from typing import Dict, Optional
from utils.logging import get_logger
from services.interfaces.trading_service import ITradingService

# Initialize logger
logger = get_logger(__name__)


class TradingServiceFactory:
    """
    Factory class for creating trading service instances.
    
    This factory implements the strategy pattern with dependency injection,
    allowing the application to switch between live and paper trading modes
    based on the TRADING_MODE environment variable without any code changes
    in the business logic layer.
    """
    
    _instances: Dict[str, ITradingService] = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_trading_service(cls, user_id: str, broker: str) -> ITradingService:
        """
        Get or create a trading service instance for the specified user and broker.
        
        The factory uses the OPENALGO_TRADING_MODE environment variable to determine
        which implementation to instantiate:
        - 'paper': Returns PaperTradingService instance
        - 'live' (default): Returns LiveBrokerService instance
        
        Args:
            user_id: Unique identifier for the user
            broker: Broker name (e.g., 'zerodha', 'angel', 'upstox')
            
        Returns:
            ITradingService: Appropriate trading service implementation
            
        Raises:
            ValueError: If OPENALGO_TRADING_MODE contains an invalid value
            ImportError: If required service classes cannot be imported
        """
        cache_key = f"{user_id}_{broker}"
        
        # Use double-checked locking pattern for thread safety
        if cache_key not in cls._instances:
            with cls._lock:
                if cache_key not in cls._instances:
                    # Get trading mode from environment
                    trading_mode = cls._get_trading_mode()
                    
                    # Create new service instance based on trading mode
                    if trading_mode == 'paper':
                        instance = cls._create_paper_trading_service(user_id, broker)
                    else:
                        instance = cls._create_live_broker_service(user_id, broker)
                    
                    cls._instances[cache_key] = instance
                    logger.info(f"Created {trading_mode} trading service for user {user_id} with broker {broker}")
        
        return cls._instances[cache_key]
    
    @classmethod
    def _get_trading_mode(cls) -> str:
        """
        Get and validate the trading mode from environment variable.
        
        Returns:
            str: Trading mode ('live' or 'paper')
            
        Raises:
            ValueError: If OPENALGO_TRADING_MODE contains an invalid value
        """
        trading_mode = os.getenv('OPENALGO_TRADING_MODE', 'live').lower().strip()
        
        if trading_mode not in ['live', 'paper']:
            raise ValueError(f"Invalid OPENALGO_TRADING_MODE: '{trading_mode}'. Must be 'live' or 'paper'")
        
        return trading_mode
    
    @classmethod
    def _create_live_broker_service(cls, user_id: str, broker: str) -> ITradingService:
        """
        Create a live broker service instance.
        
        Args:
            user_id: User identifier
            broker: Broker name
            
        Returns:
            ITradingService: Live broker service instance
            
        Raises:
            ImportError: If LiveBrokerService cannot be imported
        """
        try:
            from services.live_broker_service import LiveBrokerService
            return LiveBrokerService(user_id, broker)
        except ImportError as e:
            logger.error(f"Failed to import LiveBrokerService: {e}")
            raise ImportError(f"Live broker service not available: {e}")
    
    @classmethod
    def _create_paper_trading_service(cls, user_id: str, broker: str) -> ITradingService:
        """
        Create a paper trading service instance.
        
        Args:
            user_id: User identifier
            broker: Broker name
            
        Returns:
            ITradingService: Paper trading service instance
            
        Raises:
            ImportError: If PaperTradingService cannot be imported
        """
        try:
            from services.paper_trading_service import PaperTradingService
            return PaperTradingService(user_id, broker)
        except ImportError as e:
            logger.error(f"Failed to import PaperTradingService: {e}")
            raise ImportError(f"Paper trading service not available: {e}")
    
    @classmethod
    def clear_cache(cls):
        """
        Clear the service instance cache.
        
        This method is useful for testing or when switching trading modes
        during runtime (though mode switching typically requires app restart).
        """
        with cls._lock:
            cls._instances.clear()
            logger.info("Trading service cache cleared")
    
    @classmethod
    def get_current_mode(cls) -> str:
        """
        Get the current trading mode.
        
        Returns:
            str: Current trading mode ('live' or 'paper')
        """
        try:
            return cls._get_trading_mode()
        except ValueError:
            return 'live'  # Default fallback
    
    @classmethod
    def is_paper_trading_mode(cls) -> bool:
        """
        Check if the application is currently in paper trading mode.
        
        Returns:
            bool: True if in paper trading mode, False otherwise
        """
        return cls.get_current_mode() == 'paper'
    
    @classmethod
    def is_live_trading_mode(cls) -> bool:
        """
        Check if the application is currently in live trading mode.
        
        Returns:
            bool: True if in live trading mode, False otherwise
        """
        return cls.get_current_mode() == 'live'
    
    @classmethod
    def get_service_count(cls) -> int:
        """
        Get the number of cached service instances.
        
        Returns:
            int: Number of cached instances
        """
        return len(cls._instances)
    
    @classmethod
    def get_cached_services(cls) -> Dict[str, str]:
        """
        Get information about cached services.
        
        Returns:
            Dict[str, str]: Dictionary mapping cache keys to service types
        """
        return {
            cache_key: type(service).__name__ 
            for cache_key, service in cls._instances.items()
        }


# Convenience functions for easier integration
def get_trading_service(user_id: str, broker: str) -> ITradingService:
    """
    Convenience function to get a trading service instance.
    
    This is a shorthand for TradingServiceFactory.get_trading_service()
    and is the recommended way to obtain trading service instances
    throughout the application.
    
    Args:
        user_id: User identifier
        broker: Broker name
        
    Returns:
        ITradingService: Appropriate trading service implementation
    """
    return TradingServiceFactory.get_trading_service(user_id, broker)


def get_current_trading_mode() -> str:
    """
    Get the current trading mode.
    
    Returns:
        str: Current trading mode ('live' or 'paper')
    """
    return TradingServiceFactory.get_current_mode()


def is_paper_trading_enabled() -> bool:
    """
    Convenience function to check if paper trading is enabled.
    
    Returns:
        bool: True if paper trading is enabled, False otherwise
    """
    return TradingServiceFactory.is_paper_trading_mode()


def is_live_trading_enabled() -> bool:
    """
    Convenience function to check if live trading is enabled.
    
    Returns:
        bool: True if live trading is enabled, False otherwise
    """
    return TradingServiceFactory.is_live_trading_mode()