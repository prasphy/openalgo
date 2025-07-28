"""
Momentum Strategy

A momentum-based strategy that identifies stocks with strong price momentum
and volume confirmation for potential continuation moves.
"""

from custom_strategies.base_strategy import BaseStrategy
import pandas as pd
from typing import List
from datetime import datetime, timedelta


class MomentumStrategy(BaseStrategy):
    """
    Momentum Trading Strategy
    
    This strategy identifies stocks showing strong momentum with:
    1. Price moving above a certain percentage in recent days
    2. Volume above average to confirm the move
    3. Current price near recent highs
    """
    
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Strategy parameters
        self.momentum_period = self.get_config_value('momentum_period', 5)
        self.min_price_change = self.get_config_value('min_price_change', 3.0)  # 3% minimum
        self.volume_multiplier = self.get_config_value('volume_multiplier', 1.5)  # 1.5x avg volume
        self.near_high_threshold = self.get_config_value('near_high_threshold', 0.95)  # 95% of recent high
        self.symbols = self.get_config_value('symbols', ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK'])
        self.exchange = self.get_config_value('exchange', 'NSE')
        self.lookback_days = self.get_config_value('lookback_days', 30)
        
        self.log_info(f"Momentum Strategy initialized - Period: {self.momentum_period}, Min Change: {self.min_price_change}%")
    
    def calculate_momentum_metrics(self, data: List[dict]) -> dict:
        """
        Calculate momentum metrics from price data.
        
        Args:
            data: List of OHLCV data dictionaries
            
        Returns:
            Dictionary with momentum metrics
        """
        if len(data) < self.momentum_period + 10:
            return {}
        
        df = pd.DataFrame(data)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        
        # Calculate metrics
        current_price = df['close'].iloc[-1]
        period_start_price = df['close'].iloc[-(self.momentum_period + 1)]
        
        # Price momentum
        price_change = ((current_price - period_start_price) / period_start_price) * 100
        
        # Volume metrics
        recent_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-20:].mean()  # 20-day average volume
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0
        
        # Price position relative to recent high
        recent_high = df['high'].iloc[-self.momentum_period:].max()
        price_vs_high = current_price / recent_high if recent_high > 0 else 0
        
        # Volatility check (standard deviation of returns)
        returns = df['close'].pct_change().dropna()
        volatility = returns.std() * 100  # As percentage
        
        return {
            'current_price': current_price,
            'price_change': price_change,
            'volume_ratio': volume_ratio,
            'price_vs_high': price_vs_high,
            'recent_high': recent_high,
            'volatility': volatility,
            'avg_volume': avg_volume,
            'recent_volume': recent_volume
        }
    
    def check_momentum_signal(self, metrics: dict) -> bool:
        """
        Check if momentum criteria are met.
        
        Args:
            metrics: Momentum metrics dictionary
            
        Returns:
            True if momentum signal detected, False otherwise
        """
        if not metrics:
            return False
        
        # Check all momentum criteria
        price_momentum_ok = metrics['price_change'] >= self.min_price_change
        volume_ok = metrics['volume_ratio'] >= self.volume_multiplier
        near_high_ok = metrics['price_vs_high'] >= self.near_high_threshold
        
        # Additional filters
        not_too_volatile = metrics['volatility'] < 5.0  # Less than 5% daily volatility
        has_volume = metrics['recent_volume'] > 10000  # Minimum volume threshold
        
        signal = (price_momentum_ok and 
                 volume_ok and 
                 near_high_ok and 
                 not_too_volatile and 
                 has_volume)
        
        return signal
    
    def analyze_symbol(self, symbol: str) -> bool:
        """
        Analyze a single symbol for momentum signals.
        
        Args:
            symbol: Symbol to analyze
            
        Returns:
            True if momentum signal detected, False otherwise
        """
        try:
            # Calculate date range
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d')
            
            # Get historical data
            self.log_info(f"Fetching historical data for {symbol}")
            history_response = self.get_history(symbol, self.exchange, '1d', start_date, end_date)
            
            if history_response.get('status') != 'success':
                self.log_warning(f"Failed to get history for {symbol}: {history_response.get('message', 'Unknown error')}")
                return False
            
            history_data = history_response.get('data', [])
            if len(history_data) < self.momentum_period + 10:
                self.log_warning(f"Insufficient data for {symbol}: {len(history_data)} bars")
                return False
            
            # Calculate momentum metrics
            metrics = self.calculate_momentum_metrics(history_data)
            
            if not metrics:
                self.log_warning(f"Could not calculate momentum metrics for {symbol}")
                return False
            
            # Check for momentum signal
            signal = self.check_momentum_signal(metrics)
            
            if signal:
                self.log_info(f"Momentum signal detected for {symbol}:")
                self.log_info(f"  Price change: {metrics['price_change']:.2f}%")
                self.log_info(f"  Volume ratio: {metrics['volume_ratio']:.2f}x")
                self.log_info(f"  Price vs high: {metrics['price_vs_high']:.2f}")
                self.log_info(f"  Volatility: {metrics['volatility']:.2f}%")
                
                # Additional validation: get current quote
                quote_response = self.get_quotes(symbol, self.exchange)
                if quote_response.get('status') == 'success':
                    ltp = quote_response.get('data', {}).get('ltp', 0)
                    self.log_info(f"Current LTP for {symbol}: {ltp}")
                    return True
                else:
                    self.log_warning(f"Could not get current quote for {symbol}")
                    return False
            else:
                # Log why signal was not generated
                if metrics['price_change'] < self.min_price_change:
                    self.log_info(f"{symbol}: Insufficient price momentum ({metrics['price_change']:.2f}%)")
                elif metrics['volume_ratio'] < self.volume_multiplier:
                    self.log_info(f"{symbol}: Low volume confirmation ({metrics['volume_ratio']:.2f}x)")
                elif metrics['price_vs_high'] < self.near_high_threshold:
                    self.log_info(f"{symbol}: Not near recent high ({metrics['price_vs_high']:.2f})")
            
            return False
            
        except Exception as e:
            self.log_error(f"Error analyzing {symbol}: {str(e)}")
            return False
    
    def execute(self) -> List[str]:
        """
        Execute the momentum strategy.
        
        Returns:
            List of symbols that showed momentum signals
        """
        self.log_info("Executing Momentum Strategy")
        
        signals = []
        
        for symbol in self.symbols:
            try:
                if self.analyze_symbol(symbol):
                    signals.append(symbol)
                    self.log_info(f"Added {symbol} to signal list")
                
            except Exception as e:
                self.log_error(f"Error processing {symbol}: {str(e)}")
                continue
        
        self.log_info(f"Strategy execution completed. Signals generated for: {signals}")
        
        return self.validate_symbol_list(signals)