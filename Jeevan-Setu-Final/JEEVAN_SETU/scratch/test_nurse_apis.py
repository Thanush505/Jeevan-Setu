import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database.db import db
from services.auth_service import AuthService

app = create_app()

def test_nurse_flow():
    with app.test_client() as client:
        # Test all 3 nurses
        nurses = [
            ('nurse_priya', 'Nurse@123'),
            ('nurse_arun', 'Nurse@123'),
            ('nurse_meera', 'Nurse@123')
        ]
        for n_username, pwd in nurses:
            print(f"\n================ Testing Nurse: {n_username} ================")
            # 1. Login via API
            login_res = client.post('/api/v1/auth/login', json={
                'username': n_username,
                'password': pwd
            })
            print("Login Status:", login_res.status_code)
            login_data = login_res.get_json()
            if not login_data or not login_data.get('success'):
                print("Login failed:", login_data)
                continue
            
            token = login_data['data']['token']
            headers = {'Authorization': f'Bearer {token}'}

            # 2. GET /api/v1/auth/me
            me_res = client.get('/api/v1/auth/me', headers=headers)
            print("GET /me Status:", me_res.status_code)
            me_data = me_res.get_json()
            user_data = me_data['data']
            print(f"Name: {user_data['full_name']}, Role: {user_data['role']}, Ward: {user_data['ward']}, Spec: {user_data['specialization']}, Qual: {user_data['qualification']}")
            
            assert user_data['role'] == 'nurse', "Role must be nurse"
            assert user_data['username'] == n_username, "Username must match"
            assert user_data['ward'] is not None, "Ward must not be None"
            assert user_data['nurse_details'] is not None, "Nurse details must exist"
            
            # 3. GET /api/v1/auth/preferences
            pref_res = client.get('/api/v1/auth/preferences', headers=headers)
            print("GET /preferences Status:", pref_res.status_code)
            pref_data = pref_res.get_json()

            # 4. PUT /api/v1/auth/preferences
            put_pref_res = client.put('/api/v1/auth/preferences', headers=headers, json={
                'in_app_notifications': True,
                'critical_patient_alerts': False,
                'ews_alerts': True,
                'task_notifications': True,
                'sound_alerts': False
            })
            print("PUT /preferences Status:", put_pref_res.status_code)
            assert put_pref_res.get_json()['data']['critical_patient_alerts'] is False
            assert put_pref_res.get_json()['data']['sound_alerts'] is False

            # Reset preferences
            client.put('/api/v1/auth/preferences', headers=headers, json={
                'in_app_notifications': True,
                'critical_patient_alerts': True,
                'ews_alerts': True,
                'task_notifications': True,
                'sound_alerts': True
            })

            # 5. PUT /api/v1/auth/profile
            orig_name = user_data['full_name']
            orig_spec = user_data['specialization'] or ''
            orig_qual = user_data['qualification'] or ''
            orig_email = user_data['email']

            update_res = client.put('/api/v1/auth/profile', headers=headers, json={
                'full_name': orig_name,
                'email': orig_email,
                'specialization': orig_spec,
                'qualification': orig_qual
            })
            print("PUT /profile Status:", update_res.status_code)
            assert update_res.status_code == 200

        print("\nAll 3 Nurses verified successfully!")

if __name__ == '__main__':
    test_nurse_flow()
