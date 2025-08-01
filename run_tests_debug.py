"""
Debug test runner for paper trading tests.
This helps identify specific issues before running the full test suite.
"""

import sys
import os
import subprocess

# Add project root to path
sys.path.insert(0, '.')

# Set environment variables for testing
os.environ['OPENALGO_TRADING_MODE'] = 'paper'
os.environ['PAPER_TRADING_DATABASE_URL'] = 'sqlite:///:memory:'

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from services.trading_service_factory import TradingServiceFactory, get_trading_service
        print("✅ TradingServiceFactory imports OK")
    except Exception as e:
        print(f"❌ TradingServiceFactory import failed: {e}")
        return False
    
    try:
        from services.interfaces.trading_service import ITradingService
        print("✅ ITradingService imports OK")
    except Exception as e:
        print(f"❌ ITradingService import failed: {e}")
        return False
    
    try:
        from database.paper_trading_db import PaperAccount, PaperOrder
        print("✅ Paper trading models import OK")
    except Exception as e:
        print(f"❌ Paper trading models import failed: {e}")
        return False
    
    try:
        from database.auth_db import verify_api_key
        print("✅ verify_api_key imports OK")
    except Exception as e:
        print(f"❌ verify_api_key import failed: {e}")
        return False
    
    return True

def run_single_test_function():
    """Run a single test function"""
    print("\n🧪 Testing single function...")
    
    try:
        from services.trading_service_factory import TradingServiceFactory
        
        # Test basic functionality
        mode = TradingServiceFactory.get_current_mode()
        print(f"✅ Current mode: {mode}")
        
        is_paper = TradingServiceFactory.is_paper_trading_mode()
        print(f"✅ Is paper trading: {is_paper}")
        
        return True
        
    except Exception as e:
        print(f"❌ Single function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_pytest():
    """Run the actual pytest"""
    print("\n🚀 Running pytest...")
    
    try:
        # Run only the factory tests first
        cmd = [sys.executable, '-m', 'pytest', 'test/paper_trading/test_trading_service_factory.py', '-v', '--tb=short']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Pytest execution failed: {e}")
        return False

def main():
    """Main function"""
    print("🔧 Paper Trading Tests Debug Runner")
    print("=" * 50)
    
    # Test 1: Imports
    if not test_imports():
        print("❌ Import tests failed. Fix imports first.")
        return
    
    # Test 2: Basic functionality
    if not run_single_test_function():
        print("❌ Basic functionality test failed.")
        return
    
    # Test 3: Run pytest
    if run_pytest():
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed. Check output above.")

if __name__ == '__main__':
    main()