import urllib.request
import urllib.parse
import json

BASE_URL = "http://127.0.0.1:5000"
AUTH_TOKEN = None

def login():
    global AUTH_TOKEN
    login_url = f"{BASE_URL}/api/v1/auth/login"
    payload = json.dumps({"username": "admin", "password": "admin123"}).encode('utf-8')
    req = urllib.request.Request(login_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        if res.get('success') and 'data' in res:
            AUTH_TOKEN = res['data'].get('token')
            print(f"[*] Successfully authenticated as Admin. Token acquired.")
        else:
            print("[!] Authentication failed:", res)


def get_json(url):
    headers = {"Accept": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            return json.loads(err_body)
        except Exception:
            return {"success": False, "error": str(e)}

def test_searches():
    login()

    print("==================================================")
    print("JEEVAN SETU — FULL SEARCH VERIFICATION TEST SUITE")
    print("==================================================")
    
    results = []
    
    # 1. Test Patient Search - Ravi Kumar variations
    test_cases_patient = [
        ("Ravi", "Patient search by partial first name"),
        ("Ravi Kumar", "Patient search by full name"),
        ("RAVI", "Case-insensitive patient search (uppercase)"),
        ("  ravi kumar  ", "Whitespace padded patient search"),
        ("P001", "Patient search by patient code"),
        ("ICU-01", "Patient search by bed number"),
        ("Septic", "Patient search by diagnosis"),
        ("Anita", "Patient B search (Anita Sharma)"),
        ("Suresh", "Patient C search (Suresh Menon)"),
        ("", "Empty search query (should return all admitted)"),
        ("XYZNONEXISTENT999", "Non-existent patient query (empty list)"),
        ("!@#$%^&*()", "Special characters query (safe handling)"),
    ]
    
    for query, desc in test_cases_patient:
        encoded = urllib.parse.quote(query)
        url = f"{BASE_URL}/api/v1/patients?status=admitted&search={encoded}"
        data = get_json(url)
        count = len(data.get('data', []))
        success = data.get('success', False)
        
        # Verify EWS integrity if Ravi Kumar is in results
        ews_verified = True
        if "Ravi" in query or "P001" in query or "ICU-01" in query or query == "":
            ravi = next((p for p in data.get('data', []) if "Ravi" in p.get('name', '')), None)
            if ravi:
                ews_score = ravi.get('ews_score')
                condition = ravi.get('condition')
                recommendation = ravi.get('recommendation')
                latest_vitals = ravi.get('latest_vitals')
                if ews_score is None or condition is None or recommendation is None:
                    ews_verified = False
        
        passed = success and ews_verified and (count == 0 if "NONEXISTENT" in query else count > 0)
        status = "PASS" if passed else "FAIL"
        results.append((desc, query, count, status))
        print(f"[{status}] {desc}: query='{query}' -> {count} results")
        if query == "Ravi Kumar" and count > 0:
            p = data['data'][0]
            print(f"       Details: {p['name']} (#{p.get('patient_code')}), Bed: {p.get('bed_number')}, EWS: {p.get('ews_score')}, Condition: {p.get('condition')}, Rec: {p.get('recommendation')}")

    # 2. Test User Search (Admin staff management)
    print("\n--- Testing User Search (Admin Role) ---")
    test_cases_user = [
        ("doctor", "User search by role 'doctor'"),
        ("nurse", "User search by role 'nurse'"),
        ("admin", "User search by username 'admin'"),
        ("Arjun", "User search by full name 'Dr. Arjun Mehta'"),
        ("Priya", "User search by nurse name 'Nurse Priya'"),
        ("Cardiology", "User search by department 'Cardiology'"),
        ("NONEXISTENT_USER", "Non-existent user query"),
    ]
    
    for query, desc in test_cases_user:
        encoded = urllib.parse.quote(query)
        url = f"{BASE_URL}/api/v1/users?search={encoded}"
        data = get_json(url)
        count = len(data.get('data', []))
        success = data.get('success', False)
        passed = success and (count == 0 if "NONEXISTENT" in query else count > 0)
        status = "PASS" if passed else "FAIL"
        results.append((desc, query, count, status))
        print(f"[{status}] {desc}: query='{query}' -> {count} results")

    # 3. Test Audit Log Search
    print("\n--- Testing Audit Log Search (Doctor & Admin Roles) ---")
    test_cases_audit = [
        ("login", "Audit search for login actions"),
        ("vitals", "Audit search for vitals actions"),
        ("Dr.", "Audit search by username/doctor"),
        ("", "Empty audit search query"),
    ]
    
    for query, desc in test_cases_audit:
        encoded = urllib.parse.quote(query)
        url = f"{BASE_URL}/api/v1/reports/audit-logs?search={encoded}"
        data = get_json(url)
        count = len(data.get('data', []))
        success = data.get('success', False)
        status = "PASS" if success else "FAIL"
        results.append((desc, query, count, status))
        print(f"[{status}] {desc}: query='{query}' -> {count} results")

    # 4. Test Attendant View API (Attendant Role)
    print("\n--- Testing Attendant View (Attendant Role) ---")
    attendant_url = f"{BASE_URL}/api/v1/attendant/view?patient_id=1"
    attendant_data = get_json(attendant_url)
    att_success = attendant_data.get('success', False)
    att_patient = attendant_data.get('data', {})
    att_condition = att_patient.get('condition')
    att_score = att_patient.get('total_score')
    att_status = "PASS" if att_success and att_condition is not None else "FAIL"
    print(f"[{att_status}] Attendant View Patient #1 (Ravi Kumar): Condition='{att_condition}', EWS={att_score}")

    print("\n==================================================")
    total_tests = len(results) + 1
    passed_tests = sum(1 for r in results if r[3] == "PASS") + (1 if att_status == "PASS" else 0)
    print(f"SUMMARY: {passed_tests}/{total_tests} Tests Passed.")
    print("==================================================")

if __name__ == "__main__":
    test_searches()
