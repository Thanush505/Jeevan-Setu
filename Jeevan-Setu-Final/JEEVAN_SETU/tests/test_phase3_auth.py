"""
tests/test_phase3_auth.py — Comprehensive Test Suite for Phase 3 Authentication.
Tests:
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- POST /api/v1/auth/forgot-password
- POST /api/v1/auth/reset-password
- GET  /api/v1/auth/me
- Password hashing & verification
- Account status checking (active vs deactivated)
- Token revocation and blacklist
- Auth middleware & role permissions
"""

import sys
import os
import unittest
import json
from datetime import datetime

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User, hash_pw, verify_pw
from services.auth_service import AuthService


class TestPhase3Authentication(unittest.TestCase):
    """Test suite for Phase 3 REST Authentication endpoints and service layers."""

    @classmethod
    def setUpClass(cls):
        """Configure test app client and ensure test users exist."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Seed clean test users
        cls.test_username = f"authtest_doc_{int(datetime.now().timestamp())}"
        cls.test_email = f"{cls.test_username}@testmed.com"
        cls.test_password = "DoctorPassword@123"

        cls.user_id = User.create(
            username=cls.test_username,
            password=cls.test_password,
            full_name="Dr. Test Authenticator",
            email=cls.test_email,
            role='doctor',
            department='Critical Care'
        )

    def test_01_password_hashing_and_verification(self):
        """Test secure hashing and verification logic."""
        raw_pw = "SuperSecure#2026"
        hashed = hash_pw(raw_pw)
        self.assertNotEqual(raw_pw, hashed)
        self.assertTrue(verify_pw(raw_pw, hashed))
        self.assertFalse(verify_pw("WrongPassword", hashed))
        print("[PASS] Password hashing & verification verified.")

    def test_02_login_success_and_token_generation(self):
        """Test POST /api/v1/auth/login with valid credentials."""
        payload = {
            'username': self.test_username,
            'password': self.test_password
        }
        res = self.client.post('/api/v1/auth/login', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('token', data['data'])
        self.assertEqual(data['data']['user']['username'], self.test_username)
        self.assertEqual(data['data']['user']['role'], 'doctor')
        self.assertIn('permissions', data['data']['user'])

        # Store token for subsequent tests
        self.__class__.valid_token = data['data']['token']
        print("[PASS] Login success and JWT token generation verified.")

    def test_03_login_validation_and_failures(self):
        """Test POST /api/v1/auth/login invalid credentials and missing fields."""
        # Missing fields
        res = self.client.post('/api/v1/auth/login', json={})
        self.assertEqual(res.status_code, 400)

        # Invalid password
        res = self.client.post('/api/v1/auth/login', json={
            'username': self.test_username,
            'password': 'WrongPassword123'
        })
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json()['success'])

        # Nonexistent user
        res = self.client.post('/api/v1/auth/login', json={
            'username': 'nonexistent_user_99999',
            'password': 'SomePassword123'
        })
        self.assertEqual(res.status_code, 401)
        print("[PASS] Login validation and failure cases verified.")

    def test_04_get_auth_me(self):
        """Test GET /api/v1/auth/me with Bearer token."""
        headers = {'Authorization': f"Bearer {self.valid_token}"}
        res = self.client.get('/api/v1/auth/me', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['username'], self.test_username)
        self.assertEqual(data['data']['email'], self.test_email)

        # Test without header
        res_no_auth = self.client.get('/api/v1/auth/me')
        self.assertEqual(res_no_auth.status_code, 401)
        print("[PASS] GET /api/v1/auth/me with Bearer JWT verified.")

    def test_05_forgot_password_and_reset_flow(self):
        """Test POST /api/v1/auth/forgot-password and POST /api/v1/auth/reset-password."""
        # 1. Request password reset
        res = self.client.post('/api/v1/auth/forgot-password', json={
            'email': self.test_email
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        reset_token = data['data']['reset_token']
        self.assertIsNotNone(reset_token)

        # 2. Reset password using token
        new_pw = "NewDoctorPassword@456"
        res_reset = self.client.post('/api/v1/auth/reset-password', json={
            'token': reset_token,
            'new_password': new_pw
        })
        self.assertEqual(res_reset.status_code, 200)
        self.assertTrue(res_reset.get_json()['success'])

        # 3. Verify token cannot be reused
        res_reuse = self.client.post('/api/v1/auth/reset-password', json={
            'token': reset_token,
            'new_password': "AnotherPassword@789"
        })
        self.assertEqual(res_reuse.status_code, 400)

        # 4. Verify login with new password
        res_login_new = self.client.post('/api/v1/auth/login', json={
            'username': self.test_username,
            'password': new_pw
        })
        self.assertEqual(res_login_new.status_code, 200)
        self.assertTrue(res_login_new.get_json()['success'])
        print("[PASS] Forgot-password & Reset-password lifecycle verified.")

    def test_06_account_status_deactivation(self):
        """Test deactivated accounts are rejected during login and token validation."""
        # Deactivate user
        User.delete(self.user_id)

        # Try to login with deactivated user
        res = self.client.post('/api/v1/auth/login', json={
            'username': self.test_username,
            'password': "NewDoctorPassword@456"
        })
        self.assertEqual(res.status_code, 403)
        self.assertIn('deactivated', res.get_json()['error'].lower())

        # Reactivate for cleanup
        User.update(self.user_id, is_active=True)
        print("[PASS] Account deactivation checking verified.")

    def test_07_logout_and_token_revocation(self):
        """Test POST /api/v1/auth/logout revokes the JWT token."""
        # Get a fresh token
        login_res = self.client.post('/api/v1/auth/login', json={
            'username': self.test_username,
            'password': "NewDoctorPassword@456"
        })
        token_to_logout = login_res.get_json()['data']['token']

        # Logout
        headers = {'Authorization': f"Bearer {token_to_logout}"}
        res = self.client.post('/api/v1/auth/logout', headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify token is now blacklisted when calling /me
        res_after = self.client.get('/api/v1/auth/me', headers=headers)
        self.assertEqual(res_after.status_code, 401)
        self.assertIn('revoked', res_after.get_json()['error'].lower())
        print("[PASS] Logout and token revocation blacklist verified.")


if __name__ == '__main__':
    print("=" * 60)
    print("Running Jeevan Setu Phase 3 Authentication Tests...")
    print("=" * 60)
    unittest.main(verbosity=2)
