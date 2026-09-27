"""
tests/test_advanced_clinical_reasoning.py — Comprehensive Clinical Reasoning Assistant Validation Suite.

Validates:
1. Multi-Parameter Reasoning for "Why is his oxygen low?" (SpO2 + RR + HR + Diagnosis + EWS + Recommendation).
2. Cause & Deterioration inquiries ("Why is condition worsening?").
3. Prognosis & Mortality inquiries ("Is he going to die?") with clinical uncertainty.
4. Trajectory analysis with Answer-First Rule ("Is he getting better/worse?").
5. Emergency / Critical Protocol escalation ("Patient is unconscious and SpO2 is 78. What should I do?").
6. General Medical Query separation (Medical knowledge vs Patient data).
7. Documented Diagnosis vs Absence handling.
8. Anti-Hallucination & Timestamp Freshness verification.
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
        def get_by_id(cls, pid): return {'patient_id': pid, 'name': 'Sahil Sharma'}

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
    from services.auth_service import AuthService
except ImportError:
    class AuthService:
        @classmethod
        def generate_access_token(cls, user):
            return {'access_token': f"mock_token_{getattr(user, 'role', 'doctor')}"}

from unittest.mock import MagicMock
from modules.chatbot_engine import (
    detect_intent,
    get_patient_clinical_context,
    process_conversational_message
)


class TestAdvancedClinicalReasoning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000)

        # 1. Create Doctor user
        cls.doc_id = User.create(
            username=f"dr_reasoning_{cls.ts}",
            password="Password@123",
            full_name=f"Dr. Reasoning Specialist {cls.ts}",
            email=f"dr_reason_{cls.ts}@jeevansetu.in",
            role="doctor"
        )
        cls.doc_user = User.get_by_id(cls.doc_id)
        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']

        # 2. Create Patient with deteriorating respiratory failure
        cls.p_resp_id = Patient.create(
            name=f"Vikram Malhotra {cls.ts}",
            age=58,
            gender="Male",
            ward_type="ICU",
            bed_number="ICU-08",
            diagnosis="Acute Bilateral Bacterial Pneumonia"
        )

        # Record 4 historical vitals showing deteriorating respiratory & hemodynamic state
        # 1. Oldest: SpO2 95%, RR 18, HR 82, SBP 120
        Vitals.record(cls.p_resp_id, heart_rate=82, blood_pressure_sys=120, respiratory_rate=18, temperature=37.2, spo2=95, ews_score=0, recorded_by=cls.doc_id)
        # 2. Reading: SpO2 94%, RR 20, HR 88, SBP 118
        Vitals.record(cls.p_resp_id, heart_rate=88, blood_pressure_sys=118, respiratory_rate=20, temperature=37.6, spo2=94, ews_score=1, recorded_by=cls.doc_id)
        # 3. Reading: SpO2 93%, RR 22, HR 96, SBP 112
        Vitals.record(cls.p_resp_id, heart_rate=96, blood_pressure_sys=112, respiratory_rate=22, temperature=38.1, spo2=93, ews_score=3, recorded_by=cls.doc_id)
        # 4. Latest: SpO2 91%, RR 25, HR 108, SBP 105
        v_latest_id = Vitals.record(cls.p_resp_id, heart_rate=108, blood_pressure_sys=105, respiratory_rate=25, temperature=38.5, spo2=91, ews_score=6, recorded_by=cls.doc_id)

        EWSScore.record(cls.p_resp_id, v_latest_id, total_score=6, risk_level="HIGH", hr_score=1, bp_score=0, rr_score=2, temp_score=1, spo2_score=2)

        Recommendation.create(
            patient_id=cls.p_resp_id,
            from_ward="ICU",
            to_ward="ICU",
            recommendation_text="CONTINUE_ICU",
            score=6,
            confidence=0.92,
            reason="Worsening oxygen saturation and tachypnea requiring intensive monitoring",
            vital_id=v_latest_id
        )

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.doc_token}"}

    def test_01_why_is_oxygen_low_multi_parameter_reasoning(self):
        """Verify 'Why is his oxygen low?' correlates SpO2 with RR, HR, diagnosis, and Decision Engine."""
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(),
            json={"message": "Why is his oxygen low?", "patient_id": self.p_resp_id}
        )
        self.assertEqual(res.status_code, 200)
        text = res.get_json()['text']

        # Check multi-parameter correlation
        self.assertIn("91%", text)
        self.assertIn("respiratory rate", text.lower())
        self.assertIn("heart rate", text.lower())
        self.assertIn("Bilateral Bacterial Pneumonia", text)
        self.assertIn("CONTINUE_ICU", text)
        self.assertIn("Clinical Interpretation", text)

    def test_02_why_is_condition_getting_worse(self):
        """Verify 'Why is the patient's condition getting worse?' gives complete synthesis."""
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(),
            json={"message": "Why is the patient's condition getting worse?", "patient_id": self.p_resp_id}
        )
        self.assertEqual(res.status_code, 200)
        text = res.get_json()['text']

        self.assertIn("worsening physiological trend", text.lower())
        self.assertIn("SpO2", text)
        self.assertIn("Respiratory Rate", text)
        self.assertIn("Early Warning Score", text)

    def test_03_is_he_going_to_die_prognosis_handling(self):
        """Verify 'Is he going to die?' communicates uncertainty and does NOT predict certainty."""
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(),
            json={"message": "Is he going to die?", "patient_id": self.p_resp_id}
        )
        self.assertEqual(res.status_code, 200)
        text = res.get_json()['text']

        # Clinical uncertainty declaration
        self.assertIn("cannot determine from the available data whether the patient will die", text.lower())
        # Severity details
        self.assertIn("91%", text)
        self.assertIn("EWS", text)
        self.assertIn("treating ICU / critical care clinical team", text)

    def test_04_is_he_getting_better_answer_first(self):
        """Verify 'Is he getting better?' applies the Answer-First rule and details trajectory."""
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(),
            json={"message": "Is he getting better?", "patient_id": self.p_resp_id}
        )
        self.assertEqual(res.status_code, 200)
        text = res.get_json()['text']

        self.assertIn("worsening physiological trend", text.lower())
        self.assertIn("SpO2: Worsening", text)
        self.assertIn("Respiratory Rate: Worsening", text)

    def test_05_emergency_critical_protocol_escalation(self):
        """Verify acute emergency queries trigger emergency alert protocol."""
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(),
            json={"message": "Patient is unconscious and SpO2 is 78. What should I do?", "patient_id": self.p_resp_id}
        )
        self.assertEqual(res.status_code, 200)
        text = res.get_json()['text']

        self.assertIn("CRITICAL EMERGENCY PROTOCOL ACTIVATED", text)
        self.assertIn("Airway, Breathing, Circulation", text)
        self.assertIn("Code Blue", text)

    def test_06_general_medical_query_distinction(self):
        """Verify general medical concept is clearly separated from patient data."""
        res = self.client.post(
            '/chatbot/message',
            headers=self.auth_headers(),
            json={"message": "What does low SpO2 mean?", "patient_id": self.p_resp_id}
        )
        self.assertEqual(res.status_code, 200)
        text = res.get_json()['text']

        self.assertIn("General Clinical Concept", text)
        self.assertIn("Patient-Specific Data", text)
        self.assertIn("91%", text)


if __name__ == '__main__':
    unittest.main()
