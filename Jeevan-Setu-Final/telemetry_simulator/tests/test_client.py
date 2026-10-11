"""
tests/test_client.py — Tests for the backend HTTP client.

Uses unittest.mock to simulate HTTP responses without requiring a running backend.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client import BackendClient
from models import VitalReading


def _make_reading(**overrides):
    defaults = {
        'heart_rate': 75.0,
        'respiratory_rate': 16.0,
        'systolic_bp': 120.0,
        'temperature': 36.8,
        'patient_id': 1,
        'device_id': 'SIM-ICU-001',
    }
    defaults.update(overrides)
    return VitalReading(**defaults)


class TestBackendClientAuth:
    """Tests for authentication flow."""

    @patch('client.SimulatorConfig')
    def test_no_credentials_returns_true(self, mock_config):
        """When no credentials configured, authenticate() returns True (local dev fallback)."""
        mock_config.AUTH_USERNAME = ''
        mock_config.AUTH_PASSWORD = ''
        client = BackendClient()
        assert client.authenticate() is True

    @patch('client.requests.Session')
    @patch('client.SimulatorConfig')
    def test_successful_auth(self, mock_config, mock_session_cls):
        mock_config.AUTH_USERNAME = 'nurse_rekha'
        mock_config.AUTH_PASSWORD = 'nurse123'
        mock_config.REQUEST_TIMEOUT_SECONDS = 5
        mock_config.auth_url.return_value = 'http://127.0.0.1:5000/api/v1/auth/login'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'success': True,
            'data': {
                'token': 'fake-jwt-token',
                'user': {'role': 'nurse'}
            }
        }
        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        client = BackendClient()
        client._session = mock_session
        result = client.authenticate()
        assert result is True


class TestBackendClientSubmission:
    """Tests for vital submission."""

    def test_invalid_reading_rejected_locally(self):
        """TEST 7 & 8: Invalid values are caught before hitting the network."""
        client = BackendClient()
        reading = _make_reading(heart_rate=5.0)  # Below minimum
        success, resp = client.submit_vitals(reading)
        assert success is False
        assert 'validation' in resp.get('error', '').lower()

    def test_connection_error_handled(self):
        """TEST 9: Network failure is handled gracefully."""
        import requests as req
        client = BackendClient()
        client._session = MagicMock()
        client._session.post.side_effect = req.ConnectionError("Connection refused")
        client._jwt_token = None

        reading = _make_reading()
        success, resp = client.submit_vitals(reading)
        assert success is False

    def test_payload_contains_correct_fields(self):
        """TEST 8: The request payload has exactly the fields the backend expects."""
        reading = _make_reading()
        payload = reading.to_payload()
        expected_keys = {'heart_rate', 'respiratory_rate', 'systolic_bp', 'temperature'}
        assert set(payload.keys()) == expected_keys


class TestBackendClientPatients:
    """Tests for patient fetching."""

    def test_empty_list_on_connection_error(self):
        """Gracefully returns empty list when backend is unreachable."""
        client = BackendClient()
        # Without a running backend, this should return [] not crash
        import requests as req
        client._session = MagicMock()
        client._session.get.side_effect = req.ConnectionError("Connection refused")
        patients = client.fetch_patients()
        assert patients == []
