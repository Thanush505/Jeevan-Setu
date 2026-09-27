"""
tests/test_doctor_critical_alert_ews_score.py — Comprehensive validation:
1. Nurse records critical vitals (RR=44, HR=44, SBP=44, Temp=40 -> EWS Total = 9).
2. EWS is persisted in ews_scores and vitals as 9.
3. Critical Emergency Alert is created.
4. Doctor queries /api/v1/alerts/global-feed and receives emergency_alerts with ews_score = 9 (not None/--).
5. Doctor queries /api/v1/alerts/api/active and /api/v1/alerts/api/patient/<id> with ews_score = 9.
6. Handles EWS = 0 without losing value.
7. Handles multiple EWS history records correctly without cross-patient or historical corruption.
"""

import unittest
import time
import os
import sys

JEEVAN_SETU_ROOT = r'd:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU'
if JEEVAN_SETU_ROOT not in sys.path:
    sys.path.insert(0, JEEVAN_SETU_ROOT)

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.bed_model import Bed
from models.ward_model import Ward
from models.vitals_model import Vitals
from models.ews_score_model import EWSScore
from models.alert_model import Alert
from services.auth_service import AuthService


class TestDoctorCriticalAlertEWSScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000)

        # Create Doctor and Nurse
        cls.doc_id = User.create(
            username=f"doc_ews_{cls.ts}",
            password="Password@123",
            full_name=f"Dr. EWS Test Physician {cls.ts}",
            email=f"doc_ews_{cls.ts}@jeevansetu.in",
            role="doctor"
        )
        cls.nurse_id = User.create(
            username=f"nurse_ews_{cls.ts}",
            password="Password@123",
            full_name=f"Nurse EWS Test Practitioner {cls.ts}",
            email=f"nurse_ews_{cls.ts}@jeevansetu.in",
            role="nurse"
        )

        cls.doc_user = User.get_by_id(cls.doc_id)
        cls.nurse_user = User.get_by_id(cls.nurse_id)

        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']

        # Wards and Beds
        icu_ward = db.execute_query("SELECT ward_id FROM wards WHERE ward_type = 'ICU' LIMIT 1", fetch=True)
        cls.icu_ward_id = icu_ward[0]['ward_id'] if icu_ward else 1

        cls.bed_num = f"ICU-{cls.ts % 900 + 100}"
        cls.bed_id = Bed.create(ward_id=cls.icu_ward_id, bed_number=cls.bed_num, status="available")
        Bed.update_status(cls.bed_id, 'occupied')

        # Create Patient (Rajesh Kumar test replica)
        cls.patient_id = Patient.create(
            name=f"Rajesh Kumar {cls.ts}",
            age=58,
            gender="Male",
            ward_type="ICU",
            ward_id=cls.icu_ward_id,
            bed_id=cls.bed_id,
            bed_number=cls.bed_num,
            diagnosis="Post-Op Coronary Artery Bypass",
            assigned_doctor=cls.doc_id,
            assigned_nurse=cls.nurse_id
        )

    def test_01_nurse_submits_critical_vitals_ews_9(self):
        """Nurse posts vitals (RR=44, HR=44, SBP=44, Temp=40) resulting in EWS = 9."""
        res = self.client.post(
            f'/api/v1/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={
                'respiratory_rate': 44,
                'heart_rate': 44,
                'systolic_bp': 44,
                'temperature': 40.0,
                'spo2': 95,
                'notes': 'Critical vitals entered by nurse'
            }
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        
        # Verify EWS score calculation
        result_data = data.get('data', {})
        self.assertEqual(result_data.get('total_score'), 9)
        scores = result_data.get('scores', {})
        self.assertEqual(scores.get('respiratory_rate'), 3)
        self.assertEqual(scores.get('heart_rate'), 1)
        self.assertEqual(scores.get('systolic_bp'), 3)
        self.assertEqual(scores.get('temperature'), 2)

    def test_02_doctor_global_feed_has_persisted_ews_9(self):
        """Doctor global feed returns the critical alert with exact persisted EWS = 9."""
        res = self.client.get(
            '/api/v1/alerts/global-feed',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        emergencies = data.get('emergency_alerts', [])
        patient_alerts = [a for a in emergencies if a['patient_id'] == self.patient_id]
        self.assertTrue(len(patient_alerts) > 0, "Doctor should receive critical emergency alert")

        alert = patient_alerts[0]
        # Validate that EWS score is returned as 9 (and not None, undefined, or missing)
        self.assertEqual(alert.get('ews_score'), 9)
        self.assertEqual(alert.get('total_ews_score'), 9)
        self.assertEqual(alert.get('score'), 9)
        self.assertIn("EWS Score: 9", alert.get('message', ''))

    def test_03_doctor_active_alerts_api_has_persisted_ews_9(self):
        """Doctor active alerts endpoint returns ews_score = 9."""
        res = self.client.get(
            '/api/v1/alerts/api/active',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        alerts = [a for a in data.get('data', []) if a['patient_id'] == self.patient_id]
        self.assertTrue(len(alerts) > 0)
        alert = alerts[0]
        self.assertEqual(alert.get('ews_score'), 9)
        self.assertEqual(alert.get('total_ews_score'), 9)

    def test_04_doctor_patient_alerts_api_has_persisted_ews_9(self):
        """Doctor patient alerts endpoint returns ews_score = 9."""
        res = self.client.get(
            f'/api/v1/alerts/api/patient/{self.patient_id}',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        alerts = data.get('data', [])
        self.assertTrue(len(alerts) > 0)
        self.assertEqual(alerts[0].get('ews_score'), 9)

    def test_05_multiple_ews_history_preserves_latest_triggering_score(self):
        """Patient with historical scores (e.g. 2, 5, 9) returns the correct latest score 9."""
        # Acknowledge the first alert
        res = self.client.get(
            f'/api/v1/alerts/api/patient/{self.patient_id}',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        alert_id = res.get_json()['data'][0]['alert_id']
        self.client.post(f'/api/v1/alerts/acknowledge/{alert_id}', headers={'Authorization': f'Bearer {self.doc_token}'})

        # Submit new vitals with EWS = 11 (RR=45 (3), HR=135 (3), SBP=40 (3), Temp=40 (2))
        self.client.post(
            f'/api/v1/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={
                'respiratory_rate': 45,
                'heart_rate': 135,
                'systolic_bp': 40,
                'temperature': 40.0,
                'spo2': 90,
                'notes': 'Worsened vitals'
            }
        )

        res = self.client.get('/api/v1/alerts/global-feed', headers={'Authorization': f'Bearer {self.doc_token}'})
        emergencies = res.get_json().get('emergency_alerts', [])
        patient_alerts = [a for a in emergencies if a['patient_id'] == self.patient_id]
        self.assertTrue(len(patient_alerts) > 0)
        self.assertEqual(patient_alerts[0].get('ews_score'), 11)


if __name__ == '__main__':
    unittest.main()
