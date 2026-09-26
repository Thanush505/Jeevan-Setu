import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_ews_trends():
    session = requests.Session()

    # 1. Test HTML Page Load
    page_resp = session.get(f"{BASE_URL}/Doctor/Doctor_ews_trends/Doctor_ews_trends.html")
    print(f"[PAGE CHECK] Status: {page_resp.status_code}")
    assert page_resp.status_code == 200, "Doctor EWS trends page failed to load"
    assert "EWS Score Trend Timeline" in page_resp.text, "Chart title missing"
    assert "ewsTrendCanvas" in page_resp.text, "Canvas missing"
    assert "doctor-patient-selector" in page_resp.text, "Patient selector missing"
    assert "btn-range-10" in page_resp.text, "Latest 10 range button missing"
    print("[OK] HTML and Chart.js structure verified")

    # 2. Test Doctor Login (dr_sharma)
    login_resp = session.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": "dr_sharma",
        "password": "Doctor@123"
    })
    print(f"[AUTH CHECK] Status: {login_resp.status_code}")
    assert login_resp.status_code == 200, "Login failed"
    token = login_resp.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Test Doctor Patients
    patients_resp = session.get(f"{BASE_URL}/api/v1/patients?status=admitted", headers=headers)
    assert patients_resp.status_code == 200
    patients = patients_resp.json().get("data", [])
    print(f"[PATIENTS CHECK] Dr. Sharma has {len(patients)} assigned patients")
    assert len(patients) == 3

    # 4. Test Vitals History for each patient
    for p in patients:
        pid = p["patient_id"]
        
        # Test patient detail
        p_detail_resp = session.get(f"{BASE_URL}/api/v1/patients/{pid}", headers=headers)
        assert p_detail_resp.status_code == 200
        p_detail = p_detail_resp.json().get("data", {})
        assert p_detail["name"] == p["name"]
        
        # Test vitals history
        hist_resp = session.get(f"{BASE_URL}/api/v1/vitals/patient/{pid}/history?limit=10", headers=headers)
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json().get("data", [])
        print(f"  [OK] Patient {p['name']} (ID {pid}): {len(hist_data)} historical observation(s)")
        assert len(hist_data) >= 1, "Expected at least 1 historical vital"
        
        for obs in hist_data:
            assert "total_score" in obs, "total_score missing"
            assert "heart_rate" in obs, "heart_rate missing"
            assert "blood_pressure_sys" in obs, "blood_pressure_sys missing"
            assert "temperature" in obs, "temperature missing"
            assert "recorded_at" in obs, "recorded_at missing"
            print(f"       -> {obs['recorded_at']} | EWS: {obs['total_score']} | HR: {obs['heart_rate']} | BP: {obs['blood_pressure_sys']}/{obs.get('blood_pressure_dia')} | RR: {obs['respiratory_rate']} | Temp: {obs['temperature']}")

    # 5. Verify all 3 Doctors across all 10 canonical patients
    doc_accounts = [
        ("dr_sharma", "Doctor@123", 3),
        ("dr_patel", "Doctor@123", 3),
        ("dr_gupta", "Doctor@123", 4),
    ]

    total_patients_checked = 0
    for uname, pwd, exp_count in doc_accounts:
        l_resp = session.post(f"{BASE_URL}/api/v1/auth/login", json={"username": uname, "password": pwd})
        assert l_resp.status_code == 200
        tok = l_resp.json()["data"]["token"]
        h = {"Authorization": f"Bearer {tok}"}
        
        p_resp = session.get(f"{BASE_URL}/api/v1/patients?status=admitted", headers=h)
        doc_patients = p_resp.json().get("data", [])
        assert len(doc_patients) == exp_count
        
        for p in doc_patients:
            h_resp = session.get(f"{BASE_URL}/api/v1/vitals/patient/{p['patient_id']}/history", headers=h)
            assert h_resp.status_code == 200
            total_patients_checked += 1

    print(f"\n[OK] Verified trends data flow for all {total_patients_checked}/10 canonical patients across all doctors!")
    print("\nALL DOCTOR EWS TRENDS TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_ews_trends()
