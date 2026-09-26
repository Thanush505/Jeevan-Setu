"""
tests/test_decision.py — Unit tests for the ICU/HDU decision engine.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.decision_engine import make_transfer_decision


class TestTransferDecision:
    """Tests for ICU/HDU transfer decisions."""

    def test_escalate_to_icu(self):
        """Patient in HDU with critical EWS should be recommended for ICU."""
        patient = {'patient_id': 1, 'ward_type': 'HDU'}
        vitals = {
            'heart_rate': 145, 'blood_pressure_sys': 65,
            'respiratory_rate': 30, 'temperature': 39.5,
            'spo2': 88, 'consciousness': 'Unresponsive'
        }
        decision = make_transfer_decision(patient, vitals)
        assert decision['to_ward'] == 'ICU'
        assert decision['action_required'] is True

    def test_stay_in_icu(self):
        """Patient in ICU with moderate EWS should stay."""
        patient = {'patient_id': 2, 'ward_type': 'ICU'}
        vitals = {
            'heart_rate': 100, 'blood_pressure_sys': 110,
            'respiratory_rate': 20, 'temperature': 37.5,
            'spo2': 95, 'consciousness': 'Alert'
        }
        decision = make_transfer_decision(patient, vitals)
        assert decision['from_ward'] == 'ICU'

    def test_step_down_no_history(self):
        """Step-down without stable history should not transfer."""
        patient = {'patient_id': 3, 'ward_type': 'ICU'}
        vitals = {
            'heart_rate': 75, 'blood_pressure_sys': 120,
            'respiratory_rate': 16, 'temperature': 37.0,
            'spo2': 98, 'consciousness': 'Alert'
        }
        decision = make_transfer_decision(patient, vitals, vitals_history=None)
        # Without stable history, should not recommend transfer
        assert decision['confidence'] < 0.9

    def test_step_down_with_stable_history(self):
        """ICU patient with stable history should be recommended for HDU."""
        patient = {'patient_id': 4, 'ward_type': 'ICU'}
        vitals = {
            'heart_rate': 72, 'blood_pressure_sys': 115,
            'respiratory_rate': 14, 'temperature': 36.8,
            'spo2': 98, 'consciousness': 'Alert'
        }
        stable_history = [
            {'ews_score': 1}, {'ews_score': 0}, {'ews_score': 1},
            {'ews_score': 0}, {'ews_score': 1}
        ]
        decision = make_transfer_decision(patient, vitals, stable_history)
        assert decision['to_ward'] == 'HDU'
        assert decision['action_required'] is True

    def test_normal_patient_no_transfer(self):
        """Patient in General ward with normal vitals — no action."""
        patient = {'patient_id': 5, 'ward_type': 'General'}
        vitals = {
            'heart_rate': 78, 'blood_pressure_sys': 120,
            'respiratory_rate': 16, 'temperature': 36.9,
            'spo2': 99, 'consciousness': 'Alert'
        }
        decision = make_transfer_decision(patient, vitals)
        assert decision['to_ward'] == 'General'
        assert decision['action_required'] is False
