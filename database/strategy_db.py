from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, Time, Text
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import os
import logging
import json

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(
    DATABASE_URL,
    pool_size=50,
    max_overflow=100,
    pool_timeout=10
)

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class Strategy(Base):
    """Model for trading strategies"""
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    webhook_id = Column(String(36), unique=True, nullable=False)  # UUID
    user_id = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False, default='tradingview')  # Platform type (tradingview, chartink, custom, etc)
    
    # New fields for custom strategies - using Text for SQLite compatibility
    strategy_type = Column(String(20), nullable=False, default='webhook')  # 'webhook' or 'custom'
    strategy_file = Column(String(255), nullable=True)  # Path to custom strategy file (relative to custom_strategies)
    strategy_category = Column(String(50), nullable=True)  # 'examples' or 'user_strategies'
    execution_mode = Column(String(20), nullable=False, default='immediate')  # 'immediate', 'queue', 'schedule'
    schedule_config = Column(Text, nullable=True)  # JSON config for scheduling (stored as text for SQLite)
    strategy_config = Column(Text, nullable=True)  # JSON config for strategy parameters (stored as text for SQLite)
    
    is_active = Column(Boolean, default=True)
    is_intraday = Column(Boolean, default=True)
    trading_mode = Column(String(10), nullable=False, default='LONG')  # LONG, SHORT, or BOTH
    start_time = Column(String(5))  # HH:MM format
    end_time = Column(String(5))  # HH:MM format
    squareoff_time = Column(String(5))  # HH:MM format
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    symbol_mappings = relationship("StrategySymbolMapping", back_populates="strategy", cascade="all, delete-orphan")
    
    @property
    def schedule_config_json(self):
        """Get schedule_config as parsed JSON."""
        if self.schedule_config:
            try:
                return json.loads(self.schedule_config)
            except (json.JSONDecodeError, TypeError):
                return None
        return None
    
    @schedule_config_json.setter
    def schedule_config_json(self, value):
        """Set schedule_config from JSON object."""
        if value is not None:
            self.schedule_config = json.dumps(value)
        else:
            self.schedule_config = None
    
    @property
    def strategy_config_json(self):
        """Get strategy_config as parsed JSON."""
        if self.strategy_config:
            try:
                return json.loads(self.strategy_config)
            except (json.JSONDecodeError, TypeError):
                return None
        return None
    
    @strategy_config_json.setter
    def strategy_config_json(self, value):
        """Set strategy_config from JSON object."""
        if value is not None:
            self.strategy_config = json.dumps(value)
        else:
            self.strategy_config = None

class StrategySymbolMapping(Base):
    """Model for symbol mappings in strategies"""
    __tablename__ = 'strategy_symbol_mappings'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    product_type = Column(String(10), nullable=False)  # MIS/CNC
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    strategy = relationship("Strategy", back_populates="symbol_mappings")

def init_db():
    """Initialize the database"""
    logger.info("Initializing Strategy DB")
    Base.metadata.create_all(bind=engine)

def create_strategy(name, webhook_id, user_id, is_intraday=True, trading_mode='LONG', start_time=None, end_time=None, squareoff_time=None, platform='tradingview', strategy_type='webhook', strategy_file=None, strategy_category=None, execution_mode='immediate', schedule_config=None, strategy_config=None):
    """Create a new strategy"""
    try:
        # Convert JSON objects to strings for SQLite storage
        schedule_config_str = json.dumps(schedule_config) if schedule_config else None
        strategy_config_str = json.dumps(strategy_config) if strategy_config else None
        
        strategy = Strategy(
            name=name,
            webhook_id=webhook_id,
            user_id=user_id,
            is_intraday=is_intraday,
            trading_mode=trading_mode,
            start_time=start_time,
            end_time=end_time,
            squareoff_time=squareoff_time,
            platform=platform,
            strategy_type=strategy_type,
            strategy_file=strategy_file,
            strategy_category=strategy_category,
            execution_mode=execution_mode,
            schedule_config=schedule_config_str,
            strategy_config=strategy_config_str
        )
        db_session.add(strategy)
        db_session.commit()
        return strategy
    except Exception as e:
        logger.error(f"Error creating strategy: {str(e)}")
        db_session.rollback()
        return None

def create_custom_strategy(name, webhook_id, user_id, strategy_file, strategy_category='user_strategies', execution_mode='immediate', schedule_config=None, strategy_config=None, **kwargs):
    """Create a new custom strategy"""
    return create_strategy(
        name=name,
        webhook_id=webhook_id,
        user_id=user_id,
        platform='custom',
        strategy_type='custom',
        strategy_file=strategy_file,
        strategy_category=strategy_category,
        execution_mode=execution_mode,
        schedule_config=schedule_config,
        strategy_config=strategy_config,
        **kwargs
    )

def get_strategy(strategy_id):
    """Get strategy by ID"""
    try:
        return Strategy.query.get(strategy_id)
    except Exception as e:
        logger.error(f"Error getting strategy {strategy_id}: {str(e)}")
        return None

def get_strategy_by_webhook_id(webhook_id):
    """Get strategy by webhook ID"""
    try:
        return Strategy.query.filter_by(webhook_id=webhook_id).first()
    except Exception as e:
        logger.error(f"Error getting strategy by webhook ID {webhook_id}: {str(e)}")
        return None

def get_all_strategies():
    """Get all strategies"""
    try:
        return Strategy.query.all()
    except Exception as e:
        logger.error(f"Error getting all strategies: {str(e)}")
        return []

def get_user_strategies(user_id):
    """Get all strategies for a user"""
    try:
        logger.info(f"Fetching strategies for user: {user_id}")
        strategies = Strategy.query.filter_by(user_id=user_id).all()
        logger.info(f"Found {len(strategies)} strategies")
        return strategies
    except Exception as e:
        logger.error(f"Error getting user strategies for {user_id}: {str(e)}")
        return []

def get_custom_strategies(user_id=None):
    """Get all custom strategies, optionally filtered by user"""
    try:
        query = Strategy.query.filter_by(strategy_type='custom')
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.all()
    except Exception as e:
        logger.error(f"Error getting custom strategies: {str(e)}")
        return []

def get_strategies_by_execution_mode(execution_mode, user_id=None):
    """Get strategies by execution mode"""
    try:
        query = Strategy.query.filter_by(execution_mode=execution_mode, is_active=True)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.all()
    except Exception as e:
        logger.error(f"Error getting strategies by execution mode {execution_mode}: {str(e)}")
        return []

def delete_strategy(strategy_id):
    """Delete strategy and its symbol mappings"""
    try:
        strategy = get_strategy(strategy_id)
        if not strategy:
            return False
        
        db_session.delete(strategy)
        db_session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting strategy {strategy_id}: {str(e)}")
        db_session.rollback()
        return False

def toggle_strategy(strategy_id):
    """Toggle strategy active status"""
    try:
        strategy = get_strategy(strategy_id)
        if not strategy:
            return None
        
        strategy.is_active = not strategy.is_active
        db_session.commit()
        return strategy
    except Exception as e:
        logger.error(f"Error toggling strategy {strategy_id}: {str(e)}")
        db_session.rollback()
        return None

def update_strategy_times(strategy_id, start_time=None, end_time=None, squareoff_time=None):
    """Update strategy trading times"""
    try:
        strategy = Strategy.query.get(strategy_id)
        if strategy:
            if start_time is not None:
                strategy.start_time = start_time
            if end_time is not None:
                strategy.end_time = end_time
            if squareoff_time is not None:
                strategy.squareoff_time = squareoff_time
            db_session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating strategy times {strategy_id}: {str(e)}")
        db_session.rollback()
        return False

def update_strategy_config(strategy_id, strategy_config=None, schedule_config=None, execution_mode=None):
    """Update strategy configuration"""
    try:
        strategy = Strategy.query.get(strategy_id)
        if strategy:
            if strategy_config is not None:
                strategy.strategy_config = json.dumps(strategy_config) if strategy_config else None
            if schedule_config is not None:
                strategy.schedule_config = json.dumps(schedule_config) if schedule_config else None
            if execution_mode is not None:
                strategy.execution_mode = execution_mode
            strategy.updated_at = func.now()
            db_session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating strategy config {strategy_id}: {str(e)}")
        db_session.rollback()
        return False

def add_symbol_mapping(strategy_id, symbol, exchange, quantity, product_type):
    """Add symbol mapping to strategy"""
    try:
        mapping = StrategySymbolMapping(
            strategy_id=strategy_id,
            symbol=symbol,
            exchange=exchange,
            quantity=quantity,
            product_type=product_type
        )
        db_session.add(mapping)
        db_session.commit()
        return mapping
    except Exception as e:
        logger.error(f"Error adding symbol mapping: {str(e)}")
        db_session.rollback()
        return None

def bulk_add_symbol_mappings(strategy_id, mappings):
    """Add multiple symbol mappings at once"""
    try:
        for mapping_data in mappings:
            mapping = StrategySymbolMapping(
                strategy_id=strategy_id,
                **mapping_data
            )
            db_session.add(mapping)
        db_session.commit()
        return True
    except Exception as e:
        logger.error(f"Error bulk adding symbol mappings: {str(e)}")
        db_session.rollback()
        return False

def get_symbol_mappings(strategy_id):
    """Get all symbol mappings for a strategy"""
    try:
        return StrategySymbolMapping.query.filter_by(strategy_id=strategy_id).all()
    except Exception as e:
        logger.error(f"Error getting symbol mappings: {str(e)}")
        return []

def delete_symbol_mapping(mapping_id):
    """Delete a symbol mapping"""
    try:
        mapping = StrategySymbolMapping.query.get(mapping_id)
        if mapping:
            db_session.delete(mapping)
            db_session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting symbol mapping {mapping_id}: {str(e)}")
        db_session.rollback()
        return False
