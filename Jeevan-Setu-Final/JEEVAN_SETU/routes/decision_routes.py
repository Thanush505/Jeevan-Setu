"""
routes/decision_routes.py — Phase 10 & 11 Clinical Decision Engine REST APIs.
Endpoints:
    POST /decision/evaluate             (Evaluate EWS score and return clinical decision)
    GET  /decision/evaluate/{patient_id} (Evaluate latest vitals for a patient)
    POST /decision/approve/{id}         (Doctor approval with RBAC & Doctor-Patient assignment check)
    POST /decision/reject/{id}          (Doctor rejection with remarks & RBAC check)
    POST /decision/{id}/request-info    (Doctor request additional info from nursing staff)
    GET  /decision/pending              (Fetch pending approvals scoped to authenticated Doctor)
    GET  /decision/history/{patient_id} (Patient recommendation history)
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from services.decision_service import evaluate, get_risk_level_from_condition, get_alert_type_from_condition
from models.recommendation_model import Recommendation
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.audit_log_model import AuditLog
from models.notification_model import Notification
from database.db import db
from utils.decorators import permission_required, role_required, get_current_authenticated_user

decision_bp = Blueprint('decision', __name__)


def format_waiting_time(created_at):
    """Format elapsed waiting time from datetime created_at."""
    if not created_at:
        return 0, 'Just now', '-120m SLA'
    now = datetime.now()
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except Exception:
            return 0, 'Just now', '-120m SLA'
    diff_minutes = max(0, int((now - created_at).total_seconds() / 60))
    if diff_minutes < 1:
        formatted = 'Just now'
    elif diff_minutes < 60:
        formatted = f'{diff_minutes}m ago'
    elif diff_minutes < 1440:
        hours = diff_minutes // 60
        mins = diff_minutes % 60
        formatted = f'{hours}h {mins}m ago' if mins > 0 else f'{hours}h ago'
    else:
        days = diff_minutes // 1440
        formatted = f'{days}d ago'

    remaining_sla = 120 - diff_minutes
    if remaining_sla > 0:
        sla = f'-{remaining_sla}m SLA'
    else:
        sla = 'SLA Expired'
    return diff_minutes, formatted, sla


# ─────────────────────────────────────────────────────────────
# 1. POST /decision/evaluate & GET /decision/evaluate/{patient_id}
# ─────────────────────────────────────────────────────────────
@decision_bp.route('/evaluate', methods=['POST'])
@permission_required('view_decisions')
def evaluate_decision():
    """Evaluate clinical decision based on submitted EWS score."""
    data = request.get_json(silent=True) or {}
    total_score = data.get('total_score') or data.get('score') or data.get('ews_score')
    patient_id = data.get('patient_id')

    if total_score is None and patient_id:
        latest = Vitals.get_latest(patient_id)
        if latest:
            total_score = latest.get('ews_score', 0)
        else:
            patient = Patient.get_by_id(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404
            total_score = patient.get('ews_score', 0) or 0

    if total_score is None:
        return jsonify({'success': False, 'error': 'Missing total_score or patient_id parameter'}), 400

    try:
        total_score = int(total_score)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'total_score must be an integer'}), 400

    decision = evaluate(total_score)
    risk_level = get_risk_level_from_condition(decision['condition'])
    alert_type = get_alert_type_from_condition(decision['condition'])

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'total_score': total_score,
        'condition': decision['condition'],
        'recommendation': decision['recommendation'],
        'risk_level': risk_level,
        'alert_type': alert_type
    }), 200


@decision_bp.route('/evaluate/<int:patient_id>', methods=['GET'])
@permission_required('view_decisions')
def evaluate_patient_decision(patient_id):
    """Evaluate clinical decision for a specific patient using latest vitals."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    latest = Vitals.get_latest(patient_id)
    score = latest.get('ews_score', 0) if latest else (patient.get('ews_score', 0) or 0)

    decision = evaluate(score)
    risk_level = get_risk_level_from_condition(decision['condition'])
    alert_type = get_alert_type_from_condition(decision['condition'])

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'patient_name': patient.get('name'),
        'total_score': score,
        'condition': decision['condition'],
        'recommendation': decision['recommendation'],
        'risk_level': risk_level,
        'alert_type': alert_type
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. POST /decision/approve/{id} & /decision/reject/{id}
# ─────────────────────────────────────────────────────────────
@decision_bp.route('/approve/<int:recommendation_id>', methods=['POST'])
def approve_decision(recommendation_id):
    """
    Approve clinical recommendation (Doctor / Admin only).
    Enforces Doctor-patient assignment (prevents cross-doctor IDOR).
    Rejects Nurse approval attempts with HTTP 403.
    Rejects stale approvals if patient condition is no longer Ready-to-Transfer.
    """
    user = get_current_authenticated_user()
    if not user or not getattr(user, 'is_authenticated', True):
        return jsonify({'success': False, 'error': 'Authentication required. Please provide a valid Bearer token.'}), 401

    user_role = getattr(user, 'role', '').lower()
    user_id = getattr(user, 'id', getattr(user, 'user_id', None))

    # 1. Strict RBAC Enforcement: Nurse cannot approve transfers/decisions
    if user_role == 'nurse':
        AuditLog.log(
            action='UNAUTHORIZED_DECISION_APPROVAL_ATTEMPT',
            user_id=user_id,
            entity_type='recommendation',
            entity_id=recommendation_id,
            new_value={'role': user_role, 'attempted_action': 'approve_decision'},
            ip_address=request.remote_addr,
            description=f"Security Alert: Nurse {getattr(user, 'full_name', 'Unknown')} unauthorized attempt to approve recommendation #{recommendation_id}"
        )
        return jsonify({
            'success': False,
            'error': 'Permission denied: Access forbidden. Nurses are not authorized to approve clinical recommendations or transfers. Only attending Doctors or Administrators can approve.'
        }), 403

    if user_role not in ('doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Access forbidden: Insufficient role permissions.'}), 403

    rec = Recommendation.get_by_id(recommendation_id)
    if not rec:
        return jsonify({'success': False, 'error': f'Recommendation with ID {recommendation_id} not found'}), 404

    # Check stale status
    if rec.get('status') != 'pending':
        return jsonify({
            'success': False,
            'error': f'This transfer recommendation is no longer pending approval (current status: {rec.get("status")}).'
        }), 409

    patient_id = rec.get('patient_id')
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    # 2. Strict Cross-Doctor Authorization (IDOR Prevention):
    # Attending Doctor must be assigned to this patient (Admins can override)
    if user_role == 'doctor' and patient.get('assigned_doctor') and int(patient.get('assigned_doctor')) != int(user_id):
        AuditLog.log(
            action='UNAUTHORIZED_CROSS_DOCTOR_APPROVAL_ATTEMPT',
            user_id=user_id,
            entity_type='recommendation',
            entity_id=recommendation_id,
            new_value={'attempted_by_doctor_id': user_id, 'assigned_doctor_id': patient.get('assigned_doctor')},
            ip_address=request.remote_addr,
            description=f"Security Alert: Dr. {getattr(user, 'full_name', 'Unknown')} attempted unauthorized approval for Patient {patient.get('name')} assigned to another doctor."
        )
        return jsonify({
            'success': False,
            'error': 'Permission denied: Access forbidden. You are only authorized to approve transfers for your assigned patients.'
        }), 403

    # 3. Stale State Protection: Verify current patient clinical condition
    current_ews = patient.get('ews_score', 0) or 0
    decision = evaluate(current_ews)
    current_condition = decision.get('condition')

    # If recommendation is transfer to HDU but patient condition is no longer Stable:
    if 'HDU' in str(rec.get('recommendation_text', '')) and current_condition != 'Stable':
        AuditLog.log(
            action='DECISION_APPROVAL_REJECTED_STALE',
            user_id=user_id,
            entity_type='recommendation',
            entity_id=recommendation_id,
            new_value={'current_ews': current_ews, 'current_condition': current_condition},
            ip_address=request.remote_addr,
            description=f"Recommendation #{recommendation_id} approval rejected: Patient {patient.get('name')} condition changed to {current_condition} (EWS {current_ews})"
        )
        return jsonify({
            'success': False,
            'error': "Transfer approval is no longer valid because the patient's current clinical status has changed."
        }), 409

    # 4. Perform atomic approval transaction
    Recommendation.update_status(recommendation_id, status='approved', decided_by=user_id)

    # Sync any linked transfer record
    db.execute_query(
        """UPDATE transfers 
           SET status = 'approved', approved_by = %s, completed_at = NOW(), updated_at = NOW()
           WHERE (recommendation_id = %s OR patient_id = %s) AND status = 'pending'""",
        (user_id, recommendation_id, patient_id)
    )

    # Acknowledge / resolve any pending transfer alerts for this patient
    db.execute_query(
        """UPDATE alerts SET is_acknowledged = TRUE, acknowledged_by = %s, acknowledged_at = NOW()
           WHERE patient_id = %s AND parameter = 'transfer_pending' AND is_acknowledged = FALSE""",
        (user_id, patient_id)
    )

    doctor_name = getattr(user, 'full_name', 'Doctor')
    AuditLog.log(
        action='approve_recommendation',
        user_id=user_id,
        entity_type='recommendation',
        entity_id=recommendation_id,
        new_value={'status': 'approved'},
        ip_address=request.remote_addr,
        description=f"Approved transfer recommendation #{recommendation_id} for patient {patient.get('name')} by Dr. {doctor_name}"
    )

    # 5. Notify Nurse of approval
    try:
        Notification.broadcast_to_role(
            role='nurse',
            title=f"[TRANSFER APPROVED] {patient.get('name')}",
            message=f"Transfer recommendation for {patient.get('name')} (#{patient.get('patient_code', '')}) has been approved by Dr. {doctor_name}.",
            notif_type='TRANSFER',
            patient_id=patient_id,
            severity='TRANSFER'
        )
    except Exception as e:
        print(f"[DECISION APPROVE] Warning broadcasting nurse notification: {e}")

    return jsonify({
        'success': True,
        'message': f"Transfer recommendation #{recommendation_id} for {patient.get('name')} approved successfully by Dr. {doctor_name}",
        'status': 'approved',
        'recommendation_id': recommendation_id
    }), 200


@decision_bp.route('/reject/<int:recommendation_id>', methods=['POST'])
def reject_decision(recommendation_id):
    """
    Reject clinical recommendation (Doctor / Admin only).
    Enforces Doctor-patient assignment (prevents cross-doctor IDOR).
    """
    user = get_current_authenticated_user()
    if not user or not getattr(user, 'is_authenticated', True):
        return jsonify({'success': False, 'error': 'Authentication required. Please provide a valid Bearer token.'}), 401

    user_role = getattr(user, 'role', '').lower()
    user_id = getattr(user, 'id', getattr(user, 'user_id', None))

    if user_role == 'nurse':
        return jsonify({
            'success': False,
            'error': 'Permission denied: Nurses are not authorized to reject transfer recommendations.'
        }), 403

    if user_role not in ('doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Access forbidden: Insufficient role permissions.'}), 403

    rec = Recommendation.get_by_id(recommendation_id)
    if not rec:
        return jsonify({'success': False, 'error': f'Recommendation with ID {recommendation_id} not found'}), 404

    if rec.get('status') != 'pending':
        return jsonify({
            'success': False,
            'error': f'This transfer recommendation is no longer pending (current status: {rec.get("status")}).'
        }), 409

    patient_id = rec.get('patient_id')
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    # Strict Cross-Doctor Authorization
    if user_role == 'doctor' and patient.get('assigned_doctor') and int(patient.get('assigned_doctor')) != int(user_id):
        AuditLog.log(
            action='UNAUTHORIZED_CROSS_DOCTOR_REJECT_ATTEMPT',
            user_id=user_id,
            entity_type='recommendation',
            entity_id=recommendation_id,
            new_value={'attempted_by_doctor_id': user_id, 'assigned_doctor_id': patient.get('assigned_doctor')},
            ip_address=request.remote_addr,
            description=f"Security Alert: Dr. {getattr(user, 'full_name', 'Unknown')} attempted unauthorized rejection for Patient {patient.get('name')} assigned to another doctor."
        )
        return jsonify({
            'success': False,
            'error': 'Permission denied: Access forbidden. You are only authorized to reject transfers for your assigned patients.'
        }), 403

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    remarks = data.get('remarks') or data.get('reason') or 'Rejected by attending doctor'

    # Update recommendation
    db.execute_query(
        """UPDATE recommendations 
           SET status = 'rejected', reason = %s, decided_by = %s, decided_at = NOW()
           WHERE recommendation_id = %s""",
        (remarks, user_id, recommendation_id)
    )

    # Update any linked transfer record
    db.execute_query(
        """UPDATE transfers 
           SET status = 'rejected', approved_by = %s, transfer_reason = CONCAT(COALESCE(transfer_reason, ''), ' | Rejection Remarks: ', %s), updated_at = NOW()
           WHERE (recommendation_id = %s OR patient_id = %s) AND status = 'pending'""",
        (user_id, remarks, recommendation_id, patient_id)
    )

    doctor_name = getattr(user, 'full_name', 'Doctor')
    AuditLog.log(
        action='reject_recommendation',
        user_id=user_id,
        entity_type='recommendation',
        entity_id=recommendation_id,
        new_value={'status': 'rejected', 'remarks': remarks},
        ip_address=request.remote_addr,
        description=f"Rejected transfer recommendation #{recommendation_id} for patient {patient.get('name')} by Dr. {doctor_name}. Remarks: {remarks}"
    )

    try:
        Notification.broadcast_to_role(
            role='nurse',
            title=f"[TRANSFER REJECTED] {patient.get('name')}",
            message=f"Transfer recommendation for {patient.get('name')} was rejected by Dr. {doctor_name}. Remarks: {remarks}",
            notif_type='TRANSFER',
            patient_id=patient_id,
            severity='WARNING'
        )
    except Exception as e:
        print(f"[DECISION REJECT] Warning broadcasting nurse notification: {e}")

    return jsonify({
        'success': True,
        'message': f"Transfer recommendation #{recommendation_id} for {patient.get('name')} rejected successfully",
        'status': 'rejected',
        'recommendation_id': recommendation_id
    }), 200


@decision_bp.route('/<int:recommendation_id>/request-info', methods=['POST'])
@decision_bp.route('/request-info/<int:recommendation_id>', methods=['POST'])
def request_info_decision(recommendation_id):
    """
    Doctor requests additional clinical information from nurses for a pending transfer.
    Enforces Doctor-patient authorization.
    Creates audit trail and broadcasts nurse notification.
    """
    user = get_current_authenticated_user()
    if not user or not getattr(user, 'is_authenticated', True):
        return jsonify({'success': False, 'error': 'Authentication required. Please provide a valid Bearer token.'}), 401

    user_role = getattr(user, 'role', '').lower()
    user_id = getattr(user, 'id', getattr(user, 'user_id', None))

    if user_role not in ('doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Access forbidden: Insufficient role permissions.'}), 403

    rec = Recommendation.get_by_id(recommendation_id)
    if not rec:
        return jsonify({'success': False, 'error': f'Recommendation with ID {recommendation_id} not found'}), 404

    patient_id = rec.get('patient_id')
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    # Strict Cross-Doctor Authorization
    if user_role == 'doctor' and patient.get('assigned_doctor') and int(patient.get('assigned_doctor')) != int(user_id):
        return jsonify({
            'success': False,
            'error': 'Permission denied: Access forbidden. You are only authorized to request information for your assigned patients.'
        }), 403

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    message = data.get('message') or data.get('inquiry') or 'Attending doctor requested additional clinical information and vitals verification.'

    doctor_name = getattr(user, 'full_name', 'Doctor')

    # Record notification for nurses
    try:
        Notification.broadcast_to_role(
            role='nurse',
            title=f"[INFO REQUEST] {patient.get('name')}",
            message=f"Dr. {doctor_name} requested clinical details for patient {patient.get('name')} (#{patient.get('patient_code', '')}): {message}",
            notif_type='ALERT',
            patient_id=patient_id,
            severity='INFO'
        )
    except Exception as e:
        print(f"[REQUEST INFO] Warning broadcasting notification: {e}")

    AuditLog.log(
        action='request_info',
        user_id=user_id,
        entity_type='recommendation',
        entity_id=recommendation_id,
        new_value={'message': message, 'patient_id': patient_id},
        ip_address=request.remote_addr,
        description=f"Dr. {doctor_name} requested clinical information for patient {patient.get('name')}: {message}"
    )

    return jsonify({
        'success': True,
        'message': f"Information request for {patient.get('name')} sent to attending nursing staff successfully.",
        'recommendation_id': recommendation_id,
        'patient_id': patient_id
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. GET /decision/pending & GET /decision/history/{patient_id}
# ─────────────────────────────────────────────────────────────
@decision_bp.route('/pending', methods=['GET'])
def get_pending_decisions():
    """
    Fetch pending approvals with strict Doctor-patient scoping.
    If authenticated user is a Doctor, returns ONLY records for patients assigned to that Doctor.
    If Admin, returns all pending records.
    Returns full clinical metadata, latest vitals, EWS trend, and readiness criteria.
    """
    user = get_current_authenticated_user()
    if not user or not getattr(user, 'is_authenticated', True):
        return jsonify({'success': False, 'error': 'Authentication required. Please provide a valid Bearer token.'}), 401

    user_role = getattr(user, 'role', '').lower()
    user_id = getattr(user, 'id', getattr(user, 'user_id', None))

    # Base query for pending recommendations
    query = """
        SELECT 
            r.recommendation_id,
            r.patient_id,
            r.vital_id,
            r.ews_id,
            r.from_ward,
            r.to_ward,
            r.score,
            r.confidence,
            r.recommendation_text,
            r.reason,
            r.status,
            r.created_at,
            p.name AS patient_name,
            p.patient_code,
            p.age,
            p.gender,
            p.ward_type,
            p.bed_number,
            p.diagnosis,
            p.assigned_doctor,
            u.full_name AS doctor_name,
            u.department AS doctor_department
        FROM recommendations r
        JOIN patients p ON r.patient_id = p.patient_id
        LEFT JOIN users u ON p.assigned_doctor = u.user_id
        WHERE r.status = 'pending' AND p.status = 'admitted'
    """
    params = []

    # Strict Doctor / Nurse Scoping
    if user_role == 'doctor':
        query += " AND p.assigned_doctor = %s"
        params.append(user_id)
    elif user_role == 'nurse':
        query += " AND p.assigned_nurse = %s"
        params.append(user_id)

    query += " ORDER BY r.created_at DESC"

    rows = db.execute_query(query, tuple(params) if params else None, fetch=True) or []

    # Enhance each item with latest vitals, EWS history, SLA, readiness, and transfer info
    enhanced = []
    for r in rows:
        pid = r['patient_id']
        
        # Latest Vitals
        latest_vital = Vitals.get_latest(pid) or {}
        
        # EWS History (last 10 records for trend)
        vitals_history = db.execute_query(
            """SELECT ews_score, recorded_at 
               FROM vitals 
               WHERE patient_id = %s 
               ORDER BY recorded_at DESC, vital_id DESC LIMIT 10""",
            (pid,), fetch=True
        ) or []
        # Chronological order for chart
        ews_history = list(reversed(vitals_history))

        # Waiting duration and SLA
        waiting_mins, waiting_str, sla_str = format_waiting_time(r['created_at'])

        # Persisted EWS score (use latest vital EWS if available, else recommendation score)
        current_ews = latest_vital.get('ews_score') if latest_vital.get('ews_score') is not None else (r.get('score') or 0)
        decision = evaluate(current_ews)
        condition_str = decision.get('condition', 'Stable')

        # Priority calculation
        if current_ews >= 5 or waiting_mins >= 60:
            priority = 'High Priority'
            priority_badge = 'HIGH_PRIORITY'
        elif current_ews >= 3:
            priority = 'Medium'
            priority_badge = 'MEDIUM'
        else:
            priority = 'Routine'
            priority_badge = 'ROUTINE'

        # Check linked transfer record
        tr_rec = db.execute_query(
            """SELECT transfer_id, from_ward, to_ward, from_bed_number, to_bed_number, transfer_reason, status, requested_by 
               FROM transfers 
               WHERE (recommendation_id = %s OR patient_id = %s) AND status = 'pending'
               ORDER BY created_at DESC LIMIT 1""",
            (r['recommendation_id'], pid), fetch=True
        )
        linked_transfer = tr_rec[0] if tr_rec else None

        # Clinical Readiness checks
        hr = latest_vital.get('heart_rate')
        sbp = latest_vital.get('blood_pressure_sys')
        rr = latest_vital.get('respiratory_rate')
        spo2 = latest_vital.get('spo2')

        is_hemo_stable = (hr is not None and 50 <= hr <= 110) and (sbp is None or (85 <= sbp <= 160))
        is_airway_stable = (spo2 is None or spo2 >= 94) and (rr is None or (10 <= rr <= 24))

        enhanced.append({
            'recommendation_id': r['recommendation_id'],
            'transfer_id': linked_transfer.get('transfer_id') if linked_transfer else None,
            'patient_id': pid,
            'patient_name': r['patient_name'],
            'patient_code': r['patient_code'] or f'UHID-2026-{pid:05d}',
            'age': r['age'] or '--',
            'gender': r['gender'] or 'Other',
            'ward_type': r['ward_type'] or r['from_ward'] or 'ICU',
            'bed_number': r['bed_number'] or '--',
            'diagnosis': r['diagnosis'] or 'Active Monitoring',
            'assigned_doctor': r['assigned_doctor'],
            'doctor_name': r['doctor_name'] or 'Attending Intensivist',
            'from_ward': r['from_ward'] or r['ward_type'] or 'ICU',
            'to_ward': r['to_ward'] or 'HDU',
            'type': 'Transfer',
            'approval_title': f"Transfer: {r.get('from_ward', 'ICU')} -> {r.get('to_ward', 'HDU')}",
            'recommendation_text': r['recommendation_text'] or f"Fit for {r.get('to_ward', 'HDU')} Transfer",
            'reason': r['reason'] or (linked_transfer.get('transfer_reason') if linked_transfer else None),
            'current_ews': current_ews,
            'condition': condition_str,
            'priority': priority,
            'priority_badge': priority_badge,
            'waiting_minutes': waiting_mins,
            'waiting_formatted': waiting_str,
            'sla_status': sla_str,
            'created_at': r['created_at'].isoformat() if hasattr(r['created_at'], 'isoformat') else str(r['created_at']),
            'latest_vitals': {
                'heart_rate': latest_vital.get('heart_rate'),
                'blood_pressure_sys': latest_vital.get('blood_pressure_sys'),
                'blood_pressure_dia': latest_vital.get('blood_pressure_dia'),
                'blood_pressure_str': f"{int(latest_vital.get('blood_pressure_sys'))}/{int(latest_vital.get('blood_pressure_dia'))}" if (latest_vital.get('blood_pressure_sys') and latest_vital.get('blood_pressure_dia')) else (f"{int(latest_vital.get('blood_pressure_sys'))}" if latest_vital.get('blood_pressure_sys') else '--'),
                'respiratory_rate': latest_vital.get('respiratory_rate'),
                'temperature': latest_vital.get('temperature'),
                'spo2': latest_vital.get('spo2'),
                'consciousness': latest_vital.get('consciousness', 'Alert'),
                'ews_score': current_ews,
                'recorded_at': latest_vital.get('recorded_at').isoformat() if hasattr(latest_vital.get('recorded_at'), 'isoformat') else str(latest_vital.get('recorded_at')) if latest_vital.get('recorded_at') else None
            },
            'ews_history': [
                {
                    'score': item['ews_score'],
                    'recorded_at': item['recorded_at'].isoformat() if hasattr(item['recorded_at'], 'isoformat') else str(item['recorded_at'])
                }
                for item in ews_history
            ],
            'readiness': {
                'hemodynamically_stable': bool(is_hemo_stable),
                'extubated_airway': bool(is_airway_stable),
                'bed_available': True,
                'nurse_handover_verified': False
            },
            'requested_by_name': r['doctor_name'] or 'Clinical Decision Engine'
        })

    return jsonify({
        'success': True,
        'count': len(enhanced),
        'doctor_id': user_id if user_role == 'doctor' else None,
        'doctor_name': getattr(user, 'full_name', None),
        'data': enhanced
    }), 200


@decision_bp.route('/history/<int:patient_id>', methods=['GET'])
@permission_required('view_decisions')
def get_patient_decision_history(patient_id):
    """Get recommendation history for a patient."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    history = Recommendation.get_by_patient(patient_id) if hasattr(Recommendation, 'get_by_patient') else None
    if history is None:
        history = db.execute_query(
            """SELECT r.*, u.full_name AS decided_by_name 
               FROM recommendations r
               LEFT JOIN users u ON r.decided_by = u.user_id
               WHERE r.patient_id = %s
               ORDER BY r.created_at DESC""",
            (patient_id,), fetch=True
        ) or []

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'count': len(history),
        'data': history
    }), 200
