"""
database/migrate.py — CLI tool for running and managing database migrations.
Usage:
    python database/migrate.py up       # Run pending migrations
    python database/migrate.py status   # Show migration status
    python database/migrate.py init     # Initialize schema from schema.sql
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.migration_manager import MigrationManager
from database.init_db import init_database


def main():
    manager = MigrationManager()
    
    if len(sys.argv) < 2 or sys.argv[1] == 'up':
        print("Running database migrations...")
        manager.run_migrations()
    elif sys.argv[1] == 'status':
        manager.status()
    elif sys.argv[1] == 'init':
        print("Initializing complete schema from schema.sql...")
        init_database()
    else:
        print(f"Unknown command '{sys.argv[1]}'. Use 'up', 'status', or 'init'.")


if __name__ == '__main__':
    main()
