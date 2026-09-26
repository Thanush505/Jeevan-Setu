"""
tests/test_user_creation_workflow.py — Automated verification of Add User workflow & RBAC.
"""

import unittest
import json
from app import create_app
from database.db import db
from models.user_model import User


class TestUserCreationWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        # Login as Admin to obtain JWT token
        res = cls.client.post('/api/v1/auth/login', json={
            'username': 'admin_js',
            'password': 'Admin@123'
        })
        assert res.status_code == 200, f"Admin login failed: {res.get_json()}"
        cls.admin_token = res.get_json()['data']['token']
        cls.admin_headers = {
            'Authorization': f'Bearer {cls.admin_token}',
            'Content-Type': 'application/json'
        }

    def test_01_roles_summary_endpoint(self):
        """Test GET /api/v1/users/roles-summary returns roles, counts, departments, and wards."""
        res = self.client.get('/api/v1/users/roles-summary', headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('roles', data['data'])
        self.assertIn('departments', data['data'])
        self.assertIn('wards', data['data'])

        role_names = [r['name'] for r in data['data']['roles']]
        self.assertIn('doctor', role_names)
        self.assertIn('nurse', role_names)
        self.assertIn('admin', role_names)
        self.assertIn('attendant', role_names)

    def test_02_create_doctor_account_and_login(self):
        """Test Admin creates a new Doctor account and Doctor can log in immediately."""
        doc_username = f"dr_workflow_test_{User.get_all(include_inactive=True).__len__() + 1}"
        doc_payload = {
            'full_name': 'Dr. Vikram Malhotra',
            'email': f'{doc_username}@hospital.org',
            'username': doc_username,
            'password': 'DoctorPass123!',
            'confirm_password': 'DoctorPass123!',
            'role': 'doctor',
            'department': 'Cardiology',
            'specialization': 'Interventional Cardiology',
            'license_number': f'MCI-{doc_username}',
            'qualification': 'MBBS, MD, DM',
            'experience_years': 10,
            'is_active': True
        }

        res = self.client.post('/api/v1/users', json=doc_payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        created_user_id = data['data']['user_id']
        self.assertIsNotNone(created_user_id)

        # Verify DB records
        user_row = db.execute_query("SELECT * FROM users WHERE user_id = %s", (created_user_id,), fetch=True)
        self.assertTrue(len(user_row) > 0)
        self.assertEqual(user_row[0]['role'], 'doctor')

        doc_row = db.execute_query("SELECT * FROM doctors WHERE user_id = %s", (created_user_id,), fetch=True)
        self.assertTrue(len(doc_row) > 0)
        self.assertEqual(doc_row[0]['specialization'], 'Interventional Cardiology')
        self.assertEqual(doc_row[0]['license_number'], f'MCI-{doc_username}')

        # Test login with newly created doctor credentials
        login_res = self.client.post('/api/v1/auth/login', json={
            'username': doc_username,
            'password': 'DoctorPass123!'
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data['success'])
        self.assertEqual(login_data['data']['user']['role'], 'doctor')

    def test_03_create_nurse_account_and_login(self):
        """Test Admin creates a new Nurse account and Nurse can log in immediately."""
        nurse_username = f"nurse_workflow_test_{User.get_all(include_inactive=True).__len__() + 1}"
        nurse_payload = {
            'full_name': 'Ananya Sharma, RN',
            'email': f'{nurse_username}@hospital.org',
            'username': nurse_username,
            'password': 'NursePass123!',
            'confirm_password': 'NursePass123!',
            'role': 'nurse',
            'department': 'Critical Care / ICU',
            'specialization': 'ICU Nursing',
            'license_number': f'INC-{nurse_username}',
            'qualification': 'B.Sc Nursing',
            'ward_assignment': 'ICU',
            'shift': 'Night',
            'experience_years': 4,
            'is_active': True
        }

        res = self.client.post('/api/v1/users', json=nurse_payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        created_user_id = data['data']['user_id']

        # Verify DB records
        user_row = db.execute_query("SELECT * FROM users WHERE user_id = %s", (created_user_id,), fetch=True)
        self.assertTrue(len(user_row) > 0)
        self.assertEqual(user_row[0]['role'], 'nurse')

        nurse_row = db.execute_query("SELECT * FROM nurses WHERE user_id = %s", (created_user_id,), fetch=True)
        self.assertTrue(len(nurse_row) > 0)
        self.assertEqual(nurse_row[0]['ward_assignment'], 'ICU')
        self.assertEqual(nurse_row[0]['shift'], 'Night')

        # Test login with newly created nurse credentials
        login_res = self.client.post('/api/v1/auth/login', json={
            'username': nurse_username,
            'password': 'NursePass123!'
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data['success'])
        self.assertEqual(login_data['data']['user']['role'], 'nurse')

    def test_04_validation_errors(self):
        """Test duplicate username/email and password mismatch errors."""
        # 1. Duplicate username
        res = self.client.post('/api/v1/users', json={
            'full_name': 'Duplicate User',
            'email': 'unique_email_123@hospital.org',
            'username': 'admin_js', # Existing username
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'admin'
        }, headers=self.admin_headers)
        self.assertEqual(res.status_code, 422)

        # 2. Password mismatch
        res_mismatch = self.client.post('/api/v1/users', json={
            'full_name': 'Test User',
            'email': 'unique_user_456@hospital.org',
            'username': 'test_unique_user_456',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword123!',
            'role': 'admin'
        }, headers=self.admin_headers)
        self.assertEqual(res_mismatch.status_code, 422)
        self.assertIn('do not match', res_mismatch.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
