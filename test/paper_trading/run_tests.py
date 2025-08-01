"""
Test runner for paper trading module.

This script runs all paper trading tests and generates a coverage report.
"""

import pytest
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def run_paper_trading_tests():
    """Run all paper trading tests"""
    
    # Set environment variables for testing
    os.environ['OPENALGO_TRADING_MODE'] = 'paper'
    os.environ['PAPER_TRADING_DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['PAPER_DEFAULT_BALANCE'] = '50000.00'
    os.environ['PAPER_DEFAULT_CURRENCY'] = 'INR'
    
    # Test directory
    test_dir = Path(__file__).parent
    
    # Test arguments
    args = [
        str(test_dir),
        '-v',  # Verbose output
        '--tb=short',  # Short traceback format
        '--strict-markers',  # Strict marker checking
        '--disable-warnings',  # Disable warnings
        '-x',  # Stop on first failure (optional)
    ]
    
    # Add coverage if available
    try:
        import pytest_cov
        args.extend([
            '--cov=services/interfaces',
            '--cov=services/trading_service_factory',
            '--cov=services/paper_trading_service',
            '--cov=services/live_broker_service',
            '--cov=services/paper_trading',
            '--cov=database/paper_trading_db',
            '--cov-report=html:test/paper_trading/htmlcov',
            '--cov-report=term-missing',
        ])
        print("Running tests with coverage...")
    except ImportError:
        print("pytest-cov not available, running tests without coverage...")
    
    # Run tests
    exit_code = pytest.main(args)
    
    if exit_code == 0:
        print("\n✅ All paper trading tests passed!")
        if 'pytest_cov' in sys.modules:
            print("📊 Coverage report generated in test/paper_trading/htmlcov/")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")
    
    return exit_code


def run_specific_test(test_name):
    """Run a specific test"""
    test_dir = Path(__file__).parent
    test_file = test_dir / f"test_{test_name}.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return 1
    
    args = [str(test_file), '-v']
    exit_code = pytest.main(args)
    
    return exit_code


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        exit_code = run_specific_test(test_name)
    else:
        # Run all tests
        exit_code = run_paper_trading_tests()
    
    sys.exit(exit_code)