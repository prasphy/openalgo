"""
Strategy Loader - Dynamically loads and manages custom strategies
"""

import os
import importlib.util
import inspect
from typing import Dict, List, Optional, Type
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyLoader:
    """
    Handles loading and management of custom strategy files.
    """
    
    def __init__(self, strategies_path: str = "custom_strategies"):
        """
        Initialize the strategy loader.
        
        Args:
            strategies_path: Path to the strategies directory
        """
        self.strategies_path = strategies_path
        self.loaded_strategies: Dict[str, Type[BaseStrategy]] = {}
        self._strategy_cache: Dict[str, Dict] = {}
    
    def discover_strategies(self) -> List[Dict[str, str]]:
        """
        Discover all available strategy files.
        
        Returns:
            List of strategy metadata dictionaries
        """
        strategies = []
        
        # Check examples directory
        examples_path = os.path.join(self.strategies_path, "examples")
        if os.path.exists(examples_path):
            strategies.extend(self._scan_directory(examples_path, "examples"))
        
        # Check user strategies directory
        user_path = os.path.join(self.strategies_path, "user_strategies")
        if os.path.exists(user_path):
            strategies.extend(self._scan_directory(user_path, "user_strategies"))
        
        return strategies
    
    def _scan_directory(self, directory: str, category: str) -> List[Dict[str, str]]:
        """
        Scan a directory for strategy files.
        
        Args:
            directory: Directory to scan
            category: Strategy category (examples/user_strategies)
            
        Returns:
            List of strategy metadata
        """
        strategies = []
        
        try:
            for filename in os.listdir(directory):
                if filename.endswith('.py') and not filename.startswith('__'):
                    file_path = os.path.join(directory, filename)
                    strategy_name = filename[:-3]  # Remove .py extension
                    
                    # Try to get strategy metadata
                    metadata = self._get_strategy_metadata(file_path, strategy_name, category)
                    if metadata:
                        strategies.append(metadata)
                        
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {str(e)}")
        
        return strategies
    
    def _get_strategy_metadata(self, file_path: str, strategy_name: str, category: str) -> Optional[Dict[str, str]]:
        """
        Extract metadata from a strategy file.
        
        Args:
            file_path: Path to strategy file
            strategy_name: Name of the strategy
            category: Strategy category
            
        Returns:
            Strategy metadata or None if invalid
        """
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(strategy_name, file_path)
            if not spec or not spec.loader:
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find strategy class
            strategy_class = None
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy and 
                    obj.__module__ == module.__name__):
                    strategy_class = obj
                    break
            
            if not strategy_class:
                logger.warning(f"No valid strategy class found in {file_path}")
                return None
            
            # Extract docstring and other metadata
            description = strategy_class.__doc__ or "No description available"
            description = description.strip().split('\n')[0]  # First line only
            
            return {
                'name': strategy_name,
                'display_name': strategy_name.replace('_', ' ').title(),
                'description': description,
                'file_path': file_path,
                'category': category,
                'class_name': strategy_class.__name__
            }
            
        except Exception as e:
            logger.error(f"Error loading strategy metadata from {file_path}: {str(e)}")
            return None
    
    def load_strategy(self, strategy_name: str, category: str = "user_strategies") -> Optional[Type[BaseStrategy]]:
        """
        Load a specific strategy class.
        
        Args:
            strategy_name: Name of the strategy file (without .py)
            category: Strategy category (examples/user_strategies)
            
        Returns:
            Strategy class or None if loading fails
        """
        cache_key = f"{category}/{strategy_name}"
        
        # Check if already loaded
        if cache_key in self.loaded_strategies:
            return self.loaded_strategies[cache_key]
        
        try:
            file_path = os.path.join(self.strategies_path, category, f"{strategy_name}.py")
            
            if not os.path.exists(file_path):
                logger.error(f"Strategy file not found: {file_path}")
                return None
            
            # Load the module
            spec = importlib.util.spec_from_file_location(strategy_name, file_path)
            if not spec or not spec.loader:
                logger.error(f"Could not create module spec for {file_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find the strategy class
            strategy_class = None
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy and 
                    obj.__module__ == module.__name__):
                    strategy_class = obj
                    break
            
            if not strategy_class:
                logger.error(f"No valid strategy class found in {file_path}")
                return None
            
            # Cache the loaded strategy
            self.loaded_strategies[cache_key] = strategy_class
            logger.info(f"Successfully loaded strategy: {cache_key}")
            
            return strategy_class
            
        except Exception as e:
            logger.error(f"Error loading strategy {strategy_name}: {str(e)}")
            return None
    
    def validate_strategy(self, strategy_class: Type[BaseStrategy]) -> bool:
        """
        Validate that a strategy class is properly implemented.
        
        Args:
            strategy_class: Strategy class to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if it inherits from BaseStrategy
            if not issubclass(strategy_class, BaseStrategy):
                return False
            
            # Check if execute method is implemented
            if not hasattr(strategy_class, 'execute'):
                return False
            
            # Check if execute method is not the abstract one
            if strategy_class.execute == BaseStrategy.execute:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating strategy: {str(e)}")
            return False
    
    def reload_strategy(self, strategy_name: str, category: str = "user_strategies") -> Optional[Type[BaseStrategy]]:
        """
        Reload a strategy (useful for development).
        
        Args:
            strategy_name: Name of the strategy
            category: Strategy category
            
        Returns:
            Reloaded strategy class or None
        """
        cache_key = f"{category}/{strategy_name}"
        
        # Remove from cache
        if cache_key in self.loaded_strategies:
            del self.loaded_strategies[cache_key]
        
        # Reload
        return self.load_strategy(strategy_name, category)
    
    def get_strategy_list(self) -> List[Dict[str, str]]:
        """
        Get a formatted list of all available strategies.
        
        Returns:
            List of strategy information for UI display
        """
        strategies = self.discover_strategies()
        
        # Sort by category and name
        strategies.sort(key=lambda x: (x['category'], x['name']))
        
        return strategies