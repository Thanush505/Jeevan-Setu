"""
chatbot/rag/rag_chatbot.py — Unified Agentic Hybrid Multimodal RAG Chatbot Engine for Jeevan Setu.

Centralized backend engine shared by:
- Doctor Patient Summary AI Page (`/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html`)
- Nurse Patient Summary AI Page (`/Nurse/Nurse_patient_summary_ai/Nurse_patient_summary_ai.html`)
- Flask Chatbot REST APIs (`/chatbot/message`, `/api/v1/chatbot/message`, `/chatbot/query`, `/api/v1/chatbot/query`)

Responsibilities:
1. Enforce strict mode separation between Patient Chat (`mode='patient'`) and General Chat (`mode='general'`).
2. Combine verified MySQL patient facts (via authorized CCRL / patient tools) with ChromaDB hospital
   SOPs, clinical protocols, approved guidelines, and multimodal OCR/vision document descriptions.
3. Preserve authoritative EWS and ICU/HDU transfer recommendations without independent recalculation.
4. Provide structured `rag_sources` (ChromaDB citations), `mysql_sources` (patient fact citations),
   and `tools_invoked` audit trails for transparent frontend source reference display.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from chatbot.rag.context_builder import build_hybrid_context, build_rag_context
from chatbot.rag.retriever import retrieve_relevant_chunks as retrieve_knowledge_chunks
from chatbot.services.chatbot_engine import (
    process_conversational_message,
    extract_explicit_patient_mention,
    reason_general_medical_query,
)
from chatbot.services.openrouter_service import (
    is_ai_configured,
    query_openrouter_gemini,
)
from chatbot.tools.tool_executor import run_agentic_rag_workflow

logger = logging.getLogger("jeevan_setu.rag.chatbot")

try:
    from models.chatbot_model import ChatbotConversation
except (ImportError, ModuleNotFoundError):
    ChatbotConversation = None

try:
    from chatbot.vision.image_processor import get_authorized_patient_images
except (ImportError, ModuleNotFoundError):
    get_authorized_patient_images = None


_PROTOCOL_KEYWORDS_RE = re.compile(
    r"\b("
    r"protocol|protocols|sop|sops|guideline|guidelines|policy|policies|"
    r"criteria|admission\s+criteria|step[- ]?down\s+criteria|discharge\s+criteria|"
    r"escalation\s+protocol|monitoring\s+protocol|nursing\s+sop|nursing\s+protocol|"
    r"handover\s+protocol|transfer\s+protocol|compare.*protocol|compare.*guideline|"
    r"compare.*sop|according\s+to\s+protocol|hospital\s+guideline|standard\s+operating"
    r")\b",
    re.IGNORECASE,
)

_IMAGE_QUERY_RE = re.compile(
    r"\b("
    r"uploaded\s+image|medical\s+image|monitor\s+screenshot|monitor\s+snapshot|"
    r"ecg\s+image|xray|x-ray|chest\s+scan|ct\s+scan|lab\s+report\s+image|"
    r"ocr\s+text|image\s+analysis|scan\s+report"
    r")\b",
    re.IGNORECASE,
)


def _select_chroma_tool_name(query: str, user_role: str = "doctor") -> str:
    """Choose the most specific ChromaDB tool identifier for audit logging."""
    q_low = (query or "").lower()
    if "sop" in q_low or "standard operating" in q_low or "nursing" in q_low or "handover" in q_low:
        return "search_hospital_sops"
    if "guideline" in q_low or "step-down" in q_low or "step down" in q_low or "criteria" in q_low:
        return "search_approved_guidelines"
    if "protocol" in q_low or "escalation" in q_low or "admission" in q_low:
        return "search_clinical_protocols"
    return "search_knowledge_base"


def _retrieve_chroma_chunks(
    query: str,
    top_k: int = 3,
    retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """Safely retrieve relevant knowledge chunks from ChromaDB without raising on empty/offline store."""
    if not query or not isinstance(query, str) or not query.strip():
        return []
    try:
        if callable(retriever_fn):
            raw = retriever_fn(query=query.strip(), top_k=top_k)
        else:
            raw = retrieve_knowledge_chunks(query=query.strip(), top_k=top_k)
        return list(raw) if isinstance(raw, list) else []
    except Exception as exc:
        logger.debug("ChromaDB retrieval skipped or unavailable: %s", type(exc).__name__)
        return []


def _format_rag_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert retrieved ChromaDB chunks into normalized frontend-ready source reference dicts:
    - document_title
    - source_file
    - page_number
    - category
    - excerpt
    - document_id
    - chunk_id
    - relevance_score
    - content_type
    """
    sources: List[Dict[str, Any]] = []
    seen_keys = set()

    for ch in chunks or []:
        if not isinstance(ch, dict):
            continue
        meta = ch.get("metadata") if isinstance(ch.get("metadata"), dict) else {}
        chunk_id = str(ch.get("chunk_id") or meta.get("chunk_id") or "")
        doc_id = str(ch.get("document_id") or meta.get("document_id") or "")
        source_file = str(
            ch.get("source_file")
            or ch.get("source")
            or meta.get("source_file")
            or meta.get("source")
            or "knowledge_base"
        )
        page_num = ch.get("page_number") if ch.get("page_number") is not None else meta.get("page_number")
        dedup_key = chunk_id or f"{source_file}:{page_num}:{doc_id}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        title = (
            ch.get("document_title")
            or meta.get("document_title")
            or meta.get("title")
            or source_file.split("/")[-1].replace("_", " ").replace("-", " ").rsplit(".", 1)[0].title()
        )
        category = str(ch.get("category") or meta.get("category") or "clinical_knowledge")
        content = str(ch.get("content") or ch.get("text") or "").strip()
        excerpt = content[:260] + ("..." if len(content) > 260 else "")
        score = ch.get("relevance_score") if ch.get("relevance_score") is not None else ch.get("score")

        sources.append({
            "source_type": "chromadb",
            "chunk_id": chunk_id or None,
            "document_id": doc_id or None,
            "document_title": str(title),
            "source_file": source_file,
            "page_number": int(page_num) if isinstance(page_num, (int, float)) and int(page_num) > 0 else None,
            "category": category,
            "excerpt": excerpt,
            "relevance_score": round(float(score), 4) if isinstance(score, (int, float)) else None,
            "content_type": str(ch.get("content_type") or meta.get("content_type") or "text"),
            "image_id": ch.get("image_id") or meta.get("image_id"),
            "ai_generated_description": bool(
                ch.get("ai_generated_description") or meta.get("ai_generated_description")
            ),
        })

    return sources


def _build_mysql_sources_from_context(
    patient_context: Optional[Dict[str, Any]],
    query: str = "",
    intent: str = "",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Build structured MySQL patient fact source citations and invoked MySQL tool records
    from the verified `patient_context`.
    Preserves:
    - field
    - value
    - units
    - recorded_at (timestamp)
    - source ('MySQL Patient Record')
    """
    if not isinstance(patient_context, dict) or not patient_context.get("patient"):
        return [], []

    patient = patient_context.get("patient") or {}
    vitals = patient_context.get("latest_vitals") or {}
    ews = patient_context.get("ews") or {}
    rec = patient_context.get("recommendation") or {}
    pid = patient.get("patient_id")

    mysql_sources: List[Dict[str, Any]] = []
    mysql_tools: List[Dict[str, Any]] = []

    q_low = (query or "").lower()
    intent_low = (intent or "").lower()

    include_all = intent_low in ("status_overview", "patient_found", "concise_summary", "expand_detail") or any(
        w in q_low for w in ("summary", "overview", "condition", "compare", "handover", "status")
    )
    include_vitals = include_all or any(
        w in q_low
        for w in (
            "vital", "spo2", "oxygen", "heart rate", "hr", "pulse", "bp",
            "blood pressure", "respiratory", "rr", "temp", "temperature", "trend", "observation"
        )
    )
    include_ews = include_all or any(w in q_low for w in ("ews", "score", "risk", "stability", "csi"))
    include_transfer = include_all or any(
        w in q_low for w in ("transfer", "recommend", "icu", "hdu", "step-down", "step down", "ward", "decision")
    )

    if not (include_vitals or include_ews or include_transfer):
        include_all = True
        include_vitals = True
        include_ews = True
        include_transfer = True

    if include_all:
        mysql_tools.append({
            "tool_name": "get_patient_summary",
            "source_type": "mysql_patient",
            "status": "success",
            "success": True,
            "patient_id": pid,
        })
        if patient.get("diagnosis"):
            mysql_sources.append({
                "source_type": "mysql",
                "field": "Documented Diagnosis",
                "value": str(patient.get("diagnosis")),
                "units": "",
                "recorded_at": str(patient.get("admission_date") or "Admission Record"),
                "source": f"MySQL patients (ID #{pid})",
                "patient_id": pid,
            })

    if include_vitals and vitals:
        mysql_tools.append({
            "tool_name": "get_patient_vitals",
            "source_type": "mysql_patient",
            "status": "success",
            "success": True,
            "patient_id": pid,
        })
        rec_at = str(vitals.get("recorded_at") or "Latest recorded")
        vital_parts = []
        if vitals.get("heart_rate") is not None:
            vital_parts.append(f"HR {vitals['heart_rate']} bpm")
        if vitals.get("spo2") is not None:
            vital_parts.append(f"SpO2 {vitals['spo2']}%")
        if vitals.get("blood_pressure_sys") is not None and vitals.get("blood_pressure_dia") is not None:
            vital_parts.append(f"BP {vitals['blood_pressure_sys']}/{vitals['blood_pressure_dia']} mmHg")
        elif vitals.get("blood_pressure_sys") is not None:
            vital_parts.append(f"Systolic BP {vitals['blood_pressure_sys']} mmHg (Diastolic unrecorded)")
        elif vitals.get("blood_pressure_dia") is not None:
            vital_parts.append(f"Diastolic BP {vitals['blood_pressure_dia']} mmHg (Systolic unrecorded)")
        if vitals.get("respiratory_rate") is not None:
            vital_parts.append(f"RR {vitals['respiratory_rate']} /min")
        if vitals.get("temperature") is not None:
            vital_parts.append(f"Temp {vitals['temperature']} °C")

        if vital_parts:
            mysql_sources.append({
                "source_type": "mysql",
                "field": "Latest Vital Signs",
                "value": ", ".join(vital_parts),
                "units": "bpm / % / mmHg / breaths/min / °C",
                "recorded_at": rec_at,
                "source": f"MySQL vitals (Patient #{pid})",
                "patient_id": pid,
            })

    if include_ews and ews and ews.get("score") is not None:
        mysql_tools.append({
            "tool_name": "get_patient_ews",
            "source_type": "mysql_patient",
            "status": "success",
            "success": True,
            "patient_id": pid,
        })
        mysql_sources.append({
            "source_type": "mysql",
            "field": "Persisted EWS Score",
            "value": f"{ews.get('score')} ({ews.get('risk_level', 'LOW')})",
            "units": "EWS points",
            "recorded_at": str(ews.get("calculated_at") or vitals.get("recorded_at") or "Latest calculation"),
            "source": f"MySQL ews_scores (Patient #{pid})",
            "patient_id": pid,
        })

    if include_transfer and rec and rec.get("recommendation_text"):
        mysql_tools.append({
            "tool_name": "get_patient_recommendations",
            "source_type": "mysql_patient",
            "status": "success",
            "success": True,
            "patient_id": pid,
        })
        mysql_sources.append({
            "source_type": "mysql",
            "field": "Authoritative Transfer Recommendation",
            "value": str(rec.get("recommendation_text")),
            "units": f"{rec.get('from_ward') or 'ICU'} -> {rec.get('to_ward') or rec.get('from_ward') or 'ICU'}",
            "recorded_at": str(rec.get("decided_at") or "Current active decision"),
            "source": f"MySQL recommendations (Patient #{pid})",
            "patient_id": pid,
        })

    return mysql_sources, mysql_tools


def _format_knowledge_synthesis_section(
    rag_sources: List[Dict[str, Any]],
    patient_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Format a concise grounded clinical knowledge & protocol section from retrieved ChromaDB sources.
    When `patient_context` is provided (Patient Chat mode), also includes a factual comparison
    against the patient's recorded EWS and vital observations without recalculating EWS.
    """
    if not rag_sources:
        return ""

    lines: List[str] = ["\n\n**📚 Approved Hospital Knowledge & Protocol References (ChromaDB):**"]
    for idx, src in enumerate(rag_sources[:3], start=1):
        title = src.get("document_title") or src.get("source_file") or "Clinical Guideline"
        page_str = f", Page {src['page_number']}" if src.get("page_number") else ""
        cat_str = src.get("category", "guideline").replace("_", " ").title()
        excerpt = src.get("excerpt") or ""
        lines.append(f"• **[{idx}] {title}** (*{cat_str}{page_str}*): {excerpt}")

    if isinstance(patient_context, dict) and patient_context.get("patient"):
        p = patient_context.get("patient") or {}
        v = patient_context.get("latest_vitals") or {}
        e = patient_context.get("ews") or {}
        r = patient_context.get("recommendation") or {}
        p_name = p.get("name", "Selected Patient")
        ews_score = e.get("score") if e.get("score") is not None else v.get("ews_score", "N/A")
        ews_risk = e.get("risk_level", "N/A")
        spo2_str = f"{v.get('spo2')}%" if v.get("spo2") is not None else "Not recorded"
        hr_str = f"{v.get('heart_rate')} bpm" if v.get("heart_rate") is not None else "Not recorded"
        rec_text = r.get("recommendation_text") or "Under evaluation"
        lines.append(
            f"\n**🔍 Patient vs. Protocol Comparison ({p_name}):**\n"
            f"• **Recorded Observations:** Persisted EWS `{ews_score}` ({ews_risk}), SpO₂ `{spo2_str}`, HR `{hr_str}`.\n"
            f"• **Authoritative Decision Engine Status:** **{rec_text}** ({r.get('reason') or 'Based on persisted vital criteria'})."
        )

    return "\n".join(lines)


def query_rag_chatbot(
    user_id: int = 1,
    message: str = "",
    active_patient_id: Optional[int] = None,
    user_role: str = "doctor",
    mode: str = "patient",
    use_agentic_tools: bool = False,
    custom_vitals: Optional[Dict[str, Any]] = None,
    custom_patient: Optional[Dict[str, Any]] = None,
    custom_notes: Optional[str] = None,
    retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Process a chatbot message through the unified Jeevan Setu Agentic Hybrid Multimodal RAG engine.

    - When `use_agentic_tools=True`, executes the multi-round Agentic Tool Calling loop
      (`run_agentic_rag_workflow`).
    - In standard hybrid conversational mode (used by Doctor and Nurse Patient Summary AI pages),
      combines `process_conversational_message` with ChromaDB knowledge retrieval, MySQL fact
      source tracking, multimodal patient image context (in Patient Chat only), and strict
      General Chat isolation.
    """
    mode_norm = str(mode or "patient").strip().lower()
    if mode_norm not in ("patient", "general"):
        mode_norm = "patient" if active_patient_id else "general"

    # Enforce strict General Chat isolation upfront
    if mode_norm == "general":
        active_patient_id = None

    if use_agentic_tools:
        agentic_res = run_agentic_rag_workflow(
            question=message,
            user_id=user_id,
            user_role=user_role,
            chat_mode=mode_norm,
            patient_id=active_patient_id,
            retriever_fn=retriever_fn,
            **kwargs,
        )
        if isinstance(agentic_res, dict):
            if "text" not in agentic_res and "answer" in agentic_res:
                agentic_res["text"] = agentic_res["answer"]
            if "mode" not in agentic_res:
                agentic_res["mode"] = mode_norm
        return agentic_res

    # =========================================================================
    # A. GENERAL CHAT MODE — ChromaDB Optional Retrieval + Gemma 4 31B Knowledge
    # =========================================================================
    if mode_norm == "general":
        clean_msg = (message or "").strip()
        if not clean_msg:
            return {
                "success": False,
                "mode": "general",
                "chat_mode": "general",
                "patient_id": None,
                "error": "Empty message.",
                "text": "Please enter a medical or clinical question.",
                "response": "Please enter a medical or clinical question.",
                "intent": "empty_query",
                "rag_sources": [],
                "mysql_sources": [],
                "tools_invoked": [],
            }

        # 1. Redirection Guardrail: user asks about a patient by name or asks for patient telemetry in General Mode
        cand_name, remaining_q, is_explicit_mention = extract_explicit_patient_mention(clean_msg)
        has_generic_patient_ref = bool(
            re.search(r'\b(the patient|his|her|this patient|my patient)\b', clean_msg, re.IGNORECASE) and
            re.search(r'\b(vitals?|ews|diagnosis|heart rate|blood pressure|spo2|temperature|respiratory rate|bed|ward|transfer|recommendation|image|images|scan|scans|xray|x-ray|report|reports|lab|notes?)\b', clean_msg, re.IGNORECASE)
        )
        if (is_explicit_mention and cand_name) or has_generic_patient_ref:
            patient_target = f" for **{cand_name}**" if (is_explicit_mention and cand_name) else ""
            redirection_text = (
                f"You are currently in **General Chat mode** with no patient selected. "
                f"Patient-specific records, vitals, and transfer decisions{patient_target} are not accessible in General Chat. "
                f"Please switch to **Patient Chat mode** and select the patient from your authorized list."
            )
            return {
                "success": True,
                "mode": "general",
                "chat_mode": "general",
                "patient_id": None,
                "patient_context": None,
                "text": redirection_text,
                "response": redirection_text,
                "rag_sources": [],
                "mysql_sources": [],
                "tools_invoked": [],
                "intent": "general_mode_patient_redirection",
            }

        # 2. Greeting / General Help in General Mode
        if any(w in clean_msg.lower().split() for w in ['hi', 'hello', 'hey', 'greetings']) and len(clean_msg.split()) <= 4:
            greeting_text = (
                "Hello! I am **Dr. Setu** in **General Healthcare Chat mode**.\n\n"
                "I can assist you with general medical concepts, physiological norms, clinical score definitions (like EWS/NEWS2), and ICU/HDU terminology.\n\n"
                "• *Example:* 'What is hypertension?'\n"
                "• *Example:* 'What is the normal adult respiratory rate?'\n"
                "• *Example:* 'Explain Early Warning Score (EWS)'\n"
                "• *Example:* 'What is the difference between ICU and HDU?'\n"
                "• *Example:* 'What will be the best way to reduce back pain?'\n\n"
                "*Note: To view live bedside records or telemetry for an admitted patient, please switch to Patient Chat mode.*"
            )
            return {
                "success": True,
                "mode": "general",
                "chat_mode": "general",
                "patient_id": None,
                "patient_context": None,
                "text": greeting_text,
                "response": greeting_text,
                "rag_sources": [],
                "mysql_sources": [],
                "tools_invoked": [],
                "intent": "general_greeting",
            }

        # 3. Retrieve relevant ChromaDB knowledge chunks (OPTIONAL)
        # ChromaDB miss or unavailability must NEVER prevent Gemma from answering!
        chunks: List[Dict[str, Any]] = []
        rag_sources: List[Dict[str, Any]] = []
        tools_invoked: List[Dict[str, Any]] = []
        knowledge_context_str: Optional[str] = None

        try:
            chunks = _retrieve_chroma_chunks(clean_msg, top_k=3, retriever_fn=retriever_fn)
            rag_sources = _format_rag_sources(chunks)
            if rag_sources:
                tool_name = _select_chroma_tool_name(clean_msg, user_role=user_role)
                tools_invoked.append({
                    "tool_name": tool_name,
                    "source_type": "chroma_knowledge",
                    "status": "success",
                    "success": True,
                })
                # Build concise knowledge context string for prompt
                knowledge_context_str = _format_knowledge_synthesis_section(rag_sources, patient_context=None)
        except Exception as exc:
            logger.warning("Optional ChromaDB retrieval in General Chat encountered exception: %s", exc)
            chunks = []
            rag_sources = []

        # 4. Invoke Gemma 4 31B (OpenRouter) with broad general knowledge
        final_text: str = ""
        success_status = True
        intent_type = "general_ai_response"

        if is_ai_configured():
            ok, ai_resp, meta = query_openrouter_gemini(
                user_message=clean_msg,
                patient_context=None,
                user_role=user_role,
                mode="general",
                knowledge_context=knowledge_context_str,
            )
            if ok and ai_resp:
                final_text = ai_resp
                # Include citations/sources ONLY when actual retrieved sources are available
                if rag_sources and "Approved Hospital Knowledge" not in final_text and "Source Document:" not in final_text:
                    kb_sec = _format_knowledge_synthesis_section(rag_sources, patient_context=None)
                    if kb_sec:
                        final_text += kb_sec
            else:
                # OpenRouter call did not succeed (e.g. upstream rate limit 429 or temporary outage)
                # First check if this is a verified educational clinical concept available in the medical knowledge base
                med_resp = reason_general_medical_query(clean_msg, context=None)
                if med_resp and "This is a recognized medical/clinical term" not in med_resp and "Clinical Concept:" not in med_resp:
                    final_text = med_resp
                    intent_type = "general_medical_concept"
                    success_status = True
                else:
                    err = (meta or {}).get("error")
                    code = (meta or {}).get("code")
                    if code == 429 or err == "rate_limited":
                        final_text = "The AI service is temporarily unavailable due to upstream rate limits. Please try again shortly."
                    elif err in ("auth_error", "network_error"):
                        final_text = ai_resp or "The AI service is temporarily unavailable. Please try again later."
                    else:
                        final_text = "The AI service is temporarily unavailable. Please try again later."
                    success_status = False
        else:
            # Fallback when OpenRouter key is not configured: check static clinical concepts dictionary
            med_resp = reason_general_medical_query(clean_msg, context=None)
            if med_resp and "This is a recognized medical/clinical term" not in med_resp:
                final_text = med_resp
                intent_type = "general_medical_concept"
            else:
                final_text = "The OpenRouter AI service is not configured. Please set OPENROUTER_API_KEY in the backend environment."
                success_status = False

        response = {
            "success": success_status,
            "mode": "general",
            "chat_mode": "general",
            "patient_id": None,
            "patient_context": None,
            "context": None,
            "text": final_text,
            "response": final_text,
            "rag_sources": rag_sources,
            "mysql_sources": [],
            "tools_invoked": tools_invoked,
            "intent": intent_type,
            "rag_context_attached": bool(rag_sources),
        }

        if ChatbotConversation is not None and clean_msg and success_status:
            try:
                ChatbotConversation.save(
                    user_id=user_id,
                    user_message=clean_msg,
                    bot_response=final_text,
                    patient_id=None,
                    intent=intent_type,
                    confidence=0.95,
                    chat_mode="general",
                    tools_invoked=tools_invoked,
                    rag_sources=rag_sources,
                )
            except Exception:
                pass

        return response

    # =========================================================================
    # B. PATIENT CHAT MODE — Authorized MySQL + ChromaDB Protocols + Multimodal
    # =========================================================================
    # Execute core clinical conversational engine
    response = process_conversational_message(
        user_id=user_id,
        message=message,
        active_patient_id=active_patient_id,
        custom_vitals=custom_vitals,
        custom_patient=custom_patient,
        custom_notes=custom_notes,
        user_role=user_role,
        mode=mode_norm,
    )

    if not isinstance(response, dict):
        return {
            "success": False,
            "mode": mode_norm,
            "chat_mode": mode_norm,
            "text": "Unable to process chatbot request.",
            "response": "Unable to process chatbot request.",
            "rag_sources": [],
            "mysql_sources": [],
            "tools_invoked": [],
        }

    response["chat_mode"] = response.get("mode", mode_norm)
    intent_str = str(response.get("intent") or "")
    clean_msg = (message or "").strip()

    effective_pid = response.get("patient_id") or active_patient_id
    patient_ctx = response.get("patient_context") or response.get("context")

    mysql_sources, mysql_tools = _build_mysql_sources_from_context(
        patient_ctx, query=clean_msg, intent=intent_str
    )

    rag_sources = []
    chroma_tools: List[Dict[str, Any]] = []

    # Retrieve ChromaDB protocols/SOPs/guidelines when relevant to the question
    should_query_chroma = bool(
        clean_msg
        and (
            _PROTOCOL_KEYWORDS_RE.search(clean_msg)
            or callable(retriever_fn)
            or intent_str in ("general_medical_concept", "ai_general_query", "transfer_decision", "ews_query")
        )
    )
    if should_query_chroma:
        chunks = _retrieve_chroma_chunks(clean_msg, top_k=3, retriever_fn=retriever_fn)
        rag_sources = _format_rag_sources(chunks)
        if rag_sources:
            tool_name = _select_chroma_tool_name(clean_msg, user_role=user_role)
            chroma_tools.append({
                "tool_name": tool_name,
                "source_type": "chroma_knowledge",
                "status": "success",
                "success": True,
            })
            if _PROTOCOL_KEYWORDS_RE.search(clean_msg):
                kb_section = _format_knowledge_synthesis_section(rag_sources, patient_context=patient_ctx)
                if kb_section and "Approved Hospital Knowledge" not in str(response.get("text", "")):
                    response["text"] = str(response.get("text") or "") + kb_section
                    response["response"] = response["text"]

    # Check if clinician asked about patient-specific medical images / OCR
    patient_images_list: List[Dict[str, Any]] = []
    if (
        effective_pid
        and clean_msg
        and _IMAGE_QUERY_RE.search(clean_msg)
        and callable(get_authorized_patient_images)
    ):
        try:
            patient_images_list = get_authorized_patient_images(
                patient_id=int(effective_pid),
                user_id=user_id,
                user_role=user_role,
                chat_mode="patient",
                limit=5,
            )
            if patient_images_list:
                img_lines = ["\n\n**🖼️ Authorized Patient Clinical Images (OCR & Non-Diagnostic Summary):**"]
                for img in patient_images_list[:3]:
                    title = img.get("title") or img.get("image_type") or "Clinical Image"
                    ocr_snip = (img.get("ocr_text") or "No legible text detected via OCR")[:200]
                    vis_snip = (img.get("vision_description") or "").strip()[:200]
                    vis_note = f"Visual Note: *{vis_snip}*" if vis_snip else "Visual Analysis: *Image analysis was not completed because the vision processor was unavailable.*"
                    img_lines.append(
                        f"• **{title}** (`{img.get('image_type', 'other')}`): OCR: *{ocr_snip}* | {vis_note}"
                    )
                img_lines.append(
                    "*Note: OCR and visual descriptions are non-diagnostic assistive features only and require clinician verification. 'No OCR text detected' must not be interpreted as 'image analysed'.*"
                )
                response["text"] = str(response.get("text") or "") + "\n".join(img_lines)
                response["response"] = response["text"]
        except Exception:
            patient_images_list = []

    all_tools = mysql_tools + chroma_tools
    response["mysql_sources"] = mysql_sources
    response["rag_sources"] = rag_sources
    response["tools_invoked"] = all_tools
    response["patient_images"] = patient_images_list
    response["rag_context_attached"] = bool(rag_sources or mysql_sources)

    return response
