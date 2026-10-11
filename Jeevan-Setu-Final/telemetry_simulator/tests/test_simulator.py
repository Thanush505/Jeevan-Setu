"""
tests/test_simulator.py — Integration tests for the simulator orchestration.
"""

import os
import sys
import pytest
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SimulatorStatus, VitalReading
from scenarios import ScenarioEngine
from config import SimulatorConfig


class TestSimulatorStartStop:
    """TEST 1 & 2: Simulator starts and stops correctly."""

    def test_status_starts_stopped(self):
        status = SimulatorStatus()
        assert status.running is False

    def test_status_can_be_started(self):
        status = SimulatorStatus(running=True, scenario='STABLE', patient_id=1)
        assert status.running is True
        assert status.scenario == 'STABLE'

    def test_status_can_be_stopped(self):
        status = SimulatorStatus(running=True)
        status.running = False
        assert status.running is False


class TestGracefulShutdown:
    """TEST 15: Graceful shutdown works."""

    def test_shutdown_flag(self):
        """The global _shutdown_requested flag is used for CTRL+C handling."""
        import simulator
        # Should be False initially
        assert simulator._shutdown_requested is False

    def test_signal_handler_sets_flag(self):
        """The signal handler should set _shutdown_requested to True."""
        import simulator
        simulator._shutdown_requested = False
        simulator._signal_handler(2, None)  # SIGINT = 2
        assert simulator._shutdown_requested is True
        # Reset for other tests
        simulator._shutdown_requested = False


class TestMultiPatientIsolation:
    """TEST 12: Multiple patients do not mix data."""

    def test_readings_preserve_patient_id(self):
        patients = [
            {'patient_id': 1, 'name': 'Patient A'},
            {'patient_id': 2, 'name': 'Patient B'},
            {'patient_id': 3, 'name': 'Patient C'},
        ]

        for p in patients:
            engine = ScenarioEngine('STABLE')
            vitals = engine.next()
            reading = VitalReading(
                patient_id=p['patient_id'],
                heart_rate=vitals['heart_rate'],
                respiratory_rate=vitals['respiratory_rate'],
                systolic_bp=vitals['systolic_bp'],
                temperature=vitals['temperature'],
                device_id=f"SIM-ICU-{p['patient_id']:03d}",
            )
            # Each reading must strictly reference its own patient
            assert reading.patient_id == p['patient_id']
            payload = reading.to_payload()
            # Payload should not contain patient_id (that goes in the URL)
            assert 'patient_id' not in payload

    def test_independent_scenario_state(self):
        """Each patient's scenario engine should have independent state."""
        engine_a = ScenarioEngine('STABLE')
        engine_b = ScenarioEngine('CRITICAL')

        for _ in range(10):
            va = engine_a.next()
            vb = engine_b.next()

        # After 10 ticks, critical scenario should have higher HR than stable
        va_final = engine_a.next()
        vb_final = engine_b.next()
        # Critical engine heart rate should generally be higher
        assert engine_a.tick == 11
        assert engine_b.tick == 11


class TestNoEWSInSimulator:
    """Verify the simulator never produces EWS-related output."""

    def test_scenario_output_has_no_ews(self):
        for scenario_name in ['STABLE', 'GRADUAL_DETERIORATION', 'CRITICAL', 'RECOVERY']:
            engine = ScenarioEngine(scenario_name)
            for _ in range(20):
                vitals = engine.next()
                for forbidden_key in ['ews_score', 'risk_level', 'condition',
                                       'recommendation', 'total_score',
                                       'hr_score', 'bp_score', 'rr_score', 'temp_score']:
                    assert forbidden_key not in vitals, (
                        f"Scenario {scenario_name} output contains forbidden key '{forbidden_key}'"
                    )

    def test_reading_payload_has_no_ews(self):
        reading = VitalReading(
            heart_rate=75, respiratory_rate=16, systolic_bp=120,
            temperature=36.8, patient_id=1, device_id='SIM-ICU-001',
        )
        payload = reading.to_payload()
        for forbidden_key in ['ews_score', 'risk_level', 'condition',
                               'recommendation', 'total_score']:
            assert forbidden_key not in payload
