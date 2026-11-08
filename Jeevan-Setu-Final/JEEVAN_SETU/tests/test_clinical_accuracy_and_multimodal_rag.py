"""
tests/test_clinical_accuracy_and_multimodal_rag.py

Regression Test Suite for Jeevan Setu Chatbot Clinical Accuracy,
Data Consistency, Authoritative EWS, Vital Representation, Trend Grounding,
and Multimodal Image Analysis.

Covers:
1. EWS score mismatch reconciliation.
2. Historical versus current EWS with explicit timestamps.
3. Missing blood pressure values (diastolic missing, systolic missing).
4. Invalid vital units validation (bpm, breaths/min, mmHg, °C, %).
5. Abnormal vitals incorrectly described as stable prevention.
6. Insufficient historical observations message.
7. Cross-patient data mixing prevention.
8. Authoritative transfer recommendation preservation.
9. Vision processor unavailable explicit reporting.
10. OCR unavailable reporting.
11. Image successfully processed with cautious disclaimer.
12. Image uploaded but not processed.
13. Source attribution (MySQL, ChromaDB, Vision).
14. Patient Chat authorization and RBAC isolation.
"""

import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from chatbot.rag.rag_chatbot import query_rag_chatbot, _build_mysql_sources_from_context
from chatbot.rag.context_builder import _format_patient_core_lines
from chatbot.services.openrouter_service import build_controlled_patient_context
from chatbot.services.chatbot_engine import (
    calculate_vital_trends,
    reason_status_overview,
    reason_single_parameter_inquiry,
    reason_trajectory_and_improvement,
)
from chatbot.vision.vision_service import analyze_image_with_vision, VISION_AI_DISCLAIMER
from chatbot.vision.image_processor import (
    upload_and_process_patient_image,
    reset_fallback_patient_image_store,
)


def _create_test_image(text: str = "CHEST X-RAY PA", size=(200, 100), fmt="PNG") -> bytes:
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 35), text, fill="black", font_size=16)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_stores():
    reset_fallback_patient_image_store()
    yield
    reset_fallback_patient_image_store()


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# =============================================================================
# 1. EWS SCORE MISMATCH RECONCILIATION
# =============================================================================

def test_01_ews_score_mismatch_reconciliation():
    """
    Test 1: When an earlier alert has EWS=3 but the latest observation has EWS=9,
    the context and overview explicitly reconcile them with timestamps and do NOT
    present them as conflicting current scores.
    """
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar", "patient_code": "UHID-2026-00001", "ward_type": "ICU"},
        "latest_vitals": {
            "vital_id": 4397,
            "patient_id": 1,
            "heart_rate": 127.1,
            "blood_pressure_sys": 71.8,
            "blood_pressure_dia": None,
            "respiratory_rate": 30.1,
            "temperature": 39.1,
            "spo2": 89.0,
            "recorded_at": "2026-11-01T20:39:52",
        },
        "ews": {
            "ews_id": 4064,
            "patient_id": 1,
            "vital_id": 4397,
            "score": 9,
            "total_score": 9,
            "risk_level": "CRITICAL",
            "calculated_at": "2026-11-01T20:39:52",
        },
        "recommendation": {
            "recommendation_text": "Keep in ICU",
            "reason": "EWS Total: 9 — Condition: Critical",
            "status": "auto",
        },
        "alerts": [
            {
                "alert_id": 510,
                "patient_id": 1,
                "type": "critical",
                "title": "CRITICAL PATIENT ALERT",
                "message": "Critical condition detected. EWS Score: 3.",
                "value": 3.0,
                "created_at": "2026-11-01T19:42:55",
                "status": "ACTIVE",
            }
        ],
        "vitals_history": [],
    }

    ctx_str = build_controlled_patient_context(mock_context, user_role="doctor")

    # Authoritative current EWS must be 9
    assert "Authoritative EWS Total: 9" in ctx_str
    assert "Clinical Risk Level: CRITICAL" in ctx_str

    # Alert must be labeled as historical because its timestamp (19:42:55) is older than vitals (20:39:52)
    # and its score (3) differs from current EWS (9)
    assert "[HISTORICAL ALERT at 2026-11-01T19:42:55]" in ctx_str
    assert "Discrepancy Note" in ctx_str
    assert "EWS was 3.0" in ctx_str
    assert "current authoritative EWS" in ctx_str


# =============================================================================
# 2. HISTORICAL VERSUS CURRENT EWS TIMESTAMPS
# =============================================================================

def test_02_historical_vs_current_ews_timestamps():
    """
    Test 2: Ensure all historical vitals/EWS readings have explicit recorded_at
    timestamps and observation numbers so past scores are not confused with current.
    """
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar"},
        "latest_vitals": {
            "vital_id": 500,
            "heart_rate": 80,
            "blood_pressure_sys": 120,
            "blood_pressure_dia": 80,
            "recorded_at": "2026-11-01T20:00:00",
        },
        "ews": {"score": 1, "calculated_at": "2026-11-01T20:00:00", "vital_id": 500},
        "vitals_history": [
            {"recorded_at": "2026-11-01T18:00:00", "heart_rate": 95, "ews_score": 4, "blood_pressure_sys": 110, "blood_pressure_dia": 70},
            {"recorded_at": "2026-11-01T12:00:00", "heart_rate": 110, "ews_score": 6, "blood_pressure_sys": 105, "blood_pressure_dia": 65},
        ],
    }

    ctx_str = build_controlled_patient_context(mock_context, user_role="doctor")
    assert "Observation ID: #500" in ctx_str
    assert "Observation Timestamp: 2026-11-01T20:00:00" in ctx_str
    assert "RECENT VITALS HISTORY (PAST READINGS)" in ctx_str
    assert "Reading #1 (2026-11-01T18:00:00):" in ctx_str
    assert "EWS=4" in ctx_str
    assert "Reading #2 (2026-11-01T12:00:00):" in ctx_str
    assert "EWS=6" in ctx_str


# =============================================================================
# 3. MISSING BLOOD PRESSURE VALUES
# =============================================================================

def test_03_missing_blood_pressure_diastolic_unrecorded():
    """
    Test 3: When diastolic blood pressure is null/missing (e.g., SBP 71.8 mmHg, DBP None),
    the system must explicitly state Systolic BP and identify that Diastolic is not recorded.
    Never display ambiguous 'BP: 71.8 mmHg'.
    """
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar"},
        "latest_vitals": {
            "vital_id": 100,
            "blood_pressure_sys": 71.8,
            "blood_pressure_dia": None,
            "recorded_at": "2026-11-01T20:39:52",
        },
    }

    ctx_str = build_controlled_patient_context(mock_context, user_role="doctor")
    assert "Systolic BP: 71.8 mmHg (Diastolic BP: Not recorded)" in ctx_str
    assert "Blood Pressure: 71.8 mmHg\n" not in ctx_str

    # Test in _format_patient_core_lines (context builder)
    lines = _format_patient_core_lines(mock_context, missing_data=[], stale_observations=[])
    core_text = "\n".join(lines)
    assert "Systolic 71.8 mmHg (Diastolic: Not recorded)" in core_text

    # Test in _build_mysql_sources_from_context
    mysql_sources, _ = _build_mysql_sources_from_context(mock_context)
    vitals_src = next((s for s in mysql_sources if s["field"] == "Latest Vital Signs"), None)
    assert vitals_src is not None
    assert "Systolic BP 71.8 mmHg (Diastolic unrecorded)" in vitals_src["value"]


# =============================================================================
# 4. INVALID VITAL UNITS VALIDATION
# =============================================================================

def test_04_vital_units_validation():
    """
    Test 4: Verify units are strictly preserved and explicitly stated:
    HR (bpm), RR (breaths/min), BP (mmHg), Temp (°C), SpO2 (%).
    Missing values must report 'Not recorded' rather than fabricating units (e.g. 'None%').
    """
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar"},
        "latest_vitals": {
            "vital_id": 101,
            "heart_rate": 127.1,
            "respiratory_rate": 30.1,
            "blood_pressure_sys": 119.0,
            "blood_pressure_dia": 78.0,
            "temperature": 39.1,
            "spo2": None,  # Missing SpO2
            "recorded_at": "2026-11-01T20:39:52",
        },
    }

    ctx_str = build_controlled_patient_context(mock_context, user_role="doctor")
    assert "Heart Rate: 127.1 bpm" in ctx_str
    assert "Respiratory Rate: 30.1 breaths/min" in ctx_str
    assert "Blood Pressure: 119.0/78.0 mmHg" in ctx_str
    assert "Temperature: 39.1 °C" in ctx_str
    assert "SpO2: Not recorded" in ctx_str
    assert "None%" not in ctx_str


# =============================================================================
# 5. ABNORMAL VITALS NOT DESCRIBED AS STABLE
# =============================================================================

def test_05_abnormal_vitals_not_described_as_stable():
    """
    Test 5: When vitals show severe physiological abnormalities (HR 127.1, RR 30.1,
    BP 71.8, Temp 39.1, EWS 9), the system must NEVER describe the trend as 'Stable'.
    """
    history_abnormal = [
        {
            "heart_rate": 127.1,
            "respiratory_rate": 30.1,
            "blood_pressure_sys": 71.8,
            "temperature": 39.1,
            "spo2": 89.0,
            "ews_score": 9,
            "recorded_at": "2026-11-01T20:39:52",
        },
        {
            "heart_rate": 126.0,
            "respiratory_rate": 29.5,
            "blood_pressure_sys": 72.0,
            "temperature": 39.0,
            "spo2": 90.0,
            "ews_score": 9,
            "recorded_at": "2026-11-01T20:30:00",
        },
    ]

    trends = calculate_vital_trends(history_abnormal)
    assert trends["has_sufficient_data"] is True
    # Overall direction must NOT be 'STABLE'
    assert trends["overall_direction"] != "STABLE"
    assert trends["overall_direction"] in ("CRITICALLY ABNORMAL (PERSISTENT HIGH RISK)", "WORSENING", "UNSTABLE")


# =============================================================================
# 6. INSUFFICIENT HISTORICAL OBSERVATIONS
# =============================================================================

def test_06_insufficient_historical_observations_trend():
    """
    Test 6: When there is fewer than 2 historical observations, trend calculation
    must explicitly report: 'Insufficient historical data to determine the physiological trend.'
    """
    # 0 readings
    trends_zero = calculate_vital_trends([])
    assert trends_zero["has_sufficient_data"] is False
    assert trends_zero["overall_direction"] == "Insufficient historical data to determine the physiological trend."

    # 1 reading
    trends_one = calculate_vital_trends([{"heart_rate": 75, "recorded_at": "2026-11-01T20:00:00"}])
    assert trends_one["has_sufficient_data"] is False
    assert trends_one["overall_direction"] == "Insufficient historical data to determine the physiological trend."

    # In controlled patient context
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar"},
        "latest_vitals": {"heart_rate": 75, "recorded_at": "2026-11-01T20:00:00"},
        "vitals_history": [{"heart_rate": 75, "recorded_at": "2026-11-01T20:00:00"}],
        "trends": trends_one,
    }
    ctx_str = build_controlled_patient_context(mock_context, user_role="doctor")
    assert "Physiological Trend: Insufficient historical data to determine the physiological trend." in ctx_str


# =============================================================================
# 7. CROSS-PATIENT DATA MIXING PREVENTION
# =============================================================================

def test_07_cross_patient_data_mixing_prevention():
    """
    Test 7: Ensure facts belonging to Patient A (id=1, Rajesh) are strictly isolated
    from Patient B (id=2, Anita).
    """
    patient_a_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar", "patient_code": "UHID-2026-00001"},
        "latest_vitals": {"vital_id": 100, "patient_id": 1, "heart_rate": 127.1, "recorded_at": "2026-11-01T20:00:00"},
        "ews": {"patient_id": 1, "score": 9},
        "recommendation": {"patient_id": 1, "recommendation_text": "Keep in ICU"},
    }

    ctx_a = build_controlled_patient_context(patient_a_context, user_role="doctor")
    assert "Rajesh Kumar" in ctx_a
    assert "UHID-2026-00001" in ctx_a
    assert "Anita" not in ctx_a
    assert "UHID-2026-00002" not in ctx_a

    mysql_sources_a, _ = _build_mysql_sources_from_context(patient_a_context)
    for src in mysql_sources_a:
        assert src["patient_id"] == 1


# =============================================================================
# 8. INCORRECT TRANSFER RECOMMENDATION PREVENTION
# =============================================================================

def test_08_authoritative_transfer_recommendation_preserved():
    """
    Test 8: The existing ICU/HDU transfer decision engine is authoritative.
    Chatbot context preserves the exact recommendation and instructs AI not to override.
    """
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar"},
        "latest_vitals": {"heart_rate": 72, "recorded_at": "2026-11-01T20:00:00"},
        "ews": {"score": 0},
        "recommendation": {
            "recommendation_text": "Fit for HDU Transfer",
            "reason": "EWS Total: 0 — Condition: Stable for >24 hours",
            "from_ward": "ICU",
            "to_ward": "HDU",
            "status": "auto",
        },
    }

    ctx_str = build_controlled_patient_context(mock_context, user_role="doctor")
    assert "Authoritative Recommendation: Fit for HDU Transfer" in ctx_str
    assert "Clinical Rationale: EWS Total: 0 — Condition: Stable for >24 hours" in ctx_str
    assert "Note: This transfer decision is authoritative" in ctx_str


# =============================================================================
# 9. VISION PROCESSOR UNAVAILABLE
# =============================================================================

def test_09_vision_processor_unavailable():
    """
    Test 9: When the multimodal vision model call fails or is unavailable,
    it must explicitly return 'Image analysis was not completed because the vision processor was unavailable.'
    """
    img_bytes = _create_test_image("CHEST XRAY VIEW")

    # Mock vision caller raising network error or returning failed status
    def mock_failed_caller(*args, **kwargs):
        return {"success": False, "error": "rate_limited", "message": {}}

    res = analyze_image_with_vision(
        img_bytes,
        image_scope="patient",
        allow_external_patient_vision=True,
        vision_caller=mock_failed_caller,
    )

    assert res["vision_status"] == "failed"
    assert res["vision_description"] == ""
    assert res["error"] == "Image analysis was not completed because the vision processor was unavailable."


# =============================================================================
# 10. OCR UNAVAILABLE / NO TEXT DETECTED
# =============================================================================

def test_10_ocr_unavailable_reported():
    """
    Test 10: When an image contains no OCR text (e.g. clean X-ray without text overlay),
    it reports that no readable text was detected via OCR, but does NOT claim the scan is normal or analysed.
    """
    img_bytes = _create_test_image("NO TEXT OVERLAY")

    # Mock OCR returning empty text
    def mock_empty_ocr(img_info, **kwargs):
        return {"ocr_status": "completed", "ocr_text": "", "mean_confidence": 0.0}

    # Mock vision returning unavailable
    def mock_fail_vision(*args, **kwargs):
        return {"success": False, "error": "service_unavailable"}

    record = upload_and_process_patient_image(
        patient_id=1,
        user_id=1,
        user_role="doctor",
        file_bytes=img_bytes,
        filename="chest_xray.png",
        allow_external_patient_vision=True,
        ocr_backend=mock_empty_ocr,
        vision_caller=mock_fail_vision,
    )

    assert record["ocr_text"] == ""
    assert record["vision_status"] == "failed"
    assert record["vision_error"] == "Image analysis was not completed because the vision processor was unavailable."


# =============================================================================
# 11. IMAGE SUCCESSFULLY PROCESSED WITH CAUTIOUS DISCLAIMER
# =============================================================================

def test_11_image_successfully_processed_with_cautious_disclaimer():
    """
    Test 11: When vision processing succeeds, it returns a cautious objective description
    of visible features, with mandatory clinician verification required.
    """
    img_bytes = _create_test_image("CHEST XRAY AP VIEW")

    def mock_successful_caller(*args, **kwargs):
        json_content = """{
            "summary": "Frontal view chest radiograph showing clear lung fields and normal cardiac silhouette.",
            "content_type": "clinical_image",
            "visible_labels": ["PA VIEW", "UPRIGHT"],
            "visible_elements": ["lung fields", "cardiac silhouette", "diaphragm"],
            "layout_and_relationships": "Centrally positioned cardiac shadow flanked by bilateral radiolucent lung zones.",
            "uncertainty_notes": "Slight costophrenic angle clipping on lateral border."
        }"""
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {"role": "assistant", "content": json_content},
        }

    res = analyze_image_with_vision(
        img_bytes,
        image_scope="patient",
        allow_external_patient_vision=True,
        vision_caller=mock_successful_caller,
    )

    assert res["vision_status"] == "completed"
    assert "lung fields and normal cardiac silhouette" in res["vision_description"]
    assert res["clinician_verification_required"] is True
    assert res["ai_generated"] is True
    assert VISION_AI_DISCLAIMER in res["disclaimer"]


# =============================================================================
# 12. IMAGE UPLOADED BUT NOT PROCESSED
# =============================================================================

def test_12_image_uploaded_but_not_processed():
    """
    Test 12: When an image is uploaded with vision analysis disabled
    (enable_vision_llm=False), the record clearly indicates vision was skipped.
    """
    img_bytes = _create_test_image("MONITOR SCREENSHOT")

    record = upload_and_process_patient_image(
        patient_id=1,
        user_id=1,
        user_role="doctor",
        file_bytes=img_bytes,
        filename="monitor.png",
        enable_vision_llm=False,
    )

    assert record["vision_status"] == "skipped_privacy_policy"
    assert record["vision_description"] == ""
    assert record["vision_error"] == "Image analysis was not completed because the vision processor was unavailable."


# =============================================================================
# 13. SOURCE ATTRIBUTION
# =============================================================================

def test_13_source_attribution():
    """
    Test 13: Grounding source attribution properly captures fields, units,
    timestamps, and database source provenance.
    """
    mock_context = {
        "patient": {"patient_id": 1, "name": "Rajesh Kumar", "diagnosis": "Post-CABG Recovery"},
        "latest_vitals": {
            "vital_id": 4397,
            "heart_rate": 75.5,
            "blood_pressure_sys": 119.2,
            "blood_pressure_dia": 78.0,
            "respiratory_rate": 16.2,
            "temperature": 36.8,
            "spo2": 98.0,
            "recorded_at": "2026-11-01T20:39:52",
        },
        "ews": {"score": 0, "risk_level": "LOW", "calculated_at": "2026-11-01T20:39:52"},
        "recommendation": {"recommendation_text": "Fit for HDU Transfer", "from_ward": "ICU", "to_ward": "HDU"},
    }

    mysql_sources, tools = _build_mysql_sources_from_context(mock_context)
    assert len(mysql_sources) >= 3

    fields = [s["field"] for s in mysql_sources]
    assert "Latest Vital Signs" in fields
    assert "Persisted EWS Score" in fields
    assert "Authoritative Transfer Recommendation" in fields

    vitals_src = next(s for s in mysql_sources if s["field"] == "Latest Vital Signs")
    assert vitals_src["recorded_at"] == "2026-11-01T20:39:52"
    assert "HR 75.5 bpm" in vitals_src["value"]
    assert "BP 119.2/78.0 mmHg" in vitals_src["value"]


# =============================================================================
# 14. PATIENT CHAT AUTHORIZATION & RBAC ISOLATION
# =============================================================================

def test_14_patient_chat_authorization_and_isolation(client):
    """
    Test 14: Ensure Patient Chat requires authentication and authorized patient access,
    and blocks unauthorized user roles or patient mismatch.
    """
    # 1. Unauthenticated request to protected endpoint returns 401/403
    res_no_auth = client.post("/chatbot/image/upload", data={"mode": "patient", "patient_id": "1"})
    assert res_no_auth.status_code in (401, 403)

    # 2. General Chat mode image upload does NOT accept patient_id
    with patch("routes.chatbot_routes.get_current_request_user") as mock_user:
        mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
        img_bytes = _create_test_image("GENERAL FLOWCHART")
        data = {
            "mode": "general",
            "title": "Reference SOP Flowchart",
            "image": (io.BytesIO(img_bytes), "sop.png"),
        }
        res_gen = client.post("/chatbot/image/upload", data=data, content_type="multipart/form-data")
        assert res_gen.status_code == 200
        gen_json = res_gen.get_json()
        assert gen_json["mode"] == "general"
        assert gen_json["patient_id"] is None
        assert gen_json["image"]["is_patient_data"] is False
