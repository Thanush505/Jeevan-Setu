"""
scratch/generate_schema_sql.py — Scan live MySQL database and generate comprehensive, updated schema.sql.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import db


def generate():
    print("=== Scanning MySQL Database to produce updated schema.sql ===")

    # List of all tables in dependency order
    ordered_tables = [
        'roles',
        'users',
        'doctors',
        'nurses',
        'wards',
        'beds',
        'patients',
        'attendants',
        'bed_management',
        'vitals',
        'ews_scores',
        'decisions',
        'recommendations',
        'explanations',
        'transfers',
        'reports',
        'alerts',
        'notifications',
        'patient_qr_tokens',
        'chatbot_conversations',
        'token_blacklist',
        'audit_logs',
        'schema_migrations'
    ]

    schema_parts = [
        "-- =============================================================",
        "-- JEEVAN SETU — Complete Authoritative Database Schema",
        "-- Smart ICU/HDU Patient Monitoring & Clinical Decision Support",
        "-- Auto-synchronized with live MySQL Database",
        "-- =============================================================",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
        ""
    ]

    # DDL generation
    for idx, t in enumerate(ordered_tables, 1):
        res = db.execute_query(f"SHOW CREATE TABLE `{t}`", fetch=True)
        if not res:
            continue
        create_sql = res[0]['Create Table']
        # Convert CREATE TABLE `table` to CREATE TABLE IF NOT EXISTS `table`
        if "CREATE TABLE IF NOT EXISTS" not in create_sql:
            create_sql = create_sql.replace(f"CREATE TABLE `{t}`", f"CREATE TABLE IF NOT EXISTS `{t}`", 1)
        schema_parts.append(f"-- {idx}. Table: {t}")
        schema_parts.append(create_sql + ";")
        schema_parts.append("")

    # Seed data section
    schema_parts.extend([
        "-- =============================================================",
        "-- SEED DATA — Realistic Hospital Dataset for Jeevan Setu",
        "-- 10 Admitted Patients, 3 Doctors, 3 Nurses, 1 Admin, 10 Attendants",
        "-- 2 Wards (ICU-A, HDU-B, 20 Beds each), Live Beds & Allocations",
        "-- =============================================================",
        "",
        "-- 1. Roles",
        "INSERT INTO roles (role_id, name, display_name, description) VALUES",
        "  (1, 'admin', 'Administrator', 'Full system access'),",
        "  (2, 'doctor', 'Doctor', 'Clinical decision-making and patient care'),",
        "  (3, 'nurse', 'Nurse', 'Vital signs recording and patient monitoring'),",
        "  (4, 'attendant', 'Patient Attendant', 'Read-only patient status access')",
        "ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), description = VALUES(description);",
        "",
        "-- 2. Users (1 Admin + 3 Doctors + 3 Nurses + 10 Attendants)",
        "INSERT INTO users (user_id, username, password_hash, full_name, email, role_id, role, department, is_active) VALUES",
        "  (1,  'admin_js',     'Admin@123',     'System Administrator', 'admin@jeevansetu.in',         1, 'admin',     'Administration', 1),",
        "  (2,  'dr_sharma',    'Doctor@123',    'Dr. Anil Sharma',      'anil.sharma@jeevansetu.in',   2, 'doctor',    'Cardiology',     1),",
        "  (3,  'dr_patel',     'Doctor@123',    'Dr. Kavita Patel',     'kavita.patel@jeevansetu.in',  2, 'doctor',    'Pulmonology',    1),",
        "  (4,  'dr_gupta',     'Doctor@123',    'Dr. Rajiv Gupta',      'rajiv.gupta@jeevansetu.in',   2, 'doctor',    'Neurology',      1),",
        "  (5,  'nurse_priya',  'Nurse@123',     'Priya Menon',          'priya.menon@jeevansetu.in',   3, 'nurse',     'ICU',            1),",
        "  (6,  'nurse_arun',   'Nurse@123',     'Arun Krishnan',        'arun.krishnan@jeevansetu.in', 3, 'nurse',     'HDU',            1),",
        "  (7,  'nurse_meera',  'Nurse@123',     'Meera Jain',           'meera.jain@jeevansetu.in',    3, 'nurse',     'ICU',            1),",
        "  (8,  'att_rajesh',   'Attendant@123', 'Suman Kumar',          'suman.kumar@email.com',       4, 'attendant', NULL,             1),",
        "  (9,  'att_anita',    'Attendant@123', 'Ramesh Devi',          'ramesh.devi@email.com',       4, 'attendant', NULL,             1),",
        "  (10, 'att_vikram',   'Attendant@123', 'Geeta Singh',          'geeta.singh@email.com',       4, 'attendant', NULL,             1),",
        "  (11, 'att_sunita',   'Attendant@123', 'Prakash Rao',          'prakash.rao@email.com',       4, 'attendant', NULL,             1),",
        "  (12, 'att_mohammed', 'Attendant@123', 'Fatima Ali',           'fatima.ali@email.com',        4, 'attendant', NULL,             1),",
        "  (13, 'att_priya_n',  'Attendant@123', 'Suresh Nair',          'suresh.nair@email.com',       4, 'attendant', NULL,             1),",
        "  (14, 'att_amit',     'Attendant@123', 'Kavita Verma',         'kavita.verma@email.com',      4, 'attendant', NULL,             1),",
        "  (15, 'att_lakshmi',  'Attendant@123', 'Ganesh Iyer',          'ganesh.iyer@email.com',       4, 'attendant', NULL,             1),",
        "  (16, 'att_deepak',   'Attendant@123', 'Rani Joshi',           'rani.joshi@email.com',        4, 'attendant', NULL,             1),",
        "  (17, 'att_fatima',   'Attendant@123', 'Ahmed Begum',          'ahmed.begum@email.com',       4, 'attendant', NULL,             1)",
        "ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), email = VALUES(email), role = VALUES(role);",
        "",
        "-- 3. Doctors Profile",
        "INSERT INTO doctors (user_id, username, password_hash, full_name, email, specialization, license_number, qualification, experience_years, is_active) VALUES",
        "  (2, 'dr_sharma', 'Doctor@123', 'Dr. Anil Sharma', 'anil.sharma@jeevansetu.in', 'Cardiology',  'MCI-KA-2008-04521', 'MD Medicine, DM Cardiology (AIIMS Delhi)',        18, 1),",
        "  (3, 'dr_patel',  'Doctor@123', 'Dr. Kavita Patel', 'kavita.patel@jeevansetu.in', 'Pulmonology', 'MCI-MH-2012-07834', 'MD Pulmonary Medicine (KEM Mumbai)',            14, 1),",
        "  (4, 'dr_gupta',  'Doctor@123', 'Dr. Rajiv Gupta',  'rajiv.gupta@jeevansetu.in',  'Neurology',   'MCI-DL-2010-06219', 'MD Medicine, DM Neurology (NIMHANS Bangalore)', 16, 1)",
        "ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), specialization = VALUES(specialization);",
        "",
        "-- 4. Nurses Profile",
        "INSERT INTO nurses (user_id, username, password_hash, full_name, email, specialization, license_number, qualification, ward_assignment, shift, experience_years, is_active) VALUES",
        "  (5, 'nurse_priya', 'Nurse@123', 'Priya Menon',   'priya.menon@jeevansetu.in',   'Critical Care Nursing', 'NMC-KL-2015-11234', 'BSc Nursing, Post Basic ICU Certification', 'ICU', 'Day',       11, 1),",
        "  (6, 'nurse_arun',  'Nurse@123', 'Arun Krishnan', 'arun.krishnan@jeevansetu.in', 'General Nursing',       'NMC-KL-2017-13567', 'BSc Nursing (CMC Vellore)',                 'HDU', 'Night',     9,  1),",
        "  (7, 'nurse_meera', 'Nurse@123', 'Meera Jain',    'meera.jain@jeevansetu.in',    'Emergency Nursing',     'NMC-RJ-2016-12890', 'BSc Nursing, ACLS Certified',               'ICU', 'Rotating', 10, 1)",
        "ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), ward_assignment = VALUES(ward_assignment);",
        "",
        "-- 5. Wards (ICU-A and HDU-B, 20 Beds Capacity each)",
        "INSERT INTO wards (ward_id, name, ward_type, floor_number, total_beds, description, is_active) VALUES",
        "  (1, 'ICU-A', 'ICU', 2, 20, 'Intensive Care Unit - Wing A, Floor 2 (Level 3 Monitoring)', 1),",
        "  (2, 'HDU-B', 'HDU', 3, 20, 'High Dependency Unit - Wing B, Floor 3 (Step-Down Care)', 1)",
        "ON DUPLICATE KEY UPDATE total_beds = VALUES(total_beds), description = VALUES(description);",
        "",
        "-- 6. Beds (ICU-A01 to ICU-A20 for ICU-A, HDU-B01 to HDU-B20 for HDU-B)",
        "INSERT INTO beds (bed_id, ward_id, bed_number, status, is_active) VALUES",
        "  (1,  1, 'ICU-A01', 'occupied',  1), (2,  1, 'ICU-A02', 'occupied',  1), (3,  1, 'ICU-A03', 'occupied',  1),",
        "  (4,  1, 'ICU-A04', 'occupied',  1), (5,  1, 'ICU-A05', 'occupied',  1), (6,  1, 'ICU-A06', 'occupied',  1),",
        "  (85, 1, 'ICU-A07', 'available', 1), (86, 1, 'ICU-A08', 'available', 1), (87, 1, 'ICU-A09', 'available', 1),",
        "  (88, 1, 'ICU-A10', 'available', 1), (95, 1, 'ICU-A11', 'available', 1), (96, 1, 'ICU-A12', 'available', 1),",
        "  (97, 1, 'ICU-A13', 'available', 1), (98, 1, 'ICU-A14', 'available', 1), (99, 1, 'ICU-A15', 'available', 1),",
        "  (100, 1, 'ICU-A16', 'available', 1), (101, 1, 'ICU-A17', 'available', 1), (102, 1, 'ICU-A18', 'available', 1),",
        "  (103, 1, 'ICU-A19', 'available', 1), (104, 1, 'ICU-A20', 'available', 1),",
        "  (7,  2, 'HDU-B01', 'occupied',  1), (8,  2, 'HDU-B02', 'occupied',  1), (9,  2, 'HDU-B03', 'occupied',  1),",
        "  (10, 2, 'HDU-B04', 'occupied',  1), (89, 2, 'HDU-B05', 'available', 1), (90, 2, 'HDU-B06', 'available', 1),",
        "  (91, 2, 'HDU-B07', 'available', 1), (92, 2, 'HDU-B08', 'available', 1), (93, 2, 'HDU-B09', 'available', 1),",
        "  (94, 2, 'HDU-B10', 'available', 1), (105, 2, 'HDU-B11', 'available', 1), (106, 2, 'HDU-B12', 'available', 1),",
        "  (107, 2, 'HDU-B13', 'available', 1), (108, 2, 'HDU-B14', 'available', 1), (109, 2, 'HDU-B15', 'available', 1),",
        "  (110, 2, 'HDU-B16', 'available', 1), (111, 2, 'HDU-B17', 'available', 1), (112, 2, 'HDU-B18', 'available', 1),",
        "  (113, 2, 'HDU-B19', 'available', 1), (114, 2, 'HDU-B20', 'available', 1)",
        "ON DUPLICATE KEY UPDATE status = VALUES(status), is_active = VALUES(is_active);",
        "",
        "-- 7. Patients (The 10 Approved Canonical Patients)",
        "-- Doctor 2 & Nurse 5: Patients 1-3 (3)",
        "-- Doctor 3 & Nurse 6: Patients 4-6 (3)",
        "-- Doctor 4 & Nurse 7: Patients 7-10 (4)",
        "INSERT INTO patients (patient_id, patient_code, name, age, gender, blood_group, contact_number, emergency_contact, admission_date, ward_id, bed_id, ward_type, bed_number, diagnosis, status, assigned_doctor, assigned_nurse, created_by) VALUES",
        "  (1,  'UHID-2026-00001', 'Rajesh Kumar', 58, 'Male',   'B+',  '+91 98765 43210', '+91 98765 43211', DATE_SUB(NOW(), INTERVAL 72 HOUR), 1, 1,  'ICU', 'ICU-A01', 'Acute Respiratory Distress Syndrome (ARDS) & Sepsis', 'admitted', 2, 5, 1),",
        "  (2,  'UHID-2026-00002', 'Anita Devi',   45, 'Female', 'O+',  '+91 98765 43212', '+91 98765 43213', DATE_SUB(NOW(), INTERVAL 48 HOUR), 1, 2,  'ICU', 'ICU-A02', 'Post-Operative Coronary Artery Bypass Graft (CABG)',      'admitted', 2, 5, 1),",
        "  (3,  'UHID-2026-00003', 'Vikram Singh', 62, 'Male',   'A+',  '+91 98765 43214', '+91 98765 43215', DATE_SUB(NOW(), INTERVAL 36 HOUR), 1, 3,  'ICU', 'ICU-A03', 'Severe Polytrauma & Traumatic Brain Injury (TBI)',         'admitted', 2, 5, 1),",
        "  (4,  'UHID-2026-00004', 'Sunita Rao',   51, 'Female', 'AB+', '+91 98765 43216', '+91 98765 43217', DATE_SUB(NOW(), INTERVAL 60 HOUR), 1, 4,  'ICU', 'ICU-A04', 'Acute Kidney Injury (AKI) & Metabolic Acidosis',          'admitted', 3, 6, 1),",
        "  (5,  'UHID-2026-00005', 'Mohammed Ali', 40, 'Male',   'O-',  '+91 98765 43218', '+91 98765 43219', DATE_SUB(NOW(), INTERVAL 24 HOUR), 1, 5,  'ICU', 'ICU-A05', 'Severe Acute Pancreatitis',                              'admitted', 3, 6, 1),",
        "  (6,  'UHID-2026-00006', 'Priya Nair',   33, 'Female', 'B-',  '+91 98765 43220', '+91 98765 43221', DATE_SUB(NOW(), INTERVAL 18 HOUR), 1, 6,  'ICU', 'ICU-A06', 'Post-Partum Hemorrhage (PPH) & Hypovolemic Shock',         'admitted', 3, 6, 1),",
        "  (7,  'UHID-2026-00007', 'Amit Verma',   55, 'Male',   'A-',  '+91 98765 43222', '+91 98765 43223', DATE_SUB(NOW(), INTERVAL 96 HOUR), 2, 7,  'HDU', 'HDU-B01', 'Decompensated Heart Failure (NYHA Class IV)',            'admitted', 4, 7, 1),",
        "  (8,  'UHID-2026-00008', 'Lakshmi Iyer', 29, 'Female', 'AB-', '+91 98765 43224', '+91 98765 43225', DATE_SUB(NOW(), INTERVAL 42 HOUR), 2, 8,  'HDU', 'HDU-B02', 'Diabetic Ketoacidosis (DKA) - Resolving Phase',           'admitted', 4, 7, 1),",
        "  (9,  'UHID-2026-00009', 'Deepak Joshi', 47, 'Male',   'B+',  '+91 98765 43226', '+91 98765 43227', DATE_SUB(NOW(), INTERVAL 30 HOUR), 2, 9,  'HDU', 'HDU-B03', 'Community Acquired Pneumonia (CAP) & COPD Exacerbation',  'admitted', 4, 7, 1),",
        "  (10, 'UHID-2026-00010', 'Fatima Begum', 65, 'Female', 'O+',  '+91 98765 43228', '+91 98765 43229', DATE_SUB(NOW(), INTERVAL 12 HOUR), 2, 10, 'HDU', 'HDU-B04', 'Acute Ischemic Stroke (Subacute Recovery Phase)',          'admitted', 4, 7, 1)",
        "ON DUPLICATE KEY UPDATE name = VALUES(name), diagnosis = VALUES(diagnosis), status = VALUES(status);",
        "",
        "-- 8. Attendants Mapping (User IDs 8-17 to Patients 1-10)",
        "INSERT INTO attendants (patient_id, user_id, relationship, access_code) VALUES",
        "  (1,  8,  'Spouse',   'JSACC10001'),",
        "  (2,  9,  'Son',      'JSACC10002'),",
        "  (3,  10, 'Daughter', 'JSACC10003'),",
        "  (4,  11, 'Spouse',   'JSACC10004'),",
        "  (5,  12, 'Wife',     'JSACC10005'),",
        "  (6,  13, 'Brother',  'JSACC10006'),",
        "  (7,  14, 'Wife',     'JSACC10007'),",
        "  (8,  15, 'Father',   'JSACC10008'),",
        "  (9,  16, 'Wife',     'JSACC10009'),",
        "  (10, 17, 'Son',      'JSACC10010')",
        "ON DUPLICATE KEY UPDATE relationship = VALUES(relationship), access_code = VALUES(access_code);",
        "",
        "-- 9. Bed Management (Active Allocations for Patients 1-10)",
        "INSERT INTO bed_management (patient_id, bed_id, ward_id, allocated_at, status, allocated_by, notes) VALUES",
        "  (1,  1,  1, DATE_SUB(NOW(), INTERVAL 72 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (2,  2,  1, DATE_SUB(NOW(), INTERVAL 48 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (3,  3,  1, DATE_SUB(NOW(), INTERVAL 36 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (4,  4,  1, DATE_SUB(NOW(), INTERVAL 60 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (5,  5,  1, DATE_SUB(NOW(), INTERVAL 24 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (6,  6,  1, DATE_SUB(NOW(), INTERVAL 18 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (7,  7,  2, DATE_SUB(NOW(), INTERVAL 96 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (8,  8,  2, DATE_SUB(NOW(), INTERVAL 42 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (9,  9,  2, DATE_SUB(NOW(), INTERVAL 30 HOUR), 'occupied', 1, 'Admission allocation'),",
        "  (10, 10, 2, DATE_SUB(NOW(), INTERVAL 12 HOUR), 'occupied', 1, 'Admission allocation')",
        "ON DUPLICATE KEY UPDATE status = VALUES(status);",
        "",
        "-- 10. Schema Migrations History",
        "INSERT INTO schema_migrations (version, description) VALUES",
        "  ('001_core_schema', 'Initial database schema creation for Jeevan Setu'),",
        "  ('002_rbac_system', 'Role-based access control setup'),",
        "  ('003_seed_data', 'Realistic clinical dataset with 10 patients and 20-bed wards'),",
        "  ('seed_v1_2026', 'Authoritative verified seed data snapshot')",
        "ON DUPLICATE KEY UPDATE description = VALUES(description);",
        "",
        "SET FOREIGN_KEY_CHECKS = 1;",
        ""
    ])

    final_sql = "\n".join(schema_parts)
    target_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.sql'))
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(final_sql)

    print(f"[OK] Successfully generated schema.sql ({len(final_sql)} bytes, {len(schema_parts)} lines)")


if __name__ == '__main__':
    generate()
