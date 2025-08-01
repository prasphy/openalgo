"""
Paper trading database models and utilities.

This module defines the SQLAlchemy models for the paper trading system,
including accounts, orders, positions, and trades. It maintains a separate
database to ensure complete isolation from live trading data.
"""

import os
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Numeric, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, declarative_base
from sqlalchemy.sql import func
from utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Paper trading database URL - separate from main database
PAPER_TRADING_DATABASE_URL = os.getenv(
    'PAPER_TRADING_DATABASE_URL', 
    'sqlite:///db/paper_trading.db'
)

# Create paper trading database engine
from sqlalchemy.engine.url import make_url
url_obj = make_url(PAPER_TRADING_DATABASE_URL)
engine_kwargs = {"echo": False}
if url_obj.get_backend_name() != "sqlite":
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 50,
        "pool_timeout": 30,
    })
paper_engine = create_engine(PAPER_TRADING_DATABASE_URL, **engine_kwargs)

# Create session factory
paper_db_session = scoped_session(sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=paper_engine
))

# Create declarative base
PaperBase = declarative_base()
PaperBase.query = paper_db_session.query_property()


class PaperAccount(PaperBase):
    """
    Paper trading account model.
    
    Stores account information including initial balance, current balance,
    and currency settings for each user's paper trading account.
    """
    __tablename__ = 'paper_accounts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True, index=True)
    initial_balance = Column(Numeric(15, 2), nullable=False, default=50000.00)
    current_balance = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default='INR')
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    orders = relationship("PaperOrder", back_populates="account", cascade="all, delete-orphan")
    positions = relationship("PaperPosition", back_populates="account", cascade="all, delete-orphan")
    trades = relationship("PaperTrade", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PaperAccount(user_id='{self.user_id}', balance={self.current_balance}, currency='{self.currency}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert account to dictionary representation"""
        return {
            'user_id': self.user_id,
            'initial_balance': float(self.initial_balance),
            'current_balance': float(self.current_balance),
            'currency': self.currency,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active
        }


class PaperOrder(PaperBase):
    """
    Paper trading order model.
    
    Stores all order information including pending, filled, and cancelled orders.
    """
    __tablename__ = 'paper_orders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey('paper_accounts.user_id'), nullable=False, index=True)
    order_id = Column(String(50), nullable=False, unique=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # BUY/SELL
    product = Column(String(20), nullable=False)  # MIS/CNC/NRML
    price_type = Column(String(20), nullable=False)  # MARKET/LIMIT/SL/SLM
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=True)  # For limit orders
    trigger_price = Column(Numeric(10, 2), nullable=True)  # For stop loss orders
    disclosed_quantity = Column(Integer, default=0)
    status = Column(String(20), nullable=False, default='PENDING')  # PENDING/FILLED/CANCELLED/REJECTED
    filled_quantity = Column(Integer, default=0)
    average_price = Column(Numeric(10, 2), nullable=True)
    order_timestamp = Column(DateTime(timezone=True), default=func.now())
    filled_timestamp = Column(DateTime(timezone=True), nullable=True)
    cancelled_timestamp = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    strategy = Column(String(100), nullable=True)  # Strategy name if applicable
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    account = relationship("PaperAccount", back_populates="orders")
    trades = relationship("PaperTrade", back_populates="order", cascade="all, delete-orphan")
    
    # Composite indexes for efficient queries
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_symbol_exchange', 'symbol', 'exchange'),
        Index('idx_order_timestamp', 'order_timestamp'),
    )
    
    def __repr__(self):
        return f"<PaperOrder(order_id='{self.order_id}', symbol='{self.symbol}', status='{self.status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary representation"""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'action': self.action,
            'product': self.product,
            'price_type': self.price_type,
            'quantity': self.quantity,
            'price': float(self.price) if self.price else None,
            'trigger_price': float(self.trigger_price) if self.trigger_price else None,
            'disclosed_quantity': self.disclosed_quantity,
            'status': self.status,
            'filled_quantity': self.filled_quantity,
            'average_price': float(self.average_price) if self.average_price else None,
            'order_timestamp': self.order_timestamp.isoformat(),
            'filled_timestamp': self.filled_timestamp.isoformat() if self.filled_timestamp else None,
            'cancelled_timestamp': self.cancelled_timestamp.isoformat() if self.cancelled_timestamp else None,
            'rejection_reason': self.rejection_reason,
            'strategy': self.strategy
        }


class PaperPosition(PaperBase):
    """
    Paper trading position model.
    
    Stores current position information for each symbol, exchange, and product type combination.
    """
    __tablename__ = 'paper_positions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey('paper_accounts.user_id'), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=False)
    product = Column(String(20), nullable=False)  # MIS/CNC/NRML
    quantity = Column(Integer, nullable=False)  # Net quantity (positive for long, negative for short)
    average_price = Column(Numeric(10, 2), nullable=False)
    realized_pnl = Column(Numeric(12, 2), default=0.00)  # Realized P&L
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    account = relationship("PaperAccount", back_populates="positions")
    
    # Unique constraint and indexes
    __table_args__ = (
        UniqueConstraint('user_id', 'symbol', 'exchange', 'product', name='uq_user_position'),
        Index('idx_user_symbol', 'user_id', 'symbol'),
    )
    
    def __repr__(self):
        return f"<PaperPosition(symbol='{self.symbol}', quantity={self.quantity}, avg_price={self.average_price})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary representation"""
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'product': self.product,
            'quantity': self.quantity,
            'average_price': float(self.average_price),
            'realized_pnl': float(self.realized_pnl),
            'updated_at': self.updated_at.isoformat()
        }


class PaperTrade(PaperBase):
    """
    Paper trading trade model.
    
    Stores executed trade information. Each order execution creates one or more trade records.
    """
    __tablename__ = 'paper_trades'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey('paper_accounts.user_id'), nullable=False, index=True)
    order_id = Column(String(50), ForeignKey('paper_orders.order_id'), nullable=False, index=True)
    trade_id = Column(String(50), nullable=False, unique=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # BUY/SELL
    product = Column(String(20), nullable=False)  # MIS/CNC/NRML
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    trade_value = Column(Numeric(15, 2), nullable=False)  # quantity * price
    brokerage = Column(Numeric(8, 2), default=0.00)  # Simulated brokerage
    taxes = Column(Numeric(8, 2), default=0.00)  # Simulated taxes
    net_value = Column(Numeric(15, 2), nullable=False)  # trade_value + brokerage + taxes
    trade_timestamp = Column(DateTime(timezone=True), default=func.now())
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    account = relationship("PaperAccount", back_populates="trades")
    order = relationship("PaperOrder", back_populates="trades")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_user_trade_timestamp', 'user_id', 'trade_timestamp'),
        Index('idx_symbol_exchange_trade', 'symbol', 'exchange'),
    )
    
    def __repr__(self):
        return f"<PaperTrade(trade_id='{self.trade_id}', symbol='{self.symbol}', quantity={self.quantity})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary representation"""
        return {
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'action': self.action,
            'product': self.product,
            'quantity': self.quantity,
            'price': float(self.price),
            'trade_value': float(self.trade_value),
            'brokerage': float(self.brokerage),
            'taxes': float(self.taxes),
            'net_value': float(self.net_value),
            'trade_timestamp': self.trade_timestamp.isoformat()
        }


# Utility functions for database operations
def init_paper_trading_db():
    """Initialize paper trading database tables"""
    try:
        logger.info("Initializing Paper Trading Database")
        PaperBase.metadata.create_all(bind=paper_engine)
        logger.info("Paper Trading Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing paper trading database: {e}")
        raise


def get_paper_trading_session():
    """Get paper trading database session"""
    return paper_db_session


def create_paper_account(user_id: str, initial_balance: float = 50000.00, currency: str = 'INR') -> PaperAccount:
    """
    Create a new paper trading account.
    
    Args:
        user_id: User identifier
        initial_balance: Starting balance for the account
        currency: Account currency (INR, USD, EUR, etc.)
    
    Returns:
        PaperAccount: Created account instance
    """
    try:
        # Check if account already exists
        existing_account = paper_db_session.query(PaperAccount).filter_by(user_id=user_id).first()
        if existing_account:
            logger.warning(f"Paper trading account already exists for user {user_id}")
            return existing_account
        
        # Create new account
        account = PaperAccount(
            user_id=user_id,
            initial_balance=Decimal(str(initial_balance)),
            current_balance=Decimal(str(initial_balance)),
            currency=currency
        )
        
        paper_db_session.add(account)
        paper_db_session.commit()
        
        logger.info(f"Created paper trading account for user {user_id} with balance {initial_balance} {currency}")
        return account
        
    except Exception as e:
        paper_db_session.rollback()
        logger.error(f"Error creating paper trading account: {e}")
        raise


def get_or_create_paper_account(user_id: str) -> PaperAccount:
    """
    Get existing paper trading account or create a new one.
    
    Args:
        user_id: User identifier
    
    Returns:
        PaperAccount: Account instance
    """
    account = paper_db_session.query(PaperAccount).filter_by(user_id=user_id).first()
    if not account:
        # Get default configuration from environment
        default_balance = float(os.getenv('PAPER_DEFAULT_BALANCE', '50000.00'))
        default_currency = os.getenv('PAPER_DEFAULT_CURRENCY', 'INR')
        account = create_paper_account(user_id, default_balance, default_currency)
    return account


def generate_order_id() -> str:
    """Generate a unique order ID"""
    return f"PT{uuid.uuid4().hex[:12].upper()}"


def generate_trade_id() -> str:
    """Generate a unique trade ID"""
    return f"TR{uuid.uuid4().hex[:12].upper()}"


def reset_paper_account(user_id: str) -> bool:
    """
    Reset a paper trading account to initial state.
    
    Args:
        user_id: User identifier
    
    Returns:
        bool: True if reset successful, False otherwise
    """
    try:
        account = paper_db_session.query(PaperAccount).filter_by(user_id=user_id).first()
        if not account:
            logger.warning(f"No paper trading account found for user {user_id}")
            return False
        
        # Delete all related data
        paper_db_session.query(PaperTrade).filter_by(user_id=user_id).delete()
        paper_db_session.query(PaperPosition).filter_by(user_id=user_id).delete()
        paper_db_session.query(PaperOrder).filter_by(user_id=user_id).delete()
        
        # Reset account balance
        account.current_balance = account.initial_balance
        account.updated_at = func.now()
        
        paper_db_session.commit()
        logger.info(f"Reset paper trading account for user {user_id}")
        return True
        
    except Exception as e:
        paper_db_session.rollback()
        logger.error(f"Error resetting paper trading account: {e}")
        return False


def get_account_statistics(user_id: str) -> Dict[str, Any]:
    """
    Get comprehensive account statistics.
    
    Args:
        user_id: User identifier
    
    Returns:
        Dict containing account statistics
    """
    try:
        account = get_or_create_paper_account(user_id)
        
        # Count statistics
        total_orders = paper_db_session.query(PaperOrder).filter_by(user_id=user_id).count()
        filled_orders = paper_db_session.query(PaperOrder).filter_by(user_id=user_id, status='FILLED').count()
        active_positions = paper_db_session.query(PaperPosition).filter_by(user_id=user_id).filter(PaperPosition.quantity != 0).count()
        total_trades = paper_db_session.query(PaperTrade).filter_by(user_id=user_id).count()
        
        # P&L calculations
        total_realized_pnl = paper_db_session.query(func.sum(PaperPosition.realized_pnl)).filter_by(user_id=user_id).scalar() or 0
        
        return {
            'account': account.to_dict(),
            'total_orders': total_orders,
            'filled_orders': filled_orders,
            'active_positions': active_positions,
            'total_trades': total_trades,
            'total_realized_pnl': float(total_realized_pnl),
            'unrealized_pnl': 0.0,  # Will be calculated with live prices
            'profit_loss_percentage': ((float(account.current_balance) - float(account.initial_balance)) / float(account.initial_balance)) * 100
        }
        
    except Exception as e:
        logger.error(f"Error getting account statistics: {e}")
        return {}


# Database session cleanup
def close_paper_trading_session():
    """Close paper trading database session"""
    paper_db_session.remove()