"""
routes/alert_routes.py — Alert management and Clinical Action routes.
Protected by RBAC: Alert viewing, acknowledgment, and clinical tasks for Clinical staff (Doctors, Nurses, Admins).
"""

from flask import Blueprint, request, render_template, jsonify
from models.alert_model import Alert
from models.patient_model import Patient
from models.audit_log_model import AuditLog
from database.db import db
from utils.decorators import permission_required, get_current_authenticated_user

alert_bp = Blueprint('alert', __name__)


@alert_bp.route('/')
@permission_required('view_alerts')
def alert_panel():
    """View all active alerts."""
    alerts = Alert.get_active()
    return render_template('Doctor/Doctor_alerts_notifications/Doctor_alerts_notifications.html', alerts=alerts)


@alert_bp.route('/api/active')
@permission_required('view_alerts')
def get_active_alerts():
    """API: Get all active (unacknowledged) alerts."""
    alerts = Alert.get_active()
    return jsonify({'success': True, 'data': alerts, 'count': len(alerts)})


@alert_bp.route('/api/acknowledged')
@permission_required('view_alerts')
def get_acknowledged_alerts():
    """API: Get acknowledged alerts."""
    alerts = Alert.get_acknowledged(limit=50)
    return jsonify({'success': True, 'data': alerts, 'count': len(alerts)})


@alert_bp.route('/api/patient/<int:patient_id>')
@permission_required('view_alerts')
def get_patient_alerts(patient_id):
    """API: Get alerts for a specific patient."""
    alerts = Alert.get_by_patient(patient_id)
    return jsonify({'success': True, 'data': alerts})


@alert_bp.route('/acknowledge/<int:alert_id>', methods=['POST'])
@permission_required('acknowledge_alerts')
def acknowledge_alert(alert_id):
    """Acknowledge an alert (Doctors, Nurses, and Admins)."""
    user = get_current_authenticated_user()
    user_id = user.id if user else 1
    Alert.acknowledge(alert_id, user_id)
    AuditLog.log('ACKNOWLEDGE_ALERT', user_id=user_id, entity_type='Alert', entity_id=alert_id, description=f'Alert #{alert_id} acknowledged by user {user_id}')
    return jsonify({'success': True, 'message': 'Alert acknowledged', 'alert_id': alert_id})


@alert_bp.route('/acknowledge-all-non-urgent', methods=['POST'])
@permission_required('acknowledge_alerts')
def acknowledge_all_non_urgent():
    """Acknowledge all active non-urgent alerts (medium, low, info)."""
    user = get_current_authenticated_user()
    user_id = user.id if user else 1
    Alert.acknowledge_all_non_urgent(user_id)
    AuditLog.log('ACKNOWLEDGE_ALL_NON_URGENT', user_id=user_id, entity_type='Alert', entity_id=None, description='All active non-urgent alerts acknowledged')
    return jsonify({'success': True, 'message': 'All non-urgent alerts acknowledged'})


@alert_bp.route('/api/count')
@permission_required('view_alerts')
def alert_count():
    """API: Get count of active alerts by type."""
    counts = Alert.get_count_by_type()
    return jsonify({'success': True, 'data': counts})


# ─────────────────────────────────────────────────────────────
# Global Alert & Transfer Feed for Doctor and Nurse Portals
# ─────────────────────────────────────────────────────────────
@alert_bp.route('/global-feed', methods=['GET'])
@alert_bp.route('/api/global-feed', methods=['GET'])
def get_global_alert_feed():
    """
    Universal real-time / polling feed for Doctor & Nurse global alert layers.
    Returns:
        1. Active CRITICAL Emergency Alerts (Doctor & Nurse scoped)
        2. Prolonged Ready-to-Transfer Alerts (Doctor actionable, Nurse view-only)
        3. Overall unread notification metrics
    """
    from modules.alert_engine import (
        check_and_generate_prolonged_transfer_alerts,
        get_active_transfer_alerts_for_user
    )
    from models.notification_model import Notification
    from datetime import datetime

    user = get_current_authenticated_user()
    if not user or not getattr(user, 'is_active', True):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    role = getattr(user, 'role', '').lower()
    user_id = getattr(user, 'id', getattr(user, 'user_id', None))

    # Attendants are strictly excluded from hospital-wide emergency & transfer alerts
    if role == 'attendant':
        return jsonify({
            'success': True,
            'role': 'attendant',
            'user_id': user_id,
            'emergency_alerts': [],
            'transfer_alerts': [],
            'unread_count': 0,
            'server_time': datetime.now().isoformat()
        }), 200

    # 1. Trigger detection of prolonged ready-to-transfer states
    try:
        check_and_generate_prolonged_transfer_alerts()
    except Exception as e:
        print(f"[GLOBAL FEED] Warning checking prolonged transfer: {e}")

    # 2. Get active CRITICAL emergency alerts scoped to user/patients
    emergency_alerts = Alert.get_active_emergency_for_user(user, limit=20)

    # 3. Get active Ready-to-Transfer alerts & recommendations
    transfer_alerts = get_active_transfer_alerts_for_user(user, limit=20)

    # 4. Get unread notifications count
    unread_notifs = Notification.get_unread_count(user_id) if user_id else len(emergency_alerts)

    return jsonify({
        'success': True,
        'user_id': user_id,
        'username': getattr(user, 'username', ''),
        'full_name': getattr(user, 'full_name', ''),
        'role': role,
        'can_approve_transfers': role in ('doctor', 'admin'),
        'unread_count': unread_notifs,
        'emergency_alerts_count': len(emergency_alerts),
        'transfer_alerts_count': len(transfer_alerts),
        'emergency_alerts': emergency_alerts,
        'transfer_alerts': transfer_alerts,
        'server_time': datetime.now().isoformat()
    }), 200


@alert_bp.route('/emergency/acknowledge/<int:alert_id>', methods=['POST', 'PUT'])
@permission_required('acknowledge_alerts')
def acknowledge_emergency_alert(alert_id):
    """Acknowledge a critical emergency alert."""
    user = get_current_authenticated_user()
    user_id = user.id if user else 1

    Alert.acknowledge(alert_id, user_id)
    AuditLog.log(
        'ACKNOWLEDGE_EMERGENCY_ALERT',
        user_id=user_id,
        entity_type='Alert',
        entity_id=alert_id,
        description=f"CRITICAL Emergency Alert #{alert_id} acknowledged by {getattr(user, 'full_name', f'User #{user_id}')} ({getattr(user, 'role', 'Staff')})"
    )
    return jsonify({
        'success': True,
        'message': f'Emergency alert #{alert_id} acknowledged successfully.',
        'alert_id': alert_id
    }), 200



@alert_bp.route('/api/today-tasks')
@permission_required('view_alerts')
def get_today_tasks():
    """API: Get active clinical tasks for admitted patients."""
    try:
        patients = Patient.get_all(status='admitted')
        tasks = []
        task_id = 1

        med_templates = [
            {'med': 'Meropenem 1g IV', 'route': 'IV Push', 'type': 'Medication', 'priority': 'high', 'due': 'In 15 mins', 'action': 'medication'},
            {'med': 'Metoprolol Tartrate 25mg', 'route': 'Oral (PO)', 'type': 'Medication', 'priority': 'medium', 'due': 'In 45 mins', 'action': 'medication'},
            {'med': 'Ceftriaxone 1g IV', 'route': 'IV Push', 'type': 'Medication', 'priority': 'medium', 'due': '14:00 PM', 'action': 'medication'},
            {'med': 'Pantoprazole 40mg IV', 'route': 'IV Bolus', 'type': 'Medication', 'priority': 'low', 'due': '16:00 PM', 'action': 'medication'}
        ]

        for p in patients:
            p_id = p['patient_id']
            p_name = p['name']
            p_bed = (p.get('ward_type') or 'ICU') + '-' + (p.get('bed_number') or '01')
            p_code = p.get('patient_code') or f'P{p_id:03d}'
            ews = p.get('ews_score', 0)

            # 1. Routine / Priority Vitals Task
            v_priority = 'high' if ews >= 5 else 'medium' if ews >= 3 else 'low'
            tasks.append({
                'task_id': task_id,
                'patient_id': p_id,
                'patient_name': p_name,
                'bed_number': p_bed,
                'patient_code': p_code,
                'title': f'Vitals Check (EWS: {ews})',
                'category': 'Vitals Monitoring',
                'priority': v_priority,
                'due_time': 'Hourly' if ews >= 5 else 'Every 4 Hours',
                'action_type': 'vitals',
                'status': 'pending'
            })
            task_id += 1

            # 2. Fluid Balance / I/O Task
            tasks.append({
                'task_id': task_id,
                'patient_id': p_id,
                'patient_name': p_name,
                'bed_number': p_bed,
                'patient_code': p_code,
                'title': 'Record Fluid Intake & Output (I/O)',
                'category': 'Fluid Balance',
                'priority': 'high' if ews >= 5 else 'medium',
                'due_time': 'Every 2 Hours',
                'action_type': 'io',
                'status': 'pending'
            })
            task_id += 1

            # 3. Scheduled Medication Task
            med_info = med_templates[(p_id - 1) % len(med_templates)]
            tasks.append({
                'task_id': task_id,
                'patient_id': p_id,
                'patient_name': p_name,
                'bed_number': p_bed,
                'patient_code': p_code,
                'title': f'Administer {med_info["med"]}',
                'category': 'Medication Administration',
                'priority': med_info['priority'],
                'due_time': med_info['due'],
                'action_type': 'medication',
                'medication_name': med_info['med'],
                'route': med_info['route'],
                'status': 'pending'
            })
            task_id += 1

        return jsonify({'success': True, 'data': tasks, 'count': len(tasks)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alert_bp.route('/api/medication/administer', methods=['POST'])
@permission_required('record_vitals')
def record_medication_admin():
    """Record medication administration for a patient."""
    user = get_current_authenticated_user()
    user_id = user.id if user else 1
    data = request.get_json() or {}

    patient_id = data.get('patient_id')
    medication_name = data.get('medication_name', '').strip()
    dosage = data.get('dosage', '').strip()
    route = data.get('route', 'IV Push')
    notes = data.get('notes', '')

    if not patient_id or not medication_name:
        return jsonify({'success': False, 'error': 'Patient ID and medication name are required.'}), 400

    # Verify patient exists
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    # Log into audit_logs and notifications
    AuditLog.log(
        'ADMINISTER_MEDICATION', user_id=user_id, entity_type='Patient', entity_id=patient_id,
        description=f'Administered {medication_name} ({dosage}, {route}) to Patient {patient["name"]} (#{patient["patient_code"]}). Notes: {notes}'
    )

    return jsonify({
        'success': True,
        'message': f'Medication {medication_name} recorded as administered successfully.',
        'data': {
            'patient_id': patient_id,
            'patient_name': patient['name'],
            'medication_name': medication_name,
            'dosage': dosage,
            'route': route,
            'administered_by': getattr(user, 'full_name', 'Sr. Nurse Priya') if user else 'Sr. Nurse Priya',
            'status': 'Administered'
        }
    })


@alert_bp.route('/api/io/record', methods=['POST'])
@permission_required('record_vitals')
def record_fluid_io():
    """Record fluid intake and output for a patient."""
    user = get_current_authenticated_user()
    user_id = user.id if user else 1
    data = request.get_json() or {}

    patient_id = data.get('patient_id')
    oral_intake = float(data.get('oral_intake', 0) or 0)
    iv_intake = float(data.get('iv_intake', 0) or 0)
    tube_intake = float(data.get('tube_intake', 0) or 0)
    
    urine_output = float(data.get('urine_output', 0) or 0)
    drain_output = float(data.get('drain_output', 0) or 0)
    vomitus_output = float(data.get('vomitus_output', 0) or 0)

    notes = data.get('notes', '')

    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID is required.'}), 400

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    total_intake = oral_intake + iv_intake + tube_intake
    total_output = urine_output + drain_output + vomitus_output
    net_balance = total_intake - total_output

    # Update patient vitals urine output if recorded
    if urine_output > 0:
        try:
            db.execute_query(
                "UPDATE vitals SET urine_output = %s WHERE patient_id = %s ORDER BY recorded_at DESC, vital_id DESC LIMIT 1",
                (urine_output, patient_id)
            )
        except Exception:
            pass

    net_balance_int = int(round(net_balance))
    net_str = f"+{net_balance_int}" if net_balance_int > 0 else str(net_balance_int)

    AuditLog.log(
        'RECORD_FLUID_IO', user_id=user_id, entity_type='Patient', entity_id=patient_id,
        description=f'Fluid I/O logged for {patient["name"]}: Total Intake {total_intake} mL, Total Output {total_output} mL, Net Balance {net_str} mL.'
    )

    return jsonify({
        'success': True,
        'message': f'Fluid I/O record saved. Net balance: {net_str} mL.',
        'data': {
            'patient_id': patient_id,
            'patient_name': patient['name'],
            'total_intake': total_intake,
            'total_output': total_output,
            'net_balance': net_balance_int,
            'recorded_by': getattr(user, 'full_name', 'Sr. Nurse Priya') if user else 'Sr. Nurse Priya'
        }
    })
