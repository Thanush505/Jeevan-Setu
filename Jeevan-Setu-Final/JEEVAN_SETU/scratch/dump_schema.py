"""
scratch/dump_schema.py — Scan live MySQL database and extract complete structure & data.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import db


def scan_database():
    tables_res = db.execute_query("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'", fetch=True)
    table_names = [list(t.values())[0] for t in tables_res]
    print(f"=== Scanning Database ({len(table_names)} tables) ===")

    for t in sorted(table_names):
        cnt = db.execute_query(f"SELECT COUNT(*) as cnt FROM `{t}`", fetch=True)[0]['cnt']
        create_res = db.execute_query(f"SHOW CREATE TABLE `{t}`", fetch=True)
        create_sql = create_res[0]['Create Table']
        print(f"\n--- TABLE: {t} (Rows: {cnt}) ---")
        print(create_sql)


if __name__ == '__main__':
    scan_database()
