"""
tests/test_scoring.py — Unit tests for the EWS scoring engine.
"""

import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.scoring_engine import calculate_ews, calculate_parameter_score, get_risk_level


class TestParameterScoring:
    """Tests for individual parameter score calculation."""

    def test_normal_heart_rate(self):
        assert calculate_parameter_score('heart_rate', 75) == 0

    def test_high_heart_rate(self):
        assert calculate_parameter_score('heart_rate', 120) == 2

    def test_critical_heart_rate(self):
        assert calculate_parameter_score('heart_rate', 150) == 3

    def test_normal_sbp(self):
        assert calculate_parameter_score('blood_pressure_sys', 120) == 0

    def test_critical_sbp(self):
        assert calculate_parameter_score('blood_pressure_sys', 60) == 3

    def test_normal_rr(self):
        assert calculate_parameter_score('respiratory_rate', 16) == 0

    def test_critical_rr(self):
        assert calculate_parameter_score('respiratory_rate', 30) == 3

    def test_normal_temp(self):
        assert calculate_parameter_score('temperature', 37.0) == 0

    def test_high_temp(self):
        assert calculate_parameter_score('temperature', 39.5) == 2

    def test_none_value(self):
        assert calculate_parameter_score('heart_rate', None) == 0


class TestEWSCalculation:
    """Tests for total EWS calculation."""

    def test_normal_vitals(self):
        vitals = {
            'heart_rate': 75, 'blood_pressure_sys': 120,
            'respiratory_rate': 16, 'temperature': 37.0
        }
        result = calculate_ews(vitals)
        assert result['total_score'] == 0
        assert result['risk_level'] == 'normal'

    def test_critical_vitals(self):
        vitals = {
            'heart_rate': 150, 'blood_pressure_sys': 60,
            'respiratory_rate': 30, 'temperature': 39.5
        }
        result = calculate_ews(vitals)
        assert result['total_score'] >= 7
        assert result['risk_level'] == 'critical'

    def test_empty_vitals(self):
        result = calculate_ews({})
        assert result['total_score'] == 0

    def test_partial_vitals(self):
        vitals = {'heart_rate': 75, 'respiratory_rate': 16}
        result = calculate_ews(vitals)
        assert result['total_score'] == 0


class TestRiskLevel:
    """Tests for risk level classification."""

    def test_normal(self):
        assert get_risk_level(0) == 'normal'

    def test_low(self):
        assert get_risk_level(2) == 'low'

    def test_medium(self):
        assert get_risk_level(4) == 'medium'

    def test_high(self):
        assert get_risk_level(6) == 'high'

    def test_critical(self):
        assert get_risk_level(9) == 'critical'


class TestFromFile:
    """Tests using test_cases.json data."""

    @pytest.fixture
    def test_cases(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'test_cases.json')
        with open(path) as f:
            return json.load(f)

    def test_all_cases(self, test_cases):
        for case in test_cases:
            vitals = {k: v for k, v in case['vitals'].items() if v is not None}
            result = calculate_ews(vitals)
            assert result['risk_level'] == case['expected_risk'], \
                f"Failed {case['test_id']}: expected {case['expected_risk']}, got {result['risk_level']}"
