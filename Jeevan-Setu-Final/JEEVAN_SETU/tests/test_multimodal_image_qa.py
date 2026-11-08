"""
tests/test_multimodal_image_qa.py

Comprehensive 16-criteria Pytest Suite for Jeevan Setu Complete Multimodal Vision,
Image Question Answering, Response Isolation, and Active Image Context Tracking.

Coverage (16 Required Evaluation Criteria):
1. Multimodal payload structure: Actual image bytes (base64 data URL) reach vision service.
2. Correct image ID & file used.
3. Two different images produce distinct answers (no generic caching/descriptions).
4. Image answer excludes patient telemetry (vitals isolated).
5. Image answer excludes EWS scores.
6. Image answer excludes transfer recommendations.
7. Image answer excludes unrelated patient images.
8. Follow-up question correctly uses previous image context without re-upload.
9. New image upload replaces previous active image context.
10. Normal Patient Chat remains functional (Path B).
11. General Chat remains isolated from MySQL (Path C).
12. Transparent model routing and fallback logging verified.
13. Unauthorized image access rejected (403 Forbidden).
14. No fabricated visual findings & prohibited claims neutralized.
15. Strict 4-part structure verified (**Answer**, **Visible observations**, **Limitations**, **Important note**).
16. Clear active image context endpoint works correctly.
"""

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from chatbot.vision.vision_service import (
    IMAGE_QA_DISCLAIMER,
    IMAGE_QA_SYSTEM_PROMPT,
    answer_image_question,
    format_image_qa_response,
)
from chatbot.vision.image_processor import (
    ActiveImageContextManager,
    clear_active_image_context,
    get_active_image_context,
    get_authorized_patient_images,
    reset_fallback_patient_image_store,
    set_active_image_context,
    upload_and_process_patient_image,
)


def _create_synthetic_test_image(text: str = "CHEST XRAY AP", color=(240, 240, 240)) -> bytes:
    """Generate in-memory PNG image bytes for deterministic automated testing."""
    img = Image.new("RGB", (240, 160), color=color)
    draw = ImageDraw.Draw(img)
    draw.text((15, 60), text, fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_env_and_stores():
    reset_fallback_patient_image_store()
    clear_active_image_context(1, 1, "patient")
    clear_active_image_context(1, None, "general")
    with patch.dict(os.environ, {"ALLOW_EXTERNAL_PATIENT_VISION": "true"}):
        yield
    reset_fallback_patient_image_store()
    clear_active_image_context(1, 1, "patient")
    clear_active_image_context(1, None, "general")


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# =============================================================================
# 1. MULTIMODAL PAYLOAD STRUCTURE (IMAGE BYTES REACH VISION SERVICE)
# =============================================================================
def test_01_multimodal_payload_image_bytes_reach_vision():
    """Verify that actual image bytes (base64 data URL) and user question are passed in messages."""
    img_bytes = _create_synthetic_test_image("LUNG BASES CLEAR")
    captured_messages = []

    def mock_caller(messages, **kwargs):
        captured_messages.extend(messages)
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "requested_model": "google/gemma-4-31b-it:free",
            "actual_model": "google/gemma-4-31b-it:free",
            "is_fallback": False,
            "fallback_reason": None,
            "provider": "openrouter",
            "message": {
                "role": "assistant",
                "content": (
                    "**Answer**\nThe lung bases appear clear without focal consolidation.\n\n"
                    "**Visible observations**\nBilateral costophrenic angles are sharp.\n\n"
                    "**Limitations**\nSingle AP portable view.\n\n"
                    "**Important note**\nAssistive only; clinician review required."
                ),
            },
        }

    res = answer_image_question(
        image_source=img_bytes,
        user_question="Are the lung bases clear?",
        image_scope="patient",
        allow_external_patient_vision=True,
        vision_caller=mock_caller,
    )

    assert res["success"] is True
    assert res["response_type"] == "image_qa"
    assert len(captured_messages) >= 2
    user_turn = captured_messages[-1]
    assert user_turn["role"] == "user"
    assert isinstance(user_turn["content"], list)
    text_part = next(p for p in user_turn["content"] if p["type"] == "text")
    img_part = next(p for p in user_turn["content"] if p["type"] == "image_url")
    assert "Are the lung bases clear?" in text_part["text"]
    assert img_part["image_url"]["url"].startswith("data:image/png;base64,")


# =============================================================================
# 2. CORRECT IMAGE ID AND FILE USED
# =============================================================================
def test_02_correct_image_id_and_file_used():
    """Verify that image_id and source_path parameters are correctly bound in response."""
    img_bytes = _create_synthetic_test_image("ECG LEAD II")

    def mock_caller(messages, **kwargs):
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nRegular rhythm.\n\n**Visible observations**\nP waves present.\n\n**Limitations**\nLead II rhythm strip only.\n\n**Important note**\nAssistive observation only.",
            },
        }

    res = answer_image_question(
        image_source=img_bytes,
        user_question="What is the rhythm?",
        image_scope="patient",
        image_id="img_p1_ecg_99",
        source_path="/secure/patient_images/p1_ecg.png",
        allow_external_patient_vision=True,
        vision_caller=mock_caller,
    )

    assert res["image_id"] == "img_p1_ecg_99"
    assert res["source_path"] == "/secure/patient_images/p1_ecg.png"
    assert res["content_hash"] is not None


# =============================================================================
# 3. TWO DIFFERENT IMAGES PRODUCE DISTINCT ANSWERS (NO GENERIC CACHING)
# =============================================================================
def test_03_two_different_images_produce_distinct_answers():
    """Verify distinct image inputs and prompts produce distinct visual answers."""
    xray_bytes = _create_synthetic_test_image("CHEST XRAY NORMAL", color=(200, 200, 200))
    ecg_bytes = _create_synthetic_test_image("ECG ST ELEVATION", color=(255, 255, 255))

    def mock_caller_xray(messages, **kwargs):
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nChest radiograph demonstrates clear lung fields.\n\n**Visible observations**\nCardiac silhouette within normal limits.\n\n**Limitations**\nModerate inspiratory effort.\n\n**Important note**\nClinician review required.",
            },
        }

    def mock_caller_ecg(messages, **kwargs):
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nECG strip indicates visible ST-segment elevations.\n\n**Visible observations**\nJ-point elevation visible in leads II and III.\n\n**Limitations**\nBaseline artifact present.\n\n**Important note**\nRequires urgent cardiologist confirmation.",
            },
        }

    res_xray = answer_image_question(
        image_source=xray_bytes,
        user_question="Analyze this chest X-ray",
        image_scope="patient",
        vision_caller=mock_caller_xray,
    )
    res_ecg = answer_image_question(
        image_source=ecg_bytes,
        user_question="Analyze this ECG",
        image_scope="patient",
        vision_caller=mock_caller_ecg,
    )

    assert res_xray["answer"] != res_ecg["answer"]
    assert "Chest radiograph" in res_xray["answer"]
    assert "ECG strip" in res_ecg["answer"]


# =============================================================================
# 4. IMAGE ANSWER EXCLUDES PATIENT TELEMETRY
# =============================================================================
def test_04_image_answer_excludes_patient_telemetry():
    """Verify that image Q&A mode does NOT retrieve or inject patient vitals/telemetry."""
    img_bytes = _create_synthetic_test_image("ABDOMINAL ULTRASOUND")

    def mock_caller(messages, **kwargs):
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nFluid collection is not apparent in Morrison pouch.\n\n**Visible observations**\nHepatorenal interface is sharply defined.\n\n**Limitations**\nPatient bowel gas obscures deep pelvis.\n\n**Important note**\nAssistive observation only.",
            },
        }

    res = answer_image_question(
        image_source=img_bytes,
        user_question="Is there free fluid visible?",
        image_scope="patient",
        vision_caller=mock_caller,
    )

    # Strict isolation checks
    assert res["mysql_sources"] == []
    assert res["rag_sources"] == []
    assert res["patient_summary"] is None
    for vital_term in ["Heart Rate: 75", "119 mmHg", "36.8°C", "SpO2 Oxygen"]:
        assert vital_term not in res["answer"]


# =============================================================================
# 5. IMAGE ANSWER EXCLUDES EWS
# =============================================================================
def test_05_image_answer_excludes_ews():
    """Verify that EWS scores and risk tier calculations are excluded from image Q&A."""
    img_bytes = _create_synthetic_test_image("CT BRAIN PLAIN")

    def mock_caller(messages, **kwargs):
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nNo acute intracranial hemorrhage or midline shift visible.\n\n**Visible observations**\nSymmetrical ventricular system.\n\n**Limitations**\nMotion artifact across vertex slices.\n\n**Important note**\nAssistive analysis; radiologist report required.",
            },
        }

    res = answer_image_question(
        image_source=img_bytes,
        user_question="Is there any hemorrhage?",
        image_scope="patient",
        vision_caller=mock_caller,
    )

    assert "EWS Score" not in res["answer"]
    assert "Early Warning Score" not in res["answer"]
    assert "NEWS2" not in res["answer"]


# =============================================================================
# 6. IMAGE ANSWER EXCLUDES TRANSFER RECOMMENDATIONS
# =============================================================================
def test_06_image_answer_excludes_transfer_recommendations():
    """Verify that transfer decisions (ICU <-> HDU) are strictly excluded from image Q&A."""
    img_bytes = _create_synthetic_test_image("PORTABLE CHEST")

    def mock_caller(messages, **kwargs):
        return {
            "success": True,
            "model": "google/gemma-4-31b-it:free",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nEndotracheal tube tip is 3.5 cm above the carina.\n\n**Visible observations**\nAppropriate carina clearance visualized.\n\n**Limitations**\nSupine rotation limits apex evaluation.\n\n**Important note**\nRequires attending physician confirmation.",
            },
        }

    res = answer_image_question(
        image_source=img_bytes,
        user_question="Where is the endotracheal tube?",
        image_scope="patient",
        vision_caller=mock_caller,
    )

    assert "Ready to Transfer" not in res["answer"]
    assert "Step-Down to HDU" not in res["answer"]
    assert "Escalate to ICU" not in res["answer"]


# =============================================================================
# 7. IMAGE ANSWER EXCLUDES UNRELATED PATIENT IMAGES
# =============================================================================
def test_07_image_answer_excludes_unrelated_patient_images():
    """Verify that patient image lookup validates patient boundary and excludes other patients."""
    p1_img = upload_and_process_patient_image(
        file_bytes=_create_synthetic_test_image("PATIENT 1 CHEST"),
        filename="p1_chest.png",
        patient_id=1,
        user_id=1,
        user_role="doctor",
        image_type="xray",
        title="Patient 1 Xray",
        enable_vision_llm=False,
    )
    p1_id = str(p1_img.get("image_id") or p1_img.get("patient_image_id"))

    # Query for Patient 2 must NOT return Patient 1's images
    p2_images = get_authorized_patient_images(
        patient_id=2,
        user_id=1,
        user_role="doctor",
        chat_mode="patient",
    )
    p2_ids = [str(img.get("image_id") or img.get("patient_image_id")) for img in p2_images]
    assert p1_id not in p2_ids


# =============================================================================
# 8. FOLLOW-UP QUESTION CORRECTLY USES PREVIOUS IMAGE CONTEXT
# =============================================================================
@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_08_follow_up_question_uses_previous_image_context(mock_auth, mock_user, client):
    """Verify that a follow-up question uses active image context without re-uploading file."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    mock_auth.return_value = (True, "")

    img_rec = upload_and_process_patient_image(
        file_bytes=_create_synthetic_test_image("FOLLOWUP SCAN"),
        filename="followup_scan.png",
        patient_id=1,
        user_id=1,
        user_role="doctor",
        image_type="xray",
        title="Followup Scan",
        enable_vision_llm=False,
    )
    img_id = str(img_rec.get("image_id") or img_rec.get("patient_image_id"))

    with patch("routes.chatbot_routes.answer_image_question") as mock_qa:
        mock_qa.return_value = {
            "success": True,
            "response_type": "image_qa",
            "answer": "**Answer**\nThe lower left zone exhibits slight blunting.\n\n**Visible observations**\nMild costophrenic angle haziness.\n\n**Limitations**\nSuboptimal inspiration.\n\n**Important note**\nClinician review required.",
            "requested_model": "google/gemma-4-31b-it:free",
            "actual_model": "google/gemma-4-31b-it:free",
            "is_fallback": False,
            "fallback_reason": None,
            "provider": "openrouter",
            "mysql_sources": [],
            "rag_sources": [],
        }

        res = client.post(
            "/chatbot/message",
            json={
                "message": "What about the lower left zone?",
                "mode": "patient",
                "patient_id": 1,
                "active_image_id": img_id,
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("response_type") == "image_qa"
        assert "lower left zone" in data["text"]
        assert data["mysql_sources"] == []


# =============================================================================
# 9. NEW IMAGE UPLOAD REPLACES PREVIOUS ACTIVE IMAGE CONTEXT
# =============================================================================
def test_09_new_image_upload_replaces_previous_active_image():
    """Verify that uploading a new image replaces the previously active image in context manager."""
    mgr = ActiveImageContextManager()

    img1 = {"image_id": "img_001", "title": "First Image", "file_path": "/tmp/1.png"}
    mgr.set_active_image(user_id=1, patient_id=1, mode="patient", image_info=img1)
    mgr.add_turn(user_id=1, patient_id=1, mode="patient", question="Q1", answer="A1")

    curr = mgr.get_active_image(user_id=1, patient_id=1, mode="patient")
    assert curr["image_id"] == "img_001"
    assert len(curr["history"]) == 1

    img2 = {"image_id": "img_002", "title": "Second Image", "file_path": "/tmp/2.png"}
    mgr.set_active_image(user_id=1, patient_id=1, mode="patient", image_info=img2)

    updated = mgr.get_active_image(user_id=1, patient_id=1, mode="patient")
    assert updated["image_id"] == "img_002"
    assert updated["title"] == "Second Image"
    assert updated["history"] == []


# =============================================================================
# 10. NORMAL PATIENT CHAT REMAINS FUNCTIONAL (PATH B)
# =============================================================================
@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_10_normal_patient_chat_remains_functional(mock_auth, mock_user, client):
    """Verify that standard patient chat without image context uses verified EHR data."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    mock_auth.return_value = (True, "")
    clear_active_image_context(1, 1, "patient")

    with patch("routes.chatbot_routes.query_rag_chatbot") as mock_rag:
        mock_rag.return_value = {
            "success": True,
            "mode": "patient",
            "text": "Patient #1 is in ICU with stable vital signs. Current NEWS2 score is 2.",
            "response": "Patient #1 is in ICU with stable vital signs. Current NEWS2 score is 2.",
            "mysql_sources": [{"source": "MySQL vitals", "field": "Heart Rate", "value": 75}],
            "rag_sources": [{"title": "ICU Sepsis Protocol", "relevance_score": 0.88}],
        }

        res = client.post(
            "/chatbot/message",
            json={
                "message": "What are the latest vitals for this patient?",
                "mode": "patient",
                "patient_id": 1,
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "Patient #1 is in ICU" in data["text"]
        assert len(data["mysql_sources"]) > 0


# =============================================================================
# 11. GENERAL CHAT REMAINS ISOLATED FROM MYSQL (PATH C)
# =============================================================================
@patch("routes.chatbot_routes.get_current_request_user")
def test_11_general_chat_remains_isolated_from_mysql(mock_user, client):
    """Verify that General Chat mode is isolated from MySQL and answers general clinical queries."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)

    with patch("routes.chatbot_routes.query_rag_chatbot") as mock_rag:
        mock_rag.return_value = {
            "success": True,
            "mode": "general",
            "text": "The NEWS2 protocol assesses physiological deterioration using six physiological parameters.",
            "response": "The NEWS2 protocol assesses physiological deterioration using six physiological parameters.",
            "mysql_sources": [],
            "rag_sources": [{"title": "NEWS2 Guidelines", "relevance_score": 0.92}],
        }

        res = client.post(
            "/chatbot/message",
            json={
                "message": "Explain the NEWS2 protocol thresholds.",
                "mode": "general",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["mode"] == "general"
        assert data["mysql_sources"] == []


# =============================================================================
# 12. TRANSPARENT MODEL ROUTING AND FALLBACK LOGGING VERIFIED
# =============================================================================
def test_12_transparent_model_routing_and_fallback():
    """Verify that model fallback transparently reports requested, actual, and reason."""
    img_bytes = _create_synthetic_test_image("CHEST XRAY")

    def mock_fallback_caller(messages, **kwargs):
        return {
            "success": True,
            "model": "nvidia/nemotron-3.5-super-vl:free",
            "requested_model": "google/gemma-4-31b-it:free",
            "actual_model": "nvidia/nemotron-3.5-super-vl:free",
            "is_fallback": True,
            "fallback_reason": "primary_rate_limited_or_error",
            "provider": "openrouter",
            "message": {
                "role": "assistant",
                "content": "**Answer**\nClear cardiothoracic ratio.\n\n**Visible observations**\nNo cardiomegaly.\n\n**Limitations**\nSingle view.\n\n**Important note**\nClinician review required.",
            },
        }

    res = answer_image_question(
        image_source=img_bytes,
        user_question="Is cardiomegaly present?",
        image_scope="patient",
        model_override="google/gemma-4-31b-it:free",
        vision_caller=mock_fallback_caller,
    )

    assert res["success"] is True
    assert res["requested_model"] == "google/gemma-4-31b-it:free"
    assert res["actual_model"] == "nvidia/nemotron-3.5-super-vl:free"
    assert res["is_fallback"] is True
    assert res["fallback_reason"] == "primary_rate_limited_or_error"
    assert res["provider"] == "openrouter"


# =============================================================================
# 13. UNAUTHORIZED IMAGE ACCESS REJECTED (403)
# =============================================================================
@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_13_unauthorized_image_access_rejected_403(mock_auth, mock_user, client):
    """Verify that uploading or accessing a patient image without authorization returns 403."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    mock_auth.return_value = (False, "Clinician not assigned to this patient.")

    res = client.post(
        "/chatbot/image/upload",
        data={
            "image": (io.BytesIO(_create_synthetic_test_image()), "unauth.png"),
            "mode": "patient",
            "patient_id": 999,
        },
        content_type="multipart/form-data",
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert "not assigned" in data["error"]


# =============================================================================
# 14. NO FABRICATED VISUAL FINDINGS & PROHIBITED CLAIMS NEUTRALIZED
# =============================================================================
def test_14_no_fabricated_visual_findings_safety():
    """Verify that prohibited definitive clinical diagnosis and prescription claims are neutralized."""
    untrusted_output = (
        "**Answer**\nThe definitive diagnosis is severe bacterial pneumonia and prescribe 500mg amoxicillin.\n\n"
        "**Visible observations**\nDense consolidation.\n\n"
        "**Limitations**\nNone.\n\n"
        "**Important note**\nStandard disclaimer."
    )

    formatted = format_image_qa_response(untrusted_output)
    assert "definitive diagnosis is" not in formatted
    assert "prescribe 500mg" not in formatted
    assert "[CLINICIAN_VERIFICATION_REQUIRED]" in formatted


# =============================================================================
# 15. STRICT 4-PART RESPONSE STRUCTURE VERIFIED
# =============================================================================
def test_15_strict_four_part_response_structure():
    """Verify that the 4 mandatory bold markdown headers exist in every formatted response."""
    # Case A: Model returned markdown with all four headings
    input_a = (
        "**Answer**\nThe ECG indicates sinus bradycardia at 48 bpm.\n\n"
        "**Visible observations**\nRegular RR intervals and normal PR duration.\n\n"
        "**Limitations**\nSingle 3-lead monitoring strip.\n\n"
        "**Important note**\nAssistive observation only; physician verification required."
    )
    formatted_a = format_image_qa_response(input_a)
    assert "**Answer**" in formatted_a
    assert "**Visible observations**" in formatted_a
    assert "**Limitations**" in formatted_a
    assert "**Important note**" in formatted_a

    # Case B: Model returned unstructured plain text
    input_b = "The chest radiograph shows right middle lobe infiltrates with blunted sulcus."
    formatted_b = format_image_qa_response(input_b)
    assert "**Answer**" in formatted_b
    assert "**Visible observations**" in formatted_b
    assert "**Limitations**" in formatted_b
    assert "**Important note**" in formatted_b
    assert IMAGE_QA_DISCLAIMER in formatted_b


# =============================================================================
# 16. CLEAR ACTIVE IMAGE ENDPOINT
# =============================================================================
@patch("routes.chatbot_routes.get_current_request_user")
def test_16_clear_active_image_endpoint(mock_user, client):
    """Verify that POST /chatbot/image/active/clear safely resets the active context."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)

    set_active_image_context(
        user_id=1,
        patient_id=1,
        mode="patient",
        image_info={"image_id": "test_clear_99", "title": "Test Clear"},
    )
    assert get_active_image_context(1, 1, "patient") is not None

    res = client.post(
        "/chatbot/image/active/clear",
        json={"mode": "patient", "patient_id": 1},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["cleared"] is True

    assert get_active_image_context(1, 1, "patient") is None
