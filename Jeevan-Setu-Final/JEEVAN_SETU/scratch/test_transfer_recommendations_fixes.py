import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_transfer_recommendations():
    session = requests.Session()
    
    # 1. Test fetching page HTML
    page_resp = session.get(f"{BASE_URL}/Doctor/Doctor_transfer_recommendations/Doctor_transfer_recommendations.html")
    print(f"[PAGE CHECK] Status code: {page_resp.status_code}")
    assert page_resp.status_code == 200, "Transfer recommendations page failed to load"
    assert "Transfer Recommendations" in page_resp.text, "Page title missing"
    assert "Patient Queue" in page_resp.text, "Queue header missing"
    assert "AI Clinical Decision Explanation" in page_resp.text, "AI explanation section missing"
    assert "EWS Scoring Breakdown" in page_resp.text, "EWS breakdown missing"
    print("[OK] HTML structure verified")

    # 2. Test Doctor login (Dr. Sharma)
    login_resp = session.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": "dr_sharma",
        "password": "Doctor@123"
    })
    print(f"[AUTH CHECK] Login status: {login_resp.status_code}")
    assert login_resp.status_code == 200, "Login failed"
    auth_data = login_resp.json()
    token = auth_data["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Test doctor assigned patients
    patients_resp = session.get(f"{BASE_URL}/api/v1/patients?status=admitted", headers=headers)
    print(f"[PATIENTS CHECK] Status: {patients_resp.status_code}")
    assert patients_resp.status_code == 200
    patients = patients_resp.json().get("data", [])
    print(f"Dr. Sharma assigned patients: {len(patients)}")
    assert len(patients) == 3, f"Expected 3 patients for Dr. Sharma, got {len(patients)}"

    # Test all 3 canonical doctors
    doc_accounts = [
        ("dr_sharma", "Doctor@123", 3),
        ("dr_patel", "Doctor@123", 3),
        ("dr_gupta", "Doctor@123", 4),
    ]
    
    total_evaluated = 0
    for uname, pwd, exp_count in doc_accounts:
        l_resp = session.post(f"{BASE_URL}/api/v1/auth/login", json={"username": uname, "password": pwd})
        assert l_resp.status_code == 200, f"Login failed for {uname}"
        tok = l_resp.json()["data"]["token"]
        h = {"Authorization": f"Bearer {tok}"}
        
        p_resp = session.get(f"{BASE_URL}/api/v1/patients?status=admitted", headers=h)
        assert p_resp.status_code == 200
        doc_patients = p_resp.json().get("data", [])
        assert len(doc_patients) == exp_count, f"{uname} expected {exp_count} patients, got {len(doc_patients)}"
        print(f"\nDoctor {uname}: {len(doc_patients)} authorized patients")
        
        for p in doc_patients:
            p_id = p["patient_id"]
            eval_resp = session.get(f"{BASE_URL}/api/v1/decision/evaluate/{p_id}", headers=h)
            assert eval_resp.status_code == 200, f"Evaluate failed for patient {p_id}"
            ed = eval_resp.json().get("data", {})
            print(f"  [OK] Patient {p['name']} ({p_id}): EWS={ed.get('score')} ({ed.get('risk_level')}) -> Rec: {ed.get('recommendation')}")
            assert "contributing_parameters" in ed
            assert len(ed["contributing_parameters"]) >= 4, f"Expected at least 4 EWS parameters, got {len(ed['contributing_parameters'])}"
            total_evaluated += 1

    print(f"\nTotal canonical patients evaluated dynamically: {total_evaluated} / 10")

    print("\nALL TRANSFER RECOMMENDATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_transfer_recommendations()
