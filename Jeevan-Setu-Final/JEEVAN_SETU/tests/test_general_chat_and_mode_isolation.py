"""
tests/test_general_chat_and_mode_isolation.py — Comprehensive tests for General Chat Mode & Patient Isolation in Dr. Setu
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from modules.chatbot_engine import (
    process_conversational_message,
    process_message,
    _fmt_val,
    _fmt_bp,
    _fmt_spo2
)
from modules.openrouter_service import (
    query_openrouter_gemini,
    build_controlled_patient_context
)


class TestGeneralChatAndModeIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    # -------------------------------------------------------------
    # 1. Null / Invalid Clinical Value Formatter Tests
    # -------------------------------------------------------------
    def test_vital_formatters_no_none_or_fake_values(self):
        """Ensure no 'SpO2 None%' or 'BP 120.0/None mmHg' formats."""
        self.assertEqual(_fmt_val(None, "bpm"), "Not recorded")
        self.assertEqual(_fmt_val("None", "bpm"), "Not recorded")
        self.assertEqual(_fmt_val(78, "bpm"), "78 bpm")
        self.assertEqual(_fmt_val(78.0, "bpm"), "78 bpm")

        self.assertEqual(_fmt_spo2(None), "SpO₂: Not recorded")
        self.assertEqual(_fmt_spo2("None"), "SpO₂: Not recorded")
        self.assertEqual(_fmt_spo2(98), "SpO₂ 98%")

        self.assertEqual(_fmt_bp(None, None), "BP: Not recorded")
        self.assertEqual(_fmt_bp(120, None), "Systolic BP 120 mmHg (Diastolic: Not recorded)")
        self.assertEqual(_fmt_bp(None, 80), "Diastolic BP 80 mmHg (Systolic: Not recorded)")
        self.assertEqual(_fmt_bp(120, 80), "120/80 mmHg")

    # -------------------------------------------------------------
    # 2. General Mode - General Healthcare Queries
    # -------------------------------------------------------------
    def test_general_mode_hypertension_query(self):
        """In General Mode, queries like 'What is hypertension?' return educational medical info with no patient context."""
        res = process_conversational_message(
            user_id=1,
            message="What is hypertension?",
            active_patient_id=None,
            user_role="Doctor",
            mode="general"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'general')
        self.assertIsNone(res['patient_context'])
        self.assertIsNone(res['patient_id'])
        # Response should contain general medical explanation
        self.assertTrue(any(w in res['text'].lower() for w in ['blood pressure', 'hypertension', 'arteries', 'elevated']))

    def test_general_mode_ews_explanation(self):
        """In General Mode, 'What is EWS?' gives a general educational definition of Early Warning Score."""
        res = process_conversational_message(
            user_id=1,
            message="What is EWS and why is it used?",
            active_patient_id=None,
            user_role="Doctor",
            mode="general"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'general')
        self.assertIsNone(res['patient_context'])
        self.assertTrue(any(w in res['text'].lower() for w in ['early warning score', 'physiological', 'deterioration', 'clinical']))

    def test_general_mode_normal_vitals(self):
        """In General Mode, asking about normal adult heart rate returns educational ranges."""
        res = process_conversational_message(
            user_id=1,
            message="What is the normal adult heart rate?",
            active_patient_id=None,
            user_role="Doctor",
            mode="general"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'general')
        self.assertIn('60', res['text'])
        self.assertIn('100', res['text'])

    def test_general_mode_icu_vs_hdu(self):
        """In General Mode, asking difference between ICU and HDU returns educational distinction."""
        res = process_conversational_message(
            user_id=1,
            message="What is the difference between ICU and HDU?",
            active_patient_id=None,
            user_role="Doctor",
            mode="general"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'general')
        self.assertTrue('intensive care' in res['text'].lower() or 'high dependency' in res['text'].lower())

    # -------------------------------------------------------------
    # 3. Patient Name Leakage & Redirection in General Mode
    # -------------------------------------------------------------
    def test_general_mode_redirects_patient_name_query(self):
        """In General Mode, asking 'What is Amit Verma's EWS?' must NOT leak data and must prompt Patient Chat mode."""
        res = process_conversational_message(
            user_id=1,
            message="What is Amit Verma's current EWS?",
            active_patient_id=None,
            user_role="Doctor",
            mode="general"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'general')
        self.assertIsNone(res['patient_context'])
        self.assertIn("General Chat mode", res['text'])
        self.assertIn("Patient Chat mode", res['text'])
        # Must not contain real patient clinical records
        self.assertNotIn("UHID-2026", res['text'])

    def test_general_mode_ignores_tampered_patient_id(self):
        """If a client sends patient_id in general mode, it must be detached and zero patient context used."""
        res = process_conversational_message(
            user_id=1,
            message="What is sepsis?",
            active_patient_id=999,  # tampered/attached
            user_role="Doctor",
            mode="general"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'general')
        self.assertIsNone(res['patient_id'])
        self.assertIsNone(res['patient_context'])
        self.assertTrue(any(w in res['text'].lower() for w in ['sepsis', 'infection', 'organ']))

    # -------------------------------------------------------------
    # 4. Patient Mode - Grounded Database Operations
    # -------------------------------------------------------------
    def test_patient_mode_uses_database_context(self):
        """In Patient Mode with active patient (id 2), response uses real patient database context."""
        res = process_conversational_message(
            user_id=1,
            message="What are the latest vitals and condition?",
            active_patient_id=2,
            user_role="Doctor",
            mode="patient"
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'patient')
        self.assertEqual(res['patient_id'], 2)
        self.assertIsNotNone(res['patient_context'])
        self.assertIn("COPD", res['text'])
        self.assertTrue("Anita Devi" in res['text'] or "Amit Verma" in res['text'])

    # -------------------------------------------------------------
    # 5. Mode Switching & State Isolation
    # -------------------------------------------------------------
    def test_mode_switching_sequence(self):
        """Test sequential mode switching: Patient -> General -> Patient -> General."""
        # Step 1: Patient mode with id 2
        res1 = process_conversational_message(user_id=1, message="What is the documented diagnosis?", active_patient_id=2, mode="patient")
        self.assertEqual(res1['mode'], 'patient')
        self.assertIn("COPD", res1['text'])

        # Step 2: Switch to General mode
        res2 = process_conversational_message(user_id=1, message="What is tachycardia?", active_patient_id=None, mode="general")
        self.assertEqual(res2['mode'], 'general')
        self.assertIsNone(res2['patient_context'])
        self.assertNotIn("Anita Devi", res2['text'])
        self.assertNotIn("Amit Verma", res2['text'])
        self.assertTrue('heart rate' in res2['text'].lower() or 'tachycardia' in res2['text'].lower())

        # Step 3: Switch back to Patient mode
        res3 = process_conversational_message(user_id=1, message="What is the EWS score?", active_patient_id=2, mode="patient")
        self.assertEqual(res3['mode'], 'patient')
        self.assertEqual(res3['patient_id'], 2)
        self.assertTrue("Anita Devi" in res3['text'] or "Amit Verma" in res3['text'])
        self.assertTrue("Early Warning Score" in res3['text'] or "EWS" in res3['text'])

        # Step 4: Switch back to General mode
        res4 = process_conversational_message(user_id=1, message="What is oxygen saturation?", active_patient_id=None, mode="general")
        self.assertEqual(res4['mode'], 'general')
        self.assertIsNone(res4['patient_context'])
        self.assertNotIn("Anita Devi", res4['text'])
        self.assertNotIn("Amit Verma", res4['text'])

    # -------------------------------------------------------------
    # 6. Route API Endpoints & RBAC Validation
    # -------------------------------------------------------------
    @patch('routes.chatbot_routes.verify_user_patient_access')
    def test_route_patient_mode_unauthorized_returns_403(self, mock_access):
        """Patient mode route enforces RBAC and returns 403 when user is not authorized for patient."""
        mock_access.return_value = (False, "You are not assigned or authorized for this patient.")

        with self.client as c:
            res = c.post('/chatbot/message', json={
                'message': 'Show vitals',
                'mode': 'patient',
                'patient_id': 99
            })
            self.assertEqual(res.status_code, 403)
            data = res.get_json()
            self.assertFalse(data['success'])
            self.assertIn('not assigned or authorized', data['error'].lower())

    def test_route_general_mode_does_not_require_patient_access(self):
        """General mode route succeeds without patient authorization check."""
        with self.client as c:
            res = c.post('/chatbot/message', json={
                'message': 'What is hypertension?',
                'mode': 'general'
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['mode'], 'general')
            self.assertIsNone(data['patient_context'])


if __name__ == '__main__':
    unittest.main()
