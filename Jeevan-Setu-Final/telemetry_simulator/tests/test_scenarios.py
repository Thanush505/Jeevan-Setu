"""
tests/test_scenarios.py — Tests for simulation scenario engines.

Validates that scenarios produce realistic, gradual changes and contain
NO EWS scoring, NO risk levels, NO clinical decisions.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scenarios import ScenarioEngine


class TestStableScenario:
    """TEST 3: Stable scenario produces valid readings."""

    def test_produces_all_four_params(self):
        engine = ScenarioEngine('STABLE')
        vitals = engine.next()
        assert 'heart_rate' in vitals
        assert 'respiratory_rate' in vitals
        assert 'systolic_bp' in vitals
        assert 'temperature' in vitals

    def test_values_are_numeric(self):
        engine = ScenarioEngine('STABLE')
        vitals = engine.next()
        for key in ('heart_rate', 'respiratory_rate', 'systolic_bp', 'temperature'):
            assert isinstance(vitals[key], (int, float))

    def test_values_in_normal_range(self):
        """Stable values should remain within broadly normal physiological ranges."""
        engine = ScenarioEngine('STABLE')
        for _ in range(50):
            v = engine.next()
            assert 40 <= v['heart_rate'] <= 150
            assert 4 <= v['respiratory_rate'] <= 40
            assert 60 <= v['systolic_bp'] <= 200
            assert 35.0 <= v['temperature'] <= 40.0

    def test_gradual_changes(self):
        """Consecutive readings should NOT jump wildly."""
        engine = ScenarioEngine('STABLE')
        prev = engine.next()
        for _ in range(30):
            curr = engine.next()
            assert abs(curr['heart_rate'] - prev['heart_rate']) < 10
            assert abs(curr['respiratory_rate'] - prev['respiratory_rate']) < 5
            assert abs(curr['systolic_bp'] - prev['systolic_bp']) < 10
            assert abs(curr['temperature'] - prev['temperature']) < 1.0
            prev = curr


class TestDeteriorationScenario:
    """TEST 4: Deterioration scenario changes gradually."""

    def test_values_increase_over_time(self):
        """Heart rate should generally increase over 40+ ticks."""
        engine = ScenarioEngine('GRADUAL_DETERIORATION')
        early_readings = [engine.next() for _ in range(5)]
        for _ in range(35):
            engine.next()
        late_readings = [engine.next() for _ in range(5)]

        avg_early_hr = sum(r['heart_rate'] for r in early_readings) / 5
        avg_late_hr = sum(r['heart_rate'] for r in late_readings) / 5
        assert avg_late_hr > avg_early_hr

    def test_sbp_decreases_over_time(self):
        """SBP should generally decrease in deterioration."""
        engine = ScenarioEngine('GRADUAL_DETERIORATION')
        early_readings = [engine.next() for _ in range(5)]
        for _ in range(35):
            engine.next()
        late_readings = [engine.next() for _ in range(5)]

        avg_early_sbp = sum(r['systolic_bp'] for r in early_readings) / 5
        avg_late_sbp = sum(r['systolic_bp'] for r in late_readings) / 5
        assert avg_late_sbp < avg_early_sbp

    def test_no_ews_in_output(self):
        """Output must contain only raw vitals — no EWS keys."""
        engine = ScenarioEngine('GRADUAL_DETERIORATION')
        for _ in range(20):
            vitals = engine.next()
            assert 'ews_score' not in vitals
            assert 'risk_level' not in vitals
            assert 'condition' not in vitals
            assert 'recommendation' not in vitals
            assert 'total_score' not in vitals


class TestRecoveryScenario:
    """TEST 5: Recovery scenario changes gradually toward stable."""

    def test_hr_decreases_toward_normal(self):
        """HR should drop from initial high values toward normal range."""
        engine = ScenarioEngine('RECOVERY')
        early_readings = [engine.next() for _ in range(5)]
        for _ in range(25):
            engine.next()
        late_readings = [engine.next() for _ in range(5)]

        avg_early_hr = sum(r['heart_rate'] for r in early_readings) / 5
        avg_late_hr = sum(r['heart_rate'] for r in late_readings) / 5
        assert avg_late_hr < avg_early_hr

    def test_sbp_increases_toward_normal(self):
        """SBP should increase from low values back toward normal."""
        engine = ScenarioEngine('RECOVERY')
        early_readings = [engine.next() for _ in range(5)]
        for _ in range(25):
            engine.next()
        late_readings = [engine.next() for _ in range(5)]

        avg_early_sbp = sum(r['systolic_bp'] for r in early_readings) / 5
        avg_late_sbp = sum(r['systolic_bp'] for r in late_readings) / 5
        assert avg_late_sbp > avg_early_sbp


class TestCriticalScenario:
    """Critical scenario reaches severely abnormal values quickly."""

    def test_reaches_abnormal_within_15_ticks(self):
        engine = ScenarioEngine('CRITICAL')
        for _ in range(15):
            engine.next()
        v = engine.next()
        # At least one parameter should be significantly abnormal
        abnormal = (
            v['heart_rate'] > 110 or
            v['respiratory_rate'] > 25 or
            v['systolic_bp'] < 85 or
            v['temperature'] > 38.5
        )
        assert abnormal, f"Values after 15 ticks are not abnormal enough: {v}"


class TestManualScenario:
    """TEST 6: Manual values are accepted."""

    def test_exact_values_returned(self):
        manual = {
            'heart_rate': 44.0,
            'respiratory_rate': 44.0,
            'systolic_bp': 44.0,
            'temperature': 40.0,
        }
        engine = ScenarioEngine('MANUAL', manual_values=manual)
        vitals = engine.next()
        assert vitals['heart_rate'] == 44.0
        assert vitals['respiratory_rate'] == 44.0
        assert vitals['systolic_bp'] == 44.0
        assert vitals['temperature'] == 40.0

    def test_manual_without_values_raises(self):
        engine = ScenarioEngine('MANUAL', manual_values=None)
        with pytest.raises(ValueError, match="manual_values"):
            engine.next()


class TestInvalidScenario:
    """Unknown scenario name should raise ValueError."""

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError, match="Unknown scenario"):
            ScenarioEngine('NONEXISTENT')
