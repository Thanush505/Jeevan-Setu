"""
database/migration_manager.py — Migration runner and tracker for Jeevan Setu.
"""

import os
import glob
import hashlib
from mysql.connector import Error
from database.db import db
from config import get_config


class MigrationManager:
    """Manages versioned database migrations with idempotency and partial-recovery safety."""

    # Benign MySQL DDL errno codes that allow safe re-entry after partial DDL execution:
    # 1050: Table already exists
    # 1060: Duplicate column name
    # 1061: Duplicate key/index name
    # 1091: Can't DROP column/key; check that it exists
    # 1826: Duplicate foreign key constraint name
    IDEMPOTENT_DDL_ERRNOS = (1050, 1060, 1061, 1091, 1826)

    def __init__(self, migrations_dir=None, db_instance=None):
        if migrations_dir is None:
            self.migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        else:
            self.migrations_dir = migrations_dir
        os.makedirs(self.migrations_dir, exist_ok=True)
        self.db = db_instance or db

    @staticmethod
    def compute_checksum(filepath):
        """Compute SHA-256 hex digest of a migration SQL file."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

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
        self.db.execute_query(sql)

    def get_applied_migrations(self):
        """Return list of already applied migration versions."""
        self.init_migration_table()
        rows = self.db.execute_query(
            "SELECT version FROM schema_migrations ORDER BY migration_id ASC",
            fetch=True
        )
        return [r['version'] for r in rows] if rows else []

    def is_migration_applied(self, version):
        """Check whether a specific migration version is already recorded in schema_migrations."""
        self.init_migration_table()
        row = self.db.execute_query(
            "SELECT migration_id, version, description, applied_at FROM schema_migrations WHERE version = %s",
            (version,),
            fetch='one'
        )
        return row is not None

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

    @staticmethod
    def parse_sql_statements(sql_content):
        """
        Parse SQL content into executable statements, stripping comment-only lines
        prior to semicolon splitting so semicolons in comments do not split statements.
        """
        cleaned_lines = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                continue
            cleaned_lines.append(line)
        cleaned_sql = '\n'.join(cleaned_lines)
        return [stmt.strip() for stmt in cleaned_sql.split(';') if stmt.strip()]

    def verify_migration_postconditions(self, version, cursor):
        """
        Verify postconditions before recording a migration in schema_migrations.
        Specifically validates 009_agentic_hybrid_multimodal_rag objects if version matches.
        """
        if version == '009_agentic_hybrid_multimodal_rag':
            required_tables = [
                'rag_documents',
                'rag_document_images',
                'rag_document_chunks',
                'patient_medical_images',
            ]
            cursor.execute("SHOW TABLES")
            existing_tables = {list(r.values())[0].lower() for r in cursor.fetchall()}
            for req_tbl in required_tables:
                if req_tbl not in existing_tables:
                    raise RuntimeError(
                        f"Postcondition verification failed for {version}: missing table '{req_tbl}'"
                    )

            cursor.execute("SHOW COLUMNS FROM `chatbot_conversations`")
            conv_cols = {r['Field'] for r in cursor.fetchall()}
            for req_col in ('chat_mode', 'tools_invoked', 'rag_sources'):
                if req_col not in conv_cols:
                    raise RuntimeError(
                        f"Postcondition verification failed for {version}: "
                        f"missing column 'chatbot_conversations.{req_col}'"
                    )

    def apply_migration(self, version, filename, filepath):
        """
        Run a single SQL migration file with orchestration-level idempotency and
        partial-recovery tracking. Never records version in schema_migrations unless
        all statements and postcondition checks succeed.
        """
        if self.is_migration_applied(version):
            print(f"SKIP: Migration {version} ({filename}) is already applied.")
            return False

        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        checksum = self.compute_checksum(filepath)
        statements = self.parse_sql_statements(sql_content)
        print(f"Applying migration: {filename} (sha256={checksum[:12]}..., {len(statements)} statements)...")

        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        completed_ops = []
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for idx, clean_stmt in enumerate(statements, 1):
                stmt_preview = ' '.join(clean_stmt.split())[:80]
                try:
                    cursor.execute(clean_stmt)
                    completed_ops.append((idx, 'EXECUTED', stmt_preview))
                except Error as err:
                    if err.errno in self.IDEMPOTENT_DDL_ERRNOS:
                        completed_ops.append((idx, f'SKIPPED_EXISTING(errno={err.errno})', stmt_preview))
                        continue
                    raise err

            # Verify postconditions before marking migration as applied
            self.verify_migration_postconditions(version, cursor)

            description = f"Migration {filename} [sha256:{checksum[:16]}]"
            cursor.execute(
                """INSERT INTO schema_migrations (version, description)
                   SELECT %s, %s FROM DUAL
                   WHERE NOT EXISTS (
                       SELECT 1 FROM schema_migrations WHERE version = %s
                   )""",
                (version, description, version)
            )
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()
            print(f"SUCCESS: {filename} applied ({len(completed_ops)} statements processed).")
            return True
        except Exception as e:
            try:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                conn.rollback()
            except Exception:
                pass
            print(
                f"FAILED: Migration {filename} failed after {len(completed_ops)}/{len(statements)} "
                f"statements. Completed operations: {completed_ops}. Error: {e}"
            )
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

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
            if self.apply_migration(version, filename, filepath):
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
