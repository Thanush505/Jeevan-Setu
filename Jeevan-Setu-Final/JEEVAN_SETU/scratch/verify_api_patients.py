import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models.user_model import User
from services.auth_service import AuthService

def verify_api():
    app = create_app()
    client = app.test_client()

    admin = User.get_by_id(1)
    token = AuthService.generate_access_token(admin)['access_token']

    res = client.get('/api/v1/patients', headers={'Authorization': f'Bearer {token}'})
    data = res.get_json()
    print("API Status:", res.status_code)
    print("Success:", data.get('success'))
    patients = data.get('data', [])
    print(f"Total returned by API: {len(patients)}")
    for p in patients:
        print(f"Patient ID {p['patient_id']} ({p['patient_code']}) | Name: {p['name']} | EWS: {p.get('ews_score')} | Condition: {p.get('condition')} | Rec: {p.get('recommendation')}")

if __name__ == '__main__':
    verify_api()
