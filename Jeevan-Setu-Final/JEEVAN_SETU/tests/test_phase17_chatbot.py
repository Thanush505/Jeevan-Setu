"""
tests/test_phase17_chatbot.py — Phase 17 Patient-Specific Chatbot Backend Test Suite.

Workflow Tested:
    Doctor selects patient
           ↓
    Chatbot request
           ↓
    Patient ID / authorized context
           ↓
    Retrieve patient data
           ↓
    Retrieve latest vitals
           ↓
    Retrieve EWS
           ↓
    Retrieve recommendation
           ↓
    Generate response

Strict Rules Tested:
    1. Patient-specific context only (patient_id required)
    2. No cross-patient data leakage
    3. No fabricated / invented information
    4. No unsupported diagnosis
    5. Clearly state when information is unavailable
    6. Authorization enforcement (Doctor/Nurse/Admin allowed, Unauthorized 401, Attendant 403)
"""

import sys
import os
import unittest
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.ews_score_model import EWSScore
from models.recommendation_model import Recommendation
from services.auth_service import AuthService


class TestPhase17Chatbot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000) % 100000

        # Create Doctor
        cls.doc_id = User.create(
            username=f"doc_bot_{cls.ts}",
            email=f"doc_bot_{cls.ts}@hospital.com",
            password="DocPassword123!",
            role="doctor",
            full_name="Dr. Chatbot Clinician"
        )
        cls.doctor = User.get_by_id(cls.doc_id)
        cls.doc_token = AuthService.generate_access_token(cls.doctor)['access_token']

        # Create Nurse
        cls.nurse_id = User.create(
            username=f"nurse_bot_{cls.ts}",
            email=f"nurse_bot_{cls.ts}@hospital.com",
            password="NursePassword123!",
            role="nurse",
            full_name="Nurse Bot Tester"
        )
        cls.nurse = User.get_by_id(cls.nurse_id)
        cls.nurse_token = AuthService.generate_access_token(cls.nurse)['access_token']

        # Create Attendant
        cls.att_id = User.create(
            username=f"att_bot_{cls.ts}",
            email=f"att_bot_{cls.ts}@hospital.com",
            password="AttPassword123!",
            role="attendant",
            full_name="Attendant Test"
        )
        cls.attendant = User.get_by_id(cls.att_id)
        cls.att_token = AuthService.generate_access_token(cls.attendant)['access_token']

        # Create Patient A (ICU, Critical, Pneumonia)
        cls.patient_a_id = Patient.create(
            name=f"Patient Alpha {cls.ts}",
            age=68,
            gender="male",
            blood_group="A+",
            diagnosis="Severe Bacterial Pneumonia",
            ward_type="ICU",
            bed_number=f"A1-{cls.ts % 10000}",
            assigned_doctor=cls.doc_id
        )

        # Record Patient A Vitals & EWS & Recommendation
        cls.vitals_a_id = Vitals.create(
            patient_id=cls.patient_a_id,
            heart_rate=136,
            blood_pressure_sys=82,
            blood_pressure_dia=52,
            respiratory_rate=28,
            temperature=39.4,
            spo2=89,
            ews_score=8,
            recorded_by=cls.doc_id
        )
        EWSScore.record(cls.patient_a_id, cls.vitals_a_id, 8, 'CRITICAL', hr_score=3, bp_score=3, rr_score=2)
        Recommendation.create(
            patient_id=cls.patient_a_id,
            from_ward="ICU",
            to_ward="ICU",
            recommendation_text="CONTINUE_ICU",
            score=8,
            confidence=0.92,
            reason="Severe physiological instability and high EWS score (8)",
            vital_id=cls.vitals_a_id
        )

        # Create Patient B (HDU, Stable, Post-Op)
        cls.patient_b_id = Patient.create(
            name=f"Patient Beta {cls.ts}",
            age=29,
            gender="female",
            blood_group="B+",
            diagnosis="Post Appendectomy Recovery",
            ward_type="HDU",
            bed_number=f"B1-{cls.ts % 10000}",
            assigned_doctor=cls.doc_id
        )

        # Record Patient B Vitals & EWS
        cls.vitals_b_id = Vitals.create(
            patient_id=cls.patient_b_id,
            heart_rate=72,
            blood_pressure_sys=118,
            blood_pressure_dia=76,
            respiratory_rate=15,
            temperature=36.9,
            spo2=99,
            ews_score=0,
            recorded_by=cls.doc_id
        )
        EWSScore.record(cls.patient_b_id, cls.vitals_b_id, 0, 'LOW', hr_score=0, bp_score=0, rr_score=0)
        Recommendation.create(
            patient_id=cls.patient_b_id,
            from_ward="HDU",
            to_ward="General",
            recommendation_text="TRANSFER_TO_GENERAL",
            score=0,
            confidence=0.95,
            reason="Patient stabilized; step-down criteria satisfied",
            vital_id=cls.vitals_b_id
        )

    def auth_headers(self, token):
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    # ─────────────────────────────────────────────────────────
    # 1. Complete Chatbot Clinical Workflow
    # ─────────────────────────────────────────────────────────
    def test_01_query_patient_vitals_workflow(self):
        """Test Doctor queries latest vitals for selected patient."""
        payload = {
            "patient_id": self.patient_a_id,
            "message": "What is the latest heart rate and blood pressure for this patient?"
        }
        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json=payload
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['patient_id'], self.patient_a_id)
        self.assertEqual(data['intent'], 'vitals_query')

        # Check response references actual stored vitals
        text = data['text']
        self.assertIn("136", text)  # HR
        self.assertIn(f"Patient Alpha {self.ts}", text)

    def test_02_query_patient_ews_workflow(self):
        """Test Doctor queries EWS score for selected patient."""
        payload = {
            "patient_id": self.patient_a_id,
            "message": "What is the current EWS score and risk level?"
        }
        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json=payload
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['intent'], 'ews_query')
        self.assertIn("8", data['text'])
        self.assertIn("CRITICAL", data['text'])

    def test_03_query_patient_recommendation_workflow(self):
        """Test Doctor queries clinical transfer recommendation."""
        payload = {
            "patient_id": self.patient_a_id,
            "message": "What is the transfer recommendation for this patient?"
        }
        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json=payload
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['intent'], 'recommendation_query')
        self.assertIn("CONTINUE_ICU", data['text'])

    def test_04_query_general_patient_summary(self):
        """Test full clinical overview summary for a patient."""
        payload = {
            "patient_id": self.patient_a_id,
            "message": "Give me a summary of this patient."
        }
        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json=payload
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn(f"Patient Alpha {self.ts}", data['text'])
        self.assertIn("Severe Bacterial Pneumonia", data['text'])

    # ─────────────────────────────────────────────────────────
    # 2. Strict Rules Enforcement
    # ─────────────────────────────────────────────────────────
    def test_05_mandatory_patient_id_enforcement(self):
        """Strict Rule 1: Missing patient ID must be rejected."""
        payload = {
            "message": "What are the vitals?"
        }
        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json=payload
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn("Patient ID is required", data['error'])

    def test_06_zero_cross_patient_data_leakage(self):
        """Strict Rule 2: Querying Patient A must NEVER leak Patient B's data."""
        # Query Patient A
        res_a = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json={"patient_id": self.patient_a_id, "message": "Give me a summary"}
        )
        text_a = res_a.get_json()['text']
        self.assertIn("Severe Bacterial Pneumonia", text_a)
        self.assertNotIn("Post Appendectomy Recovery", text_a)
        self.assertNotIn(f"Patient Beta {self.ts}", text_a)

        # Query Patient B
        res_b = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json={"patient_id": self.patient_b_id, "message": "Give me a summary"}
        )
        text_b = res_b.get_json()['text']
        self.assertIn("Post Appendectomy Recovery", text_b)
        self.assertNotIn("Severe Bacterial Pneumonia", text_b)
        self.assertNotIn(f"Patient Alpha {self.ts}", text_b)

    def test_07_no_fabricated_information_rule(self):
        """Strict Rule 3: Missing information must be clearly declared as unavailable."""
        # Create a patient with no vitals
        p_empty_id = Patient.create(
            name=f"Empty Vitals Patient {self.ts}",
            age=40,
            gender="male",
            diagnosis="Observation",
            ward_type="General"
        )

        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json={"patient_id": p_empty_id, "message": "What is the heart rate?"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("No vital sign records are currently available", data['text'])

    def test_08_patient_existence_validation(self):
        """Non-existent patient ID must return 404."""
        res = self.client.post(
            '/chatbot/query',
            headers=self.auth_headers(self.doc_token),
            json={"patient_id": 999999, "message": "Status update"}
        )
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data['success'])

    # ─────────────────────────────────────────────────────────
    # 3. Context & History APIs
    # ─────────────────────────────────────────────────────────
    def test_09_get_patient_context_api(self):
        """Test GET /chatbot/context/{patient_id} and API alias."""
        res = self.client.get(
            f'/chatbot/context/{self.patient_a_id}',
            headers=self.auth_headers(self.doc_token)
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('patient', data['data'])
        self.assertIn('latest_vitals', data['data'])
        self.assertIn('ews', data['data'])
        self.assertIn('recommendation', data['data'])

        # API alias
        res_v1 = self.client.get(
            f'/api/v1/chatbot/context/{self.patient_a_id}',
            headers=self.auth_headers(self.doc_token)
        )
        self.assertEqual(res_v1.status_code, 200)

    def test_10_get_conversation_history_api(self):
        """Test GET /chatbot/history/{patient_id} and GET /chatbot/history."""
        res_p = self.client.get(
            f'/chatbot/history/{self.patient_a_id}',
            headers=self.auth_headers(self.doc_token)
        )
        self.assertEqual(res_p.status_code, 200)
        data_p = res_p.get_json()
        self.assertTrue(data_p['success'])
        self.assertGreater(data_p['count'], 0)

        # User history
        res_u = self.client.get('/chatbot/history', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_u.status_code, 200)
        self.assertTrue(res_u.get_json()['success'])

    # ─────────────────────────────────────────────────────────
    # 4. RBAC & Security Protections
    # ─────────────────────────────────────────────────────────
    def test_11_rbac_protections(self):
        """Verify Nurse is authorized, Attendant is forbidden (403), Unauthenticated is 401."""
        payload = {"patient_id": self.patient_a_id, "message": "Vitals summary"}

        # Nurse authorized
        res_nurse = self.client.post('/chatbot/query', headers=self.auth_headers(self.nurse_token), json=payload)
        self.assertEqual(res_nurse.status_code, 200)

        # Attendant forbidden (403)
        res_att = self.client.post('/chatbot/query', headers=self.auth_headers(self.att_token), json=payload)
        self.assertEqual(res_att.status_code, 403)

        # Unauthenticated rejected (401)
        res_unauth = self.client.post('/chatbot/query', json=payload)
        self.assertEqual(res_unauth.status_code, 401)


if __name__ == '__main__':
    unittest.main()
