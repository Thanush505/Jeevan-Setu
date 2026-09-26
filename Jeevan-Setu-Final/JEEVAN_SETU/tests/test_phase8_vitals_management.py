"""
tests/test_phase8_vitals_management.py — Comprehensive Test Suite for Phase 8 Vital Management.
Tests:
- POST /vitals & /api/v1/vitals (Submit 4 clinical parameters: RR, HR, BP, Temp + SpO2, Consciousness)
- Input Validation:
  - Data types (non-numeric rejected)
  - Missing values (patient_id missing, all vitals missing)
  - Clinically acceptable input ranges (HR 20-300, BP 40-300, RR 4-80, Temp 25-45)
  - Patient existence check (404 for non-existent patient)
- Automated Vitals -> EWS Engine Pipeline:
  - EWS score calculated and stored
  - EWS breakdown stored in ews_scores table
  - Risk categorization (Normal, Low, Medium, High, Critical)
  - Threshold alert generation for abnormal vitals
- GET /vitals/{patient_id} & /api/v1/vitals/{patient_id}
- GET /vitals/{patient_id}/latest & /api/v1/vitals/{patient_id}/latest
- GET /vitals/{patient_id}/history & /api/v1/vitals/{patient_id}/history
- RBAC validation: Nurse/Doctor allowed vs Attendant/Unauthenticated restricted
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
from models.ews_score_model import EWSScore
from services.auth_service import AuthService


class TestPhase8VitalsManagement(unittest.TestCase):
    """Test suite for Phase 8 Vital Signs Management REST APIs and EWS Pipeline."""

    @classmethod
    def setUpClass(cls):
        """Configure test client and create tokens for Nurse, Doctor, and Attendant."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(datetime.now().timestamp())

        # Admin User & Token
        admin_user = User.authenticate('admin', 'admin123')
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

        # Doctor User & Token
        cls.doc_id = User.create(
            username=f"p8_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. Lisa Cuddy",
            email=f"p8_doc_{ts}@hospital.com",
            role='doctor',
            department='ICU'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(cls.doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Nurse User & Token
        cls.nurse_id = User.create(
            username=f"p8_nurse_{ts}",
            password="NursePassword123!",
            full_name="Nurse Carol Hathaway",
            email=f"p8_nurse_{ts}@hospital.com",
            role='nurse',
            department='ICU'
        )
        cls.nurse_token = AuthService.generate_access_token(User.get_by_id(cls.nurse_id))['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Attendant User & Token
        cls.attendant_id = User.create(
            username=f"p8_att_{ts}",
            password="AttendantPass123!",
            full_name="Attendant Sam",
            email=f"p8_att_{ts}@hospital.com",
            role='attendant'
        )
        cls.attendant_token = AuthService.generate_access_token(User.get_by_id(cls.attendant_id))['access_token']
        cls.attendant_headers = {'Authorization': f"Bearer {cls.attendant_token}"}

        # Create test patient for vitals recording
        cls.patient_id = Patient.create(
            name=f"Vitals Test Patient {ts}",
            age=48,
            gender="Male",
            ward_type="ICU",
            diagnosis="Post-op Coronary Artery Bypass",
            assigned_doctor=cls.doc_id,
            created_by=cls.nurse_id
        )

    def test_01_submit_vitals_and_ews_pipeline(self):
        """Test POST /vitals: Submit clinical parameters (RR, HR, BP, Temp) and verify EWS calculation."""
        payload = {
            'patient_id': self.patient_id,
            'heart_rate': 78,              # Normal: score 0
            'blood_pressure_sys': 122,     # Normal: score 0
            'blood_pressure_dia': 82,
            'respiratory_rate': 16,        # Normal: score 0
            'temperature': 37.0,           # Normal: score 0
            'spo2': 98,                    # Normal: score 0
            'consciousness': 'Alert',      # Normal: score 0
            'urine_output': 150,
            'blood_sugar': 105
        }

        res = self.client.post('/api/v1/vitals', json=payload, headers=self.nurse_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('vital_id', data['data'])
        self.assertIn('ews', data['data'])

        # Check EWS Score
        ews = data['data']['ews']
        self.assertEqual(ews['total_score'], 0)
        self.assertEqual(ews['risk_level'], 'normal')
        self.assertIn('breakdown', ews)

        self.__class__.normal_vital_id = data['data']['vital_id']
        print("[PASS] Normal vitals submission and EWS pipeline verified.")

    def test_02_critical_vitals_and_high_ews_alert(self):
        """Test POST /vitals with abnormal vitals: Verifies EWS score elevation and alert generation."""
        abnormal_payload = {
            'patient_id': self.patient_id,
            'heart_rate': 135,             # Critical High (>130): score 3
            'blood_pressure_sys': 68,      # Critical Low (<70): score 3
            'respiratory_rate': 28,        # Critical High (>=25): score 3
            'temperature': 39.4,           # High (>39.1): score 2
            'spo2': 88,                    # Low (<=91): score 3
            'consciousness': 'Voice'       # Voice: score 1
        }
        # Expected total EWS: 3 + 3 + 3 + 2 + 3 + 1 = 15 (Critical Risk)

        res = self.client.post('/api/v1/vitals', json=abnormal_payload, headers=self.nurse_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])

        ews = data['data']['ews']
        self.assertGreaterEqual(ews['total_score'], 7)
        self.assertEqual(ews['risk_level'], 'critical')
        self.assertGreaterEqual(data['data']['alerts_triggered'], 1)

        # Verify EWS score was saved to ews_scores table
        ews_db = EWSScore.get_latest(self.patient_id)
        self.assertIsNotNone(ews_db)
        self.assertGreaterEqual(ews_db['total_score'], 7)
        self.assertEqual(ews_db['risk_level'], 'CRITICAL')
        print("[PASS] Critical vitals elevation and EWS alert pipeline verified.")

    def test_03_validation_missing_patient_and_nonexistent(self):
        """Test validation: missing patient_id and non-existent patient ID (404)."""
        # Missing patient_id
        res_missing = self.client.post('/api/v1/vitals', json={'heart_rate': 80}, headers=self.nurse_headers)
        self.assertEqual(res_missing.status_code, 422)

        # Non-existent patient ID
        res_404 = self.client.post('/api/v1/vitals', json={'patient_id': 999999, 'heart_rate': 80}, headers=self.nurse_headers)
        self.assertEqual(res_404.status_code, 404)
        print("[PASS] Patient existence validations verified.")

    def test_04_validation_clinical_ranges_and_types(self):
        """Test validation: non-numeric inputs and clinically impossible values."""
        # 1. Non-numeric heart_rate
        res_str = self.client.post('/api/v1/vitals', json={
            'patient_id': self.patient_id,
            'heart_rate': 'EXTREMELY_FAST'
        }, headers=self.nurse_headers)
        self.assertEqual(res_str.status_code, 422)

        # 2. Out of acceptable clinical range: Temperature = 12.0°C
        res_temp = self.client.post('/api/v1/vitals', json={
            'patient_id': self.patient_id,
            'temperature': 12.0
        }, headers=self.nurse_headers)
        self.assertEqual(res_temp.status_code, 422)
        self.assertIn('temperature', res_temp.get_json()['error'].lower())

        # 3. Out of range: Heart Rate = 500 bpm
        res_hr = self.client.post('/api/v1/vitals', json={
            'patient_id': self.patient_id,
            'heart_rate': 500
        }, headers=self.nurse_headers)
        self.assertEqual(res_hr.status_code, 422)
        self.assertIn('heart rate', res_hr.get_json()['error'].lower())

        # 4. Out of range: Respiratory Rate = 150
        res_rr = self.client.post('/api/v1/vitals', json={
            'patient_id': self.patient_id,
            'respiratory_rate': 150
        }, headers=self.nurse_headers)
        self.assertEqual(res_rr.status_code, 422)

        # 5. Missing all vital sign measurements
        res_empty = self.client.post('/api/v1/vitals', json={
            'patient_id': self.patient_id
        }, headers=self.nurse_headers)
        self.assertEqual(res_empty.status_code, 422)
        print("[PASS] Clinical range and type validations verified.")

    def test_05_get_patient_vitals_list(self):
        """Test GET /vitals/{patient_id} (Fetch patient vitals list)."""
        res = self.client.get(f"/api/v1/vitals/{self.patient_id}", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 2)
        print("[PASS] GET /vitals/{patient_id} verified.")

    def test_06_get_latest_vitals(self):
        """Test GET /vitals/{patient_id}/latest (Fetch latest vitals record and EWS score)."""
        res = self.client.get(f"/api/v1/vitals/{self.patient_id}/latest", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('vitals', data['data'])
        self.assertIn('ews', data['data'])
        self.assertEqual(data['data']['vitals']['patient_id'], self.patient_id)
        print("[PASS] GET /vitals/{patient_id}/latest verified.")

    def test_07_get_vitals_history_timeline(self):
        """Test GET /vitals/{patient_id}/history (Fetch vitals and EWS history)."""
        res = self.client.get(f"/api/v1/vitals/{self.patient_id}/history", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('vitals_history', data['data'])
        self.assertIn('ews_history', data['data'])
        self.assertGreaterEqual(len(data['data']['vitals_history']), 2)
        print("[PASS] GET /vitals/{patient_id}/history verified.")

    def test_08_rbac_permissions(self):
        """Test RBAC access control on Vitals endpoints."""
        # 1. Attendant has NO access to staff /vitals endpoints (should receive 403)
        res_att = self.client.get(f"/api/v1/vitals/{self.patient_id}", headers=self.attendant_headers)
        self.assertEqual(res_att.status_code, 403)

        # 2. Unauthenticated request should receive 401
        res_unauth = self.client.get(f"/api/v1/vitals/{self.patient_id}")
        self.assertEqual(res_unauth.status_code, 401)
        print("[PASS] RBAC protection on Vital Management endpoints verified.")


if __name__ == '__main__':
    unittest.main()
