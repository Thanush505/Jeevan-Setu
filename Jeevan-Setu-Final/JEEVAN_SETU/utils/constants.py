"""
utils/constants.py — Application-wide thresholds, limits, and RBAC permissions.
"""

# =============================================
# VITAL SIGN THRESHOLDS (4 Core Parameters)
# =============================================
VITAL_THRESHOLDS = {
    'heart_rate': {
        'critical_low': 40,
        'warning_low': 50,
        'warning_high': 110,
        'critical_high': 130,
        'unit': 'bpm'
    },
    'blood_pressure_sys': {
        'critical_low': 70,
        'warning_low': 90,
        'warning_high': 180,
        'critical_high': 200,
        'unit': 'mmHg'
    },
    'respiratory_rate': {
        'critical_low': 8,
        'warning_low': 10,
        'warning_high': 24,
        'critical_high': 30,
        'unit': 'breaths/min'
    },
    'temperature': {
        'critical_low': 35.0,
        'warning_low': 36.0,
        'warning_high': 38.5,
        'critical_high': 39.5,
        'unit': '°C'
    },
}

# =============================================
# EWS (EARLY WARNING SCORE) LEVELS
# =============================================
EWS_LEVELS = {
    'normal': {'min': 0, 'max': 0, 'color': '#6c757d', 'label': 'Normal'},
    'low': {'min': 1, 'max': 2, 'color': '#28a745', 'label': 'Low Risk'},
    'medium': {'min': 3, 'max': 4, 'color': '#ffc107', 'label': 'Medium Risk'},
    'high': {'min': 5, 'max': 6, 'color': '#fd7e14', 'label': 'High Risk'},
    'critical': {'min': 7, 'max': 99, 'color': '#dc3545', 'label': 'Critical'},
}

# =============================================
# WARD CAPACITIES
# =============================================
WARD_CAPACITY = {
    'ICU': 20,
    'HDU': 30,
    'General': 100,
}

# =============================================
# SYSTEM LIMITS
# =============================================
MAX_VITALS_HISTORY = 500
MAX_ALERTS_DISPLAY = 100
MAX_REPORT_SIZE = 10 * 1024 * 1024  # 10 MB
SESSION_TIMEOUT_HOURS = 8
DEFAULT_PAGE_SIZE = 20

# =============================================
# ROLES & PERMISSIONS MATRIX (RBAC)
# =============================================
# 1. Administrator : Full system access
# 2. Doctor        : Clinical + transfer decisions, reports, diagnosis
# 3. Nurse         : Vitals + patient intake + alert monitoring
# 4. Attendant     : Read-only patient status access through QR / access code
ROLES = {
    'admin': [
        'all'
    ],
    'doctor': [
        'view_patients',
        'edit_patients',
        'view_vitals',
        'record_vitals',
        'view_decisions',
        'approve_decisions',
        'reject_decisions',
        'transfer_patients',
        'view_reports',
        'generate_reports',
        'view_alerts',
        'acknowledge_alerts',
        'use_chatbot',
        'view_explanations',
        'view_analytics'
    ],
    'nurse': [
        'view_patients',
        'edit_patients',
        'view_vitals',
        'record_vitals',
        'view_alerts',
        'acknowledge_alerts',
        'use_chatbot'
    ],
    'attendant': [
        'view_patient_status',
        'view_patient_vitals_summary'
    ],
}
