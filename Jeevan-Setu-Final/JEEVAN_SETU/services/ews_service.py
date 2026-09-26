"""
services/ews_service.py — Dedicated EWS (Early Warning Score) calculation service.

Provides the 4-parameter clinical scoring interface for the Core Clinical Data Flow:
    - Respiratory Rate
    - Heart Rate
    - Systolic Blood Pressure
    - Temperature

Delegates to the approved scoring thresholds in modules/scoring_engine.py.
Does NOT duplicate or invent clinical thresholds.
"""

from modules.scoring_engine import calculate_parameter_score, EWS_RANGES


def calculate_respiratory_rate_score(value):
    """
    Calculate EWS score for Respiratory Rate (breaths/min).
    Uses approved thresholds from scoring_engine.EWS_RANGES['respiratory_rate'].

    Returns:
        int: Score 0–3
    """
    if value is None:
        return 0
    return calculate_parameter_score('respiratory_rate', float(value))


def calculate_heart_rate_score(value):
    """
    Calculate EWS score for Heart Rate (bpm).
    Uses approved thresholds from scoring_engine.EWS_RANGES['heart_rate'].

    Returns:
        int: Score 0–3
    """
    if value is None:
        return 0
    return calculate_parameter_score('heart_rate', float(value))


def calculate_systolic_bp_score(value):
    """
    Calculate EWS score for Systolic Blood Pressure (mmHg).
    Uses approved thresholds from scoring_engine.EWS_RANGES['blood_pressure_sys'].

    Returns:
        int: Score 0–3
    """
    if value is None:
        return 0
    return calculate_parameter_score('blood_pressure_sys', float(value))


def calculate_temperature_score(value):
    """
    Calculate EWS score for Temperature (°C).
    Uses approved thresholds from scoring_engine.EWS_RANGES['temperature'].

    Returns:
        int: Score 0–3
    """
    if value is None:
        return 0
    return calculate_parameter_score('temperature', float(value))


def calculate_ews(respiratory_rate, heart_rate, systolic_bp, temperature):
    """
    Calculate the complete EWS from the four core vital parameters.

    Args:
        respiratory_rate (float): Breaths per minute.
        heart_rate (float): Beats per minute.
        systolic_bp (float): Systolic blood pressure in mmHg.
        temperature (float): Body temperature in °C.

    Returns:
        dict: Structured EWS result containing:
            - respiratory_rate_score (int)
            - heart_rate_score (int)
            - systolic_bp_score (int)
            - temperature_score (int)
            - total_score (int)
            - abnormal_parameters (list[dict]): Parameters with score > 0
    """
    rr_score = calculate_respiratory_rate_score(respiratory_rate)
    hr_score = calculate_heart_rate_score(heart_rate)
    bp_score = calculate_systolic_bp_score(systolic_bp)
    temp_score = calculate_temperature_score(temperature)

    total_score = rr_score + hr_score + bp_score + temp_score

    # Identify abnormal parameters (score > 0)
    abnormal_parameters = []
    param_details = [
        ('respiratory_rate', 'Respiratory Rate', respiratory_rate, rr_score, 'breaths/min'),
        ('heart_rate', 'Heart Rate', heart_rate, hr_score, 'bpm'),
        ('systolic_bp', 'Systolic BP', systolic_bp, bp_score, 'mmHg'),
        ('temperature', 'Temperature', temperature, temp_score, '°C'),
    ]
    for key, name, value, score, unit in param_details:
        if score > 0:
            abnormal_parameters.append({
                'parameter': key,
                'name': name,
                'value': value,
                'score': score,
                'unit': unit
            })

    return {
        'respiratory_rate_score': rr_score,
        'heart_rate_score': hr_score,
        'systolic_bp_score': bp_score,
        'temperature_score': temp_score,
        'total_score': total_score,
        'abnormal_parameters': abnormal_parameters
    }
