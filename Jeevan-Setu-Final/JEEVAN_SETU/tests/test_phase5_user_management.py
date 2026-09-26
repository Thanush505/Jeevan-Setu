"""
tests/test_phase5_user_management.py — Comprehensive Test Suite for Phase 5 User Management.
Tests:
- GET    /users & /api/v1/users (List, paginate, search, filter by role/status)
- GET    /users/{id} (Single user lookup)
- POST   /users (Create user with role assignment & validation)
- PUT    /users/{id} (Update user details & duplicate prevention)
- DELETE /users/{id} (Deactivate user & self-deactivation prevention)
- PATCH  /users/{id}/status (Update user active status)
- POST   /users/{id}/reset-password (Admin password reset)
- RBAC protection (403 Forbidden for non-admins)
"""

import sys
import os
import unittest
from datetime import datetime

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService


class TestPhase5UserManagement(unittest.TestCase):
    """Test suite for Phase 5 Administrator User Management APIs."""

    @classmethod
    def setUpClass(cls):
        """Configure test client and create tokens for admin, doctor, and nurse."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(datetime.now().timestamp())

        # Admin Token
        admin_user = User.authenticate('admin', 'admin123')
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

        # Doctor Token (Non-admin)
        doc_id = User.create(
            username=f"p5_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. P5 Test",
            email=f"p5_doc_{ts}@test.com",
            role='doctor',
            department='Cardiology'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Unique prefix for created test users
        cls.test_prefix = f"u_{ts}"

    def test_01_create_user_and_validation(self):
        """Test POST /users (Create user, validate role, uniqueness, and password)."""
        uname = f"{self.test_prefix}_nurse"
        email = f"{uname}@hospital.com"

        # 1. Successful user creation
        payload = {
            'username': uname,
            'password': 'NursePass123!',
            'full_name': 'Sister Mary',
            'email': email,
            'role': 'nurse',
            'department': 'ICU Ward 2'
        }
        res = self.client.post('/api/v1/users', json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['username'], uname)
        self.assertEqual(data['data']['role'], 'nurse')

        self.__class__.created_user_id = data['data']['id']

        # 2. Reject duplicate username
        res_dup_uname = self.client.post('/api/v1/users', json=payload, headers=self.admin_headers)
        self.assertEqual(res_dup_uname.status_code, 422)

        # 3. Reject invalid role
        res_bad_role = self.client.post('/api/v1/users', json={
            'username': f"{uname}_2",
            'password': 'Password123!',
            'full_name': 'Test User',
            'email': f"{uname}_2@hospital.com",
            'role': 'super_manager_invalid'
        }, headers=self.admin_headers)
        self.assertEqual(res_bad_role.status_code, 422)
        print("[PASS] User creation and input validations verified.")

    def test_02_get_user_by_id(self):
        """Test GET /users/{id} (Fetch single user)."""
        res = self.client.get(f"/api/v1/users/{self.created_user_id}", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['id'], self.created_user_id)
        self.assertNotIn('password_hash', data['data'])

        # 404 on nonexistent user
        res_404 = self.client.get("/api/v1/users/999999", headers=self.admin_headers)
        self.assertEqual(res_404.status_code, 404)
        print("[PASS] GET /users/{id} verified.")

    def test_03_list_search_and_filter_users(self):
        """Test GET /users with search, role filter, status filter, and pagination."""
        # 1. List users with pagination
        res = self.client.get('/api/v1/users?page=1&limit=5', headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('pagination', data)
        self.assertGreaterEqual(data['pagination']['total'], 1)

        # 2. Filter by role
        res_role = self.client.get('/api/v1/users?role=nurse', headers=self.admin_headers)
        self.assertEqual(res_role.status_code, 200)
        users = res_role.get_json()['data']
        for u in users:
            self.assertEqual(u['role'], 'nurse')

        # 3. Search query
        res_search = self.client.get(f'/api/v1/users?search={self.test_prefix}', headers=self.admin_headers)
        self.assertEqual(res_search.status_code, 200)
        self.assertGreaterEqual(len(res_search.get_json()['data']), 1)
        print("[PASS] User search, filtering, and pagination verified.")

    def test_04_update_user(self):
        """Test PUT /users/{id} (Update user profile, role, and department)."""
        update_payload = {
            'full_name': 'Senior Sister Mary Updated',
            'department': 'HDU Step-Down',
            'role': 'nurse'
        }
        res = self.client.put(f"/api/v1/users/{self.created_user_id}", json=update_payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['full_name'], 'Senior Sister Mary Updated')
        self.assertEqual(data['data']['department'], 'HDU Step-Down')
        print("[PASS] PUT /users/{id} user updates verified.")

    def test_05_update_user_status_and_deactivation(self):
        """Test PATCH /users/{id}/status and DELETE /users/{id}."""
        # 1. Deactivate user via PATCH
        res_patch = self.client.patch(
            f"/api/v1/users/{self.created_user_id}/status",
            json={'is_active': False},
            headers=self.admin_headers
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertFalse(res_patch.get_json()['data']['is_active'])

        # 2. Activate user via PATCH
        res_activate = self.client.patch(
            f"/api/v1/users/{self.created_user_id}/status",
            json={'is_active': True},
            headers=self.admin_headers
        )
        self.assertEqual(res_activate.status_code, 200)
        self.assertTrue(res_activate.get_json()['data']['is_active'])

        # 3. Deactivate user via DELETE
        res_delete = self.client.delete(f"/api/v1/users/{self.created_user_id}", headers=self.admin_headers)
        self.assertEqual(res_delete.status_code, 200)
        user = User.get_by_id(self.created_user_id)
        self.assertFalse(user.is_active)

        # 4. Self-deactivation prevention for admin
        admin_user = User.authenticate('admin', 'admin123')
        res_self = self.client.delete(f"/api/v1/users/{admin_user.id}", headers=self.admin_headers)
        self.assertEqual(res_self.status_code, 400)
        print("[PASS] User status PATCH, DELETE, and self-deactivation protection verified.")

    def test_06_admin_reset_password(self):
        """Test POST /users/{id}/reset-password (Admin direct password reset)."""
        # Reactivate user first
        User.set_status(self.created_user_id, True)

        new_password = "BrandNewSecurePassword#2026"
        res = self.client.post(
            f"/api/v1/users/{self.created_user_id}/reset-password",
            json={'new_password': new_password},
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify user can authenticate with new password
        u_obj = User.get_by_id(self.created_user_id)
        authenticated = User.authenticate(u_obj.username, new_password)
        self.assertIsNotNone(authenticated)
        print("[PASS] Admin direct password reset verified.")

    def test_07_rbac_protection_for_non_admins(self):
        """Test non-admin users (Doctor/Nurse) receive 403 Forbidden on User Management APIs."""
        # Doctor tries to list users
        res_list = self.client.get('/api/v1/users', headers=self.doctor_headers)
        self.assertEqual(res_list.status_code, 403)

        # Doctor tries to create user
        res_create = self.client.post('/api/v1/users', json={'username': 'illegal_user'}, headers=self.doctor_headers)
        self.assertEqual(res_create.status_code, 403)

        # Doctor tries to delete user
        res_delete = self.client.delete(f"/api/v1/users/{self.created_user_id}", headers=self.doctor_headers)
        self.assertEqual(res_delete.status_code, 403)
        print("[PASS] RBAC protection: 403 Forbidden verified for non-admin users.")


if __name__ == '__main__':
    print("=" * 60)
    print("Running Jeevan Setu Phase 5 User Management Tests...")
    print("=" * 60)
    unittest.main(verbosity=2)
