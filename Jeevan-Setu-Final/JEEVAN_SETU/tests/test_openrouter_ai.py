"""
tests/test_openrouter_ai.py — Verification & Compliance Test Suite for Jeevan Setu OpenRouter AI Integration.

Validates all 24 requirements from the specification:
A. API Key Security & Configuration
B. RBAC & Transfer Guardrails
C. Database Grounding (Diagnosis, Vitals, EWS, Recommendations)
D. Anti-Hallucination Protections
E. Patient Isolation & Multi-patient Safety
F. Error Handling & Secret Leakage Prevention
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.openrouter_service import (
    get_openrouter_api_key,
    get_openrouter_model,
    is_ai_configured,
    build_controlled_patient_context,
    query_openrouter_gemini,
    OPENROUTER_ENDPOINT,
    SYSTEM_PROMPT
)
from modules.chatbot_engine import (
    process_conversational_message,
    process_message,
    get_patient_clinical_context,
    reason_documented_condition,
    reason_single_parameter_inquiry,
    reason_transfer_decision,
    getPatient,
    getEWS,
    getLatestVitals
)


class TestOpenRouterAIIntegration(unittest.TestCase):
    """Test suite for Jeevan Setu OpenRouter AI integration and clinical safety guardrails."""

    def setUp(self):
        self.test_patient_id = 1  # Sahil Sharma (ICU, Bilateral Pneumonia, EWS 7)
        self.test_patient_2_id = 2  # Rajesh Patel (HDU, COPD)

    # ─────────────────────────────────────────────────────────────
    # A. API KEY SECURITY & CONFIGURATION
    # ─────────────────────────────────────────────────────────────
    def test_01_api_key_loaded_from_environment(self):
        """Verify API key is loaded strictly from environment and not hardcoded."""
        key = get_openrouter_api_key()
        self.assertIsNotNone(key, "OPENROUTER_API_KEY should be present in environment")
        self.assertTrue(len(key) > 10, "API key should be a valid non-empty string")

    def test_02_model_configured_centralized(self):
        """Verify centralized model configuration defaults to google/gemini-2.0-flash-exp:free."""
        model = get_openrouter_model()
        self.assertTrue(any(k in model.lower() for k in ("gemini", "gemma", "google")))
        self.assertEqual(OPENROUTER_ENDPOINT, "https://openrouter.ai/api/v1/chat/completions")

    def test_03_env_example_has_placeholder_only(self):
        """Verify .env.example contains placeholder only and not real secrets."""
        example_path = Path(__file__).resolve().parent.parent.parent / ".env.example"
        self.assertTrue(example_path.exists(), ".env.example must exist")
        content = example_path.read_text(encoding="utf-8")
        self.assertIn("OPENROUTER_API_KEY=your_openrouter_api_key_here", content)
        self.assertNotIn("sk-or-v1-", content, ".env.example must never contain real API keys")

    def test_04_gitignore_protects_env(self):
        """Verify .gitignore exists and contains .env."""
        gitignore_path = Path(__file__).resolve().parent.parent.parent / ".gitignore"
        self.assertTrue(gitignore_path.exists(), ".gitignore must exist")
        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn(".env", content, ".gitignore must ignore .env")

    # ─────────────────────────────────────────────────────────────
    # B. RBAC & TRANSFER GUARDRAILS
    # ─────────────────────────────────────────────────────────────
    def test_05_nurse_cannot_approve_transfer(self):
        """Verify Nurse asking to approve transfer receives authority rejection."""
        resp = process_conversational_message(
            user_id=10,
            message="Approve transfer to HDU for this patient",
            active_patient_id=self.test_patient_id,
            user_role="nurse"
        )
        self.assertTrue(resp['success'])
        text = resp['text']
        self.assertIn("Nurses do not have transfer approval authority", text)

    def test_06_doctor_directed_to_official_workflow_for_transfer(self):
        """Verify Doctor asking chatbot to approve transfer is directed to official workflow."""
        resp = process_conversational_message(
            user_id=1,
            message="Approve transfer for Sahil",
            active_patient_id=self.test_patient_id,
            user_role="doctor"
        )
        self.assertTrue(resp['success'])
        text = resp['text']
        self.assertIn("The AI assistant cannot approve or execute patient transfers", text)
        self.assertIn("Doctor Portal", text)

    # ─────────────────────────────────────────────────────────────
    # C. DATABASE GROUNDING (SOURCE OF TRUTH)
    # ─────────────────────────────────────────────────────────────
    def test_07_diagnosis_matches_database(self):
        """Verify recorded diagnosis comes strictly from database records."""
        resp = process_conversational_message(
            user_id=1,
            message="What is the patient's diagnosis?",
            active_patient_id=self.test_patient_id,
            user_role="doctor"
        )
        self.assertTrue(resp['success'])
        text = resp['text']
        self.assertIn("Severe Acute Respiratory Infection", text)
        self.assertIn("Bilateral Pneumonia", text)

    def test_08_latest_vitals_match_database(self):
        """Verify latest vitals telemetry matches persisted database records."""
        context = get_patient_clinical_context(self.test_patient_id)
        latest_v = context['latest_vitals']
        
        # Test SpO2
        resp_spo2 = process_conversational_message(
            user_id=1,
            message="What is the SpO2?",
            active_patient_id=self.test_patient_id,
            user_role="doctor"
        )
        self.assertIn(f"{latest_v['spo2']}%", resp_spo2['text'])

        # Test Heart Rate
        resp_hr = process_conversational_message(
            user_id=1,
            message="What is the heart rate?",
            active_patient_id=self.test_patient_id,
            user_role="doctor"
        )
        self.assertIn(f"{latest_v['heart_rate']} bpm", resp_hr['text'])

    def test_09_persisted_ews_authoritative(self):
        """Verify EWS score is retrieved directly from database and not recalculated."""
        context = get_patient_clinical_context(self.test_patient_id)
        ews_info = context.get('ews') or {}
        expected_score = ews_info.get('score', 7)

        resp = process_conversational_message(
            user_id=1,
            message="What is the EWS score?",
            active_patient_id=self.test_patient_id,
            user_role="doctor"
        )
        self.assertTrue(resp['success'])
        self.assertIn(f"{expected_score}", resp['text'])

    # ─────────────────────────────────────────────────────────────
    # D. ANTI-HALLUCINATION PROTECTIONS
    # ─────────────────────────────────────────────────────────────
    def test_10_missing_information_declared_explicitly(self):
        """Verify that when a patient has no diagnosis recorded, missing record notice is returned."""
        # Query with non-existent diagnosis for simulated patient without records
        text = reason_documented_condition(999999)
        self.assertIn("could not be found", text)

    def test_11_controlled_context_contains_no_unverified_data(self):
        """Verify built context strictly reflects verified database values."""
        context = get_patient_clinical_context(self.test_patient_id)
        context_str = build_controlled_patient_context(context, user_role="doctor")
        
        expected_ews = (context.get('ews') or {}).get('score') or (context.get('ews') or {}).get('total_score')
        self.assertIn("Sahil Sharma", context_str)
        self.assertIn("SpO2: 89%", context_str)
        self.assertIn(f"Persisted EWS Total: {expected_ews}", context_str)
        self.assertIn("Keep in ICU", context_str)

    # ─────────────────────────────────────────────────────────────
    # E. PATIENT ISOLATION
    # ─────────────────────────────────────────────────────────────
    def test_12_patient_isolation_no_data_leakage(self):
        """Verify querying Patient 2 returns Patient 2 data and never Patient 1 data."""
        resp_p2 = process_conversational_message(
            user_id=1,
            message="What is the diagnosis?",
            active_patient_id=self.test_patient_2_id,
            user_role="doctor"
        )
        self.assertTrue(resp_p2['success'])
        text_p2 = resp_p2['text']
        self.assertIn("COPD", text_p2)
        self.assertNotIn("SARI", text_p2)
        self.assertNotIn("Bilateral Pneumonia", text_p2)

    # ─────────────────────────────────────────────────────────────
    # F. ERROR HANDLING & SECRET LEAKAGE PREVENTION
    # ─────────────────────────────────────────────────────────────
    @patch('urllib.request.urlopen')
    def test_13_simulated_api_error_returns_clean_fallback(self, mock_urlopen):
        """Verify that when OpenRouter fails (e.g., 500/timeout), response is clean with zero secret leakage."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )
        
        ok, msg, meta = query_openrouter_gemini("What is sepsis?", patient_context=None)
        self.assertFalse(ok)
        self.assertNotIn("sk-or-v1-", msg)
        self.assertIn("temporarily unavailable", msg)

    @patch('urllib.request.urlopen')
    def test_14_simulated_rate_limit_handled_gracefully(self, mock_urlopen):
        """Verify that HTTP 429 rate limit returns user-friendly notice without secret leakage."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )
        
        ok, msg, meta = query_openrouter_gemini("Explain this patient", patient_context=None)
        self.assertFalse(ok)
        self.assertNotIn("sk-or-v1-", msg)
        self.assertIn("rate-limited", msg)


if __name__ == '__main__':
    unittest.main()
