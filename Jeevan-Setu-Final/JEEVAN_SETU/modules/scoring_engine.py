"""
modules/scoring_engine.py — Early Warning Score (EWS) calculation engine.

The EWS is calculated from vital signs to identify patients at risk of
clinical deterioration. Each parameter is scored 0-3 and summed.
"""


# EWS scoring ranges for each vital parameter (4 core parameters)
EWS_RANGES = {
    'heart_rate': [
        (0, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1),
        (111, 130, 2), (131, 999, 3)
    ],
    'blood_pressure_sys': [
        (0, 70, 3), (71, 80, 2), (81, 100, 1), (101, 199, 0), (200, 999, 3)
    ],
    'respiratory_rate': [
        (0, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2), (25, 999, 3)
    ],
    'temperature': [
        (0, 35.0, 3), (35.1, 36.0, 1), (36.1, 38.0, 0),
        (38.1, 39.0, 1), (39.1, 99, 2)
    ]
}


def calculate_parameter_score(parameter, value):
    """Calculate EWS score for a single vital parameter."""
    if value is None:
        return 0

    ranges = EWS_RANGES.get(parameter)
    if not ranges:
        return 0

    for low, high, score in ranges:
        if low <= value <= high:
            return score
    return 0


def calculate_ews(vitals_data):
    """
    Calculate the total Early Warning Score from 4 vital signs.

    Args:
        vitals_data (dict): Dictionary containing vital sign values.

    Returns:
        dict: Total EWS score and breakdown by parameter.
    """
    parameters = ['heart_rate', 'blood_pressure_sys', 'respiratory_rate', 'temperature']

    breakdown = {}
    total_score = 0

    for param in parameters:
        value = vitals_data.get(param)
        score = calculate_parameter_score(param, value)
        breakdown[param] = {
            'value': value,
            'score': score
        }
        total_score += score

    return {
        'total_score': total_score,
        'risk_level': get_risk_level(total_score),
        'breakdown': breakdown
    }


def get_risk_level(score):
    """Determine risk level based on EWS score."""
    if score >= 7:
        return 'critical'
    elif score >= 5:
        return 'high'
    elif score >= 3:
        return 'medium'
    elif score >= 1:
        return 'low'
    else:
        return 'normal'


def get_risk_color(risk_level):
    """Get the display color for a risk level."""
    colors = {
        'critical': '#dc3545',  # Red
        'high': '#fd7e14',      # Orange
        'medium': '#ffc107',    # Yellow
        'low': '#28a745',       # Green
        'normal': '#6c757d'     # Gray
    }
    return colors.get(risk_level, '#6c757d')
