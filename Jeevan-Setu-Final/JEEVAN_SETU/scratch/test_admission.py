"""
scratch/test_admission.py — Test full transactional patient admission into an available bed.
"""

import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import db

payload = {
    'name': 'Rohan Deshmukh',
    'age': 54,
    'gender': 'Male',
    'diagnosis': 'Post CABG Observation',
    'blood_group': 'B+',
    'ward_id': 1,
    'bed_id': 85,
    'assigned_doctor': 2,
    'assigned_nurse': 5,
    'attendant_name': 'Meera Deshmukh',
    'attendant_relationship': 'Wife',
    'attendant_contact': '9876543210'
}

res = requests.post('http://127.0.0.1:5000/api/v1/patients/admit', json=payload)
print('POST /api/v1/patients/admit status:', res.status_code)
print('Response:', res.json())

if res.status_code in (200, 201):
    pid = res.json().get('data', {}).get('patient_id')
    print('Admission test succeeded! Patient ID:', pid)
    db.execute_query('DELETE FROM patient_qr_tokens WHERE patient_id = %s', (pid,))
    db.execute_query('DELETE FROM bed_management WHERE patient_id = %s', (pid,))
    db.execute_query('DELETE FROM attendants WHERE patient_id = %s', (pid,))
    db.execute_query('DELETE FROM patients WHERE patient_id = %s', (pid,))
    db.execute_query("UPDATE beds SET status = 'available' WHERE bed_id = 85")
    print('Cleaned test admission cleanly.')
