"""
Strategy Execution Engine

Handles the execution of custom strategies with support for immediate,
queue, and scheduled execution modes.
"""

import logging
import threading
import time
import queue
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Try to import schedule, handle gracefully if not available
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    schedule = None

from .strategy_loader import StrategyLoader
from .strategy_validator import StrategyValidator
from database.strategy_db import get_strategy, update_strategy_config
from database.auth_db import get_api_key_for_tradingview
from utils.logging import get_logger

logger = get_logger(__name__)


class StrategyExecutionResult:
    """Result of strategy execution"""
    
    def __init__(self, strategy_id: int, success: bool, signals: List[str] = None, 
                 error: str = None, execution_time: float = 0, logs: List[str] = None):
        self.strategy_id = strategy_id
        self.success = success
        self.signals = signals or []
        self.error = error
        self.execution_time = execution_time
        self.logs = logs or []
        self.timestamp = datetime.now()


class StrategyExecutor:
    """
    Main strategy execution engine that handles different execution modes.
    """
    
    def __init__(self, max_workers: int = 5, execution_timeout: int = 300):
        """
        Initialize the strategy executor.
        
        Args:
            max_workers: Maximum number of concurrent strategy executions
            execution_timeout: Maximum execution time per strategy in seconds
        """
        self.max_workers = max_workers
        self.execution_timeout = execution_timeout
        self.loader = StrategyLoader()
        self.validator = StrategyValidator()
        
        # Thread pool for concurrent executions
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Queue for queued executions
        self.execution_queue = queue.Queue()
        self.queue_worker_running = False
        self.queue_worker_thread = None
        
        # Scheduled executions
        self.scheduler_running = False
        self.scheduler_thread = None
        self.schedule_enabled = SCHEDULE_AVAILABLE
        
        # Execution tracking
        self.active_executions: Dict[int, threading.Thread] = {}
        self.execution_history: List[StrategyExecutionResult] = []
        
        if not SCHEDULE_AVAILABLE:
            logger.warning("Schedule module not available. Scheduled execution will be disabled.")
        
        logger.info("Strategy Executor initialized")
    
    def start_background_services(self):
        """Start background services for queue and scheduler."""
        self._start_queue_worker()
        if self.schedule_enabled:
            self._start_scheduler()
    
    def stop_background_services(self):
        """Stop background services."""
        self._stop_queue_worker()
        if self.schedule_enabled:
            self._stop_scheduler()
        self.executor.shutdown(wait=True)
    
    def execute_strategy_immediate(self, strategy_id: int, **kwargs) -> StrategyExecutionResult:
        """
        Execute a strategy immediately.
        
        Args:
            strategy_id: ID of the strategy to execute
            **kwargs: Additional parameters for strategy execution
            
        Returns:
            StrategyExecutionResult
        """
        logger.info(f"Executing strategy {strategy_id} immediately")
        
        try:
            # Submit to thread pool with timeout
            future = self.executor.submit(self._execute_strategy_sync, strategy_id, **kwargs)
            result = future.result(timeout=self.execution_timeout)
            
            # Store in history
            self.execution_history.append(result)
            
            return result
            
        except TimeoutError:
            error_msg = f"Strategy {strategy_id} execution timed out after {self.execution_timeout} seconds"
            logger.error(error_msg)
            result = StrategyExecutionResult(strategy_id, False, error=error_msg)
            self.execution_history.append(result)
            return result
            
        except Exception as e:
            error_msg = f"Error executing strategy {strategy_id}: {str(e)}"
            logger.error(error_msg)
            result = StrategyExecutionResult(strategy_id, False, error=error_msg)
            self.execution_history.append(result)
            return result
    
    def execute_strategy_queue(self, strategy_id: int, **kwargs) -> bool:
        """
        Queue a strategy for execution.
        
        Args:
            strategy_id: ID of the strategy to execute
            **kwargs: Additional parameters for strategy execution
            
        Returns:
            True if successfully queued, False otherwise
        """
        try:
            execution_item = {
                'strategy_id': strategy_id,
                'timestamp': datetime.now(),
                'kwargs': kwargs
            }
            
            self.execution_queue.put(execution_item)
            logger.info(f"Strategy {strategy_id} queued for execution")
            
            # Start queue worker if not running
            if not self.queue_worker_running:
                self._start_queue_worker()
            
            return True
            
        except Exception as e:
            logger.error(f"Error queueing strategy {strategy_id}: {str(e)}")
            return False
    
    def schedule_strategy_execution(self, strategy_id: int, schedule_config: Dict[str, Any]) -> bool:
        """
        Schedule a strategy for periodic execution.
        
        Args:
            strategy_id: ID of the strategy to schedule
            schedule_config: Schedule configuration dictionary
            
        Returns:
            True if successfully scheduled, False otherwise
        """
        if not self.schedule_enabled:
            logger.error("Schedule module not available. Cannot schedule strategy execution.")
            return False
        
        try:
            strategy = get_strategy(strategy_id)
            if not strategy:
                logger.error(f"Strategy {strategy_id} not found")
                return False
            
            # Parse schedule configuration
            interval_type = schedule_config.get('interval_type', 'minutes')
            interval_value = schedule_config.get('interval_value', 5)
            
            # Create scheduled job
            if interval_type == 'minutes':
                schedule.every(interval_value).minutes.do(
                    self._scheduled_execution_wrapper, strategy_id
                ).tag(f'strategy_{strategy_id}')
            elif interval_type == 'hours':
                schedule.every(interval_value).hours.do(
                    self._scheduled_execution_wrapper, strategy_id
                ).tag(f'strategy_{strategy_id}')
            elif interval_type == 'daily':
                time_str = schedule_config.get('time', '09:30')
                schedule.every().day.at(time_str).do(
                    self._scheduled_execution_wrapper, strategy_id
                ).tag(f'strategy_{strategy_id}')
            else:
                logger.error(f"Unsupported interval type: {interval_type}")
                return False
            
            # Update strategy schedule config
            update_strategy_config(strategy_id, schedule_config=schedule_config)
            
            # Start scheduler if not running
            if not self.scheduler_running:
                self._start_scheduler()
            
            logger.info(f"Strategy {strategy_id} scheduled for execution: {schedule_config}")
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling strategy {strategy_id}: {str(e)}")
            return False
    
    def cancel_scheduled_strategy(self, strategy_id: int) -> bool:
        """Cancel scheduled execution for a strategy."""
        if not self.schedule_enabled:
            return True  # Nothing to cancel if scheduling is disabled
        
        try:
            schedule.clear(f'strategy_{strategy_id}')
            logger.info(f"Cancelled scheduled execution for strategy {strategy_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling schedule for strategy {strategy_id}: {str(e)}")
            return False
    
    def _execute_strategy_sync(self, strategy_id: int, **kwargs) -> StrategyExecutionResult:
        """
        Synchronously execute a strategy.
        
        Args:
            strategy_id: ID of the strategy to execute
            **kwargs: Additional parameters
            
        Returns:
            StrategyExecutionResult
        """
        start_time = time.time()
        execution_logs = []
        
        try:
            # Get strategy from database
            strategy = get_strategy(strategy_id)
            if not strategy:
                return StrategyExecutionResult(
                    strategy_id, False, error="Strategy not found"
                )
            
            # Only execute custom strategies
            if strategy.strategy_type != 'custom':
                return StrategyExecutionResult(
                    strategy_id, False, error="Not a custom strategy"
                )
            
            # Check if strategy is active
            if not strategy.is_active:
                return StrategyExecutionResult(
                    strategy_id, False, error="Strategy is inactive"
                )
            
            execution_logs.append(f"Loading custom strategy: {strategy.strategy_file}")
            
            # Load the strategy class
            strategy_class = self.loader.load_strategy(
                strategy.strategy_file.replace('.py', ''), 
                strategy.strategy_category or 'user_strategies'
            )
            
            if not strategy_class:
                return StrategyExecutionResult(
                    strategy_id, False, 
                    error=f"Failed to load strategy file: {strategy.strategy_file}",
                    logs=execution_logs
                )
            
            # Validate the strategy class
            if not self.loader.validate_strategy(strategy_class):
                return StrategyExecutionResult(
                    strategy_id, False, 
                    error="Strategy class validation failed",
                    logs=execution_logs
                )
            
            execution_logs.append("Strategy class loaded and validated successfully")
            
            # Get API key for the user
            api_key = get_api_key_for_tradingview(strategy.user_id)
            if not api_key:
                return StrategyExecutionResult(
                    strategy_id, False, 
                    error="API key not found for user",
                    logs=execution_logs
                )
            
            # Prepare strategy configuration
            strategy_config = {}
            if strategy.strategy_config:
                try:
                    strategy_config = json.loads(strategy.strategy_config)
                except (json.JSONDecodeError, TypeError):
                    execution_logs.append("Warning: Could not parse strategy configuration JSON")
            
            strategy_config.update(kwargs.get('strategy_params', {}))
            
            execution_logs.append("Initializing strategy instance")
            
            # Create strategy instance
            strategy_instance = strategy_class(
                api_key=api_key,
                strategy_config=strategy_config
            )
            
            execution_logs.append("Executing strategy logic")
            
            # Execute the strategy
            signals = strategy_instance.execute()
            
            # Validate signals
            if not isinstance(signals, list):
                return StrategyExecutionResult(
                    strategy_id, False, 
                    error="Strategy must return a list of symbols",
                    logs=execution_logs
                )
            
            execution_time = time.time() - start_time
            execution_logs.append(f"Strategy execution completed in {execution_time:.2f} seconds")
            execution_logs.append(f"Generated {len(signals)} signals: {signals}")
            
            return StrategyExecutionResult(
                strategy_id, True, 
                signals=signals, 
                execution_time=execution_time,
                logs=execution_logs
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Strategy execution error: {str(e)}"
            execution_logs.append(error_msg)
            
            return StrategyExecutionResult(
                strategy_id, False, 
                error=error_msg,
                execution_time=execution_time,
                logs=execution_logs
            )
    
    def _start_queue_worker(self):
        """Start the queue worker thread."""
        if self.queue_worker_running:
            return
        
        self.queue_worker_running = True
        self.queue_worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self.queue_worker_thread.start()
        logger.info("Queue worker started")
    
    def _stop_queue_worker(self):
        """Stop the queue worker thread."""
        self.queue_worker_running = False
        if self.queue_worker_thread:
            self.queue_worker_thread.join(timeout=5)
        logger.info("Queue worker stopped")
    
    def _queue_worker(self):
        """Background worker for processing queued executions."""
        while self.queue_worker_running:
            try:
                # Get item from queue with timeout
                execution_item = self.execution_queue.get(timeout=1)
                
                strategy_id = execution_item['strategy_id']
                kwargs = execution_item.get('kwargs', {})
                
                logger.info(f"Processing queued execution for strategy {strategy_id}")
                
                # Execute the strategy
                result = self._execute_strategy_sync(strategy_id, **kwargs)
                
                # Store result
                self.execution_history.append(result)
                
                # Mark task as done
                self.execution_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in queue worker: {str(e)}")
    
    def _start_scheduler(self):
        """Start the scheduler thread."""
        if not self.schedule_enabled:
            logger.warning("Cannot start scheduler: schedule module not available")
            return
        
        if self.scheduler_running:
            return
        
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_worker, daemon=True)
        self.scheduler_thread.start()
        logger.info("Scheduler started")
    
    def _stop_scheduler(self):
        """Stop the scheduler thread."""
        self.scheduler_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Scheduler stopped")
    
    def _scheduler_worker(self):
        """Background worker for scheduled executions."""
        if not self.schedule_enabled:
            return
        
        while self.scheduler_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler worker: {str(e)}")
    
    def _scheduled_execution_wrapper(self, strategy_id: int):
        """Wrapper for scheduled strategy execution."""
        try:
            logger.info(f"Executing scheduled strategy {strategy_id}")
            result = self._execute_strategy_sync(strategy_id)
            self.execution_history.append(result)
        except Exception as e:
            logger.error(f"Error in scheduled execution for strategy {strategy_id}: {str(e)}")
    
    def get_execution_history(self, strategy_id: Optional[int] = None, limit: int = 100) -> List[StrategyExecutionResult]:
        """Get execution history, optionally filtered by strategy ID."""
        if strategy_id:
            history = [r for r in self.execution_history if r.strategy_id == strategy_id]
        else:
            history = self.execution_history
        
        # Return most recent executions first
        return sorted(history, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_active_executions(self) -> Dict[int, Dict[str, Any]]:
        """Get information about currently active executions."""
        return {
            strategy_id: {
                'thread_id': thread.ident,
                'is_alive': thread.is_alive()
            }
            for strategy_id, thread in self.active_executions.items()
        }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status information."""
        return {
            'queue_size': self.execution_queue.qsize(),
            'worker_running': self.queue_worker_running,
            'scheduler_running': self.scheduler_running,
            'scheduler_enabled': self.schedule_enabled,
            'active_executions': len(self.active_executions),
            'total_executions': len(self.execution_history)
        }


# Global strategy executor instance
_strategy_executor = None

def get_strategy_executor() -> StrategyExecutor:
    """Get the global strategy executor instance."""
    global _strategy_executor
    if _strategy_executor is None:
        _strategy_executor = StrategyExecutor()
        _strategy_executor.start_background_services()
    return _strategy_executor

def cleanup_strategy_executor():
    """Cleanup the global strategy executor."""
    global _strategy_executor
    if _strategy_executor:
        _strategy_executor.stop_background_services()
        _strategy_executor = None