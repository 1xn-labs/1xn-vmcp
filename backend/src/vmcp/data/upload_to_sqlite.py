#!/usr/bin/env python3
"""
Script to upload global_public_vmcp_registry data from JSON to SQLite database.

Handles JSONB columns from PostgreSQL by storing them as TEXT in SQLite,
which can be queried using SQLite's built-in JSON functions.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def create_table(cursor: sqlite3.Cursor):
    """Create the global_public_vmcp_registry table in SQLite.
    
    Always drops existing table and index before creating fresh schema.
    
    Note: In PostgreSQL, vmcp_registry_config and vmcp_config are JSONB.
    In SQLite, we store them as TEXT, which can be queried using JSON functions.
    """
    # Drop index if it exists
    cursor.execute("DROP INDEX IF EXISTS idx_type")
    
    # Drop table if it exists
    cursor.execute("DROP TABLE IF EXISTS global_public_vmcp_registry")
    
    # Create table with fresh schema
    cursor.execute("""
        CREATE TABLE global_public_vmcp_registry (
            public_vmcp_id TEXT NOT NULL PRIMARY KEY,
            type TEXT,
            vmcp_registry_config TEXT NOT NULL,  -- JSON stored as TEXT
            vmcp_config TEXT NOT NULL,           -- JSON stored as TEXT
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index on type for faster queries
    cursor.execute("""
        CREATE INDEX idx_type ON global_public_vmcp_registry(type)
    """)


def load_json_data(json_file: Path) -> List[Dict[str, Any]]:
    """Load records from JSON file."""
    print(f"Loading data from {json_file}...")
    
    if not json_file.exists():
        raise FileNotFoundError(f"JSON file not found: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        raise ValueError("JSON file must contain an array of records")
    
    print(f"Loaded {len(data)} records")
    return data


def parse_timestamp(timestamp_str: Any) -> datetime:
    """Parse ISO format timestamp string to datetime object.
    
    Handles various timestamp formats and returns current time if parsing fails.
    """
    if timestamp_str is None:
        return datetime.now()
    
    if isinstance(timestamp_str, datetime):
        return timestamp_str
    
    if not isinstance(timestamp_str, str):
        return datetime.now()
    
    try:
        # Handle ISO format with or without timezone
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str.replace('Z', '+00:00')
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, AttributeError):
        # Fallback to current time if parsing fails
        return datetime.now()


def insert_records(cursor: sqlite3.Cursor, records: List[Dict[str, Any]], batch_size: int = 100):
    """Insert records into the database in batches."""
    insert_sql = """
        INSERT OR REPLACE INTO global_public_vmcp_registry 
        (public_vmcp_id, type, vmcp_registry_config, vmcp_config, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    
    total = len(records)
    print(f"Inserting {total} records...")
    
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        batch_data = []
        
        for record in batch:
            # Convert JSON objects to JSON strings for storage
            vmcp_registry_config = json.dumps(record.get('vmcp_registry_config', {}))
            vmcp_config = json.dumps(record.get('vmcp_config', {}))
            
            # Extract timestamps from vmcp_registry_config
            registry_config = record.get('vmcp_registry_config', {})
            created_at = parse_timestamp(registry_config.get('created_at'))
            updated_at = parse_timestamp(registry_config.get('updated_at'))
            
            batch_data.append((
                record.get('public_vmcp_id'),
                record.get('type'),
                vmcp_registry_config,
                vmcp_config,
                created_at,
                updated_at
            ))
        
        cursor.executemany(insert_sql, batch_data)
        print(f"  Inserted batch {i // batch_size + 1} ({min(i + batch_size, total)}/{total} records)")


def ensure_db_directory(db_path: Path):
    """Ensure the database directory exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description='Upload global_public_vmcp_registry data from JSON to SQLite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload to default database (~/.vmcp/vmcp.db):
  python upload_to_sqlite.py -j global_public_vmcp_registry.json

  # Upload to custom database:
  python upload_to_sqlite.py -j global_public_vmcp_registry.json -d /path/to/custom.db

  # Upload with custom batch size:
  python upload_to_sqlite.py -j global_public_vmcp_registry.json -b 500

Notes:
  - JSONB columns from PostgreSQL are stored as TEXT in SQLite
  - SQLite's JSON functions (json_extract, json_each, etc.) can query JSON stored as TEXT
  - Use json_extract(vmcp_registry_config, '$.field') to query nested JSON fields
  - Table is always dropped if it exists before creating new one
        """
    )
    
    parser.add_argument(
        '-j', '--json',
        required=True,
        type=Path,
        help='Path to JSON file containing registry data'
    )
    
    parser.add_argument(
        '-d', '--database',
        default=str(Path.home() / '.vmcp' / 'vmcp.db'),
        help='SQLite database file path (default: ~/.vmcp/vmcp.db)'
    )
    
    parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=100,
        help='Batch size for inserts (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Expand ~ in database path
    db_path = Path(args.database).expanduser()
    
    # Validate JSON file exists
    json_file = args.json.expanduser()
    if not json_file.exists():
        print(f"Error: JSON file not found: {json_file}")
        return 1
    
    # Load JSON data
    try:
        records = load_json_data(json_file)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return 1
    
    # Ensure database directory exists
    try:
        ensure_db_directory(db_path)
    except Exception as e:
        print(f"Error creating database directory: {e}")
        return 1
    
    # Connect to SQLite database
    print(f"Connecting to SQLite database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
    
    try:
        cursor = conn.cursor()
        
        # Create table (always drops existing table first)
        print("Creating table (dropping existing if present)...")
        create_table(cursor)
        
        # Insert records
        insert_records(cursor, records, args.batch_size)
        
        # Commit transaction
        conn.commit()
        print(f"\nSuccessfully uploaded {len(records)} records to {db_path}")
        
        # Show some statistics
        cursor.execute("SELECT COUNT(*) FROM global_public_vmcp_registry")
        count = cursor.fetchone()[0]
        print(f"Total records in database: {count}")
        
        cursor.execute("SELECT COUNT(DISTINCT type) FROM global_public_vmcp_registry")
        type_count = cursor.fetchone()[0]
        print(f"Distinct types: {type_count}")
        
        # Show type breakdown
        cursor.execute("""
            SELECT type, COUNT(*) as count 
            FROM global_public_vmcp_registry 
            GROUP BY type 
            ORDER BY count DESC
        """)
        type_breakdown = cursor.fetchall()
        if type_breakdown:
            print("\nType breakdown:")
            for type_name, count in type_breakdown:
                print(f"  {type_name}: {count}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()
        print("Database connection closed.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

