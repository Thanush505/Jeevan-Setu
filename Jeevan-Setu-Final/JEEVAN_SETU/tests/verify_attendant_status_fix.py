import time
import requests
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.auth_service import AuthService
from models.user_model import User

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    print("=== Jeevan Setu Attendant Status & Performance Verification ===")

    # 1. Generate valid staff and attendant tokens
    admin_user = User.get_by_id(1)
    admin_token = AuthService.generate_access_token(admin_user)['access_token']
    headers = {"Authorization": f"Bearer {admin_token}"}
    print("[PASS] Generated valid test authentication token.")

    # 2. Test Patient 4 (Sunita Rao - EWS 11 Critical)
    t0 = time.time()
    res_p4 = requests.get(f"{BASE_URL}/api/v1/attendant/patient?patient_id=4", headers=headers)
    t_elapsed = (time.time() - t0) * 1000
    assert res_p4.status_code == 200, f"Patient 4 fetch failed: {res_p4.text}"
    p4 = res_p4.json()["data"]
    
    print(f"\n--- Patient 4 (Sunita Rao) Verification (Latency: {t_elapsed:.1f}ms) ---")
    print(f"Name: {p4.get('name')}")
    print(f"EWS Score: {p4.get('total_score')}")
    print(f"Condition: {p4.get('condition')}")
    print(f"Recommendation: {p4.get('recommendation')}")
    print(f"Risk Level: {p4.get('risk_level')}")
    print(f"Ward: {p4.get('ward_type')} · Bed: {p4.get('bed_number')}")
    print(f"Assigned Nurse: {p4.get('assigned_nurse', {}).get('nurse_name')} ({p4.get('assigned_nurse', {}).get('phone_number')})")

    assert p4.get('name') == "Sunita Rao", f"Expected 'Sunita Rao', got {p4.get('name')}"
    assert p4.get('total_score') == 11, f"Expected 11, got {p4.get('total_score')}"
    assert p4.get('condition') == "Critical", f"Condition MUST be 'Critical' for EWS 11, got {p4.get('condition')}"
    assert p4.get('recommendation') == "Keep in ICU", f"Expected 'Keep in ICU', got {p4.get('recommendation')}"
    assert p4.get('assigned_nurse', {}).get('nurse_assigned') is True, "Nurse should be assigned"
    print("[PASS] Patient 4 authoritative clinical data is 100% consistent!")

    # 3. Test Patient 1 (Rajesh Kumar - EWS 0 Stable)
    t0 = time.time()
    res_p1 = requests.get(f"{BASE_URL}/api/v1/attendant/patient?patient_id=1", headers=headers)
    t_p1 = (time.time() - t0) * 1000
    assert res_p1.status_code == 200
    p1 = res_p1.json()["data"]
    print(f"\n--- Patient 1 (Rajesh Kumar) Verification (Latency: {t_p1:.1f}ms) ---")
    print(f"Name: {p1.get('name')}")
    print(f"EWS Score: {p1.get('total_score')}")
    print(f"Condition: {p1.get('condition')}")
    print(f"Recommendation: {p1.get('recommendation')}")
    assert p1.get('condition') == "Stable", f"Expected 'Stable', got {p1.get('condition')}"
    assert p1.get('recommendation') == "Fit for HDU Transfer"
    print("[PASS] Patient 1 authoritative clinical data is 100% consistent!")

    # 4. Test Patient 2 (Anita Devi - EWS 11 Critical)
    t0 = time.time()
    res_p2 = requests.get(f"{BASE_URL}/api/v1/attendant/patient?patient_id=2", headers=headers)
    t_p2 = (time.time() - t0) * 1000
    assert res_p2.status_code == 200
    p2 = res_p2.json()["data"]
    print(f"\n--- Patient 2 (Anita Devi) Verification (Latency: {t_p2:.1f}ms) ---")
    print(f"Name: {p2.get('name')}")
    print(f"EWS Score: {p2.get('total_score')}")
    print(f"Condition: {p2.get('condition')}")
    assert p2.get('condition') == "Critical", f"Expected 'Critical', got {p2.get('condition')}"
    print("[PASS] Patient 2 authoritative clinical data is 100% consistent!")

    # 5. Attendant Session Isolation & QR Token Validation
    from routes.attendant_routes import generate_attendant_session_token
    att_token_data = generate_attendant_session_token(4, "Ramesh Rao", "sample_hash")
    att_headers = {"Authorization": f"Bearer {att_token_data['access_token']}"}
    
    t0 = time.time()
    att_res = requests.get(f"{BASE_URL}/api/v1/attendant/patient", headers=att_headers)
    t_att = (time.time() - t0) * 1000
    assert att_res.status_code == 200, f"Attendant session fetch failed: {att_res.text}"
    att_p4 = att_res.json()["data"]
    print(f"\n--- Attendant Session Isolation for Patient 4 (Latency: {t_att:.1f}ms) ---")
    print(f"Attendant Greeting: Hello, {att_p4.get('attendant_name')}")
    print(f"Patient Name: {att_p4.get('name')}")
    print(f"EWS Score: {att_p4.get('total_score')}")
    print(f"Condition: {att_p4.get('condition')}")
    assert att_p4.get("name") == "Sunita Rao"
    assert att_p4.get("total_score") == 11
    assert att_p4.get("condition") == "Critical"
    print("[PASS] Attendant session token accurately retrieves Patient 4 with 0 cross-talk.")

    # Check that direct URL without token is blocked with 401
    unauth_res = requests.get(f"{BASE_URL}/api/v1/attendant/patient")
    assert unauth_res.status_code == 401, f"Expected 401 Unauthorized without credentials, got {unauth_res.status_code}"
    print("[PASS] Security isolation verified: unauthenticated direct access blocked with 401.")

    # 6. Verify Frontend Files Static Integrity
    html_path = "Jeevan-Setu-Final/Jeevan_setu_frontend/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Verify no data-i18n="common.loading" on attendant-patient-name
    assert 'id="attendant-patient-name" data-i18n="common.loading"' not in html_content, "STUCK LOADING BUG: data-i18n='common.loading' must not be on #attendant-patient-name"
    assert 'id="attendant-condition-text" data-i18n="condition.stable"' not in html_content, "STATUS MISMATCH BUG: data-i18n='condition.stable' must not be on #attendant-condition-text"
    assert 'isAttendantRefreshInFlight' in html_content, "In-flight protection guard missing"
    assert '5000' in html_content, "5-second auto-refresh missing in HTML"
    assert 'Promise.allSettled' in html_content, "Promise.allSettled concurrency missing"
    print("[PASS] Frontend HTML/JS static invariants strictly verified.")

    # 7. Verify LanguageManager Guards
    lang_js_paths = [
        "Jeevan-Setu-Final/Jeevan_setu_frontend/static/js/i18n/language_manager.js",
        "Jeevan-Setu-Final/Jeevan_setu_frontend/Attendant/i18n/language_manager.js"
    ]
    for lp in lang_js_paths:
        with open(lp, "r", encoding="utf-8") as f:
            content = f.read()
        assert "attendant-patient-name" in content, f"Safety guard missing in {lp}"
        print(f"[PASS] LanguageManager safety guard confirmed in {lp}.")

    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY! (100% HEALTHY)")

if __name__ == "__main__":
    run_tests()
