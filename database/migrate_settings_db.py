"""
Settings database migration script.

This script safely adds new SMTP columns to the existing settings table
without breaking existing data.
"""

import sqlite3
import os
from utils.logging import get_logger

logger = get_logger(__name__)

def migrate_settings_database():
    """
    Migrate the settings database to add SMTP columns if they don't exist.
    """
    database_url = os.getenv('DATABASE_URL', 'sqlite:///db/openalgo.db')
    
    # Extract the database path from the URL
    if database_url.startswith('sqlite:///'):
        db_path = database_url[10:]  # Remove 'sqlite:///'
    else:
        logger.error("This migration script only supports SQLite databases")
        return False
    
    if not os.path.exists(db_path):
        logger.info("Database doesn't exist yet, will be created with proper schema")
        return True
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if settings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='settings'
        """)
        
        if not cursor.fetchone():
            logger.info("Settings table doesn't exist, will be created with proper schema")
            conn.close()
            return True
        
        # Get current table schema
        cursor.execute("PRAGMA table_info(settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # List of new SMTP columns to add
        smtp_columns = [
            ('smtp_server', 'VARCHAR(255)'),
            ('smtp_port', 'INTEGER'),
            ('smtp_username', 'VARCHAR(255)'),
            ('smtp_password_encrypted', 'TEXT'),
            ('smtp_use_tls', 'BOOLEAN DEFAULT 1'),
            ('smtp_from_email', 'VARCHAR(255)'),
            ('smtp_helo_hostname', 'VARCHAR(255)')
        ]
        
        # Add missing columns
        columns_added = 0
        for column_name, column_type in smtp_columns:
            if column_name not in columns:
                try:
                    alter_sql = f"ALTER TABLE settings ADD COLUMN {column_name} {column_type}"
                    cursor.execute(alter_sql)
                    logger.info(f"Added column: {column_name}")
                    columns_added += 1
                except sqlite3.OperationalError as e:
                    logger.warning(f"Could not add column {column_name}: {e}")
        
        conn.commit()
        conn.close()
        
        if columns_added > 0:
            logger.info(f"Successfully added {columns_added} new columns to settings table")
        else:
            logger.info("Settings table is already up to date")
        
        return True
        
    except Exception as e:
        logger.error(f"Error migrating settings database: {e}")
        return False

if __name__ == "__main__":
    migrate_settings_database()