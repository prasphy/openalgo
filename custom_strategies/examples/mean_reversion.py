"""
Mean Reversion Strategy

A mean reversion strategy that identifies oversold stocks that are likely
to bounce back toward their average price levels.
"""

from custom_strategies.base_strategy import BaseStrategy
import pandas as pd
from typing import List
from datetime import datetime, timedelta


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Trading Strategy
    
    This strategy identifies stocks that have moved significantly away
    from their moving average and are likely to revert back to the mean.
    """
    
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Strategy parameters
        self.ma_period = self.get_config_value('ma_period', 20)
        self.std_period = self.get_config_value('std_period', 20)
        self.entry_threshold = self.get_config_value('entry_threshold', -2.0)  # -2 standard deviations
        self.max_deviation = self.get_config_value('max_deviation', -2.5)  # Maximum allowed deviation
        self.volume_confirm = self.get_config_value('volume_confirm', True)
        self.symbols = self.get_config_value('symbols', ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK'])
        self.exchange = self.get_config_value('exchange', 'NSE')
        self.lookback_days = self.get_config_value('lookback_days', 50)
        
        self.log_info(f"Mean Reversion Strategy initialized - MA Period: {self.ma_period}, Entry: {self.entry_threshold}σ")
    
    def calculate_bollinger_metrics(self, data: List[dict]) -> dict:
        """
        Calculate Bollinger Band and mean reversion metrics.
        
        Args:
            data: List of OHLCV data dictionaries
            
        Returns:
            Dictionary with mean reversion metrics
        """
        if len(data) < self.ma_period + 5:
            return {}
        
        df = pd.DataFrame(data)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Calculate moving average and standard deviation
        df['ma'] = df['close'].rolling(window=self.ma_period).mean()
        df['std'] = df['close'].rolling(window=self.std_period).std()
        
        # Calculate Bollinger Bands
        df['upper_band'] = df['ma'] + (2 * df['std'])
        df['lower_band'] = df['ma'] - (2 * df['std'])
        
        # Calculate position relative to bands (z-score)
        df['z_score'] = (df['close'] - df['ma']) / df['std']
        
        # Get current values
        current_price = df['close'].iloc[-1]
        current_ma = df['ma'].iloc[-1]
        current_std = df['std'].iloc[-1]
        current_z_score = df['z_score'].iloc[-1]
        current_volume = df['volume'].iloc[-1]
        
        # Volume metrics
        avg_volume = df['volume'].iloc[-10:].mean()  # 10-day average
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        # Support/resistance levels
        recent_low = df['close'].iloc[-10:].min()
        recent_high = df['close'].iloc[-10:].max()
        
        return {
            'current_price': current_price,
            'moving_average': current_ma,
            'std_dev': current_std,
            'z_score': current_z_score,
            'upper_band': current_ma + (2 * current_std),
            'lower_band': current_ma - (2 * current_std),
            'volume_ratio': volume_ratio,
            'recent_low': recent_low,
            'recent_high': recent_high,
            'price_vs_ma': ((current_price - current_ma) / current_ma) * 100
        }
    
    def check_mean_reversion_signal(self, metrics: dict) -> bool:
        """
        Check if mean reversion criteria are met.
        
        Args:
            metrics: Mean reversion metrics dictionary
            
        Returns:
            True if mean reversion signal detected, False otherwise
        """
        if not metrics:
            return False
        
        z_score = metrics['z_score']
        volume_ratio = metrics['volume_ratio']
        current_price = metrics['current_price']
        recent_low = metrics['recent_low']
        
        # Check for oversold condition
        oversold = z_score <= self.entry_threshold
        
        # Not too oversold (avoid falling knives)
        not_extreme = z_score >= self.max_deviation
        
        # Volume confirmation if required
        volume_ok = True
        if self.volume_confirm:
            volume_ok = volume_ratio >= 1.2  # Above average volume
        
        # Price near recent support
        near_support = current_price <= recent_low * 1.02  # Within 2% of recent low
        
        # Additional quality filters
        has_std = metrics['std_dev'] > 0  # Valid standard deviation
        not_gap_down = current_price >= metrics['recent_low'] * 0.95  # Not a major gap down
        
        signal = (oversold and 
                 not_extreme and 
                 volume_ok and 
                 near_support and 
                 has_std and 
                 not_gap_down)
        
        return signal
    
    def analyze_symbol(self, symbol: str) -> bool:
        """
        Analyze a single symbol for mean reversion signals.
        
        Args:
            symbol: Symbol to analyze
            
        Returns:
            True if mean reversion signal detected, False otherwise
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
            if len(history_data) < self.ma_period + 5:
                self.log_warning(f"Insufficient data for {symbol}: {len(history_data)} bars")
                return False
            
            # Calculate mean reversion metrics
            metrics = self.calculate_bollinger_metrics(history_data)
            
            if not metrics:
                self.log_warning(f"Could not calculate mean reversion metrics for {symbol}")
                return False
            
            # Check for mean reversion signal
            signal = self.check_mean_reversion_signal(metrics)
            
            if signal:
                self.log_info(f"Mean reversion signal detected for {symbol}:")
                self.log_info(f"  Z-Score: {metrics['z_score']:.2f}")
                self.log_info(f"  Price vs MA: {metrics['price_vs_ma']:.2f}%")
                self.log_info(f"  Volume ratio: {metrics['volume_ratio']:.2f}x")
                self.log_info(f"  Current price: {metrics['current_price']:.2f}")
                self.log_info(f"  Moving average: {metrics['moving_average']:.2f}")
                
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
                z_score = metrics.get('z_score', 0)
                if z_score > self.entry_threshold:
                    self.log_info(f"{symbol}: Not oversold enough (Z-Score: {z_score:.2f})")
                elif z_score < self.max_deviation:
                    self.log_info(f"{symbol}: Too oversold, possible falling knife (Z-Score: {z_score:.2f})")
                elif self.volume_confirm and metrics.get('volume_ratio', 0) < 1.2:
                    self.log_info(f"{symbol}: Insufficient volume confirmation ({metrics.get('volume_ratio', 0):.2f}x)")
            
            return False
            
        except Exception as e:
            self.log_error(f"Error analyzing {symbol}: {str(e)}")
            return False
    
    def execute(self) -> List[str]:
        """
        Execute the mean reversion strategy.
        
        Returns:
            List of symbols that showed mean reversion signals
        """
        self.log_info("Executing Mean Reversion Strategy")
        
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