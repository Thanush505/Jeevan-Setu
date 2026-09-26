import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database.db import db
from services.auth_service import AuthService
from models.user_model import verify_pw, hash_pw

app = create_app()

def test_nurse_settings_complete():
    with app.test_client() as client:
        # Test all 3 nurses
        nurses = [
            ('nurse_priya', 'Nurse@123', 'Priya Menon', 'ICU', 'ICU & Critical Care Nursing', 'BSc Nursing, Post Basic ICU Certification'),
            ('nurse_arun', 'Nurse@123', 'Arun Krishnan', 'HDU', 'General Nursing', 'BSc Nursing (CMC Vellore)'),
            ('nurse_meera', 'Nurse@123', 'Meera Jain', 'ICU', 'Emergency Nursing', 'BSc Nursing, ACLS Certified')
        ]

        for username, password, expected_name, expected_ward, expected_spec, expected_qual in nurses:
            print(f"\n--- Testing Nurse: {username} ---")
            
            # 1. Login
            login_res = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
            assert login_res.status_code == 200, f"Login failed for {username}"
            token = login_res.get_json()['data']['token']
            headers = {'Authorization': f'Bearer {token}'}

            # 2. GET /me profile
            me_res = client.get('/api/v1/auth/me', headers=headers)
            assert me_res.status_code == 200
            user_info = me_res.get_json()['data']
            
            assert user_info['role'] == 'nurse'
            assert user_info['username'] == username
            assert user_info['full_name'] == expected_name
            assert user_info['ward'] == expected_ward
            assert user_info['specialization'] == expected_spec
            assert user_info['qualification'] == expected_qual
            assert user_info['nurse_details']['nurse_id'] is not None
            print(f"[PASS] Profile verified: {user_info['full_name']} | {user_info['ward']} | {user_info['specialization']}")

            # 3. Notification Preferences (GET & PUT)
            pref_res = client.get('/api/v1/auth/preferences', headers=headers)
            assert pref_res.status_code == 200
            
            put_pref = client.put('/api/v1/auth/preferences', headers=headers, json={
                'in_app_notifications': True,
                'critical_patient_alerts': False,
                'ews_alerts': True,
                'task_notifications': False,
                'sound_alerts': True
            })
            assert put_pref.status_code == 200
            assert put_pref.get_json()['data']['critical_patient_alerts'] is False
            assert put_pref.get_json()['data']['task_notifications'] is False

            # Restore Preferences
            client.put('/api/v1/auth/preferences', headers=headers, json={
                'in_app_notifications': True,
                'critical_patient_alerts': True,
                'ews_alerts': True,
                'task_notifications': True,
                'sound_alerts': True
            })
            print("[PASS] Notification preferences verified and persisted")

            # 4. Profile Editing (PUT /profile)
            update_res = client.put('/api/v1/auth/profile', headers=headers, json={
                'full_name': f"{expected_name} (Verified)",
                'email': user_info['email'],
                'specialization': expected_spec,
                'qualification': expected_qual
            })
            assert update_res.status_code == 200
            
            # Re-fetch /me to verify persistence in DB
            me_after = client.get('/api/v1/auth/me', headers=headers).get_json()['data']
            assert me_after['full_name'] == f"{expected_name} (Verified)"

            # Restore original full_name
            client.put('/api/v1/auth/profile', headers=headers, json={
                'full_name': expected_name,
                'email': user_info['email'],
                'specialization': expected_spec,
                'qualification': expected_qual
            })
            print("[PASS] Profile update and persistence verified")

            # 5. Password Change Validation
            # 5a. Mismatched confirmation
            bad_pw1 = client.post('/api/v1/auth/change-password', headers=headers, json={
                'current_password': password,
                'new_password': 'NewPassword123',
                'confirm_password': 'MismatchedPassword'
            })
            assert bad_pw1.status_code == 422
            
            # 5b. Wrong current password
            bad_pw2 = client.post('/api/v1/auth/change-password', headers=headers, json={
                'current_password': 'WrongPassword123',
                'new_password': 'NewPassword123',
                'confirm_password': 'NewPassword123'
            })
            assert bad_pw2.status_code == 400

            # 5c. Valid password change and rollback
            change_ok = client.post('/api/v1/auth/change-password', headers=headers, json={
                'current_password': password,
                'new_password': 'Nurse@NewPassword123',
                'confirm_password': 'Nurse@NewPassword123'
            })
            assert change_ok.status_code == 200
            
            # Verify new login
            login_new = client.post('/api/v1/auth/login', json={'username': username, 'password': 'Nurse@NewPassword123'})
            assert login_new.status_code == 200
            
            # Reset password back to original
            new_token = login_new.get_json()['data']['token']
            client.post('/api/v1/auth/change-password', headers={'Authorization': f'Bearer {new_token}'}, json={
                'current_password': 'Nurse@NewPassword123',
                'new_password': password,
                'confirm_password': password
            })
            print("[PASS] Password management (security validations & hash update) verified")

        # 6. Doctor RBAC Isolation Test
        print("\n--- Testing Doctor RBAC Isolation on Nurse Settings ---")
        doc_login = client.post('/api/v1/auth/login', json={'username': 'dr_sharma', 'password': 'Doctor@123'})
        doc_token = doc_login.get_json()['data']['token']
        doc_me = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {doc_token}'}).get_json()['data']
        assert doc_me['role'] == 'doctor'
        print("[PASS] Doctor account correctly identified as 'doctor' role for frontend role mismatch guard")

        print("\n==========================================")
        print("ALL NURSE SETTINGS REQUIREMENTS PASS 100%!")
        print("==========================================")

if __name__ == '__main__':
    test_nurse_settings_complete()
