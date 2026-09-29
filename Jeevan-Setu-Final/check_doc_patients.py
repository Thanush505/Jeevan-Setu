import urllib.request
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JEEVAN_SETU'))
from services.auth_service import AuthService

doctors = [
    (2, 'Dr. Sharma', 'dr.sharma@hospital.org'),
    (3, 'Dr. Patel', 'dr.patel@hospital.org'),
    (4, 'Dr. Gupta', 'dr.gupta@hospital.org')
]

for doc_id, name, email in doctors:
    token_dict = AuthService.generate_access_token({
        'user_id': doc_id,
        'username': email.split('@')[0],
        'email': email,
        'role': 'doctor'
    })
    token = token_dict['access_token']
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/v1/patients',
        headers={'Authorization': f'Bearer {token}'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        patients = data.get('data', [])
        print(f"\n=== {name} (ID: {doc_id}) -> Total Patients: {len(patients)} ===")
        for p in patients:
            lv = p.get('latest_vitals') or {}
            ews = lv.get('ews_score') if lv else p.get('ews_score', 0)
            print(f"  - [{p.get('patient_code')}] {p.get('name')} | Ward: {p.get('ward_type')} (Bed {p.get('bed_number')}) | EWS: {ews} | Status: {p.get('status')}")
