import urllib.request
import json

BASE_URL = "http://127.0.0.1:5000"

# 1. Login
req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", 
    data=json.dumps({"username": "admin", "password": "admin123"}).encode('utf-8'),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    token = res['token']

# 2. Query /api/v1/patients
req2 = urllib.request.Request(f"{BASE_URL}/api/v1/patients", headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req2) as resp:
    res2 = json.loads(resp.read().decode('utf-8'))
    print("PATIENTS RESPONSE:", json.dumps(res2, indent=2))

# 3. Query /api/v1/users
req3 = urllib.request.Request(f"{BASE_URL}/api/v1/users", headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req3) as resp:
    res3 = json.loads(resp.read().decode('utf-8'))
    print("USERS RESPONSE:", json.dumps(res3, indent=2))
