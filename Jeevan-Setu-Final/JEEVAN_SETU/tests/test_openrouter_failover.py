"""
tests/test_openrouter_failover.py — Strictly Offline Unit Tests for
Primary + Secondary OpenRouter API Key Failover Controller & Config Validation.

No live OpenRouter API calls are performed; all HTTP requests are mocked.
"""

import io
import json
import logging
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chatbot.services.openrouter_service import (
    call_openrouter_with_tools,
    classify_openrouter_error,
    get_openrouter_max_retries,
    get_openrouter_model,
    get_openrouter_timeout,
    get_primary_api_key,
    get_secondary_api_key,
    is_ai_configured,
    is_failover_enabled,
    is_openrouter_enabled,
    query_openrouter_gemini,
    validate_openrouter_config,
)


FAKE_PRIMARY_KEY = "sk-or-test-primary-0000000000000000"
FAKE_SECONDARY_KEY = "sk-or-test-secondary-1111111111111111"


class _MockHTTPResponse:
    def __init__(self, status: int, body_dict: dict):
        self.status = status
        self._raw = json.dumps(body_dict).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_http_error(code: int, message: str = "provider error", headers: dict = None) -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message}}).encode("utf-8")
    return urllib.error.HTTPError(
        url="https://openrouter.ai/api/v1/chat/completions",
        code=code,
        msg=message,
        hdrs=headers or {},
        fp=io.BytesIO(body),
    )


class TestOpenRouterTwoKeyFailover(unittest.TestCase):
    def _base_env(self, **overrides):
        env = {
            "OPENROUTER_ENABLED": "true",
            "OPENROUTER_PRIMARY_API_KEY": FAKE_PRIMARY_KEY,
            "OPENROUTER_SECONDARY_API_KEY": FAKE_SECONDARY_KEY,
            "OPENROUTER_MODEL": "google/gemma-4-31b-it:free",
            "OPENROUTER_FAILOVER_ENABLED": "true",
        }
        env.update(overrides)
        return env

    # 1. Primary key succeeds
    def test_01_primary_key_succeeds(self):
        seen_auth = []

        def fake_urlopen(req, timeout=None):
            seen_auth.append(req.get_header("Authorization"))
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "Primary ok"}}]}
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Explain EWS", mode="general")

        self.assertTrue(ok)
        self.assertEqual(text, "Primary ok")
        self.assertEqual(meta["key_slot_used"], "primary")
        self.assertFalse(meta["failover_triggered"])
        self.assertEqual(seen_auth, [f"Bearer {FAKE_PRIMARY_KEY}"])

    # 2. Primary fails with temporary network error -> secondary succeeds
    def test_02_primary_network_error_secondary_succeeds(self):
        seen_auth = []

        def fake_urlopen(req, timeout=None):
            seen_auth.append(req.get_header("Authorization"))
            if len(seen_auth) == 1:
                raise urllib.error.URLError("Temporary DNS failure")
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "Secondary ok"}}]}
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Explain EWS", mode="general")

        self.assertTrue(ok)
        self.assertEqual(text, "Secondary ok")
        self.assertEqual(meta["key_slot_used"], "secondary")
        self.assertTrue(meta["failover_triggered"])
        self.assertEqual(meta["failover_reason"], "network_error")
        self.assertEqual(seen_auth, [f"Bearer {FAKE_PRIMARY_KEY}", f"Bearer {FAKE_SECONDARY_KEY}"])

    # 3. Primary timeout -> secondary succeeds
    def test_03_primary_timeout_secondary_succeeds(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.get_header("Authorization"))
            if len(calls) == 1:
                raise TimeoutError("Read timed out")
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "Recovered after timeout"}}]}
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Explain SpO2", mode="general")

        self.assertTrue(ok)
        self.assertEqual(meta["key_slot_used"], "secondary")
        self.assertEqual(meta["failover_reason"], "timeout")

    # 4. Primary 5xx server error -> secondary succeeds
    def test_04_primary_server_error_secondary_succeeds(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.get_header("Authorization"))
            if len(calls) == 1:
                raise _make_http_error(503, "Upstream unavailable")
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "Secondary 503 recovery"}}]}
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Explain BP", mode="general")

        self.assertTrue(ok)
        self.assertEqual(meta["key_slot_used"], "secondary")
        self.assertEqual(meta["failover_reason"], "server_error")

    # 5. Primary and secondary both fail
    def test_05_primary_and_secondary_both_fail(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.get_header("Authorization"))
            raise _make_http_error(502, "Bad gateway")

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Explain EWS", mode="general")

        self.assertFalse(ok)
        self.assertEqual(len(calls), 2)
        self.assertEqual(meta["key_slot_used"], "secondary")
        self.assertTrue(meta["failover_triggered"])
        self.assertEqual(meta["error"], "server_error")
        self.assertNotIn(FAKE_PRIMARY_KEY, text)
        self.assertNotIn(FAKE_SECONDARY_KEY, text)

    # 6. Primary key missing -> does NOT substitute secondary or legacy keys
    def test_06_primary_key_missing_no_substitution(self):
        env = self._base_env(
            OPENROUTER_PRIMARY_API_KEY="",
            OPENROUTER_API_KEY="sk-or-legacy-ignored",
            OPENROUTER_BACKUP_API_KEY="sk-or-backup-ignored",
        )
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(get_primary_api_key())
            with patch("urllib.request.urlopen") as mock_open:
                ok, text, meta = query_openrouter_gemini("Hello", mode="general")
                mock_open.assert_not_called()
        self.assertFalse(ok)
        self.assertEqual(meta["error"], "missing_api_key")

    # 7. Secondary key missing -> safe failure without crashing
    def test_07_secondary_key_missing(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            raise _make_http_error(503, "Service down")

        with patch.dict(os.environ, self._base_env(OPENROUTER_SECONDARY_API_KEY=""), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Hello", mode="general")

        self.assertFalse(ok)
        self.assertEqual(len(calls), 1)
        self.assertFalse(meta["failover_triggered"])
        self.assertEqual(meta["key_slot_used"], "primary")

    # 8. Both keys missing -> safe failure, no live calls
    def test_08_both_keys_missing(self):
        with patch.dict(
            os.environ,
            self._base_env(OPENROUTER_PRIMARY_API_KEY="", OPENROUTER_SECONDARY_API_KEY=""),
            clear=True,
        ):
            self.assertFalse(is_ai_configured())
            with patch("urllib.request.urlopen") as mock_open:
                ok, _, meta = query_openrouter_gemini("Hello", mode="general")
                mock_open.assert_not_called()
        self.assertFalse(ok)
        self.assertEqual(meta["error"], "missing_api_key")

    # 9. Failover disabled
    def test_09_failover_disabled(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            raise TimeoutError("Timed out")

        with patch.dict(os.environ, self._base_env(OPENROUTER_FAILOVER_ENABLED="false"), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Hello", mode="general")

        self.assertFalse(ok)
        self.assertEqual(len(calls), 1)
        self.assertFalse(meta["failover_triggered"])

    # 10. OpenRouter disabled
    def test_10_openrouter_disabled(self):
        with patch.dict(os.environ, self._base_env(OPENROUTER_ENABLED="false"), clear=True):
            self.assertFalse(is_openrouter_enabled())
            self.assertFalse(is_ai_configured())
            with patch("urllib.request.urlopen") as mock_open:
                ok, text, meta = query_openrouter_gemini("Hello", mode="general")
                res_tools = call_openrouter_with_tools([{"role": "user", "content": "hi"}])
                mock_open.assert_not_called()
        self.assertFalse(ok)
        self.assertEqual(meta["error"], "openrouter_disabled")
        self.assertFalse(res_tools["success"])
        self.assertEqual(res_tools["error"], "openrouter_disabled")

    # 11. Invalid request (400) & invalid model config -> no failover
    def test_11_invalid_request_and_invalid_model_no_failover(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.get_header("Authorization"))
            raise _make_http_error(400, "Malformed payload")

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok, text, meta = query_openrouter_gemini("Hello", mode="general")

        self.assertFalse(ok)
        self.assertEqual(len(calls), 1)
        self.assertFalse(meta["failover_triggered"])
        self.assertEqual(meta["error"], "invalid_request")

        with patch.dict(os.environ, self._base_env(OPENROUTER_MODEL="invalid model"), clear=True):
            cfg = validate_openrouter_config()
            self.assertFalse(cfg["model_valid"])
            self.assertFalse(cfg["valid"])
            with patch("urllib.request.urlopen") as mock_open:
                ok2, _, meta2 = query_openrouter_gemini("Hello", mode="general")
                mock_open.assert_not_called()
            self.assertFalse(ok2)
            self.assertEqual(meta2["error"], "invalid_model_config")

    # 12. Auth (401 vs 403) & Rate-limit (429 transient vs daily quota / Retry-After)
    def test_12_auth_and_rate_limit_policies(self):
        # 401 key-specific auth failure -> failover to secondary allowed
        auth_calls = []

        def fake_401(req, timeout=None):
            auth_calls.append(req.get_header("Authorization"))
            if len(auth_calls) == 1:
                raise _make_http_error(401, "Invalid primary key")
            return _MockHTTPResponse(200, {"choices": [{"message": {"role": "assistant", "content": "Sec auth ok"}}]})

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_401):
                ok, _, meta = query_openrouter_gemini("Hi", mode="general")
        self.assertTrue(ok)
        self.assertEqual(meta["key_slot_used"], "secondary")
        self.assertEqual(meta["failover_reason"], "auth_error")

        # 403 permission denied -> no failover
        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=_make_http_error(403, "Forbidden")):
                ok403, _, meta403 = query_openrouter_gemini("Hi", mode="general")
        self.assertFalse(ok403)
        self.assertFalse(meta403["failover_triggered"])
        self.assertEqual(meta403["error"], "permission_denied")

        # 429 account daily quota -> no failover
        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=_make_http_error(429, "free-models-per-day exceeded")):
                ok_daily, _, meta_daily = query_openrouter_gemini("Hi", mode="general")
        self.assertFalse(ok_daily)
        self.assertFalse(meta_daily["failover_triggered"])

        # 429 long Retry-After (>5s) -> no failover
        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=_make_http_error(429, "Slow down", {"Retry-After": "30"})):
                ok_ra, _, meta_ra = query_openrouter_gemini("Hi", mode="general")
        self.assertFalse(ok_ra)
        self.assertFalse(meta_ra["failover_triggered"])

        # 429 transient per-key RPM limit -> secondary failover succeeds
        rpm_calls = []

        def fake_rpm(req, timeout=None):
            rpm_calls.append(req.get_header("Authorization"))
            if len(rpm_calls) == 1:
                raise _make_http_error(429, "Per-minute rate limit")
            return _MockHTTPResponse(200, {"choices": [{"message": {"role": "assistant", "content": "RPM ok"}}]})

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_rpm):
                ok_rpm, _, meta_rpm = query_openrouter_gemini("Hi", mode="general")
        self.assertTrue(ok_rpm)
        self.assertEqual(meta_rpm["key_slot_used"], "secondary")

    # 13. Keys are never exposed in logs or responses/metadata
    def test_13_keys_not_in_logs_or_responses(self):
        def fake_urlopen(req, timeout=None):
            if req.get_header("Authorization") == f"Bearer {FAKE_PRIMARY_KEY}":
                raise _make_http_error(503, f"Error with {FAKE_PRIMARY_KEY}")
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "Safe reply"}}]}
            )

        log_records = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record):
                log_records.append(self.format(record))

        logger = logging.getLogger("jeevan_setu.openrouter")
        handler = _CaptureHandler()
        logger.addHandler(handler)
        prev_level = logger.level
        logger.setLevel(logging.INFO)
        try:
            with patch.dict(os.environ, self._base_env(), clear=True):
                with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                    ok, text, meta = query_openrouter_gemini("Secret patient prompt?", mode="general")
        finally:
            logger.removeHandler(handler)
            logger.setLevel(prev_level)

        self.assertTrue(ok)
        joined_logs = "\n".join(log_records)
        self.assertNotIn(FAKE_PRIMARY_KEY, joined_logs)
        self.assertNotIn(FAKE_SECONDARY_KEY, joined_logs)
        self.assertNotIn("Secret patient prompt?", joined_logs)
        self.assertNotIn(FAKE_PRIMARY_KEY, json.dumps(meta))
        self.assertNotIn(FAKE_SECONDARY_KEY, json.dumps(meta))

    # 14. Primary remains default for subsequent requests after a failover
    def test_14_primary_remains_default_after_failover(self):
        auth_sequence = []

        def fake_urlopen(req, timeout=None):
            auth = req.get_header("Authorization")
            auth_sequence.append(auth)
            if len(auth_sequence) == 1:
                raise TimeoutError("Transient timeout")
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok1, _, meta1 = query_openrouter_gemini("First", mode="general")
                ok2, _, meta2 = query_openrouter_gemini("Second", mode="general")

        self.assertTrue(ok1 and ok2)
        self.assertEqual(meta1["key_slot_used"], "secondary")
        self.assertEqual(meta2["key_slot_used"], "primary")
        self.assertEqual(
            auth_sequence,
            [f"Bearer {FAKE_PRIMARY_KEY}", f"Bearer {FAKE_SECONDARY_KEY}", f"Bearer {FAKE_PRIMARY_KEY}"],
        )

    # 15. Tool calling, multimodal payloads, and model preserved across failover
    def test_15_tools_and_multimodal_preserved_across_failover(self):
        captured_payloads = []
        sample_tools = [{"type": "function", "function": {"name": "get_vitals", "parameters": {"type": "object", "properties": {}}}}]
        multimodal_messages = [
            {"role": "system", "content": "Analyze monitor"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Read this monitor"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                ],
            },
        ]

        def fake_urlopen(req, timeout=None):
            captured_payloads.append(json.loads(req.data.decode("utf-8")))
            if len(captured_payloads) == 1:
                raise _make_http_error(503, "Temporary outage")
            return _MockHTTPResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [{"id": "tc_1", "type": "function", "function": {"name": "get_vitals", "arguments": "{}"}}],
                            }
                        }
                    ]
                },
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                res = call_openrouter_with_tools(
                    messages=multimodal_messages,
                    tools=sample_tools,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=512,
                )

        self.assertTrue(res["success"])
        self.assertTrue(res["failover_triggered"])
        self.assertEqual(res["key_slot_used"], "secondary")
        self.assertEqual(len(captured_payloads), 2)
        self.assertEqual(captured_payloads[0], captured_payloads[1])
        self.assertEqual(captured_payloads[1]["model"], "google/gemma-4-31b-it:free")
        self.assertEqual(captured_payloads[1]["tools"], sample_tools)
        self.assertEqual(captured_payloads[1]["messages"], multimodal_messages)

    # 16. Patient Chat vs General Chat isolation
    def test_16_patient_and_general_chat_isolation(self):
        captured_bodies = []

        def fake_urlopen(req, timeout=None):
            captured_bodies.append(json.loads(req.data.decode("utf-8")))
            return _MockHTTPResponse(
                200, {"choices": [{"message": {"role": "assistant", "content": "Response"}}]}
            )

        with patch.dict(os.environ, self._base_env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                query_openrouter_gemini("What is sepsis?", patient_context=None, mode="general")
                query_openrouter_gemini(
                    "Summarize patient",
                    patient_context={"patient": {"patient_id": 1, "name": "Test Patient", "age": 45, "gender": "M"}},
                    mode="patient",
                )

        general_text = json.dumps(captured_bodies[0]["messages"])
        patient_text = json.dumps(captured_bodies[1]["messages"])
        self.assertNotIn("Test Patient", general_text)
        self.assertIn("Test Patient", patient_text)

    # 17. Env config validation & legacy key non-use
    def test_17_env_configuration_validation_and_no_legacy_fallback(self):
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_ENABLED": "false",
                "OPENROUTER_PRIMARY_API_KEY": "",
                "OPENROUTER_SECONDARY_API_KEY": "",
                "OPENROUTER_API_KEY": "legacy-ignored",
                "OPENROUTER_BACKUP_API_KEY": "legacy-backup-ignored",
                "OPENROUTER_MODEL": "google/gemma-4-31b-it:free",
                "OPENROUTER_FAILOVER_ENABLED": "true",
                "OPENROUTER_TIMEOUT_SECONDS": "12",
                "OPENROUTER_MAX_RETRIES": "1",
            },
            clear=True,
        ):
            self.assertFalse(is_openrouter_enabled())
            self.assertTrue(is_failover_enabled())
            self.assertIsNone(get_primary_api_key())
            self.assertIsNone(get_secondary_api_key())
            self.assertEqual(get_openrouter_model(), "google/gemma-4-31b-it:free")
            self.assertEqual(get_openrouter_timeout(), 12)
            self.assertEqual(get_openrouter_max_retries(), 1)
            cfg = validate_openrouter_config()
            self.assertFalse(cfg["valid"])
            self.assertFalse(cfg["has_primary_key"])
            self.assertFalse(cfg["has_secondary_key"])
            self.assertFalse(is_ai_configured())

    # 18. .env file has ONLY standardized two-key vars & .gitignore excludes .env
    def test_18_env_and_gitignore_safety(self):
        root = Path(__file__).resolve().parent.parent.parent
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", gitignore)
        env_path = root / ".env"
        if env_path.is_file():
            env_keys = {}
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_keys[k.strip()] = v.strip()
            for req_key in (
                "OPENROUTER_ENABLED",
                "OPENROUTER_PRIMARY_API_KEY",
                "OPENROUTER_SECONDARY_API_KEY",
                "OPENROUTER_MODEL",
                "OPENROUTER_FAILOVER_ENABLED",
                "ALLOW_EXTERNAL_PATIENT_VISION",
            ):
                self.assertIn(req_key, env_keys, f"{req_key} must exist in .env")
            self.assertNotIn("OPENROUTER_API_KEY", env_keys)
            self.assertNotIn("OPENROUTER_BACKUP_API_KEY", env_keys)
            self.assertEqual(env_keys["OPENROUTER_ENABLED"], "false")


if __name__ == "__main__":
    unittest.main()
