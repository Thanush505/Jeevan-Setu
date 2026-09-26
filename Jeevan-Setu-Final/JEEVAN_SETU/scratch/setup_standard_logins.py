import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import db
from models.user_model import verify_pw, hash_pw

# 1. Clean up stale historical test alerts
db.execute_query("UPDATE alerts SET is_acknowledged = TRUE, acknowledged_at = NOW() WHERE is_acknowledged = FALSE")
print("All historical test alerts marked as acknowledged.")

# 2. Reset standard seed doctor and nurse passwords to standard known passwords
standard_logins = [
    # Doctors
    ('dr_sharma', 'Doctor@123', 'doctor', 'Dr. Rajesh Sharma', 'dr.sharma@jeevansetu.com', 'ICU'),
    ('dr_gupta', 'Doctor@123', 'doctor', 'Dr. Ananya Gupta', 'dr.gupta@jeevansetu.com', 'Cardiology'),
    ('dr_verma', 'Doctor@123', 'doctor', 'Dr. Vikram Verma', 'dr.verma@jeevansetu.com', 'Neurology'),
    ('dr_mehta', 'Doctor@123', 'doctor', 'Dr. Sunita Mehta', 'dr.mehta@jeevansetu.com', 'Pulmonology'),
    
    # Nurses
    ('nurse_priya', 'Nurse@123', 'nurse', 'Sr. Nurse Priya Sharma', 'nurse.priya@jeevansetu.com', 'ICU'),
    ('nurse_anjali', 'Nurse@123', 'nurse', 'Nurse Anjali Verma', 'nurse.anjali@jeevansetu.com', 'HDU'),
    ('nurse_sunita', 'Nurse@123', 'nurse', 'Nurse Sunita Patel', 'nurse.sunita@jeevansetu.com', 'General'),
    ('nurse_rekha', 'Nurse@123', 'nurse', 'Nurse Rekha Nair', 'nurse.rekha@jeevansetu.com', 'ICU'),

    # Admin & Attendant
    ('admin', 'Admin@123', 'admin', 'System Administrator', 'admin@jeevansetu.com', 'Administration'),
    ('attendant_1', 'Attendant@123', 'attendant', 'Ramesh Kumar (Attendant)', 'ramesh.attendant@gmail.com', 'Patient Care')
]

for username, password, role, full_name, email, dept in standard_logins:
    existing = db.execute_query("SELECT user_id FROM users WHERE username = %s", (username,), fetch=True)
    pw_hash = hash_pw(password)
    if existing:
        db.execute_query(
            "UPDATE users SET password_hash = %s, role = %s, full_name = %s, email = %s, department = %s, is_active = TRUE WHERE user_id = %s",
            (pw_hash, role, full_name, email, dept, existing[0]['user_id'])
        )
    else:
        db.execute_query(
            "INSERT INTO users (username, password_hash, role, full_name, email, department, is_active) VALUES (%s, %s, %s, %s, %s, %s, TRUE)",
            (username, pw_hash, role, full_name, email, dept)
        )

print("Standard seed users updated and verified.")
