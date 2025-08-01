# Paper Trading Test Suite

This directory contains comprehensive unit tests for the paper trading module implementation.

## Test Structure

```
test/paper_trading/
├── __init__.py                         # Test module initialization
├── test_trading_service_factory.py     # Factory pattern tests
├── test_paper_trading_service.py       # Paper trading service tests
├── run_tests.py                        # Test runner script
└── README.md                          # This file
```

## Test Coverage

### 1. Trading Service Factory Tests (`test_trading_service_factory.py`)

- **Factory Pattern**: Tests correct instantiation of paper vs live services
- **Environment Configuration**: Tests TRADING_MODE environment variable handling
- **Caching Mechanism**: Tests service instance caching and reuse
- **Thread Safety**: Tests concurrent access to factory
- **Error Handling**: Tests invalid configuration and import errors
- **Convenience Functions**: Tests helper functions for mode detection

### 2. Paper Trading Service Tests (`test_paper_trading_service.py`)

- **Service Initialization**: Tests proper setup of dependencies
- **Order Placement**: Tests market orders, limit orders, validation, and error handling
- **Position Management**: Tests position retrieval, calculations, and P&L
- **Order Management**: Tests order cancellation, status tracking
- **Account Operations**: Tests balance retrieval, account reset
- **Portfolio Operations**: Tests position closure, batch operations
- **Statistics**: Tests trading statistics and reporting

## Running Tests

### Prerequisites

Install required packages:
```powershell
pip install pytest pytest-cov
```

### Run All Tests

```powershell
# From project root
python test/paper_trading/run_tests.py
```

### Run Specific Test File

```powershell
# Run factory tests only
python test/paper_trading/run_tests.py trading_service_factory

# Run service tests only
python test/paper_trading/run_tests.py paper_trading_service
```

### Run Individual Test Methods

```powershell
# Run specific test method
pytest test/paper_trading/test_trading_service_factory.py::TestTradingServiceFactory::test_get_live_trading_service -v
```

### Coverage Report

Tests automatically generate coverage reports when `pytest-cov` is available:

- **HTML Report**: `test/paper_trading/htmlcov/index.html`
- **Terminal Report**: Shows missing lines in console output

## Test Environment

The tests use the following environment configuration:

```python
TRADING_MODE=paper
PAPER_TRADING_DATABASE_URL=sqlite:///db/paper_trading.db
PAPER_DEFAULT_BALANCE=50000.00
PAPER_DEFAULT_CURRENCY=INR
```

## Mocking Strategy

Tests use comprehensive mocking to isolate units under test:

- **Database Sessions**: Mocked to prevent actual database operations
- **Market Data Feeds**: Mocked to provide predictable price data
- **Order Matching Engine**: Mocked to test service interactions
- **External Dependencies**: All imports and external calls are mocked

## Test Data

Tests use realistic but deterministic test data:

- **Symbols**: RELIANCE, TCS, INFY (common Indian stocks)
- **Exchanges**: NSE, BSE
- **Products**: MIS, CNC, NRML
- **Prices**: Realistic price ranges for testing P&L calculations

## Assertions and Validations

Tests validate:

1. **Return Values**: Correct success/failure status and status codes
2. **Data Structures**: Proper response format and required fields
3. **Business Logic**: Accurate calculations and state changes
4. **Error Handling**: Appropriate error messages and status codes
5. **Side Effects**: Correct database operations and external calls

## Continuous Integration

To integrate with CI/CD pipelines:

```powershell
# Run tests with JUnit XML output
pytest test/paper_trading/ --junitxml=test-results.xml

# Run tests with coverage and fail if below threshold
pytest test/paper_trading/ --cov=services --cov-fail-under=80
```

## Test Development Guidelines

When adding new tests:

1. **Follow Naming Convention**: `test_<functionality>_<scenario>`
2. **Use Setup/Teardown**: Clean state for each test
3. **Mock External Dependencies**: Keep tests isolated
4. **Test Both Success and Failure**: Cover happy path and error cases
5. **Validate All Assertions**: Test return values, side effects, and state changes
6. **Use Realistic Data**: Mirror production scenarios
7. **Document Complex Tests**: Add comments for complex test logic

## Debugging Tests

### Verbose Output
```powershell
pytest test/paper_trading/ -v -s
```

### Debug Specific Test
```powershell
pytest test/paper_trading/test_trading_service_factory.py::TestTradingServiceFactory::test_get_live_trading_service -v -s --pdb
```

### Show Warnings
```powershell
pytest test/paper_trading/ --disable-warnings=False
```

## Performance Considerations

- Tests use in-memory SQLite for fast execution
- Mocking eliminates external API calls
- Parallel execution possible with `pytest-xdist`
- Average test suite execution time: < 5 seconds

## Known Limitations

1. **Real Market Data**: Tests don't use actual market data feeds
2. **Integration Testing**: Unit tests don't cover full end-to-end scenarios
3. **Performance Testing**: No load or stress testing included
4. **Browser Testing**: No UI testing for admin interfaces

For integration and end-to-end testing, see the main test suite in the parent directory.

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Python path includes project root
2. **Database Errors**: Check SQLAlchemy version compatibility
3. **Mock Failures**: Verify mock target paths are correct
4. **Coverage Issues**: Ensure all relevant modules are in coverage scope

### Getting Help

- Check test output for detailed error messages
- Review mock configurations in test setup
- Validate environment variable settings
- Ensure all dependencies are installed