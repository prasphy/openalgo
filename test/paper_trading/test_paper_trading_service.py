"""
Unit tests for the paper trading service implementation.

This module tests the PaperTradingService class which implements the ITradingService
interface for paper trading simulation.
"""

import pytest
import os
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal
from datetime import datetime
from services.paper_trading_service import PaperTradingService
from database.paper_trading_db import PaperAccount, PaperOrder, PaperPosition, PaperTrade


class TestPaperTradingService:
    """Test cases for PaperTradingService"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Mock the database session and related components
        self.mock_session = MagicMock()
        self.mock_account = MagicMock(spec=PaperAccount)
        self.mock_account.user_id = "test_user"
        self.mock_account.current_balance = Decimal('50000.00')
        self.mock_account.initial_balance = Decimal('50000.00')
        self.mock_account.currency = 'INR'
        
        # Patch dependencies
        self.session_patcher = patch('services.paper_trading_service.get_paper_trading_session')
        self.account_patcher = patch('services.paper_trading_service.get_or_create_paper_account')
        self.market_feed_patcher = patch('services.paper_trading_service.MarketDataFeed')
        self.matching_engine_patcher = patch('services.paper_trading_service.OrderMatchingEngine')
        
        self.mock_session_func = self.session_patcher.start()
        self.mock_account_func = self.account_patcher.start()
        self.mock_market_feed_class = self.market_feed_patcher.start()
        self.mock_matching_engine_class = self.matching_engine_patcher.start()
        
        # Setup mock returns
        self.mock_session_func.return_value = self.mock_session
        self.mock_account_func.return_value = self.mock_account
        self.mock_market_feed = MagicMock()
        self.mock_matching_engine = MagicMock()
        self.mock_market_feed_class.return_value = self.mock_market_feed
        self.mock_matching_engine_class.return_value = self.mock_matching_engine
        
        # Create service instance
        self.service = PaperTradingService("test_user", "zerodha")
    
    def teardown_method(self):
        """Cleanup after each test method"""
        self.session_patcher.stop()
        self.account_patcher.stop()
        self.market_feed_patcher.stop()
        self.matching_engine_patcher.stop()
    
    def test_initialization(self):
        """Test service initialization"""
        assert self.service.user_id == "test_user"
        assert self.service.broker == "zerodha"
        assert self.service.account == self.mock_account
        
        # Verify dependencies were created
        self.mock_market_feed_class.assert_called_once_with("zerodha", "paper_trading_mock_token")
        self.mock_matching_engine_class.assert_called_once_with(self.mock_market_feed)
        self.mock_account_func.assert_called_once_with("test_user")
    
    @patch('services.paper_trading_service.generate_order_id')
    def test_place_order_success(self, mock_order_id):
        """Test successful order placement"""
        # Arrange
        mock_order_id.return_value = "PT123456789ABC"
        order_data = {
            'symbol': 'RELIANCE',
            'exchange': 'NSE',
            'action': 'BUY',
            'product': 'MIS',
            'pricetype': 'MARKET',
            'quantity': 10
        }
        
        # Act
        success, response, status_code = self.service.place_order(order_data, "mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['status'] == 'success'
        assert response['orderid'] == "PT123456789ABC"
        
        # Verify order was added to session and processed
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
        self.mock_matching_engine.process_order.assert_called_once()
    
    def test_place_order_missing_fields(self):
        """Test order placement with missing required fields"""
        # Arrange
        order_data = {
            'symbol': 'RELIANCE',
            'exchange': 'NSE'
            # Missing required fields
        }
        
        # Act
        success, response, status_code = self.service.place_order(order_data, "mock_token")
        
        # Assert
        assert success is False
        assert status_code == 400
        assert response['status'] == 'error'
        assert 'Missing required fields' in response['message']
    
    def test_place_order_exception_handling(self):
        """Test order placement exception handling"""
        # Arrange
        order_data = {
            'symbol': 'RELIANCE',
            'exchange': 'NSE',
            'action': 'BUY',
            'product': 'MIS',
            'pricetype': 'MARKET',
            'quantity': 10
        }
        self.mock_session.add.side_effect = Exception("Database error")
        
        # Act
        success, response, status_code = self.service.place_order(order_data, "mock_token")
        
        # Assert
        assert success is False
        assert status_code == 500
        assert response['status'] == 'error'
        assert 'Failed to place order' in response['message']
        self.mock_session.rollback.assert_called_once()
    
    def test_get_positions_success(self):
        """Test successful positions retrieval"""
        # Arrange
        mock_position = MagicMock(spec=PaperPosition)
        mock_position.symbol = 'RELIANCE'
        mock_position.exchange = 'NSE'
        mock_position.product = 'MIS'
        mock_position.quantity = 10
        mock_position.average_price = Decimal('2450.50')
        mock_position.realized_pnl = Decimal('0.00')
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [mock_position]
        self.mock_market_feed.get_live_price.return_value = Decimal('2500.00')
        
        # Act
        success, response, status_code = self.service.get_positions("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['status'] == 'success'
        assert len(response['data']) == 1
        
        position_data = response['data'][0]
        assert position_data['symbol'] == 'RELIANCE'
        assert position_data['quantity'] == 10
        assert position_data['average_price'] == 2450.50
        assert position_data['ltp'] == 2500.00
        assert position_data['pnl'] == 495.0  # (2500-2450.50) * 10
    
    def test_get_positions_no_current_price(self):
        """Test positions retrieval when current price unavailable"""
        # Arrange
        mock_position = MagicMock(spec=PaperPosition)
        mock_position.symbol = 'RELIANCE'
        mock_position.exchange = 'NSE'
        mock_position.product = 'MIS'
        mock_position.quantity = 10
        mock_position.average_price = Decimal('2450.50')
        mock_position.realized_pnl = Decimal('0.00')
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [mock_position]
        self.mock_market_feed.get_live_price.return_value = None
        
        # Act
        success, response, status_code = self.service.get_positions("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        
        position_data = response['data'][0]
        assert position_data['pnl'] == 0.0  # No P&L when price unavailable
        assert position_data['ltp'] == 2450.50  # Falls back to average price
    
    def test_get_open_orders_success(self):
        """Test successful open orders retrieval"""
        # Arrange
        mock_order = MagicMock(spec=PaperOrder)
        mock_order.to_dict.return_value = {
            'order_id': 'PT123456789ABC',
            'symbol': 'RELIANCE',
            'status': 'PENDING'
        }
        
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.order_by.return_value.all.return_value = [mock_order]
        
        # Act
        success, response, status_code = self.service.get_open_orders("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['status'] == 'success'
        assert len(response['data']) == 1
        assert response['data'][0]['order_id'] == 'PT123456789ABC'
    
    def test_cancel_order_success(self):
        """Test successful order cancellation"""
        # Arrange
        self.mock_matching_engine.cancel_order.return_value = True
        
        # Act
        success, response, status_code = self.service.cancel_order("PT123456789ABC", "mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['status'] == 'success'
        assert 'cancelled successfully' in response['message']
        self.mock_matching_engine.cancel_order.assert_called_once_with("PT123456789ABC")
    
    def test_cancel_order_not_found(self):
        """Test order cancellation when order not found"""
        # Arrange
        self.mock_matching_engine.cancel_order.return_value = False
        
        # Act
        success, response, status_code = self.service.cancel_order("INVALID_ID", "mock_token")
        
        # Assert
        assert success is False
        assert status_code == 404
        assert response['status'] == 'error'
        assert 'not found' in response['message']
    
    def test_get_account_balance_success(self):
        """Test successful account balance retrieval"""
        # Arrange
        mock_position = MagicMock(spec=PaperPosition)
        mock_position.quantity = 10
        mock_position.average_price = Decimal('2450.50')
        
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = self.mock_account
        self.mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_position]
        
        # Act
        success, response, status_code = self.service.get_account_balance("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['status'] == 'success'
        
        data = response['data']
        assert data['initial_balance'] == 50000.00
        assert data['current_balance'] == 50000.00
        assert data['currency'] == 'INR'
        assert data['account_type'] == 'Paper Trading'
        assert data['position_value'] == 24505.0  # 10 * 2450.50
    
    def test_get_account_balance_no_account(self):
        """Test account balance retrieval when account not found"""
        # Arrange
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        # Act
        success, response, status_code = self.service.get_account_balance("mock_token")
        
        # Assert
        assert success is False
        assert status_code == 404
        assert response['status'] == 'error'
        assert 'not found' in response['message']
    
    def test_get_open_position_success(self):
        """Test successful specific position retrieval"""
        # Arrange
        mock_position = MagicMock(spec=PaperPosition)
        mock_position.quantity = 15
        
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.first.return_value = mock_position
        
        # Act
        success, response, status_code = self.service.get_open_position(
            "RELIANCE", "NSE", "MIS", "mock_token"
        )
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['data']['quantity'] == 15
    
    def test_get_open_position_no_position(self):
        """Test specific position retrieval when position doesn't exist"""
        # Arrange
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.first.return_value = None
        
        # Act
        success, response, status_code = self.service.get_open_position(
            "RELIANCE", "NSE", "MIS", "mock_token"
        )
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['data']['quantity'] == 0
    
    def test_close_position_success(self):
        """Test successful position closure"""
        # Arrange
        mock_position = MagicMock(spec=PaperPosition)
        mock_position.quantity = 10  # Long position
        
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.first.return_value = mock_position
        
        # Mock the place_order call that will be made internally
        with patch.object(self.service, 'place_order') as mock_place_order:
            mock_place_order.return_value = (True, {'status': 'success', 'orderid': 'PT123'}, 200)
            
            # Act
            success, response, status_code = self.service.close_position(
                "RELIANCE", "NSE", "MIS", "mock_token"
            )
            
            # Assert
            assert success is True
            mock_place_order.assert_called_once()
            
            # Verify the close order parameters
            call_args = mock_place_order.call_args[0]
            close_order_data = call_args[0]
            assert close_order_data['action'] == 'SELL'  # Opposite of long position
            assert close_order_data['quantity'] == 10
            assert close_order_data['pricetype'] == 'MARKET'
    
    def test_close_position_no_position(self):
        """Test position closure when no position exists"""
        # Arrange
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.first.return_value = None
        
        # Act
        success, response, status_code = self.service.close_position(
            "RELIANCE", "NSE", "MIS", "mock_token"
        )
        
        # Assert
        assert success is False
        assert status_code == 404
        assert 'No open position found' in response['message']
    
    def test_close_all_positions_success(self):
        """Test successful closure of all positions"""
        # Arrange
        mock_position1 = MagicMock(spec=PaperPosition)
        mock_position1.symbol = 'RELIANCE'
        mock_position1.exchange = 'NSE'
        mock_position1.product = 'MIS'
        mock_position1.quantity = 10
        
        mock_position2 = MagicMock(spec=PaperPosition)
        mock_position2.symbol = 'TCS'
        mock_position2.exchange = 'NSE'
        mock_position2.product = 'MIS'
        mock_position2.quantity = -5  # Short position
        
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.all.return_value = [mock_position1, mock_position2]
        
        # Mock the close_position calls
        with patch.object(self.service, 'close_position') as mock_close_position:
            mock_close_position.return_value = (True, {'status': 'success'}, 200)
            
            # Act
            success, response, status_code = self.service.close_all_positions("mock_token")
            
            # Assert
            assert success is True
            assert status_code == 200
            assert 'Closed 2 positions' in response['message']
            assert mock_close_position.call_count == 2
    
    def test_close_all_positions_no_positions(self):
        """Test closure of all positions when no positions exist"""
        # Arrange
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.all.return_value = []
        
        # Act
        success, response, status_code = self.service.close_all_positions("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert 'No open positions to close' in response['message']
    
    def test_cancel_all_orders_success(self):
        """Test successful cancellation of all orders"""
        # Arrange
        mock_order1 = MagicMock(spec=PaperOrder)
        mock_order1.order_id = 'PT123'
        mock_order2 = MagicMock(spec=PaperOrder)
        mock_order2.order_id = 'PT456'
        
        query_mock = self.mock_session.query.return_value
        query_mock.filter.return_value.all.return_value = [mock_order1, mock_order2]
        self.mock_matching_engine.cancel_order.return_value = True
        
        # Act
        success, response, status_code = self.service.cancel_all_orders("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert 'Cancelled 2 orders' in response['message']
        assert self.mock_matching_engine.cancel_order.call_count == 2
    
    def test_get_holdings_returns_empty(self):
        """Test that holdings returns empty for paper trading"""
        # Act
        success, response, status_code = self.service.get_holdings("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['data'] == []
        assert 'No holdings in paper trading' in response['message']
    
    def test_modify_order_not_implemented(self):
        """Test that order modification is not implemented"""
        # Act
        success, response, status_code = self.service.modify_order(
            "PT123", {'price': 2500}, "mock_token"
        )
        
        # Assert
        assert success is False
        assert status_code == 501
        assert 'not supported' in response['message']
    
    @patch('database.paper_trading_db.reset_paper_account')
    def test_reset_account_success(self, mock_reset):
        """Test successful account reset"""
        # Arrange
        mock_reset.return_value = True
        
        # Act
        success, response, status_code = self.service.reset_account("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert 'reset successfully' in response['message']
        mock_reset.assert_called_once_with("test_user")
    
    @patch('database.paper_trading_db.reset_paper_account')
    def test_reset_account_failure(self, mock_reset):
        """Test account reset failure"""
        # Arrange
        mock_reset.return_value = False
        
        # Act
        success, response, status_code = self.service.reset_account("mock_token")
        
        # Assert
        assert success is False
        assert status_code == 500
        assert 'Failed to reset' in response['message']
    
    @patch('database.paper_trading_db.get_account_statistics')
    def test_get_trading_statistics_success(self, mock_stats):
        """Test successful trading statistics retrieval"""
        # Arrange
        mock_stats.return_value = {
            'total_orders': 10,
            'filled_orders': 8,
            'total_trades': 8,
            'profit_loss_percentage': 5.5
        }
        self.mock_matching_engine.get_engine_statistics.return_value = {
            'pending_orders': 2,
            'fill_rate': 80.0
        }
        
        # Act
        success, response, status_code = self.service.get_trading_statistics("mock_token")
        
        # Assert
        assert success is True
        assert status_code == 200
        assert response['data']['total_orders'] == 10
        assert response['data']['profit_loss_percentage'] == 5.5
        assert response['data']['engine_statistics']['fill_rate'] == 80.0
        assert response['data']['mode'] == 'paper_trading'


if __name__ == '__main__':
    pytest.main([__file__])