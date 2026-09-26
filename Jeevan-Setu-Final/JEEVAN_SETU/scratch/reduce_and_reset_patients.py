"""
scratch/reduce_and_reset_patients.py
Reduces database to exactly 10 patients and sets their EWS score to 0 across the entire database.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from datetime import datetime
from config import get_config

def execute_reduction_and_reset():
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
        print("=== STEP 1: Removing records for patients with ID > 10 ===")
        
        tables = [
            'alerts', 'attendants', 'bed_management', 'chatbot_conversations',
            'decisions', 'ews_scores', 'explanations', 'notifications',
            'patient_qr_tokens', 'recommendations', 'reports', 'transfers', 'vitals'
        ]
        for tbl in tables:
            cursor.execute(f"DELETE FROM {tbl} WHERE patient_id > 10")
            print(f" - Deleted from {tbl} (patient_id > 10): {cursor.rowcount} rows")

        cursor.execute("DELETE FROM patients WHERE patient_id > 10")
        print(f" - Deleted from patients (patient_id > 10): {cursor.rowcount} rows")

        print("\n=== STEP 2: Cleaning test beds, wards, and users from test runs ===")
        cursor.execute("DELETE FROM bed_management WHERE bed_id > 114 OR ward_id > 2")
        cursor.execute("DELETE FROM beds WHERE ward_id > 2 OR bed_id > 114")
        cursor.execute("DELETE FROM wards WHERE ward_id > 2")
        cursor.execute("DELETE FROM notifications WHERE user_id > 17")
        cursor.execute("DELETE FROM doctors WHERE user_id > 17")
        cursor.execute("DELETE FROM nurses WHERE user_id > 17")
        cursor.execute("DELETE FROM users WHERE user_id > 17")
        print(" - Cleaned extra test beds, wards, and test users.")

        print("\n=== STEP 3: Resetting EWS Score to 0 for all 10 remaining patients ===")
        # 1. Clean previous vitals and ews_scores for the 10 patients
        cursor.execute("DELETE FROM vitals WHERE patient_id <= 10")
        cursor.execute("DELETE FROM ews_scores WHERE patient_id <= 10")
        cursor.execute("DELETE FROM alerts WHERE patient_id <= 10")
        cursor.execute("DELETE FROM recommendations WHERE patient_id <= 10")
        cursor.execute("DELETE FROM decisions WHERE patient_id <= 10")
        cursor.execute("DELETE FROM transfers WHERE patient_id <= 10")

        # Standard patient definitions (1-6 ICU, 7-10 HDU)
        patient_meta = [
            # ID, Name, Age, Gender, BloodGroup, WardType, BedNum, WardId, BedId, DoctorId, NurseId, Diagnosis
            (1, 'Rajesh Kumar', 58, 'Male', 'O+', 'ICU', 'ICU-A01', 1, 1, 2, 5, 'Post-Op Coronary Artery Bypass'),
            (2, 'Anita Devi', 64, 'Female', 'A+', 'ICU', 'ICU-A02', 1, 2, 2, 5, 'Acute Exacerbation of COPD'),
            (3, 'Vikram Singh', 45, 'Male', 'B+', 'ICU', 'ICU-A03', 1, 3, 3, 6, 'Community Acquired Pneumonia'),
            (4, 'Sunita Rao', 52, 'Female', 'AB+', 'ICU', 'ICU-A04', 1, 4, 3, 6, 'Septicemia Secondary to UTI'),
            (5, 'Mohammed Ali', 71, 'Male', 'O-', 'ICU', 'ICU-A05', 1, 5, 4, 7, 'Acute Ischemic Stroke'),
            (6, 'Priya Nair', 39, 'Female', 'B-', 'ICU', 'ICU-A06', 1, 6, 4, 7, 'Post-Polytrauma Stabilization'),
            (7, 'Amit Verma', 61, 'Male', 'A-', 'HDU', 'HDU-B01', 2, 7, 2, 5, 'Step-Down Post-Stenting Recovery'),
            (8, 'Lakshmi Iyer', 48, 'Female', 'O+', 'HDU', 'HDU-B02', 2, 8, 3, 6, 'Subacute Respiratory Failure'),
            (9, 'Deepak Joshi', 55, 'Male', 'B+', 'HDU', 'HDU-B03', 2, 9, 4, 7, 'Elective Aortic Valve Replacement'),
            (10, 'Fatima Begum', 67, 'Female', 'A+', 'HDU', 'HDU-B04', 2, 10, 2, 5, 'Resolved Sepsis Step-Down')
        ]

        now = datetime.now()

        for p_id, name, age, gender, bg, ward, bed_num, w_id, b_id, doc_id, nurse_id, diag in patient_meta:
            # Update patient record
            cursor.execute("""
                UPDATE patients 
                SET name = %s, age = %s, gender = %s, blood_group = %s,
                    ward_type = %s, bed_number = %s, ward_id = %s, bed_id = %s,
                    assigned_doctor = %s, assigned_nurse = %s, diagnosis = %s,
                    status = 'admitted', admission_date = %s, discharge_date = NULL,
                    updated_at = %s
                WHERE patient_id = %s
            """, (name, age, gender, bg, ward, bed_num, w_id, b_id, doc_id, nurse_id, diag, now, now, p_id))

            # Insert baseline vitals giving strictly EWS = 0:
            # HR: 72 (51-90 -> 0), BP Sys: 120 (101-199 -> 0), RR: 16 (12-20 -> 0), Temp: 36.8 (36.1-38.0 -> 0)
            cursor.execute("""
                INSERT INTO vitals (
                    patient_id, heart_rate, blood_pressure_sys,
                    respiratory_rate, temperature, ews_score,
                    recorded_by, recorded_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (p_id, 72.0, 120.0, 16.0, 36.8, 0, nurse_id, now))
            vital_id = cursor.lastrowid

            # Insert EWS Score record with score 0
            cursor.execute("""
                INSERT INTO ews_scores (
                    patient_id, patient_name, vital_id, rr_score, hr_score, bp_score,
                    temp_score, total_score, risk_level, calculated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (p_id, name, vital_id, 0, 0, 0, 0, 0, 'LOW', now))

            # Insert Recommendation with Stable status
            cursor.execute("""
                INSERT INTO recommendations (
                    patient_id, recommendation_text, score, status,
                    from_ward, to_ward, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (p_id, 'Fit for HDU Transfer', 0, 'pending', ward, 'HDU' if ward == 'ICU' else 'General', now))

        print(" - Successfully inserted EWS=0 vitals, EWS score records, and recommendations for all 10 patients.")

        # Update bed occupancy
        cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id BETWEEN 1 AND 10")
        cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id > 10")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("\n=== Database transaction committed successfully! ===")

        # Verification query
        cursor.execute("SELECT COUNT(*) as total_patients FROM patients")
        tot = cursor.fetchone()['total_patients']
        print(f"\nFinal Total Patients in Database: {tot}")

        cursor.execute("""
            SELECT p.patient_id, p.patient_code, p.name, p.ward_type, p.bed_number, 
                   v.heart_rate, v.blood_pressure_sys, v.respiratory_rate, v.temperature,
                   v.ews_score as vital_ews, e.total_score as ews_total, e.risk_level
            FROM patients p
            LEFT JOIN vitals v ON p.patient_id = v.patient_id
            LEFT JOIN ews_scores e ON p.patient_id = e.patient_id
            ORDER BY p.patient_id ASC
        """)
        rows = cursor.fetchall()
        print("\nVerified Patient Roster & EWS Scores (All 10 Patients):")
        for r in rows:
            print(f" - [{r['patient_id']}] {r['patient_code']} | {r['name']} | Ward: {r['ward_type']} | Bed: {r['bed_number']} | EWS: {r['ews_total']} (Risk: {r['risk_level']}) | Vitals: HR={r['heart_rate']}, SBP={r['blood_pressure_sys']}, RR={r['respiratory_rate']}, Temp={r['temperature']}")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Transaction failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    execute_reduction_and_reset()
