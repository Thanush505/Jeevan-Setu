import urllib.request
import json
import urllib.parse

BASE_URL = 'http://127.0.0.1:5000'

def post_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

def get_json(url):
    req = urllib.request.Request(url, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

print("=== TESTING MANUAL ATTENDANT LOGIN & SEARCH APIS ===")

# 1. Search patients by query
status, res = get_json(f"{BASE_URL}/api/v1/attendant/search-patients?q=Rajesh")
print(f"1. Search Patients 'Rajesh' (Status {status}):", res)
assert status == 200 and res.get('success'), "Search patients failed"

# 2. Manual Login with Patient Name + Attendant Name
status, res = post_json(f"{BASE_URL}/api/v1/attendant/manual-login", {
    "patient_name": "Rajesh Kumar",
    "attendant_name": "Suman Kumar",
    "relationship": "Spouse"
})
print(f"2. Manual Login 'Rajesh Kumar' + 'Suman Kumar' (Status {status}):", res)
assert status == 200 and res.get('success'), "Manual login failed"
assert 'access_token' in res, "Missing access token"
token = res['access_token']

# 3. Access Attendant Patient Dashboard with token
req = urllib.request.Request(f"{BASE_URL}/api/v1/attendant/patient", headers={
    'Content-Type': 'application/json',
    'Authorization': f"Bearer {token}"
})
with urllib.request.urlopen(req) as r:
    dash_data = json.loads(r.read().decode('utf-8'))
print(f"3. Fetch Attendant Patient View: {dash_data['data']['name']} | Condition: {dash_data['data']['condition']}")
assert dash_data['success'], "Failed to fetch patient data"

# 4. Manual Login with UHID
status, res_uhid = post_json(f"{BASE_URL}/api/v1/attendant/manual-login", {
    "patient_name": "UHID-2026-00001",
    "attendant_name": "Anita Sharma",
    "relationship": "Daughter"
})
print(f"4. Manual Login with UHID (Status {status}):", res_uhid.get('patient_name'), "| ID:", res_uhid.get('patient_id'))
assert status == 200 and res_uhid.get('success'), "Manual login via UHID failed"

# 5. Invalid / Non-existent Patient Name
status, res_invalid = post_json(f"{BASE_URL}/api/v1/attendant/manual-login", {
    "patient_name": "NonExistentPatient999",
    "attendant_name": "Tester"
})
print(f"5. Non-existent patient handling (Status {status}):", res_invalid.get('error'))
assert status == 404, "Should return 404 for non-existent patient"

# 6. HTML page loads
with urllib.request.urlopen(f"{BASE_URL}/Attendant/attendant_access.html") as r:
    content = r.read().decode('utf-8')
    assert "Manual Login" in content and "QR Code Access" in content
    print("6. attendant_access.html loads with both Manual Login and QR Access tabs (200 OK)")

print("\nALL MANUAL ATTENDANT LOGIN & QR TESTS PASSED PERFECTLY!")
