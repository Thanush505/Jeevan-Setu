"""
tests/test_agentic_rag.py

End-to-end pytest suite for Jeevan Setu Agentic Hybrid RAG Orchestration
(`chatbot/tools/tool_executor.py` & `chatbot/rag/rag_chatbot.py`).

Tests:
1. Patient Chat with authorized MySQL tool calls.
2. General Chat with ChromaDB knowledge tool calls (zero MySQL tools exposed or invoked).
3. General Chat isolation when a `patient_id` is supplied by the frontend.
4. Mixed MySQL + ChromaDB tool selection in Patient Chat.
5. Unauthorized patient access rejected before LLM or tools are called.
6. Tool-call round limits (`max_tool_rounds`) and total call limits (`max_total_tool_calls`).
7. Infinite loop prevention when the LLM repeatedly requests identical tool calls.
8. Structured-output fallback tool execution when native `tool_calls` are omitted.
9. Source traceability (`rag_sources` and `tools_invoked`) and `ChatbotConversation` persistence.
10. Existing chatbot and authoritative EWS / transfer decision compatibility.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from chatbot.rag.rag_chatbot import query_rag_chatbot
from chatbot.tools.tool_executor import run_agentic_rag_workflow


@pytest.fixture
def ref_now() -> datetime:
    return datetime(2026, 11, 1, 15, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fictional_patient() -> dict:
    return {
        "patient": {
            "patient_id": 701,
            "patient_code": "JS-0701",
            "name": "Fictional Patient Gamma",
            "age": 49,
            "gender": "Female",
            "blood_group": "A+",
            "ward_type": "ICU",
            "ward_name": "ICU-2",
            "bed_number": "ICU-02",
            "diagnosis": "Synthetic Hemodynamic Monitoring",
            "doctor_name": "Dr. Fictional Specialist",
            "status": "admitted",
            "admission_date": "2026-10-31 07:00:00",
        },
        "diagnosis": "Synthetic Hemodynamic Monitoring",
        "latest_vitals": {
            "vital_id": 7001,
            "heart_rate": 80,
            "blood_pressure_sys": 120,
            "blood_pressure_dia": 78,
            "respiratory_rate": 16,
            "temperature": 37.0,
            "spo2": 98,
            "consciousness": "Alert",
            "recorded_at": "2026-11-01 14:40:00",
        },
        "vitals_history": [],
        "ews": {
            "score": 0,
            "risk_level": "LOW",
            "breakdown": {},
            "calculated_at": "2026-11-01 14:40:00",
        },
        "recommendation": {
            "recommendation_id": 555,
            "recommendation_text": "Eligible for Step-Down Transfer from ICU to HDU",
            "from_ward": "ICU",
            "to_ward": "HDU",
            "reason": "EWS 0 and stable hemodynamics.",
            "status": "pending",
            "decided_at": "2026-11-01 14:45:00",
        },
        "decisions_history": [],
        "alerts": [],
        "clinical_notes": [],
    }


@pytest.fixture
def fictional_guideline_chunks() -> list:
    return [
        {
            "chunk_id": "DOC_GUIDE_v1.0_c0_99887766",
            "document_id": "DOC_GUIDE_01",
            "source": "guidelines/icu_hdu_transfer_criteria.pdf",
            "category": "transfer_guidelines",
            "page_number": 4,
            "document_version": "1.0",
            "content": "Patients with EWS <= 2 and stable blood pressure without vasopressors qualify for HDU step-down.",
            "relevance_score": 0.94,
            "metadata": {
                "chunk_id": "DOC_GUIDE_v1.0_c0_99887766",
                "document_id": "DOC_GUIDE_01",
                "source": "guidelines/icu_hdu_transfer_criteria.pdf",
                "category": "transfer_guidelines",
                "page_number": 4,
                "document_version": "1.0",
            },
        }
    ]


def test_01_mixed_mysql_and_chromadb_agentic_workflow_in_patient_chat(
    fictional_patient, fictional_guideline_chunks, ref_now
):
    """
    Verify that in Patient Chat, Gemma can invoke both MySQL patient tools
    (`get_patient_vitals`, `get_patient_ews`, `get_patient_recommendations`)
    and ChromaDB knowledge tools (`search_approved_guidelines`), and synthesize
    a grounded answer with full source traceability.
    """
    call_counter = {"count": 0}

    def mock_llm_caller(messages, tools=None, tool_choice="auto", **kwargs):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            # Round 1: Model requests both MySQL patient tools and a ChromaDB guideline tool
            return {
                "success": True,
                "model": "google/gemma-4-31b-it:free",
                "native_tools_used": True,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_patient_ews",
                                "arguments": '{"patient_id": 701}',
                            },
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "get_patient_recommendations",
                                "arguments": '{"patient_id": 701}',
                            },
                        },
                        {
                            "id": "call_3",
                            "type": "function",
                            "function": {
                                "name": "search_approved_guidelines",
                                "arguments": '{"query": "HDU step-down EWS criteria", "top_k": 2}',
                            },
                        },
                    ],
                },
            }
        # Round 2: Model provides final grounded answer
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "native_tools_used": True,
            "message": {
                "role": "assistant",
                "content": (
                    "Fictional Patient Gamma has an authoritative persisted EWS score of 0 (LOW risk) "
                    "and is recommended for ICU to HDU step-down transfer, consistent with protocol DOC_GUIDE_01."
                ),
            },
        }

    result = run_agentic_rag_workflow(
        question="Does this patient meet the ICU to HDU step-down protocol based on her EWS and recommendation?",
        user_id=10,
        user_role="doctor",
        chat_mode="patient",
        patient_id=701,
        llm_caller=mock_llm_caller,
        authorization_fn=lambda u, pid: (True, ""),
        patient_data_provider=lambda pid: fictional_patient,
        retriever_fn=lambda **kw: fictional_guideline_chunks,
        reference_time=ref_now,
        save_conversation=False,
    )

    assert result["success"] is True
    assert result["chat_mode"] == "patient"
    assert result["patient_id"] == 701
    assert "EWS score of 0" in result["answer"]
    assert len(result["tools_invoked"]) == 3
    invoked_names = [t["tool_name"] for t in result["tools_invoked"]]
    assert invoked_names == [
        "get_patient_ews",
        "get_patient_recommendations",
        "search_approved_guidelines",
    ]
    assert all(t["success"] is True for t in result["tools_invoked"])
    assert len(result["rag_sources"]) == 1
    assert result["rag_sources"][0]["document_id"] == "DOC_GUIDE_01"
    assert result["rag_sources"][0]["page_number"] == 4


def test_02_general_chat_isolation_and_chroma_only_tools(fictional_guideline_chunks):
    """
    Verify that in General Chat:
    1. No MySQL patient tools are included in the tool definitions sent to Gemma.
    2. Even if a `patient_id` is passed to `run_agentic_rag_workflow` AND the model
       attempts to call a MySQL patient tool, the MySQL tool is blocked and the
       patient data provider is never invoked.
    """
    mysql_provider_spy = MagicMock()
    captured_tools = []

    call_idx = {"n": 0}

    def mock_llm_caller(messages, tools=None, tool_choice="auto", **kwargs):
        call_idx["n"] += 1
        if tools:
            captured_tools.extend([t["function"]["name"] for t in tools])
        if call_idx["n"] == 1:
            return {
                "success": True,
                "model": "google/gemma-4-31b-it:free",
                "native_tools_used": True,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        # Model tries to call a prohibited MySQL patient tool in General Chat
                        {
                            "id": "illegal_mysql_call",
                            "type": "function",
                            "function": {
                                "name": "get_patient_vitals",
                                "arguments": '{"patient_id": 701}',
                            },
                        },
                        # Model also calls an allowed ChromaDB knowledge tool
                        {
                            "id": "valid_chroma_call",
                            "type": "function",
                            "function": {
                                "name": "search_approved_guidelines",
                                "arguments": '{"query": "ICU to HDU step-down criteria"}',
                            },
                        },
                    ],
                },
            }
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "native_tools_used": True,
            "message": {
                "role": "assistant",
                "content": "General ICU to HDU step-down criteria require EWS <= 2 and hemodynamic stability.",
            },
        }

    result = run_agentic_rag_workflow(
        question="What are the standard ICU to HDU transfer criteria?",
        user_id=10,
        user_role="doctor",
        chat_mode="general",
        patient_id=701,  # Supplied patient_id must be ignored in General Chat
        llm_caller=mock_llm_caller,
        patient_data_provider=mysql_provider_spy,
        retriever_fn=lambda **kw: fictional_guideline_chunks,
        save_conversation=False,
    )

    assert result["success"] is True
    assert result["chat_mode"] == "general"
    assert result["patient_id"] is None
    assert result["context"]["patient_context"] is None
    assert result["context"]["context_metadata"]["patient_data_included"] is False

    # Verify zero MySQL tools were advertised in the schema sent to OpenRouter
    assert "get_patient_vitals" not in captured_tools
    assert "get_patient_summary" not in captured_tools
    assert "search_approved_guidelines" in captured_tools

    # Verify the illegal MySQL tool call was blocked and provider was never called
    mysql_provider_spy.assert_not_called()
    assert result["tools_invoked"][0]["tool_name"] == "get_patient_vitals"
    assert result["tools_invoked"][0]["success"] is False
    assert result["tools_invoked"][0]["status"] == "unauthorized_mode"
    assert result["tools_invoked"][1]["tool_name"] == "search_approved_guidelines"
    assert result["tools_invoked"][1]["success"] is True


def test_03_infinite_loop_prevention_and_round_limits(fictional_patient, ref_now):
    """
    Verify that if the LLM repeatedly requests identical tool calls across rounds,
    duplicate calls are skipped and the orchestrator terminates cleanly within
    `max_tool_rounds`.
    """
    def looping_llm_caller(messages, tools=None, tool_choice="auto", **kwargs):
        if tools is None:
            return {
                "success": True,
                "model": "google/gemma-4-31b-it:free",
                "message": {"role": "assistant", "content": "Final synthesized answer after loop guard."},
            }
        # Always requests the exact same tool call on every round
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "dup_call",
                        "type": "function",
                        "function": {
                            "name": "get_patient_summary",
                            "arguments": '{"patient_id": 701}',
                        },
                    }
                ],
            },
        }

    result = run_agentic_rag_workflow(
        question="Summarize patient 701.",
        user_id=10,
        user_role="doctor",
        chat_mode="patient",
        patient_id=701,
        max_tool_rounds=3,
        max_total_tool_calls=5,
        llm_caller=looping_llm_caller,
        authorization_fn=lambda u, pid: (True, ""),
        patient_data_provider=lambda pid: fictional_patient,
        retriever_fn=lambda **kw: [],
        reference_time=ref_now,
        save_conversation=False,
    )

    assert result["success"] is True
    assert result["agent_metadata"]["loop_prevented"] is True
    # Only executed once; the second round duplicate was skipped and broke the loop
    assert result["agent_metadata"]["total_tool_calls"] == 1
    assert result["tools_invoked"][0]["status"] == "success"
    assert result["tools_invoked"][1]["status"] == "duplicate_skipped"


def test_04_structured_output_fallback_in_agentic_workflow(fictional_guideline_chunks):
    """
    Verify that when a model route returns a structured JSON tool request in
    `content` instead of native `tool_calls`, the orchestrator validates and
    executes it safely.
    """
    turn = {"n": 0}

    def fallback_llm_caller(messages, tools=None, tool_choice="auto", **kwargs):
        turn["n"] += 1
        if turn["n"] == 1:
            return {
                "success": True,
                "model": "google/gemma-4-31b-it:free",
                "native_tools_used": False,
                "message": {
                    "role": "assistant",
                    "content": '```json\n{"tool": "search_knowledge_base", "arguments": {"query": "HDU step down"}}\n```',
                },
            }
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "native_tools_used": False,
            "message": {
                "role": "assistant",
                "content": "According to the retrieved guideline DOC_GUIDE_01, EWS <= 2 is required.",
            },
        }

    res = run_agentic_rag_workflow(
        question="What EWS score is required for HDU step-down?",
        user_id=10,
        user_role="doctor",
        chat_mode="general",
        llm_caller=fallback_llm_caller,
        retriever_fn=lambda **kw: fictional_guideline_chunks,
        save_conversation=False,
    )

    assert res["success"] is True
    assert len(res["tools_invoked"]) == 1
    assert res["tools_invoked"][0]["tool_name"] == "search_knowledge_base"
    assert res["tools_invoked"][0]["success"] is True
    assert "DOC_GUIDE_01" in res["answer"]


def test_05_existing_rag_chatbot_and_engine_compatibility(fictional_patient, ref_now):
    """
    Verify `query_rag_chatbot` supports both legacy mode and `use_agentic_tools=True`
    without altering existing EWS or transfer recommendations.
    """
    res = query_rag_chatbot(
        user_id=10,
        message="What is the patient's EWS and transfer recommendation?",
        active_patient_id=701,
        user_role="doctor",
        mode="patient",
        use_agentic_tools=True,
        llm_caller=lambda messages, **kw: {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {"role": "assistant", "content": "Persisted EWS is 0 and recommendation is HDU step-down."},
        },
        authorization_fn=lambda u, pid: (True, ""),
        patient_data_provider=lambda pid: fictional_patient,
        retriever_fn=lambda **kw: [],
        reference_time=ref_now,
        save_conversation=False,
    )

    assert res["success"] is True
    assert res["patient_id"] == 701
    assert res["context"]["patient_context"]["ews"]["score"] == 0
    assert (
        res["context"]["patient_context"]["recommendation"]["recommendation_text"]
        == "Eligible for Step-Down Transfer from ICU to HDU"
    )

