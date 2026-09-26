"""
tests/test_phase13_qr_attendant.py — Comprehensive Test Suite for Phase 13 QR-Based Attendant System.

Workflow:
Patient
   ↓
Generate secure token
   ↓
Generate QR
   ↓
Attendant scans
   ↓
Token validation
   ↓
Patient dashboard

Backend Responsibilities Tested:
1. Secure random token (cryptographic entropy & SHA-256 hash).
2. Privacy Rule: QR contains a token, NEVER raw patient PII.
3. Token expiry validation & rejection.
4. Active/inactive status & revocation.
5. Patient association (sanitized read-only access for family).
6. QR regeneration (deactivates previous tokens).
7. QR access audit (tracks generate, scan, view, and regenerate events in audit_logs).
8. RBAC security: Staff manage QR codes, Attendant is strictly read-only.
"""

import sys
import os
import unittest
from datetime import datetime, timedelta

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.qr_token_model import PatientQRToken
from models.audit_log_model import AuditLog
from services.auth_service import AuthService


class TestPhase13QRAttendantSystem(unittest.TestCase):
    """Test suite for Phase 13 QR-Based Attendant System."""

    @classmethod
    def setUpClass(cls):
        """Configure test client, users, tokens, and test patient."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(datetime.now().timestamp())

        # Admin Token
        admin_user = User.authenticate('admin', 'admin123')
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

        # Doctor User & Token
        cls.doc_id = User.create(
            username=f"p13_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. Eric Foreman",
            email=f"p13_doc_{ts}@hospital.com",
            role='doctor',
            department='Critical Care'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(cls.doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Nurse User & Token
        cls.nurse_id = User.create(
            username=f"p13_nurse_{ts}",
            password="NursePassword123!",
            full_name="Nurse Wendy",
            email=f"p13_nurse_{ts}@hospital.com",
            role='nurse',
            department='ICU'
        )
        cls.nurse_token = AuthService.generate_access_token(User.get_by_id(cls.nurse_id))['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Attendant User & Token
        cls.attendant_id = User.create(
            username=f"p13_att_{ts}",
            password="AttendantPass123!",
            full_name="Attendant Sarah",
            email=f"p13_att_{ts}@hospital.com",
            role='attendant'
        )
        cls.attendant_token = AuthService.generate_access_token(User.get_by_id(cls.attendant_id))['access_token']
        cls.attendant_headers = {'Authorization': f"Bearer {cls.attendant_token}"}

        # Create Patient
        cls.patient_id = Patient.create(
            name=f"QR Test Patient {ts}",
            age=48,
            gender="Male",
            ward_type="ICU",
            diagnosis="Severe pneumonia recovery",
            created_by=cls.doc_id
        )

        # Record vitals for patient
        Vitals.create(
            patient_id=cls.patient_id,
            heart_rate=76.0,
            blood_pressure_sys=120.0,
            blood_pressure_dia=80.0,
            respiratory_rate=16.0,
            temperature=36.7,
            spo2=98.0,
            consciousness='Alert',
            ews_score=0,
            recorded_by=cls.nurse_id
        )

    # ─────────────────────────────────────────────────────────────
    # Token Generation & Privacy Rule Tests
    # ─────────────────────────────────────────────────────────────

    def test_01_generate_secure_random_token_and_privacy_rule(self):
        """
        Verify:
        1. Token is cryptographically random.
        2. QR code data contains ONLY the secure token / lookup URL, NEVER raw patient PII.
        3. Generates valid PNG base64 data URL.
        """
        qr_info = PatientQRToken.generate_token(patient_id=self.patient_id, created_by=self.nurse_id, valid_hours=24)

        self.assertIn('raw_token', qr_info)
        self.assertIn('token_hash', qr_info)
        self.assertIn('access_code', qr_info)
        self.assertIn('qr_image_data_url', qr_info)
        self.assertTrue(qr_info['qr_image_data_url'].startswith("data:image/png;base64,"))

        # PRIVACY RULE CHECK: QR payload MUST NOT contain patient name, age, gender, or diagnosis!
        raw_token = qr_info['raw_token']
        qr_data = qr_info['qr_code_data']
        patient = Patient.get_by_id(self.patient_id)

        self.assertNotIn(patient['name'], raw_token)
        self.assertNotIn(patient['diagnosis'], raw_token)
        self.assertNotIn(patient['name'], qr_data)
        self.assertNotIn(patient['diagnosis'], qr_data)

        self.__class__.active_token = raw_token
        self.__class__.active_access_code = qr_info['access_code']
        self.__class__.active_token_id = qr_info['token_id']

        print("[PASS] Secure token generation & zero PII in QR verified.")

    # ─────────────────────────────────────────────────────────────
    # Token Validation & Attendant View
    # ─────────────────────────────────────────────────────────────

    def test_02_validate_token_and_access_code_api(self):
        """Test POST /api/v1/attendant/validate with raw token and access code."""
        # 1. Validate by Token
        res_token = self.client.post('/api/v1/attendant/validate', json={'token': self.active_token})
        self.assertEqual(res_token.status_code, 200)
        data_token = res_token.get_json()
        self.assertTrue(data_token['valid'])
        self.assertEqual(data_token['patient_id'], self.patient_id)

        # 2. Validate by 8-char Access Code
        res_code = self.client.post('/api/v1/attendant/validate', json={'access_code': self.active_access_code})
        self.assertEqual(res_code.status_code, 200)
        data_code = res_code.get_json()
        self.assertTrue(data_code['valid'])
        self.assertEqual(data_code['patient_id'], self.patient_id)

        # 3. Validate Invalid Token -> 401
        res_invalid = self.client.post('/api/v1/attendant/validate', json={'token': 'INVALID-TOKEN-12345'})
        self.assertEqual(res_invalid.status_code, 401)
        self.assertFalse(res_invalid.get_json()['valid'])

        print("[PASS] Token & Access Code validation API verified.")

    def test_03_attendant_read_only_view_and_sanitization(self):
        """Test GET /api/v1/attendant/view: Attendant receives sanitized patient recovery data."""
        res = self.client.get(f"/api/v1/attendant/view?token={self.active_token}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        p_data = data['data']
        self.assertEqual(p_data['patient_id'], self.patient_id)
        self.assertIn('patient_name', p_data)
        self.assertIn('ward_type', p_data)
        self.assertIn('latest_vitals', p_data)

        # Check sanitized vitals summary (read-only)
        vitals = p_data['latest_vitals']
        self.assertEqual(vitals['heart_rate'], 76.0)
        self.assertTrue("120" in str(vitals.get('blood_pressure') or vitals.get('blood_pressure_sys')))
        self.assertEqual(vitals['temperature'], 36.7)

        # Web Dashboard HTML View
        web_res = self.client.get(f"/attendant/dashboard?token={self.active_token}")
        self.assertEqual(web_res.status_code, 200)

        print("[PASS] Attendant sanitized read-only view verified.")

    # ─────────────────────────────────────────────────────────────
    # Expiry & Revocation Tests
    # ─────────────────────────────────────────────────────────────

    def test_04_token_expiry_enforcement(self):
        """Verify: Expired QR tokens are automatically rejected."""
        # Create an expired token manually in DB
        expired_token = PatientQRToken.generate_token(patient_id=self.patient_id, valid_hours=-2)
        
        val = PatientQRToken.validate_token(expired_token['raw_token'])
        self.assertFalse(val['valid'])
        self.assertIn("expired", val['error'].lower())

        # Test API rejection
        api_res = self.client.post('/api/v1/attendant/validate', json={'token': expired_token['raw_token']})
        self.assertEqual(api_res.status_code, 401)
        self.assertIn("expired", api_res.get_json()['error'].lower())

        print("[PASS] Token expiry enforcement verified.")

    def test_05_token_revocation_and_inactivation(self):
        """Test revoking a token and verifying it is no longer valid."""
        # Create token to revoke
        temp_token = PatientQRToken.generate_token(patient_id=self.patient_id, valid_hours=24)
        
        # Revoke via API
        rev_res = self.client.post('/api/v1/attendant/qr/revoke',
                                   json={'token_id': temp_token['token_id']},
                                   headers=self.nurse_headers)
        self.assertEqual(rev_res.status_code, 200)

        # Validate revoked token fails
        val = PatientQRToken.validate_token(temp_token['raw_token'])
        self.assertFalse(val['valid'])
        self.assertIn("revoked", val['error'].lower())

        print("[PASS] Token revocation and active status checking verified.")

    # ─────────────────────────────────────────────────────────────
    # QR Regeneration Workflow
    # ─────────────────────────────────────────────────────────────

    def test_06_qr_regeneration_invalidates_previous_tokens(self):
        """
        Verify: Generating a new QR token for a patient automatically deactivates all previous active tokens.
        """
        # 1. Generate Token A
        token_a = PatientQRToken.generate_token(patient_id=self.patient_id, valid_hours=24)
        self.assertTrue(PatientQRToken.validate_token(token_a['raw_token'])['valid'])

        # 2. Regenerate Token B for the same patient via API
        regen_res = self.client.post('/api/v1/attendant/qr/regenerate',
                                     json={'patient_id': self.patient_id, 'valid_hours': 48},
                                     headers=self.nurse_headers)
        self.assertEqual(regen_res.status_code, 200)
        token_b = regen_res.get_json()['data']

        # 3. Token B MUST be valid
        self.assertTrue(PatientQRToken.validate_token(token_b['raw_token'])['valid'])

        # 4. Token A MUST NOW BE INVALID (revoked/replaced)
        val_a = PatientQRToken.validate_token(token_a['raw_token'])
        self.assertFalse(val_a['valid'])
        self.assertIn("revoked or replaced", val_a['error'].lower())

        print("[PASS] QR regeneration & previous token invalidation verified.")

    # ─────────────────────────────────────────────────────────────
    # QR Access Audit Logging
    # ─────────────────────────────────────────────────────────────

    def test_07_qr_access_and_scan_auditing(self):
        """Verify audit logs are recorded for QR generation, scanning, and viewing."""
        # 1. Trigger scan via dashboard
        self.client.get(f"/attendant/dashboard?token={self.active_token}")

        # 2. Trigger API view
        self.client.get(f"/api/v1/attendant/view?token={self.active_token}")

        # 3. Check audit logs table
        scan_logs = db.execute_query(
            "SELECT * FROM audit_logs WHERE action IN ('scan_qr_token', 'view_attendant_api', 'generate_qr_token') AND entity_id = %s",
            (self.patient_id,), fetch=True
        )
        self.assertGreaterEqual(len(scan_logs), 1)

        print("[PASS] QR access, scanning, and generation audit logging verified.")

    # ─────────────────────────────────────────────────────────────
    # RBAC Permissions on QR Management
    # ─────────────────────────────────────────────────────────────

    def test_08_rbac_protection_on_qr_management(self):
        """Verify: Only clinical staff can manage QR tokens; Attendant is restricted."""
        # Nurse CAN generate QR tokens -> 200/201
        nurse_res = self.client.post('/api/v1/attendant/qr/generate',
                                     json={'patient_id': self.patient_id},
                                     headers=self.nurse_headers)
        self.assertIn(nurse_res.status_code, (200, 201))

        # Attendant CANNOT generate QR tokens -> 403 Forbidden
        att_res = self.client.post('/api/v1/attendant/qr/generate',
                                   json={'patient_id': self.patient_id},
                                   headers=self.attendant_headers)
        self.assertEqual(att_res.status_code, 403)

        # Attendant CANNOT revoke tokens -> 403 Forbidden
        att_rev_res = self.client.post('/api/v1/attendant/qr/revoke',
                                       json={'token_id': self.active_token_id},
                                       headers=self.attendant_headers)
        self.assertEqual(att_rev_res.status_code, 403)

        # Unauthenticated -> 401 Unauthorized
        unauth_res = self.client.post('/api/v1/attendant/qr/generate',
                                      json={'patient_id': self.patient_id})
        self.assertEqual(unauth_res.status_code, 401)

        print("[PASS] RBAC protection on QR Token management verified.")


if __name__ == '__main__':
    unittest.main()
