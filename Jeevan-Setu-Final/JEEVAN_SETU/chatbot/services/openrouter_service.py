"""
chatbot/services/openrouter_service.py — Centralized OpenRouter AI Integration &
Two-Key Failover Controller for Jeevan Setu.

Model: google/gemma-4-31b-it:free (via OPENROUTER_MODEL)
API Provider: OpenRouter (https://openrouter.ai/api/v1/chat/completions)

Core Principles:
1. The MySQL Database & Jeevan Setu Decision Engine are the SOLE SOURCE OF TRUTH.
2. The AI is strictly an explanation and synthesis layer over verified backend data.
3. The AI never guesses, calculates EWS independently, or approves transfers.
4. Security: Primary and Secondary API keys are loaded strictly from
   OPENROUTER_PRIMARY_API_KEY and OPENROUTER_SECONDARY_API_KEY and never logged or exposed.
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
DEFAULT_MODEL = "google/gemma-4-31b-it:free"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_FAILOVER_RETRIES = 1
_PLACEHOLDER_KEYS = {"", "your_openrouter_api_key_here"}


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_openrouter_enabled() -> bool:
    """Check whether OpenRouter external AI calls are enabled via OPENROUTER_ENABLED."""
    return _parse_bool_env("OPENROUTER_ENABLED", False)


def is_failover_enabled() -> bool:
    """Check whether controlled primary->secondary key failover is enabled."""
    return _parse_bool_env("OPENROUTER_FAILOVER_ENABLED", True)


def get_openrouter_timeout(override: Optional[int] = None) -> int:
    """Retrieve request timeout in seconds (clamped to 1..120)."""
    if override is not None:
        try:
            return max(1, min(120, int(override)))
        except (TypeError, ValueError):
            pass
    raw = os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "").strip()
    if raw:
        try:
            return max(1, min(120, int(raw)))
        except ValueError:
            pass
    return DEFAULT_TIMEOUT_SECONDS


def get_openrouter_max_retries() -> int:
    """Retrieve maximum secondary failover attempts per request (0 or 1; never infinite)."""
    raw = os.environ.get("OPENROUTER_MAX_RETRIES", "").strip()
    if raw:
        try:
            return max(0, min(1, int(raw)))
        except ValueError:
            pass
    return DEFAULT_MAX_FAILOVER_RETRIES


def get_primary_api_key() -> Optional[str]:
    """Retrieve primary OpenRouter API key strictly from OPENROUTER_PRIMARY_API_KEY."""
    primary = os.environ.get("OPENROUTER_PRIMARY_API_KEY", "").strip()
    if primary and primary not in _PLACEHOLDER_KEYS:
        return primary
    return None


def get_secondary_api_key() -> Optional[str]:
    """Retrieve secondary OpenRouter API key strictly from OPENROUTER_SECONDARY_API_KEY."""
    secondary = os.environ.get("OPENROUTER_SECONDARY_API_KEY", "").strip()
    if not secondary or secondary in _PLACEHOLDER_KEYS:
        return None
    primary = get_primary_api_key()
    if primary and secondary == primary:
        return None
    return secondary


def get_openrouter_api_key() -> Optional[str]:
    """Retrieve primary API key from backend environment only."""
    return get_primary_api_key()


def get_openrouter_model() -> str:
    """Retrieve configured model name."""
    raw = os.environ.get("OPENROUTER_MODEL")
    if raw is None:
        return DEFAULT_MODEL
    return raw.strip()


def validate_openrouter_config(model_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Centralized, sanitized validation of OpenRouter configuration.
    Reads only standardized variables and never exposes secret key values.
    """
    enabled = is_openrouter_enabled()
    failover_enabled = is_failover_enabled()
    model = (model_override if model_override is not None else get_openrouter_model()).strip()
    has_primary = bool(get_primary_api_key())
    has_secondary = bool(get_secondary_api_key())

    errors = []
    warnings = []

    if not model or any(ch.isspace() for ch in model) or "/" not in model:
        errors.append("invalid_model_config")

    if enabled and not has_primary:
        errors.append("missing_primary_api_key")

    if enabled and failover_enabled and not has_secondary:
        warnings.append("secondary_api_key_not_configured")

    return {
        "valid": len(errors) == 0 and enabled and has_primary,
        "enabled": enabled,
        "model": model,
        "model_valid": "invalid_model_config" not in errors,
        "has_primary_key": has_primary,
        "has_secondary_key": has_secondary,
        "failover_enabled": failover_enabled,
        "errors": errors,
        "warnings": warnings,
    }


def is_ai_configured() -> bool:
    """Check if OpenRouter is enabled, model is valid, and primary key is configured."""
    return bool(validate_openrouter_config()["valid"])


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


def classify_openrouter_error(
    status_code: Optional[int] = None,
    exc: Optional[BaseException] = None,
    err_detail: str = "",
    retry_after: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Classify an OpenRouter provider/network failure and determine whether
    controlled primary->secondary key failover is permitted.

    Policy:
    - Transient network/connection/timeout/5xx failures -> eligible_for_failover=True
    - Key-specific auth failure (HTTP 401) -> eligible_for_failover=True
    - Transient per-key rate-limit (HTTP 429 without account-level quota exhaustion
      and without long Retry-After cooldown) -> eligible_for_failover=True
    - Account/policy blocks (402 quota, 403 permission, daily quota 429) -> eligible_for_failover=False
    - Invalid payloads (400/422), invalid model (404), programming errors -> eligible_for_failover=False
    """
    import socket
    import urllib.error

    detail_lower = (err_detail or "").lower()

    if status_code is not None:
        if status_code == 429:
            is_account_limit = any(
                tok in detail_lower for tok in ("free-models-per-day", "daily", "quota", "credits")
            )
            long_cooldown = retry_after is not None and retry_after > 5
            eligible = not is_account_limit and not long_cooldown
            return {
                "category": "rate_limited",
                "eligible_for_failover": eligible,
                "http_status": 429,
                "user_message": "The AI service is temporarily rate-limited. Please try again in a few moments.",
            }
        if status_code == 402:
            return {
                "category": "quota_exhausted",
                "eligible_for_failover": False,
                "http_status": 402,
                "user_message": "The AI service quota is currently unavailable. Please contact the administrator.",
            }
        if status_code == 401:
            return {
                "category": "auth_error",
                "eligible_for_failover": True,
                "http_status": 401,
                "user_message": "AI authentication failed. Please check the backend OpenRouter API key.",
            }
        if status_code == 403:
            return {
                "category": "permission_denied",
                "eligible_for_failover": False,
                "http_status": 403,
                "user_message": "AI request was denied by provider permissions. Please contact the administrator.",
            }
        if status_code in (400, 422):
            return {
                "category": "invalid_request",
                "eligible_for_failover": False,
                "http_status": status_code,
                "user_message": "The AI request could not be processed due to invalid parameters.",
            }
        if status_code == 404:
            return {
                "category": "model_not_found",
                "eligible_for_failover": False,
                "http_status": 404,
                "user_message": "The configured AI model is currently unavailable.",
            }
        if status_code == 408:
            return {
                "category": "timeout",
                "eligible_for_failover": True,
                "http_status": 408,
                "user_message": "The AI service timed out. Please try again shortly.",
            }
        if 500 <= status_code < 600:
            return {
                "category": "server_error",
                "eligible_for_failover": True,
                "http_status": status_code,
                "user_message": "The AI service is temporarily unavailable. Please try again later.",
            }
        return {
            "category": f"http_error_{status_code}",
            "eligible_for_failover": False,
            "http_status": status_code,
            "user_message": "The AI service could not complete the request.",
        }

    if exc is not None:
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return {
                "category": "timeout",
                "eligible_for_failover": True,
                "http_status": None,
                "user_message": "The AI service timed out. Please try again shortly.",
            }
        if isinstance(exc, urllib.error.URLError):
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(exc).lower():
                return {
                    "category": "timeout",
                    "eligible_for_failover": True,
                    "http_status": None,
                    "user_message": "The AI service timed out. Please try again shortly.",
                }
            return {
                "category": "network_error",
                "eligible_for_failover": True,
                "http_status": None,
                "user_message": "Unable to reach the AI service endpoint due to a network error.",
            }
        if isinstance(exc, (ConnectionError, OSError)):
            return {
                "category": "network_error",
                "eligible_for_failover": True,
                "http_status": None,
                "user_message": "Unable to reach the AI service endpoint due to a network error.",
            }
        if isinstance(exc, json.JSONDecodeError):
            return {
                "category": "provider_response_error",
                "eligible_for_failover": True,
                "http_status": None,
                "user_message": "The AI service returned an unexpected response. Please try again later.",
            }

    return {
        "category": f"unexpected_error:{type(exc).__name__}" if exc else "service_unavailable",
        "eligible_for_failover": False,
        "http_status": None,
        "user_message": "The AI service is temporarily unavailable. Please try again later.",
    }


def _log_provider_event(
    *,
    request_category: str,
    key_slot: str,
    model: str,
    outcome: str,
    duration_ms: int,
    failover_triggered: bool,
    error_category: Optional[str] = None,
) -> None:
    """
    Emit a strictly sanitized OpenRouter diagnostic log entry.
    Never logs API keys, Authorization headers, credentials, or patient prompts/PHI.
    """
    from datetime import datetime, timezone

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_category": request_category,
        "key_slot": key_slot,
        "model": model,
        "error_category": error_category,
        "failover_triggered": bool(failover_triggered),
        "outcome": outcome,
        "duration_ms": int(duration_ms),
    }
    if outcome == "success":
        logger.info("OpenRouter request succeeded: %s", json.dumps(event))
    else:
        logger.warning("OpenRouter request failed: %s", json.dumps(event))


def _send_single_openrouter_request(
    payload: Dict[str, Any],
    api_key: str,
    timeout: int,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Execute a single HTTP POST to OPENROUTER_ENDPOINT with the supplied API key.
    Returns (ok, parsed_json_data, error_classification).
    """
    import urllib.request
    import urllib.error

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://jeevansetu.in",
        "X-Title": "Jeevan Setu AI Clinical Assistant",
    }

    try:
        req = urllib.request.Request(
            OPENROUTER_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            resp_body = resp.read().decode("utf-8")
            data = json.loads(resp_body)
            if status_code == 200 and isinstance(data, dict) and data.get("choices"):
                return True, data, None
            return False, None, classify_openrouter_error(status_code=status_code if status_code != 200 else None)
    except urllib.error.HTTPError as e:
        err_detail = ""
        retry_after = None
        try:
            if e.headers:
                ra_raw = e.headers.get("Retry-After")
                if ra_raw and str(ra_raw).strip().isdigit():
                    retry_after = int(str(ra_raw).strip())
        except Exception:
            pass
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            err_detail = str(err_json.get("error", {}).get("message") or "")
        except Exception:
            pass
        return False, None, classify_openrouter_error(
            status_code=e.code, exc=e, err_detail=err_detail, retry_after=retry_after
        )
    except Exception as exc:
        return False, None, classify_openrouter_error(exc=exc)


def _execute_openrouter_with_failover(
    payload: Dict[str, Any],
    request_category: str,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Controlled Primary -> Secondary OpenRouter failover controller.
    - Primary key is always attempted first.
    - Secondary key is attempted at most once, only when the primary failure is
      classified as eligible, failover is enabled, and a distinct secondary key exists.
    - Never alters `payload["model"]`, messages, tools, or multimodal blocks.
    - Never permanently switches the default key away from primary.
    """
    import time

    model_name = str(payload.get("model") or get_openrouter_model())
    cfg = validate_openrouter_config(model_override=model_name)
    effective_timeout = get_openrouter_timeout(timeout)

    if not cfg["enabled"]:
        return {
            "success": False,
            "data": None,
            "error_info": {
                "category": "openrouter_disabled",
                "eligible_for_failover": False,
                "http_status": None,
                "user_message": "External OpenRouter AI integration is currently disabled.",
            },
            "key_slot_used": None,
            "failover_triggered": False,
            "failover_reason": None,
        }

    if not cfg["model_valid"]:
        return {
            "success": False,
            "data": None,
            "error_info": {
                "category": "invalid_model_config",
                "eligible_for_failover": False,
                "http_status": None,
                "user_message": "The configured OpenRouter model identifier is invalid.",
            },
            "key_slot_used": None,
            "failover_triggered": False,
            "failover_reason": None,
        }

    primary_key = get_primary_api_key()
    if not primary_key:
        return {
            "success": False,
            "data": None,
            "error_info": {
                "category": "missing_api_key",
                "eligible_for_failover": False,
                "http_status": None,
                "user_message": "The OpenRouter Primary API key is not configured. Please set OPENROUTER_PRIMARY_API_KEY in the backend environment.",
            },
            "key_slot_used": None,
            "failover_triggered": False,
            "failover_reason": None,
        }

    t0 = time.monotonic()
    ok, data, err_info = _send_single_openrouter_request(payload, primary_key, effective_timeout)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if ok and data is not None:
        _log_provider_event(
            request_category=request_category,
            key_slot="primary",
            model=model_name,
            outcome="success",
            duration_ms=dur_ms,
            failover_triggered=False,
        )
        return {
            "success": True,
            "data": data,
            "error_info": None,
            "key_slot_used": "primary",
            "failover_triggered": False,
            "failover_reason": None,
        }

    primary_err = err_info or classify_openrouter_error()
    _log_provider_event(
        request_category=request_category,
        key_slot="primary",
        model=model_name,
        outcome="failure",
        duration_ms=dur_ms,
        failover_triggered=False,
        error_category=primary_err["category"],
    )

    secondary_key = get_secondary_api_key()
    can_failover = (
        bool(primary_err.get("eligible_for_failover"))
        and cfg["failover_enabled"]
        and get_openrouter_max_retries() >= 1
        and bool(secondary_key)
    )

    if not can_failover:
        return {
            "success": False,
            "data": None,
            "error_info": primary_err,
            "key_slot_used": "primary",
            "failover_triggered": False,
            "failover_reason": None,
        }

    t1 = time.monotonic()
    s_ok, s_data, s_err_info = _send_single_openrouter_request(payload, secondary_key, effective_timeout)
    s_dur_ms = int((time.monotonic() - t1) * 1000)

    if s_ok and s_data is not None:
        _log_provider_event(
            request_category=request_category,
            key_slot="secondary",
            model=model_name,
            outcome="success",
            duration_ms=s_dur_ms,
            failover_triggered=True,
            error_category=primary_err["category"],
        )
        return {
            "success": True,
            "data": s_data,
            "error_info": None,
            "key_slot_used": "secondary",
            "failover_triggered": True,
            "failover_reason": primary_err["category"],
        }

    secondary_err = s_err_info or classify_openrouter_error()
    _log_provider_event(
        request_category=request_category,
        key_slot="secondary",
        model=model_name,
        outcome="failure",
        duration_ms=s_dur_ms,
        failover_triggered=True,
        error_category=secondary_err["category"],
    )
    return {
        "success": False,
        "data": None,
        "error_info": secondary_err,
        "key_slot_used": "secondary",
        "failover_triggered": True,
        "failover_reason": primary_err["category"],
    }


def query_openrouter_gemini(
    user_message: str,
    patient_context: Optional[Dict[str, Any]] = None,
    user_role: str = "doctor",
    timeout: int = 15,
    mode: str = "patient",
    knowledge_context: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Calls OpenRouter API (configured model) to explain verified clinical data
    or answer general healthcare inquiries, using the controlled Primary/Backup
    key failover controller.
    """
    model = get_openrouter_model()
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
            {"role": "user", "content": user_message},
        ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 800,
    }

    req_category = "general_chat" if is_general_mode else "patient_chat"
    result = _execute_openrouter_with_failover(
        payload=payload,
        request_category=req_category,
        timeout=timeout,
    )

    if result["success"] and result["data"]:
        raw_text = result["data"]["choices"][0].get("message", {}).get("content", "").strip()
        ai_text = clean_ai_response(raw_text)
        if ai_text:
            return True, ai_text, {
                "model": model,
                "provider": "openrouter",
                "status": "success",
                "mode": "general" if is_general_mode else "patient",
                "key_slot_used": result["key_slot_used"],
                "failover_triggered": result["failover_triggered"],
                "failover_reason": result["failover_reason"],
            }

    err = result.get("error_info") or {}
    meta = {
        "error": err.get("category", "service_unavailable"),
        "key_slot_used": result.get("key_slot_used"),
        "failover_triggered": result.get("failover_triggered", False),
        "failover_reason": result.get("failover_reason"),
    }
    if err.get("http_status") is not None:
        meta["code"] = err["http_status"]
    return False, err.get("user_message", "The AI service is temporarily unavailable. Please try again later."), meta


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
    Send a chat completion request to OpenRouter (preserving model, messages,
    tools, and multimodal payloads) with controlled Primary/Backup key failover.
    """
    model = model_override or get_openrouter_model()
    req_category = "tool_calling" if tools else "multimodal_or_chat"

    base_payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        base_payload["tools"] = tools
        base_payload["tool_choice"] = tool_choice

    last_res: Dict[str, Any] = {}
    for attempt_native in ([True, False] if tools else [False]):
        req_payload = dict(base_payload)
        if not attempt_native and "tools" in req_payload:
            req_payload.pop("tools", None)
            req_payload.pop("tool_choice", None)

        res = _execute_openrouter_with_failover(
            payload=req_payload,
            request_category=req_category,
            timeout=timeout,
        )
        last_res = res

        if res["success"] and res["data"]:
            msg_obj = res["data"]["choices"][0].get("message") or {}
            if "content" in msg_obj and isinstance(msg_obj["content"], str):
                msg_obj["content"] = clean_ai_response(msg_obj["content"])
            return {
                "success": True,
                "model": model,
                "message": msg_obj,
                "raw_response": res["data"],
                "native_tools_used": attempt_native,
                "error": None,
                "requested_model": model,
                "actual_model": model,
                "is_fallback": False,
                "fallback_reason": None,
                "provider": "openrouter",
                "key_slot_used": res["key_slot_used"],
                "failover_triggered": res["failover_triggered"],
                "failover_reason": res["failover_reason"],
            }

        err_info = res.get("error_info") or {}
        if attempt_native and err_info.get("http_status") in (400, 422):
            # Route did not accept native `tools` parameter; retry without `tools` on primary
            continue
        break

    err_info = last_res.get("error_info") or {}
    err_cat = err_info.get("category", "service_unavailable")
    if err_info.get("http_status") in (401, 403):
        err_cat = f"auth_error_{err_info['http_status']}"

    return {
        "success": False,
        "model": model if last_res.get("key_slot_used") else None,
        "message": {},
        "raw_response": {},
        "native_tools_used": False,
        "error": err_cat,
        "requested_model": model,
        "actual_model": None,
        "is_fallback": False,
        "fallback_reason": err_cat,
        "provider": "openrouter",
        "key_slot_used": last_res.get("key_slot_used"),
        "failover_triggered": last_res.get("failover_triggered", False),
        "failover_reason": last_res.get("failover_reason"),
    }


__all__ = [
    "is_openrouter_enabled",
    "is_failover_enabled",
    "get_openrouter_timeout",
    "get_openrouter_max_retries",
    "get_primary_api_key",
    "get_secondary_api_key",
    "get_openrouter_api_key",
    "get_openrouter_model",
    "validate_openrouter_config",
    "is_ai_configured",
    "classify_openrouter_error",
    "clean_ai_response",
    "build_controlled_patient_context",
    "query_openrouter_gemini",
    "call_openrouter_with_tools",
    "PATIENT_CHAT_PROMPT",
    "GENERAL_CHAT_PROMPT",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_GENERAL",
]


