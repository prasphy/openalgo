"""
Order matching engine for paper trading simulation.

This engine processes orders based on live market data and simulates
realistic order execution. It supports market orders, limit orders,
and stop-loss orders with simple price-based matching logic.
"""

import threading
import time
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import and_
from database.paper_trading_db import (
    PaperOrder, PaperTrade, PaperPosition, PaperAccount,
    get_paper_trading_session, generate_trade_id
)
from services.paper_trading.market_data_feed import MarketDataFeed
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


class OrderMatchingEngine:
    """
    Order matching engine for paper trading simulation.
    
    This engine processes orders based on live market data and simulates
    realistic order execution. It supports:
    - Market orders: Immediate execution at current LTP
    - Limit orders: Execution when price crosses limit
    - Stop-loss orders: Execution when trigger price is reached
    """
    
    def __init__(self, market_data_feed: MarketDataFeed):
        """
        Initialize order matching engine.
        
        Args:
            market_data_feed: Market data feed for price information
        """
        self.market_data_feed = market_data_feed
        self.session = get_paper_trading_session()
        self._lock = threading.Lock()
        self._stop_monitoring = False
        self._monitoring_thread = None
        
        # Start background monitoring thread
        self.start_monitoring()
    
    def process_order(self, order: PaperOrder) -> bool:
        """
        Process a single order based on its type.
        
        Args:
            order: Paper order to process
            
        Returns:
            bool: True if order was processed (filled or rejected), False if still pending
        """
        try:
            if order.price_type == 'MARKET':
                return self._process_market_order(order)
            elif order.price_type == 'LIMIT':
                return self._process_limit_order(order)
            elif order.price_type in ['SL', 'SLM']:
                return self._process_stop_loss_order(order)
            else:
                logger.error(f"Unsupported order type: {order.price_type}")
                self._reject_order(order, f"Unsupported order type: {order.price_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing order {order.order_id}: {e}")
            self._reject_order(order, f"Internal error: {str(e)}")
            return True
    
    def _process_market_order(self, order: PaperOrder) -> bool:
        """
        Process market order - execute immediately at current market price.
        
        Args:
            order: Market order to process
            
        Returns:
            bool: True (market orders are always processed immediately)
        """
        logger.info(f"Processing market order {order.order_id} for {order.symbol}-{order.exchange}")
        
        # Get current market price
        current_price = self.market_data_feed.get_price_with_retry(order.symbol, order.exchange)
        
        if current_price is None:
            self._reject_order(order, "Unable to get current market price")
            return True
        
        # Execute the order at current price
        return self._fill_order(order, current_price, order.quantity)
    
    def _process_limit_order(self, order: PaperOrder) -> bool:
        """
        Process limit order - execute if price condition is met.
        
        Args:
            order: Limit order to process
            
        Returns:
            bool: True if order was filled, False if still pending
        """
        if order.price is None:
            self._reject_order(order, "Limit order missing price")
            return True
        
        # Get current market price
        current_price = self.market_data_feed.get_live_price(order.symbol, order.exchange)
        
        if current_price is None:
            logger.debug(f"No price available for limit order {order.order_id}, keeping pending")
            return False
        
        # Check if limit condition is met
        should_fill = False
        
        if order.action == 'BUY':
            # Buy limit order fills when market price <= limit price
            should_fill = current_price <= order.price
        elif order.action == 'SELL':
            # Sell limit order fills when market price >= limit price
            should_fill = current_price >= order.price
        
        if should_fill:
            logger.info(f"Filling limit order {order.order_id} at price {order.price}")
            return self._fill_order(order, order.price, order.quantity)
        
        return False  # Order remains pending
    
    def _process_stop_loss_order(self, order: PaperOrder) -> bool:
        """
        Process stop-loss order - execute when trigger price is reached.
        
        Args:
            order: Stop-loss order to process
            
        Returns:
            bool: True if order was triggered, False if still pending
        """
        if order.trigger_price is None:
            self._reject_order(order, "Stop-loss order missing trigger price")
            return True
        
        # Get current market price
        current_price = self.market_data_feed.get_live_price(order.symbol, order.exchange)
        
        if current_price is None:
            logger.debug(f"No price available for stop-loss order {order.order_id}, keeping pending")
            return False
        
        # Check if trigger condition is met
        should_trigger = False
        
        if order.action == 'BUY':
            # Buy stop-loss triggers when market price >= trigger price
            should_trigger = current_price >= order.trigger_price
        elif order.action == 'SELL':
            # Sell stop-loss triggers when market price <= trigger price
            should_trigger = current_price <= order.trigger_price
        
        if should_trigger:
            logger.info(f"Triggering stop-loss order {order.order_id} at price {current_price}")
            
            if order.price_type == 'SL':
                # Stop-limit order: convert to limit order at specified price
                execution_price = order.price if order.price else current_price
            else:  # SLM
                # Stop-market order: execute at current market price
                execution_price = current_price
            
            return self._fill_order(order, execution_price, order.quantity)
        
        return False  # Order remains pending
    
    def _fill_order(self, order: PaperOrder, fill_price: Decimal, fill_quantity: int) -> bool:
        """
        Fill an order at the specified price.
        
        Args:
            order: Order to fill
            fill_price: Price at which to fill the order
            fill_quantity: Quantity to fill
            
        Returns:
            bool: True if order was successfully filled
        """
        try:
            with self._lock:
                # Check account balance for buy orders
                if order.action == 'BUY':
                    required_funds = fill_price * fill_quantity
                    account = self.session.query(PaperAccount).filter_by(user_id=order.user_id).first()
                    
                    if not account or account.current_balance < required_funds:
                        self._reject_order(order, "Insufficient funds")
                        return True
                
                # Update order status
                order.status = 'FILLED'
                order.filled_quantity = fill_quantity
                order.average_price = fill_price
                order.filled_timestamp = datetime.utcnow()
                
                # Create trade record
                trade = PaperTrade(
                    user_id=order.user_id,
                    order_id=order.order_id,
                    trade_id=generate_trade_id(),
                    symbol=order.symbol,
                    exchange=order.exchange,
                    action=order.action,
                    product=order.product,
                    quantity=fill_quantity,
                    price=fill_price,
                    trade_value=fill_price * fill_quantity,
                    net_value=fill_price * fill_quantity  # Simplified - no brokerage/taxes for now
                )
                
                self.session.add(trade)
                
                # Update positions
                self._update_position(order, fill_price, fill_quantity)
                
                # Update account balance
                self._update_account_balance(order, fill_price, fill_quantity)
                
                self.session.commit()
                
                logger.info(f"Successfully filled order {order.order_id}: {fill_quantity} @ {fill_price}")
                return True
                
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error filling order {order.order_id}: {e}")
            self._reject_order(order, f"Fill error: {str(e)}")
            return True
    
    def _update_position(self, order: PaperOrder, fill_price: Decimal, fill_quantity: int):
        """
        Update position based on filled order.
        
        Args:
            order: Filled order
            fill_price: Fill price
            fill_quantity: Fill quantity
        """
        # Find existing position
        position = self.session.query(PaperPosition).filter(
            and_(
                PaperPosition.user_id == order.user_id,
                PaperPosition.symbol == order.symbol,
                PaperPosition.exchange == order.exchange,
                PaperPosition.product == order.product
            )
        ).first()
        
        # Calculate quantity change (positive for buy, negative for sell)
        quantity_change = fill_quantity if order.action == 'BUY' else -fill_quantity
        
        if position:
            # Update existing position
            old_quantity = position.quantity
            new_quantity = old_quantity + quantity_change
            
            if new_quantity == 0:
                # Position closed, delete the record
                self.session.delete(position)
            else:
                # Calculate new average price
                if (old_quantity > 0 and quantity_change > 0) or (old_quantity < 0 and quantity_change < 0):
                    # Same direction - calculate weighted average
                    total_value = (position.average_price * abs(old_quantity)) + (fill_price * abs(quantity_change))
                    total_quantity = abs(old_quantity) + abs(quantity_change)
                    position.average_price = total_value / total_quantity
                else:
                    # Opposite direction - partial/full closure
                    if abs(new_quantity) < abs(old_quantity):
                        # Partial closure - average price remains same
                        pass
                    else:
                        # New position in opposite direction
                        position.average_price = fill_price
                
                position.quantity = new_quantity
        else:
            # Create new position
            if quantity_change != 0:  # Only create if there's actually a position
                position = PaperPosition(
                    user_id=order.user_id,
                    symbol=order.symbol,
                    exchange=order.exchange,
                    product=order.product,
                    quantity=quantity_change,
                    average_price=fill_price
                )
                self.session.add(position)
    
    def _update_account_balance(self, order: PaperOrder, fill_price: Decimal, fill_quantity: int):
        """
        Update account balance based on filled order.
        
        Args:
            order: Filled order
            fill_price: Fill price
            fill_quantity: Fill quantity
        """
        account = self.session.query(PaperAccount).filter_by(user_id=order.user_id).first()
        
        if account:
            trade_value = fill_price * fill_quantity
            
            if order.action == 'BUY':
                # Deduct money for buy orders
                account.current_balance -= trade_value
            else:
                # Add money for sell orders
                account.current_balance += trade_value
    
    def _reject_order(self, order: PaperOrder, reason: str):
        """
        Reject an order with specified reason.
        
        Args:
            order: Order to reject
            reason: Rejection reason
        """
        try:
            order.status = 'REJECTED'
            order.rejection_reason = reason
            self.session.commit()
            logger.warning(f"Rejected order {order.order_id}: {reason}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error rejecting order {order.order_id}: {e}")
    
    def start_monitoring(self):
        """Start background monitoring thread for pending orders"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring = False
        self._monitoring_thread = threading.Thread(target=self._monitor_pending_orders, daemon=True)
        self._monitoring_thread.start()
        logger.info("Started order monitoring thread")
    
    def stop_monitoring(self):
        """Stop background monitoring thread"""
        self._stop_monitoring = True
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("Stopped order monitoring thread")
    
    def _monitor_pending_orders(self):
        """
        Background thread to monitor and process pending orders.
        
        This method runs continuously and checks pending orders against
        current market conditions.
        """
        logger.info("Order monitoring thread started")
        
        while not self._stop_monitoring:
            try:
                # Get all pending orders
                pending_orders = self.session.query(PaperOrder).filter_by(status='PENDING').all()
                
                for order in pending_orders:
                    if self._stop_monitoring:
                        break
                    
                    # Process each pending order
                    self.process_order(order)
                
                # Sleep for a short interval before next check
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in order monitoring thread: {e}")
                time.sleep(5)  # Wait longer on error
        
        logger.info("Order monitoring thread stopped")
    
    def get_pending_orders_count(self, user_id: Optional[str] = None) -> int:
        """
        Get count of pending orders.
        
        Args:
            user_id: Optional user filter
            
        Returns:
            Number of pending orders
        """
        query = self.session.query(PaperOrder).filter_by(status='PENDING')
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.count()
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            bool: True if order was cancelled, False otherwise
        """
        try:
            order = self.session.query(PaperOrder).filter_by(order_id=order_id, status='PENDING').first()
            
            if order:
                order.status = 'CANCELLED'
                order.cancelled_timestamp = datetime.utcnow()
                self.session.commit()
                logger.info(f"Cancelled order {order_id}")
                return True
            else:
                logger.warning(f"Order {order_id} not found or not pending")
                return False
                
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_engine_statistics(self) -> Dict[str, any]:
        """
        Get order matching engine statistics.
        
        Returns:
            Dictionary containing engine statistics
        """
        try:
            total_orders = self.session.query(PaperOrder).count()
            pending_orders = self.session.query(PaperOrder).filter_by(status='PENDING').count()
            filled_orders = self.session.query(PaperOrder).filter_by(status='FILLED').count()
            cancelled_orders = self.session.query(PaperOrder).filter_by(status='CANCELLED').count()
            rejected_orders = self.session.query(PaperOrder).filter_by(status='REJECTED').count()
            
            return {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'filled_orders': filled_orders,
                'cancelled_orders': cancelled_orders,
                'rejected_orders': rejected_orders,
                'fill_rate': (filled_orders / total_orders * 100) if total_orders > 0 else 0,
                'monitoring_active': not self._stop_monitoring,
                'market_data_cache_stats': self.market_data_feed.get_cache_stats()
            }
            
        except Exception as e:
            logger.error(f"Error getting engine statistics: {e}")
            return {}