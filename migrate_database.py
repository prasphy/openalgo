"""
Database Migration Script for Custom Strategy System

This script adds the necessary columns to the existing strategies table
to support custom strategies functionality.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_database_path():
    """Get the database path from environment or use default."""
    db_url = os.getenv('DATABASE_URL', 'sqlite:///db/openalgo.db')
    if db_url.startswith('sqlite:///'):
        return db_url[10:]  # Remove 'sqlite:///' prefix
    else:
        raise ValueError("This migration script only supports SQLite databases")

def migrate_strategies_table():
    """Add custom strategy columns to the strategies table."""
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        print(f"Database file not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategies'")
        if not cursor.fetchone():
            print("Strategies table not found. Please ensure OpenAlgo is properly initialized.")
            return False
        
        # Get current table schema
        cursor.execute("PRAGMA table_info(strategies)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # List of new columns to add
        new_columns = [
            ("strategy_type", "VARCHAR(20) DEFAULT 'webhook'"),
            ("strategy_file", "VARCHAR(255)"),
            ("strategy_category", "VARCHAR(50)"),
            ("execution_mode", "VARCHAR(20) DEFAULT 'immediate'"),
            ("schedule_config", "TEXT"),  # Using TEXT instead of JSON for SQLite compatibility
            ("strategy_config", "TEXT")   # Using TEXT instead of JSON for SQLite compatibility
        ]
        
        # Add missing columns
        for column_name, column_definition in new_columns:
            if column_name not in columns:
                try:
                    sql = f"ALTER TABLE strategies ADD COLUMN {column_name} {column_definition}"
                    print(f"Adding column: {sql}")
                    cursor.execute(sql)
                    print(f"✓ Successfully added column: {column_name}")
                except sqlite3.Error as e:
                    print(f"✗ Error adding column {column_name}: {e}")
                    return False
            else:
                print(f"✓ Column {column_name} already exists")
        
        # Commit changes
        conn.commit()
        print("✓ Database migration completed successfully!")
        
        # Verify the new schema
        cursor.execute("PRAGMA table_info(strategies)")
        new_columns_list = [column[1] for column in cursor.fetchall()]
        print(f"Updated columns: {new_columns_list}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def check_dependencies():
    """Check if required Python packages are installed."""
    required_packages = ['schedule']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ Package '{package}' is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ Package '{package}' is missing")
    
    return missing_packages

def main():
    """Run the migration process."""
    print("OpenAlgo Custom Strategy System - Database Migration")
    print("=" * 55)
    
    # Check dependencies
    print("\n1. Checking dependencies...")
    missing_packages = check_dependencies()
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Please install missing packages using:")
        for package in missing_packages:
            print(f"  pip install {package}")
        print("\nThen run this script again.")
        return False
    
    # Run database migration
    print("\n2. Running database migration...")
    success = migrate_strategies_table()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your OpenAlgo application")
        print("2. Go to Strategies > New Strategy")
        print("3. Select 'Custom Strategy' from the platform dropdown")
        print("4. Create your first custom strategy!")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    main()