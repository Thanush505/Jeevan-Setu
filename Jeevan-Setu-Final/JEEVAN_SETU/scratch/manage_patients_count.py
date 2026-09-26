import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import db

def inspect_db():
    print("--- DESCRIBE patients ---")
    cols = db.execute_query('DESCRIBE patients', fetch=True)
    for c in cols:
        print(f"  {c['Field']}: {c['Type']}")

    patients = db.execute_query('SELECT * FROM patients ORDER BY patient_id ASC', fetch=True)
    print(f"\nTotal patients count: {len(patients)}")
    for p in patients:
        print(p)

    tables = db.execute_query("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME = 'patient_id'
    """, fetch=True)
    print("\nTables with patient_id:")
    for t in tables:
        print(f" - {t['TABLE_NAME']}.{t['COLUMN_NAME']}")

if __name__ == '__main__':
    inspect_db()
