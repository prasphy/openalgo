"""
RSI Strategy

A momentum strategy based on the Relative Strength Index (RSI) indicator.
Generates buy signals when RSI is oversold and shows signs of reversal.
"""

from custom_strategies.base_strategy import BaseStrategy
import pandas as pd
from typing import List
from datetime import datetime, timedelta


class RSIStrategy(BaseStrategy):
    """
    RSI-based Trading Strategy
    
    This strategy uses the Relative Strength Index to identify oversold
    conditions and potential reversal opportunities.
    """
    
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Strategy parameters
        self.rsi_period = self.get_config_value('rsi_period', 14)
        self.oversold_level = self.get_config_value('oversold_level', 30)
        self.recovery_level = self.get_config_value('recovery_level', 35)
        self.symbols = self.get_config_value('symbols', ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK'])
        self.exchange = self.get_config_value('exchange', 'NSE')
        self.lookback_days = self.get_config_value('lookback_days', 40)
        
        self.log_info(f"RSI Strategy initialized with period {self.rsi_period}, oversold level {self.oversold_level}")
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: List of closing prices
            period: RSI calculation period
            
        Returns:
            List of RSI values
        """
        if len(prices) < period + 1:
            return []
        
        df = pd.DataFrame({'close': prices})
        
        # Calculate price changes
        delta = df['close'].diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate average gains and losses
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.dropna().tolist()
    
    def check_rsi_signal(self, rsi_values: List[float]) -> bool:
        """
        Check if RSI shows a buy signal.
        
        Args:
            rsi_values: List of RSI values
            
        Returns:
            True if buy signal detected, False otherwise
        """
        if len(rsi_values) < 3:
            return False
        
        current_rsi = rsi_values[-1]
        previous_rsi = rsi_values[-2]
        
        # Signal: RSI was oversold and is now recovering above recovery level
        signal = (previous_rsi <= self.oversold_level and 
                 current_rsi > self.recovery_level and 
                 current_rsi < 70)  # Not overbought
        
        return signal
    
    def analyze_symbol(self, symbol: str) -> bool:
        """
        Analyze a single symbol for RSI signals.
        
        Args:
            symbol: Symbol to analyze
            
        Returns:
            True if RSI signal detected, False otherwise
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
            if len(history_data) < self.rsi_period + 5:
                self.log_warning(f"Insufficient data for {symbol}: {len(history_data)} bars")
                return False
            
            # Extract closing prices
            closes = [float(bar['close']) for bar in history_data]
            
            # Calculate RSI
            rsi_values = self.calculate_rsi(closes, self.rsi_period)
            
            if not rsi_values:
                self.log_warning(f"Could not calculate RSI for {symbol}")
                return False
            
            # Check for RSI signal
            signal = self.check_rsi_signal(rsi_values)
            
            if signal:
                current_rsi = rsi_values[-1]
                self.log_info(f"RSI Signal detected for {symbol} - Current RSI: {current_rsi:.2f}")
                
                # Additional validation: get current quote
                quote_response = self.get_quotes(symbol, self.exchange)
                if quote_response.get('status') == 'success':
                    ltp = quote_response.get('data', {}).get('ltp', 0)
                    self.log_info(f"Current LTP for {symbol}: {ltp}")
                    return True
                else:
                    self.log_warning(f"Could not get current quote for {symbol}")
                    return False
            
            return False
            
        except Exception as e:
            self.log_error(f"Error analyzing {symbol}: {str(e)}")
            return False
    
    def execute(self) -> List[str]:
        """
        Execute the RSI strategy.
        
        Returns:
            List of symbols that showed RSI signals
        """
        self.log_info("Executing RSI Strategy")
        
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