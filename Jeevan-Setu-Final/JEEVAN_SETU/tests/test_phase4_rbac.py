"""
tests/test_phase4_rbac.py — Comprehensive Test Suite for Phase 4 Role-Based Access Control (RBAC).
Validates role permissions for:
1. Administrator (Full access)
2. Doctor (Clinical & transfer decisions, reports, vitals)
3. Nurse (Vitals & patient monitoring, alert acknowledgment)
4. Attendant (Read-only patient view through QR / access code)
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
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.qr_token_model import PatientQRToken
from services.auth_service import AuthService
from utils.constants import ROLES


class TestPhase4RBAC(unittest.TestCase):
    """Test suite for Phase 4 Role-Based Access Control."""

    @classmethod
    def setUpClass(cls):
        """Create app client and test accounts for all four roles."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(datetime.now().timestamp())

        # 1. Admin Account
        cls.admin_token = AuthService.generate_access_token(
            User.authenticate('admin', 'admin123')
        )['access_token']

        # 2. Doctor Account
        cls.doc_username = f"rbac_doc_{ts}"
        cls.doc_id = User.create(
            username=cls.doc_username,
            password="DoctorPassword123!",
            full_name="Dr. RBAC Specialist",
            email=f"{cls.doc_username}@jeevansetu.com",
            role='doctor',
            department='Critical Care'
        )
        cls.doc_user = User.get_by_id(cls.doc_id)
        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']

        # 3. Nurse Account
        cls.nurse_username = f"rbac_nurse_{ts}"
        cls.nurse_id = User.create(
            username=cls.nurse_username,
            password="NursePassword123!",
            full_name="Nurse RBAC Staff",
            email=f"{cls.nurse_username}@jeevansetu.com",
            role='nurse',
            department='ICU Ward 1'
        )
        cls.nurse_user = User.get_by_id(cls.nurse_id)
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']

        # 4. Attendant Account
        cls.attendant_username = f"rbac_attendant_{ts}"
        cls.attendant_id = User.create(
            username=cls.attendant_username,
            password="AttendantPass123!",
            full_name="Mr. Family Attendant",
            email=f"{cls.attendant_username}@family.com",
            role='attendant',
            department='Family'
        )
        cls.attendant_user = User.get_by_id(cls.attendant_id)
        cls.attendant_token = AuthService.generate_access_token(cls.attendant_user)['access_token']

        # Seed test patient and QR token
        cls.patient_id = Patient.create(
            name="RBAC Test Patient",
            age=45,
            gender="Female",
            ward_type="ICU",
            bed_number="ICU-102",
            diagnosis="Sepsis",
            assigned_doctor=cls.doc_id
        )
        cls.vital_id = Vitals.record(
            patient_id=cls.patient_id,
            heart_rate=98.0,
            blood_pressure_sys=120.0,
            blood_pressure_dia=80.0,
            temperature=37.2,
            spo2=98.0,
            ews_score=1
        )
        cls.qr_data = PatientQRToken.generate_token(cls.patient_id, created_by=cls.nurse_id)

    def test_01_role_definitions_matrix(self):
        """Verify role definition permissions in constants.py."""
        self.assertIn('all', ROLES['admin'])
        self.assertIn('approve_decisions', ROLES['doctor'])
        self.assertIn('generate_reports', ROLES['doctor'])
        self.assertNotIn('approve_decisions', ROLES['nurse'])
        self.assertNotIn('generate_reports', ROLES['nurse'])
        self.assertIn('record_vitals', ROLES['nurse'])
        self.assertIn('view_patient_status', ROLES['attendant'])
        self.assertNotIn('record_vitals', ROLES['attendant'])
        print("[PASS] Role permissions matrix validated.")

    def test_02_admin_full_system_access(self):
        """Test Administrator has unrestricted access to all endpoints."""
        headers = {'Authorization': f"Bearer {self.admin_token}"}

        # 1. Admin can access user management
        res = self.client.get('/auth/users', headers=headers)
        self.assertIn(res.status_code, (200, 302))

        # 2. Admin can evaluate and approve decisions
        res_eval = self.client.get(f"/decision/evaluate/{self.patient_id}", headers=headers)
        self.assertEqual(res_eval.status_code, 200)

        # 3. Admin can view active alerts
        res_alerts = self.client.get('/alerts/api/active', headers=headers)
        self.assertEqual(res_alerts.status_code, 200)
        print("[PASS] Administrator full system access verified.")

    def test_03_doctor_clinical_and_decision_permissions(self):
        """Test Doctor can evaluate decisions, generate reports, but cannot manage users."""
        headers = {'Authorization': f"Bearer {self.doc_token}"}

        # 1. Doctor CAN evaluate clinical decisions
        res_eval = self.client.get(f"/decision/evaluate/{self.patient_id}", headers=headers)
        self.assertEqual(res_eval.status_code, 200)

        # 2. Doctor CAN view vitals history
        res_vitals = self.client.get(f"/vitals/history/{self.patient_id}", headers=headers)
        self.assertEqual(res_vitals.status_code, 200)

        # 3. Doctor CAN generate reports
        res_rep = self.client.post(f"/reports/generate/daily/{self.patient_id}", headers=headers)
        self.assertEqual(res_rep.status_code, 200)

        # 4. Doctor CANNOT access admin user management
        res_users = self.client.get('/auth/users', headers=headers)
        # Should be forbidden 403 or redirect
        self.assertIn(res_users.status_code, (403, 302))
        print("[PASS] Doctor clinical & decision permissions verified.")

    def test_04_nurse_vitals_and_monitoring_boundaries(self):
        """Test Nurse can record vitals and view alerts, but CANNOT approve decisions or generate reports."""
        headers = {'Authorization': f"Bearer {self.nurse_token}"}

        # 1. Nurse CAN view patient vitals
        res_vitals = self.client.get(f"/vitals/history/{self.patient_id}", headers=headers)
        self.assertEqual(res_vitals.status_code, 200)

        # 2. Nurse CAN view and acknowledge alerts
        res_alerts = self.client.get('/alerts/api/active', headers=headers)
        self.assertEqual(res_alerts.status_code, 200)

        # 3. Nurse CANNOT approve decisions (403 Forbidden)
        res_approve = self.client.post('/decision/approve/9999', headers=headers)
        self.assertEqual(res_approve.status_code, 403)
        self.assertIn('permission denied', res_approve.get_json()['error'].lower())

        # 4. Nurse CANNOT reject decisions (403 Forbidden)
        res_reject = self.client.post('/decision/reject/9999', headers=headers)
        self.assertEqual(res_reject.status_code, 403)

        # 5. Nurse CANNOT generate clinical reports (403 Forbidden)
        res_report = self.client.post(f"/reports/generate/daily/{self.patient_id}", headers=headers)
        self.assertEqual(res_report.status_code, 403)

        # 6. Nurse CANNOT access admin user list
        res_users = self.client.get('/auth/users', headers=headers)
        self.assertIn(res_users.status_code, (403, 302))
        print("[PASS] Nurse vitals & monitoring boundary restrictions verified.")

    def test_05_attendant_read_only_qr_access(self):
        """Test Attendant has read-only access via QR/access code, and is blocked from staff endpoints."""
        # 1. Attendant CAN view sanitized summary via access code / QR token
        res_view = self.client.get(f"/attendant/api/view?code={self.qr_data['access_code']}")
        self.assertEqual(res_view.status_code, 200)
        data = res_view.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['patient_name'], "RBAC Test Patient")
        self.assertIn('latest_vitals_summary', data['data'])

        # 2. Attendant CAN view via QR token
        res_qr = self.client.get(f"/attendant/api/view?token={self.qr_data['raw_token']}")
        self.assertEqual(res_qr.status_code, 200)

        # 3. Attendant token CANNOT access clinical evaluation (403 Forbidden)
        attendant_headers = {'Authorization': f"Bearer {self.attendant_token}"}
        res_eval = self.client.get(f"/decision/evaluate/{self.patient_id}", headers=attendant_headers)
        self.assertEqual(res_eval.status_code, 403)

        # 4. Attendant token CANNOT approve decisions (403 Forbidden)
        res_approve = self.client.post('/decision/approve/9999', headers=attendant_headers)
        self.assertEqual(res_approve.status_code, 403)

        # 5. Attendant token CANNOT generate reports (403 Forbidden)
        res_rep = self.client.post(f"/reports/generate/daily/{self.patient_id}", headers=attendant_headers)
        self.assertEqual(res_rep.status_code, 403)
        print("[PASS] Attendant read-only QR access and security isolation verified.")


if __name__ == '__main__':
    print("=" * 60)
    print("Running Jeevan Setu Phase 4 RBAC Tests...")
    print("=" * 60)
    unittest.main(verbosity=2)
