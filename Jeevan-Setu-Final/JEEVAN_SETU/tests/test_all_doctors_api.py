import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib.request
import json
from database.db import execute_query
from services.auth_service import AuthService

def main():
    print("=" * 70)
    print("DOCTOR PORTAL BACKEND RBAC & PATIENT ASSIGNMENT VERIFICATION")
    print("=" * 70)

    # 1. Canonical Doctors (dr_sharma, dr_patel, dr_gupta)
    canonical_docs = execute_query(
        "SELECT user_id, username, full_name, email, role, department FROM users WHERE username IN ('dr_sharma', 'dr_patel', 'dr_gupta') ORDER BY user_id",
        fetch=True
    )
    
    expected_distribution = {
        'dr_sharma': 3,
        'dr_patel': 3,
        'dr_gupta': 4
    }

    for doc in canonical_docs:
        username = doc['username']
        expected_count = expected_distribution[username]
        token_obj = AuthService.generate_access_token(doc)
        token = token_obj['access_token']
        
        # Test /api/v1/patients
        req = urllib.request.Request(
            'http://127.0.0.1:5000/api/v1/patients?status=admitted',
            headers={'Authorization': f'Bearer {token}'}
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode())
            patients = res.get('data', [])
            print(f"\nDoctor: {doc['full_name']} (@{username}, ID: {doc['user_id']})")
            print(f"  Assigned Patient Count: {len(patients)} (Expected: {expected_count})")
            assert len(patients) == expected_count, f"Doctor {username} expected {expected_count} patients, got {len(patients)}"
            
            for p in patients:
                v = p.get('latest_vitals') or {}
                print(f"    - Patient #{p.get('patient_id')}: {p.get('name'):<16} ({p.get('patient_code')}) | Bed: {p.get('bed_number'):<8} | EWS: {p.get('ews_score')} | HR: {v.get('heart_rate')} | SBP: {v.get('blood_pressure_sys')}")

        # Test Search as Doctor
        test_patient = patients[0]
        search_term = test_patient['name'].split()[0]
        search_req = urllib.request.Request(
            f"http://127.0.0.1:5000/api/v1/patients/search?q={urllib.parse.quote(search_term)}",
            headers={'Authorization': f'Bearer {token}'}
        )
        with urllib.request.urlopen(search_req) as resp:
            s_res = json.loads(resp.read().decode())
            s_data = s_res.get('data', [])
            print(f"  Search '{search_term}' returned: {len(s_data)} matches")
            assert len(s_data) >= 1, f"Search failed for doctor's own patient {search_term}"

    # 2. Test Admin view (must see all 10)
    admin = execute_query("SELECT user_id, username, full_name, email, role FROM users WHERE role = 'admin' LIMIT 1", fetch=True)[0]
    admin_token = AuthService.generate_access_token(admin)['access_token']
    admin_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/v1/patients?status=admitted&limit=50',
        headers={'Authorization': f'Bearer {admin_token}'}
    )
    with urllib.request.urlopen(admin_req) as resp:
        admin_res = json.loads(resp.read().decode())
        admin_patients = admin_res.get('data', [])
        print(f"\nAdmin: {admin['full_name']} -> Total Patients: {len(admin_patients)} (Expected: 10)")
        assert len(admin_patients) == 10, f"Admin expected 10 patients, got {len(admin_patients)}"

    print("\n" + "=" * 70)
    print("ALL 3 DOCTORS & ADMIN RBAC PASSED SUCCESSFULLY (3 / 3 / 4 / 10)!")
    print("=" * 70)

if __name__ == "__main__":
    main()
