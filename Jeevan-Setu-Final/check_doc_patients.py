import urllib.request
import json
import sys

sys.path.append('c:/Users/Admin/Downloads/Jeevan-Setu-main/Jeevan-Setu-main')
from JEEVAN_SETU.utils.security import generate_token

doctors = [
    (2, 'Dr. Sharma', 'dr.sharma@hospital.org'),
    (3, 'Dr. Patel', 'dr.patel@hospital.org'),
    (4, 'Dr. Gupta', 'dr.gupta@hospital.org')
]

for doc_id, name, email in doctors:
    token = generate_token(user_id=doc_id, email=email, role='doctor')
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
