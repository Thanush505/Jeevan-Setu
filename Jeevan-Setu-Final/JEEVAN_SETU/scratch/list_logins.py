import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import db
from models.user_model import verify_pw, hash_pw

users = db.execute_query('SELECT user_id, username, full_name, email, role, department, password_hash, is_active FROM users WHERE is_active = TRUE ORDER BY user_id ASC', fetch=True) or []

passwords_to_test = [
    'Doctor@123', 'Nurse@123', 'Admin@123', 'Attendant@123', 
    'Password@123', 'Admin@2026', 'Doctor@2026', 'Nurse@2026', 
    'admin123', 'doctor123', 'nurse123', 'admin', 'password'
]

# Standardize default passwords for known seed users if needed
seed_defaults = {
    'admin': 'Admin@123',
    'admin_js': 'Admin@123',
    'dr_sharma': 'Doctor@123',
    'dr_gupta': 'Doctor@123',
    'dr_verma': 'Doctor@123',
    'dr_mehta': 'Doctor@123',
    'nurse_priya': 'Nurse@123',
    'nurse_anjali': 'Nurse@123',
    'nurse_sunita': 'Nurse@123',
    'nurse_rekha': 'Nurse@123',
    'attendant_1': 'Attendant@123'
}

for username, pw in seed_defaults.items():
    u = db.execute_query('SELECT user_id, password_hash FROM users WHERE username = %s', (username,), fetch=True)
    if u and not any(verify_pw(p, u[0]['password_hash']) for p in passwords_to_test):
        new_hash = hash_pw(pw)
        db.execute_query('UPDATE users SET password_hash = %s WHERE user_id = %s', (new_hash, u[0]['user_id']))

# Re-fetch
users = db.execute_query('SELECT user_id, username, full_name, email, role, department, password_hash, is_active FROM users WHERE is_active = TRUE ORDER BY user_id ASC', fetch=True) or []

print("=" * 110)
print(f"{'ROLE':<10} | {'USERNAME':<16} | {'PASSWORD':<14} | {'NAME':<24} | {'EMAIL'}")
print("=" * 110)

core_roles = ['doctor', 'nurse', 'admin', 'attendant']
seen_users = set()

for u in users:
    role = u['role'].lower()
    uname = u['username']
    if uname in seen_users:
        continue
    
    # Test matched password
    matched = 'N/A'
    for p in passwords_to_test:
        if verify_pw(p, u.get('password_hash', '')):
            matched = p
            break
            
    if matched != 'N/A' or u['user_id'] <= 15:
        seen_users.add(uname)
        print(f"{u['role'].upper():<10} | {uname:<16} | {matched:<14} | {u['full_name']:<24} | {u['email']}")

print("=" * 110)
