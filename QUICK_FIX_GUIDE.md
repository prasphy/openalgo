# Quick Fix Guide for Custom Strategy System

## Issues Identified

You encountered two main issues:
1. **Database Schema Error**: Missing custom strategy columns in the database
2. **Missing Schedule Module**: The `schedule` package is not installed

## Solution

Follow these steps in order to fix both issues:

### Step 1: Install Required Packages

```powershell
# Install the schedule package for strategy scheduling
pip install schedule

# Install other optional packages for enhanced functionality
pip install pandas numpy

# Or install all at once from the requirements file
pip install -r requirements_custom_strategies.txt
```

### Step 2: Run Database Migration

```powershell
# Run the migration script to add the new columns
python migrate_database.py
```

**Expected Output:**
```
OpenAlgo Custom Strategy System - Database Migration
=======================================================

1. Checking dependencies...
✓ Package 'schedule' is installed

2. Running database migration...
Current columns: ['id', 'name', 'webhook_id', 'user_id', 'platform', 'is_active', ...]
Adding column: ALTER TABLE strategies ADD COLUMN strategy_type VARCHAR(20) DEFAULT 'webhook'
✓ Successfully added column: strategy_type
Adding column: ALTER TABLE strategies ADD COLUMN strategy_file VARCHAR(255)
✓ Successfully added column: strategy_file
Adding column: ALTER TABLE strategies ADD COLUMN strategy_category VARCHAR(50)
✓ Successfully added column: strategy_category
Adding column: ALTER TABLE strategies ADD COLUMN execution_mode VARCHAR(20) DEFAULT 'immediate'
✓ Successfully added column: execution_mode
Adding column: ALTER TABLE strategies ADD COLUMN schedule_config TEXT
✓ Successfully added column: schedule_config
Adding column: ALTER TABLE strategies ADD COLUMN strategy_config TEXT
✓ Successfully added column: strategy_config
✓ Database migration completed successfully!

🎉 Migration completed successfully!
```

### Step 3: Restart OpenAlgo Application

After running the migration, restart your OpenAlgo application:

```powershell
# Stop the current application (Ctrl+C if running in terminal)
# Then restart it
python app.py
```

### Step 4: Test the Custom Strategy System

1. **Go to Strategies Page**: Navigate to the strategies section
2. **Create New Strategy**: Click "New Strategy" 
3. **Select Custom Strategy**: Choose "Custom Strategy" from the platform dropdown
4. **Verify**: You should now see the custom strategy options without errors

## Verification Steps

### 1. Check Database Schema
```powershell
# Run this to verify the database has been updated
python -c "
from database.strategy_db import Strategy
import inspect
fields = [name for name, obj in inspect.getmembers(Strategy) if not name.startswith('_')]
custom_fields = ['strategy_type', 'strategy_file', 'strategy_category', 'execution_mode', 'schedule_config', 'strategy_config']
for field in custom_fields:
    if field in str(fields):
        print(f'✓ {field} - OK')
    else:
        print(f'✗ {field} - Missing')
"
```

### 2. Test Strategy Loading
```powershell
# Run the test suite to verify everything works
python test_custom_strategy.py
```

### 3. Test Custom Strategy Creation
1. Go to **Strategies** → **New Strategy**
2. Select **Platform**: "Custom Strategy"
3. You should see:
   - Strategy file dropdown with example strategies
   - Execution mode options
   - Strategy parameters field
   - Schedule configuration (if schedule mode selected)

## What Each Fix Does

### Database Migration (`migrate_database.py`)
- Adds 6 new columns to the existing `strategies` table
- Uses ALTER TABLE statements for backward compatibility
- Handles SQLite-specific requirements (TEXT instead of JSON)
- Provides detailed logging of the migration process

### Requirements Installation
- `schedule`: Required for periodic strategy execution
- `pandas`: Used by example strategies for data analysis
- `numpy`: Mathematical operations in strategies

### Updated Strategy Executor
- Gracefully handles missing `schedule` module
- Falls back to immediate and queue execution if scheduling unavailable
- Provides clear error messages about missing dependencies

## Troubleshooting

### If Migration Fails
1. **Check Database Path**: Ensure OpenAlgo database exists
2. **Check Permissions**: Ensure write access to database file
3. **Backup First**: Make a backup of your database before migration

### If Packages Won't Install
```powershell
# Try upgrading pip first
python -m pip install --upgrade pip

# Then install packages
pip install schedule pandas numpy
```

### If Strategies Page Still Shows Errors
1. **Clear Browser Cache**: Hard refresh the page (Ctrl+F5)
2. **Check Console**: Look for JavaScript errors in browser console
3. **Restart Application**: Completely restart the OpenAlgo application

## Manual Database Update (Alternative)

If the migration script doesn't work, you can manually update the database:

```sql
-- Connect to your SQLite database and run these commands
ALTER TABLE strategies ADD COLUMN strategy_type VARCHAR(20) DEFAULT 'webhook';
ALTER TABLE strategies ADD COLUMN strategy_file VARCHAR(255);
ALTER TABLE strategies ADD COLUMN strategy_category VARCHAR(50);
ALTER TABLE strategies ADD COLUMN execution_mode VARCHAR(20) DEFAULT 'immediate';
ALTER TABLE strategies ADD COLUMN schedule_config TEXT;
ALTER TABLE strategies ADD COLUMN strategy_config TEXT;
```

## Expected Behavior After Fix

### Strategy Creation Page
- Platform dropdown includes "Custom Strategy" option
- Selecting custom strategy shows additional configuration options
- No more "missing column" errors

### Strategy Execution
- Immediate execution works for custom strategies
- Queue execution available
- Scheduled execution available (if schedule package installed)

### Strategy Management
- View custom strategies with their specific information
- Execute custom strategies manually
- Monitor execution history and logs

## Post-Fix Testing

Create a simple test strategy to verify everything works:

1. **Create Strategy File**: `custom_strategies/user_strategies/test_strategy.py`
```python
from custom_strategies.base_strategy import BaseStrategy

class TestStrategy(BaseStrategy):
    def execute(self):
        symbols = self.get_config_value('symbols', ['RELIANCE'])
        self.log_info(f"Test strategy executed with {len(symbols)} symbols")
        return symbols
```

2. **Create Strategy in UI**:
   - Name: "Test Custom Strategy"
   - Platform: "Custom Strategy" 
   - Strategy File: "test_strategy.py"
   - Parameters: `{"symbols": ["RELIANCE", "TCS"]}`

3. **Execute Strategy**: Click "Execute Now" and verify it runs without errors

## Support

If you continue to experience issues after following this guide:

1. **Check Application Logs**: Look for detailed error messages
2. **Verify File Permissions**: Ensure all files are readable
3. **Test Individual Components**: Use `test_custom_strategy.py` to isolate issues
4. **Check Dependencies**: Verify all required packages are installed

The custom strategy system should now be fully functional!