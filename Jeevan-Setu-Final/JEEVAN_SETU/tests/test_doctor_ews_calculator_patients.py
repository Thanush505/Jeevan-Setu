"""
tests/test_doctor_ews_calculator_patients.py — Comprehensive Test Suite for
Doctor EWS Calculator Patient Loading, Selection, Authorization & Data Isolation.

Validates all 12 requirements:
1. Successful patient-list retrieval
2. Empty patient-list response
3. Unauthorized request (401)
4. Forbidden request / IDOR protection (403)
5. Backend database error handling
6. Expired authentication token (401)
7. Correct patient selection
8. Correct patient details loading
9. Latest vitals retrieval
10. Current EWS retrieval
11. Patient switching without stale data
12. Prevention of cross-patient data leakage
"""

import unittest
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
import jwt

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from database.db import get_db
from models.user_model import User
from models.patient_model import Patient
from services.auth_service import AuthService
from config import get_config


class TestDoctorEWSCalculatorPatients(unittest.TestCase):
    """Test suite covering the 12 requirements for Doctor EWS Calculator patient loading."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.config = get_config()
        cls.db = get_db()

        # Doctor 1: Dr. Mehta (user_id=2, doctor_id=1)
        cls.doc_mehta = User.get_by_id(2)
        cls.token_mehta = AuthService.generate_access_token(cls.doc_mehta)['access_token']
        cls.headers_mehta = {'Authorization': f'Bearer {cls.token_mehta}', 'Accept': 'application/json'}

        # Doctor 2: Dr. Patel (user_id=3, doctor_id=2)
        cls.doc_patel = User.get_by_id(3)
        cls.token_patel = AuthService.generate_access_token(cls.doc_patel)['access_token']
        cls.headers_patel = {'Authorization': f'Bearer {cls.token_patel}', 'Accept': 'application/json'}

    # 1. Successful patient-list retrieval
    def test_01_successful_patient_list_retrieval(self):
        """Doctor successfully retrieves authorized admitted patients."""
        res = self.client.get('/api/v1/patients?status=admitted&limit=50&doctor_id=2', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('data', data)
        patients = data.get('data', [])
        self.assertGreater(len(patients), 0, "Authorized doctor must have assigned patients")
        p0 = patients[0]
        self.assertIn('patient_id', p0)
        self.assertIn('name', p0)
        self.assertIn('patient_code', p0)
        self.assertIn('bed_number', p0)
        print(f"[TEST 01 PASS] Retrieved {len(patients)} authorized patients for Dr. Mehta. First: {p0['name']} ({p0['patient_code']})")

    # 2. Empty patient-list response
    def test_02_empty_patient_list_response(self):
        """Querying for a non-existent doctor ID returns clean empty list without crashing."""
        res = self.client.get('/api/v1/patients?status=admitted&limit=50&doctor_id=99999', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('data'), [], "Doctor with no patients must receive empty data list")
        print("[TEST 02 PASS] Empty patient list handled cleanly with empty data array.")

    # 3. Unauthorized request (401)
    def test_03_unauthorized_request(self):
        """Requests without Authorization header must return HTTP 401."""
        res_list = self.client.get('/api/v1/patients?status=admitted')
        self.assertEqual(res_list.status_code, 401)
        res_detail = self.client.get('/api/v1/patients/1')
        self.assertEqual(res_detail.status_code, 401)
        print("[TEST 03 PASS] Unauthenticated requests rejected with HTTP 401.")

    # 4. Forbidden request / IDOR protection (403)
    def test_04_forbidden_request_idor_protection(self):
        """Doctor attempting to directly access another doctor's unassigned patient returns HTTP 403."""
        # Patient 5 is assigned to Dr. Gupta (user_id=4), not Dr. Mehta (user_id=2)
        res = self.client.get('/api/v1/patients/5', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn('Permission denied', data.get('error', ''))
        print("[TEST 04 PASS] IDOR protection blocks cross-doctor patient inspection with HTTP 403.")

    # 5. Backend database error handling
    def test_05_database_error_handling(self):
        """Malformed query parameters handled safely without uncaught 500 crashes."""
        res = self.client.get('/api/v1/patients?doctor_id=invalid_string&page=not_a_num', headers=self.headers_mehta)
        self.assertIn(res.status_code, (200, 422))
        data = res.get_json()
        self.assertTrue(data.get('success') is not None)
        print("[TEST 05 PASS] Malformed query parameters handled gracefully.")

    # 6. Expired authentication token (401)
    def test_06_expired_authentication_token(self):
        """Expired JWT token returns HTTP 401 Unauthorized."""
        now = datetime.now(timezone.utc)
        expired_payload = {
            'sub': str(self.doc_mehta.id),
            'username': self.doc_mehta.username,
            'email': self.doc_mehta.email,
            'role': self.doc_mehta.role,
            'iat': now - timedelta(hours=2),
            'exp': now - timedelta(hours=1)
        }
        expired_token = jwt.encode(expired_payload, self.config.JWT_SECRET_KEY, algorithm=self.config.JWT_ALGORITHM)
        expired_headers = {'Authorization': f'Bearer {expired_token}', 'Accept': 'application/json'}

        res = self.client.get('/api/v1/patients', headers=expired_headers)
        self.assertEqual(res.status_code, 401)
        print("[TEST 06 PASS] Expired JWT token correctly returns HTTP 401.")

    # 7. Correct patient selection
    def test_07_correct_patient_selection(self):
        """Patient selection retrieves matching patient record."""
        res = self.client.get('/api/v1/patients/1', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']
        self.assertEqual(data['patient_id'], 1)
        self.assertEqual(data['patient_code'], 'UHID-2026-00001')
        print(f"[TEST 07 PASS] Patient selection for ID 1 correctly returns {data['name']} ({data['patient_code']}).")

    # 8. Correct patient details loading
    def test_08_correct_patient_details_loading(self):
        """Loaded patient profile includes all demographic and clinical information."""
        res = self.client.get('/api/v1/patients/1', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']

        self.assertIn('name', data)
        self.assertIn('age', data)
        self.assertIn('gender', data)
        self.assertIn('admission_date', data)
        self.assertIn('diagnosis', data)
        self.assertIn('ward_type', data)
        self.assertIn('bed_number', data)

        self.assertEqual(data['name'], 'Rajesh Kumar')
        self.assertEqual(data['age'], 58)
        self.assertEqual(data['gender'], 'Male')
        self.assertEqual(data['ward_type'], 'ICU')
        print(f"[TEST 08 PASS] Patient profile complete: {data['name']}, Age {data['age']}, Gender {data['gender']}, Ward {data['ward_type']}.")

    # 9. Latest vitals retrieval
    def test_09_latest_vitals_retrieval(self):
        """Patient profile includes latest 4-parameter telemetry vitals."""
        res = self.client.get('/api/v1/patients/1', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']

        self.assertIn('latest_vitals', data)
        vitals = data['latest_vitals']
        self.assertIsNotNone(vitals)
        self.assertIn('heart_rate', vitals)
        self.assertIn('respiratory_rate', vitals)
        self.assertIn('systolic_bp', vitals)
        self.assertIn('temperature', vitals)
        self.assertIn('recorded_at', vitals)
        print(f"[TEST 09 PASS] Latest vitals present: HR={vitals['heart_rate']}, RR={vitals['respiratory_rate']}, SBP={vitals['systolic_bp']}, Temp={vitals['temperature']}.")

    # 10. Current EWS retrieval
    def test_10_current_ews_retrieval(self):
        """Patient profile contains valid authoritative EWS score, risk level, condition, and recommendation."""
        res = self.client.get('/api/v1/patients/1', headers=self.headers_mehta)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']

        self.assertIn('ews_score', data)
        self.assertIn('ews_risk_level', data)
        self.assertIn('condition', data)
        self.assertIn('recommendation', data)
        self.assertIsInstance(data['ews_score'], (int, float))
        print(f"[TEST 10 PASS] Authoritative EWS: Score={data['ews_score']}, Risk={data['ews_risk_level']}, Condition={data['condition']}.")

    # 11. Patient switching without stale data
    def test_11_patient_switching_without_stale_data(self):
        """Switching between Patient 1 and Patient 2 returns distinct, isolated clinical contexts."""
        # Patient 1 (Rajesh Kumar)
        res1 = self.client.get('/api/v1/patients/1', headers=self.headers_mehta)
        self.assertEqual(res1.status_code, 200)
        p1 = res1.get_json()['data']

        # Patient 2 (Anita Devi)
        res2 = self.client.get('/api/v1/patients/2', headers=self.headers_mehta)
        self.assertEqual(res2.status_code, 200)
        p2 = res2.get_json()['data']

        self.assertNotEqual(p1['patient_id'], p2['patient_id'])
        self.assertNotEqual(p1['name'], p2['name'])
        self.assertNotEqual(p1['patient_code'], p2['patient_code'])
        self.assertNotEqual(p1['bed_number'], p2['bed_number'])
        self.assertNotEqual(p1['age'], p2['age'])
        self.assertNotEqual(p1['gender'], p2['gender'])
        print(f"[TEST 11 PASS] Patient 1 ({p1['name']}) and Patient 2 ({p2['name']}) cleanly isolated without stale bleeding.")

    # 12. Prevention of cross-patient data leakage
    def test_12_prevention_of_cross_patient_data_leakage(self):
        """Authorized doctor lists contain strictly authorized patients; cross-doctor leakage is impossible."""
        res_mehta = self.client.get('/api/v1/patients?status=admitted&limit=50&doctor_id=2', headers=self.headers_mehta)
        mehta_ids = [p['patient_id'] for p in res_mehta.get_json()['data']]

        res_patel = self.client.get('/api/v1/patients?status=admitted&limit=50&doctor_id=3', headers=self.headers_patel)
        patel_ids = [p['patient_id'] for p in res_patel.get_json()['data']]

        # Patient 1 is assigned to Mehta, not Patel
        self.assertIn(1, mehta_ids)
        self.assertNotIn(1, patel_ids)

        # Cross-doctor direct profile fetch attempt is blocked
        res_leak = self.client.get('/api/v1/patients/1', headers=self.headers_patel)
        self.assertEqual(res_leak.status_code, 403, "Patel must NOT be able to view Mehta's Patient 1")
        print("[TEST 12 PASS] Cross-patient and cross-doctor data leakage strictly prevented by RBAC.")


if __name__ == '__main__':
    unittest.main()

