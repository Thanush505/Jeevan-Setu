"""
utils/validators.py — Input validation utilities.
"""

import re


def validate_patient_data(data):
    """Validate patient registration data."""
    errors = []

    if not data.get('name') or len(data['name'].strip()) < 2:
        errors.append('Patient name is required (min 2 characters).')

    age = data.get('age')
    if age is None:
        errors.append('Age is required.')
    elif not isinstance(age, int) or age < 0 or age > 150:
        errors.append('Age must be between 0 and 150.')

    if data.get('gender') not in ('Male', 'Female', 'Other'):
        errors.append('Gender must be Male, Female, or Other.')

    if data.get('ward_type') not in ('ICU', 'HDU', 'General'):
        errors.append('Ward type must be ICU, HDU, or General.')

    return errors


def validate_vitals_data(data):
    """Validate vital sign data and clinically acceptable ranges (4 core parameters)."""
    errors = []
    ranges = {
        'heart_rate': (20, 300, 'Heart Rate'),
        'blood_pressure_sys': (40, 300, 'Systolic BP'),
        'respiratory_rate': (4, 80, 'Respiratory Rate'),
        'temperature': (25.0, 45.0, 'Temperature'),
    }

    provided_count = 0
    for field, (low, high, name) in ranges.items():
        value = data.get(field)
        if value is None and field == 'blood_pressure_sys':
            value = data.get('systolic_bp')
        if value is not None and value != '':
            provided_count += 1
            try:
                val = float(value)
                if val < low or val > high:
                    errors.append(f'{name} must be between {low} and {high}.')
            except (ValueError, TypeError):
                errors.append(f'{name} must be a valid number.')

    if provided_count == 0:
        errors.append('At least one vital sign measurement must be provided.')

    return errors


def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username):
    """Validate username format (alphanumeric, 3-50 chars)."""
    pattern = r'^[a-zA-Z0-9_]{3,50}$'
    return bool(re.match(pattern, username))


def sanitize_string(value):
    """Sanitize a string input (strip and limit length)."""
    if not isinstance(value, str):
        return ''
    return value.strip()[:500]
