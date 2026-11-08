"""
tests/test_general_chat_gemma_fallback.py — Regression Test Suite for General Chat Gemma Fallback & Security.

Covers all 12 required scenarios:
1. General Chat with relevant ChromaDB results + citations.
2. General Chat with no ChromaDB results -> Gemma answers using general knowledge.
3. General Chat with empty ChromaDB collection -> Gemma answers without error.
4. General Chat when ChromaDB is unavailable/raises exception -> Gemma answers without error.
5. General Chat with general non-medical questions.
6. General Chat with general medical-information questions ("What will be the best way to reduce back pain?").
7. General Chat cannot access patient tools (enforced by ToolRegistry & validation).
8. General Chat cannot access MySQL patient records (even if patient_id is passed).
9. General Chat cannot access patient-specific images.
10. Patient Chat still retrieves authorized MySQL data.
11. Patient Chat still retrieves ChromaDB documents.
12. General Chat and Patient Chat use separate system prompts.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatbot.prompts.prompts import (
    GENERAL_CHAT_PROMPT,
    PATIENT_CHAT_PROMPT,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_GENERAL,
)
from chatbot.rag.rag_chatbot import query_rag_chatbot
from chatbot.tools.tool_registry import get_default_tool_registry, ToolRegistry
from chatbot.tools.tool_executor import run_agentic_rag_workflow


class TestGeneralChatGemmaFallback(unittest.TestCase):
    """Automated regression test suite verifying General Chat fallback to Gemma general knowledge."""

    def setUp(self):
        self.registry = get_default_tool_registry()

    # -------------------------------------------------------------------------
    # Scenario 1: General Chat with relevant ChromaDB results
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks")
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_01_general_chat_with_relevant_chromadb_results(self, mock_llm, mock_chroma, mock_ai_cfg):
        """General Chat incorporates approved ChromaDB documents and provides verified citations."""
        mock_chroma.return_value = [
            {
                "content": "ICU admission requires invasive mechanical ventilation or severe shock with EWS >= 7.",
                "source": "hospital_icu_admission_sop_v2.pdf",
                "category": "clinical_protocol",
                "page_number": 3,
                "relevance_score": 0.89,
                "document_title": "ICU Admission SOP",
            }
        ]
        mock_llm.return_value = (
            True,
            "Based on the hospital's approved ICU admission protocol, admission requires invasive mechanical ventilation or severe shock.",
            {"model": "google/gemma-4-31b-it:free", "provider": "openrouter"}
        )

        resp = query_rag_chatbot(
            user_id=1,
            message="What is the hospital's approved ICU admission protocol?",
            active_patient_id=None,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "general")
        self.assertIsNone(resp["patient_id"])
        self.assertEqual(len(resp["rag_sources"]), 1)
        self.assertEqual(resp["rag_sources"][0]["document_title"], "ICU Admission SOP")
        self.assertIn("hospital's approved ICU admission protocol", resp["text"])
        self.assertEqual(len(resp["mysql_sources"]), 0)

    # -------------------------------------------------------------------------
    # Scenario 2: General Chat with no ChromaDB results -> Gemma answers using general knowledge
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks", return_value=[])
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_02_general_chat_with_no_chromadb_results_uses_gemma(self, mock_llm, mock_chroma, mock_ai_cfg):
        """When ChromaDB has zero results, Gemma answers using general medical knowledge without rejecting."""
        gemma_answer = (
            "**Managing Back Pain (Evidence-Based Self-Care):**\n\n"
            "To reduce lower back pain effectively, consider the following evidence-based approaches:\n"
            "• **Stay Active:** Gentle movement and light walking prevent stiffness; avoid prolonged bed rest.\n"
            "• **Heat & Cold Application:** Apply cold compresses during acute flare-ups and warm packs to relax tight muscles.\n"
            "• **Ergonomic Posture:** Maintain neutral lumbar curvature and lift with the knees.\n"
            "• **Red Flags:** Seek emergency evaluation for progressive leg weakness or bowel/bladder incontinence."
        )
        mock_llm.return_value = (
            True,
            gemma_answer,
            {"model": "google/gemma-4-31b-it:free", "provider": "openrouter"}
        )

        resp = query_rag_chatbot(
            user_id=1,
            message="What will be the best way to reduce back pain?",
            active_patient_id=None,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "general")
        self.assertIsNone(resp["patient_id"])
        # No citations when no ChromaDB sources exist
        self.assertEqual(len(resp["rag_sources"]), 0)
        # Verify answer content
        self.assertIn("Managing Back Pain", resp["text"])
        self.assertIn("Stay Active", resp["text"])
        # Verify absence of the broken fallback template
        self.assertNotIn("While I don't have a detailed knowledge base entry", resp["text"])
        self.assertNotIn("patient-specific telemetry data", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 3: General Chat with empty ChromaDB collection
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks", return_value=[])
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_03_general_chat_empty_chromadb_collection(self, mock_llm, mock_chroma, mock_ai_cfg):
        """Empty ChromaDB collection does not cause errors; Gemma answers directly."""
        mock_llm.return_value = (
            True,
            "Viruses require a living host cell to replicate, whereas bacteria are single-celled organisms that can survive independently.",
            {"model": "google/gemma-4-31b-it:free"}
        )

        resp = query_rag_chatbot(
            user_id=1,
            message="Explain the difference between a virus and bacteria.",
            active_patient_id=None,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "general")
        self.assertEqual(len(resp["rag_sources"]), 0)
        self.assertIn("Viruses require a living host", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 4: General Chat when ChromaDB is unavailable
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks", side_effect=Exception("ChromaDB vector store connection timed out"))
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_04_general_chat_chromadb_unavailable_still_answers(self, mock_llm, mock_chroma, mock_ai_cfg):
        """If ChromaDB throws an exception, General Chat continues seamlessly with Gemma general knowledge."""
        mock_llm.return_value = (
            True,
            "Hypertension is primarily caused by increased systemic vascular resistance, arterial stiffness, and renal fluid regulation imbalance.",
            {"model": "google/gemma-4-31b-it:free"}
        )

        resp = query_rag_chatbot(
            user_id=1,
            message="What causes hypertension?",
            active_patient_id=None,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "general")
        self.assertEqual(len(resp["rag_sources"]), 0)
        self.assertIn("Hypertension is primarily caused", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 5: General Chat with general non-medical question
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks", return_value=[])
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_05_general_chat_nonmedical_question(self, mock_llm, mock_chroma, mock_ai_cfg):
        """General non-medical concepts are handled cleanly by Gemma without retrieval failure."""
        mock_llm.return_value = (
            True,
            "RAM (Random Access Memory) provides high-speed volatile storage for executing processes, while SSD/HDD provides persistent non-volatile storage.",
            {"model": "google/gemma-4-31b-it:free"}
        )

        resp = query_rag_chatbot(
            user_id=1,
            message="How does computer memory work?",
            active_patient_id=None,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "general")
        self.assertEqual(len(resp["rag_sources"]), 0)
        self.assertIn("Random Access Memory", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 6: General Chat with medical information question
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks", return_value=[])
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_06_general_chat_medical_information_question(self, mock_llm, mock_chroma, mock_ai_cfg):
        """General medical questions return accurate educational ranges without patient data."""
        mock_llm.return_value = (
            True,
            "The normal resting adult respiratory rate is typically 12 to 20 breaths per minute. A rate above 24 indicates tachypnea.",
            {"model": "google/gemma-4-31b-it:free"}
        )

        resp = query_rag_chatbot(
            user_id=1,
            message="What is the normal adult respiratory rate?",
            active_patient_id=None,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertIn("12 to 20 breaths per minute", resp["text"])
        self.assertIsNone(resp["patient_id"])
        self.assertEqual(len(resp["mysql_sources"]), 0)

    # -------------------------------------------------------------------------
    # Scenario 7: General Chat cannot access patient tools
    # -------------------------------------------------------------------------
    def test_07_general_chat_cannot_access_patient_tools(self):
        """In General Chat mode, ToolRegistry strictly excludes all MySQL patient tools."""
        general_tools = self.registry.list_tools_for_mode(chat_mode="general", user_role="doctor")
        general_tool_names = [t.name for t in general_tools]

        patient_only_tools = [
            "get_patient_summary",
            "get_patient_vitals",
            "get_patient_ews",
            "get_patient_recommendations",
            "get_patient_transfer_history",
            "get_patient_clinical_notes",
            "get_patient_alerts",
            "get_patient_bed_and_ward_details",
        ]

        for pt in patient_only_tools:
            self.assertNotIn(pt, general_tool_names, f"Tool '{pt}' should NOT be available in General Mode!")

            # Validate that execution validation rejects it
            is_valid, err_msg, _ = self.registry.validate_tool_call(
                tool_name=pt,
                arguments={"patient_id": 2},
                chat_mode="general",
                user_id=1,
                user_role="doctor",
            )
            self.assertFalse(is_valid, f"Validation must reject '{pt}' in General Mode!")
            self.assertIn("not permitted in 'general' chat mode", err_msg)

    # -------------------------------------------------------------------------
    # Scenario 8: General Chat cannot access MySQL patient records
    # -------------------------------------------------------------------------
    def test_08_general_chat_cannot_access_mysql_patient_records(self):
        """Even if the frontend supplies a patient_id or patient name, General Chat strips it and redirects."""
        resp = query_rag_chatbot(
            user_id=1,
            message="What is Amit Verma's latest heart rate?",
            active_patient_id=2,  # Tampered or leftover ID
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "general")
        self.assertIsNone(resp["patient_id"])
        self.assertEqual(len(resp["mysql_sources"]), 0)
        self.assertIn("General Chat mode", resp["text"])
        self.assertIn("Patient Chat mode", resp["text"])
        # Real patient clinical records must NOT be leaked
        self.assertNotIn("UHID-2026", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 9: General Chat cannot access patient-specific images
    # -------------------------------------------------------------------------
    @patch("chatbot.rag.rag_chatbot.is_ai_configured", return_value=True)
    @patch("chatbot.rag.rag_chatbot.query_openrouter_gemini")
    def test_09_general_chat_cannot_access_patient_images(self, mock_llm, mock_ai_cfg):
        """General Chat has zero multimodal patient image context attached."""
        mock_llm.return_value = (
            True,
            "In General Chat mode, I do not have access to individual patient scans or uploaded medical images.",
            {"model": "google/gemma-4-31b-it:free"}
        )
        resp = query_rag_chatbot(
            user_id=1,
            message="Analyze this patient's uploaded chest x-ray scan.",
            active_patient_id=2,
            user_role="doctor",
            mode="general",
        )

        self.assertTrue(resp["success"])
        self.assertIsNone(resp["patient_id"])
        self.assertEqual(len(resp["mysql_sources"]), 0)
        self.assertIn("General Chat mode", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 10: Patient Chat still retrieves authorized MySQL data
    # -------------------------------------------------------------------------
    @patch("chatbot.services.chatbot_engine.query_openrouter_gemini")
    def test_10_patient_chat_retrieves_authorized_mysql_data(self, mock_llm):
        """Patient Chat mode retrieves authorized MySQL telemetry and patient facts."""
        mock_llm.return_value = (
            True,
            "Patient Anita Devi (UHID-2026-00002) is admitted with acute COPD exacerbation.",
            {"model": "google/gemma-4-31b-it:free"}
        )
        resp = query_rag_chatbot(
            user_id=1,
            message="What are the latest vitals and diagnosis?",
            active_patient_id=2,
            user_role="doctor",
            mode="patient",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "patient")
        self.assertEqual(resp["patient_id"], 2)
        self.assertGreater(len(resp["mysql_sources"]), 0)
        self.assertIn("COPD", resp["text"])

    # -------------------------------------------------------------------------
    # Scenario 11: Patient Chat still retrieves ChromaDB documents
    # -------------------------------------------------------------------------
    @patch("chatbot.services.chatbot_engine.query_openrouter_gemini")
    @patch("chatbot.rag.rag_chatbot._retrieve_chroma_chunks")
    def test_11_patient_chat_retrieves_chromadb_documents(self, mock_chroma, mock_llm):
        """Patient Chat combines MySQL patient facts with ChromaDB protocol retrieval."""
        mock_llm.return_value = (
            True,
            "The patient's status meets the step-down criteria under hospital protocol.",
            {"model": "google/gemma-4-31b-it:free"}
        )
        mock_chroma.return_value = [
            {
                "content": "Step-down from ICU to HDU criteria requires EWS <= 4 for at least 12 hours.",
                "source": "icu_stepdown_criteria_sop.pdf",
                "category": "clinical_protocol",
                "page_number": 1,
                "relevance_score": 0.91,
                "document_title": "ICU Step-Down Protocol",
            }
        ]

        resp = query_rag_chatbot(
            user_id=1,
            message="Compare the patient's status with hospital transfer protocol",
            active_patient_id=2,
            user_role="doctor",
            mode="patient",
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["mode"], "patient")
        self.assertEqual(resp["patient_id"], 2)
        self.assertGreater(len(resp["mysql_sources"]), 0)
        self.assertEqual(len(resp["rag_sources"]), 1)
        self.assertEqual(resp["rag_sources"][0]["document_title"], "ICU Step-Down Protocol")

    # -------------------------------------------------------------------------
    # Scenario 12: General Chat and Patient Chat use separate system prompts
    # -------------------------------------------------------------------------
    def test_12_separate_system_prompts(self):
        """General Chat and Patient Chat prompts have distinct instructions and boundaries."""
        self.assertNotEqual(GENERAL_CHAT_PROMPT, PATIENT_CHAT_PROMPT)

        # General Chat prompt checks
        self.assertIn("GENERAL CHAT MODE", GENERAL_CHAT_PROMPT)
        self.assertIn("SUPPLEMENTARY context, NOT a mandatory prerequisite", GENERAL_CHAT_PROMPT)
        self.assertIn("answer directly, thoroughly, and helpfully using your general medical knowledge", GENERAL_CHAT_PROMPT)
        self.assertIn("NEVER invent or fabricate citations", GENERAL_CHAT_PROMPT)
        self.assertIn("ZERO ACCESS to patient records", GENERAL_CHAT_PROMPT)

        # Patient Chat prompt checks
        self.assertIn("Clinical Decision Support Assistant", PATIENT_CHAT_PROMPT)
        self.assertIn("database context is the authoritative source of truth", PATIENT_CHAT_PROMPT)
        self.assertIn("Always reference the persisted EWS from the backend", PATIENT_CHAT_PROMPT)


if __name__ == "__main__":
    unittest.main()
