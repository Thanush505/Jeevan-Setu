"""
database/migration_manager.py — Migration runner and tracker for Jeevan Setu.
"""

import os
import glob
from mysql.connector import Error
from database.db import db
from config import get_config


class MigrationManager:
    """Manages versioned database migrations."""

    def __init__(self, migrations_dir=None):
        if migrations_dir is None:
            self.migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        else:
            self.migrations_dir = migrations_dir
        os.makedirs(self.migrations_dir, exist_ok=True)

    def init_migration_table(self):
        """Ensure schema_migrations table exists."""
        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id INT AUTO_INCREMENT PRIMARY KEY,
            version VARCHAR(100) UNIQUE NOT NULL,
            description VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        db.execute_query(sql)

    def get_applied_migrations(self):
        """Return list of already applied migration versions."""
        self.init_migration_table()
        rows = db.execute_query("SELECT version FROM schema_migrations ORDER BY migration_id ASC", fetch=True)
        return [r['version'] for r in rows] if rows else []

    def get_available_migrations(self):
        """Return sorted list of (version, filename, full_path)."""
        pattern = os.path.join(self.migrations_dir, '*.sql')
        files = sorted(glob.glob(pattern))
        migrations = []
        for path in files:
            filename = os.path.basename(path)
            version = os.path.splitext(filename)[0]
            migrations.append((version, filename, path))
        return migrations

    def apply_migration(self, version, filename, filepath):
        """Run a single SQL migration file inside a transaction."""
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print(f"Applying migration: {filename}...")
        
        # Split statements by semicolon
        raw_statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Temporarily disable foreign key checks for DDL operations
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for stmt in raw_statements:
                # Remove comment-only lines
                lines = [line for line in stmt.splitlines() if line.strip() and not line.strip().startswith('--')]
                clean_stmt = '\n'.join(lines).strip()
                if clean_stmt:
                    try:
                        cursor.execute(clean_stmt)
                    except Error as err:
                        # Ignore benign warnings/errors like duplicate column (1060), index already exists (1061), table already exists (1050), or column does not exist when dropping (1091)
                        if err.errno in (1060, 1061, 1050, 1091):
                            continue
                        raise err

            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (%s, %s)",
                (version, f"Migration {filename}")
            )
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()
            print(f"SUCCESS: {filename} applied.")
            return True
        except Exception as e:
            conn.rollback()
            print(f"FAILED: Migration {filename} failed: {e}")
            raise
        finally:
            cursor.close()

    def run_migrations(self):
        """Apply all pending migrations."""
        self.init_migration_table()
        applied = set(self.get_applied_migrations())
        available = self.get_available_migrations()
        pending = [m for m in available if m[0] not in applied]

        if not pending:
            print("No pending migrations. Database is up to date.")
            return 0

        applied_count = 0
        for version, filename, filepath in pending:
            self.apply_migration(version, filename, filepath)
            applied_count += 1

        print(f"Applied {applied_count} migrations successfully.")
        return applied_count

    def status(self):
        """Display migration status."""
        self.init_migration_table()
        applied = set(self.get_applied_migrations())
        available = self.get_available_migrations()

        print("Migration Status:")
        print("--------------------------------------------------")
        for version, filename, _ in available:
            status = "[APPLIED]" if version in applied else "[PENDING]"
            print(f"{status} {filename}")
        print("--------------------------------------------------")
