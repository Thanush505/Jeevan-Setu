import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import get_config

def inspect_ews_scores():
    config = get_config()
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    
    print("--- DESCRIBE ews_scores ---")
    cursor.execute("DESCRIBE ews_scores")
    cols = cursor.fetchall()
    for c in cols:
        print(f"  {c['Field']}: {c['Type']}")

    print("\n--- ALL ews_scores ROWS ---")
    cursor.execute("SELECT * FROM ews_scores ORDER BY ews_id ASC")
    rows = cursor.fetchall()
    for r in rows:
        print(r)

    cursor.close()
    conn.close()

if __name__ == '__main__':
    inspect_ews_scores()
