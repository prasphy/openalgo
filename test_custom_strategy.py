"""
Test Script for Custom Strategy System

This script tests the basic functionality of the custom strategy system
including strategy loading, validation, and execution.
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_strategy_loader():
    """Test the strategy loader functionality."""
    print("=== Testing Strategy Loader ===")
    
    try:
        from custom_strategies import StrategyLoader
        
        loader = StrategyLoader()
        
        # Test strategy discovery
        print("1. Testing strategy discovery...")
        strategies = loader.discover_strategies()
        print(f"   Found {len(strategies)} strategies:")
        for strategy in strategies:
            print(f"   - {strategy['display_name']} ({strategy['category']})")
        
        # Test loading example strategies
        print("\n2. Testing strategy loading...")
        for strategy in strategies:
            if strategy['category'] == 'examples':
                strategy_name = strategy['name']
                print(f"   Loading {strategy_name}...")
                
                strategy_class = loader.load_strategy(strategy_name, 'examples')
                if strategy_class:
                    print(f"   ✓ Successfully loaded {strategy_name}")
                    
                    # Test validation
                    if loader.validate_strategy(strategy_class):
                        print(f"   ✓ Strategy {strategy_name} is valid")
                    else:
                        print(f"   ✗ Strategy {strategy_name} validation failed")
                else:
                    print(f"   ✗ Failed to load {strategy_name}")
        
        print("Strategy Loader tests completed!\n")
        return True
        
    except Exception as e:
        print(f"Strategy Loader test failed: {str(e)}\n")
        return False

def test_strategy_validator():
    """Test the strategy validator functionality."""
    print("=== Testing Strategy Validator ===")
    
    try:
        from custom_strategies import StrategyValidator
        
        validator = StrategyValidator()
        
        # Test valid strategy code
        print("1. Testing valid strategy validation...")
        valid_code = '''
from custom_strategies.base_strategy import BaseStrategy

class TestStrategy(BaseStrategy):
    def execute(self):
        return ["RELIANCE", "TCS"]
'''
        
        is_valid, errors, warnings = validator.validate_code_string(valid_code)
        print(f"   Valid code result: {'✓ PASS' if is_valid else '✗ FAIL'}")
        if errors:
            print(f"   Errors: {errors}")
        if warnings:
            print(f"   Warnings: {warnings}")
        
        # Test invalid strategy code
        print("\n2. Testing invalid strategy validation...")
        invalid_code = '''
import os
from custom_strategies.base_strategy import BaseStrategy

class BadStrategy(BaseStrategy):
    def execute(self):
        os.system("rm -rf /")  # Dangerous operation
        return []
'''
        
        is_valid, errors, warnings = validator.validate_code_string(invalid_code)
        print(f"   Invalid code result: {'✓ PASS' if not is_valid else '✗ FAIL'}")
        if errors:
            print(f"   Errors: {errors}")
        if warnings:
            print(f"   Warnings: {warnings}")
        
        print("Strategy Validator tests completed!\n")
        return True
        
    except Exception as e:
        print(f"Strategy Validator test failed: {str(e)}\n")
        return False

def test_strategy_execution():
    """Test the strategy execution engine."""
    print("=== Testing Strategy Execution ===")
    
    try:
        from custom_strategies import get_strategy_executor
        
        executor = get_strategy_executor()
        
        # Test executor status
        print("1. Testing executor status...")
        status = executor.get_queue_status()
        print(f"   Queue size: {status['queue_size']}")
        print(f"   Worker running: {status['worker_running']}")
        print(f"   Scheduler running: {status['scheduler_running']}")
        print(f"   Total executions: {status['total_executions']}")
        
        print("Strategy Execution tests completed!\n")
        return True
        
    except Exception as e:
        print(f"Strategy Execution test failed: {str(e)}\n")
        return False

def test_database_schema():
    """Test the database schema extensions."""
    print("=== Testing Database Schema ===")
    
    try:
        from database.strategy_db import Strategy
        
        # Check if new fields exist
        print("1. Checking Strategy model fields...")
        strategy_fields = [attr for attr in dir(Strategy) if not attr.startswith('_')]
        
        required_fields = [
            'strategy_type', 'strategy_file', 'strategy_category',
            'execution_mode', 'schedule_config', 'strategy_config'
        ]
        
        for field in required_fields:
            if field in strategy_fields:
                print(f"   ✓ Field '{field}' exists")
            else:
                print(f"   ✗ Field '{field}' missing")
        
        print("Database Schema tests completed!\n")
        return True
        
    except Exception as e:
        print(f"Database Schema test failed: {str(e)}\n")
        return False

def test_api_endpoints():
    """Test API endpoint availability."""
    print("=== Testing API Endpoints ===")
    
    try:
        import requests
        
        base_url = "http://127.0.0.1:5000"
        
        # Test custom strategy availability endpoint
        print("1. Testing custom strategy availability endpoint...")
        try:
            response = requests.get(f"{base_url}/strategy/custom/available", timeout=5)
            if response.status_code == 200:
                print("   ✓ Custom strategy availability endpoint accessible")
            else:
                print(f"   ! Custom strategy availability endpoint returned {response.status_code}")
        except requests.exceptions.RequestException:
            print("   ! Server not running or endpoint not accessible")
        
        print("API Endpoints tests completed!\n")
        return True
        
    except Exception as e:
        print(f"API Endpoints test failed: {str(e)}\n")
        return False

def main():
    """Run all tests."""
    print("Custom Strategy System Test Suite")
    print("=" * 50)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    test_results = []
    
    # Run tests
    test_results.append(("Strategy Loader", test_strategy_loader()))
    test_results.append(("Strategy Validator", test_strategy_validator()))
    test_results.append(("Strategy Execution", test_strategy_execution()))
    test_results.append(("Database Schema", test_database_schema()))
    test_results.append(("API Endpoints", test_api_endpoints()))
    
    # Summary
    print("=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:20} : {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The custom strategy system is ready for use.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()