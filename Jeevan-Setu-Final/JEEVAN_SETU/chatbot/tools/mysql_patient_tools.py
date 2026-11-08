"""
chatbot/tools/mysql_patient_tools.py

Narrowly scoped, RBAC-protected MySQL patient clinical tools for Jeevan Setu
Agentic Hybrid RAG.

Security & Clinical Safety Guarantees:
1. No arbitrary SQL execution — only pre-defined parameterized model/database queries.
2. No database credentials or connection strings are ever exposed.
3. No direct LLM-to-database access; every tool call is validated server-side.
4. Strict General Chat isolation: any call with `chat_mode != "patient"` is
   immediately rejected with `PermissionError`.
5. Every tool call validates `user_id`, `user_role`, `patient_id`, and server-side
   patient access authorization (`verify_patient_authorization`) BEFORE reading
   any patient record.
6. Persisted EWS scores and ICU/HDU transfer recommendations remain strictly
   authoritative — these tools never recalculate EWS or invent transfer decisions.
7. Preserves clinical units, observation timestamps, stale-data warnings, and
   honest missing-field reporting.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from chatbot.rag.context_builder import (
    DEFAULT_STALE_THRESHOLD_HOURS,
    VITAL_UNITS,
    detect_stale_observations,
    identify_missing_patient_data,
    normalize_patient_clinical_data,
    sanitize_untrusted_text,
    verify_patient_authorization,
)

logger = logging.getLogger("jeevan_setu.tools.mysql_patient")

try:
    from database.db import db
except (ImportError, ModuleNotFoundError):
    db = None

try:
    from models.patient_model import Patient
    from models.vitals_model import Vitals
    from models.ews_score_model import EWSScore
    from models.recommendation_model import Recommendation
    from models.decision_model import Decision
    from models.explanation_model import Explanation
    from models.transfer_model import Transfer
    from models.alert_model import Alert
    from models.bed_model import Bed
    from models.ward_model import Ward
except (ImportError, ModuleNotFoundError):
    Patient = None
    Vitals = None
    EWSScore = None
    Recommendation = None
    Decision = None
    Explanation = None
    Transfer = None
    Alert = None
    Bed = None
    Ward = None

try:
    from chatbot.services.chatbot_engine import (
        get_patient_clinical_context as _engine_get_patient_context,
        getEWSHistory as _engine_get_ews_history,
        getVitalTrend as _engine_get_vital_trend,
    )
except (ImportError, ModuleNotFoundError):
    _engine_get_patient_context = None
    _engine_get_ews_history = None
    _engine_get_vital_trend = None


# =============================================================================
# INTERNAL VALIDATION & AUTHORIZATION GUARD
# =============================================================================

def _validate_and_authorize_patient_tool(
    patient_id: Any,
    user_id: Any,
    user_role: Optional[str],
    chat_mode: str = "patient",
    assigned_patient_id: Any = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
) -> int:
    """
    Validate chat_mode, patient_id, user identity, and RBAC patient authorization.
    Raises PermissionError or ValueError on failure before any data lookup occurs.
    """
    mode_norm = str(chat_mode or "").strip().lower()
    if mode_norm != "patient":
        raise PermissionError(
            "MySQL patient tools are strictly prohibited outside Patient Chat mode."
        )

    if patient_id is None or isinstance(patient_id, bool):
        raise ValueError("A valid integer patient_id is required.")
    try:
        pid_int = int(patient_id)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid patient_id '{patient_id}': must be a positive integer.") from exc

    if pid_int <= 0:
        raise ValueError(f"Invalid patient_id '{patient_id}': must be > 0.")

    is_auth, err_msg = verify_patient_authorization(
        user_id=user_id,
        user_role=user_role,
        patient_id=pid_int,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )
    if not is_auth:
        raise PermissionError(err_msg or f"Unauthorized access to patient #{pid_int}.")

    return pid_int


def _load_normalized_patient_bundle(
    patient_id: int,
    user_role: str = "doctor",
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve and normalize patient clinical context from an injected provider or
    the existing chatbot engine / MySQL models.
    """
    provider = patient_data_provider or _engine_get_patient_context
    raw_data: Optional[Dict[str, Any]] = None
    if provider is not None:
        raw_data = provider(patient_id)

    if not raw_data or not isinstance(raw_data, dict) or not raw_data.get("patient"):
        return None

    normalized, _ = normalize_patient_clinical_data(raw_data, user_role=user_role)
    return normalized


# =============================================================================
# 1. get_patient_summary
# =============================================================================

def get_patient_summary(
    patient_id: int,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Retrieve authorized demographic, admission, ward/bed, and primary diagnosis
    summary for a specific patient.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_summary",
            "patient_id": pid,
            "found": False,
            "summary": None,
            "missing_fields": ["patient_record"],
            "message": f"Patient #{pid} was not found in MySQL records.",
        }

    p = bundle.get("patient") or {}
    missing: List[str] = []
    for field in ("name", "age", "gender", "blood_group", "ward_type", "bed_number", "diagnosis", "doctor_name"):
        val = p.get(field)
        if val is None or val == "" or val == "N/A":
            missing.append(field)

    return {
        "tool": "get_patient_summary",
        "patient_id": pid,
        "found": True,
        "summary": {
            "patient_id": p.get("patient_id", pid),
            "patient_code": p.get("patient_code"),
            "name": p.get("name"),
            "age": p.get("age"),
            "gender": p.get("gender"),
            "blood_group": p.get("blood_group"),
            "ward_type": p.get("ward_type"),
            "ward_name": p.get("ward_name") or p.get("ward_type"),
            "bed_number": p.get("bed_number"),
            "diagnosis": p.get("diagnosis"),
            "doctor_name": p.get("doctor_name"),
            "status": p.get("status", "admitted"),
            "admission_date": p.get("admission_date"),
        },
        "missing_fields": missing,
        "source": "mysql:patients",
    }


# =============================================================================
# 2. get_patient_vitals
# =============================================================================

def get_patient_vitals(
    patient_id: int,
    include_history: bool = True,
    history_limit: int = 5,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
    stale_threshold_hours: float = DEFAULT_STALE_THRESHOLD_HOURS,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Retrieve latest vital signs with explicit measurement units and timestamps,
    optional historical vital readings, longitudinal trend summary, and stale-data
    flags for an authorized patient.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    safe_limit = max(1, min(int(history_limit or 5), 20))
    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_vitals",
            "patient_id": pid,
            "found": False,
            "latest_vitals": None,
            "vitals_history": [],
            "trends": None,
            "units": dict(VITAL_UNITS),
            "stale_observations": [],
            "missing_fields": ["latest_vitals"],
            "message": f"Patient #{pid} was not found in MySQL records.",
        }

    latest = bundle.get("latest_vitals")
    history = (bundle.get("vitals_history") or [])[:safe_limit] if include_history else []
    trends = bundle.get("trends")
    if trends is None and _engine_get_vital_trend is not None and patient_data_provider is None:
        try:
            trends = _engine_get_vital_trend(pid)
        except Exception:
            trends = None

    stale_obs = [
        s for s in detect_stale_observations(
            bundle, stale_threshold_hours=stale_threshold_hours, reference_time=reference_time
        )
        if s.get("field") == "latest_vitals"
    ]

    missing: List[str] = []
    if not latest:
        missing.append("latest_vitals")
    else:
        for k in (
            "heart_rate",
            "blood_pressure_sys",
            "blood_pressure_dia",
            "respiratory_rate",
            "temperature",
            "spo2",
            "consciousness",
            "recorded_at",
        ):
            if latest.get(k) is None:
                missing.append(k)

    return {
        "tool": "get_patient_vitals",
        "patient_id": pid,
        "found": latest is not None,
        "latest_vitals": latest,
        "vitals_history": history,
        "trends": trends,
        "units": dict(VITAL_UNITS),
        "stale_observations": stale_obs,
        "missing_fields": missing,
        "source": "mysql:vitals",
    }


# =============================================================================
# 3. get_patient_ews
# =============================================================================

def get_patient_ews(
    patient_id: int,
    include_history: bool = False,
    history_limit: int = 5,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
    stale_threshold_hours: float = DEFAULT_STALE_THRESHOLD_HOURS,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Retrieve the authoritative persisted Early Warning Score (EWS), risk level,
    parameter breakdown, and calculation timestamp for an authorized patient.
    Never recalculates or overrides the persisted EWS score.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    safe_limit = max(1, min(int(history_limit or 5), 20))
    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_ews",
            "patient_id": pid,
            "found": False,
            "ews": None,
            "ews_history": [],
            "stale_observations": [],
            "missing_fields": ["ews_score"],
            "authoritative_source": "mysql_persisted_ews",
        }

    ews = bundle.get("ews")
    ews_history: List[Dict[str, Any]] = []
    if include_history:
        if patient_data_provider is None and _engine_get_ews_history is not None:
            try:
                ews_history = _engine_get_ews_history(pid, limit=safe_limit)
            except Exception:
                ews_history = []
        if not ews_history and bundle.get("vitals_history"):
            for h in bundle["vitals_history"][:safe_limit]:
                if isinstance(h, dict) and h.get("ews_score") is not None:
                    ews_history.append({
                        "recorded_at": h.get("recorded_at"),
                        "ews_score": h.get("ews_score"),
                    })

    stale_obs = [
        s for s in detect_stale_observations(
            bundle, stale_threshold_hours=stale_threshold_hours, reference_time=reference_time
        )
        if s.get("field") == "ews"
    ]

    missing = [] if (isinstance(ews, dict) and ews.get("score") is not None) else ["ews_score"]

    return {
        "tool": "get_patient_ews",
        "patient_id": pid,
        "found": len(missing) == 0,
        "ews": ews,
        "ews_history": ews_history,
        "composite_stability_index": bundle.get("composite_stability_index"),
        "stale_observations": stale_obs,
        "missing_fields": missing,
        "authoritative_source": "mysql_persisted_ews",
        "source": "mysql:ews_scores",
    }


# =============================================================================
# 4. get_patient_recommendations
# =============================================================================

def get_patient_recommendations(
    patient_id: int,
    include_explanations: bool = True,
    include_decision_history: bool = True,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Retrieve the authoritative persisted ICU/HDU transfer recommendation,
    clinician decision history, and Explainable AI (XAI) feature contributions.
    Never generates a competing transfer decision.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_recommendations",
            "patient_id": pid,
            "found": False,
            "recommendation": None,
            "decisions_history": [],
            "explanations": [],
            "missing_fields": ["transfer_recommendation"],
            "authoritative_source": "mysql_transfer_decision_engine",
        }

    rec = bundle.get("recommendation")
    decisions_history = (bundle.get("decisions_history") or []) if include_decision_history else []
    explanations = (bundle.get("explanations") or []) if include_explanations else []

    missing = [] if (isinstance(rec, dict) and rec.get("recommendation_text")) else ["transfer_recommendation"]

    return {
        "tool": "get_patient_recommendations",
        "patient_id": pid,
        "found": len(missing) == 0,
        "recommendation": rec,
        "decisions_history": decisions_history,
        "explanations": explanations,
        "missing_fields": missing,
        "authoritative_source": "mysql_transfer_decision_engine",
        "source": "mysql:recommendations,decisions,explanations",
    }


# =============================================================================
# 5. get_patient_transfer_history
# =============================================================================

def get_patient_transfer_history(
    patient_id: int,
    limit: int = 5,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Retrieve ward/bed transfer history and clinician transfer decision logs for
    an authorized patient.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    safe_limit = max(1, min(int(limit or 5), 20))
    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_transfer_history",
            "patient_id": pid,
            "found": False,
            "transfers": [],
            "decisions_history": [],
            "missing_fields": ["transfer_history"],
        }

    transfers = list(bundle.get("transfers") or [])[:safe_limit]
    if not transfers and patient_data_provider is None and db is not None:
        try:
            rows = db.execute_query(
                """SELECT transfer_id, patient_id, from_ward, to_ward,
                          from_bed_number, to_bed_number, transfer_reason,
                          status, created_at, completed_at
                   FROM transfers
                   WHERE patient_id = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (pid, safe_limit),
                fetch=True,
            )
            if rows:
                transfers = [
                    {
                        "transfer_id": r.get("transfer_id"),
                        "from_ward": r.get("from_ward"),
                        "to_ward": r.get("to_ward"),
                        "from_bed_number": r.get("from_bed_number"),
                        "to_bed_number": r.get("to_bed_number"),
                        "transfer_reason": r.get("transfer_reason"),
                        "status": r.get("status"),
                        "created_at": str(r.get("created_at", "")),
                        "completed_at": str(r.get("completed_at", "")) if r.get("completed_at") else None,
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.debug("Transfer query skipped: %s", exc)

    decisions = list(bundle.get("decisions_history") or [])[:safe_limit]
    has_records = bool(transfers or decisions)

    return {
        "tool": "get_patient_transfer_history",
        "patient_id": pid,
        "found": has_records,
        "transfers": transfers,
        "decisions_history": decisions,
        "missing_fields": [] if has_records else ["transfer_history"],
        "source": "mysql:transfers,decisions",
    }


# =============================================================================
# 6. get_patient_clinical_notes
# =============================================================================

def get_patient_clinical_notes(
    patient_id: int,
    limit: int = 5,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Retrieve documented primary diagnosis and sanitized clinical notes / medical
    history for an authorized patient.
    Attendant role is restricted from viewing internal clinician progress notes.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    role_norm = str(user_role or "doctor").strip().lower()
    if role_norm == "attendant":
        raise PermissionError(
            "Access restricted: Attendant role cannot access internal clinical progress notes."
        )

    safe_limit = max(1, min(int(limit or 5), 20))
    bundle = _load_normalized_patient_bundle(
        pid, user_role=role_norm, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_clinical_notes",
            "patient_id": pid,
            "found": False,
            "diagnosis": None,
            "clinical_notes": [],
            "missing_fields": ["diagnosis", "clinical_notes"],
        }

    diagnosis = bundle.get("diagnosis") or (bundle.get("patient") or {}).get("diagnosis")
    notes = list(bundle.get("clinical_notes") or [])[:safe_limit]

    missing: List[str] = []
    if not diagnosis:
        missing.append("diagnosis")
    if not notes:
        missing.append("clinical_notes")

    return {
        "tool": "get_patient_clinical_notes",
        "patient_id": pid,
        "found": bool(diagnosis or notes),
        "diagnosis": diagnosis,
        "clinical_notes": notes,
        "missing_fields": missing,
        "source": "mysql:patients,clinical_notes",
    }


# =============================================================================
# 7. get_patient_alerts
# =============================================================================

def get_patient_alerts(
    patient_id: int,
    limit: int = 5,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Retrieve active and recent clinical telemetry alerts for an authorized patient.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    safe_limit = max(1, min(int(limit or 5), 20))
    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_alerts",
            "patient_id": pid,
            "found": False,
            "alerts": [],
            "active_count": 0,
            "missing_fields": ["patient_record"],
        }

    alerts = list(bundle.get("alerts") or [])[:safe_limit]
    active_count = sum(1 for a in alerts if isinstance(a, dict) and not a.get("is_acknowledged", False))

    return {
        "tool": "get_patient_alerts",
        "patient_id": pid,
        "found": True,
        "alerts": alerts,
        "active_count": active_count,
        "missing_fields": [],
        "source": "mysql:alerts",
    }


# =============================================================================
# 8. get_patient_bed_and_ward_details
# =============================================================================

def get_patient_bed_and_ward_details(
    patient_id: int,
    *,
    user_id: Optional[Union[int, str]] = None,
    user_role: str = "doctor",
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    patient_data_provider: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Retrieve current ward, bed number, allocation details, and ward-type metadata
    for an authorized patient.
    """
    pid = _validate_and_authorize_patient_tool(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )

    bundle = _load_normalized_patient_bundle(
        pid, user_role=user_role, patient_data_provider=patient_data_provider
    )
    if not bundle:
        return {
            "tool": "get_patient_bed_and_ward_details",
            "patient_id": pid,
            "found": False,
            "bed_and_ward": None,
            "missing_fields": ["bed_and_ward"],
        }

    p = bundle.get("patient") or {}
    ward_type = p.get("ward_type")
    ward_name = p.get("ward_name") or ward_type
    bed_number = p.get("bed_number")

    floor_number = None
    allocated_at = None
    bed_status = "occupied" if bed_number and bed_number != "N/A" else "unassigned"

    # Query supplementary bed_management / wards info when connected to MySQL
    if patient_data_provider is None and db is not None:
        try:
            rows = db.execute_query(
                """SELECT b.bed_id, b.bed_number, b.status AS bed_status,
                          w.ward_id, w.name AS ward_name, w.ward_type, w.floor_number,
                          bm.allocated_at
                   FROM patients pt
                   LEFT JOIN beds b ON pt.bed_id = b.bed_id
                   LEFT JOIN wards w ON COALESCE(pt.ward_id, b.ward_id) = w.ward_id
                   LEFT JOIN bed_management bm ON pt.patient_id = bm.patient_id
                        AND bm.status IN ('allocated', 'occupied')
                   WHERE pt.patient_id = %s
                   ORDER BY bm.allocated_at DESC LIMIT 1""",
                (pid,),
                fetch=True,
            )
            if rows:
                r = rows[0]
                ward_name = r.get("ward_name") or ward_name
                ward_type = r.get("ward_type") or ward_type
                bed_number = r.get("bed_number") or bed_number
                bed_status = r.get("bed_status") or bed_status
                floor_number = r.get("floor_number")
                allocated_at = str(r.get("allocated_at")) if r.get("allocated_at") else None
        except Exception as exc:
            logger.debug("Supplementary bed/ward query skipped: %s", exc)

    missing: List[str] = []
    if not ward_type:
        missing.append("ward_type")
    if not bed_number or bed_number == "N/A":
        missing.append("bed_number")

    return {
        "tool": "get_patient_bed_and_ward_details",
        "patient_id": pid,
        "found": True,
        "bed_and_ward": {
            "patient_id": pid,
            "patient_name": p.get("name"),
            "ward_type": ward_type,
            "ward_name": ward_name,
            "bed_number": bed_number,
            "bed_status": bed_status,
            "floor_number": floor_number,
            "allocated_at": allocated_at,
            "admission_status": p.get("status", "admitted"),
        },
        "missing_fields": missing,
        "source": "mysql:patients,beds,wards,bed_management",
    }


__all__ = [
    "get_patient_summary",
    "get_patient_vitals",
    "get_patient_ews",
    "get_patient_recommendations",
    "get_patient_transfer_history",
    "get_patient_clinical_notes",
    "get_patient_alerts",
    "get_patient_bed_and_ward_details",
]

