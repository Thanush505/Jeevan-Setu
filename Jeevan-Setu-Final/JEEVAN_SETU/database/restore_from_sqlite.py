"""
database/restore_from_sqlite.py — Restores the MySQL database from SQLite .db snapshot.
"""

import os
import sys
import sqlite3
import mysql.connector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_config

def restore_from_sqlite():
    config = get_config()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(base_dir, '..', '..', '..'))
    
    sqlite_candidates = [
        os.path.join(repo_root, 'schema.db'),
        os.path.join(base_dir, 'schema.db'),
        os.path.join(base_dir, 'jeevan_setu.db')
    ]
    
    sqlite_path = None
    for p in sqlite_candidates:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            sqlite_path = p
            break
            
    if not sqlite_path:
        print("Error: No SQLite snapshot (.db) file found.")
        return False

    print(f"Loading SQLite snapshot from: {sqlite_path}")
    sq_conn = sqlite3.connect(sqlite_path)
    sq_conn.row_factory = sqlite3.Row
    sq_cur = sq_conn.cursor()

    my_conn = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=False
    )
    my_cur = my_conn.cursor()

    my_cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
    my_conn.commit()

    my_cur.execute("SHOW TABLES;")
    mysql_tables = set(row[0] for row in my_cur.fetchall())

    sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    sqlite_tables = [row[0] for row in sq_cur.fetchall()]

    print(f"Found {len(sqlite_tables)} tables in SQLite. Restoring into MySQL '{config.DB_NAME}'...")

    total_inserted = 0
    for table in sqlite_tables:
        if table not in mysql_tables:
            print(f"Skipping table '{table}' (not present in MySQL).")
            continue

        my_cur.execute(f"DESCRIBE `{table}`;")
        my_cols = [col[0] for col in my_cur.fetchall()]

        sq_cur.execute(f'SELECT * FROM "{table}";')
        rows = sq_cur.fetchall()
        if not rows:
            continue

        sq_col_names = [d[0] for d in sq_cur.description]
        common_cols = [c for c in sq_col_names if c in my_cols]

        if not common_cols:
            continue

        cols_clause = ", ".join([f"`{c}`" for c in common_cols])
        placeholders = ", ".join(["%s"] * len(common_cols))
        insert_sql = f"INSERT INTO `{table}` ({cols_clause}) VALUES ({placeholders})"

        my_cur.execute(f"DELETE FROM `{table}`;")

        data_to_insert = [
            tuple(r[c] for c in common_cols)
            for r in rows
        ]

        batch_size = 500
        for i in range(0, len(data_to_insert), batch_size):
            batch = data_to_insert[i:i + batch_size]
            my_cur.executemany(insert_sql, batch)

        my_conn.commit()
        total_inserted += len(data_to_insert)
        print(f"  - `{table}`: restored {len(data_to_insert)} rows")

    my_cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
    my_conn.commit()

    my_cur.close()
    my_conn.close()
    sq_conn.close()

    print(f"\nRestore complete. Successfully inserted {total_inserted} total rows across {len(sqlite_tables)} tables.")
    return True

if __name__ == '__main__':
    restore_from_sqlite()
