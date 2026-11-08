"""
tests/test_patient_image_security.py

Pytest suite for Jeevan Setu Patient-Specific Clinical Image Security & Isolation
(`chatbot/vision/image_processor.py`).

Tests:
1. Authorized doctor/nurse can upload and retrieve patient-specific images.
2. Patient images are stored in isolated patient storage outside `knowledge_base/`
   and are NEVER indexed into the shared ChromaDB collection.
3. General Chat (`chat_mode='general'`) is strictly blocked from uploading or
   retrieving patient-specific image data.
4. Unauthorized users (wrong doctor, wrong nurse, attendant) are rejected.
5. Role-based `access_level` enforcement (`doctor_only` hidden from `nurse`).
6. External OpenRouter vision transmission is disabled by default for patient images.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image, ImageDraw
import pytest

from chatbot.rag.document_loader import KNOWLEDGE_BASE_DIR
from chatbot.vision.image_processor import (
    get_authorized_patient_image_file,
    get_authorized_patient_images,
    reset_fallback_patient_image_store,
    upload_and_process_patient_image,
)


def _make_synthetic_ecg_bytes() -> bytes:
    img = Image.new("RGB", (360, 140), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 45), "SYNTHETIC ECG HR 78 BPM", fill="black", font_size=22)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clean_fallback_store():
    reset_fallback_patient_image_store()
    yield
    reset_fallback_patient_image_store()


def test_01_authorized_patient_image_upload_and_isolation(tmp_path: Path):
    vision_spy = MagicMock()
    patient_storage = tmp_path / "secure_patient_images"

    rec = upload_and_process_patient_image(
        patient_id=801,
        user_id=10,
        user_role="doctor",
        image_source=_make_synthetic_ecg_bytes(),
        title="Synthetic Bedside ECG Strip",
        image_type="ecg",
        clinical_context="Routine post-op telemetry check",
        access_level="clinical_staff",
        chat_mode="patient",
        storage_dir=patient_storage,
        authorization_fn=lambda u, pid: (True, ""),
        vision_caller=vision_spy,
    )

    assert rec["patient_id"] == 801
    assert rec["image_type"] == "ecg"
    assert rec["shared_chromadb_indexed"] is False
    assert rec["ocr_status"] == "completed"
    # External vision MUST be skipped by default for patient images
    assert rec["vision_status"] == "skipped_privacy_policy"
    vision_spy.assert_not_called()

    saved_file = Path(rec["absolute_file_path"])
    assert saved_file.exists()
    assert not saved_file.resolve().is_relative_to(KNOWLEDGE_BASE_DIR.resolve())

    # Retrieve via `get_authorized_patient_images` and `get_authorized_patient_image_file`
    imgs = get_authorized_patient_images(
        patient_id=801,
        user_id=10,
        user_role="doctor",
        chat_mode="patient",
        authorization_fn=lambda u, pid: (True, ""),
    )
    assert len(imgs) == 1
    assert imgs[0]["patient_image_id"] == rec["patient_image_id"]

    file_path = get_authorized_patient_image_file(
        patient_image_id=rec["patient_image_id"],
        patient_id=801,
        user_id=10,
        user_role="doctor",
        chat_mode="patient",
        storage_dir=patient_storage,
        authorization_fn=lambda u, pid: (True, ""),
    )
    assert file_path == saved_file.resolve()


def test_02_general_chat_cannot_upload_or_retrieve_patient_images(tmp_path: Path):
    with pytest.raises(PermissionError, match="General Chat mode"):
        upload_and_process_patient_image(
            patient_id=801,
            user_id=10,
            user_role="doctor",
            image_source=_make_synthetic_ecg_bytes(),
            title="Blocked Upload",
            chat_mode="general",
            storage_dir=tmp_path / "secure_patient_images",
            authorization_fn=lambda u, pid: (True, ""),
        )

    with pytest.raises(PermissionError, match="General Chat mode"):
        get_authorized_patient_images(
            patient_id=801,
            user_id=10,
            user_role="doctor",
            chat_mode="general",
            authorization_fn=lambda u, pid: (True, ""),
        )


def test_03_unauthorized_user_and_access_level_restrictions(tmp_path: Path):
    patient_storage = tmp_path / "secure_patient_images"

    # 1. Unauthorized doctor rejected on upload
    with pytest.raises(PermissionError, match="Access forbidden"):
        upload_and_process_patient_image(
            patient_id=801,
            user_id=99,
            user_role="doctor",
            image_source=_make_synthetic_ecg_bytes(),
            title="Unauthorized Upload",
            chat_mode="patient",
            storage_dir=patient_storage,
            authorization_fn=lambda u, pid: (False, "Access forbidden: not assigned doctor."),
        )

    # 2. Attendant rejected on upload
    with pytest.raises(PermissionError, match="not authorized to upload"):
        upload_and_process_patient_image(
            patient_id=801,
            user_id=50,
            user_role="attendant",
            image_source=_make_synthetic_ecg_bytes(),
            title="Attendant Upload",
            chat_mode="patient",
            storage_dir=patient_storage,
            authorization_fn=lambda u, pid: (True, ""),
        )

    # 3. Upload a `doctor_only` image and verify Nurse cannot view it
    doc_only_rec = upload_and_process_patient_image(
        patient_id=801,
        user_id=10,
        user_role="doctor",
        image_source=_make_synthetic_ecg_bytes(),
        title="Doctor-Only CT Review",
        image_type="ct_scan",
        access_level="doctor_only",
        chat_mode="patient",
        storage_dir=patient_storage,
        authorization_fn=lambda u, pid: (True, ""),
    )

    nurse_imgs = get_authorized_patient_images(
        patient_id=801,
        user_id=20,
        user_role="nurse",
        chat_mode="patient",
        authorization_fn=lambda u, pid: (True, ""),
    )
    assert nurse_imgs == []

    with pytest.raises(PermissionError, match="Access denied"):
        get_authorized_patient_image_file(
            patient_image_id=doc_only_rec["patient_image_id"],
            patient_id=801,
            user_id=20,
            user_role="nurse",
            chat_mode="patient",
            storage_dir=patient_storage,
            authorization_fn=lambda u, pid: (True, ""),
        )


def test_04_cannot_store_patient_images_inside_shared_knowledge_base():
    with pytest.raises(PermissionError, match="never be stored inside the shared knowledge_base"):
        upload_and_process_patient_image(
            patient_id=801,
            user_id=10,
            user_role="doctor",
            image_source=_make_synthetic_ecg_bytes(),
            title="Invalid Storage Path",
            chat_mode="patient",
            storage_dir=KNOWLEDGE_BASE_DIR / "hospital_sops",
            authorization_fn=lambda u, pid: (True, ""),
        )

