"""
seed_exact_10_patients.py — Clean and seed exactly 10 realistic hospital patients in Jeevan Setu MySQL DB.
"""

from datetime import datetime, timedelta
from database.db import db
from modules.scoring_engine import calculate_ews, calculate_parameter_score
from services.decision_service import evaluate

def seed_10_patients():
    print("=== STARTING EXACT 10 PATIENTS SEEDING ===")

    # 1. Clean up records for patient_id > 10 in child-to-parent order
    child_tables = [
        'explanations', 'decisions', 'recommendations', 'ews_scores',
        'vitals', 'transfers', 'alerts', 'notifications', 'bed_management',
        'attendants', 'patient_qr_tokens', 'chatbot_conversations', 'reports'
    ]

    for tbl in child_tables:
        try:
            db.execute_query(f"DELETE FROM {tbl} WHERE patient_id > 10")
            print(f"Cleaned {tbl} for patient_id > 10")
        except Exception as e:
            print(f"Warning cleaning {tbl}: {e}")

    try:
        db.execute_query("DELETE FROM patients WHERE patient_id > 10")
        print("Cleaned patients table for patient_id > 10")
    except Exception as e:
        print(f"Warning cleaning patients: {e}")

    # 2. Clean extra beds (keep beds 1 to 18) and extra wards (keep 1, 2, 3)
    try:
        db.execute_query("DELETE FROM beds WHERE bed_id > 18")
        db.execute_query("DELETE FROM wards WHERE ward_id > 3")
        print("Cleaned extra test wards and beds")
    except Exception as e:
        print(f"Warning cleaning extra beds: {e}")

    # Set initial bed statuses
    # Beds 1-6 (ICU-A01 to A06): occupied
    # Beds 7-10 (HDU-B01 to B04): occupied
    # Beds 11-12 (ICU-A07, A08): available
    # Beds 13-14 (HDU-B05, B06): available
    # Beds 15-18 (GEN-C01 to C04): available
    occupied_bed_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    available_bed_ids = [11, 12, 13, 14, 15, 16, 17, 18]

    for b_id in occupied_bed_ids:
        db.execute_query("UPDATE beds SET status='occupied' WHERE bed_id=%s", (b_id,))
    for b_id in available_bed_ids:
        db.execute_query("UPDATE beds SET status='available' WHERE bed_id=%s", (b_id,))

    # 3. Clean records for patient_ids 1-10 to rebuild pristine baseline
    for pid in range(1, 11):
        for tbl in ['explanations', 'decisions', 'recommendations', 'ews_scores', 'vitals', 'bed_management', 'patient_qr_tokens']:
            try:
                db.execute_query(f"DELETE FROM {tbl} WHERE patient_id = %s", (pid,))
            except Exception:
                pass

    # 4. Core 10 Patients Master Data
    patients_data = [
        {
            'patient_id': 1,
            'patient_code': 'UHID-2026-00001',
            'name': 'Rajesh Kumar',
            'age': 45,
            'gender': 'Male',
            'blood_group': 'B+',
            'contact_number': '+91 98765 43210',
            'emergency_contact': '+91 98765 43211',
            'ward_id': 1,
            'ward_type': 'ICU',
            'bed_id': 1,
            'bed_number': 'ICU-A01',
            'diagnosis': 'Acute Respiratory Distress Syndrome (ARDS) & Sepsis',
            'assigned_doctor': 2,  # Dr. Anil Sharma
            'assigned_nurse': 5,   # Priya Menon
            'admission_days_ago': 4,
            'vitals_history': [
                {'hr': 128, 'sbp': 85, 'rr': 28, 'temp': 39.2, 'hours_ago': 1},
                {'hr': 122, 'sbp': 88, 'rr': 26, 'temp': 38.9, 'hours_ago': 4},
                {'hr': 118, 'sbp': 92, 'rr': 24, 'temp': 38.6, 'hours_ago': 8}
            ]
        },
        {
            'patient_id': 2,
            'patient_code': 'UHID-2026-00002',
            'name': 'Anita Devi',
            'age': 62,
            'gender': 'Female',
            'blood_group': 'O+',
            'contact_number': '+91 98765 43212',
            'emergency_contact': '+91 98765 43213',
            'ward_id': 1,
            'ward_type': 'ICU',
            'bed_id': 2,
            'bed_number': 'ICU-A02',
            'diagnosis': 'Post-Operative Coronary Artery Bypass Graft (CABG)',
            'assigned_doctor': 2,  # Dr. Anil Sharma
            'assigned_nurse': 5,   # Priya Menon
            'admission_days_ago': 3,
            'vitals_history': [
                {'hr': 98, 'sbp': 135, 'rr': 18, 'temp': 37.1, 'hours_ago': 1},
                {'hr': 95, 'sbp': 130, 'rr': 17, 'temp': 37.0, 'hours_ago': 5},
                {'hr': 102, 'sbp': 128, 'rr': 19, 'temp': 37.2, 'hours_ago': 10}
            ]
        },
        {
            'patient_id': 3,
            'patient_code': 'UHID-2026-00003',
            'name': 'Vikram Singh',
            'age': 38,
            'gender': 'Male',
            'blood_group': 'A+',
            'contact_number': '+91 98765 43214',
            'emergency_contact': '+91 98765 43215',
            'ward_id': 1,
            'ward_type': 'ICU',
            'bed_id': 3,
            'bed_number': 'ICU-A03',
            'diagnosis': 'Severe Polytrauma & Traumatic Brain Injury (TBI)',
            'assigned_doctor': 2,  # Dr. Anil Sharma
            'assigned_nurse': 5,   # Priya Menon
            'admission_days_ago': 5,
            'vitals_history': [
                {'hr': 114, 'sbp': 95, 'rr': 22, 'temp': 38.4, 'hours_ago': 2},
                {'hr': 110, 'sbp': 98, 'rr': 21, 'temp': 38.2, 'hours_ago': 6},
                {'hr': 116, 'sbp': 92, 'rr': 23, 'temp': 38.5, 'hours_ago': 12}
            ]
        },
        {
            'patient_id': 4,
            'patient_code': 'UHID-2026-00004',
            'name': 'Sunita Rao',
            'age': 51,
            'gender': 'Female',
            'blood_group': 'AB+',
            'contact_number': '+91 98765 43216',
            'emergency_contact': '+91 98765 43217',
            'ward_id': 1,
            'ward_type': 'ICU',
            'bed_id': 4,
            'bed_number': 'ICU-A04',
            'diagnosis': 'Acute Kidney Injury (AKI) & Metabolic Acidosis',
            'assigned_doctor': 3,  # Dr. Kavita Patel
            'assigned_nurse': 6,   # Arun Krishnan
            'admission_days_ago': 2,
            'vitals_history': [
                {'hr': 102, 'sbp': 155, 'rr': 21, 'temp': 37.4, 'hours_ago': 1},
                {'hr': 98, 'sbp': 150, 'rr': 20, 'temp': 37.3, 'hours_ago': 5},
                {'hr': 105, 'sbp': 160, 'rr': 22, 'temp': 37.5, 'hours_ago': 9}
            ]
        },
        {
            'patient_id': 5,
            'patient_code': 'UHID-2026-00005',
            'name': 'Mohammed Ali',
            'age': 40,
            'gender': 'Male',
            'blood_group': 'O-',
            'contact_number': '+91 98765 43218',
            'emergency_contact': '+91 98765 43219',
            'ward_id': 1,
            'ward_type': 'ICU',
            'bed_id': 5,
            'bed_number': 'ICU-A05',
            'diagnosis': 'Severe Acute Pancreatitis',
            'assigned_doctor': 3,  # Dr. Kavita Patel
            'assigned_nurse': 6,   # Arun Krishnan
            'admission_days_ago': 6,
            'vitals_history': [
                {'hr': 88, 'sbp': 122, 'rr': 16, 'temp': 36.8, 'hours_ago': 2},
                {'hr': 85, 'sbp': 120, 'rr': 15, 'temp': 36.7, 'hours_ago': 6},
                {'hr': 90, 'sbp': 125, 'rr': 17, 'temp': 36.9, 'hours_ago': 12}
            ]
        },
        {
            'patient_id': 6,
            'patient_code': 'UHID-2026-00006',
            'name': 'Priya Nair',
            'age': 33,
            'gender': 'Female',
            'blood_group': 'B-',
            'contact_number': '+91 98765 43220',
            'emergency_contact': '+91 98765 43221',
            'ward_id': 1,
            'ward_type': 'ICU',
            'bed_id': 6,
            'bed_number': 'ICU-A06',
            'diagnosis': 'Post-Partum Hemorrhage (PPH) & Hypovolemic Shock',
            'assigned_doctor': 3,  # Dr. Kavita Patel
            'assigned_nurse': 6,   # Arun Krishnan
            'admission_days_ago': 2,
            'vitals_history': [
                {'hr': 118, 'sbp': 88, 'rr': 23, 'temp': 36.2, 'hours_ago': 1},
                {'hr': 122, 'sbp': 85, 'rr': 24, 'temp': 36.1, 'hours_ago': 4},
                {'hr': 115, 'sbp': 90, 'rr': 22, 'temp': 36.4, 'hours_ago': 8}
            ]
        },
        {
            'patient_id': 7,
            'patient_code': 'UHID-2026-00007',
            'name': 'Amit Verma',
            'age': 55,
            'gender': 'Male',
            'blood_group': 'A-',
            'contact_number': '+91 98765 43222',
            'emergency_contact': '+91 98765 43223',
            'ward_id': 2,
            'ward_type': 'HDU',
            'bed_id': 7,
            'bed_number': 'HDU-B01',
            'diagnosis': 'Decompensated Heart Failure (NYHA Class IV)',
            'assigned_doctor': 4,  # Dr. Rajiv Gupta
            'assigned_nurse': 7,   # Meera Jain
            'admission_days_ago': 4,
            'vitals_history': [
                {'hr': 92, 'sbp': 148, 'rr': 20, 'temp': 36.9, 'hours_ago': 2},
                {'hr': 88, 'sbp': 145, 'rr': 19, 'temp': 36.8, 'hours_ago': 6},
                {'hr': 94, 'sbp': 150, 'rr': 21, 'temp': 37.0, 'hours_ago': 10}
            ]
        },
        {
            'patient_id': 8,
            'patient_code': 'UHID-2026-00008',
            'name': 'Lakshmi Iyer',
            'age': 29,
            'gender': 'Female',
            'blood_group': 'AB-',
            'contact_number': '+91 98765 43224',
            'emergency_contact': '+91 98765 43225',
            'ward_id': 2,
            'ward_type': 'HDU',
            'bed_id': 8,
            'bed_number': 'HDU-B02',
            'diagnosis': 'Diabetic Ketoacidosis (DKA) - Resolving Phase',
            'assigned_doctor': 4,  # Dr. Rajiv Gupta
            'assigned_nurse': 7,   # Meera Jain
            'admission_days_ago': 3,
            'vitals_history': [
                {'hr': 82, 'sbp': 118, 'rr': 15, 'temp': 36.6, 'hours_ago': 1},
                {'hr': 80, 'sbp': 115, 'rr': 15, 'temp': 36.5, 'hours_ago': 5},
                {'hr': 84, 'sbp': 120, 'rr': 16, 'temp': 36.7, 'hours_ago': 9}
            ]
        },
        {
            'patient_id': 9,
            'patient_code': 'UHID-2026-00009',
            'name': 'Deepak Joshi',
            'age': 47,
            'gender': 'Male',
            'blood_group': 'B+',
            'contact_number': '+91 98765 43226',
            'emergency_contact': '+91 98765 43227',
            'ward_id': 2,
            'ward_type': 'HDU',
            'bed_id': 9,
            'bed_number': 'HDU-B03',
            'diagnosis': 'Community Acquired Pneumonia (CAP) & COPD Exacerbation',
            'assigned_doctor': 4,  # Dr. Rajiv Gupta
            'assigned_nurse': 7,   # Meera Jain
            'admission_days_ago': 5,
            'vitals_history': [
                {'hr': 104, 'sbp': 112, 'rr': 22, 'temp': 38.3, 'hours_ago': 2},
                {'hr': 100, 'sbp': 110, 'rr': 21, 'temp': 38.1, 'hours_ago': 6},
                {'hr': 108, 'sbp': 115, 'rr': 23, 'temp': 38.4, 'hours_ago': 11}
            ]
        },
        {
            'patient_id': 10,
            'patient_code': 'UHID-2026-00010',
            'name': 'Fatima Begum',
            'age': 65,
            'gender': 'Female',
            'blood_group': 'O+',
            'contact_number': '+91 98765 43228',
            'emergency_contact': '+91 98765 43229',
            'ward_id': 2,
            'ward_type': 'HDU',
            'bed_id': 10,
            'bed_number': 'HDU-B04',
            'diagnosis': 'Acute Ischemic Stroke (Subacute Recovery Phase)',
            'assigned_doctor': 4,  # Dr. Rajiv Gupta
            'assigned_nurse': 7,   # Meera Jain
            'admission_days_ago': 7,
            'vitals_history': [
                {'hr': 76, 'sbp': 138, 'rr': 14, 'temp': 36.7, 'hours_ago': 1},
                {'hr': 74, 'sbp': 135, 'rr': 14, 'temp': 36.6, 'hours_ago': 5},
                {'hr': 78, 'sbp': 140, 'rr': 15, 'temp': 36.8, 'hours_ago': 10}
            ]
        }
    ]

    now = datetime.now()

    for p in patients_data:
        adm_date = now - timedelta(days=p['admission_days_ago'])
        
        # 1. Insert/Update Patient Record
        db.execute_query(
            """INSERT INTO patients (patient_id, patient_code, name, age, gender, blood_group,
                                    contact_number, emergency_contact, ward_id, ward_type,
                                    bed_id, bed_number, diagnosis, status, assigned_doctor,
                                    assigned_nurse, admission_date, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'admitted', %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                    patient_code=%s, name=%s, age=%s, gender=%s, blood_group=%s,
                    contact_number=%s, emergency_contact=%s, ward_id=%s, ward_type=%s,
                    bed_id=%s, bed_number=%s, diagnosis=%s, status='admitted',
                    assigned_doctor=%s, assigned_nurse=%s, admission_date=%s, updated_at=%s""",
            (
                p['patient_id'], p['patient_code'], p['name'], p['age'], p['gender'], p['blood_group'],
                p['contact_number'], p['emergency_contact'], p['ward_id'], p['ward_type'],
                p['bed_id'], p['bed_number'], p['diagnosis'], p['assigned_doctor'],
                p['assigned_nurse'], adm_date, adm_date, now,
                p['patient_code'], p['name'], p['age'], p['gender'], p['blood_group'],
                p['contact_number'], p['emergency_contact'], p['ward_id'], p['ward_type'],
                p['bed_id'], p['bed_number'], p['diagnosis'], p['assigned_doctor'],
                p['assigned_nurse'], adm_date, now
            )
        )

        # 2. Insert Bed Management Allocation
        db.execute_query(
            """INSERT INTO bed_management (patient_id, bed_id, ward_id, allocated_at, status, allocated_by, notes)
               VALUES (%s, %s, %s, %s, 'occupied', 1, 'Initial patient ward bed allocation')""",
            (p['patient_id'], p['bed_id'], p['ward_id'], adm_date)
        )

        # 3. Insert Vitals History & EWS Scores
        latest_vital_id = None
        latest_ews_score = 0
        latest_risk_lvl = 'normal'

        for v in reversed(p['vitals_history']):
            v_time = now - timedelta(hours=v['hours_ago'])
            
            # Compute EWS points
            v_dict = {'heart_rate': v['hr'], 'blood_pressure_sys': v['sbp'], 'respiratory_rate': v['rr'], 'temperature': v['temp']}
            ews_res = calculate_ews(v_dict)
            tot_ews = ews_res['total_score']
            risk = ews_res['risk_level']

            v_id = db.execute_query(
                """INSERT INTO vitals (patient_id, heart_rate, blood_pressure_sys, blood_pressure_dia,
                                      respiratory_rate, temperature, spo2, ews_score, recorded_by, recorded_at)
                   VALUES (%s, %s, %s, 80, %s, %s, 98, %s, %s, %s)""",
                (p['patient_id'], v['hr'], v['sbp'], v['rr'], v['temp'], tot_ews, p['assigned_nurse'], v_time)
            )

            # Insert ews_scores entry
            hr_s = calculate_parameter_score('heart_rate', v['hr'])
            bp_s = calculate_parameter_score('blood_pressure_sys', v['sbp'])
            rr_s = calculate_parameter_score('respiratory_rate', v['rr'])
            temp_s = calculate_parameter_score('temperature', v['temp'])

            risk_db = 'LOW' if risk.upper() in ('NORMAL', 'LOW') else risk.upper()

            db.execute_query(
                """INSERT INTO ews_scores (patient_id, vital_id, total_score, risk_level,
                                          hr_score, bp_score, rr_score, temp_score, calculated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (p['patient_id'], v_id, tot_ews, risk_db, hr_s, bp_s, rr_s, temp_s, v_time)
            )

            latest_vital_id = v_id
            latest_ews_score = tot_ews
            latest_risk_lvl = risk

        # 4. Insert Decisions and Recommendations
        dec = evaluate(latest_ews_score)
        db.execute_query(
            """INSERT INTO decisions (patient_id, vital_id, from_ward, to_ward, ews_score,
                                     confidence, recommendation, status, decided_by, decided_at, created_at)
               VALUES (%s, %s, %s, %s, %s, 0.95, %s, 'pending', %s, %s, %s)""",
            (p['patient_id'], latest_vital_id, p['ward_type'],
             'HDU' if p['ward_type'] == 'ICU' and dec['condition'] == 'Stable' else ('ICU' if latest_ews_score >= 5 else p['ward_type']),
             latest_ews_score, dec['recommendation'], p['assigned_doctor'], now, now)
        )

        db.execute_query(
            """INSERT INTO recommendations (patient_id, vital_id, from_ward, to_ward, score,
                                           confidence, recommendation_text, reason, status, decided_by, decided_at, created_at)
               VALUES (%s, %s, %s, %s, %s, 0.95, %s, %s, 'pending', %s, %s, %s)""",
            (p['patient_id'], latest_vital_id, p['ward_type'],
             'HDU' if p['ward_type'] == 'ICU' and dec['condition'] == 'Stable' else p['ward_type'],
             latest_ews_score, dec['recommendation'],
             f"Condition evaluated as {dec['condition']} based on EWS total score {latest_ews_score}.",
             p['assigned_doctor'], now, now)
        )

        # 5. Insert QR Token
        db.execute_query(
            """INSERT INTO patient_qr_tokens (patient_id, token_hash, access_code, qr_code_data, valid_from, expires_at, is_active, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, 1, 1)""",
            (p['patient_id'], f"token_hash_{p['patient_id']}", f"ACC{p['patient_id']:04d}",
             f"https://jeevansetu.org/qr/{p['patient_code']}", adm_date, now + timedelta(days=30))
        )

    # 6. Insert clean sample transfer records for Patient 2 (Stable CABG)
    db.execute_query("DELETE FROM transfers WHERE patient_id > 10")
    
    print("=== SEEDING COMPLETED SUCCESSFULLY ===")
    total_pts = db.execute_query("SELECT COUNT(*) as cnt FROM patients", fetch=True)[0]['cnt']
    print(f"Total Patients in MySQL: {total_pts}")

if __name__ == '__main__':
    seed_10_patients()
