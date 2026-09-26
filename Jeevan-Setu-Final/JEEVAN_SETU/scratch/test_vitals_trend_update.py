import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_vitals_trend_update():
    session = requests.Session()
    
    # 1. Login as Dr. Sharma
    login_resp = session.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": "dr_sharma",
        "password": "Doctor@123"
    })
    token = login_resp.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Add a new vital sign observation for Patient 1 (Rajesh Kumar)
    # Testing HR=118, SBP=82, RR=28, Temp=38.8 (EWS will be calculated)
    new_vital_payload = {
        "patient_id": 1,
        "heart_rate": 118,
        "blood_pressure_sys": 82,
        "blood_pressure_dia": 78,
        "respiratory_rate": 28,
        "temperature": 38.8,
        "spo2": 94,
        "consciousness": "Alert"
    }
    
    add_resp = session.post(f"{BASE_URL}/api/v1/vitals", json=new_vital_payload, headers=headers)
    print(f"[ADD VITAL] Status: {add_resp.status_code}")
    assert add_resp.status_code in [200, 201], f"Failed to record vital: {add_resp.text}"
    created_vital = add_resp.json().get("data", {})
    vital_id = created_vital.get("vital_id")
    print(f"[OK] Recorded Vital ID: {vital_id}")
    
    # 3. Check history endpoint
    hist_resp = session.get(f"{BASE_URL}/api/v1/vitals/patient/1/history?limit=10", headers=headers)
    assert hist_resp.status_code == 200
    hist = hist_resp.json().get("data", [])
    print(f"[OK] Total historical observations now: {len(hist)}")
    assert len(hist) >= 2, "Expected at least 2 historical records after adding new vital"
    
    # Verify latest record is the new vital
    latest = hist[0]
    print(f"[OK] Latest observation: EWS={latest['total_score']}, HR={latest['heart_rate']}, BP={latest['blood_pressure_sys']}/{latest['blood_pressure_dia']}, RR={latest['respiratory_rate']}, Temp={latest['temperature']}")
    assert latest['heart_rate'] == 118.0
    
    # 4. Clean up the test vital to preserve exact canonical state
    del_resp = session.delete(f"{BASE_URL}/api/v1/vitals/{vital_id}", headers=headers)
    print(f"[CLEANUP] Deleted test vital {vital_id}: status {del_resp.status_code}")
    
    # 5. Verify restored count
    hist_resp_final = session.get(f"{BASE_URL}/api/v1/vitals/patient/1/history?limit=10", headers=headers)
    final_count = len(hist_resp_final.json().get("data", []))
    print(f"[OK] Canonical vitals count restored: {final_count}")

if __name__ == "__main__":
    test_vitals_trend_update()
