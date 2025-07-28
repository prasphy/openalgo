# Custom Strategies User Guide

## Overview

The Custom Strategy System in OpenAlgo allows you to create and execute sophisticated trading strategies using Python code. This system provides full access to OpenAlgo's APIs while maintaining security and performance.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Creating Your First Custom Strategy](#creating-your-first-custom-strategy)
3. [Strategy Development Guide](#strategy-development-guide)
4. [Available API Methods](#available-api-methods)
5. [Configuration and Parameters](#configuration-and-parameters)
6. [Execution Modes](#execution-modes)
7. [Best Practices](#best-practices)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- Active OpenAlgo account with API access
- Basic Python knowledge
- Understanding of trading concepts

### System Architecture

The custom strategy system consists of:
- **Base Strategy Class**: Provides API access and common functionality
- **Strategy Loader**: Discovers and loads strategy files
- **Strategy Validator**: Ensures code security and correctness
- **Execution Engine**: Handles immediate, queued, and scheduled execution
- **Web Interface**: Manage strategies through the browser

## Creating Your First Custom Strategy

### Step 1: Create a Strategy File

Navigate to `custom_strategies/user_strategies/` and create a new Python file (e.g., `my_first_strategy.py`):

```python
from custom_strategies.base_strategy import BaseStrategy
from typing import List

class MyFirstStrategy(BaseStrategy):
    """
    A simple strategy that buys when RSI is oversold
    """
    
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        # Get configuration parameters
        self.symbols = self.get_config_value('symbols', ['RELIANCE', 'TCS'])
        self.exchange = self.get_config_value('exchange', 'NSE')
        self.rsi_threshold = self.get_config_value('rsi_threshold', 30)
        
        self.log_info("My First Strategy initialized")
    
    def execute(self) -> List[str]:
        """
        Main strategy logic
        """
        self.log_info("Executing My First Strategy")
        
        signals = []
        
        for symbol in self.symbols:
            try:
                # Get current quote
                quote_response = self.get_quotes(symbol, self.exchange)
                
                if quote_response.get('status') == 'success':
                    ltp = quote_response.get('data', {}).get('ltp', 0)
                    
                    # Simple logic: if price exists, add to signals
                    if ltp > 0:
                        signals.append(symbol)
                        self.log_info(f"Signal generated for {symbol} at price {ltp}")
                
            except Exception as e:
                self.log_error(f"Error processing {symbol}: {str(e)}")
                continue
        
        return self.validate_symbol_list(signals)
```

### Step 2: Create Strategy in OpenAlgo

1. Go to **Strategies** → **New Strategy**
2. Select **Platform**: Custom Strategy
3. Enter **Strategy Name**: My First Strategy
4. Select **Strategy File**: my_first_strategy.py
5. Choose **Execution Mode**: Immediate
6. Add **Strategy Parameters**:
   ```json
   {
     "symbols": ["RELIANCE", "TCS", "INFY"],
     "exchange": "NSE",
     "rsi_threshold": 30
   }
   ```
7. Click **Create Strategy**

### Step 3: Execute the Strategy

- **Manual Execution**: Click "Execute Now" on the strategy view page
- **API Execution**: POST to `/strategy/execute/{webhook_id}`
- **Scheduled Execution**: Configure schedule parameters

## Strategy Development Guide

### Required Structure

Every custom strategy must:

1. **Inherit from BaseStrategy**
   ```python
   from custom_strategies.base_strategy import BaseStrategy
   
   class MyStrategy(BaseStrategy):
   ```

2. **Implement the execute() method**
   ```python
   def execute(self) -> List[str]:
       # Your strategy logic here
       return ["SYMBOL1", "SYMBOL2"]  # Return list of symbols to trade
   ```

3. **Call parent __init__**
   ```python
   def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
       super().__init__(api_key, strategy_config, base_url)
   ```

### Strategy Lifecycle

1. **Initialization**: Strategy object created with API key and configuration
2. **Execution**: `execute()` method called
3. **Signal Processing**: Returned symbols processed for trading
4. **Order Placement**: Orders queued through existing order system

## Available API Methods

### Market Data Methods

```python
# Get real-time quotes
quote_data = self.get_quotes("RELIANCE", "NSE")

# Get historical data
history_data = self.get_history("RELIANCE", "NSE", "1d", "2023-01-01", "2023-12-31")

# Get market depth
depth_data = self.get_depth("RELIANCE", "NSE")

# Search symbols
search_results = self.search_symbols("RELI", "NSE")

# Get symbol information
symbol_info = self.get_symbol_info("RELIANCE", "NSE")
```

### Account Data Methods

```python
# Get account funds
funds = self.get_funds()

# Get current positions
positions = self.get_positions()

# Get order book
orders = self.get_orderbook()
```

### Utility Methods

```python
# Get configuration values
symbols = self.get_config_value('symbols', ['DEFAULT'])

# Logging
self.log_info("Information message")
self.log_warning("Warning message")
self.log_error("Error message")

# Validate symbol list
validated_symbols = self.validate_symbol_list(symbol_list)
```

## Configuration and Parameters

### Strategy Configuration

Pass parameters to your strategy via the configuration JSON:

```json
{
  "symbols": ["RELIANCE", "TCS", "INFY"],
  "exchange": "NSE",
  "short_period": 9,
  "long_period": 21,
  "threshold": 0.02,
  "max_positions": 5
}
```

### Accessing Configuration

```python
def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
    super().__init__(api_key, strategy_config, base_url)
    
    # Get values with defaults
    self.symbols = self.get_config_value('symbols', ['RELIANCE'])
    self.threshold = self.get_config_value('threshold', 0.01)
    self.max_positions = self.get_config_value('max_positions', 3)
```

## Execution Modes

### 1. Immediate Execution

- Executes strategy immediately when called
- Returns results synchronously
- Best for: Manual execution, testing

```
POST /strategy/execute/{webhook_id}?mode=immediate
```

### 2. Queue Execution

- Adds strategy to execution queue
- Returns immediately, executes in background
- Best for: High-frequency strategies, batch processing

```
POST /strategy/execute/{webhook_id}?mode=queue
```

### 3. Scheduled Execution

- Executes strategy at regular intervals
- Configurable timing (minutes, hours, daily)
- Best for: Long-term strategies, automated trading

```json
{
  "interval_type": "minutes",
  "interval_value": 15,
  "time": "09:30"
}
```

## Best Practices

### 1. Error Handling

Always wrap API calls in try-catch blocks:

```python
def analyze_symbol(self, symbol: str) -> bool:
    try:
        quote_response = self.get_quotes(symbol, self.exchange)
        if quote_response.get('status') == 'success':
            # Process data
            return True
        else:
            self.log_warning(f"Failed to get quote for {symbol}")
            return False
    except Exception as e:
        self.log_error(f"Error analyzing {symbol}: {str(e)}")
        return False
```

### 2. Logging

Use the built-in logging methods for debugging:

```python
self.log_info("Strategy started")
self.log_warning("Unusual market condition detected")
self.log_error("Failed to process symbol")
```

### 3. Configuration

Make your strategy configurable:

```python
# Good: Configurable
self.risk_percent = self.get_config_value('risk_percent', 2.0)

# Bad: Hardcoded
self.risk_percent = 2.0
```

### 4. Performance

- Cache expensive calculations
- Use efficient data structures
- Avoid unnecessary API calls

```python
def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
    super().__init__(api_key, strategy_config, base_url)
    
    # Cache symbols to avoid repeated lookups
    self.symbol_cache = {}
```

### 5. Testing

Test your strategy with small positions first:

```python
# Start with test configuration
test_config = {
    "symbols": ["RELIANCE"],  # Single symbol
    "quantity": 1,            # Small quantity
    "test_mode": True
}
```

## Examples

### Example 1: EMA Crossover Strategy

```python
from custom_strategies.base_strategy import BaseStrategy
import pandas as pd
from typing import List

class EMACrossoverStrategy(BaseStrategy):
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        self.short_period = self.get_config_value('short_period', 9)
        self.long_period = self.get_config_value('long_period', 21)
        self.symbols = self.get_config_value('symbols', ['RELIANCE'])
        self.exchange = self.get_config_value('exchange', 'NSE')
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        df = pd.DataFrame({'price': prices})
        ema = df['price'].ewm(span=period, adjust=False).mean()
        return ema.tolist()
    
    def execute(self) -> List[str]:
        signals = []
        
        for symbol in self.symbols:
            try:
                # Get historical data
                history = self.get_history(symbol, self.exchange, '1d', '2023-01-01', '2023-12-31')
                
                if history.get('status') == 'success':
                    data = history.get('data', [])
                    closes = [float(bar['close']) for bar in data]
                    
                    if len(closes) >= self.long_period:
                        short_ema = self.calculate_ema(closes, self.short_period)
                        long_ema = self.calculate_ema(closes, self.long_period)
                        
                        # Check for crossover
                        if (len(short_ema) >= 2 and len(long_ema) >= 2 and
                            short_ema[-1] > long_ema[-1] and short_ema[-2] <= long_ema[-2]):
                            signals.append(symbol)
                            self.log_info(f"EMA crossover detected for {symbol}")
                
            except Exception as e:
                self.log_error(f"Error processing {symbol}: {str(e)}")
        
        return self.validate_symbol_list(signals)
```

### Example 2: RSI Strategy

```python
from custom_strategies.base_strategy import BaseStrategy
import pandas as pd
from typing import List

class RSIStrategy(BaseStrategy):
    def __init__(self, api_key: str, strategy_config: dict, base_url: str = "http://127.0.0.1:5000"):
        super().__init__(api_key, strategy_config, base_url)
        
        self.rsi_period = self.get_config_value('rsi_period', 14)
        self.oversold_level = self.get_config_value('oversold_level', 30)
        self.symbols = self.get_config_value('symbols', ['RELIANCE'])
        self.exchange = self.get_config_value('exchange', 'NSE')
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        df = pd.DataFrame({'close': prices})
        delta = df['close'].diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        return rsi.dropna().tolist()
    
    def execute(self) -> List[str]:
        signals = []
        
        for symbol in self.symbols:
            try:
                # Get historical data
                history = self.get_history(symbol, self.exchange, '1d', '2023-01-01', '2023-12-31')
                
                if history.get('status') == 'success':
                    data = history.get('data', [])
                    closes = [float(bar['close']) for bar in data]
                    
                    if len(closes) >= self.rsi_period + 5:
                        rsi_values = self.calculate_rsi(closes, self.rsi_period)
                        
                        if rsi_values and rsi_values[-1] <= self.oversold_level:
                            signals.append(symbol)
                            self.log_info(f"RSI oversold for {symbol}: {rsi_values[-1]:.2f}")
                
            except Exception as e:
                self.log_error(f"Error processing {symbol}: {str(e)}")
        
        return self.validate_symbol_list(signals)
```

## Troubleshooting

### Common Issues

1. **Strategy Not Loading**
   - Check file is in correct directory
   - Ensure class inherits from BaseStrategy
   - Verify execute() method is implemented

2. **API Errors**
   - Check API key is valid
   - Verify symbol names are correct
   - Ensure exchange is supported

3. **Execution Errors**
   - Check strategy logs in execution history
   - Verify configuration parameters
   - Test with simple strategy first

### Debugging Tips

1. **Use Logging**
   ```python
   self.log_info("Strategy started")
   self.log_info(f"Processing {len(self.symbols)} symbols")
   ```

2. **Test Individual Components**
   ```python
   # Test API access
   quote = self.get_quotes("RELIANCE", "NSE")
   self.log_info(f"Quote response: {quote}")
   ```

3. **Validate Data**
   ```python
   if not data or len(data) < required_length:
       self.log_warning("Insufficient data")
       return []
   ```

### Security Restrictions

The system prevents:
- File system access (except reading)
- Network operations (except through provided APIs)
- System command execution
- Import of dangerous modules

Allowed modules:
- Math and statistics modules
- Pandas, NumPy for data analysis
- TA-Lib for technical analysis
- Requests for API calls (internal only)

## Support

For additional help:
1. Check the example strategies in `custom_strategies/examples/`
2. Review the system logs for detailed error messages
3. Test with simple strategies before implementing complex logic
4. Use the strategy validation system to check code security

## API Reference

### Response Format

All API methods return responses in this format:

```json
{
  "status": "success|error",
  "message": "Response message",
  "data": { /* Response data */ }
}
```

### Error Handling

Always check the response status:

```python
response = self.get_quotes(symbol, exchange)
if response.get('status') == 'success':
    data = response.get('data', {})
    # Process data
else:
    self.log_error(f"API error: {response.get('message', 'Unknown error')}")
```

This completes the Custom Strategies User Guide. The system provides a powerful, secure, and flexible way to implement sophisticated trading strategies while maintaining integration with OpenAlgo's ecosystem.