"""
modules/openrouter_service.py — Centralized OpenRouter AI Integration for Jeevan Setu.

Model: google/gemini-2.0-flash-exp:free (via OPENROUTER_MODEL)
API Provider: OpenRouter (https://openrouter.ai/api/v1/chat/completions)

Core Principles:
1. The MySQL Database & Jeevan Setu Decision Engine are the SOLE SOURCE OF TRUTH.
2. The AI is strictly an explanation and synthesis layer over verified backend data.
3. The AI never guesses, calculates EWS independently, or approves transfers.
4. Security: API Key is loaded only from environment variables and never logged or exposed.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("jeevan_setu.openrouter")

# Safe environment loading without hardcoded secrets
def load_environment():
    """Load environment variables from .env if not already set."""
    search_paths = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env"
    ]
    for p in search_paths:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
                break
            except Exception:
                pass

load_environment()

# Centralized OpenRouter Configuration
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"

def get_openrouter_api_key() -> Optional[str]:
    """Retrieve API key from backend environment only."""
    return os.environ.get("OPENROUTER_API_KEY", "").strip() or None

def get_openrouter_model() -> str:
    """Retrieve configured model name."""
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

def is_ai_configured() -> bool:
    """Check if OpenRouter is configured with a valid key."""
    key = get_openrouter_api_key()
    return bool(key and key != "your_openrouter_api_key_here")


# Grounded System Prompt (Strict Anti-Hallucination & Clinical Rule Enforcement for Patient Mode)
SYSTEM_PROMPT = """You are the Jeevan Setu Clinical Decision Support Assistant (Dr. Setu), a highly knowledgeable medical AI assisting clinicians with authorized patient records.

CRITICAL CLINICAL & SYSTEM RULES:
1. Accuracy & Grounding:
   - For patient-specific data, the database context is the authoritative source of truth. Never invent vitals, EWS, history, or transfer decisions.
   - For general medical, physiological, and clinical knowledge (e.g., "What causes tachycardia?", "Explain sepsis pathophysiology", "Difference between ICU and HDU", "Normal vital ranges"), provide a thorough, accurate, structured, and clinically precise answer.

2. Tone & Directness:
   - Provide direct, concise, professional answers immediately.
   - DO NOT include internal reasoning scratchpads, "Here's a thinking process:", chain-of-thought traces, or conversational fluff.
   - Use bullet points, bold key terms, and clear sections where appropriate for clinical readability.

3. Role & Transfer Guardrails:
   - You CANNOT approve transfers, modify orders, or prescribe medications.
   - If a Nurse asks to approve a transfer, explain that Nurses do not have transfer approval authority.
   - If a Doctor asks to approve a transfer, direct them to the official Doctor Portal transfer authorization workflow.

4. EWS (Early Warning Score):
   - Always reference the persisted EWS from the backend; never calculate a competing score.
"""

# General Mode System Prompt (Educational Healthcare Information - Zero Patient Context)
SYSTEM_PROMPT_GENERAL = """You are the Jeevan Setu Healthcare Information Assistant (Dr. Setu) operating in GENERAL / MULTIPURPOSE CHAT MODE.

In this mode, NO PATIENT IS SELECTED. You act as an educational, multipurpose healthcare and medical information assistant for clinicians, nurses, and healthcare staff.

CRITICAL GUIDELINES FOR GENERAL CHAT MODE:
1. Educational & Healthcare Concepts:
   - Answer general healthcare, medical, physiological, pharmacology, and clinical scoring questions (e.g., "What is hypertension?", "What is diabetes?", "What is tachycardia?", "What is EWS?", "What is the difference between ICU and HDU?", "Normal adult vital signs").
   - Provide clear, direct, structured, objective, and clinically accurate educational explanations.

2. Strict Anti-Hallucination & Zero Patient Context:
   - You have NO patient selected and NO patient records attached.
   - Do NOT invent or guess any real patient's vitals, diagnosis, EWS score, bed, or transfer status.
   - If a user asks about a specific person or patient by name or UHID (e.g., "What is Amit Verma's EWS?", "What are Amit's vitals?"), explicitly instruct them:
     "You are currently in General Chat mode with no patient selected. To view verified clinical records, telemetry, or transfer recommendations for a patient, please switch to Patient Chat mode and select the patient from your authorized list."

3. Medical Safety & Boundaries:
   - Do NOT diagnose an individual patient, prescribe medications or specific dosages, or approve transfers.
   - Clarify when appropriate that educational medical information does not replace individual clinical assessment by a qualified doctor.

4. Direct Tone:
   - Deliver direct, professional answers without internal thinking traces or chain-of-thought scratchpads.
   - Use clean markdown formatting, bold keywords, and bulleted lists.
"""

def clean_ai_response(text: str) -> str:
    """Strip any internal reasoning traces, <think> tags, or model meta-preambles."""
    if not text:
        return ""
    import re
    # Strip <think>...</think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Strip leading thinking preambles like "Here's a thinking process:"
    if "Here's a thinking process:" in text:
        parts = text.split("Here's a thinking process:", 1)
        after = parts[1]
        lines = after.splitlines()
        clean_lines = []
        skip = True
        for line in lines:
            if not skip:
                clean_lines.append(line)
            elif line.startswith("#") or line.startswith("**") or line.startswith("•") or (line.strip() and not any(line.strip().startswith(x) for x in ["1", "2", "3", "4", "5", "Looking at", "The user is", "Rule ", "I need to", "I should", "I will"])):
                skip = False
                clean_lines.append(line)
        if clean_lines:
            text = "\n".join(clean_lines).strip()
    return text.strip()


def build_controlled_patient_context(context: Dict[str, Any], user_role: str = "doctor") -> str:
    """
    Constructs a minimal, controlled clinical context string strictly from verified database records.
    Only includes fields authorized for the user's role.
    """
    if not context or not isinstance(context, dict):
        return "No patient record selected or available."

    patient = context.get('patient') or {}
    vitals = context.get('latest_vitals') or {}
    ews = context.get('ews') or {}
    rec = context.get('recommendation') or {}
    transfer = context.get('transfer_decision') or {}
    alerts = context.get('alerts') or []
    history = context.get('vitals_history') or []
    decision_history = context.get('decision_history') or []
    doc_cond = context.get('documented_conditions') or {}

    lines = []
    lines.append("=== AUTHORIZED JEEVAN SETU PATIENT RECORD (SOURCE OF TRUTH) ===")
    
    # Patient Demographics
    lines.append(f"Patient ID: {patient.get('patient_id', 'N/A')}")
    lines.append(f"UHID: {patient.get('patient_code', 'N/A')}")
    lines.append(f"Name: {patient.get('name', 'Unknown')}")
    lines.append(f"Age/Gender: {patient.get('age', 'N/A')} yrs, {patient.get('gender', 'N/A')}")
    lines.append(f"Location: {patient.get('ward_type', 'N/A')} (Bed: {patient.get('bed_number', 'N/A')})")
    
    # Recorded Diagnosis (Strict)
    diagnosis = patient.get('diagnosis') or doc_cond.get('diagnosis')
    if diagnosis:
        lines.append(f"Primary Recorded Diagnosis: {diagnosis}")
    else:
        lines.append("Primary Recorded Diagnosis: [This information is not available in the Jeevan Setu records.]")

    med_hist = doc_cond.get('medical_history') or []
    if med_hist:
        lines.append(f"Recorded Medical History: {', '.join(med_hist)}")

    # Latest Persisted Vitals (Clean formatting without None% or /None)
    lines.append("\n--- LATEST PERSISTED VITALS ---")
    if vitals:
        hr = vitals.get('heart_rate')
        sbp = vitals.get('blood_pressure_sys')
        dbp = vitals.get('blood_pressure_dia')
        rr = vitals.get('respiratory_rate')
        temp = vitals.get('temperature')
        spo2 = vitals.get('spo2')
        rec_time = vitals.get('recorded_at') or "Latest recorded"

        lines.append(f"Heart Rate: {hr} bpm" if hr is not None and str(hr).lower() not in ('none', 'null') else "Heart Rate: Not recorded")
        
        # Format Blood Pressure cleanly
        s_val = None if sbp is None or str(sbp).lower() in ('none', 'null', '') else str(sbp)
        d_val = None if dbp is None or str(dbp).lower() in ('none', 'null', '') else str(dbp)
        if s_val and d_val:
            bp_str = f"{s_val}/{d_val} mmHg"
        elif s_val:
            bp_str = f"{s_val} mmHg (Sys)"
        elif d_val:
            bp_str = f"{d_val} mmHg (Dia)"
        else:
            bp_str = "Not recorded"
        lines.append(f"Blood Pressure: {bp_str}")

        lines.append(f"Respiratory Rate: {rr} breaths/min" if rr is not None and str(rr).lower() not in ('none', 'null') else "Respiratory Rate: Not recorded")
        lines.append(f"Temperature: {temp} °C" if temp is not None and str(temp).lower() not in ('none', 'null') else "Temperature: Not recorded")
        lines.append(f"SpO2: {spo2}%" if spo2 is not None and str(spo2).lower() not in ('none', 'null') else "SpO2: Not recorded")
        lines.append(f"Vitals Timestamp: {rec_time}")
    else:
        lines.append("No vitals recorded in database.")

    # Latest Persisted EWS
    lines.append("\n--- PERSISTED EWS (EARLY WARNING SCORE) ---")
    if ews:
        total = ews.get('score') if ews.get('score') is not None else ews.get('total_score')
        risk = ews.get('risk_level', 'N/A')
        comp = ews.get('components') or {}
        lines.append(f"Persisted EWS Total: {total}")
        lines.append(f"Clinical Risk Level: {risk}")
        if comp:
            lines.append(f"Component Breakdown: HR={comp.get('hr_score', 0)}, BP={comp.get('bp_score', 0)}, RR={comp.get('rr_score', 0)}, Temp={comp.get('temp_score', 0)}, SpO2={comp.get('spo2_score', 0)}")
    elif vitals and vitals.get('ews_score') is not None and str(vitals.get('ews_score')).lower() not in ('none', 'null'):
        lines.append(f"Persisted EWS Total: {vitals.get('ews_score')}")
    else:
        lines.append("Persisted EWS: Not recorded.")

    # Decision Engine Recommendation & Transfer Status
    lines.append("\n--- DECISION ENGINE & TRANSFER STATUS ---")
    rec_text = rec.get('recommendation_text') or transfer.get('recommendation_text') or rec.get('action') or "Keep in ICU"
    rec_reason = rec.get('reason') or transfer.get('reason') or "Under active monitoring"
    lines.append(f"Authoritative Recommendation: {rec_text}")
    lines.append(f"Clinical Rationale: {rec_reason}")

    if transfer:
        lines.append(f"Transfer Status: {transfer.get('status', 'active')}")
        if transfer.get('from_ward'):
            lines.append(f"From Ward: {transfer.get('from_ward')} -> Target Ward: {transfer.get('to_ward') or 'N/A'}")

    # Active Alerts
    if alerts:
        lines.append("\n--- ACTIVE CLINICAL ALERTS ---")
        for a in alerts[:3]:
            lines.append(f"- [{a.get('type', 'ALERT')}] {a.get('title', 'Alert')}: {a.get('message', '')}")

    # Recent Vitals History (max 4 entries for factual comparison)
    if history and len(history) > 1:
        lines.append("\n--- RECENT VITALS HISTORY (PAST READINGS) ---")
        for idx, h in enumerate(history[:4]):
            h_spo2 = f"{h.get('spo2')}%" if h.get('spo2') is not None and str(h.get('spo2')).lower() not in ('none', 'null') else "Not recorded"
            h_sys = h.get('blood_pressure_sys')
            h_dia = h.get('blood_pressure_dia')
            if h_sys is not None and h_dia is not None and str(h_sys).lower() not in ('none', 'null') and str(h_dia).lower() not in ('none', 'null'):
                h_bp = f"{h_sys}/{h_dia} mmHg"
            elif h_sys is not None and str(h_sys).lower() not in ('none', 'null'):
                h_bp = f"{h_sys} mmHg"
            else:
                h_bp = "Not recorded"
            lines.append(f"Reading #{idx+1} ({h.get('recorded_at', 'Past')}): HR={h.get('heart_rate', 'N/A')} bpm, BP={h_bp}, RR={h.get('respiratory_rate', 'N/A')}, SpO2={h_spo2}, EWS={h.get('ews_score', 'N/A')}")

    # Decision History
    if decision_history:
        lines.append("\n--- CLINICIAN DECISION HISTORY ---")
        for d in decision_history[:3]:
            by = f" by {d.get('decided_by_name')}" if d.get('decided_by_name') else ""
            lines.append(f"- {d.get('decided_at', 'Recent')}: {d.get('recommendation', 'Review')} (Status: {d.get('status', 'logged')}){by}")

    # Role constraint notice
    lines.append(f"\nUser Role: {user_role.upper()}")
    if user_role.lower() == "nurse":
        lines.append("NOTE: Nurse is authorized to view records and record vitals, but CANNOT approve transfers.")
    elif user_role.lower() == "attendant":
        lines.append("NOTE: Attendant has read-only access for patient status.")

    lines.append("=== END OF AUTHORIZED CONTEXT ===")
    return "\n".join(lines)


def query_openrouter_gemini(
    user_message: str,
    patient_context: Optional[Dict[str, Any]] = None,
    user_role: str = "doctor",
    timeout: int = 15,
    mode: str = "patient"
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Calls OpenRouter API to explain verified clinical data or answer general healthcare inquiries.
    
    Parameters:
        user_message: Clinical or medical inquiry text
        patient_context: Authorized database context dictionary (or None for General Mode)
        user_role: Current user's authenticated role ('doctor', 'nurse', 'attendant', 'admin')
        timeout: Network timeout in seconds
        mode: Chat mode ('patient' or 'general')
        
    Returns:
        (success: bool, response_text: str, metadata: dict)
    """
    api_key = get_openrouter_api_key()
    if not api_key:
        return False, "The OpenRouter API key is not configured. Please set OPENROUTER_API_KEY in the backend environment.", {"error": "missing_api_key"}

    primary_model = get_openrouter_model()
    # List of candidate models to ensure 100% availability on OpenRouter free tier
    candidate_models = [primary_model]
    for alt in [
        'google/gemma-4-31b-it:free',
        'inclusionai/ling-3.0-flash-sante:free',
        'nvidia/nemotron-3.5-lightning:free',
        'qwen/qwen3.8-27b:free',
        'google/gemini-2.0-flash-exp:free'
    ]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    is_general_mode = (mode or "").lower() == "general" or patient_context is None

    if is_general_mode:
        system_instructions = SYSTEM_PROMPT_GENERAL
        messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_message}
        ]
    else:
        system_instructions = SYSTEM_PROMPT
        context_str = build_controlled_patient_context(patient_context, user_role=user_role)
        messages = [
            {"role": "system", "content": system_instructions},
            {"role": "system", "content": f"CURRENT AUTHORIZED CLINICAL CONTEXT:\n{context_str}"},
            {"role": "user", "content": user_message}
        ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://jeevansetu.in",
        "X-Title": "Jeevan Setu AI Clinical Assistant"
    }

    import urllib.request
    import urllib.error

    last_error = None
    timeout = 8
    for model in candidate_models:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 800
        }

        try:
            req = urllib.request.Request(
                OPENROUTER_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = resp.status
                resp_body = resp.read().decode("utf-8")
                data = json.loads(resp_body)

                if status_code == 200 and "choices" in data and len(data["choices"]) > 0:
                    raw_text = data["choices"][0].get("message", {}).get("content", "").strip()
                    ai_text = clean_ai_response(raw_text)
                    if ai_text:
                        return True, ai_text, {
                            "model": model,
                            "provider": "openrouter",
                            "status": "success",
                            "mode": "general" if is_general_mode else "patient"
                        }
        except urllib.error.HTTPError as e:
            status = e.code
            if status in (404, 429):
                # Try next candidate model in list
                last_error = (status, "rate_limited" if status == 429 else "model_not_found")
                continue
            elif status in (401, 403):
                return False, "AI authentication failed. Please check the backend OpenRouter API key.", {"error": "auth_error", "code": status}
            else:
                last_error = (status, f"http_error_{status}")
        except urllib.error.URLError:
            return False, "Unable to reach the AI service endpoint due to a network error.", {"error": "network_error"}
        except Exception:
            break

    if last_error and last_error[0] == 429:
        return False, "The AI service is temporarily rate-limited. Please try again in a few moments.", {"error": "rate_limited", "code": 429}
    return False, "The AI service is temporarily unavailable. Please try again later.", {"error": "service_unavailable"}
