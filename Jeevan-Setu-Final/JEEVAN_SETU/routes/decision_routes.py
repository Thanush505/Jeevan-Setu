"""
routes/decision_routes.py — Phase 10 Decision Engine REST APIs & Transfer Evaluation.
Endpoints:
    GET    /decision/evaluate/{patient_id} & /api/v1/decision/evaluate/{patient_id}
    POST   /decision/evaluate & /api/v1/decision/evaluate
    POST   /decision/approve/{recommendation_id} & /api/v1/decision/approve/{recommendation_id}
    POST   /decision/reject/{recommendation_id} & /api/v1/decision/reject/{recommendation_id}
    GET    /decision/pending & /api/v1/decision/pending
    GET    /decision/history/{patient_id} & /api/v1/decision/history/{patient_id}
"""

from flask import Blueprint, request, jsonify
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.recommendation_model import Recommendation
from models.decision_model import Decision
from models.audit_log_model import AuditLog
from modules.decision_engine import evaluate_decision, make_transfer_decision
from modules.explanation_engine import generate_explanation
from utils.decorators import permission_required, get_current_authenticated_user

decision_bp = Blueprint('decision', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET & POST /decision/evaluate — Evaluate Transfer Decision
# ─────────────────────────────────────────────────────────────
@decision_bp.route('/evaluate/<int:patient_id>', methods=['GET'])
@decision_bp.route('/evaluate/<int:patient_id>', methods=['GET'], endpoint='evaluate')
@permission_required('view_decisions')
def evaluate_patient_decision(patient_id):
    """Evaluate transfer recommendation for an admitted patient based on latest vitals."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    vitals = Vitals.get_latest(patient_id)
    if not vitals:
        return jsonify({'success': False, 'error': 'No vitals recorded for this patient yet'}), 404

    vitals_history = Vitals.get_history(patient_id, limit=10)

    # Execute pure decision engine
    decision = make_transfer_decision(patient, vitals, vitals_history)

    # Automatically persist to recommendations & decisions table
    user = get_current_authenticated_user()
    user_id = user.id if user else None

    rec_id = Recommendation.create(
        patient_id=patient_id,
        from_ward=decision['from_ward'],
        to_ward=decision['to_ward'],
        recommendation_text=decision['recommendation'],
        score=decision['score'],
        confidence=decision['confidence'],
        reason=decision['reason'],
        vital_id=vitals.get('vital_id'),
        status='pending'
    )
    decision['recommendation_id'] = rec_id

    dec_id = Decision.create(
        patient_id=patient_id,
        patient_name=patient.get('name') if patient else None,
        from_ward=decision['from_ward'],
        to_ward=decision['to_ward'],
        recommendation=decision['recommendation'],
        vital_id=vitals.get('vital_id'),
        ews_score=decision['score'],
        confidence=decision['confidence'],
        status='pending',
        decided_by=user_id
    )
    decision['decision_id'] = dec_id

    # Generate and store explanation records in database
    explanation = generate_explanation(
        decision_id=dec_id,
        patient_id=patient_id,
        vitals_data=vitals,
        recommendation=decision['recommendation'],
        reason=decision['reason'],
        save_to_db=True
    )
    decision['explanation'] = explanation
    decision['contributing_parameters'] = explanation['contributing_parameters']
    decision['contributing_parameter_names'] = explanation['contributing_parameter_names']

    return jsonify({
        'success': True,
        'data': decision
    }), 200



@decision_bp.route('/evaluate', methods=['POST'])
@permission_required('view_decisions')
def evaluate_custom_decision():
    """
    Directly evaluate clinical decision rules from payload.
    Payload:
        {
            "score": 7,
            "current_unit": "HDU",
            "vitals": { ... }
        }
    """
    data = request.get_json(silent=True) or {}
    score = data.get('score', 0)
    current_unit = data.get('current_unit') or data.get('ward_type', 'ICU')
    vitals_data = data.get('vitals')
    patient_id = data.get('patient_id')

    if patient_id:
        patient = Patient.get_by_id(int(patient_id))
        if not patient:
            return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404
        if not vitals_data:
            vitals_data = Vitals.get_latest(patient_id)
            if vitals_data and not score:
                score = vitals_data.get('ews_score', 0)
        current_unit = patient.get('ward_type', current_unit)

    decision = evaluate_decision(
        score=score,
        current_unit=current_unit,
        vitals_data=vitals_data
    )

    if patient_id:
        decision['patient_id'] = int(patient_id)
        # Record recommendation
        rec_id = Recommendation.create(
            patient_id=int(patient_id),
            from_ward=decision['from_ward'],
            to_ward=decision['to_ward'],
            recommendation_text=decision['recommendation'],
            score=decision['score'],
            confidence=decision['confidence'],
            reason=decision['reason'],
            status='pending'
        )
        decision['recommendation_id'] = rec_id

    return jsonify({
        'success': True,
        'data': decision
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. POST /decision/approve/{id} & /decision/reject/{id}
# ─────────────────────────────────────────────────────────────
@decision_bp.route('/approve/<int:recommendation_id>', methods=['POST'])
def approve_decision(recommendation_id):
    """
    Approve clinical recommendation (Doctor / Admin only).
    Rejects Nurse approval attempts with HTTP 403.
    Rejects stale approvals if patient condition is no longer Ready-to-Transfer.
    """
    from services.decision_service import evaluate
    from models.notification_model import Notification
    from models.alert_model import Alert
    from database.db import db

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

    patient_id = rec.get('patient_id')
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    # 2. Stale State Protection: Verify current patient clinical condition
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
            'error': "Transfer approval is no longer valid because the patient's current status has changed."
        }), 400

    Recommendation.update_status(recommendation_id, status='approved', decided_by=user_id)

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
        description=f"Approved transfer recommendation {recommendation_id} for patient {patient.get('name')} by Dr. {doctor_name}"
    )

    # 3. Notify Nurse
    try:
        Notification.broadcast_to_role(
            role='nurse',
            title=f"[TRANSFER APPROVED] {patient.get('name')}",
            message=f"Transfer recommendation for {patient.get('name')} has been approved by Dr. {doctor_name}.",
            notif_type='TRANSFER',
            patient_id=patient_id,
            severity='TRANSFER'
        )
    except Exception as e:
        print(f"[DECISION APPROVE] Warning broadcasting nurse notification: {e}")

    return jsonify({
        'success': True,
        'message': f"Recommendation #{recommendation_id} approved successfully by Dr. {doctor_name}",
        'status': 'approved',
        'recommendation_id': recommendation_id
    }), 200


@decision_bp.route('/reject/<int:recommendation_id>', methods=['POST'])
@permission_required('reject_decisions')
def reject_decision(recommendation_id):
    """Reject clinical recommendation (Doctor / Admin only)."""
    rec = Recommendation.get_by_id(recommendation_id)
    if not rec:
        return jsonify({'success': False, 'error': f'Recommendation with ID {recommendation_id} not found'}), 404

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    Recommendation.update_status(recommendation_id, status='rejected', decided_by=user_id)

    AuditLog.log(
        action='reject_recommendation',
        user_id=user_id,
        entity_type='recommendation',
        entity_id=recommendation_id,
        new_value={'status': 'rejected'},
        ip_address=request.remote_addr,
        description=f"Rejected transfer recommendation {recommendation_id} for patient ID {rec.get('patient_id')}"
    )

    return jsonify({
        'success': True,
        'message': 'Recommendation rejected successfully',
        'status': 'rejected',
        'recommendation_id': recommendation_id
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. GET /decision/pending & GET /decision/history/{patient_id}
# ─────────────────────────────────────────────────────────────
@decision_bp.route('/pending', methods=['GET'])
@permission_required('view_decisions')
def get_pending_decisions():
    """Fetch all pending recommendations across the hospital."""
    pending = Recommendation.get_pending()
    return jsonify({
        'success': True,
        'count': len(pending),
        'data': pending
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
        from database.db import db
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
