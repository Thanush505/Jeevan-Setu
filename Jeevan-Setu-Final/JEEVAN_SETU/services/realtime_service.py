"""
services/realtime_service.py — Real-time data service layer.

Provides functions for fetching live patient data and pushing updates
via AJAX endpoints.
"""

from models.patient_model import Patient
from models.vitals_model import Vitals
from models.alert_model import Alert
from modules.scoring_engine import calculate_ews, get_risk_level


def get_dashboard_data():
    """
    Fetch all data needed for a real-time dashboard refresh.

    Returns:
        dict: Dashboard data including patients, vitals, alerts, and ward counts.
    """
    patients = Patient.get_all(status='admitted')
    active_alerts = Alert.get_active(limit=20)
    ward_counts = Patient.count_by_ward()
    critical_patients = Vitals.get_critical_patients()

    # Enrich patients with latest vitals
    enriched_patients = []
    for patient in patients:
        latest_vitals = Vitals.get_latest(patient['patient_id'])
        patient_data = dict(patient)
        if latest_vitals:
            patient_data['latest_vitals'] = latest_vitals
            patient_data['ews_score'] = latest_vitals.get('ews_score', 0)
            patient_data['risk_level'] = get_risk_level(latest_vitals.get('ews_score', 0))
        else:
            patient_data['latest_vitals'] = None
            patient_data['ews_score'] = 0
            patient_data['risk_level'] = 'normal'
        enriched_patients.append(patient_data)

    return {
        'patients': enriched_patients,
        'alerts': active_alerts,
        'ward_counts': ward_counts,
        'critical_patients': critical_patients,
        'total_patients': len(patients),
        'total_alerts': len(active_alerts)
    }


def get_patient_realtime(patient_id):
    """
    Get real-time data for a single patient.

    Args:
        patient_id (int): Patient ID.

    Returns:
        dict: Patient info with latest vitals and alerts.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return None

    vitals = Vitals.get_latest(patient_id)
    alerts = Alert.get_by_patient(patient_id)
    vitals_history = Vitals.get_history(patient_id, limit=12)

    return {
        'patient': patient,
        'vitals': vitals,
        'alerts': [a for a in alerts if not a.get('is_acknowledged')],
        'vitals_history': vitals_history
    }
