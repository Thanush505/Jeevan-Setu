"""
scratch/fill_patient_names_ews_scores.py
Populates patient_name in ews_scores table from patients table where it is NULL.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import get_config

def fill_patient_names():
    config = get_config()
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)

    try:
        # Update patient_name by joining with patients table
        cursor.execute("""
            UPDATE ews_scores e
            JOIN patients p ON e.patient_id = p.patient_id
            SET e.patient_name = p.name
            WHERE e.patient_name IS NULL OR e.patient_name = ''
        """)
        updated_count = cursor.rowcount
        conn.commit()
        print(f"[OK] Updated {updated_count} rows in ews_scores with patient names.")

        # Verify all rows in ews_scores
        cursor.execute("SELECT ews_id, patient_id, patient_name, total_score, risk_level, calculated_at FROM ews_scores ORDER BY ews_id ASC")
        rows = cursor.fetchall()
        print("\nVerified ews_scores rows:")
        for r in rows:
            print(f" - EWS ID: {r['ews_id']} | Patient ID: {r['patient_id']} | Patient Name: '{r['patient_name']}' | Total Score: {r['total_score']} | Risk: {r['risk_level']}")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to update ews_scores: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    fill_patient_names()
