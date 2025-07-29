# Custom Strategy Implementation Plan

## Overview
This document outlines the comprehensive plan for implementing a custom Python strategy execution system in OpenAlgo. This system will allow users to create custom Python strategy classes that can be executed via API endpoints, providing flexible algorithmic trading capabilities.

## Architecture Overview

```mermaid
graph TD
    A[User Creates Strategy] --> B[Strategy Management UI]
    B --> C[Select Strategy Type]
    C --> D[Custom Python Strategy]
    C --> E[Traditional Webhook Strategy]
    
    D --> F[Strategy File Selection]
    F --> G[custom_strategies Folder]
    G --> H[Strategy Validation]
    
    I[External Trigger] --> J[/strategy/execute/webhook_id]
    J --> K[Strategy Execution Engine]
    
    K --> L[Immediate Execution]
    K --> M[Queue Execution]
    K --> N[Schedule Execution]
    
    L --> O[Load Strategy Class]
    M --> O
    N --> O
    
    O --> P[Execute Strategy Logic]
    P --> Q[Access OpenAlgo APIs]
    Q --> R[Generate Trading Signals]
    R --> S[Return Symbols for Trading]
    
    S --> T[Process Signals]
    T --> U[Place Orders via Existing System]
```

## Key Components

### 1. Directory Structure
```
custom_strategies/
├── __init__.py
├── base_strategy.py           # Base class template
├── examples/
│   ├── __init__.py
│   ├── ema_crossover.py      # EMA crossover strategy
│   ├── rsi_strategy.py       # RSI-based strategy
│   ├── momentum_strategy.py  # Momentum strategy
│   └── mean_reversion.py     # Mean reversion strategy
└── user_strategies/          # User-created strategies
    ├── __init__.py
    └── README.md
```

### 2. Database Schema Extensions
The existing `Strategy` table will be extended with:
- `strategy_type` ENUM('webhook', 'custom') DEFAULT 'webhook'
- `strategy_file` VARCHAR(255) NULL (path to custom strategy file)
- `execution_mode` ENUM('immediate', 'queue', 'schedule') DEFAULT 'immediate'
- `schedule_config` JSON NULL (for scheduling parameters)

### 3. API Endpoints
- **Immediate**: `POST /strategy/execute/<webhook_id>?mode=immediate`
- **Queue**: `POST /strategy/execute/<webhook_id>?mode=queue`
- **Schedule**: `POST /strategy/execute/<webhook_id>?mode=schedule&interval=300`

### 4. Strategy Base Class Interface
```python
class BaseStrategy:
    def __init__(self, api_key, strategy_config):
        self.api_key = api_key
        self.config = strategy_config
        
    def get_quotes(self, symbol, exchange):
        """Access OpenAlgo quotes API"""
        
    def get_history(self, symbol, exchange, interval, start_date, end_date):
        """Access OpenAlgo history API"""
        
    def execute(self):
        """Main strategy logic - must be implemented by subclasses"""
        raise NotImplementedError
```

## Implementation Tasks

### Phase 1: Foundation
1. **Create custom_strategies directory structure and base strategy interface**
   - Set up folder structure with examples and user directories
   - Create base strategy class template
   - Implement validation utilities

2. **Implement strategy discovery and validation system**
   - Scan custom_strategies folder for valid Python files
   - Validate strategy classes against base interface
   - Cache strategy metadata for performance

3. **Add custom strategy type to database schema and models**
   - Extend Strategy model with new fields
   - Add migration scripts
   - Update database functions

### Phase 2: Core Implementation
4. **Create custom strategy management UI with dropdown for strategy selection**
   - Extend new_strategy.html template
   - Add strategy file selection dropdown
   - Implement frontend validation

5. **Implement new API endpoint /strategy/execute/<webhook_id> for custom strategy execution**
   - Create new route in strategy_bp
   - Implement request validation
   - Add authentication and rate limiting

6. **Develop strategy execution engine with immediate, queue, and schedule options**
   - Create strategy loader and executor
   - Implement execution modes
   - Add result processing

### Phase 3: Strategy Templates and Examples
7. **Create strategy base class template and example strategies**
   - Implement BaseStrategy class
   - Create 4-5 example strategies
   - Add documentation and comments

### Phase 4: Security and Error Handling
8. **Implement error handling and logging for custom strategy execution**
   - Add comprehensive error handling
   - Implement execution logging
   - Create failure recovery mechanisms

9. **Add rate limiting and security measures for custom strategy endpoint**
   - Implement execution timeouts
   - Add resource monitoring
   - Restrict dangerous imports

### Phase 5: Integration and Testing
10. **Create documentation and testing for the custom strategy system**
    - Write user documentation
    - Create developer guides
    - Implement unit and integration tests

11. **Update existing strategy templates to include custom strategy option**
    - Modify strategy creation UI
    - Update configuration forms
    - Add help documentation

12. **Test integration with existing webhook system and order placement**
    - Test end-to-end workflows
    - Validate order placement
    - Performance testing

## Security Considerations
- Strategy files executed in restricted environment
- Import restrictions on dangerous modules
- Timeout limits for strategy execution
- Resource usage monitoring
- Code validation before execution

## Integration Points
1. **UI Integration**: Extends existing strategy creation workflow
2. **Webhook Compatibility**: Works alongside current webhook system
3. **Order System**: Uses existing rate-limited order queues
4. **Authentication**: Leverages current API key system
5. **Logging**: Integrates with existing logging infrastructure

## Example Strategy Structure
```python
from custom_strategies.base_strategy import BaseStrategy

class EMACrossoverStrategy(BaseStrategy):
    def __init__(self, api_key, strategy_config):
        super().__init__(api_key, strategy_config)
        self.short_period = strategy_config.get('short_period', 9)
        self.long_period = strategy_config.get('long_period', 21)
    
    def execute(self):
        symbols = ['RELIANCE', 'TCS', 'INFY']
        signals = []
        
        for symbol in symbols:
            # Get historical data
            history = self.get_history(symbol, 'NSE', '1D', '2023-01-01', '2023-12-31')
            
            # Calculate EMAs and generate signals
            if self.calculate_ema_crossover(history):
                signals.append(symbol)
        
        return signals
    
    def calculate_ema_crossover(self, data):
        # EMA crossover logic
        return True  # Simplified for example
```

## Expected Benefits
1. **Flexibility**: Users can implement complex strategies with custom logic
2. **Integration**: Full access to OpenAlgo API ecosystem
3. **Scalability**: Multiple execution modes for different use cases
4. **Security**: Sandboxed execution with proper validation
5. **Compatibility**: Works alongside existing webhook strategies

## Timeline
- **Phase 1**: 2-3 days
- **Phase 2**: 3-4 days
- **Phase 3**: 2-3 days
- **Phase 4**: 2-3 days
- **Phase 5**: 3-4 days

**Total Estimated Time**: 12-17 days