"""
services/decision_service.py — Clinical Decision Service for Jeevan Setu.

Implements the documented 3-tier total score decision rule:

    Total Score 0–2:  Condition = "Stable",        Recommendation = "Fit for HDU Transfer"
    Total Score 3–4:  Condition = "Moderate Risk",  Recommendation = "Re-evaluate"
    Total Score ≥5:   Condition = "Critical",       Recommendation = "Keep in ICU"

This module is intentionally separated from database and route logic
to keep clinical decision rules isolated and testable.
"""


def evaluate(total_score):
    """
    Determine patient condition and recommendation based on total EWS score.

    Args:
        total_score (int): The total Early Warning Score (sum of individual parameter scores).

    Returns:
        dict: Decision result containing:
            - condition (str): "Stable", "Moderate Risk", or "Critical"
            - recommendation (str): "Fit for HDU Transfer", "Re-evaluate", or "Keep in ICU"
    """
    total_score = max(0, int(total_score))

    if total_score <= 2:
        return {
            'condition': 'Stable',
            'recommendation': 'Fit for HDU Transfer'
        }
    elif total_score <= 4:
        return {
            'condition': 'Moderate Risk',
            'recommendation': 'Re-evaluate'
        }
    else:
        return {
            'condition': 'Critical',
            'recommendation': 'Keep in ICU'
        }


def get_risk_level_from_condition(condition):
    """
    Map the simplified condition string to the database risk_level ENUM.

    Args:
        condition (str): "Stable", "Moderate Risk", or "Critical"

    Returns:
        str: One of 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    """
    mapping = {
        'Stable': 'LOW',
        'Moderate Risk': 'MEDIUM',
        'Critical': 'CRITICAL'
    }
    return mapping.get(condition, 'LOW')


def get_alert_type_from_condition(condition):
    """
    Determine the alert type to generate based on condition.

    Args:
        condition (str): "Stable", "Moderate Risk", or "Critical"

    Returns:
        str or None: Alert type string, or None if no alert is needed.
    """
    if condition == 'Critical':
        return 'critical'
    elif condition == 'Moderate Risk':
        return 'high'
    return None
