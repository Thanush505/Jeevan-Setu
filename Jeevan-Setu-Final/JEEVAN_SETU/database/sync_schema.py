"""
database/sync_schema.py — Live database scanner and schema sync utility.
Scans the live MySQL database and updates:
1. database/schema.sql (Authoritative MySQL DDL)
2. database/schema.db & database/jeevan_setu.db (SQLite database snapshots)
3. schema.db at workspace root
"""

import os
import sys
import sqlite3
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import Database

def map_mysql_type_to_sqlite(data_type, col_type):
    data_type = data_type.lower()
    col_type = col_type.lower()
    if 'int' in data_type:
        return 'INTEGER'
    elif any(t in data_type for t in ['char', 'text', 'enum', 'set']):
        return 'TEXT'
    elif any(t in data_type for t in ['date', 'time', 'year']):
        return 'TEXT'
    elif any(t in data_type for t in ['decimal', 'numeric', 'float', 'double', 'real']):
        return 'REAL'
    elif 'blob' in data_type or 'binary' in data_type:
        return 'BLOB'
    return 'TEXT'

def sanitize_value_for_sqlite(val):
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val

def sync_all():
    print("=== Scanning Live MySQL Database ===")
    mysql_db = Database()
    
    tables_res = mysql_db.execute_query("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'", fetch=True)
    table_names = [list(t.values())[0] for t in tables_res]
    print(f"Found {len(table_names)} tables in 'jeevan_setu'.")

    # Update schema.sql
    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_sql_path = os.path.join(base_dir, 'schema.sql')
    
    sql_lines = [
        "-- =============================================================",
        "-- JEEVAN SETU — Complete Live Database Schema (schema.sql)",
        "-- Smart ICU/HDU Patient Monitoring & Clinical Decision Support",
        f"-- Scanned and synchronized on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "-- =============================================================",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
        ""
    ]

    for idx, t in enumerate(sorted(table_names), 1):
        res = mysql_db.execute_query(f"SHOW CREATE TABLE `{t}`", fetch=True)
        if res:
            create_sql = res[0]['Create Table']
            if "CREATE TABLE IF NOT EXISTS" not in create_sql:
                create_sql = create_sql.replace(f"CREATE TABLE `{t}`", f"CREATE TABLE IF NOT EXISTS `{t}`", 1)
            sql_lines.append(f"-- {idx}. Table: {t}")
            sql_lines.append(create_sql + ";\n")

    sql_lines.append("SET FOREIGN_KEY_CHECKS = 1;\n")
    with open(schema_sql_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_lines))
    print(f"Updated MySQL DDL: {schema_sql_path}")

    # Update SQLite database snapshots (.db files)
    workspace_root = os.path.abspath(os.path.join(base_dir, '..', '..'))
    db_paths = [
        os.path.join(base_dir, 'schema.db'),
        os.path.join(base_dir, 'jeevan_setu.db'),
        os.path.join(workspace_root, 'Jeevan-Setu-Final', 'schema.db'),
        os.path.join(workspace_root, 'schema.db')
    ]

    for target_db in db_paths:
        if os.path.exists(target_db):
            os.remove(target_db)
            
        conn = sqlite3.connect(target_db)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = OFF;")

        for t in sorted(table_names):
            cols = mysql_db.execute_query(f"""
                SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'jeevan_setu' AND TABLE_NAME = '{t}'
                ORDER BY ORDINAL_POSITION
            """, fetch=True)

            col_defs = []
            pk_cols = [c['COLUMN_NAME'] for c in cols if c['COLUMN_KEY'] == 'PRI']

            for c in cols:
                c_name = c['COLUMN_NAME']
                c_type = map_mysql_type_to_sqlite(c['DATA_TYPE'], c['COLUMN_TYPE'])
                is_auto = 'auto_increment' in str(c['EXTRA']).lower()
                
                if is_auto and len(pk_cols) == 1 and c_name == pk_cols[0]:
                    col_defs.append(f'"{c_name}" INTEGER PRIMARY KEY AUTOINCREMENT')
                else:
                    null_str = "NOT NULL" if c['IS_NULLABLE'] == 'NO' and not is_auto else ""
                    col_defs.append(f'"{c_name}" {c_type} {null_str}'.strip())

            if len(pk_cols) > 1 or (len(pk_cols) == 1 and 'auto_increment' not in str(cols[0]['EXTRA']).lower()):
                pk_clause = f", PRIMARY KEY ({', '.join(['\"' + p + '\"' for p in pk_cols])})"
            else:
                pk_clause = ""

            create_table_stmt = f'CREATE TABLE IF NOT EXISTS "{t}" (\n  ' + ",\n  ".join(col_defs) + pk_clause + "\n);"
            cur.execute(create_table_stmt)

            rows = mysql_db.execute_query(f"SELECT * FROM `{t}`", fetch=True)
            if rows:
                col_names = list(rows[0].keys())
                placeholders = ", ".join(["?"] * len(col_names))
                cols_str = ", ".join([f'"{cn}"' for cn in col_names])
                insert_stmt = f'INSERT INTO "{t}" ({cols_str}) VALUES ({placeholders})'
                
                values_to_insert = [
                    [sanitize_value_for_sqlite(row[cn]) for cn in col_names]
                    for row in rows
                ]
                cur.executemany(insert_stmt, values_to_insert)

        conn.commit()
        conn.close()
        print(f"Synchronized SQLite DB: {target_db} ({os.path.getsize(target_db):,} bytes)")

    print("=== Database Scan & Schema Sync Complete ===")

if __name__ == '__main__':
    sync_all()
