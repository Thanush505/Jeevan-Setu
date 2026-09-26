import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import get_config

def get_top10():
    config = get_config()
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT patient_id, patient_code, name, ward_type, bed_number, status FROM patients ORDER BY patient_id ASC LIMIT 15")
    rows = cursor.fetchall()
    print("Lowest patient rows:")
    for r in rows:
        print(r)
    cursor.close()
    conn.close()

if __name__ == '__main__':
    get_top10()
