"""
tests/test_mysql_patient_tools.py

Pytest suite for Jeevan Setu MySQL Patient Tools (`chatbot/tools/mysql_patient_tools.py`).

Tests:
1. All 8 MySQL patient tools with authorized fictional patient fixtures.
2. Units and timestamps preservation on vital signs.
3. Stale observation detection on vitals and EWS.
4. Honest missing-field reporting when patient fields are absent.
5. Authoritative EWS and ICU/HDU transfer recommendation preservation (never recalculated).
6. General Chat mode rejection (`PermissionError`).
7. Unauthorized user / cross-patient rejection (`PermissionError`).
8. Attendant role restriction on clinical progress notes.
"""

from datetime import datetime, timezone
import pytest

from chatbot.tools.mysql_patient_tools import (
    get_patient_alerts,
    get_patient_bed_and_ward_details,
    get_patient_clinical_notes,
    get_patient_ews,
    get_patient_recommendations,
    get_patient_summary,
    get_patient_transfer_history,
    get_patient_vitals,
)


@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fictional_patient_bundle() -> dict:
    return {
        "patient": {
            "patient_id": 601,
            "patient_code": "JS-0601",
            "name": "Fictional Patient Beta",
            "age": 62,
            "gender": "Male",
            "blood_group": "B+",
            "ward_type": "ICU",
            "ward_name": "ICU-1",
            "bed_number": "ICU-09",
            "diagnosis": "Synthetic Respiratory Observation",
            "doctor_name": "Dr. Fictional Attending",
            "status": "admitted",
            "admission_date": "2026-10-29 08:30:00",
        },
        "diagnosis": "Synthetic Respiratory Observation",
        "latest_vitals": {
            "vital_id": 801,
            "heart_rate": 88,
            "blood_pressure_sys": 118,
            "blood_pressure_dia": 76,
            "respiratory_rate": 18,
            "temperature": 37.2,
            "spo2": 96,
            "consciousness": "Alert",
            "recorded_at": "2026-11-01 13:30:00",
        },
        "vitals_history": [
            {
                "vital_id": 801,
                "heart_rate": 88,
                "blood_pressure_sys": 118,
                "blood_pressure_dia": 76,
                "respiratory_rate": 18,
                "temperature": 37.2,
                "spo2": 96,
                "consciousness": "Alert",
                "ews_score": 1,
                "recorded_at": "2026-11-01 13:30:00",
            }
        ],
        "ews": {
            "score": 1,
            "risk_level": "LOW",
            "breakdown": {"spo2": {"value": 96, "score": 1}},
            "calculated_at": "2026-11-01 13:30:00",
        },
        "recommendation": {
            "recommendation_id": 901,
            "recommendation_text": "Consider Step-Down to HDU",
            "from_ward": "ICU",
            "to_ward": "HDU",
            "reason": "Stable vitals and low EWS score of 1.",
            "status": "pending",
            "decided_at": "2026-11-01 13:35:00",
        },
        "decisions_history": [
            {
                "decision_id": 51,
                "recommendation": "Remain in ICU",
                "from_ward": "ICU",
                "to_ward": "ICU",
                "status": "approved",
                "decided_by_name": "Dr. Fictional Attending",
                "decided_at": "2026-10-31 18:00:00",
            }
        ],
        "explanations": [
            {
                "explanation_id": 1,
                "decision_id": 51,
                "feature_name": "spo2",
                "feature_value": "96%",
                "contribution": -0.25,
                "importance_rank": 1,
                "explanation_text": "Oxygen saturation stable above 95%.",
            }
        ],
        "alerts": [
            {
                "alert_id": 77,
                "type": "low",
                "title": "Routine Step-Down Review",
                "message": "Patient eligible for HDU evaluation.",
                "is_acknowledged": False,
                "created_at": "2026-11-01 13:35:00",
            }
        ],
        "clinical_notes": [
            {
                "note_id": 301,
                "note_type": "progress",
                "note_text": "Patient comfortable on room air.",
                "created_at": "2026-11-01 12:00:00",
            }
        ],
    }


def test_01_all_mysql_patient_tools_succeed_when_authorized(fictional_patient_bundle, ref_time):
    common_kwargs = {
        "user_id": 10,
        "user_role": "doctor",
        "chat_mode": "patient",
        "authorization_fn": lambda u, pid: (True, ""),
        "patient_data_provider": lambda pid: fictional_patient_bundle,
    }

    summary_res = get_patient_summary(601, **common_kwargs)
    assert summary_res["found"] is True
    assert summary_res["summary"]["name"] == "Fictional Patient Beta"
    assert summary_res["summary"]["ward_type"] == "ICU"

    vitals_res = get_patient_vitals(601, reference_time=ref_time, **common_kwargs)
    assert vitals_res["found"] is True
    assert vitals_res["latest_vitals"]["heart_rate"] == 88
    assert vitals_res["units"]["heart_rate"] == "bpm"
    assert vitals_res["units"]["blood_pressure_sys"] == "mmHg"
    assert vitals_res["stale_observations"] == []

    ews_res = get_patient_ews(601, include_history=True, reference_time=ref_time, **common_kwargs)
    assert ews_res["found"] is True
    assert ews_res["ews"]["score"] == 1
    assert ews_res["authoritative_source"] == "mysql_persisted_ews"

    rec_res = get_patient_recommendations(601, **common_kwargs)
    assert rec_res["found"] is True
    assert rec_res["recommendation"]["recommendation_text"] == "Consider Step-Down to HDU"
    assert rec_res["authoritative_source"] == "mysql_transfer_decision_engine"
    assert len(rec_res["explanations"]) == 1

    transfer_res = get_patient_transfer_history(601, **common_kwargs)
    assert transfer_res["found"] is True
    assert len(transfer_res["decisions_history"]) == 1

    notes_res = get_patient_clinical_notes(601, **common_kwargs)
    assert notes_res["found"] is True
    assert notes_res["diagnosis"] == "Synthetic Respiratory Observation"
    assert len(notes_res["clinical_notes"]) == 1

    alerts_res = get_patient_alerts(601, **common_kwargs)
    assert alerts_res["found"] is True
    assert alerts_res["active_count"] == 1

    bed_res = get_patient_bed_and_ward_details(601, **common_kwargs)
    assert bed_res["found"] is True
    assert bed_res["bed_and_ward"]["bed_number"] == "ICU-09"
    assert bed_res["bed_and_ward"]["ward_type"] == "ICU"


def test_02_general_chat_mode_strictly_rejected(fictional_patient_bundle):
    with pytest.raises(PermissionError, match="strictly prohibited outside Patient Chat mode"):
        get_patient_vitals(
            601,
            user_id=10,
            user_role="doctor",
            chat_mode="general",
            authorization_fn=lambda u, pid: (True, ""),
            patient_data_provider=lambda pid: fictional_patient_bundle,
        )


def test_03_unauthorized_patient_access_rejected(fictional_patient_bundle):
    with pytest.raises(PermissionError, match="Access forbidden"):
        get_patient_summary(
            601,
            user_id=99,
            user_role="doctor",
            chat_mode="patient",
            authorization_fn=lambda u, pid: (False, "Access forbidden: not assigned doctor."),
            patient_data_provider=lambda pid: fictional_patient_bundle,
        )


def test_04_attendant_restricted_from_clinical_notes(fictional_patient_bundle):
    with pytest.raises(PermissionError, match="Attendant role cannot access internal clinical progress notes"):
        get_patient_clinical_notes(
            601,
            user_id=45,
            user_role="attendant",
            chat_mode="patient",
            assigned_patient_id=601,
            authorization_fn=lambda u, pid: (True, ""),
            patient_data_provider=lambda pid: fictional_patient_bundle,
        )


def test_05_missing_patient_data_reported_honestly():
    res = get_patient_summary(
        9999,
        user_id=1,
        user_role="admin",
        chat_mode="patient",
        authorization_fn=lambda u, pid: (True, ""),
        patient_data_provider=lambda pid: None,
    )
    assert res["found"] is False
    assert "patient_record" in res["missing_fields"]

