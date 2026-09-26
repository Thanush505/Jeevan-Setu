import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database.db import db

app = create_app()

def test_database_routes():
    print("Testing DB direct queries...")
    try:
        patients = db.execute_query("SELECT * FROM patients LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(patients)} patients")
    except Exception as e:
        print(f"[FAIL] Patient query failed: {e}")

    try:
        vitals = db.execute_query("SELECT * FROM vitals LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(vitals)} vitals")
    except Exception as e:
        print(f"[FAIL] Vitals query failed: {e}")

    try:
        wards = db.execute_query("SELECT * FROM wards LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(wards)} wards")
    except Exception as e:
        print(f"[FAIL] Wards query failed: {e}")

    try:
        beds = db.execute_query("SELECT * FROM beds LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(beds)} beds")
    except Exception as e:
        print(f"[FAIL] Beds query failed: {e}")

    try:
        users = db.execute_query("SELECT * FROM users LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(users)} users")
    except Exception as e:
        print(f"[FAIL] Users query failed: {e}")

    try:
        nurses = db.execute_query("SELECT * FROM nurses LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(nurses)} nurses")
    except Exception as e:
        print(f"[FAIL] Nurses query failed: {e}")

    try:
        doctors = db.execute_query("SELECT * FROM doctors LIMIT 5", fetch=True)
        print(f"[OK] Fetched {len(doctors)} doctors")
    except Exception as e:
        print(f"[FAIL] Doctors query failed: {e}")

    print("\nTesting Blueprint endpoints...")
    with app.test_client() as client:
        # Test nurse search
        res = client.get('/patients/nurse-search?q=test')
        print(f"GET /patients/nurse-search: {res.status_code}")

        # Test ward list
        res = client.get('/api/v1/wards')
        print(f"GET /api/v1/wards: {res.status_code}")

        # Test bed list
        res = client.get('/api/v1/beds')
        print(f"GET /api/v1/beds: {res.status_code}")

        # Test vitals
        res = client.get('/api/v1/vitals/1')
        print(f"GET /api/v1/vitals/1: {res.status_code}")

if __name__ == '__main__':
    test_database_routes()
