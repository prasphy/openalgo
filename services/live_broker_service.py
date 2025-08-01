"""
Live broker service implementation.

This service implements the ITradingService interface by wrapping existing
broker-specific API functions. It provides a standardized interface for
live trading operations while delegating to the actual broker implementations.
"""

import importlib
from typing import Dict, Any, Tuple, Optional
from services.interfaces.trading_service import ITradingService, TradingServiceError
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


class LiveBrokerService(ITradingService):
    """
    Live broker service implementation.
    
    This service implements the ITradingService interface by wrapping existing
    broker-specific API functions. It provides a standardized interface for
    live trading operations while delegating to the actual broker implementations.
    """
    
    def __init__(self, user_id: str, broker: str):
        """
        Initialize live broker service.
        
        Args:
            user_id: User identifier
            broker: Broker name (e.g., 'zerodha', 'angel', 'upstox')
        """
        super().__init__(user_id, broker)
        
        # Import broker-specific modules
        self.order_api_module = self._import_broker_module('api.order_api')
        self.mapping_module = self._import_broker_module('mapping.order_data')
        
        logger.info(f"Initialized live broker service for user {user_id} with broker {broker}")
    
    def _import_broker_module(self, module_path: str) -> Optional[Any]:
        """
        Import broker-specific module.
        
        Args:
            module_path: Module path relative to broker directory
            
        Returns:
            Imported module or None if import fails
        """
        try:
            full_path = f'broker.{self.broker}.{module_path}'
            return importlib.import_module(full_path)
        except ImportError as e:
            logger.error(f"Failed to import {full_path}: {e}")
            return None
    
    def _ensure_module_loaded(self, module_name: str) -> bool:
        """
        Ensure required module is loaded.
        
        Args:
            module_name: Module name for error messages
            
        Returns:
            bool: True if module is available
        """
        if module_name == 'order_api' and not self.order_api_module:
            logger.error(f"Order API module not available for broker {self.broker}")
            return False
        elif module_name == 'mapping' and not self.mapping_module:
            logger.error(f"Mapping module not available for broker {self.broker}")
            return False
        return True
    
    def place_order(self, order_data: Dict[str, Any], auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Place a trading order using live broker API.
        
        Args:
            order_data: Order details containing symbol, exchange, action, quantity, etc.
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing order ID and status
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has place_order_api function
            if not hasattr(self.order_api_module, 'place_order_api'):
                return False, {
                    'status': 'error',
                    'message': f'place_order_api not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's place_order_api function
            res, response_data, order_id = self.order_api_module.place_order_api(order_data, auth_token)
            
            if hasattr(res, 'status') and res.status == 200:
                return True, {
                    'status': 'success',
                    'orderid': order_id,
                    'message': 'Order placed successfully'
                }, 200
            else:
                message = response_data.get('message', 'Failed to place order') if isinstance(response_data, dict) else 'Failed to place order'
                status_code = res.status if hasattr(res, 'status') else 400
                return False, {
                    'status': 'error',
                    'message': message
                }, status_code
                
        except Exception as e:
            logger.error(f"Error placing order via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to place order: {str(e)}'
            }, 500
    
    def get_positions(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get current trading positions using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing positions list
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_positions function
            if not hasattr(self.order_api_module, 'get_positions'):
                return False, {
                    'status': 'error',
                    'message': f'get_positions not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's get_positions function
            positions_data = self.order_api_module.get_positions(auth_token)
            
            # Check for error response
            if isinstance(positions_data, dict) and positions_data.get('status') == 'error':
                return False, positions_data, 400
            
            # Apply mapping if available
            if self.mapping_module and hasattr(self.mapping_module, 'map_position_data'):
                try:
                    positions_data = self.mapping_module.map_position_data(positions_data)
                except Exception as e:
                    logger.warning(f"Error in position mapping: {e}")
            
            # Transform data if available
            if self.mapping_module and hasattr(self.mapping_module, 'transform_positions_data'):
                try:
                    positions_data = self.mapping_module.transform_positions_data(positions_data)
                except Exception as e:
                    logger.warning(f"Error in position transformation: {e}")
            
            return True, {
                'status': 'success',
                'data': positions_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting positions via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get positions: {str(e)}'
            }, 500
    
    def get_open_orders(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get currently open/pending orders using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing open orders list
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_order_book function
            if not hasattr(self.order_api_module, 'get_order_book'):
                return False, {
                    'status': 'error',
                    'message': f'get_order_book not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's get_order_book function
            order_data = self.order_api_module.get_order_book(auth_token)
            
            # Check for error response
            if isinstance(order_data, dict) and order_data.get('status') == 'error':
                return False, order_data, 400
            
            # Apply mapping if available
            if self.mapping_module and hasattr(self.mapping_module, 'map_order_data'):
                try:
                    order_data = self.mapping_module.map_order_data(order_data=order_data)
                except Exception as e:
                    logger.warning(f"Error in order mapping: {e}")
            
            # Filter for open orders only
            if isinstance(order_data, list):
                open_orders = [order for order in order_data if order.get('order_status', '').upper() in ['PENDING', 'OPEN', 'TRIGGER_PENDING']]
            else:
                open_orders = order_data
            
            return True, {
                'status': 'success',
                'data': open_orders
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting open orders via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get open orders: {str(e)}'
            }, 500
    
    def get_trade_history(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get trade execution history using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing trade history
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_trade_book function
            if not hasattr(self.order_api_module, 'get_trade_book'):
                return False, {
                    'status': 'error',
                    'message': f'get_trade_book not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's get_trade_book function
            trade_data = self.order_api_module.get_trade_book(auth_token)
            
            # Check for error response
            if isinstance(trade_data, dict) and trade_data.get('status') == 'error':
                return False, trade_data, 400
            
            # Apply mapping if available
            if self.mapping_module and hasattr(self.mapping_module, 'map_trade_data'):
                try:
                    trade_data = self.mapping_module.map_trade_data(trade_data=trade_data)
                except Exception as e:
                    logger.warning(f"Error in trade mapping: {e}")
            
            # Transform data if available
            if self.mapping_module and hasattr(self.mapping_module, 'transform_tradebook_data'):
                try:
                    trade_data = self.mapping_module.transform_tradebook_data(trade_data)
                except Exception as e:
                    logger.warning(f"Error in trade transformation: {e}")
            
            return True, {
                'status': 'success',
                'data': trade_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting trade history via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get trade history: {str(e)}'
            }, 500
    
    def cancel_order(self, order_id: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Cancel a pending order using live broker API.
        
        Args:
            order_id: Unique identifier of the order to cancel
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing cancellation status
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has cancel_order_api function
            if not hasattr(self.order_api_module, 'cancel_order_api'):
                return False, {
                    'status': 'error',
                    'message': f'cancel_order_api not implemented for broker {self.broker}'
                }, 501
            
            # Prepare cancel order data
            cancel_data = {'orderid': order_id}
            
            # Call broker's cancel_order_api function
            res, response_data = self.order_api_module.cancel_order_api(cancel_data, auth_token)
            
            if hasattr(res, 'status') and res.status == 200:
                return True, {
                    'status': 'success',
                    'message': f'Order {order_id} cancelled successfully'
                }, 200
            else:
                message = response_data.get('message', 'Failed to cancel order') if isinstance(response_data, dict) else 'Failed to cancel order'
                status_code = res.status if hasattr(res, 'status') else 400
                return False, {
                    'status': 'error',
                    'message': message
                }, status_code
                
        except Exception as e:
            logger.error(f"Error cancelling order via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to cancel order: {str(e)}'
            }, 500
    
    def get_account_balance(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get account balance and fund information using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing balance information
            - HTTP status code (int)
        """
        try:
            # Try to import funds API
            funds_module = self._import_broker_module('api.funds')
            
            if not funds_module:
                return False, {
                    'status': 'error',
                    'message': f'Funds API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_margin_data function (preferred) or get_funds function (fallback)
            get_funds_func = None
            if hasattr(funds_module, 'get_margin_data'):
                get_funds_func = getattr(funds_module, 'get_margin_data')
            elif hasattr(funds_module, 'get_funds'):
                get_funds_func = getattr(funds_module, 'get_funds')
            else:
                return False, {
                    'status': 'error',
                    'message': f'No funds function (get_margin_data or get_funds) implemented for broker {self.broker}'
                }, 501
            
            # Call broker's funds function
            funds_data = get_funds_func(auth_token)
            
            # Check for error response
            if isinstance(funds_data, dict) and funds_data.get('status') == 'error':
                return False, funds_data, 400
            
            return True, {
                'status': 'success',
                'data': funds_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting account balance via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get account balance: {str(e)}'
            }, 500
    
    def get_open_position(self, symbol: str, exchange: str, product: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get quantity of a specific open position using live broker API.
        
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
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_open_position function
            if not hasattr(self.order_api_module, 'get_open_position'):
                return False, {
                    'status': 'error',
                    'message': f'get_open_position not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's get_open_position function
            quantity = self.order_api_module.get_open_position(symbol, exchange, product, auth_token)
            
            return True, {
                'status': 'success',
                'data': {
                    'quantity': quantity if quantity is not None else 0
                }
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting open position via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get open position: {str(e)}'
            }, 500
    
    def modify_order(self, order_id: str, order_data: Dict[str, Any], auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Modify an existing order using live broker API.
        
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
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has modify_order_api function
            if not hasattr(self.order_api_module, 'modify_order_api'):
                return False, {
                    'status': 'error',
                    'message': f'modify_order_api not implemented for broker {self.broker}'
                }, 501
            
            # Add order ID to order data
            order_data['orderid'] = order_id
            
            # Call broker's modify_order_api function
            res, response_data = self.order_api_module.modify_order_api(order_data, auth_token)
            
            if hasattr(res, 'status') and res.status == 200:
                return True, {
                    'status': 'success',
                    'message': f'Order {order_id} modified successfully'
                }, 200
            else:
                message = response_data.get('message', 'Failed to modify order') if isinstance(response_data, dict) else 'Failed to modify order'
                status_code = res.status if hasattr(res, 'status') else 400
                return False, {
                    'status': 'error',
                    'message': message
                }, status_code
                
        except Exception as e:
            logger.error(f"Error modifying order via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to modify order: {str(e)}'
            }, 500
    
    def close_position(self, symbol: str, exchange: str, product: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Close a specific position using live broker API.
        
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
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has close_position_api function
            if hasattr(self.order_api_module, 'close_position_api'):
                # Use broker's dedicated close position function
                close_data = {
                    'symbol': symbol,
                    'exchange': exchange,
                    'product': product
                }
                
                res, response_data = self.order_api_module.close_position_api(close_data, auth_token)
                
                if hasattr(res, 'status') and res.status == 200:
                    return True, {
                        'status': 'success',
                        'message': f'Position closed successfully'
                    }, 200
                else:
                    message = response_data.get('message', 'Failed to close position') if isinstance(response_data, dict) else 'Failed to close position'
                    status_code = res.status if hasattr(res, 'status') else 400
                    return False, {
                        'status': 'error',
                        'message': message
                    }, status_code
            else:
                # Manual implementation - get position and place opposite order
                return False, {
                    'status': 'error',
                    'message': 'Close position API not available for this broker'
                }, 501
                
        except Exception as e:
            logger.error(f"Error closing position via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to close position: {str(e)}'
            }, 500
    
    def close_all_positions(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Close all open positions using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing closure status
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has close_all_positions function
            if hasattr(self.order_api_module, 'close_all_positions'):
                response_code, status_code = self.order_api_module.close_all_positions('', auth_token)
                
                if status_code == 200:
                    return True, {
                        'status': 'success',
                        'message': 'All positions closed successfully'
                    }, 200
                else:
                    message = response_code.get('message', 'Failed to close positions') if isinstance(response_code, dict) else 'Failed to close positions'
                    return False, {
                        'status': 'error',
                        'message': message
                    }, status_code
            else:
                return False, {
                    'status': 'error',
                    'message': 'Close all positions API not available for this broker'
                }, 501
                
        except Exception as e:
            logger.error(f"Error closing all positions via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to close all positions: {str(e)}'
            }, 500
    
    def cancel_all_orders(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Cancel all pending orders using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing cancellation status
            - HTTP status code (int)
        """
        try:
            # Use existing cancel_all_orders service
            from services.cancel_all_order_service import cancel_all_orders
            
            success, response_data, status_code = cancel_all_orders(
                order_data={},
                auth_token=auth_token,  
                broker=self.broker
            )
            
            return success, response_data, status_code
            
        except Exception as e:
            logger.error(f"Error cancelling all orders via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to cancel all orders: {str(e)}'
            }, 500
    
    def get_holdings(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get investment holdings using live broker API.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing holdings information
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_holdings function
            if not hasattr(self.order_api_module, 'get_holdings'):
                return False, {
                    'status': 'error',
                    'message': f'get_holdings not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's get_holdings function
            holdings_data = self.order_api_module.get_holdings(auth_token)
            
            # Check for error response from Dhan API
            if isinstance(holdings_data, dict):
                # Check for Dhan-specific error formats
                if holdings_data.get('status') == 'error' or holdings_data.get('status') == 'failed':
                    return False, holdings_data, 400
                # Check for errorType in response (another Dhan error format)
                if holdings_data.get('errorType'):
                    return False, {
                        'status': 'error',
                        'message': holdings_data.get('errorMessage', 'API Error')
                    }, 400
                # Check for DH-1111 error specifically
                if 'DH-1111' in str(holdings_data.get('errorCode', '')) or 'No holdings available' in str(holdings_data.get('errorMessage', '')):
                    # Return empty list instead of error for "No holdings available" case
                    holdings_data = []
            
            # Handle case where holdings_data might be None or empty
            if holdings_data is None:
                holdings_data = []
            
            # Apply mapping if available
            if self.mapping_module and hasattr(self.mapping_module, 'map_portfolio_data'):
                try:
                    holdings_data = self.mapping_module.map_portfolio_data(holdings_data)
                except Exception as e:
                    logger.warning(f"Error in holdings mapping: {e}")
            
            return True, {
                'status': 'success',
                'data': holdings_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting holdings via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get holdings: {str(e)}'
            }, 500
    
    def get_order_history(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get complete order history using live broker API.
        
        This method returns the same data as get_open_orders but without filtering.
        
        Args:
            auth_token: Authentication token for the broker API
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing order history
            - HTTP status code (int)
        """
        try:
            if not self._ensure_module_loaded('order_api'):
                return False, {
                    'status': 'error',
                    'message': f'Order API not available for broker {self.broker}'
                }, 500
            
            # Check if broker has get_order_book function
            if not hasattr(self.order_api_module, 'get_order_book'):
                return False, {
                    'status': 'error',
                    'message': f'get_order_book not implemented for broker {self.broker}'
                }, 501
            
            # Call broker's get_order_book function
            order_data = self.order_api_module.get_order_book(auth_token)
            
            # Check for error response
            if isinstance(order_data, dict) and order_data.get('status') == 'error':
                return False, order_data, 400
            
            # Apply mapping if available
            if self.mapping_module and hasattr(self.mapping_module, 'map_order_data'):
                try:
                    order_data = self.mapping_module.map_order_data(order_data=order_data)
                except Exception as e:
                    logger.warning(f"Error in order mapping: {e}")
            
            # Transform data if available
            if self.mapping_module and hasattr(self.mapping_module, 'transform_order_data'):
                try:
                    order_data = self.mapping_module.transform_order_data(order_data)
                except Exception as e:
                    logger.warning(f"Error in order transformation: {e}")
            
            return True, {
                'status': 'success',
                'data': order_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting order history via {self.broker}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get order history: {str(e)}'
            }, 500