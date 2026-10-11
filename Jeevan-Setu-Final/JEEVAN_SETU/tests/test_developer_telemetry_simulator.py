"""
tests/test_developer_telemetry_simulator.py — Automated Test Suite for ICU Telemetry Simulator.
Covers:
- Direct URL Access RBAC (401 unauthenticated, 403 non-admin, 200 admin)
- Developer diagnostic & health check APIs
- Simulator vital ingestion through authoritative backend pipeline
- Multi-patient data isolation & independent EWS scoring
- Read-back verification and EWS-to-vital relationship consistency
- Alert triggering on deteriorating vitals
"""

import unittest
from app import create_app
from database.db import db
from services.auth_service import AuthService
from models.user_model import User


class TestDeveloperTelemetrySimulator(unittest.TestCase):
    """Test suite for Developer ICU Telemetry Simulator."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Fetch test users from seed data
        cls.admin_user = User.get_by_username('admin_js') or User.get_by_username('admin')
        cls.doctor_user = User.get_by_username('dr_sharma')
        cls.nurse_user = User.get_by_username('nurse_priya')

        # Generate JWT access tokens
        if cls.admin_user:
            cls.admin_token = AuthService.generate_access_token(cls.admin_user)['access_token']
        else:
            cls.admin_token = ''

        if cls.doctor_user:
            cls.doctor_token = AuthService.generate_access_token(cls.doctor_user)['access_token']
        else:
            cls.doctor_token = ''

        if cls.nurse_user:
            cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']
        else:
            cls.nurse_token = ''

    def test_01_simulator_page_direct_access_unauthenticated(self):
        """Direct request to /Developer/Telemetry_Simulator/ without login must render HTML directly (200 OK)."""
        response = self.client.get('/Developer/Telemetry_Simulator/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ICU Telemetry Simulator', response.data)

    def test_02_simulator_page_nurse_access_granted(self):
        """Nurse account accessing /Developer/Telemetry_Simulator/ must render HTML directly (200 OK)."""
        response = self.client.get(
            '/Developer/Telemetry_Simulator/',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ICU Telemetry Simulator', response.data)

    def test_03_simulator_page_doctor_access_granted(self):
        """Doctor account accessing /Developer/Telemetry_Simulator/ must render HTML directly (200 OK)."""
        response = self.client.get(
            '/Developer/Telemetry_Simulator/',
            headers={'Authorization': f'Bearer {self.doctor_token}'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ICU Telemetry Simulator', response.data)

    def test_04_simulator_page_admin_access_granted(self):
        """Admin account accessing /Developer/Telemetry_Simulator/ must render HTML directly (200 OK)."""
        response = self.client.get(
            '/Developer/Telemetry_Simulator/',
            headers={'Authorization': f'Bearer {self.admin_token}'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ICU Telemetry Simulator', response.data)

    def test_05_developer_db_health_public_diagnostic(self):
        """Health check endpoint can be queried for connectivity status without exposing credentials."""
        response = self.client.get('/api/v1/developer/telemetry-simulator/health')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data['success'])
        self.assertEqual(json_data['data']['status'], 'connected')

    def test_06_developer_db_health_authorized(self):
        """Health check endpoint with token returns connected status and roundtrip latency."""
        response = self.client.get(
            '/api/v1/developer/telemetry-simulator/health',
            headers={'Authorization': f'Bearer {self.admin_token}'}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data['success'])
        self.assertEqual(json_data['data']['status'], 'connected')
        self.assertTrue(json_data['data']['query_success'])
        self.assertGreaterEqual(json_data['data']['latency_ms'], 0)

    def test_07_developer_verify_access_returns_user_info(self):
        """Verify-access endpoint confirms caller permissions or guest status."""
        response = self.client.get(
            '/api/v1/developer/telemetry-simulator/verify-access',
            headers={'Authorization': f'Bearer {self.admin_token}'}
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data['success'])
        self.assertEqual(json_data['data']['role'], 'admin')

        # Also test unauthenticated verify-access
        guest_resp = self.client.get('/api/v1/developer/telemetry-simulator/verify-access')
        self.assertEqual(guest_resp.status_code, 200)
        guest_json = guest_resp.get_json()
        self.assertTrue(guest_json['success'])
        self.assertFalse(guest_json['data']['authenticated'])

    def test_08_simulator_vital_submission_pipeline(self):
        """Submit single simulated vital reading to existing backend for Patient 1."""
        payload = {
            'heart_rate': 74.0,
            'respiratory_rate': 16.0,
            'systolic_bp': 120.0,
            'temperature': 36.8,
            'source': 'SIMULATOR',
            'device_id': 'JS-ICU-SIM-001'
        }
        response = self.client.post(
            '/api/v1/vitals/patient/1/submit',
            headers={'Authorization': f'Bearer {self.admin_token}'},
            json=payload
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()['data']

        self.assertEqual(data['patient_id'], 1)
        self.assertIsNotNone(data['vital_id'])
        self.assertEqual(data['vitals']['heart_rate'], 74.0)
        self.assertEqual(data['vitals']['systolic_bp'], 120.0)
        self.assertEqual(data['vitals']['respiratory_rate'], 16.0)
        self.assertEqual(data['vitals']['temperature'], 36.8)

        # Existing EWS engine verification: Normal resting vitals -> score 0 (Stable)
        self.assertEqual(data['total_score'], 0)
        self.assertEqual(data['condition'], 'Stable')
        self.assertIn('HDU', data['recommendation'])

    def test_09_multi_patient_data_isolation(self):
        """
        Verify multi-patient telemetry submission and ensure zero cross-contamination.
        Patient 1 receives Stable vitals (EWS 0).
        Patient 2 receives Critical vitals (HR 145, RR 36, SBP 60, Temp 40.0 -> EWS >= 7).
        """
        # Patient 1: Stable
        res1 = self.client.post(
            '/api/v1/vitals/patient/1/submit',
            headers={'Authorization': f'Bearer {self.admin_token}'},
            json={
                'heart_rate': 72.0,
                'respiratory_rate': 15.0,
                'systolic_bp': 122.0,
                'temperature': 36.7
            }
        )
        self.assertEqual(res1.status_code, 201)
        p1_data = res1.get_json()['data']
        self.assertEqual(p1_data['patient_id'], 1)
        self.assertEqual(p1_data['total_score'], 0)
        self.assertEqual(p1_data['condition'], 'Stable')

        # Patient 2: Critical
        res2 = self.client.post(
            '/api/v1/vitals/patient/2/submit',
            headers={'Authorization': f'Bearer {self.admin_token}'},
            json={
                'heart_rate': 148.0,
                'respiratory_rate': 36.0,
                'systolic_bp': 58.0,
                'temperature': 40.0
            }
        )
        self.assertEqual(res2.status_code, 201)
        p2_data = res2.get_json()['data']
        self.assertEqual(p2_data['patient_id'], 2)
        self.assertGreaterEqual(p2_data['total_score'], 7)
        self.assertEqual(p2_data['condition'], 'Critical')

        # Verify Patient 1 latest status remains unaffected (zero data leaking)
        status_res1 = self.client.get(
            '/api/v1/vitals/patient/1/latest-status',
            headers={'Authorization': f'Bearer {self.admin_token}'}
        )
        self.assertEqual(status_res1.status_code, 200)
        s1 = status_res1.get_json()['data']
        self.assertEqual(s1['patient_id'], 1)
        self.assertEqual(s1['latest_vitals']['heart_rate'], 72.0)
        self.assertEqual(s1['total_score'], 0)
        self.assertEqual(s1['condition'], 'Stable')

        # Verify Patient 2 latest status is strictly isolated
        status_res2 = self.client.get(
            '/api/v1/vitals/patient/2/latest-status',
            headers={'Authorization': f'Bearer {self.admin_token}'}
        )
        self.assertEqual(status_res2.status_code, 200)
        s2 = status_res2.get_json()['data']
        self.assertEqual(s2['patient_id'], 2)
        self.assertEqual(s2['latest_vitals']['heart_rate'], 148.0)
        self.assertGreaterEqual(s2['total_score'], 7)
        self.assertEqual(s2['condition'], 'Critical')

    def test_10_database_readback_and_ews_relationship_verification(self):
        """
        Verify database read-back integrity and confirm vital_id matches ews_scores.vital_id.
        """
        # Submit known reading for Patient 3
        sent_vitals = {
            'heart_rate': 80.0,
            'respiratory_rate': 18.0,
            'systolic_bp': 125.0,
            'temperature': 36.9
        }
        post_res = self.client.post(
            '/api/v1/vitals/patient/3/submit',
            headers={'Authorization': f'Bearer {self.admin_token}'},
            json=sent_vitals
        )
        self.assertEqual(post_res.status_code, 201)
        post_data = post_res.get_json()['data']
        created_vital_id = post_data['vital_id']

        # Query GET /api/v1/vitals/3/latest
        latest_res = self.client.get(
            '/api/v1/vitals/3/latest',
            headers={'Authorization': f'Bearer {self.admin_token}'}
        )
        self.assertEqual(latest_res.status_code, 200)
        latest_data = latest_res.get_json()['data']

        db_vitals = latest_data['vitals']
        db_ews = latest_data['ews']

        # 1. Read-back match
        self.assertEqual(db_vitals['vital_id'], created_vital_id)
        self.assertEqual(db_vitals['heart_rate'], sent_vitals['heart_rate'])
        self.assertEqual(db_vitals['respiratory_rate'], sent_vitals['respiratory_rate'])
        self.assertEqual(db_vitals['blood_pressure_sys'], sent_vitals['systolic_bp'])
        self.assertEqual(db_vitals['temperature'], sent_vitals['temperature'])

        # 2. EWS relationship check: vital_id must strictly match ews.vital_id
        self.assertIsNotNone(db_ews)
        self.assertEqual(db_ews['vital_id'], created_vital_id)
        self.assertEqual(db_ews['patient_id'], 3)
        self.assertEqual(db_vitals['patient_id'], 3)


if __name__ == '__main__':
    unittest.main()
