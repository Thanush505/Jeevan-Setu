"""
tests/test_config.py — Tests for simulator configuration loading.
"""

import os
import pytest
import sys

# Ensure the simulator package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SimulatorConfig


class TestConfig:
    """TEST 13: Configuration loads correctly."""

    def test_default_api_base_url(self):
        """Default URL should be localhost:5000."""
        assert '127.0.0.1' in SimulatorConfig.API_BASE_URL or 'localhost' in SimulatorConfig.API_BASE_URL

    def test_interval_minimum_enforced(self):
        """Interval must be at least 1 second."""
        assert SimulatorConfig.INTERVAL_SECONDS >= 1

    def test_timeout_positive(self):
        assert SimulatorConfig.REQUEST_TIMEOUT_SECONDS > 0

    def test_max_retries_non_negative(self):
        assert SimulatorConfig.MAX_RETRIES >= 0

    def test_vitals_url_construction(self):
        url = SimulatorConfig.vitals_url(42)
        assert '/vitals/patient/42/submit' in url
        assert url.startswith('http')

    def test_patients_url_construction(self):
        url = SimulatorConfig.patients_url()
        assert '/api/v1/patients' in url

    def test_auth_url_construction(self):
        url = SimulatorConfig.auth_url()
        assert '/api/v1/auth/login' in url

    def test_valid_ranges_present(self):
        """All four vital parameters must have defined validation ranges."""
        for field in ('heart_rate', 'respiratory_rate', 'systolic_bp', 'temperature'):
            assert field in SimulatorConfig.VALID_RANGES
            lo, hi = SimulatorConfig.VALID_RANGES[field]
            assert lo < hi

    def test_summary_no_secrets(self):
        """TEST 14: No secrets are logged — summary must not contain passwords."""
        summary = SimulatorConfig.summary()
        summary_str = str(summary).lower()
        assert 'password' not in summary_str or 'not set' in summary_str
        assert 'jwt' not in summary_str
        assert 'secret' not in summary_str
