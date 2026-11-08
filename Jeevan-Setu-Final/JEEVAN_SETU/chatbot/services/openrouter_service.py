"""
chatbot/services/openrouter_service.py — Centralized OpenRouter AI Integration for Jeevan Setu.

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

# Safe environment loading prioritizing canonical project root .env (Jeevan-Setu-Final/.env)
def load_environment(override: bool = False):
    """Load environment variables from the canonical root .env file."""
    root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
    search_paths = [
        root_env,
        backend_env,
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
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
                        if k and (override or k not in os.environ):
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


from chatbot.prompts.prompts import (
    PATIENT_CHAT_PROMPT,
    GENERAL_CHAT_PROMPT,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_GENERAL,
)

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

    # Latest Persisted Vitals (Clean formatting with explicit units & timestamps)
    lines.append("\n--- LATEST PERSISTED VITALS ---")
    if vitals:
        vital_id = vitals.get('vital_id') or vitals.get('id')
        hr = vitals.get('heart_rate')
        sbp = vitals.get('blood_pressure_sys')
        dbp = vitals.get('blood_pressure_dia')
        rr = vitals.get('respiratory_rate')
        temp = vitals.get('temperature')
        spo2 = vitals.get('spo2')
        rec_time = vitals.get('recorded_at') or "Latest recorded"

        if vital_id:
            lines.append(f"Observation ID: #{vital_id}")
        lines.append(f"Observation Timestamp: {rec_time}")
        lines.append(f"Heart Rate: {hr} bpm" if hr is not None and str(hr).lower() not in ('none', 'null') else "Heart Rate: Not recorded")
        
        # Format Blood Pressure cleanly — never ambiguous
        s_val = None if sbp is None or str(sbp).lower() in ('none', 'null', '') else str(sbp)
        d_val = None if dbp is None or str(dbp).lower() in ('none', 'null', '') else str(dbp)
        if s_val and d_val:
            bp_str = f"{s_val}/{d_val} mmHg"
        elif s_val:
            bp_str = f"Systolic BP: {s_val} mmHg (Diastolic BP: Not recorded)"
        elif d_val:
            bp_str = f"Diastolic BP: {d_val} mmHg (Systolic BP: Not recorded)"
        else:
            bp_str = "Not recorded"
        lines.append(f"Blood Pressure: {bp_str}")

        lines.append(f"Respiratory Rate: {rr} breaths/min" if rr is not None and str(rr).lower() not in ('none', 'null') else "Respiratory Rate: Not recorded")
        lines.append(f"Temperature: {temp} °C" if temp is not None and str(temp).lower() not in ('none', 'null') else "Temperature: Not recorded")
        lines.append(f"SpO2: {spo2}%" if spo2 is not None and str(spo2).lower() not in ('none', 'null') else "SpO2: Not recorded")
    else:
        lines.append("No vitals recorded in database.")

    # Latest Persisted EWS (Authoritative source of truth)
    lines.append("\n--- PERSISTED EWS (EARLY WARNING SCORE) ---")
    curr_ews_score = None
    if ews:
        ews_id = ews.get('ews_id') or ews.get('id')
        curr_ews_score = ews.get('score') if ews.get('score') is not None else ews.get('total_score')
        risk = ews.get('risk_level', 'N/A')
        calc_at = ews.get('calculated_at') or (vitals.get('recorded_at') if vitals else "Latest calculation")
        obs_id = ews.get('vital_id') or (vitals.get('vital_id') if vitals else "N/A")
        comp = ews.get('components') or {}
        if ews_id:
            lines.append(f"EWS Record ID: #{ews_id}")
        lines.append(f"Associated Vital Observation ID: #{obs_id}")
        lines.append(f"Calculation Timestamp: {calc_at}")
        lines.append(f"Authoritative EWS Total: {curr_ews_score}")
        lines.append(f"Clinical Risk Level: {risk}")
        lines.append("Note: Authoritative backend calculation. Do NOT recalculate or override with AI.")
        if comp:
            lines.append(f"Component Breakdown: HR={comp.get('hr_score', 0)}, BP={comp.get('bp_score', 0)}, RR={comp.get('rr_score', 0)}, Temp={comp.get('temp_score', 0)}, SpO2={comp.get('spo2_score', 0)}")
    elif vitals and vitals.get('ews_score') is not None and str(vitals.get('ews_score')).lower() not in ('none', 'null'):
        curr_ews_score = vitals.get('ews_score')
        lines.append(f"Authoritative EWS Total: {curr_ews_score} (from latest vitals record)")
    else:
        lines.append("Persisted EWS: Not recorded.")

    # Authoritative Physiological Trend & Trajectory
    lines.append("\n--- AUTHORITATIVE PHYSIOLOGICAL TREND ---")
    trends_obj = context.get('trends') or {}
    has_suff = trends_obj.get('has_sufficient_data', False)
    readings_count = trends_obj.get('readings_count', len(history) if history else 0)
    if not has_suff or readings_count < 2:
        lines.append("Physiological Trend: Insufficient historical data to determine the physiological trend.")
        lines.append("Trend Rule: State exactly 'Insufficient historical data to determine the physiological trend.' Do NOT invent stability.")
    else:
        direction = str(trends_obj.get('overall_direction', 'STABLE')).upper()
        summary = trends_obj.get('summary_text', '')
        lines.append(f"Longitudinal Trajectory: {direction} (Based on {readings_count} serial observations)")
        if summary:
            lines.append(f"Serial Parameter Details: {summary}")
        # Clinical alert if vitals are severely abnormal
        if curr_ews_score is not None and (int(curr_ews_score) >= 5 or direction in ("WORSENING", "CRITICALLY ABNORMAL (PERSISTENT HIGH RISK)", "UNSTABLE")):
            lines.append("Clinical Warning: Patient observations indicate high physiological stress. Do NOT describe the patient's condition or trend as 'stable'.")

    # Decision Engine Recommendation & Transfer Status
    lines.append("\n--- DECISION ENGINE & TRANSFER STATUS ---")
    rec_text = rec.get('recommendation_text') or transfer.get('recommendation_text') or rec.get('action') or "Keep in ICU"
    rec_reason = rec.get('reason') or transfer.get('reason') or "Under active monitoring"
    lines.append(f"Authoritative Recommendation: {rec_text}")
    lines.append(f"Clinical Rationale: {rec_reason}")
    lines.append("Note: This transfer decision is authoritative and generated by the clinical engine. AI must NOT override or invent an alternative decision.")

    if transfer:
        lines.append(f"Transfer Status: {transfer.get('status', 'active')}")
        if transfer.get('from_ward'):
            lines.append(f"From Ward: {transfer.get('from_ward')} -> Target Ward: {transfer.get('to_ward') or 'N/A'}")

    # Active vs Historical Alerts (with timestamps and EWS reconciliation)
    if alerts:
        lines.append("\n--- CLINICAL ALERTS ---")
        vitals_rec_time = str(vitals.get('recorded_at') or '') if vitals else ''
        for a in alerts[:4]:
            a_type = a.get('type') or a.get('alert_type') or 'ALERT'
            a_title = a.get('title') or 'Alert'
            a_msg = a.get('message') or ''
            a_time = str(a.get('created_at') or 'Timestamp unrecorded')
            a_val = a.get('value')
            is_active = str(a.get('status', 'ACTIVE')).upper() == 'ACTIVE'
            
            # Determine if this alert is historical relative to current vitals
            is_historical = False
            if vitals_rec_time and a_time and a_time < vitals_rec_time:
                is_historical = True
            if curr_ews_score is not None and a_val is not None:
                try:
                    if float(a_val) != float(curr_ews_score):
                        is_historical = True
                except (ValueError, TypeError):
                    pass

            label = "HISTORICAL ALERT" if is_historical else ("ACTIVE ALERT" if is_active else "RESOLVED ALERT")
            lines.append(f"- [{label} at {a_time}] {a_title}: {a_msg}")
            if is_historical and curr_ews_score is not None:
                lines.append(f"  *Discrepancy Note: Alert above was generated at {a_time} when EWS was {a_val}. The current authoritative EWS at {vitals_rec_time or 'now'} is {curr_ews_score}. The alert represents a past reading.*")

    # Multimodal Clinical Images & Vision Analysis
    images = context.get('patient_images') or []
    if images:
        lines.append("\n--- MULTIMODAL CLINICAL IMAGES ---")
        for img in images[:3]:
            img_title = img.get('title') or img.get('image_type') or 'Clinical Image'
            ocr_text = (img.get('ocr_text') or '').strip()
            vis_desc = (img.get('vision_description') or '').strip()
            vis_status = img.get('vision_status') or ('completed' if vis_desc else 'failed')
            uploaded_at = img.get('created_at') or 'Recent'

            lines.append(f"- Clinical Image: {img_title} ({img.get('image_type', 'other')}) [Uploaded: {uploaded_at}]")
            if ocr_text:
                lines.append(f"  OCR Status: Legible text detected -> \"{ocr_text[:300]}\"")
            else:
                lines.append("  OCR Status: No readable text detected via OCR (typical for medical scans/radiographs without text annotations).")

            if vis_status == 'completed' and vis_desc:
                lines.append(f"  Vision Analysis: {vis_desc}")
                lines.append("  Vision Notice: [Clinician Verification Required] AI-assisted visual features only; not a definitive diagnosis.")
            else:
                lines.append("  Vision Analysis: Image analysis was not completed because the vision processor was unavailable.")

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
    mode: str = "patient",
    knowledge_context: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Calls OpenRouter API (Gemma 4 31B primary) to explain verified clinical data
    or answer general healthcare inquiries.

    Parameters:
        user_message: Clinical or medical inquiry text
        patient_context: Authorized database context dictionary (or None for General Mode)
        user_role: Current user's authenticated role ('doctor', 'nurse', 'attendant', 'admin')
        timeout: Network timeout in seconds
        mode: Chat mode ('patient' or 'general')
        knowledge_context: Optional supplementary ChromaDB knowledge text for General Mode

    Returns:
        (success: bool, response_text: str, metadata: dict)
    """
    api_key = get_openrouter_api_key()
    if not api_key:
        return False, "The OpenRouter API key is not configured. Please set OPENROUTER_API_KEY in the backend environment.", {"error": "missing_api_key"}

    primary_model = get_openrouter_model()
    # Candidate models for Gemma 4 31B / fast inference on OpenRouter
    candidate_models = [primary_model]
    for alt in [
        'google/gemma-4-31b-it:free',
        'google/gemma-4-26b-a4b-it:free',
        'xingchen-agi/xing4.0-29b-a4b:free',
        'nvidia/nemotron-3.5-lightning:free',
        'openrouter/free',
    ]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    is_general_mode = (mode or "").lower() == "general" or patient_context is None

    if is_general_mode:
        system_instructions = GENERAL_CHAT_PROMPT
        messages = [
            {"role": "system", "content": system_instructions}
        ]
        if knowledge_context and str(knowledge_context).strip():
            messages.append({
                "role": "system",
                "content": (
                    "APPROVED SUPPLEMENTARY HOSPITAL KNOWLEDGE "
                    "(Use if relevant; cite only verified sources):\n"
                    f"{str(knowledge_context).strip()}"
                ),
            })
        messages.append({"role": "user", "content": user_message})
    else:
        system_instructions = PATIENT_CHAT_PROMPT
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
            if status == 429:
                return False, "The AI service is temporarily rate-limited. Please try again in a few moments.", {"error": "rate_limited", "code": 429}
            elif status == 404:
                last_error = (status, "model_not_found")
                continue
            elif status in (401, 403):
                return False, "AI authentication failed. Please check the backend OpenRouter API key.", {"error": "auth_error", "code": status}
            else:
                last_error = (status, f"http_error_{status}")
                break
        except urllib.error.URLError:
            return False, "Unable to reach the AI service endpoint due to a network error.", {"error": "network_error"}
        except Exception:
            break

    if last_error and last_error[0] == 429:
        return False, "The AI service is temporarily rate-limited. Please try again in a few moments.", {"error": "rate_limited", "code": 429}
    return False, "The AI service is temporarily unavailable. Please try again later.", {"error": "service_unavailable"}


def call_openrouter_with_tools(
    messages: list,
    tools: Optional[list] = None,
    tool_choice: str = "auto",
    temperature: float = 0.2,
    max_tokens: int = 800,
    timeout: int = 10,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a chat completion request to OpenRouter (Gemma 4 31B primary) with
    optional function-calling `tools` definitions.

    Supports:
    1. Native OpenRouter tool calling (`tools` + `tool_choice`, returning
       `message.tool_calls`).
    2. Automatic fallback to structured JSON output on routes that return HTTP
       400/422 when `tools` is supplied.

    Returns a dictionary:
        {
            "success": bool,
            "model": str or None,
            "message": dict (containing "role", "content", and optional "tool_calls"),
            "raw_response": dict,
            "native_tools_used": bool,
            "error": str or None
        }
    """
    api_key = get_openrouter_api_key()
    if not api_key:
        return {
            "success": False,
            "model": None,
            "message": {},
            "raw_response": {},
            "native_tools_used": False,
            "error": "missing_api_key",
        }

    primary_model = model_override or get_openrouter_model()
    candidate_models = [primary_model]
    for alt in [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3.5-super-vl:free",
    ]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://jeevansetu.in",
        "X-Title": "Jeevan Setu AI Clinical Assistant",
    }

    import urllib.request
    import urllib.error

    last_error = "service_unavailable"

    for model in candidate_models:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        for attempt_native in ([True, False] if tools else [False]):
            req_payload = dict(payload)
            if not attempt_native and "tools" in req_payload:
                req_payload.pop("tools", None)
                req_payload.pop("tool_choice", None)

            try:
                req = urllib.request.Request(
                    OPENROUTER_ENDPOINT,
                    data=json.dumps(req_payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    status_code = resp.status
                    resp_body = resp.read().decode("utf-8")
                    data = json.loads(resp_body)

                    if status_code == 200 and "choices" in data and len(data["choices"]) > 0:
                        msg_obj = data["choices"][0].get("message") or {}
                        if "content" in msg_obj and isinstance(msg_obj["content"], str):
                            msg_obj["content"] = clean_ai_response(msg_obj["content"])
                        return {
                            "success": True,
                            "model": model,
                            "message": msg_obj,
                            "raw_response": data,
                            "native_tools_used": attempt_native,
                            "error": None,
                            "requested_model": primary_model,
                            "actual_model": model,
                            "is_fallback": bool(model != primary_model),
                            "fallback_reason": ("primary_rate_limited_or_error" if model != primary_model else None),
                            "provider": "openrouter",
                        }
            except urllib.error.HTTPError as e:
                status = e.code
                err_detail = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                    err_json = json.loads(err_body)
                    err_detail = str(err_json.get("error", {}).get("message") or "")
                except Exception:
                    pass

                logger.warning(
                    "OpenRouter API call returned HTTP %d for model '%s': %s",
                    status,
                    model,
                    err_detail[:180] if err_detail else "No error details returned",
                )

                if status in (400, 422) and attempt_native:
                    # Provider route did not accept native `tools` parameter; retry without `tools`
                    last_error = f"http_{status}_native_tools_unsupported"
                    continue
                if status == 429:
                    last_error = "rate_limited"
                    # If daily free tier quota is exhausted across the account, other free models will also fail
                    if ":free" in model or "free-models-per-day" in err_detail:
                        break
                    continue
                if status == 404:
                    if last_error != "rate_limited":
                        last_error = "model_not_found"
                    continue
                if status in (401, 403):
                    return {
                        "success": False,
                        "model": model,
                        "message": {},
                        "raw_response": {},
                        "native_tools_used": False,
                        "error": f"auth_error_{status}",
                    }
                if last_error != "rate_limited":
                    last_error = f"http_error_{status}"
                break
            except urllib.error.URLError:
                return {
                    "success": False,
                    "model": model,
                    "message": {},
                    "raw_response": {},
                    "native_tools_used": False,
                    "error": "network_error",
                }
            except Exception as exc:
                last_error = f"unexpected_error:{type(exc).__name__}"
                break

    return {
        "success": False,
        "model": None,
        "message": {},
        "raw_response": {},
        "native_tools_used": False,
        "error": last_error,
        "requested_model": primary_model,
        "actual_model": None,
        "is_fallback": False,
        "fallback_reason": last_error,
        "provider": "openrouter",
    }


__all__ = [
    "get_openrouter_api_key",
    "get_openrouter_model",
    "is_ai_configured",
    "clean_ai_response",
    "build_controlled_patient_context",
    "query_openrouter_gemini",
    "call_openrouter_with_tools",
    "PATIENT_CHAT_PROMPT",
    "GENERAL_CHAT_PROMPT",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_GENERAL",
]


