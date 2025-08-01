"""
Unit tests for the trading service factory.

This module tests the factory pattern implementation that switches between
paper trading and live trading services based on environment configuration.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from services.trading_service_factory import TradingServiceFactory, get_trading_service
from services.interfaces.trading_service import ITradingService


class TestTradingServiceFactory:
    """Test cases for TradingServiceFactory"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Clear factory cache before each test
        TradingServiceFactory.clear_cache()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        # Clear factory cache after each test
        TradingServiceFactory.clear_cache()
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'live'})
    @patch('services.live_broker_service.LiveBrokerService')
    def test_get_live_trading_service(self, mock_live_service):
        """Test factory returns LiveBrokerService when OPENALGO_TRADING_MODE=live"""
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_live_service.return_value = mock_instance
        
        # Act
        service = TradingServiceFactory.get_trading_service("test_user", "zerodha")
        
        # Assert
        assert service == mock_instance
        mock_live_service.assert_called_once_with("test_user", "zerodha")
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_get_paper_trading_service(self, mock_paper_service):
        """Test factory returns PaperTradingService when OPENALGO_TRADING_MODE=paper"""
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_paper_service.return_value = mock_instance
        
        # Act
        service = TradingServiceFactory.get_trading_service("test_user", "zerodha")
        
        # Assert
        assert service == mock_instance
        mock_paper_service.assert_called_once_with("test_user", "zerodha")
    
    @patch.dict(os.environ, {}, clear=True)  # Clear OPENALGO_TRADING_MODE
    @patch('services.live_broker_service.LiveBrokerService')
    def test_default_to_live_trading(self, mock_live_service):
        """Test factory defaults to live trading when OPENALGO_TRADING_MODE is not set"""
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_live_service.return_value = mock_instance
        
        # Act
        service = TradingServiceFactory.get_trading_service("test_user", "zerodha")
        
        # Assert
        assert service == mock_instance
        mock_live_service.assert_called_once_with("test_user", "zerodha")
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'invalid'})
    def test_invalid_trading_mode(self):
        """Test factory raises ValueError for invalid OPENALGO_TRADING_MODE"""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid OPENALGO_TRADING_MODE: 'invalid'"):
            TradingServiceFactory.get_trading_service("test_user", "zerodha")
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_service_caching(self, mock_paper_service):
        """Test that services are cached and reused"""
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_paper_service.return_value = mock_instance
        
        # Act
        service1 = TradingServiceFactory.get_trading_service("test_user", "zerodha")
        service2 = TradingServiceFactory.get_trading_service("test_user", "zerodha")
        
        # Assert
        assert service1 == service2
        assert service1 is service2  # Same instance
        # Should only be called once due to caching
        mock_paper_service.assert_called_once_with("test_user", "zerodha")
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_different_users_get_different_services(self, mock_paper_service):
        """Test that different users get different service instances"""
        # Arrange
        mock_instance1 = MagicMock(spec=ITradingService)
        mock_instance2 = MagicMock(spec=ITradingService)
        mock_paper_service.side_effect = [mock_instance1, mock_instance2]
        
        # Act
        service1 = TradingServiceFactory.get_trading_service("user1", "zerodha")
        service2 = TradingServiceFactory.get_trading_service("user2", "zerodha")
        
        # Assert
        assert service1 != service2
        assert service1 is not service2
        assert mock_paper_service.call_count == 2
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_different_brokers_get_different_services(self, mock_paper_service):
        """Test that different brokers get different service instances"""
        # Arrange
        mock_instance1 = MagicMock(spec=ITradingService)
        mock_instance2 = MagicMock(spec=ITradingService)
        mock_paper_service.side_effect = [mock_instance1, mock_instance2]
        
        # Act
        service1 = TradingServiceFactory.get_trading_service("test_user", "zerodha")
        service2 = TradingServiceFactory.get_trading_service("test_user", "angel")
        
        # Assert
        assert service1 != service2
        assert service1 is not service2
        assert mock_paper_service.call_count == 2
    
    def test_clear_cache(self):
        """Test cache clearing functionality"""
        # Arrange - populate cache
        with patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'}):
            with patch('services.paper_trading_service.PaperTradingService') as mock_service:
                mock_instance = MagicMock(spec=ITradingService)
                mock_service.return_value = mock_instance
                
                # Get service to populate cache
                TradingServiceFactory.get_trading_service("test_user", "zerodha")
                assert TradingServiceFactory.get_service_count() == 1
                
                # Act
                TradingServiceFactory.clear_cache()
                
                # Assert
                assert TradingServiceFactory.get_service_count() == 0
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    def test_get_current_mode(self):
        """Test getting current trading mode"""
        assert TradingServiceFactory.get_current_mode() == 'paper'
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'live'})
    def test_is_paper_trading_mode(self):
        """Test paper trading mode detection"""
        assert TradingServiceFactory.is_paper_trading_mode() is False
        assert TradingServiceFactory.is_live_trading_mode() is True
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    def test_is_live_trading_mode(self):
        """Test live trading mode detection"""
        assert TradingServiceFactory.is_paper_trading_mode() is True
        assert TradingServiceFactory.is_live_trading_mode() is False
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_get_cached_services(self, mock_paper_service):
        """Test getting information about cached services"""
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_paper_service.return_value = mock_instance
        
        # Act
        TradingServiceFactory.get_trading_service("user1", "zerodha")
        TradingServiceFactory.get_trading_service("user2", "angel")
        
        cached_services = TradingServiceFactory.get_cached_services()
        
        # Assert
        assert len(cached_services) == 2
        assert "user1_zerodha" in cached_services
        assert "user2_angel" in cached_services
        assert all("Mock" in service_type for service_type in cached_services.values())
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService', side_effect=ImportError("Module not found"))
    def test_import_error_handling(self, mock_paper_service):
        """Test handling of import errors"""
        # Act & Assert
        with pytest.raises(ImportError, match="Paper trading service not available"):
            TradingServiceFactory.get_trading_service("test_user", "zerodha")


class TestConvenienceFunctions:
    """Test cases for convenience functions"""
    
    def setup_method(self):
        """Setup for each test method"""
        TradingServiceFactory.clear_cache()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        TradingServiceFactory.clear_cache()
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_get_trading_service_convenience_function(self, mock_paper_service):
        """Test the convenience function for getting trading service"""
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_paper_service.return_value = mock_instance
        
        # Act
        service = get_trading_service("test_user", "zerodha")
        
        # Assert
        assert service == mock_instance
        mock_paper_service.assert_called_once_with("test_user", "zerodha")
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    def test_get_current_trading_mode_convenience_function(self):
        """Test convenience function for getting current trading mode"""
        from services.trading_service_factory import get_current_trading_mode
        assert get_current_trading_mode() == 'paper'
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    def test_is_paper_trading_enabled_convenience_function(self):
        """Test convenience function for paper trading detection"""
        from services.trading_service_factory import is_paper_trading_enabled
        assert is_paper_trading_enabled() is True
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'live'})
    def test_is_live_trading_enabled_convenience_function(self):
        """Test convenience function for live trading detection"""
        from services.trading_service_factory import is_live_trading_enabled
        assert is_live_trading_enabled() is True


class TestThreadSafety:
    """Test thread safety of the factory"""
    
    def setup_method(self):
        """Setup for each test method"""
        TradingServiceFactory.clear_cache()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        TradingServiceFactory.clear_cache()
    
    @patch.dict(os.environ, {'OPENALGO_TRADING_MODE': 'paper'})
    @patch('services.paper_trading_service.PaperTradingService')
    def test_concurrent_access(self, mock_paper_service):
        """Test thread-safe access to factory"""
        import threading
        import time
        
        # Arrange
        mock_instance = MagicMock(spec=ITradingService)
        mock_paper_service.return_value = mock_instance
        
        results = []
        
        def get_service():
            time.sleep(0.01)  # Small delay to increase chance of race condition
            service = TradingServiceFactory.get_trading_service("test_user", "zerodha")
            results.append(service)
        
        # Act - Create multiple threads accessing factory concurrently
        threads = [threading.Thread(target=get_service) for _ in range(10)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Assert - All threads should get the same instance
        assert len(results) == 10
        assert all(service == mock_instance for service in results)
        # Service should only be created once due to caching and thread safety
        mock_paper_service.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])