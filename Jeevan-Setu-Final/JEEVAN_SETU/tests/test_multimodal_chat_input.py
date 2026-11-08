"""
tests/test_multimodal_chat_input.py

Comprehensive Pytest Suite for Jeevan Setu Upgraded Multimodal Chat Input,
Image Upload, Clipboard Paste, Ctrl+V, Preview, and File Streaming.

Covers:
1. Exception hierarchy: ImageValidationError (ValueError) and ImageAuthorizationError (PermissionError).
2. Parameter aliases in `upload_and_process_patient_image` (file_bytes, filename, enable_vision_llm).
3. Secure image_url generation (/chatbot/image/<id>/view).
4. RBAC authorization & patient isolation enforcement.
5. General Chat image processing (process_general_chat_image) with complete patient isolation.
6. Flask REST API: POST /chatbot/image/upload (Patient mode & General mode).
7. Flask REST API: GET /chatbot/image/<image_id>/view (RBAC streaming & general streaming).
8. Flask REST API: POST /chatbot/message (Multipart delegation for text + image).
"""

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from chatbot.vision.image_processor import (
    DEFAULT_PATIENT_IMAGE_STORAGE_DIR,
    DEFAULT_GENERAL_IMAGE_STORAGE_DIR,
    ImageAuthorizationError,
    ImageValidationError,
    get_authorized_patient_image_file,
    get_general_chat_image_file,
    process_general_chat_image,
    reset_fallback_patient_image_store,
    upload_and_process_patient_image,
)


def _create_synthetic_image(text: str = "CLINICAL CHART", size=(200, 100), fmt="PNG") -> bytes:
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 35), text, fill="black", font_size=18)
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
# 1. EXCEPTION HIERARCHY TESTS
# =============================================================================

def test_exception_subclass_hierarchy():
    """Ensure custom exceptions preserve backward compatibility with ValueError & PermissionError."""
    val_err = ImageValidationError("Corrupt image header")
    assert isinstance(val_err, ValueError)
    assert isinstance(val_err, ImageValidationError)

    auth_err = ImageAuthorizationError("Patient access denied")
    assert isinstance(auth_err, PermissionError)
    assert isinstance(auth_err, ImageAuthorizationError)


# =============================================================================
# 2. PARAMETER ALIASES & DIRECT PROCESSOR TESTS
# =============================================================================

def test_upload_and_process_patient_image_aliases_and_image_url(tmp_path: Path):
    """Test that file_bytes, filename, and enable_vision_llm parameter aliases work."""
    img_bytes = _create_synthetic_image("ECG LEAD II")
    storage = tmp_path / "patient_images"

    record = upload_and_process_patient_image(
        patient_id=101,
        user_id=1,
        user_role="doctor",
        file_bytes=img_bytes,
        filename="bedside_ecg.png",
        image_type="ecg",
        title="Bedside ECG",
        chat_mode="patient",
        enable_vision_llm=True,
        storage_dir=storage,
        authorization_fn=lambda u, p: (True, ""),
    )

    assert record["patient_id"] == 101
    assert record["image_type"] == "ecg"
    assert "image_url" in record
    assert record["image_url"] == f"/chatbot/image/{record['patient_image_id']}/view"
    assert record["shared_chromadb_indexed"] is False
    assert Path(record["absolute_file_path"]).exists()


def test_upload_patient_image_blocked_in_general_chat():
    """upload_and_process_patient_image must raise ImageAuthorizationError if mode is general."""
    img_bytes = _create_synthetic_image("TEST")
    with pytest.raises(ImageAuthorizationError, match="General Chat mode"):
        upload_and_process_patient_image(
            patient_id=101,
            user_id=1,
            user_role="doctor",
            file_bytes=img_bytes,
            filename="test.png",
            chat_mode="general",
            authorization_fn=lambda u, p: (True, ""),
        )


def test_upload_patient_image_unauthorized_user():
    """upload_and_process_patient_image must raise ImageAuthorizationError if authorization fails."""
    img_bytes = _create_synthetic_image("TEST")
    with pytest.raises(ImageAuthorizationError, match="Unauthorized"):
        upload_and_process_patient_image(
            patient_id=999,
            user_id=1,
            user_role="doctor",
            file_bytes=img_bytes,
            filename="test.png",
            chat_mode="patient",
            authorization_fn=lambda u, p: (False, "Unauthorized clinician"),
        )


def test_upload_patient_image_invalid_bytes():
    """upload_and_process_patient_image must raise ImageValidationError on corrupt/empty data."""
    with pytest.raises(ImageValidationError):
        upload_and_process_patient_image(
            patient_id=101,
            user_id=1,
            user_role="doctor",
            file_bytes=b"NOT_AN_IMAGE_FILE",
            filename="corrupt.png",
            chat_mode="patient",
            authorization_fn=lambda u, p: (True, ""),
        )


# =============================================================================
# 3. GENERAL CHAT IMAGE PROCESSING TESTS
# =============================================================================

def test_process_general_chat_image_isolation(tmp_path: Path):
    """process_general_chat_image must process reference images without touching patient tables."""
    img_bytes = _create_synthetic_image("ICU PROTOCOL FLOWCHART")
    storage = tmp_path / "general_images"

    record = process_general_chat_image(
        file_bytes=img_bytes,
        filename="protocol_stepdown.png",
        title="ICU Protocol Chart",
        chat_mode="general",
        storage_dir=storage,
    )

    assert record["is_patient_data"] is False
    assert record["patient_id"] is None
    assert record["patient_image_id"] is None
    assert record["chat_mode"] == "general"
    assert record["image_id"].startswith("gen_")
    assert record["image_url"] == f"/chatbot/image/{record['image_id']}/view"
    assert Path(record["absolute_file_path"]).exists()

    # Retrieve through get_general_chat_image_file
    retrieved = get_general_chat_image_file(record["image_id"], storage_dir=storage)
    assert retrieved == Path(record["absolute_file_path"])


# =============================================================================
# 4. FLASK ENDPOINT TESTS: POST /chatbot/image/upload
# =============================================================================

@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_endpoint_upload_patient_image_success(mock_auth, mock_user, client):
    """POST /chatbot/image/upload in patient mode returns 200 with image_url and structured bot briefing."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    mock_auth.return_value = (True, "")

    img_bytes = _create_synthetic_image("VITALS MONITOR")
    data = {
        "mode": "patient",
        "patient_id": "1",
        "title": "Bedside Monitor",
        "image_type": "monitor_snapshot",
        "image": (io.BytesIO(img_bytes), "monitor.png"),
        "message": "Is this heart rate stable?",
    }

    res = client.post("/chatbot/image/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert json_data["mode"] == "patient"
    assert json_data["patient_id"] == 1
    assert "image" in json_data
    assert "image_url" in json_data
    assert "/chatbot/image/" in json_data["image_url"]


@patch("routes.chatbot_routes.get_current_request_user")
def test_endpoint_upload_general_image_success(mock_user, client):
    """POST /chatbot/image/upload in general mode returns 200 without patient ID."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)

    img_bytes = _create_synthetic_image("HDU CRITERIA")
    data = {
        "mode": "general",
        "title": "HDU Criteria Reference",
        "image": (io.BytesIO(img_bytes), "hdu_chart.png"),
    }

    res = client.post("/chatbot/image/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert json_data["mode"] == "general"
    assert json_data["patient_id"] is None
    assert json_data["image"]["is_patient_data"] is False
    assert "/chatbot/image/gen_" in json_data["image_url"]


@patch("routes.chatbot_routes.get_current_request_user")
def test_endpoint_upload_missing_file(mock_user, client):
    """POST /chatbot/image/upload with no file attached returns 400."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    res = client.post("/chatbot/image/upload", data={"mode": "general"}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "No image file provided" in res.get_json()["error"]


@patch("routes.chatbot_routes.get_current_request_user")
def test_endpoint_upload_patient_mode_missing_patient_id(mock_user, client):
    """POST /chatbot/image/upload in patient mode without patient_id returns 400."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    img_bytes = _create_synthetic_image("ECG")
    res = client.post(
        "/chatbot/image/upload",
        data={"mode": "patient", "image": (io.BytesIO(img_bytes), "ecg.png")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "patient_id is required" in res.get_json()["error"]


@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_endpoint_upload_patient_mode_unauthorized_patient(mock_auth, mock_user, client):
    """POST /chatbot/image/upload for unauthorized patient returns 403."""
    mock_user.return_value = MagicMock(id=2, role="nurse", is_authenticated=True)
    mock_auth.return_value = (False, "Patient access restricted")

    img_bytes = _create_synthetic_image("ECG")
    res = client.post(
        "/chatbot/image/upload",
        data={"mode": "patient", "patient_id": "999", "image": (io.BytesIO(img_bytes), "ecg.png")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 403
    assert "access restricted" in res.get_json()["error"].lower()


# =============================================================================
# 5. FLASK ENDPOINT TESTS: GET /chatbot/image/<image_id>/view
# =============================================================================

@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_endpoint_view_authorized_patient_image(mock_auth, mock_user, client, tmp_path: Path):
    """GET /chatbot/image/<id>/view streams authorized patient image file."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    mock_auth.return_value = (True, "")

    img_bytes = _create_synthetic_image("LAB RESULTS")
    record = upload_and_process_patient_image(
        patient_id=1,
        user_id=1,
        user_role="doctor",
        file_bytes=img_bytes,
        filename="lab.png",
        authorization_fn=lambda u, p: (True, ""),
    )
    img_id = record["patient_image_id"]

    res = client.get(f"/chatbot/image/{img_id}/view")
    assert res.status_code == 200
    assert res.content_type.startswith("image/")
    assert len(res.data) > 0


@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_endpoint_view_unauthorized_patient_image_blocked(mock_auth, mock_user, client):
    """GET /chatbot/image/<id>/view returns 403 when user is not authorized for patient."""
    mock_user.return_value = MagicMock(id=5, role="nurse", is_authenticated=True)
    # Upload image for patient 10
    img_bytes = _create_synthetic_image("PRIVATE XRAY")
    record = upload_and_process_patient_image(
        patient_id=10,
        user_id=1,
        user_role="doctor",
        file_bytes=img_bytes,
        filename="xray.png",
        authorization_fn=lambda u, p: (True, ""),
    )
    img_id = record["patient_image_id"]

    # Now simulate nurse #5 has no access to patient #10
    mock_auth.return_value = (False, "Forbidden")
    res = client.get(f"/chatbot/image/{img_id}/view")
    assert res.status_code == 403


@patch("routes.chatbot_routes.get_current_request_user")
def test_endpoint_view_general_chat_image(mock_user, client):
    """GET /chatbot/image/<gen_id>/view streams general chat reference image."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)

    img_bytes = _create_synthetic_image("REFERENCE GUIDE")
    rec = process_general_chat_image(file_bytes=img_bytes, filename="guide.png")
    gen_id = rec["image_id"]

    res = client.get(f"/chatbot/image/{gen_id}/view")
    assert res.status_code == 200
    assert res.content_type.startswith("image/")


# =============================================================================
# 6. FLASK ENDPOINT TESTS: POST /chatbot/message WITH MULTIPART ATTACHMENT
# =============================================================================

@patch("routes.chatbot_routes.get_current_request_user")
@patch("routes.chatbot_routes.verify_user_patient_access")
def test_endpoint_message_multipart_image_delegation(mock_auth, mock_user, client):
    """POST /chatbot/message with multipart image attachment automatically delegates to upload endpoint."""
    mock_user.return_value = MagicMock(id=1, role="doctor", is_authenticated=True)
    mock_auth.return_value = (True, "")

    img_bytes = _create_synthetic_image("TELEMETRY")
    data = {
        "mode": "patient",
        "patient_id": "1",
        "message": "Analyze this rhythm strip",
        "image": (io.BytesIO(img_bytes), "strip.png"),
    }

    res = client.post("/chatbot/message", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert "image_url" in json_data

