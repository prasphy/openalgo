"""
Paper trading service implementation.

This service provides a complete paper trading simulation that implements
the ITradingService interface. It uses live market data for realistic
price execution while maintaining all trading data locally.
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Tuple, List, Optional
from sqlalchemy import and_, desc
from database.paper_trading_db import (
    PaperOrder, PaperTrade, PaperPosition, PaperAccount,
    get_paper_trading_session, get_or_create_paper_account,
    generate_order_id, generate_trade_id
)
from services.interfaces.trading_service import ITradingService, TradingServiceError
from services.paper_trading.market_data_feed import MarketDataFeed
from services.paper_trading.order_matching_engine import OrderMatchingEngine
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


class PaperTradingService(ITradingService):
    """
    Paper trading service implementation.
    
    This service provides a complete paper trading simulation that implements
    the ITradingService interface. It uses live market data for realistic
    price execution while maintaining all trading data locally.
    """
    
    def __init__(self, user_id: str, broker: str):
        """
        Initialize paper trading service.
        
        Args:
            user_id: User identifier
            broker: Broker name (used for market data feed)
        """
        super().__init__(user_id, broker)
        self.session = get_paper_trading_session()
        
        # Initialize market data feed and order matching engine
        # Note: We'll use a mock auth token for market data since we're in paper mode
        self.market_data_feed = MarketDataFeed(broker, "paper_trading_mock_token")
        self.order_matching_engine = OrderMatchingEngine(self.market_data_feed)
        
        # Ensure user has a paper trading account
        self.account = get_or_create_paper_account(user_id)
        
        logger.info(f"Initialized paper trading service for user {user_id} with broker {broker}")
    
    def place_order(self, order_data: Dict[str, Any], auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Place a trading order in paper trading mode.
        
        Args:
            order_data: Order details containing symbol, exchange, action, quantity, etc.
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing order ID and status
            - HTTP status code (int)
        """
        try:
            # Validate required fields
            required_fields = ['symbol', 'exchange', 'action', 'product', 'pricetype', 'quantity']
            missing_fields = [field for field in required_fields if field not in order_data]
            if missing_fields:
                return False, {
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }, 400
            
            # Generate unique order ID
            order_id = generate_order_id()
            
            # Create paper order
            paper_order = PaperOrder(
                user_id=self.user_id,
                order_id=order_id,
                symbol=order_data['symbol'],
                exchange=order_data['exchange'],
                action=order_data['action'].upper(),
                product=order_data['product'],
                price_type=order_data['pricetype'],
                quantity=int(order_data['quantity']),
                price=Decimal(str(order_data['price'])) if order_data.get('price') else None,
                trigger_price=Decimal(str(order_data['trigger_price'])) if order_data.get('trigger_price') else None,
                disclosed_quantity=int(order_data.get('disclosed_quantity', 0)),
                strategy=order_data.get('strategy', 'Paper Trading')
            )
            
            # Save order to database
            self.session.add(paper_order)
            self.session.commit()
            
            # Process the order through matching engine
            self.order_matching_engine.process_order(paper_order)
            
            logger.info(f"Placed paper trading order {order_id} for {self.user_id}")
            
            return True, {
                'status': 'success',
                'orderid': order_id,
                'message': 'Paper trading order placed successfully'
            }, 200
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error placing paper trading order: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to place order: {str(e)}'
            }, 500
    
    def get_positions(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get current trading positions.
        
        Args:
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing positions list
            - HTTP status code (int)
        """
        try:
            positions = self.session.query(PaperPosition).filter(
                and_(
                    PaperPosition.user_id == self.user_id,
                    PaperPosition.quantity != 0
                )
            ).all()
            
            positions_data = []
            total_pnl = 0.0
            
            for position in positions:
                # Get current market price for P&L calculation
                current_price = self.market_data_feed.get_live_price(position.symbol, position.exchange)
                
                if current_price:
                    # Calculate unrealized P&L
                    unrealized_pnl = (current_price - position.average_price) * position.quantity
                    total_pnl += float(unrealized_pnl)
                else:
                    unrealized_pnl = 0
                    current_price = position.average_price
                
                position_dict = {
                    'symbol': position.symbol,
                    'exchange': position.exchange,
                    'product': position.product,
                    'quantity': position.quantity,
                    'average_price': float(position.average_price),
                    'ltp': float(current_price),
                    'pnl': float(unrealized_pnl),
                    'realized_pnl': float(position.realized_pnl)
                }
                positions_data.append(position_dict)
            
            return True, {
                'status': 'success',
                'data': positions_data,
                'total_pnl': total_pnl
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get positions: {str(e)}'
            }, 500
    
    def get_open_orders(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get currently open/pending orders.
        
        Args:
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing open orders list
            - HTTP status code (int)
        """
        try:
            open_orders = self.session.query(PaperOrder).filter(
                and_(
                    PaperOrder.user_id == self.user_id,
                    PaperOrder.status == 'PENDING'
                )
            ).order_by(desc(PaperOrder.order_timestamp)).all()
            
            orders_data = [order.to_dict() for order in open_orders]
            
            return True, {
                'status': 'success',
                'data': orders_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get open orders: {str(e)}'
            }, 500
    
    def get_trade_history(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get trade execution history.
        
        Args:
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing trade history
            - HTTP status code (int)
        """
        try:
            trades = self.session.query(PaperTrade).filter_by(
                user_id=self.user_id
            ).order_by(desc(PaperTrade.trade_timestamp)).all()
            
            trades_data = [trade.to_dict() for trade in trades]
            
            return True, {
                'status': 'success',
                'data': trades_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get trade history: {str(e)}'
            }, 500
    
    def cancel_order(self, order_id: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Cancel a pending order.
        
        Args:
            order_id: Unique identifier of the order to cancel
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing cancellation status
            - HTTP status code (int)
        """
        try:
            success = self.order_matching_engine.cancel_order(order_id)
            
            if success:
                return True, {
                    'status': 'success',
                    'message': f'Order {order_id} cancelled successfully'
                }, 200
            else:
                return False, {
                    'status': 'error',
                    'message': f'Order {order_id} not found or cannot be cancelled'
                }, 404
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to cancel order: {str(e)}'
            }, 500
    
    def get_account_balance(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get account balance and fund information.
        
        Args:
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing balance information
            - HTTP status code (int)
        """
        try:
            account = self.session.query(PaperAccount).filter_by(user_id=self.user_id).first()
            
            if not account:
                return False, {
                    'status': 'error',
                    'message': 'Paper trading account not found'
                }, 404
            
            # Calculate used and available funds
            # Get total value of current positions
            positions = self.session.query(PaperPosition).filter_by(user_id=self.user_id).all()
            position_value = 0.0
            
            for position in positions:
                if position.quantity > 0:  # Long positions
                    position_value += float(position.average_price * position.quantity)
            
            available_balance = float(account.current_balance)
            used_balance = float(account.initial_balance) - available_balance
            
            return True, {
                'status': 'success',
                'data': {
                    'initial_balance': float(account.initial_balance),
                    'current_balance': available_balance,
                    'used_balance': used_balance,
                    'position_value': position_value,
                    'currency': account.currency,
                    'account_type': 'Paper Trading'
                }
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get account balance: {str(e)}'
            }, 500
    
    def get_open_position(self, symbol: str, exchange: str, product: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get quantity of a specific open position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            product: Product type (MIS, CNC, NRML)
            auth_token: Authentication token (not used in paper trading)
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing position quantity
            - HTTP status code (int)
        """
        try:
            position = self.session.query(PaperPosition).filter(
                and_(
                    PaperPosition.user_id == self.user_id,
                    PaperPosition.symbol == symbol,
                    PaperPosition.exchange == exchange,
                    PaperPosition.product == product
                )
            ).first()
            
            quantity = position.quantity if position else 0
            
            return True, {
                'status': 'success',
                'data': {
                    'quantity': quantity
                }
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting open position: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get open position: {str(e)}'
            }, 500
    
    def modify_order(self, order_id: str, order_data: Dict[str, Any], auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Modify an existing order (not implemented for paper trading).
        
        Args:
            order_id: Unique identifier of the order to modify
            order_data: New order parameters
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing modification status
            - HTTP status code (int)
        """
        return False, {
            'status': 'error',
            'message': 'Order modification not supported in paper trading mode'
        }, 501
    
    def close_position(self, symbol: str, exchange: str, product: str, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Close a specific position.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            product: Product type (MIS, CNC, NRML)
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing closure status
            - HTTP status code (int)
        """
        try:
            position = self.session.query(PaperPosition).filter(
                and_(
                    PaperPosition.user_id == self.user_id,
                    PaperPosition.symbol == symbol,
                    PaperPosition.exchange == exchange,
                    PaperPosition.product == product
                )
            ).first()
            
            if not position or position.quantity == 0:
                return False, {
                    'status': 'error',
                    'message': 'No open position found'
                }, 404
            
            # Create opposite order to close position
            close_action = 'SELL' if position.quantity > 0 else 'BUY'
            close_quantity = abs(position.quantity)
            
            order_data = {
                'symbol': symbol,
                'exchange': exchange,
                'action': close_action,
                'product': product,
                'pricetype': 'MARKET',
                'quantity': close_quantity,
                'strategy': 'Close Position'
            }
            
            return self.place_order(order_data, auth_token)
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to close position: {str(e)}'
            }, 500
    
    def close_all_positions(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Close all open positions.
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing closure status
            - HTTP status code (int)
        """
        try:
            positions = self.session.query(PaperPosition).filter(
                and_(
                    PaperPosition.user_id == self.user_id,
                    PaperPosition.quantity != 0
                )
            ).all()
            
            if not positions:
                return True, {
                    'status': 'success',
                    'message': 'No open positions to close'
                }, 200
            
            closed_count = 0
            failed_count = 0
            
            for position in positions:
                success, _, _ = self.close_position(
                    position.symbol, 
                    position.exchange, 
                    position.product, 
                    auth_token
                )
                
                if success:
                    closed_count += 1
                else:
                    failed_count += 1
            
            return True, {
                'status': 'success',
                'message': f'Closed {closed_count} positions, {failed_count} failed'
            }, 200
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to close positions: {str(e)}'
            }, 500
    
    def cancel_all_orders(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Cancel all pending orders.
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing cancellation status
            - HTTP status code (int)
        """
        try:
            pending_orders = self.session.query(PaperOrder).filter(
                and_(
                    PaperOrder.user_id == self.user_id,
                    PaperOrder.status == 'PENDING'
                )
            ).all()
            
            if not pending_orders:
                return True, {
                    'status': 'success',
                    'message': 'No pending orders to cancel'
                }, 200
            
            cancelled_count = 0
            
            for order in pending_orders:
                success = self.order_matching_engine.cancel_order(order.order_id)
                if success:
                    cancelled_count += 1
            
            return True, {
                'status': 'success',
                'message': f'Cancelled {cancelled_count} orders'
            }, 200
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to cancel orders: {str(e)}'
            }, 500
    
    def get_holdings(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get investment holdings (returns empty for paper trading).
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing holdings information
            - HTTP status code (int)
        """
        return True, {
            'status': 'success',
            'data': [],
            'message': 'No holdings in paper trading mode'
        }, 200
    
    def get_order_history(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get complete order history.
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing order history
            - HTTP status code (int)
        """
        try:
            orders = self.session.query(PaperOrder).filter_by(
                user_id=self.user_id
            ).order_by(desc(PaperOrder.order_timestamp)).all()
            
            orders_data = [order.to_dict() for order in orders]
            
            return True, {
                'status': 'success',
                'data': orders_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get order history: {str(e)}'
            }, 500
    
    def reset_account(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Reset paper trading account to initial state.
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing reset status
            - HTTP status code (int)
        """
        try:
            from database.paper_trading_db import reset_paper_account
            
            success = reset_paper_account(self.user_id)
            
            if success:
                # Recreate account reference
                self.account = get_or_create_paper_account(self.user_id)
                
                return True, {
                    'status': 'success',
                    'message': 'Paper trading account reset successfully'
                }, 200
            else:
                return False, {
                    'status': 'error',
                    'message': 'Failed to reset paper trading account'
                }, 500
                
        except Exception as e:
            logger.error(f"Error resetting account: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to reset account: {str(e)}'
            }, 500
    
    def get_trading_statistics(self, auth_token: str) -> Tuple[bool, Dict[str, Any], int]:
        """
        Get comprehensive trading statistics for paper trading.
        
        Args:
            auth_token: Authentication token
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data (dict) containing statistics
            - HTTP status code (int)
        """
        try:
            from database.paper_trading_db import get_account_statistics
            
            stats = get_account_statistics(self.user_id)
            engine_stats = self.order_matching_engine.get_engine_statistics()
            
            # Combine statistics
            combined_stats = {
                **stats,
                'engine_statistics': engine_stats,
                'mode': 'paper_trading'
            }
            
            return True, {
                'status': 'success',
                'data': combined_stats
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting trading statistics: {e}")
            return False, {
                'status': 'error',
                'message': f'Failed to get statistics: {str(e)}'
            }, 500