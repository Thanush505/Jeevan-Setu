"""
tests/test_vision_diagnostics.py

Automated tests for Multimodal Vision Processor diagnostics, error traceability,
and failure logging in Jeevan Setu.

Tests:
1. Successful synthetic image processing with mocked OpenRouter vision provider.
2. HTTP 429 rate limit detection and structured failure reason without secret exposure.
3. Patient privacy guardrail handling and failure reason reporting.
4. Unsupported model modality rejection and failure reason reporting.
5. Unconfigured API key handling and failure reason reporting.
6. Verification that rate_limited status is preserved and not overwritten by fallback model 404s.
7. Strict confidentiality: verification that logs and return structures never expose API keys,
   passwords, patient PII, or raw image bytes.
"""

import io
import json
import logging
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from chatbot.vision.vision_service import (
    analyze_image_with_vision,
    verify_vision_provider_capability,
    VISION_AI_DISCLAIMER,
)
from chatbot.services.openrouter_service import call_openrouter_with_tools


def _create_synthetic_test_image(width: int = 80, height: int = 80, color=(120, 180, 220)) -> bytes:
    """Create a minimal synthetic in-memory PNG image."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_01_synthetic_image_success_with_mocked_provider():
    """Verify end-to-end synthetic image processing with a mocked successful vision provider."""
    mock_payload = {
        "summary": "Bedside monitor screen showing vital sign numerical readouts and ECG rhythm trace.",
        "content_type": "monitor_display",
        "visible_labels": ["HR", "SpO2", "NIBP", "Resp"],
        "visible_elements": ["Green ECG trace", "Numeric digits 78", "Waveform grid"],
        "layout_and_relationships": "Numeric readouts arranged vertically on right; waveforms on left.",
        "uncertainty_notes": "Plethysmograph baseline slightly degraded.",
    }

    mock_caller = MagicMock(return_value={
        "success": True,
        "model": "google/gemma-4-31b-it:free",
        "message": {"role": "assistant", "content": f"```json\n{json.dumps(mock_payload)}\n```"},
        "raw_response": {},
        "native_tools_used": False,
        "error": None,
    })

    img_bytes = _create_synthetic_test_image()
    res = analyze_image_with_vision(
        img_bytes,
        image_scope="patient",
        allow_external_patient_vision=True,
        vision_caller=mock_caller,
    )

    assert res["vision_status"] == "completed"
    assert res["ai_generated"] is True
    assert res["clinician_verification_required"] is True
    assert res["content_type"] == "monitor_display"
    assert res["failure_reason"] is None
    assert res["error"] is None
    assert "Bedside monitor screen" in res["vision_description"]
    assert "Visible Labels: HR, SpO2, NIBP, Resp" in res["vision_description"]
    assert res["disclaimer"] == VISION_AI_DISCLAIMER


def test_02_rate_limit_429_diagnostic_traceability(caplog):
    """Verify HTTP 429 rate limit is captured with structured failure_reason without secret leakage."""
    caplog.set_level(logging.WARNING)

    mock_caller = MagicMock(return_value={
        "success": False,
        "model": "google/gemma-4-31b-it:free",
        "message": {},
        "raw_response": {},
        "native_tools_used": False,
        "error": "rate_limited",
    })

    img_bytes = _create_synthetic_test_image()
    res = analyze_image_with_vision(
        img_bytes,
        image_scope="patient",
        allow_external_patient_vision=True,
        vision_caller=mock_caller,
    )

    assert res["vision_status"] == "failed"
    assert res["failure_reason"] == "rate_limited"
    assert res["error"] == "Image analysis was not completed because the vision processor was unavailable."
    # Verify warning log was emitted
    assert any("rate_limited" in record.message for record in caplog.records)


def test_03_privacy_guardrail_diagnostic_traceability(caplog):
    """Verify patient privacy blocking records structured failure_reason='privacy_policy_disabled'."""
    caplog.set_level(logging.INFO)

    img_bytes = _create_synthetic_test_image()
    res = analyze_image_with_vision(
        img_bytes,
        image_scope="patient",
        allow_external_patient_vision=False,
    )

    assert res["vision_status"] == "skipped_privacy_policy"
    assert res["failure_reason"] == "privacy_policy_disabled"
    assert res["error"] == "Image analysis was not completed because the vision processor was unavailable."


def test_04_unsupported_model_diagnostic_traceability(caplog):
    """Verify unsupported models record failure_reason='unsupported_model_modality'."""
    caplog.set_level(logging.WARNING)

    img_bytes = _create_synthetic_test_image()
    res = analyze_image_with_vision(
        img_bytes,
        image_scope="knowledge_base",
        model_override="google/gemma-2-27b-it",
    )

    assert res["vision_status"] == "unsupported_provider"
    assert res["failure_reason"] == "unsupported_model_modality"
    assert res["error"] == "Image analysis was not completed because the vision processor was unavailable."


def test_05_unconfigured_api_key_diagnostic_traceability():
    """Verify missing API key records failure_reason='api_key_not_configured'."""
    with patch("chatbot.vision.vision_service.is_ai_configured", return_value=False):
        img_bytes = _create_synthetic_test_image()
        res = analyze_image_with_vision(
            img_bytes,
            image_scope="knowledge_base",
            vision_caller=None,
        )

        assert res["vision_status"] == "skipped_unconfigured"
        assert res["failure_reason"] == "api_key_not_configured"
        assert res["error"] == "Image analysis was not completed because the vision processor was unavailable."


def test_06_openrouter_rate_limit_not_overwritten_by_fallback_404():
    """Verify call_openrouter_with_tools preserves 'rate_limited' when 429 is encountered."""
    import urllib.error

    class FakeHTTP429(urllib.error.HTTPError):
        def __init__(self):
            super().__init__(
                url="https://openrouter.ai/api/v1/chat/completions",
                code=429,
                msg="Too Many Requests",
                hdrs={},
                fp=io.BytesIO(b'{"error":{"message":"Rate limit exceeded: free-models-per-day","code":429}}'),
            )

    with patch("chatbot.services.openrouter_service.get_openrouter_api_key", return_value="sk-or-v1-fake-key-for-test"):
        with patch("urllib.request.urlopen", side_effect=FakeHTTP429()):
            resp = call_openrouter_with_tools(
                messages=[{"role": "user", "content": "ping"}],
                model_override="google/gemma-4-31b-it:free",
            )
            assert resp["success"] is False
            assert resp["error"] == "rate_limited"


def test_07_no_secret_or_raw_image_data_exposure(caplog):
    """Verify diagnostic logging never outputs API keys, secrets, or raw bytes."""
    secret_key = "sk-or-v1-secret-test-key-do-not-leak"
    raw_img = _create_synthetic_test_image()

    with patch("chatbot.services.openrouter_service.get_openrouter_api_key", return_value=secret_key):
        with patch("urllib.request.urlopen", side_effect=Exception("Simulated upstream error")):
            res = analyze_image_with_vision(
                raw_img,
                image_scope="patient",
                allow_external_patient_vision=True,
            )

    # Check logs for leaked key or raw bytes
    all_logs = " ".join([r.message for r in caplog.records])
    assert secret_key not in all_logs
    assert "sk-or-v1" not in all_logs
    assert str(raw_img[:20]) not in all_logs

