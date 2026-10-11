import requests
import json
import time

BASE = 'http://127.0.0.1:5000'

def test_live_refresh():
    # 1. Admin login
    doc_res = requests.post(f'{BASE}/api/v1/auth/login', json={'username': 'admin_js', 'password': 'Admin@123'})
    assert doc_res.status_code == 200, f"Admin login failed: {doc_res.text}"
    token = doc_res.json()['data']['token']
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Get initial patient state
    p_res = requests.get(f'{BASE}/api/v1/patients?status=admitted', headers=headers)
    assert p_res.status_code == 200, "Get patients failed"
    patients = p_res.json()['data']
    assert len(patients) > 0, "No patients found"

    target_patient = patients[0]
    pid = target_patient['patient_id']
    print(f"[TEST] Target Patient #{pid}: {target_patient['name']} | Initial EWS: {target_patient.get('ews_score', 0)}")

    # 3. Simulate new vitals submission from telemetry monitor
    print("[TEST] Submitting new vitals from telemetry monitor...")
    vital_payload = {
        'heart_rate': 124.0,
        'systolic_bp': 88.0,
        'respiratory_rate': 26.0,
        'temperature': 39.0
    }
    sub_res = requests.post(f'{BASE}/vitals/patient/{pid}/submit', json=vital_payload, headers=headers)
    assert sub_res.status_code == 201, f"Vitals submit failed: {sub_res.text}"
    sub_data = sub_res.json()['data']
    print(f"[TEST] Vitals saved! Calculated Total EWS: {sub_data['total_score']}, Condition: {sub_data['condition']}")

    # 4. Simulate the 10-second automatic polling request
    print("[TEST] Simulating 10-second background polling request...")
    poll_res = requests.get(f'{BASE}/api/v1/patients?status=admitted', headers=headers)
    assert poll_res.status_code == 200
    updated_patient = [p for p in poll_res.json()['data'] if p['patient_id'] == pid][0]

    print(f"[TEST] Polled result for Patient #{pid}: EWS={updated_patient.get('ews_score')}, Condition={updated_patient.get('condition')}, Vitals={updated_patient.get('latest_vitals')}")
    assert updated_patient.get('ews_score') == sub_data['total_score'], "Polled EWS must match backend calculated EWS"
    print("[SUCCESS] 10-second automatic polling data pipeline verified!")

if __name__ == '__main__':
    test_live_refresh()
