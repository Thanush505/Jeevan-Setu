"""
scratch/verify_10_patients.py — Verify that the system enforces exactly 10 patients
across all APIs, staff distributions, attendant QR status, and rejects an 11th admission.
"""

import requests

BASE = 'http://127.0.0.1:5000'

def run_tests():
    print("=== TEST 1: Total Patient Count & List ===")
    res = requests.get(f"{BASE}/api/v1/patients")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    patients = data.get('data', [])
    print(f"Total Admitted Patients: {len(patients)} (Expected: 10)")
    assert len(patients) == 10, f"Expected 10 patients, got {len(patients)}"
    for p in sorted(patients, key=lambda x: x['patient_id']):
        print(f"  [{p['patient_id']}] {p['name']} | Code: {p.get('patient_code')} | Ward: {p.get('ward_type')} | Bed: {p.get('bed_number')} | Doc: {p.get('assigned_doctor')} | Nurse: {p.get('assigned_nurse')}")

    print("\n=== TEST 2: Doctor Patient Distribution (3, 3, 4) ===")
    for doc_id, expected_cnt in [(2, 3), (3, 3), (4, 4)]:
        res = requests.get(f"{BASE}/api/v1/patients?doctor_id={doc_id}")
        doc_pts = res.json().get('data', [])
        print(f"Doctor ID {doc_id}: {len(doc_pts)} patients assigned (Expected: {expected_cnt})")
        assert len(doc_pts) == expected_cnt, f"Doctor {doc_id} expected {expected_cnt}, got {len(doc_pts)}"

    print("\n=== TEST 3: Nurse Patient Distribution (3, 3, 4) ===")
    for nurse_id, expected_cnt in [(5, 3), (6, 3), (7, 4)]:
        res = requests.get(f"{BASE}/api/v1/patients?nurse_id={nurse_id}")
        nurse_pts = res.json().get('data', [])
        print(f"Nurse ID {nurse_id}: {len(nurse_pts)} patients assigned (Expected: {expected_cnt})")
        assert len(nurse_pts) == expected_cnt, f"Nurse {nurse_id} expected {expected_cnt}, got {len(nurse_pts)}"

    print("\n=== TEST 4: Attendant QR Management (Admin) ===")
    res = requests.get(f"{BASE}/attendant/api/patients")
    qr_pts = res.json().get('data', [])
    print(f"Attendant QR Patients: {len(qr_pts)} (Expected: 10)")
    assert len(qr_pts) == 10, f"Expected 10 QR patients, got {len(qr_pts)}"
    for p in sorted(qr_pts, key=lambda x: x['patient_id']):
        print(f"  [{p['patient_id']}] {p.get('patient_name')}: QR Status = {p.get('qr_status')}, Access Code = {p.get('access_code')}")

    print("\n=== TEST 5: Search Specific Approved Patient ===")
    res = requests.get(f"{BASE}/api/v1/patients/search?q=Fatima")
    sdata = res.json().get('data', [])
    print(f"Search 'Fatima': Found {len(sdata)} patient(s)")
    assert len(sdata) == 1 and sdata[0]['name'] == 'Fatima Begum'

    print("\n=== TEST 6: Reject 11th Patient Admission ===")
    post_res = requests.post(f"{BASE}/api/v1/patients", json={
        'name': 'Unapproved Extra Patient',
        'age': 45,
        'gender': 'Male',
        'diagnosis': 'Should Be Rejected',
        'ward_type': 'ICU'
    })
    print(f"POST /api/v1/patients Status: {post_res.status_code}")
    print(f"Response Error: {post_res.json().get('error')}")
    assert post_res.status_code == 400
    assert "Maximum capacity of 10 patients" in post_res.json().get('error')

    print("\n[ALL 6 VERIFICATION TESTS PASSED SUCCESSFULLY!]")

if __name__ == '__main__':
    run_tests()
