"""
scratch/clean_db.py — Safely clean all extra patient, test user, and orphan records,
enforcing exactly the approved 10-patient dataset.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import db


def clean_database():
    print("=== Starting Database Cleanup to strictly 10 Patients ===")

    with db.transaction() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        # 1. Clean child tables referencing patient_id
        child_tables = [
            'alerts', 'attendants', 'bed_management', 'chatbot_conversations',
            'decisions', 'ews_scores', 'explanations', 'notifications',
            'patient_qr_tokens', 'recommendations', 'reports', 'transfers', 'vitals'
        ]
        for table in child_tables:
            cursor.execute(f"DELETE FROM {table} WHERE patient_id > 10 OR patient_id NOT IN (1,2,3,4,5,6,7,8,9,10)")
            print(f"Cleaned {table}: {cursor.rowcount} rows removed")

        # 2. Patients table
        cursor.execute("DELETE FROM patients WHERE patient_id > 10 OR patient_id NOT IN (1,2,3,4,5,6,7,8,9,10)")
        print(f"Cleaned patients: {cursor.rowcount} extra rows removed")

        # 3. Clean test users (> 17) and their relations
        cursor.execute("DELETE FROM doctors WHERE user_id > 17")
        cursor.execute("DELETE FROM nurses WHERE user_id > 17")
        cursor.execute("DELETE FROM attendants WHERE user_id > 17")
        cursor.execute("DELETE FROM audit_logs WHERE user_id > 17")
        cursor.execute("DELETE FROM notifications WHERE user_id > 17")
        cursor.execute("DELETE FROM reports WHERE generated_by > 17")
        cursor.execute("DELETE FROM transfers WHERE requested_by > 17 OR approved_by > 17")
        cursor.execute("DELETE FROM decisions WHERE decided_by > 17")
        cursor.execute("DELETE FROM bed_management WHERE allocated_by > 17")
        cursor.execute("DELETE FROM users WHERE user_id > 17")
        print(f"Cleaned extra test users: {cursor.rowcount} users removed")

        # 4. Clean extra test beds and wards
        cursor.execute("DELETE FROM bed_management WHERE bed_id > 10")
        cursor.execute("DELETE FROM beds WHERE bed_id > 10")
        cursor.execute("DELETE FROM wards WHERE ward_id > 2")
        print("Cleaned extra test beds and wards")

        # 5. Ensure all 10 beds 1..10 are assigned to wards 1 and 2 and marked occupied
        cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id BETWEEN 1 AND 10")

        # 6. Re-enable FK checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    print("\n=== Verification ===")
    patients = db.execute_query("SELECT patient_id, name, ward_type, bed_number, status, assigned_doctor, assigned_nurse FROM patients ORDER BY patient_id ASC", fetch=True)
    print(f"Total Patients: {len(patients)}")
    for p in patients:
        print(f"  [{p['patient_id']}] {p['name']} | Ward: {p['ward_type']} | Bed: {p['bed_number']} | Doc: {p['assigned_doctor']} | Nurse: {p['assigned_nurse']} | Status: {p['status']}")

    users = db.execute_query("SELECT user_id, username, full_name, role FROM users ORDER BY user_id ASC", fetch=True)
    print(f"\nTotal Users: {len(users)}")
    for u in users:
        print(f"  [{u['user_id']}] {u['username']} ({u['role']}) - {u['full_name']}")


if __name__ == '__main__':
    clean_database()
