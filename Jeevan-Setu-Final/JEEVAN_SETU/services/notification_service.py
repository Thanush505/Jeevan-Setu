"""
services/notification_service.py — Backend event-driven notification & alert dispatcher.

Handles dispatching:
- CRITICAL_VITAL (Severity: CRITICAL)
- TRANSFER_READY (Severity: TRANSFER)
- ESCALATION (Severity: CRITICAL)
- SYSTEM (Severity: INFO / WARNING)
"""

from models.notification_model import Notification
from models.alert_model import Alert
from models.patient_model import Patient


class NotificationService:
    """Dispatches real-time clinical notifications and alerts triggered by backend events."""

    @staticmethod
    def trigger_critical_vital(patient_id, parameter, value, threshold=None, ews_score=None):
        """
        Trigger CRITICAL_VITAL alert when a patient's vital signs breach danger thresholds.
        Broadcasts to all attending nurses, doctors, and records an active alert.
        """
        patient = Patient.get_by_id(patient_id)
        p_name = patient.get('name') if patient else f"Patient #{patient_id}"
        ward = patient.get('ward_type') if patient else 'ICU'
        bed = patient.get('bed_number') if patient else 'N/A'

        param_display = parameter.replace('_', ' ').title()
        title = f"CRITICAL_VITAL: {param_display} Alert ({p_name})"
        message = (
            f"Critical vital breached for {p_name} in {ward} (Bed {bed}). "
            f"{param_display}: {value} (Threshold: {threshold or 'Severe'}). "
            f"EWS Score: {ews_score if ews_score is not None else 'Elevated'}."
        )

        # 1. Record in alerts table
        alert_id = Alert.create(
            patient_id=patient_id,
            alert_type='critical',
            title=f"Critical {param_display} Threshold Exceeded",
            message=message,
            parameter=parameter,
            value=float(value) if isinstance(value, (int, float)) else None,
            threshold=float(threshold) if isinstance(threshold, (int, float)) else None
        )

        # 2. Broadcast in-app notification to all clinical staff
        Notification.broadcast_to_all_staff(
            title=title,
            message=message,
            notif_type='CRITICAL_VITAL',
            patient_id=patient_id,
            severity='CRITICAL'
        )

        return {
            'event': 'CRITICAL_VITAL',
            'severity': 'CRITICAL',
            'alert_id': alert_id,
            'title': title,
            'message': message
        }

    @staticmethod
    def trigger_transfer_ready(patient_id, from_ward, to_ward, recommendation_id=None, score=None):
        """
        Trigger TRANSFER_READY notification when clinical decision engine suggests step-down or transfer.
        """
        patient = Patient.get_by_id(patient_id)
        p_name = patient.get('name') if patient else f"Patient #{patient_id}"

        title = f"TRANSFER_READY: {p_name} ({from_ward} → {to_ward})"
        message = (
            f"Patient {p_name} is clinically stable and ready for step-down transfer "
            f"from {from_ward} to {to_ward} (EWS = {score if score is not None else 'Normal'}). "
            f"Doctor review & authorization required."
        )

        # Broadcast to doctors for authorization and nurses for transfer prep
        Notification.broadcast_to_role(
            role='doctor',
            title=title,
            message=message,
            notif_type='TRANSFER_READY',
            patient_id=patient_id,
            severity='TRANSFER'
        )
        Notification.broadcast_to_role(
            role='nurse',
            title=title,
            message=message,
            notif_type='TRANSFER_READY',
            patient_id=patient_id,
            severity='TRANSFER'
        )

        return {
            'event': 'TRANSFER_READY',
            'severity': 'TRANSFER',
            'title': title,
            'message': message
        }

    @staticmethod
    def trigger_escalation(patient_id, from_ward, to_ward='ICU', reason=None, score=None):
        """
        Trigger ESCALATION notification when clinical decision engine detects urgent deterioration.
        """
        patient = Patient.get_by_id(patient_id)
        p_name = patient.get('name') if patient else f"Patient #{patient_id}"

        title = f"ESCALATION: Emergency ICU Transfer ({p_name})"
        message = (
            f"URGENT: Patient {p_name} deteriorating in {from_ward} (EWS = {score if score is not None else 'Critical'}). "
            f"Immediate emergency escalation to {to_ward} required. "
            f"Clinical Reason: {reason or 'Acute physiological deterioration'}."
        )

        # 1. Record alert
        Alert.create(
            patient_id=patient_id,
            alert_type='critical',
            title=f"Urgent ICU Escalation for {p_name}",
            message=message
        )

        # 2. Broadcast to all doctors & nurses
        Notification.broadcast_to_all_staff(
            title=title,
            message=message,
            notif_type='ESCALATION',
            patient_id=patient_id,
            severity='CRITICAL'
        )

        return {
            'event': 'ESCALATION',
            'severity': 'CRITICAL',
            'title': title,
            'message': message
        }

    @staticmethod
    def trigger_system_event(title, message, severity='INFO', target_role=None, user_id=None):
        """
        Trigger SYSTEM broadcast or targeted notification.
        """
        sev = str(severity).upper()
        if sev not in ('INFO', 'WARNING', 'CRITICAL', 'TRANSFER'):
            sev = 'INFO'

        if user_id:
            Notification.create(
                user_id=user_id,
                title=title,
                message=message,
                notif_type='SYSTEM',
                severity=sev
            )
        elif target_role:
            Notification.broadcast_to_role(
                role=target_role,
                title=title,
                message=message,
                notif_type='SYSTEM',
                severity=sev
            )
        else:
            Notification.broadcast_to_all_staff(
                title=title,
                message=message,
                notif_type='SYSTEM',
                severity=sev
            )

        return {
            'event': 'SYSTEM',
            'severity': sev,
            'title': title,
            'message': message
        }
