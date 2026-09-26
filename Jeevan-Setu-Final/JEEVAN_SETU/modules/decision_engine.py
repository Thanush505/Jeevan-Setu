"""
modules/decision_engine.py — Rule-based Clinical Decision Engine for ICU ↔ HDU transfers.

Pure Python module independent from Flask routes for isolated testing and background processing.
Pipeline:
    EWS
     ↓
    Current Unit
     ↓
    Decision Rules
     ↓
    Recommendation

Supported Recommendations:
    - TRANSFER_TO_HDU
    - CONTINUE_ICU
    - CONTINUE_HDU
    - ESCALATE_TO_ICU
    - RE_EVALUATE
"""

from modules.scoring_engine import calculate_ews, get_risk_level


# Standard recommendations enum/constants
RECOMMENDATION_TRANSFER_TO_HDU = "TRANSFER_TO_HDU"
RECOMMENDATION_CONTINUE_ICU = "CONTINUE_ICU"
RECOMMENDATION_CONTINUE_HDU = "CONTINUE_HDU"
RECOMMENDATION_ESCALATE_TO_ICU = "ESCALATE_TO_ICU"
RECOMMENDATION_RE_EVALUATE = "RE_EVALUATE"

VALID_RECOMMENDATIONS = {
    RECOMMENDATION_TRANSFER_TO_HDU,
    RECOMMENDATION_CONTINUE_ICU,
    RECOMMENDATION_CONTINUE_HDU,
    RECOMMENDATION_ESCALATE_TO_ICU,
    RECOMMENDATION_RE_EVALUATE,
}


def evaluate_decision(score=0, current_unit='ICU', vitals_data=None, vitals_history=None, risk_level=None):
    """
    Pure rule-based clinical decision engine.

    Args:
        score (int): Total Early Warning Score (0-20+).
        current_unit (str): Current unit/ward type ('ICU', 'HDU', 'General').
        vitals_data (dict, optional): Current vital signs.
        vitals_history (list, optional): Previous vitals for trend/stability.
        risk_level (str, optional): Overridden risk level string.

    Returns:
        dict: Standard recommendation payload containing:
            - score (int)
            - risk_level (str: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'NORMAL')
            - recommendation (str)
            - reason (str)
            - status (str: 'PENDING')
    """
    # 1. Normalize input score & vitals
    breakdown = {}
    if vitals_data and not score:
        ews_result = calculate_ews(vitals_data)
        score = ews_result['total_score']
        breakdown = ews_result.get('breakdown', {})
        if not risk_level:
            risk_level = ews_result['risk_level']
    elif vitals_data:
        ews_calc = calculate_ews(vitals_data)
        breakdown = ews_calc.get('breakdown', {})

    score = max(0, int(score))
    calculated_risk = (risk_level or get_risk_level(score)).upper()

    unit = (current_unit or 'ICU').strip().upper()
    if unit in ('GENERAL WARD', 'GEN'):
        unit = 'GENERAL'

    recommendation = RECOMMENDATION_RE_EVALUATE
    reason = ""
    target_ward = current_unit
    action_required = False
    confidence = 0.85

    # Check for single severe red-flag vital parameters (score >= 3 in any single parameter)
    has_severe_parameter = any(p.get('score', 0) >= 3 for p in breakdown.values())

    # ─────────────────────────────────────────────────────────
    # Clinical Decision Rules
    # ─────────────────────────────────────────────────────────

    if unit == 'ICU':
        if score >= 5 or has_severe_parameter or calculated_risk in ('HIGH', 'CRITICAL'):
            # High/Critical risk in ICU -> Continue Intensive Monitoring
            recommendation = RECOMMENDATION_CONTINUE_ICU
            target_ward = 'ICU'
            reason = (
                f"Patient exhibits elevated EWS score ({score}) with {calculated_risk} risk. "
                "Requires continuous Level 3 ICU intensive monitoring and mechanical/vasopressor support."
            )
            confidence = min(0.98, 0.75 + (score * 0.02))

        elif score <= 3 and calculated_risk in ('NORMAL', 'LOW'):
            # Stable patient in ICU -> Step-down to HDU
            recommendation = RECOMMENDATION_TRANSFER_TO_HDU
            target_ward = 'HDU'
            action_required = True
            reason = (
                f"Patient vitals stabilized (EWS = {score}, {calculated_risk} risk). "
                "Clinical criteria met for step-down to High Dependency Unit (HDU)."
            )
            confidence = 0.92 if vitals_history else 0.85

        else:
            # Score == 4 or Borderline Medium risk in ICU
            recommendation = RECOMMENDATION_RE_EVALUATE
            target_ward = 'ICU'
            reason = (
                f"Borderline EWS score ({score}, {calculated_risk} risk). "
                "Recommend serial vitals reassessment in 1-2 hours before deciding transfer."
            )
            confidence = 0.70

    elif unit == 'HDU':
        if score >= 5 or has_severe_parameter or calculated_risk in ('HIGH', 'CRITICAL'):
            # Deteriorating in HDU -> Escalate to ICU
            recommendation = RECOMMENDATION_ESCALATE_TO_ICU
            target_ward = 'ICU'
            action_required = True
            reason = (
                f"Patient deteriorating in HDU (EWS = {score}, {calculated_risk} risk). "
                "Urgent escalation and transfer to Intensive Care Unit (ICU) required."
            )
            confidence = min(0.98, 0.80 + (score * 0.02))

        elif 1 <= score <= 4 and calculated_risk in ('LOW', 'MEDIUM'):
            # Manageable in HDU -> Continue HDU care
            recommendation = RECOMMENDATION_CONTINUE_HDU
            target_ward = 'HDU'
            reason = (
                f"Patient vital signs within acceptable HDU parameters (EWS = {score}, {calculated_risk} risk). "
                "Continue intermediate level monitoring in HDU."
            )
            confidence = 0.85

        else:
            # Score 0 (Normal) -> Consider step-down or re-evaluate
            recommendation = RECOMMENDATION_RE_EVALUATE
            target_ward = 'General'
            reason = (
                f"Patient is completely stable (EWS = {score}, {calculated_risk} risk). "
                "Re-evaluate for step-down to General Ward or discharge from intermediate care."
            )
            confidence = 0.80

    else:
        # General Ward
        if score >= 7 or has_severe_parameter:
            recommendation = RECOMMENDATION_ESCALATE_TO_ICU
            target_ward = 'ICU'
            action_required = True
            reason = (
                f"Critical deterioration in General ward (EWS = {score}, {calculated_risk} risk). "
                "Immediate emergency transfer to ICU required."
            )
            confidence = 0.95
        elif 3 <= score <= 6:
            recommendation = RECOMMENDATION_TRANSFER_TO_HDU
            target_ward = 'HDU'
            action_required = True
            reason = (
                f"Moderate physiological instability (EWS = {score}, {calculated_risk} risk). "
                "Transfer to HDU recommended for continuous telemetry monitoring."
            )
            confidence = 0.88
        else:
            recommendation = RECOMMENDATION_RE_EVALUATE
            target_ward = 'General'
            reason = f"Patient stable in General Ward (EWS = {score}, {calculated_risk} risk). Continue routine ward rounds."
            confidence = 0.90

    # Generate explanation breakdown based on actual recorded parameters
    from modules.explanation_engine import generate_explanation
    explanation_info = generate_explanation(
        vitals_data=vitals_data,
        ews_result={'total_score': score, 'risk_level': calculated_risk, 'breakdown': breakdown},
        recommendation=recommendation,
        reason=reason,
        save_to_db=False
    )

    return {
        'score': score,
        'risk_level': calculated_risk,
        'recommendation': recommendation,
        'reason': reason,
        'status': 'PENDING',
        'from_ward': current_unit,
        'to_ward': target_ward,
        'confidence': round(confidence, 2),
        'action_required': action_required,
        'breakdown': breakdown,
        'contributing_parameters': explanation_info.get('contributing_parameters', []),
        'contributing_parameter_names': explanation_info.get('contributing_parameter_names', []),
        'explanation': explanation_info
    }


def make_transfer_decision(patient, vitals_data, vitals_history=None):
    """
    Legacy & patient wrapper for transfer decision evaluation.
    """
    current_ward = patient.get('ward_type', 'ICU') if isinstance(patient, dict) else getattr(patient, 'ward_type', 'ICU')
    ews_result = calculate_ews(vitals_data) if vitals_data else {'total_score': 0, 'risk_level': 'normal'}
    score = ews_result['total_score']
    risk_level = ews_result['risk_level']

    decision = evaluate_decision(
        score=score,
        current_unit=current_ward,
        vitals_data=vitals_data,
        vitals_history=vitals_history,
        risk_level=risk_level
    )

    if isinstance(patient, dict):
        decision['patient_id'] = patient.get('patient_id')
        decision['patient_name'] = patient.get('name')
    return decision

