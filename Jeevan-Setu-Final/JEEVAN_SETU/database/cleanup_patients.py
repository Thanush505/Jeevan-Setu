import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import get_config

def cleanup():
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
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        tables = [
            'alerts', 'attendants', 'bed_management', 'chatbot_conversations',
            'decisions', 'ews_scores', 'explanations', 'notifications',
            'patient_qr_tokens', 'recommendations', 'reports', 'transfers', 'vitals'
        ]
        for tbl in tables:
            cursor.execute(f"DELETE FROM {tbl} WHERE patient_id > 10")
            print(f"Deleted from {tbl} where patient_id > 10: {cursor.rowcount} rows")
            
        cursor.execute("DELETE FROM notifications WHERE user_id > 17")
        print(f"Deleted test notifications: {cursor.rowcount} rows")

        cursor.execute("DELETE FROM patients WHERE patient_id > 10")
        print(f"Deleted from patients where patient_id > 10: {cursor.rowcount} rows")
        
        cursor.execute("DELETE FROM bed_management WHERE bed_id > 114 OR ward_id > 2")
        cursor.execute("DELETE FROM beds WHERE ward_id > 2 OR bed_id > 114")
        print(f"Deleted test beds: {cursor.rowcount} rows")
        cursor.execute("DELETE FROM wards WHERE ward_id > 2")
        print(f"Deleted test wards: {cursor.rowcount} rows")

        cursor.execute("DELETE FROM doctors WHERE user_id > 17")
        cursor.execute("DELETE FROM nurses WHERE user_id > 17")
        cursor.execute("DELETE FROM users WHERE user_id > 17")
        print("Cleaned test users/doctors/nurses.")

        cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id IN (1, 2, 3, 4, 5, 6)")
        cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id IN (85, 86, 87, 88, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104)")
        cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id IN (7, 8, 9, 10)")
        cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id IN (89, 90, 91, 92, 93, 94, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114)")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("=== Database cleanup committed successfully! ===")
        
        # Verify counts
        cursor.execute("SELECT COUNT(*) as count FROM patients")
        print(f"Final Patient Count: {cursor.fetchone()['count']}")
        cursor.execute("SELECT patient_id, patient_code, name, ward_type, bed_number FROM patients ORDER BY patient_id")
        for r in cursor.fetchall():
            print(f" - [{r['patient_id']}] {r['patient_code']}: {r['name']} ({r['ward_type']}, {r['bed_number']})")
            
    except Exception as e:
        conn.rollback()
        print("Error during cleanup:", e)
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    cleanup()
