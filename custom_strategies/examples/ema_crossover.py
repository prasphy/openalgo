"""
EMA Crossover Strategy

A simple moving average crossover strategy that generates buy signals
when the short EMA crosses above the long EMA.
"""

from custom_strategies.base_strategy import BaseStrategy
import pandas as pd
from typing import List
from datetime import datetime, timedelta


class EMACrossoverStrategy(BaseStrategy):
    """
    EMA Crossover Strategy Implementation
    
    This strategy uses two exponential moving averages (EMA) to generate
    trading signals. When the shorter EMA crosses above the longer EMA,
    it generates a buy signal for the symbol.
    """
    
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Strategy parameters
        self.short_period = self.get_config_value('short_period', 9)
        self.long_period = self.get_config_value('long_period', 21)
        self.symbols = self.get_config_value('symbols', ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK'])
        self.exchange = self.get_config_value('exchange', 'NSE')
        self.lookback_days = self.get_config_value('lookback_days', 30)
        
        self.log_info(f"EMA Crossover Strategy initialized with periods {self.short_period}/{self.long_period}")
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate Exponential Moving Average.
        
        Args:
            prices: List of prices
            period: EMA period
            
        Returns:
            List of EMA values
        """
        if len(prices) < period:
            return []
        
        df = pd.DataFrame({'price': prices})
        ema = df['price'].ewm(span=period, adjust=False).mean()
        return ema.tolist()
    
    def check_crossover(self, short_ema: List[float], long_ema: List[float]) -> bool:
        """
        Check if short EMA crossed above long EMA.
        
        Args:
            short_ema: Short period EMA values
            long_ema: Long period EMA values
            
        Returns:
            True if crossover occurred, False otherwise
        """
        if len(short_ema) < 2 or len(long_ema) < 2:
            return False
        
        # Check if short EMA crossed above long EMA in the last period
        current_short = short_ema[-1]
        current_long = long_ema[-1]
        previous_short = short_ema[-2]
        previous_long = long_ema[-2]
        
        # Crossover: previous short <= previous long AND current short > current long
        crossover = (previous_short <= previous_long) and (current_short > current_long)
        
        return crossover
    
    def analyze_symbol(self, symbol: str) -> bool:
        """
        Analyze a single symbol for EMA crossover.
        
        Args:
            symbol: Symbol to analyze
            
        Returns:
            True if crossover signal detected, False otherwise
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
            if len(history_data) < self.long_period:
                self.log_warning(f"Insufficient data for {symbol}: {len(history_data)} bars")
                return False
            
            # Extract closing prices
            closes = [float(bar['close']) for bar in history_data]
            
            # Calculate EMAs
            short_ema = self.calculate_ema(closes, self.short_period)
            long_ema = self.calculate_ema(closes, self.long_period)
            
            if not short_ema or not long_ema:
                self.log_warning(f"Could not calculate EMAs for {symbol}")
                return False
            
            # Check for crossover
            crossover = self.check_crossover(short_ema, long_ema)
            
            if crossover:
                self.log_info(f"EMA Crossover detected for {symbol} - Short EMA: {short_ema[-1]:.2f}, Long EMA: {long_ema[-1]:.2f}")
                
                # Additional validation: get current quote to ensure market is active
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
        Execute the EMA crossover strategy.
        
        Returns:
            List of symbols that showed crossover signals
        """
        self.log_info("Executing EMA Crossover Strategy")
        
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