"""
database/sync_schema.py — Live database schema scanner and synchronization utility.
Scans the live MySQL database INFORMATION_SCHEMA and synchronizes:
1. database/schema.sql (Authoritative MySQL DDL without sensitive row data)
2. database/schema.db & database/jeevan_setu.db (SQLite 3 schema-only reference databases)
3. Jeevan-Setu-Final/schema.db & workspace-root schema.db

SECURITY POLICY:
- Synchronizes ONLY table structures, columns, types, nullability, defaults,
  primary keys, foreign keys, unique constraints, indexes, and non-sensitive
  `schema_migrations` version tracking metadata.
- NEVER copies patient records, clinical records, user password hashes,
  authentication tokens, or private user data into Schema.db or schema.sql.
"""

import os
import re
import sys
import sqlite3
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import Database


# Only non-sensitive migration version tracking metadata may be mirrored
ALLOWED_METADATA_TABLES = frozenset({'schema_migrations'})


def map_mysql_type_to_sqlite(data_type, col_type):
    """Map MySQL column data type to SQLite affinity while preserving descriptive type info."""
    data_type = str(data_type or '').lower()
    col_type = str(col_type or '').lower()
    if 'int' in data_type:
        return 'INTEGER'
    elif any(t in data_type for t in ['char', 'text', 'enum', 'set', 'json']):
        return 'TEXT'
    elif any(t in data_type for t in ['date', 'time', 'year']):
        return 'TEXT'
    elif any(t in data_type for t in ['decimal', 'numeric', 'float', 'double', 'real']):
        return 'REAL'
    elif 'blob' in data_type or 'binary' in data_type:
        return 'BLOB'
    return 'TEXT'


def format_sqlite_default(col_default, data_type):
    """Format a MySQL COLUMN_DEFAULT into a valid SQLite DEFAULT clause."""
    if col_default is None:
        return ""
    default_str = str(col_default).strip()
    upper_def = default_str.upper()
    if upper_def in ('CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP()', 'NOW()'):
        return "DEFAULT CURRENT_TIMESTAMP"
    if upper_def == 'NULL':
        return "DEFAULT NULL"
    data_type_lower = str(data_type or '').lower()
    if 'int' in data_type_lower or any(t in data_type_lower for t in ['decimal', 'numeric', 'float', 'double', 'real']):
        try:
            float(default_str)
            return f"DEFAULT {default_str}"
        except ValueError:
            pass
    escaped = default_str.replace("'", "''")
    return f"DEFAULT '{escaped}'"


def sanitize_value_for_sqlite(val):
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def normalize_mysql_create_table(create_sql, table_name):
    """Ensure CREATE TABLE IF NOT EXISTS and strip dynamic AUTO_INCREMENT=<n> counters."""
    if "CREATE TABLE IF NOT EXISTS" not in create_sql:
        create_sql = create_sql.replace(
            f"CREATE TABLE `{table_name}`",
            f"CREATE TABLE IF NOT EXISTS `{table_name}`",
            1
        )
    create_sql = re.sub(r'\s+AUTO_INCREMENT=\d+', '', create_sql)
    return create_sql


def get_mysql_schema_metadata(mysql_db, schema_name='jeevan_setu'):
    """Inspect MySQL INFORMATION_SCHEMA for all tables, columns, PKs, FKs, unique constraints, and indexes."""
    tables_res = mysql_db.execute_query(
        "SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'",
        fetch=True
    )
    table_names = sorted([list(t.values())[0] for t in tables_res])

    metadata = {}
    for t in table_names:
        cols = mysql_db.execute_query(
            """
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE,
                   COLUMN_KEY, EXTRA, COLUMN_DEFAULT, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (schema_name, t),
            fetch=True
        )

        fks_raw = mysql_db.execute_query(
            """
            SELECT kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME,
                   kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
                   rc.UPDATE_RULE, rc.DELETE_RULE
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
              ON kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
             AND kcu.TABLE_NAME = rc.TABLE_NAME
             AND kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            WHERE kcu.TABLE_SCHEMA = %s
              AND kcu.TABLE_NAME = %s
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
            """,
            (schema_name, t),
            fetch=True
        )

        stats_raw = mysql_db.execute_query(
            """
            SELECT INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """,
            (schema_name, t),
            fetch=True
        )

        indexes = {}
        for s in stats_raw:
            idx_name = s['INDEX_NAME']
            if idx_name not in indexes:
                indexes[idx_name] = {
                    'name': idx_name,
                    'unique': (int(s['NON_UNIQUE']) == 0),
                    'columns': []
                }
            indexes[idx_name]['columns'].append(s['COLUMN_NAME'])

        metadata[t] = {
            'columns': cols,
            'foreign_keys': fks_raw,
            'indexes': indexes,
        }

    return table_names, metadata


def build_sqlite_schema_statements(table_name, tbl_meta):
    """Build SQLite CREATE TABLE and CREATE INDEX statements preserving PKs, FKs, Unique constraints, and Indexes."""
    cols = tbl_meta['columns']
    fks = tbl_meta['foreign_keys']
    indexes = tbl_meta['indexes']

    pk_cols = indexes.get('PRIMARY', {}).get('columns') or [
        c['COLUMN_NAME'] for c in cols if c['COLUMN_KEY'] == 'PRI'
    ]
    single_auto_pk = (
        len(pk_cols) == 1 and any(
            c['COLUMN_NAME'] == pk_cols[0] and 'auto_increment' in str(c['EXTRA']).lower()
            for c in cols
        )
    )

    col_defs = []
    for c in cols:
        c_name = c['COLUMN_NAME']
        c_type = map_mysql_type_to_sqlite(c['DATA_TYPE'], c['COLUMN_TYPE'])
        is_auto = 'auto_increment' in str(c['EXTRA']).lower()

        if single_auto_pk and c_name == pk_cols[0] and is_auto:
            col_defs.append(f'"{c_name}" INTEGER PRIMARY KEY AUTOINCREMENT')
        else:
            parts = [f'"{c_name}"', c_type]
            if c['IS_NULLABLE'] == 'NO' and not is_auto:
                parts.append("NOT NULL")
            def_clause = format_sqlite_default(c['COLUMN_DEFAULT'], c['DATA_TYPE'])
            if def_clause:
                parts.append(def_clause)
            col_defs.append(" ".join(parts))

    table_constraints = []
    if pk_cols and not single_auto_pk:
        pk_cols_quoted = ", ".join(f'"{p}"' for p in pk_cols)
        table_constraints.append(f"PRIMARY KEY ({pk_cols_quoted})")

    # Group composite or single-column unique constraints
    for idx_name, idx_info in indexes.items():
        if idx_name == 'PRIMARY':
            continue
        if idx_info['unique']:
            u_cols_quoted = ", ".join(f'"{col}"' for col in idx_info['columns'])
            table_constraints.append(f'CONSTRAINT "{idx_name}" UNIQUE ({u_cols_quoted})')

    # Group foreign keys by constraint name
    fk_groups = {}
    for fk in fks:
        cname = fk['CONSTRAINT_NAME']
        if cname not in fk_groups:
            fk_groups[cname] = {
                'cols': [],
                'ref_table': fk['REFERENCED_TABLE_NAME'],
                'ref_cols': [],
                'on_delete': fk['DELETE_RULE'],
                'on_update': fk['UPDATE_RULE'],
            }
        fk_groups[cname]['cols'].append(fk['COLUMN_NAME'])
        fk_groups[cname]['ref_cols'].append(fk['REFERENCED_COLUMN_NAME'])

    for cname, fk_info in fk_groups.items():
        local_cols = ", ".join(f'"{col}"' for col in fk_info['cols'])
        ref_cols = ", ".join(f'"{col}"' for col in fk_info['ref_cols'])
        fk_clause = (
            f'CONSTRAINT "{cname}" FOREIGN KEY ({local_cols}) '
            f'REFERENCES "{fk_info["ref_table"]}" ({ref_cols})'
        )
        if fk_info['on_delete']:
            fk_clause += f' ON DELETE {fk_info["on_delete"]}'
        if fk_info['on_update']:
            fk_clause += f' ON UPDATE {fk_info["on_update"]}'
        table_constraints.append(fk_clause)

    all_entries = col_defs + table_constraints
    create_table_stmt = (
        f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  '
        + ",\n  ".join(all_entries)
        + "\n);"
    )

    index_stmts = []
    for idx_name, idx_info in indexes.items():
        if idx_name == 'PRIMARY':
            continue
        unique_kw = "UNIQUE " if idx_info['unique'] else ""
        safe_idx_name = f"idx_{table_name}_{idx_name}"
        cols_quoted = ", ".join(f'"{col}"' for col in idx_info['columns'])
        index_stmts.append(
            f'CREATE {unique_kw}INDEX IF NOT EXISTS "{safe_idx_name}" '
            f'ON "{table_name}" ({cols_quoted});'
        )

    return create_table_stmt, index_stmts


def sync_sqlite_file(target_db_path, table_names, metadata, migration_rows):
    """Write a clean, schema-only SQLite 3 reference database to target_db_path."""
    tmp_path = target_db_path + ".tmp_sync"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    conn = sqlite3.connect(tmp_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF;")

    for t in table_names:
        create_stmt, index_stmts = build_sqlite_schema_statements(t, metadata[t])
        cur.execute(create_stmt)
        for idx_stmt in index_stmts:
            cur.execute(idx_stmt)

        if t in ALLOWED_METADATA_TABLES and t == 'schema_migrations' and migration_rows:
            col_names = list(migration_rows[0].keys())
            placeholders = ", ".join(["?"] * len(col_names))
            cols_str = ", ".join([f'"{cn}"' for cn in col_names])
            insert_stmt = f'INSERT INTO "{t}" ({cols_str}) VALUES ({placeholders})'
            values_to_insert = [
                [sanitize_value_for_sqlite(row[cn]) for cn in col_names]
                for row in migration_rows
            ]
            cur.executemany(insert_stmt, values_to_insert)

    conn.commit()
    conn.close()

    if os.path.exists(target_db_path):
        os.remove(target_db_path)
    os.replace(tmp_path, target_db_path)


def sync_all(target_db_paths=None, schema_sql_path=None):
    """
    Scan live MySQL INFORMATION_SCHEMA and synchronize schema.sql and all Schema.db files.
    Returns a summary dictionary for verification and testing.
    """
    print("=== Scanning Live MySQL Database (Schema-Only Safe Mode) ===")
    mysql_db = Database()
    table_names, metadata = get_mysql_schema_metadata(mysql_db, schema_name='jeevan_setu')
    print(f"Found {len(table_names)} tables in 'jeevan_setu'.")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if schema_sql_path is None:
        schema_sql_path = os.path.join(base_dir, 'schema.sql')

    sql_lines = [
        "-- =============================================================",
        "-- JEEVAN SETU — Complete Live Database Schema (schema.sql)",
        "-- Smart ICU/HDU Patient Monitoring & Clinical Decision Support",
        "-- Authoritative MySQL DDL (Schema-Only, No Sensitive Data)",
        "-- =============================================================",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
        ""
    ]

    for idx, t in enumerate(table_names, 1):
        res = mysql_db.execute_query(f"SHOW CREATE TABLE `{t}`", fetch=True)
        if res:
            create_sql = normalize_mysql_create_table(res[0]['Create Table'], t)
            sql_lines.append(f"-- {idx}. Table: {t}")
            sql_lines.append(create_sql + ";\n")

    sql_lines.append("SET FOREIGN_KEY_CHECKS = 1;\n")
    with open(schema_sql_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_lines))
    print(f"Updated MySQL DDL: {schema_sql_path}")

    migration_rows = mysql_db.execute_query(
        "SELECT migration_id, version, description, applied_at FROM schema_migrations ORDER BY migration_id ASC",
        fetch=True
    ) or []

    if target_db_paths is None:
        project_root = os.path.abspath(os.path.join(base_dir, '..'))
        final_root = os.path.abspath(os.path.join(base_dir, '..', '..'))
        repo_root = os.path.abspath(os.path.join(base_dir, '..', '..', '..'))
        candidate_paths = [
            os.path.join(base_dir, 'schema.db'),
            os.path.join(base_dir, 'jeevan_setu.db'),
            os.path.join(final_root, 'schema.db'),
            os.path.join(repo_root, 'schema.db'),
        ]
        target_db_paths = []
        for p in candidate_paths:
            abs_p = os.path.abspath(p)
            if os.path.exists(abs_p) or abs_p.startswith(os.path.abspath(final_root)):
                if abs_p not in target_db_paths:
                    target_db_paths.append(abs_p)

    for target_db in target_db_paths:
        sync_sqlite_file(target_db, table_names, metadata, migration_rows)
        print(f"Synchronized Schema-Only SQLite DB: {target_db} ({os.path.getsize(target_db):,} bytes)")

    print("=== Database Scan & Schema Sync Complete ===")
    return {
        'table_count': len(table_names),
        'tables': table_names,
        'schema_sql_path': schema_sql_path,
        'sqlite_paths': target_db_paths,
    }


if __name__ == '__main__':
    sync_all()
