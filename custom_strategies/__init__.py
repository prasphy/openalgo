"""
Custom Strategy System for OpenAlgo

This module provides the infrastructure for users to create and execute
custom Python-based trading strategies with full access to OpenAlgo APIs.
"""

__version__ = "1.0.0"
__author__ = "OpenAlgo Team"

from .base_strategy import BaseStrategy
from .strategy_loader import StrategyLoader
from .strategy_validator import StrategyValidator
from .strategy_executor import StrategyExecutor, StrategyExecutionResult, get_strategy_executor

__all__ = [
    "BaseStrategy", 
    "StrategyLoader", 
    "StrategyValidator", 
    "StrategyExecutor", 
    "StrategyExecutionResult",
    "get_strategy_executor"
]