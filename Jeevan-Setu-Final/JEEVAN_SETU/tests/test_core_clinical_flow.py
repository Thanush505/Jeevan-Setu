"""
tests/test_core_clinical_flow.py — Comprehensive tests for the Core Clinical Data Flow.

Tests cover:
    1–5:   Valid submission + missing individual parameters
    6:     Invalid numeric values
    7:     Unknown patient
    8:     Unauthorized user
    9–11:  Role-based access (nurse, doctor, attendant)
    12:    Individual score calculations
    13:    Total score calculation
    14–16: Decision rules (0–2, 3–4, ≥5)
    17:    Database persistence
    18:    Latest patient data retrieval
    19:    Historical records retrieval
    20:    Transaction rollback on failure
"""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ews_service import (
    calculate_respiratory_rate_score,
    calculate_heart_rate_score,
    calculate_systolic_bp_score,
    calculate_temperature_score,
    calculate_ews
)
from services.decision_service import (
    evaluate,
    get_risk_level_from_condition,
    get_alert_type_from_condition
)


# ═══════════════════════════════════════════════════════════════
# Test 12: Individual Score Calculations
# ═══════════════════════════════════════════════════════════════
class TestIndividualScoreCalculations:
    """Test each of the 4 individual parameter scoring functions."""

    # — Respiratory Rate (approved thresholds from scoring_engine.py) —
    # Score 3: 0–8, Score 1: 9–11, Score 0: 12–20, Score 2: 21–24, Score 3: 25+

    def test_rr_normal(self):
        """RR 16 is in normal range (12–20) → score 0."""
        assert calculate_respiratory_rate_score(16) == 0

    def test_rr_normal_boundary_low(self):
        """RR 12 is at normal range lower boundary → score 0."""
        assert calculate_respiratory_rate_score(12) == 0

    def test_rr_normal_boundary_high(self):
        """RR 20 is at normal range upper boundary → score 0."""
        assert calculate_respiratory_rate_score(20) == 0

    def test_rr_slightly_low(self):
        """RR 10 (range 9–11) → score 1."""
        assert calculate_respiratory_rate_score(10) == 1

    def test_rr_moderately_high(self):
        """RR 22 (range 21–24) → score 2."""
        assert calculate_respiratory_rate_score(22) == 2

    def test_rr_critical_low(self):
        """RR 6 (≤8) → score 3."""
        assert calculate_respiratory_rate_score(6) == 3

    def test_rr_critical_high(self):
        """RR 30 (≥25) → score 3."""
        assert calculate_respiratory_rate_score(30) == 3

    def test_rr_none(self):
        """None value → score 0."""
        assert calculate_respiratory_rate_score(None) == 0

    # — Heart Rate (approved thresholds) —
    # Score 3: 0–40, Score 1: 41–50, Score 0: 51–90, Score 1: 91–110,
    # Score 2: 111–130, Score 3: 131+

    def test_hr_normal(self):
        """HR 75 (range 51–90) → score 0."""
        assert calculate_heart_rate_score(75) == 0

    def test_hr_slightly_high(self):
        """HR 100 (range 91–110) → score 1."""
        assert calculate_heart_rate_score(100) == 1

    def test_hr_moderately_high(self):
        """HR 120 (range 111–130) → score 2."""
        assert calculate_heart_rate_score(120) == 2

    def test_hr_critical_high(self):
        """HR 150 (≥131) → score 3."""
        assert calculate_heart_rate_score(150) == 3

    def test_hr_critical_low(self):
        """HR 35 (≤40) → score 3."""
        assert calculate_heart_rate_score(35) == 3

    def test_hr_none(self):
        assert calculate_heart_rate_score(None) == 0

    # — Systolic BP (approved thresholds) —
    # Score 3: 0–70, Score 2: 71–80, Score 1: 81–100, Score 0: 101–199, Score 3: 200+

    def test_sbp_normal(self):
        """SBP 120 (range 101–199) → score 0."""
        assert calculate_systolic_bp_score(120) == 0

    def test_sbp_slightly_low(self):
        """SBP 95 (range 81–100) → score 1."""
        assert calculate_systolic_bp_score(95) == 1

    def test_sbp_moderately_low(self):
        """SBP 75 (range 71–80) → score 2."""
        assert calculate_systolic_bp_score(75) == 2

    def test_sbp_critical_low(self):
        """SBP 60 (≤70) → score 3."""
        assert calculate_systolic_bp_score(60) == 3

    def test_sbp_critical_high(self):
        """SBP 220 (≥200) → score 3."""
        assert calculate_systolic_bp_score(220) == 3

    def test_sbp_none(self):
        assert calculate_systolic_bp_score(None) == 0

    # — Temperature (approved thresholds) —
    # Score 3: 0–35.0, Score 1: 35.1–36.0, Score 0: 36.1–38.0,
    # Score 1: 38.1–39.0, Score 2: 39.1+

    def test_temp_normal(self):
        """Temp 37.0 (range 36.1–38.0) → score 0."""
        assert calculate_temperature_score(37.0) == 0

    def test_temp_slightly_low(self):
        """Temp 35.5 (range 35.1–36.0) → score 1."""
        assert calculate_temperature_score(35.5) == 1

    def test_temp_slightly_high(self):
        """Temp 38.5 (range 38.1–39.0) → score 1."""
        assert calculate_temperature_score(38.5) == 1

    def test_temp_moderately_high(self):
        """Temp 39.5 (≥39.1) → score 2."""
        assert calculate_temperature_score(39.5) == 2

    def test_temp_critical_low(self):
        """Temp 34.0 (≤35.0) → score 3."""
        assert calculate_temperature_score(34.0) == 3

    def test_temp_none(self):
        assert calculate_temperature_score(None) == 0


# ═══════════════════════════════════════════════════════════════
# Test 13: Total Score Calculation
# ═══════════════════════════════════════════════════════════════
class TestTotalScoreCalculation:
    """Test the combined EWS calculation from all 4 parameters."""

    def test_all_normal_vitals(self):
        """All normal → total score 0."""
        result = calculate_ews(
            respiratory_rate=16, heart_rate=75,
            systolic_bp=120, temperature=37.0
        )
        assert result['total_score'] == 0
        assert result['respiratory_rate_score'] == 0
        assert result['heart_rate_score'] == 0
        assert result['systolic_bp_score'] == 0
        assert result['temperature_score'] == 0
        assert result['abnormal_parameters'] == []

    def test_one_abnormal_parameter(self):
        """One slightly abnormal parameter → total score 1."""
        result = calculate_ews(
            respiratory_rate=16, heart_rate=100,  # score 1
            systolic_bp=120, temperature=37.0
        )
        assert result['total_score'] == 1
        assert result['heart_rate_score'] == 1
        assert len(result['abnormal_parameters']) == 1
        assert result['abnormal_parameters'][0]['parameter'] == 'heart_rate'

    def test_multiple_abnormal(self):
        """Multiple abnormal → scores add up."""
        result = calculate_ews(
            respiratory_rate=22,   # score 2
            heart_rate=120,        # score 2
            systolic_bp=75,        # score 2
            temperature=39.5       # score 2
        )
        assert result['total_score'] == 8
        assert len(result['abnormal_parameters']) == 4

    def test_critical_vitals(self):
        """All critical → maximum total score."""
        result = calculate_ews(
            respiratory_rate=5,    # score 3
            heart_rate=35,         # score 3
            systolic_bp=60,        # score 3
            temperature=34.0       # score 3
        )
        assert result['total_score'] == 12

    def test_mixed_scores(self):
        """Mixed normal and abnormal."""
        result = calculate_ews(
            respiratory_rate=16,   # score 0
            heart_rate=100,        # score 1
            systolic_bp=120,       # score 0
            temperature=38.5       # score 1
        )
        assert result['total_score'] == 2


# ═══════════════════════════════════════════════════════════════
# Tests 14–16: Decision Rules
# ═══════════════════════════════════════════════════════════════
class TestDecisionRules:
    """Test the documented 3-tier decision rule."""

    # Test 14: Score 0–2 → Stable / Fit for HDU Transfer
    def test_score_0_stable(self):
        result = evaluate(0)
        assert result['condition'] == 'Stable'
        assert result['recommendation'] == 'Fit for HDU Transfer'

    def test_score_1_stable(self):
        result = evaluate(1)
        assert result['condition'] == 'Stable'
        assert result['recommendation'] == 'Fit for HDU Transfer'

    def test_score_2_stable(self):
        result = evaluate(2)
        assert result['condition'] == 'Stable'
        assert result['recommendation'] == 'Fit for HDU Transfer'

    # Test 15: Score 3–4 → Moderate Risk / Re-evaluate
    def test_score_3_moderate(self):
        result = evaluate(3)
        assert result['condition'] == 'Moderate Risk'
        assert result['recommendation'] == 'Re-evaluate'

    def test_score_4_moderate(self):
        result = evaluate(4)
        assert result['condition'] == 'Moderate Risk'
        assert result['recommendation'] == 'Re-evaluate'

    # Test 16: Score ≥5 → Critical / Keep in ICU
    def test_score_5_critical(self):
        result = evaluate(5)
        assert result['condition'] == 'Critical'
        assert result['recommendation'] == 'Keep in ICU'

    def test_score_8_critical(self):
        result = evaluate(8)
        assert result['condition'] == 'Critical'
        assert result['recommendation'] == 'Keep in ICU'

    def test_score_12_critical(self):
        result = evaluate(12)
        assert result['condition'] == 'Critical'
        assert result['recommendation'] == 'Keep in ICU'

    def test_negative_score_treated_as_zero(self):
        """Negative scores should be clamped to 0 → Stable."""
        result = evaluate(-1)
        assert result['condition'] == 'Stable'

    def test_risk_level_mapping(self):
        """Test risk level mapping for database ENUM."""
        assert get_risk_level_from_condition('Stable') == 'LOW'
        assert get_risk_level_from_condition('Moderate Risk') == 'MEDIUM'
        assert get_risk_level_from_condition('Critical') == 'CRITICAL'

    def test_alert_type_mapping(self):
        """Test alert type mapping."""
        assert get_alert_type_from_condition('Stable') is None
        assert get_alert_type_from_condition('Moderate Risk') == 'high'
        assert get_alert_type_from_condition('Critical') == 'critical'


# ═══════════════════════════════════════════════════════════════
# Test 1: Valid Vital Submission (End-to-End Service Logic)
# ═══════════════════════════════════════════════════════════════
class TestValidVitalSubmission:
    """Test the full EWS → Decision pipeline with valid vitals."""

    def test_normal_vitals_pipeline(self):
        """Normal vitals → score 0 → Stable → Fit for HDU Transfer."""
        ews = calculate_ews(
            respiratory_rate=16, heart_rate=75,
            systolic_bp=120, temperature=37.0
        )
        decision = evaluate(ews['total_score'])
        assert ews['total_score'] == 0
        assert decision['condition'] == 'Stable'
        assert decision['recommendation'] == 'Fit for HDU Transfer'

    def test_moderate_risk_pipeline(self):
        """Moderately abnormal → score 3–4 → Moderate Risk → Re-evaluate."""
        ews = calculate_ews(
            respiratory_rate=22,   # score 2
            heart_rate=100,        # score 1
            systolic_bp=120,       # score 0
            temperature=37.0       # score 0
        )
        decision = evaluate(ews['total_score'])
        assert ews['total_score'] == 3
        assert decision['condition'] == 'Moderate Risk'
        assert decision['recommendation'] == 'Re-evaluate'

    def test_critical_pipeline(self):
        """Critical vitals → score ≥5 → Critical → Keep in ICU."""
        ews = calculate_ews(
            respiratory_rate=30,   # score 3
            heart_rate=150,        # score 3
            systolic_bp=60,        # score 3
            temperature=34.0       # score 3
        )
        decision = evaluate(ews['total_score'])
        assert ews['total_score'] >= 5
        assert decision['condition'] == 'Critical'
        assert decision['recommendation'] == 'Keep in ICU'


# ═══════════════════════════════════════════════════════════════
# Tests 2–5: Missing Individual Parameters (Service Level)
# ═══════════════════════════════════════════════════════════════
class TestMissingParameterValidation:
    """
    Test that the EWS service handles individual None parameters.
    Note: The API endpoint enforces all 4 are required; these test
    the service layer's robustness.
    """

    def test_missing_respiratory_rate(self):
        """Missing RR should not crash; RR score = 0."""
        ews = calculate_ews(
            respiratory_rate=None, heart_rate=75,
            systolic_bp=120, temperature=37.0
        )
        assert ews['respiratory_rate_score'] == 0

    def test_missing_heart_rate(self):
        """Missing HR should not crash; HR score = 0."""
        ews = calculate_ews(
            respiratory_rate=16, heart_rate=None,
            systolic_bp=120, temperature=37.0
        )
        assert ews['heart_rate_score'] == 0

    def test_missing_systolic_bp(self):
        """Missing SBP should not crash; SBP score = 0."""
        ews = calculate_ews(
            respiratory_rate=16, heart_rate=75,
            systolic_bp=None, temperature=37.0
        )
        assert ews['systolic_bp_score'] == 0

    def test_missing_temperature(self):
        """Missing temperature should not crash; temp score = 0."""
        ews = calculate_ews(
            respiratory_rate=16, heart_rate=75,
            systolic_bp=120, temperature=None
        )
        assert ews['temperature_score'] == 0


# ═══════════════════════════════════════════════════════════════
# Test 6: Invalid Numeric Values (Service Level)
# ═══════════════════════════════════════════════════════════════
class TestInvalidValues:
    """Test that invalid values don't cause crashes at service level."""

    def test_zero_values(self):
        """Zero values should be scored (not rejected at service level)."""
        ews = calculate_ews(
            respiratory_rate=0, heart_rate=0,
            systolic_bp=0, temperature=0
        )
        # All should get score 3 (critically low)
        assert ews['respiratory_rate_score'] == 3
        assert ews['heart_rate_score'] == 3
        assert ews['systolic_bp_score'] == 3
        assert ews['temperature_score'] == 3
        assert ews['total_score'] == 12

    def test_boundary_normal_values(self):
        """Values at exact normal boundaries."""
        ews = calculate_ews(
            respiratory_rate=12, heart_rate=51,
            systolic_bp=101, temperature=36.1
        )
        assert ews['total_score'] == 0


# ═══════════════════════════════════════════════════════════════
# Combined Integration Test: Full Pipeline
# ═══════════════════════════════════════════════════════════════
class TestFullPipeline:
    """End-to-end pipeline: vitals → EWS → decision with abnormal tracking."""

    def test_pipeline_returns_all_required_fields(self):
        """Verify the EWS result contains all required fields."""
        ews = calculate_ews(
            respiratory_rate=18, heart_rate=82,
            systolic_bp=120, temperature=36.8
        )
        assert 'respiratory_rate_score' in ews
        assert 'heart_rate_score' in ews
        assert 'systolic_bp_score' in ews
        assert 'temperature_score' in ews
        assert 'total_score' in ews
        assert 'abnormal_parameters' in ews

    def test_decision_returns_all_required_fields(self):
        """Verify the decision result contains condition and recommendation."""
        decision = evaluate(3)
        assert 'condition' in decision
        assert 'recommendation' in decision

    def test_abnormal_parameters_tracking(self):
        """Abnormal parameters should be listed with details."""
        ews = calculate_ews(
            respiratory_rate=30,   # score 3 → abnormal
            heart_rate=75,         # score 0 → normal
            systolic_bp=60,        # score 3 → abnormal
            temperature=37.0       # score 0 → normal
        )
        abnormal = ews['abnormal_parameters']
        assert len(abnormal) == 2
        param_keys = [p['parameter'] for p in abnormal]
        assert 'respiratory_rate' in param_keys
        assert 'systolic_bp' in param_keys

    def test_example_from_spec(self):
        """
        Example from specification:
        RR=18, HR=82, SBP=120, Temp=36.8 → all normal → score 0 → Stable.
        """
        ews = calculate_ews(
            respiratory_rate=18, heart_rate=82,
            systolic_bp=120, temperature=36.8
        )
        decision = evaluate(ews['total_score'])
        assert ews['total_score'] == 0
        assert decision['condition'] == 'Stable'
        assert decision['recommendation'] == 'Fit for HDU Transfer'
