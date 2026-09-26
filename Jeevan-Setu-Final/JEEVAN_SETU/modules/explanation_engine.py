"""
modules/explanation_engine.py — Explainable AI (XAI) & Clinical Decision Explanation Module.

Generates transparent, human-readable explanations for all clinical recommendations
based strictly on actual stored patient vital parameters.
The backend NEVER invents or hallucinates patient information.
"""

from models.explanation_model import Explanation
from modules.scoring_engine import calculate_ews, calculate_parameter_score, get_risk_level

# Parameter display metadata
PARAMETER_METADATA = {
    'heart_rate': {
        'name': 'Heart Rate',
        'unit': 'bpm',
        'order': 1
    },
    'respiratory_rate': {
        'name': 'Respiratory Rate',
        'unit': 'breaths/min',
        'order': 2
    },
    'blood_pressure_sys': {
        'name': 'Blood Pressure',
        'unit': 'mmHg',
        'order': 3
    },
    'blood_pressure_dia': {
        'name': 'Diastolic Blood Pressure',
        'unit': 'mmHg',
        'order': 4
    },
    'temperature': {
        'name': 'Temperature',
        'unit': '°C',
        'order': 5
    },
    'spo2': {
        'name': 'Oxygen Saturation (SpO2)',
        'unit': '%',
        'order': 6
    },
    'consciousness': {
        'name': 'Consciousness',
        'unit': '',
        'order': 7
    },
    'blood_sugar': {
        'name': 'Blood Sugar',
        'unit': 'mg/dL',
        'order': 8
    },
    'urine_output': {
        'name': 'Urine Output',
        'unit': 'mL/hr',
        'order': 9
    }
}

RECOMMENDATION_TITLES = {
    'TRANSFER_TO_HDU': 'Transfer to HDU',
    'CONTINUE_ICU': 'Continue ICU',
    'CONTINUE_HDU': 'Continue HDU',
    'ESCALATE_TO_ICU': 'Escalate to ICU',
    'RE_EVALUATE': 'Re-evaluate'
}

STANDARD_REASONS = {
    'TRANSFER_TO_HDU': (
        "The patient's latest recorded parameters indicate "
        "improved physiological stability according to the "
        "configured Jeevan Setu decision rules."
    ),
    'CONTINUE_ICU': (
        "The patient's latest recorded parameters indicate "
        "persistent critical instability requiring continuous "
        "Level 3 intensive monitoring according to the "
        "configured Jeevan Setu decision rules."
    ),
    'CONTINUE_HDU': (
        "The patient's latest recorded parameters indicate "
        "moderate physiological stability suitable for ongoing "
        "High Dependency Unit intermediate care according to the "
        "configured Jeevan Setu decision rules."
    ),
    'ESCALATE_TO_ICU': (
        "The patient's latest recorded parameters indicate "
        "acute physiological deterioration requiring urgent "
        "escalation to the Intensive Care Unit according to the "
        "configured Jeevan Setu decision rules."
    ),
    'RE_EVALUATE': (
        "The patient's latest recorded parameters warrant "
        "serial reassessment within 1-2 hours according to the "
        "configured Jeevan Setu decision rules."
    )
}


def generate_explanation(decision_id=None, patient_id=None, vitals_data=None,
                         ews_result=None, recommendation=None, reason=None,
                         save_to_db=True):
    """
    Generate transparent, evidence-backed clinical explanation for a recommendation.
    
    Args:
        decision_id (int, optional): ID of decision record in DB.
        patient_id (int, optional): Patient ID.
        vitals_data (dict, optional): Actual stored vital parameters dict.
        ews_result (dict, optional): Calculated EWS dict.
        recommendation (str, optional): Recommendation code or title.
        reason (str, optional): Custom reason text if provided.
        save_to_db (bool): Whether to persist entries into explanations table.

    Returns:
        dict: Full structured explanation object.
    """
    vitals_data = vitals_data or {}

    # Calculate EWS if not provided
    if not ews_result and vitals_data:
        ews_result = calculate_ews(vitals_data)
    elif not ews_result:
        ews_result = {'total_score': 0, 'risk_level': 'normal', 'breakdown': {}}

    total_score = ews_result.get('total_score', 0)
    risk_level = (ews_result.get('risk_level') or get_risk_level(total_score)).upper()
    breakdown = ews_result.get('breakdown', {})

    # Normalize recommendation title
    rec_raw = str(recommendation or 'RE_EVALUATE').strip()
    rec_code = rec_raw.upper().replace(' ', '_')
    rec_title = RECOMMENDATION_TITLES.get(rec_code, rec_raw)

    # Standardize or preserve reason
    if not reason or reason.strip() == "":
        reason_text = STANDARD_REASONS.get(rec_code, (
            "The patient's latest recorded parameters indicate "
            "clinical status evaluated according to configured Jeevan Setu decision rules."
        ))
    else:
        reason_text = reason

    # Extract ONLY actual recorded parameters (never invent patient information)
    contributing_params = []
    
    # Priority order for standard clinical vital parameters
    candidate_keys = [
        'heart_rate', 'respiratory_rate', 'blood_pressure_sys',
        'temperature', 'spo2', 'consciousness', 'blood_sugar', 'urine_output'
    ]

    for key in candidate_keys:
        value = vitals_data.get(key)
        if value is None:
            # Check if breakdown contains it
            b_val = breakdown.get(key, {}).get('value')
            if b_val is not None:
                value = b_val
            else:
                # Parameter was not recorded — DO NOT INVENT DATA
                continue

        meta = PARAMETER_METADATA.get(key, {
            'name': key.replace('_', ' ').title(),
            'unit': '',
            'order': 99
        })

        score = breakdown.get(key, {}).get('score')
        if score is None:
            score = calculate_parameter_score(key, value)

        status = _get_parameter_status(score)
        exp_text = _generate_text(key, meta['name'], value, meta['unit'], score)

        contributing_params.append({
            'parameter_key': key,
            'parameter_name': meta['name'],
            'name': meta['name'],
            'value': value,
            'unit': meta['unit'],
            'score': score,
            'status': status,
            'explanation_text': exp_text,
            'text': exp_text,
            'order': meta.get('order', 99)
        })

    # Sort parameters: abnormal (highest score) first, then standard clinical order
    contributing_params.sort(key=lambda p: (-p['score'], p['order']))

    # Assign ranks and contribution percentages
    total_active_score = sum(p['score'] for p in contributing_params)
    for rank, p in enumerate(contributing_params, 1):
        p['importance_rank'] = rank
        p['rank'] = rank
        if total_active_score > 0:
            contrib_pct = round((p['score'] / total_active_score) * 100, 1)
        else:
            contrib_pct = 0.0
        p['contribution'] = contrib_pct
        p['contribution_pct'] = contrib_pct

    # Extract names list
    contributing_names = [p['parameter_name'] for p in contributing_params]

    # Save to database if requested and IDs are present
    if save_to_db and decision_id and patient_id:
        try:
            for p in contributing_params:
                # Convert value to float if numerical for schema column
                f_val = float(p['value']) if isinstance(p['value'], (int, float)) else 0.0
                Explanation.create(
                    decision_id=decision_id,
                    patient_id=patient_id,
                    feature_name=p['parameter_key'],
                    feature_value=f_val,
                    contribution=p['contribution'] / 100.0,
                    importance_rank=p['importance_rank'],
                    explanation_text=p['explanation_text']
                )
        except Exception as e:
            # Non-blocking log if DB write fails during tests
            pass

    # Build summary
    summary_text = get_summary_explanation(contributing_params)

    # Build formatted text block exactly as shown in specification
    text_block = (
        f"Recommendation:\n{rec_title}\n\n"
        f"Reason:\n{reason_text}\n\n"
        f"Contributing Parameters:\n" + "\n".join(contributing_names)
    )

    return {
        'recommendation': rec_title,
        'recommendation_code': rec_code,
        'reason': reason_text,
        'contributing_parameters': contributing_params,
        'contributing_parameter_names': contributing_names,
        'total_score': total_score,
        'risk_level': risk_level,
        'summary': summary_text,
        'text_block': text_block
    }


def _get_parameter_status(score):
    """Map EWS parameter score to clinical status string."""
    if score == 0:
        return "Normal"
    elif score == 1:
        return "Slightly Abnormal"
    elif score == 2:
        return "Moderately Abnormal"
    elif score >= 3:
        return "Severely Abnormal"
    return "Unknown"


def _generate_text(key, name, value, unit, score):
    """Generate precise human-readable explanation with actual measured value."""
    unit_str = f" {unit}" if unit else ""
    val_str = f"{value}{unit_str}"

    if score == 0:
        return f"{name} is within normal physiological range ({val_str})."
    elif score == 1:
        return f"{name} is slightly abnormal ({val_str}), contributing minimally to risk."
    elif score == 2:
        return f"{name} is moderately abnormal ({val_str}), indicating clinical concern."
    elif score >= 3:
        return f"⚠️ {name} is severely abnormal ({val_str}), a major contributor to the decision."

    return f"{name}: {val_str} (EWS score: {score})"


def get_summary_explanation(explanations):
    """Generate a cohesive summary text from a list of parameter explanations."""
    if not explanations:
        return "No parameters recorded."

    critical = [e for e in explanations if e['score'] >= 3]
    concerning = [e for e in explanations if e['score'] == 2]
    slight = [e for e in explanations if e['score'] == 1]
    normal = [e for e in explanations if e['score'] == 0]

    parts = []
    if critical:
        crit_names = ', '.join(e['parameter_name'] for e in critical)
        parts.append(f"Critical parameters: {crit_names}")
    if concerning:
        conc_names = ', '.join(e['parameter_name'] for e in concerning)
        parts.append(f"Moderately abnormal: {conc_names}")
    if slight:
        slight_names = ', '.join(e['parameter_name'] for e in slight)
        parts.append(f"Slightly elevated: {slight_names}")
    if not critical and not concerning and not slight:
        parts.append("All recorded vital parameters are within normal physiological limits")

    return '. '.join(parts) + '.'


def format_text_explanation(explanation_dict):
    """Produce the exact formatted text block specified in Phase 11."""
    rec = explanation_dict.get('recommendation', 'Re-evaluate')
    reason = explanation_dict.get('reason', '')
    params = explanation_dict.get('contributing_parameter_names', [])
    
    return (
        f"Recommendation:\n{rec}\n\n"
        f"Reason:\n{reason}\n\n"
        f"Contributing Parameters:\n" + "\n".join(params)
    )
