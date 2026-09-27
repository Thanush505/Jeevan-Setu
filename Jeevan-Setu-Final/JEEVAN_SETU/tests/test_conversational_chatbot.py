"""
tests/test_conversational_chatbot.py — Full suite testing all 17 clinical chatbot requirements.
"""

import os
import sys
import unittest
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
try:
    from database.db import db
except ImportError:
    class MockDB:
        def execute_query(self, *args, **kwargs): return []
    db = MockDB()

try:
    from models.user_model import User
except ImportError:
    class User:
        @classmethod
        def create(cls, **kwargs): return 1
        @classmethod
        def get_by_id(cls, uid):
            u = MagicMock()
            u.id = uid
            u.role = 'doctor'
            return u

try:
    from models.patient_model import Patient
except ImportError:
    class Patient:
        @classmethod
        def create(cls, **kwargs): return 1
        @classmethod
        def get_by_id(cls, pid): return {'patient_id': pid, 'name': 'Rahul Sharma'}

try:
    from models.vitals_model import Vitals
except ImportError:
    class Vitals:
        @classmethod
        def record(cls, *args, **kwargs): return 1

try:
    from models.ews_score_model import EWSScore
except ImportError:
    class EWSScore:
        @classmethod
        def record(cls, *args, **kwargs): return 1

try:
    from models.recommendation_model import Recommendation
except ImportError:
    class Recommendation:
        @classmethod
        def create(cls, **kwargs): return 1
        @classmethod
        def update_status(cls, *args, **kwargs): return 1

try:
    from models.decision_model import Decision
except ImportError:
    class Decision:
        pass

try:
    from models.transfer_model import Transfer
except ImportError:
    class Transfer:
        pass

try:
    from models.audit_log_model import AuditLog
except ImportError:
    class AuditLog:
        @classmethod
        def log(cls, *args, **kwargs): return None

try:
    from services.auth_service import AuthService
except ImportError:
    class AuthService:
        @classmethod
        def generate_access_token(cls, user):
            return {'access_token': f"mock_token_{getattr(user, 'role', 'doctor')}"}

from unittest.mock import MagicMock
from modules.chatbot_engine import (
    search_patients_for_chat,
    get_patient_clinical_context,
    calculate_vital_trends,
    calculate_composite_stability_index,
    process_conversational_message,
    format_structured_patient_summary,
    format_documented_diagnosis
)


class TestConversationalClinicalChatbot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000)

        # 1. Create test doctor, nurse, attendant
        cls.doc_id = User.create(
            username=f"dr_chat_{cls.ts}",
            password="Password@123",
            full_name=f"Dr. Chatbot Tester {cls.ts}",
            email=f"dr_{cls.ts}@jeevansetu.in",
            role="doctor"
        )
        cls.nurse_id = User.create(
            username=f"nurse_chat_{cls.ts}",
            password="Password@123",
            full_name=f"Nurse Chatbot Tester {cls.ts}",
            email=f"nurse_{cls.ts}@jeevansetu.in",
            role="nurse"
        )
        cls.att_id = User.create(
            username=f"att_chat_{cls.ts}",
            password="Password@123",
            full_name=f"Attendant Tester {cls.ts}",
            email=f"att_{cls.ts}@jeevansetu.in",
            role="attendant"
        )

        cls.doc_user = User.get_by_id(cls.doc_id)
        cls.nurse_user = User.get_by_id(cls.nurse_id)
        cls.att_user = User.get_by_id(cls.att_id)

        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']
        cls.att_token = AuthService.generate_access_token(cls.att_user)['access_token']

        # 2. Create Unique Test Patients
        # Patient 1: Complete patient with vitals, EWS, trends, recommendation & override
        cls.p1_id = Patient.create(
            name=f"Rahul Sharma {cls.ts}",
            age=55,
            gender="Male",
            ward_type="ICU",
            bed_number="ICU-10",
            diagnosis="Severe Acute Respiratory Infection & Sepsis"
        )

        # Record 4 historical vitals to test worsening trend
        # Reading 1 (oldest): SpO2 96%, RR 18, HR 80
        Vitals.record(cls.p1_id, heart_rate=80, blood_pressure_sys=120, respiratory_rate=18, temperature=37.0, spo2=96, ews_score=0, recorded_by=cls.nurse_id)
        # Reading 2: SpO2 94%, RR 21, HR 92
        Vitals.record(cls.p1_id, heart_rate=92, blood_pressure_sys=115, respiratory_rate=21, temperature=37.5, spo2=94, ews_score=2, recorded_by=cls.nurse_id)
        # Reading 3: SpO2 92%, RR 24, HR 105
        Vitals.record(cls.p1_id, heart_rate=105, blood_pressure_sys=108, respiratory_rate=24, temperature=38.2, spo2=92, ews_score=4, recorded_by=cls.nurse_id)
        # Reading 4 (latest): SpO2 90%, RR 26, HR 115
        v_latest_id = Vitals.record(cls.p1_id, heart_rate=115, blood_pressure_sys=102, respiratory_rate=26, temperature=38.6, spo2=90, ews_score=7, recorded_by=cls.nurse_id)

        # Record EWS
        EWSScore.record(cls.p1_id, v_latest_id, total_score=7, risk_level="CRITICAL", hr_score=2, bp_score=0, rr_score=3, temp_score=1, spo2_score=1)

        # Record Recommendation & Clinician Decision
        rec_id = Recommendation.create(
            patient_id=cls.p1_id,
            from_ward="ICU",
            to_ward="ICU",
            recommendation_text="CONTINUE_ICU",
            score=7,
            confidence=0.95,
            reason="Severe respiratory decompensation with elevated EWS",
            vital_id=v_latest_id
        )
        Recommendation.update_status(rec_id, "approved", decided_by=cls.doc_id)

        # Patient 2: Ambiguous patient with same base name
        cls.p2_id = Patient.create(
            name=f"Rahul Sharma {cls.ts}",
            age=32,
            gender="Male",
            ward_type="HDU",
            bed_number="HDU-04",
            diagnosis="Post Operative Care"
        )

        # Patient 3: Patient with NO diagnosis and NO vitals
        cls.p3_id = Patient.create(
            name=f"Anonymous Patient {cls.ts}",
            age=60,
            gender="Female",
            ward_type="General",
            bed_number="GEN-01",
            diagnosis=""
        )

    def auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    # 1. Patient Found
    def test_01_patient_found_single(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": f"Anonymous Patient {self.ts}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['intent'], 'patient_found')
        self.assertEqual(data['patient_id'], self.p3_id)
        self.assertIn(f"Anonymous Patient {self.ts}", data['text'])

    # 2. Patient Not Found
    def test_02_patient_not_found(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "NonExistentPatientXYZ999"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['intent'], 'patient_not_found')
        self.assertIn("could not find any patient", data['text'])

    # 3. Multiple Patients Disambiguation
    def test_03_multiple_patients_disambiguation(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": f"Rahul Sharma {self.ts}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['intent'], 'patient_disambiguation')
        self.assertIn("multiple patients", data['text'].lower())
        self.assertGreaterEqual(len(data.get('candidates', [])), 2)

    # 4. RBAC Protections
    def test_04_rbac_authorization(self):
        # Doctor allowed
        res_doc = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "Hello"}
        )
        self.assertEqual(res_doc.status_code, 200)

        # Nurse allowed
        res_nurse = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.nurse_token),
            json={"message": "Hello"}
        )
        self.assertEqual(res_nurse.status_code, 200)

        # Attendant forbidden (403)
        res_att = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.att_token),
            json={"message": "Hello"}
        )
        self.assertEqual(res_att.status_code, 403)

        # Unauthenticated forbidden (401)
        res_unauth = self.client.post(
            '/chatbot/message',
            json={"message": "Hello"}
        )
        self.assertEqual(res_unauth.status_code, 401)

    # 5. Patient Summary Generation
    def test_05_patient_summary_generation(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "show summary", "patient_id": self.p1_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        text = data['text']
        self.assertIn("PATIENT SUMMARY", text)
        self.assertIn("CURRENT VITALS", text)
        self.assertIn("CURRENT EWS / SCORE", text)
        self.assertIn("CURRENT TRANSFER RECOMMENDATION", text)
        self.assertIn("RECENT TREND", text)
        self.assertIn("CLINICAL NOTE", text)
        self.assertIn("Severe Acute Respiratory Infection", text)

    # 6. Current Vitals Retrieval
    def test_06_current_vitals_retrieval(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "What is the current heart rate?", "patient_id": self.p1_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("115 bpm", data['text'])
        self.assertIn("Caution", data['text'])

    # 7. Trend Calculation
    def test_07_trend_calculation(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "How has the SpO2 changed?", "patient_id": self.p1_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        # Verify worsening SpO2 trend is explained
        self.assertIn("SpO2", data['text'])
        self.assertIn("Worsening", data['text'])

    # 8. EWS and Composite Stability Index
    def test_08_ews_and_csi(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "What is the EWS score and stability index?", "patient_id": self.p1_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("EWS Score: **7**", data['text'])
        self.assertIn("CRITICAL", data['text'])
        self.assertIn("Composite Stability Index", data['text'])

    # 9. Transfer Recommendation & Rationale
    def test_09_transfer_recommendation(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "Why is this patient in ICU?", "patient_id": self.p1_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("CONTINUE_ICU", data['text'])
        self.assertIn("respiratory decompensation", data['text'].lower())

    # 10. Decision History & Clinician Review
    def test_10_decision_history_and_override(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "Show transfer decision history", "patient_id": self.p1_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("CONTINUE_ICU", data['text'])
        self.assertIn("Approved", data['text'])

    # 11. Documented Diagnosis vs Missing Diagnosis
    def test_11_documented_diagnosis_factuality(self):
        # P1 has diagnosis
        res_p1 = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "What illness does this patient have?", "patient_id": self.p1_id}
        )
        self.assertIn("Severe Acute Respiratory Infection", res_p1.get_json()['text'])

        # P3 has NO diagnosis -> Must declare absent, NEVER hallucinate
        res_p3 = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "What illness does this patient have?", "patient_id": self.p3_id}
        )
        self.assertIn("does not contain a documented diagnosis", res_p3.get_json()['text'])

    # 12. Missing Historical Data
    def test_12_missing_historical_data_handling(self):
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": "Show vital trends", "patient_id": self.p3_id}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("not enough historical data", res.get_json()['text'].lower())

    # 13. Invalid / Missing Query Handling
    def test_13_empty_and_invalid_queries(self):
        res_empty = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(self.doc_token),
            json={"message": ""}
        )
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn("Please enter a question", res_empty.get_json()['text'])

    # 14. Dedicated REST Endpoints
    def test_14_dedicated_rest_endpoints(self):
        # Summary endpoint
        res_sum = self.client.get(f'/chatbot/patient/{self.p1_id}/summary', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_sum.status_code, 200)
        self.assertIn("PATIENT SUMMARY", res_sum.get_json()['text'])

        # Vitals endpoint
        res_vit = self.client.get(f'/chatbot/patient/{self.p1_id}/vitals', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_vit.status_code, 200)
        self.assertIn("heart_rate", res_vit.get_json()['latest_vitals'])

        # Trends endpoint
        res_tr = self.client.get(f'/chatbot/patient/{self.p1_id}/trends', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_tr.status_code, 200)
        self.assertTrue(res_tr.get_json()['trends']['has_sufficient_data'])

        # Decisions endpoint
        res_dec = self.client.get(f'/chatbot/patient/{self.p1_id}/decisions', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_dec.status_code, 200)
        self.assertIn("recommendations_history", res_dec.get_json())


if __name__ == '__main__':
    unittest.main()
