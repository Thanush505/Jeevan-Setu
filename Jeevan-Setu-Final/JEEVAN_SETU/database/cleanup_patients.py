"""
database/cleanup_patients.py — Clean test artifacts and enforce exact 10-patient baseline.

Baseline:
- Patients 1 to 10 (UHID-2026-00001 to UHID-2026-00010)
- Assigned beds 400-409 (ICU-01 to ICU-04, HDU-01 to HDU-06) marked as 'occupied'
- Standard hospital beds (ICU-A01..A20, HDU-B01..B20) marked as 'available'
- Removes test wards (ward_id > 2), test beds, test users (user_id > 17), and test patient child records.
"""

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
        
        child_tables = [
            'alerts', 'attendants', 'bed_management', 'chatbot_conversations',
            'clinical_notes', 'decisions', 'ews_scores', 'explanations',
            'notifications', 'patient_qr_tokens', 'recommendations', 'reports',
            'transfers', 'vitals'
        ]
        for tbl in child_tables:
            cursor.execute(f"DELETE FROM {tbl} WHERE patient_id > 10")
            print(f"Cleaned {tbl} (patient_id > 10): {cursor.rowcount} rows removed")
            
        cursor.execute("DELETE FROM notifications WHERE user_id > 17")
        print(f"Cleaned test notifications (user_id > 17): {cursor.rowcount} rows removed")

        cursor.execute("DELETE FROM patients WHERE patient_id > 10")
        print(f"Cleaned test patients (patient_id > 10): {cursor.rowcount} rows removed")

        # Clean test beds & wards
        cursor.execute("DELETE FROM bed_management WHERE ward_id > 2 OR bed_id > 409")
        print(f"Cleaned test bed_management: {cursor.rowcount} rows removed")

        cursor.execute("""
            DELETE FROM beds 
            WHERE ward_id > 2 
               OR bed_id > 409 
               OR bed_number LIKE '%-T-%' 
               OR bed_number LIKE '%-CRIT-%'
               OR bed_number LIKE 'I1-%'
               OR bed_number LIKE 'RB1-%'
               OR bed_number LIKE 'IB1-%'
               OR bed_number LIKE 'HB1-%'
               OR bed_number LIKE 'A1-%'
               OR bed_number LIKE 'B1-%'
               OR bed_number LIKE 'B6-%'
               OR bed_number LIKE 'B-%'
        """)
        print(f"Cleaned test beds: {cursor.rowcount} rows removed")

        cursor.execute("DELETE FROM wards WHERE ward_id > 2")
        print(f"Cleaned test wards: {cursor.rowcount} rows removed")

        cursor.execute("DELETE FROM attendants WHERE user_id > 17")
        cursor.execute("DELETE FROM doctors WHERE user_id > 17")
        cursor.execute("DELETE FROM nurses WHERE user_id > 17")
        cursor.execute("DELETE FROM users WHERE user_id > 17")
        print("Cleaned test users / staff (user_id > 17)")

        # Enforce exact bed occupancy status for baseline patients 1-10
        # Beds 400..409 are ICU-01..04 and HDU-01..06
        cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id BETWEEN 400 AND 409")
        cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id NOT BETWEEN 400 AND 409 AND status = 'occupied'")
        print("Updated bed occupancy: 10 baseline occupied beds, all other beds available.")

        # Ensure all 10 baseline patients are marked 'admitted'
        cursor.execute("UPDATE patients SET status = 'admitted' WHERE patient_id <= 10")
        
        # Reset AUTO_INCREMENT on patients
        cursor.execute("ALTER TABLE patients AUTO_INCREMENT = 11")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("\n=== Database successfully updated to 10-patient baseline! ===")
        
        # Verify counts
        cursor.execute("SELECT COUNT(*) as count FROM patients")
        total_patients = cursor.fetchone()['count']
        print(f"Total Patients: {total_patients}")
        
        cursor.execute("SELECT patient_id, patient_code, name, ward_type, bed_number, status, assigned_doctor, assigned_nurse FROM patients ORDER BY patient_id")
        for r in cursor.fetchall():
            print(f" - [{r['patient_id']}] {r['patient_code']}: {r['name']} | Ward: {r['ward_type']} | Bed: {r['bed_number']} | Status: {r['status']} | Doc: {r['assigned_doctor']} | Nurse: {r['assigned_nurse']}")
            
    except Exception as e:
        conn.rollback()
        print("Error during cleanup:", e)
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    cleanup()
