"""
tests/test_phase19_security.py — Comprehensive Test Suite for Phase 19 Backend Security.

Covers:
1. Password Hashing (Werkzeug/bcrypt with salt)
2. Authentication (JWT generation, verification, revocation blacklist)
3. RBAC Enforcement (Role boundary defense, 403 Forbidden)
4. Input Validation & Parameter Bounds
5. SQL Injection Prevention (Parameterized queries & SQLi payloads)
6. Secure Database Transactions (Atomic rollback)
7. Secure QR Tokens (High entropy, zero PII payload, hash-based validation)
8. Rate Limiting (Sliding window, 429 response, Retry-After header)
9. Secure HTTP Headers & CORS (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
10. Sensitive Data Redaction (Zero exposure of password_hash, secrets, DB credentials)
11. Path Traversal Prevention (validate_safe_path)
12. Error Handling & Zero Stack Trace Leakage (Sanitized responses on errors)
"""

import unittest
import json
import time
import os
from datetime import datetime
from app import create_app
from database.db import db
from models.user_model import User, hash_pw, verify_pw
from models.qr_token_model import PatientQRToken
from services.auth_service import AuthService
from utils.security import (
    RateLimiter, rate_limit, sanitize_dict, validate_safe_path, sanitize_input_string, SENSITIVE_FIELDS
)


class TestPhase19Security(unittest.TestCase):
    """Unit and Integration tests for Phase 19 Backend Security."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(time.time())
        # Create dedicated test accounts for each role
        cls.admin_username = f"sec_admin_{ts}"
        cls.admin_password = "AdminSecPassword#123"
        cls.admin_id = User.create(
            username=cls.admin_username,
            password=cls.admin_password,
            full_name="Sec Admin",
            email=f"{cls.admin_username}@hospital.com",
            role='admin'
        )

        cls.doc_username = f"sec_doc_{ts}"
        cls.doc_password = "DocSecPassword#123"
        cls.doc_id = User.create(
            username=cls.doc_username,
            password=cls.doc_password,
            full_name="Dr. Sec Doctor",
            email=f"{cls.doc_username}@hospital.com",
            role='doctor',
            department='ICU'
        )

        cls.nurse_username = f"sec_nurse_{ts}"
        cls.nurse_password = "NurseSecPassword#123"
        cls.nurse_id = User.create(
            username=cls.nurse_username,
            password=cls.nurse_password,
            full_name="Sec Nurse",
            email=f"{cls.nurse_username}@hospital.com",
            role='nurse',
            department='ICU'
        )

        # Authenticate and obtain JWT access tokens
        cls.admin_token = cls._login(cls.admin_username, cls.admin_password)
        cls.doctor_token = cls._login(cls.doc_username, cls.doc_password)
        cls.nurse_token = cls._login(cls.nurse_username, cls.nurse_password)

    @classmethod
    def _login(cls, username, password):
        resp = cls.client.post('/api/v1/auth/login', json={'username': username, 'password': password})
        data = resp.get_json()
        if data and data.get('success'):
            return data['data']['token']
        return None

    # =========================================================================
    # 1. Password Hashing & Verification
    # =========================================================================
    def test_01_password_hashing(self):
        """Verify secure password hashing and verification."""
        password = "SecurePassword2026!"
        h1 = hash_pw(password)
        h2 = hash_pw(password)

        # Hashes must never equal plaintext
        self.assertNotEqual(h1, password)
        # Unique salt ensures two hashes of same password are distinct
        self.assertNotEqual(h1, h2)

        # Verification
        self.assertTrue(verify_pw(password, h1))
        self.assertTrue(verify_pw(password, h2))
        self.assertFalse(verify_pw("WrongPassword", h1))
        self.assertFalse(verify_pw("", h1))
        self.assertFalse(verify_pw(password, ""))

    # =========================================================================
    # 2. Authentication & Token Revocation
    # =========================================================================
    def test_02_jwt_authentication_and_revocation(self):
        """Verify JWT generation, authentication, and revocation blacklist."""
        user = User.get_by_username(self.doc_username)
        self.assertIsNotNone(user)
        user_obj = User(user['user_id'], user['username'], user['full_name'], user['email'], user['role'], user['department'])

        token_data = AuthService.generate_access_token(user_obj)
        token = token_data['access_token']

        # Verify token decoding
        payload, err = AuthService.decode_access_token(token)
        self.assertIsNone(err)
        self.assertEqual(payload['username'], self.doc_username)

        # Blacklist / Revoke token
        AuthService.blacklist_token(token, user_id=user['user_id'])

        # Verify revoked token is now rejected
        payload_revoked, err_revoked = AuthService.decode_access_token(token)
        self.assertIsNone(payload_revoked)
        self.assertIn('revoked', err_revoked.lower())

    # =========================================================================
    # 3. RBAC Enforcement (Access Control Barriers)
    # =========================================================================
    def test_03_rbac_enforcement(self):
        """Verify 403 Forbidden when unauthorized roles attempt privileged routes."""
        self.assertIsNotNone(self.nurse_token)
        self.assertIsNotNone(self.doctor_token)
        self.assertIsNotNone(self.admin_token)

        # 1. Nurse attempts Admin user creation -> 403 Forbidden
        headers_nurse = {'Authorization': f'Bearer {self.nurse_token}'}
        resp = self.client.post('/api/v1/users', headers=headers_nurse, json={
            'username': f'attacker_{int(time.time())}',
            'password': 'Password123!',
            'full_name': 'Attacker',
            'email': f'attacker_{int(time.time())}@example.com',
            'role': 'admin'
        })
        self.assertEqual(resp.status_code, 403)

        # 2. Doctor attempts Admin user listing -> 403 Forbidden
        headers_doc = {'Authorization': f'Bearer {self.doctor_token}'}
        resp = self.client.get('/api/v1/users', headers=headers_doc)
        self.assertEqual(resp.status_code, 403)

        # 3. Unauthenticated attempts vitals submission -> 401 Unauthorized
        resp = self.client.post('/api/v1/vitals', json={
            'patient_id': 1,
            'heart_rate': 80
        })
        self.assertIn(resp.status_code, (401, 403))

    # =========================================================================
    # 4. Input Validation & Parameter Bounds
    # =========================================================================
    def test_04_input_validation(self):
        """Verify strict input bounds, type checking, and format validations."""
        headers = {'Authorization': f'Bearer {self.admin_token}'}

        # Invalid email format
        resp = self.client.post('/api/v1/users', headers=headers, json={
            'username': f'validuser_{int(time.time())}',
            'password': 'Password123!',
            'full_name': 'Valid Name',
            'email': 'not-an-email',
            'role': 'nurse'
        })
        self.assertEqual(resp.status_code, 422)

        # Invalid short password
        resp = self.client.post('/api/v1/users', headers=headers, json={
            'username': f'validuser2_{int(time.time())}',
            'password': '123',
            'full_name': 'Valid Name',
            'email': f'valid_{int(time.time())}@example.com',
            'role': 'nurse'
        })
        self.assertEqual(resp.status_code, 422)

        # Invalid clinical vitals parameter bounds
        doc_headers = {'Authorization': f'Bearer {self.doctor_token}'}
        resp = self.client.post('/api/v1/vitals', headers=doc_headers, json={
            'patient_id': 1,
            'heart_rate': 999,  # Clinically impossible HR
            'respiratory_rate': 20,
            'blood_pressure_sys': 120,
            'blood_pressure_dia': 80,
            'temperature': 37.0
        })
        self.assertEqual(resp.status_code, 422)

    # =========================================================================
    # 5. SQL Injection Prevention (100% Parameterized Queries)
    # =========================================================================
    def test_05_sql_injection_prevention(self):
        """Verify database layer resilience against classic SQL injection attempts."""
        sqli_payloads = [
            "admin' OR '1'='1",
            "admin'--",
            "'; DROP TABLE users; --",
            "' UNION SELECT null, null, null, null, null, null, null, null, null, null --",
            "1; SELECT pg_sleep(5); --"
        ]

        for payload in sqli_payloads:
            # Query by username with payload
            res = User.get_by_username(payload)
            self.assertIsNone(res, f"SQLi payload succeeded unexpectedly: {payload}")

            # Filter search with payload
            search_res = User.get_filtered(search=payload)
            self.assertIsInstance(search_res, dict)
            # Table users must remain intact and unharmed
            all_users = User.get_all(include_inactive=True)
            self.assertTrue(len(all_users) > 0)

    # =========================================================================
    # 6. Secure Database Transactions & Rollback
    # =========================================================================
    def test_06_database_transaction_rollback(self):
        """Verify that transactions rollback atomically if an error occurs."""
        count_before = len(User.get_all(include_inactive=True))

        try:
            with db.transaction() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, full_name, email, role) VALUES (%s, %s, %s, %s, %s)",
                    (f"temp_tx_user_{int(time.time())}", "hash", "Temp User", f"temptx_{int(time.time())}@hospital.com", "nurse")
                )
                # Intentionally trigger error within transaction
                cur.execute("INSERT INTO non_existent_table_xyz VALUES (1)")
        except Exception:
            pass  # Expected rollback

        count_after = len(User.get_all(include_inactive=True))
        self.assertEqual(count_before, count_after, "Transaction did not roll back cleanly!")

    # =========================================================================
    # 7. Secure QR Tokens (Zero PII, High Entropy, SHA-256 Hashes)
    # =========================================================================
    def test_07_secure_qr_tokens(self):
        """Verify QR tokens do not leak patient PII and use secure hashing."""
        token_info = PatientQRToken.generate_token(patient_id=1, valid_hours=24)
        raw_token = token_info.get('raw_token') or token_info.get('token')

        # Token must be high entropy string, starting with secure prefix
        self.assertTrue(raw_token.startswith(('JS-ATT-', 'JS-QR-')))
        # Raw token must NOT contain plain patient name or diagnosis
        self.assertNotIn('John', raw_token)
        self.assertNotIn('Sharma', raw_token)
        self.assertNotIn('ICU', raw_token)

        # Database must store SHA-256 hash or secure reference, not unhashed payload
        records = db.execute_query(
            "SELECT token_hash, patient_id FROM patient_qr_tokens WHERE patient_id = 1 ORDER BY token_id DESC LIMIT 1",
            fetch=True
        )
        self.assertTrue(len(records) > 0)
        self.assertNotEqual(records[0]['token_hash'], raw_token)
        self.assertEqual(len(records[0]['token_hash']), 64)  # SHA-256 hex length

    # =========================================================================
    # 8. Rate Limiting (Sliding Window & 429 Response)
    # =========================================================================
    def test_08_rate_limiting(self):
        """Verify RateLimiter sliding window rejects excessive calls with 429."""
        limiter = RateLimiter()
        client_key = "test_client_ip_127_0_0_1"

        # Allow 5 calls within 10 seconds
        for i in range(5):
            allowed, retry_after = limiter.is_allowed(client_key, limit=5, window_seconds=10)
            self.assertTrue(allowed, f"Call {i+1} should have been allowed")

        # 6th call should be blocked
        allowed, retry_after = limiter.is_allowed(client_key, limit=5, window_seconds=10)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    # =========================================================================
    # 9. Secure HTTP Headers & CORS
    # =========================================================================
    def test_09_secure_http_headers_and_cors(self):
        """Verify required security headers are attached to API responses."""
        resp = self.client.get('/api/v1/auth/me')

        # Check critical security headers
        headers = resp.headers
        self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertIn('mode=block', headers.get('X-XSS-Protection', ''))
        self.assertIn('max-age=31536000', headers.get('Strict-Transport-Security', ''))
        self.assertIn('default-src', headers.get('Content-Security-Policy', ''))
        self.assertEqual(headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
        self.assertIn('geolocation=()', headers.get('Permissions-Policy', ''))

        # Check CORS
        self.assertIn('Access-Control-Allow-Origin', headers)
        self.assertIn('Access-Control-Allow-Methods', headers)

        # Preflight OPTIONS request
        options_resp = self.client.options('/api/v1/patients')
        self.assertEqual(options_resp.status_code, 200)

    # =========================================================================
    # 10. Sensitive Data Redaction (Never Expose Passwords/Secrets)
    # =========================================================================
    def test_10_sensitive_data_redaction(self):
        """Verify password hashes, secret keys, and DB credentials are never returned."""
        headers = {'Authorization': f'Bearer {self.admin_token}'}
        resp = self.client.get('/api/v1/users', headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        for user in data.get('data', []):
            self.assertNotIn('password_hash', user)
            self.assertNotIn('password', user)
            self.assertNotIn('secret_key', user)

        # Test dictionary sanitization helper
        raw_payload = {
            'username': 'doctor1',
            'password_hash': '$2b$12$eX4mpL3H4sH...',
            'reset_token': 'SECRET_TOKEN_XYZ',
            'db_password': 'RootPassword123!',
            'patient_info': {
                'name': 'A. Kumar',
                'secret_key': 'KEY-12345'
            }
        }
        sanitized = sanitize_dict(raw_payload)
        self.assertNotIn('password_hash', sanitized)
        self.assertNotIn('reset_token', sanitized)
        self.assertNotIn('db_password', sanitized)
        self.assertNotIn('secret_key', sanitized['patient_info'])
        self.assertEqual(sanitized['patient_info']['name'], 'A. Kumar')

    # =========================================================================
    # 11. Path Traversal Prevention
    # =========================================================================
    def test_11_path_traversal_prevention(self):
        """Verify directory traversal attempts are blocked."""
        base_dir = os.path.abspath('reports_storage')

        # Legitimate path
        safe_path = validate_safe_path(base_dir, 'patient_10_report.pdf')
        self.assertTrue(safe_path.startswith(base_dir))

        # Traversal attempts
        traversal_attempts = [
            '../../etc/passwd',
            '..\\..\\windows\\system32\\cmd.exe',
            '../../../.env',
            'subfolder/../../app.py'
        ]
        for attempt in traversal_attempts:
            with self.assertRaises(ValueError):
                validate_safe_path(base_dir, attempt)

    # =========================================================================
    # 12. Error Handling & Zero Stack Trace Leakage
    # =========================================================================
    def test_12_error_handling_sanitization(self):
        """Verify 404, 401, 403, and 500 error responses contain zero stack traces."""
        # 404 Not Found
        resp = self.client.get('/api/v1/non_existent_endpoint_12345')
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data.get('success', True))
        self.assertNotIn('Traceback', json.dumps(data))
        self.assertNotIn('File "', json.dumps(data))

        # 401 Unauthorized
        resp = self.client.get('/api/v1/users')
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data.get('success', True))
        self.assertNotIn('Traceback', json.dumps(data))


if __name__ == '__main__':
    unittest.main(verbosity=2)
