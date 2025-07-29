# User Custom Strategies

This directory is where you can place your own custom trading strategies.

## How to Create a Custom Strategy

1. Create a new Python file (e.g., `my_strategy.py`)
2. Import the base strategy class:
   ```python
   from custom_strategies.base_strategy import BaseStrategy
   ```
3. Create a class that inherits from `BaseStrategy`
4. Implement the `execute()` method
5. Use the provided API methods to access market data

## Example Strategy Template

```python
from custom_strategies.base_strategy import BaseStrategy
from typing import List

class MyCustomStrategy(BaseStrategy):
    """
    My Custom Trading Strategy
    
    Description of what this strategy does.
    """
    
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Get configuration values
        self.symbols = self.get_config_value('symbols', ['RELIANCE', 'TCS'])
        self.exchange = self.get_config_value('exchange', 'NSE')
        
        self.log_info("My Custom Strategy initialized")
    
    def execute(self) -> List[str]:
        """
        Execute the strategy logic.
        
        Returns:
            List of symbols to trade
        """
        self.log_info("Executing My Custom Strategy")
        
        signals = []
        
        for symbol in self.symbols:
            try:
                # Get current quote
                quote_response = self.get_quotes(symbol, self.exchange)
                
                if quote_response.get('status') == 'success':
                    ltp = quote_response.get('data', {}).get('ltp', 0)
                    
                    # Your strategy logic here
                    if ltp > 0:  # Example condition
                        signals.append(symbol)
                        self.log_info(f"Signal generated for {symbol} at price {ltp}")
                
            except Exception as e:
                self.log_error(f"Error processing {symbol}: {str(e)}")
                continue
        
        return self.validate_symbol_list(signals)
```

## Available API Methods

### Market Data
- `get_quotes(symbol, exchange)` - Get real-time quotes
- `get_history(symbol, exchange, interval, start_date, end_date)` - Get historical data
- `get_depth(symbol, exchange)` - Get market depth
- `search_symbols(query, exchange=None)` - Search for symbols
- `get_symbol_info(symbol, exchange)` - Get symbol information

### Account Data
- `get_funds()` - Get account funds and margin
- `get_positions()` - Get current positions
- `get_orderbook()` - Get order book

### Utility Methods
- `get_config_value(key, default=None)` - Get configuration values
- `log_info(message)` - Log information messages
- `log_warning(message)` - Log warning messages
- `log_error(message)` - Log error messages
- `validate_symbol_list(symbols)` - Validate symbol list

## Configuration

Your strategy can access configuration values through `self.get_config_value()`. These can be set when creating the strategy in the UI.

Common configuration options:
- `symbols` - List of symbols to analyze
- `exchange` - Default exchange (NSE, BSE, NFO, etc.)
- Custom parameters specific to your strategy

## Best Practices

1. **Error Handling**: Always wrap API calls in try-catch blocks
2. **Logging**: Use the logging methods to track strategy execution
3. **Validation**: Validate inputs and outputs
4. **Configuration**: Make your strategy configurable through parameters
5. **Documentation**: Add clear docstrings explaining your strategy logic
6. **Testing**: Test your strategy with paper trading first

## Security Notes

- Do not import dangerous modules (os, sys, subprocess, etc.)
- Avoid file system operations unless absolutely necessary
- Use only the provided API methods for market data access
- Do not hardcode sensitive information like API keys

## Examples

Check the `examples` directory for sample strategies:
- `ema_crossover.py` - EMA crossover strategy
- `rsi_strategy.py` - RSI-based strategy  
- `momentum_strategy.py` - Momentum strategy
- `mean_reversion.py` - Mean reversion strategy