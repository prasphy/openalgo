"""
OpenAlgo Services Module

This module contains all service implementations for OpenAlgo, including:
- Trading service factory for live/paper trading mode switching
- Paper trading service for simulation
- Live broker service for real trading
- Market data feeds and order matching engines
"""

# Version information
__version__ = "1.0.0"
__author__ = "OpenAlgo Team"

# Import key classes for easier access
from .trading_service_factory import TradingServiceFactory, get_trading_service
from .interfaces.trading_service import ITradingService

# Make commonly used functions available at package level
def get_current_trading_mode():
    """Get current trading mode (live or paper)"""
    from .trading_service_factory import get_current_trading_mode
    return get_current_trading_mode()

def is_paper_trading_enabled():
    """Check if paper trading is enabled"""
    from .trading_service_factory import is_paper_trading_enabled
    return is_paper_trading_enabled()

def is_live_trading_enabled():
    """Check if live trading is enabled"""
    from .trading_service_factory import is_live_trading_enabled
    return is_live_trading_enabled()

__all__ = [
    'TradingServiceFactory',
    'get_trading_service',
    'ITradingService',
    'get_current_trading_mode',
    'is_paper_trading_enabled',
    'is_live_trading_enabled'
]