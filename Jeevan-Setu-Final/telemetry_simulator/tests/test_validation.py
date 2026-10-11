"""
tests/test_validation.py — Tests for vital reading validation and models.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import VitalReading, SimulatorStatus
from config import SimulatorConfig


class TestVitalReading:
    """Tests for the VitalReading data model."""

    def _make_reading(self, **overrides):
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

    def test_valid_reading_passes(self):
        """Valid vitals should produce no validation errors."""
        reading = self._make_reading()
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert errors == []

    def test_invalid_hr_too_low(self):
        """TEST 7: Invalid values are rejected — HR below minimum."""
        reading = self._make_reading(heart_rate=5.0)
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert any('heart_rate' in e for e in errors)

    def test_invalid_hr_too_high(self):
        reading = self._make_reading(heart_rate=350.0)
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert any('heart_rate' in e for e in errors)

    def test_invalid_temperature_too_low(self):
        reading = self._make_reading(temperature=20.0)
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert any('temperature' in e for e in errors)

    def test_invalid_temperature_too_high(self):
        reading = self._make_reading(temperature=50.0)
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert any('temperature' in e for e in errors)

    def test_invalid_sbp_too_low(self):
        reading = self._make_reading(systolic_bp=10.0)
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert any('systolic_bp' in e for e in errors)

    def test_invalid_rr_too_high(self):
        reading = self._make_reading(respiratory_rate=100.0)
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        assert any('respiratory_rate' in e for e in errors)

    def test_to_payload_format(self):
        """TEST 8: API request format is correct."""
        reading = self._make_reading()
        payload = reading.to_payload()
        # Must contain exactly the four fields the backend expects
        assert set(payload.keys()) == {'heart_rate', 'respiratory_rate', 'systolic_bp', 'temperature'}
        # All values must be numeric
        for v in payload.values():
            assert isinstance(v, (int, float))

    def test_patient_id_preserved(self):
        """TEST 11: Patient ID is preserved correctly."""
        reading = self._make_reading(patient_id=42)
        assert reading.patient_id == 42

    def test_different_patients_have_different_ids(self):
        """TEST 12: Multiple patients do not mix data."""
        r1 = self._make_reading(patient_id=1)
        r2 = self._make_reading(patient_id=2)
        assert r1.patient_id != r2.patient_id
        assert r1.event_id != r2.event_id

    def test_event_id_uniqueness(self):
        """Each reading should have a unique event ID."""
        readings = [self._make_reading() for _ in range(100)]
        event_ids = [r.event_id for r in readings]
        assert len(set(event_ids)) == 100

    def test_display_str(self):
        reading = self._make_reading()
        s = reading.display_str()
        assert 'HR=' in s
        assert 'RR=' in s
        assert 'SBP=' in s
        assert 'TEMP=' in s

    def test_no_ews_fields_in_payload(self):
        """Payload must NOT contain any EWS-related fields."""
        reading = self._make_reading()
        payload = reading.to_payload()
        forbidden = ['ews_score', 'risk_level', 'condition', 'recommendation', 'total_score']
        for key in forbidden:
            assert key not in payload


class TestSimulatorStatus:
    """Tests for the SimulatorStatus tracker."""

    def test_initial_state(self):
        status = SimulatorStatus()
        assert not status.running
        assert status.readings_sent == 0
        assert status.successful == 0
        assert status.failed == 0

    def test_record_success(self):
        status = SimulatorStatus()
        status.record_success()
        assert status.readings_sent == 1
        assert status.successful == 1
        assert status.failed == 0
        assert status.last_success_time is not None
        assert status.last_error is None

    def test_record_failure(self):
        status = SimulatorStatus()
        status.record_failure('HTTP 500')
        assert status.readings_sent == 1
        assert status.successful == 0
        assert status.failed == 1
        assert status.last_error == 'HTTP 500'

    def test_summary_keys(self):
        status = SimulatorStatus(patient_id=1, scenario='STABLE')
        summary = status.summary()
        assert 'running' in summary
        assert 'patient_id' in summary
        assert 'scenario' in summary
        assert 'readings_sent' in summary
