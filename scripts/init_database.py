#!/usr/bin/env python3
"""
Initialize PC-Inspector Database

Creates SQLite database with complete schema for system monitoring.
Safe to run multiple times - only creates tables if they don't exist.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import Database

def main():
    print("PC-Inspector: Database Initialization")
    print("=" * 50)

    try:
        # Create database instance
        db = Database()
        db.connect()

        print("Creating database schema...")
        db.create_schema()
        db.disconnect()

        print("✓ Database initialized successfully!")
        print(f"✓ Location: {db.db_path}")
        print("\nDatabase is ready for use.")
        print("Start backend with: python backend/main.py")

    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
