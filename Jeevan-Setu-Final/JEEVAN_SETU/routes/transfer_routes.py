"""
routes/transfer_routes.py — Phase 12 Patient Transfer Management REST APIs & Workflow.
Endpoints:
    GET  /transfers & /api/v1/transfers                (List & filter transfers)
    POST /transfers & /api/v1/transfers                (Create transfer request)
    GET  /transfers/{id} & /api/v1/transfers/{id}        (Get transfer details)
    PUT  /transfers/{id}/approve & POST .../approve    (Doctor approve & execute transfer)
    PUT  /transfers/{id}/reject & POST .../reject      (Doctor reject transfer with remarks)
    GET  /patients/{id}/transfers                      (Get patient transfer history)
"""

from flask import Blueprint, request, jsonify
from models.transfer_model import Transfer
from models.patient_model import Patient
from models.bed_model import Bed
from models.ward_model import Ward
from models.audit_log_model import AuditLog
from utils.decorators import permission_required, role_required, get_current_authenticated_user

transfer_bp = Blueprint('transfer', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /transfers & /api/v1/transfers — List Transfers
# ─────────────────────────────────────────────────────────────
@transfer_bp.route('/', methods=['GET'])
@transfer_bp.route('', methods=['GET'])
@permission_required('view_patients')
def list_transfers():
    """List all patient transfer records with optional status filter."""
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)

    transfers = Transfer.get_all(status=status, limit=limit)

    return jsonify({
        'success': True,
        'count': len(transfers),
        'status_filter': status,
        'data': transfers
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. POST /transfers & /api/v1/transfers — Create Transfer Request
# ─────────────────────────────────────────────────────────────
@transfer_bp.route('/', methods=['POST'])
@transfer_bp.route('', methods=['POST'])
@permission_required('edit_patients')
def create_transfer_request():
    """
    Create a new transfer request for an admitted patient.
    Payload:
        {
            "patient_id": 12,
            "to_ward": "HDU",
            "from_ward": "ICU", (optional, inferred from patient)
            "to_bed_id": 5,     (optional)
            "reason": "Step-down to HDU following clinical stabilization",
            "recommendation_id": 3 (optional)
        }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    patient_id = data.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Missing required parameter: patient_id'}), 400

    try:
        patient_id = int(patient_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'patient_id must be an integer'}), 400

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    if patient.get('status') != 'admitted':
        return jsonify({
            'success': False,
            'error': f"Cannot transfer patient #{patient_id} because status is '{patient.get('status')}' (must be 'admitted')"
        }), 400

    to_ward = data.get('to_ward')
    if not to_ward:
        return jsonify({'success': False, 'error': 'Missing required parameter: to_ward (ICU, HDU, General)'}), 400

    # Normalize ward
    to_ward = to_ward.strip()
    if to_ward.upper() in ('ICU', 'HDU', 'GENERAL'):
        to_ward = 'General' if to_ward.upper() == 'GENERAL' else to_ward.upper()

    from_ward = data.get('from_ward') or patient.get('ward_type', 'ICU')
    from_bed_id = data.get('from_bed_id') or patient.get('bed_id')
    from_bed_number = data.get('from_bed_number') or patient.get('bed_number')

    to_bed_id = data.get('to_bed_id')
    to_bed_number = data.get('to_bed_number')
    if to_bed_id:
        try:
            to_bed_id = int(to_bed_id)
            target_bed = Bed.get_by_id(to_bed_id)
            if not target_bed:
                return jsonify({'success': False, 'error': f'Target bed #{to_bed_id} not found'}), 404
            to_bed_number = target_bed.get('bed_number')
        except (ValueError, TypeError):
            pass

    recommendation_id = data.get('recommendation_id')
    if recommendation_id:
        try:
            recommendation_id = int(recommendation_id)
        except (ValueError, TypeError):
            recommendation_id = None

    reason = data.get('reason') or data.get('transfer_reason') or 'Clinical transfer request'

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    transfer_id = Transfer.request_transfer(
        patient_id=patient_id,
        from_ward=from_ward,
        to_ward=to_ward,
        requested_by=user_id,
        recommendation_id=recommendation_id,
        from_bed_id=from_bed_id,
        to_bed_id=to_bed_id,
        from_bed_number=from_bed_number,
        to_bed_number=to_bed_number,
        reason=reason
    )

    # Audit Log
    AuditLog.log(
        action='create_transfer_request',
        user_id=user_id,
        entity_type='transfer',
        entity_id=transfer_id,
        new_value={
            'patient_id': patient_id,
            'from_ward': from_ward,
            'to_ward': to_ward,
            'reason': reason
        },
        ip_address=request.remote_addr,
        description=f"Transfer request #{transfer_id} created for {patient.get('name')} from {from_ward} to {to_ward}"
    )

    transfer = Transfer.get_by_id(transfer_id)

    return jsonify({
        'success': True,
        'message': 'Transfer request created successfully',
        'transfer_id': transfer_id,
        'data': transfer
    }), 201


# ─────────────────────────────────────────────────────────────
# 3. GET /transfers/{id} — Single Transfer Details
# ─────────────────────────────────────────────────────────────
@transfer_bp.route('/<int:transfer_id>', methods=['GET'])
@permission_required('view_patients')
def get_transfer_by_id(transfer_id):
    """Get complete transfer record details."""
    transfer = Transfer.get_by_id(transfer_id)
    if not transfer:
        return jsonify({'success': False, 'error': f'Transfer #{transfer_id} not found'}), 404

    return jsonify({
        'success': True,
        'data': transfer
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. PUT /transfers/{id}/approve — Doctor Review & Approval
# ─────────────────────────────────────────────────────────────
@transfer_bp.route('/<int:transfer_id>/approve', methods=['PUT', 'POST'])
def approve_transfer_request(transfer_id):
    """
    Doctor review and approval of patient transfer request.
    Only authorized Doctors and Administrators can approve.
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

    # 1. Strict RBAC Enforcement: Nurse cannot approve transfers
    if user_role == 'nurse':
        AuditLog.log(
            action='UNAUTHORIZED_TRANSFER_APPROVAL_ATTEMPT',
            user_id=user_id,
            entity_type='transfer',
            entity_id=transfer_id,
            new_value={'role': user_role, 'attempted_action': 'approve_transfer'},
            ip_address=request.remote_addr,
            description=f"Security Alert: Nurse {getattr(user, 'full_name', 'Unknown')} unauthorized attempt to approve transfer #{transfer_id}"
        )
        return jsonify({
            'success': False,
            'error': 'Permission denied: Access forbidden. Nurses are not authorized to approve patient transfers. Only attending Doctors or Administrators can approve transfers.'
        }), 403

    if user_role not in ('doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Access forbidden: Insufficient role permissions.'}), 403

    transfer = Transfer.get_by_id(transfer_id)
    if not transfer:
        return jsonify({'success': False, 'error': f'Transfer #{transfer_id} not found'}), 404

    patient_id = transfer['patient_id']
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    # 2. Stale State Protection: Verify current patient clinical condition
    current_ews = patient.get('ews_score', 0) or 0
    decision = evaluate(current_ews)
    current_condition = decision.get('condition')

    # If patient condition changed from Stable to Moderate Risk or Critical, transfer approval is stale/invalid
    if current_condition != 'Stable':
        AuditLog.log(
            action='TRANSFER_APPROVAL_REJECTED_STALE',
            user_id=user_id,
            entity_type='transfer',
            entity_id=transfer_id,
            new_value={'current_ews': current_ews, 'current_condition': current_condition},
            ip_address=request.remote_addr,
            description=f"Transfer #{transfer_id} approval rejected: Patient {patient.get('name')} condition changed to {current_condition} (EWS {current_ews})"
        )
        return jsonify({
            'success': False,
            'error': "Transfer approval is no longer valid because the patient's current status has changed."
        }), 400

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    remarks = data.get('remarks') or data.get('notes') or 'Approved by attending doctor'
    to_bed_id = data.get('to_bed_id')
    to_ward = data.get('to_ward')

    if to_bed_id:
        try:
            to_bed_id = int(to_bed_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'to_bed_id must be an integer'}), 400

    try:
        Transfer.approve_transfer(
            transfer_id=transfer_id,
            approved_by=user_id,
            to_bed_id=to_bed_id,
            to_ward=to_ward,
            remarks=remarks
        )

        # Acknowledge / resolve any pending transfer alerts for this patient
        db.execute_query(
            """UPDATE alerts SET is_acknowledged = TRUE, acknowledged_by = %s, acknowledged_at = NOW()
               WHERE patient_id = %s AND parameter = 'transfer_pending' AND is_acknowledged = FALSE""",
            (user_id, patient_id)
        )

        # Audit Log
        doctor_name = getattr(user, 'full_name', 'Doctor')
        AuditLog.log(
            action='approve_transfer',
            user_id=user_id,
            entity_type='transfer',
            entity_id=transfer_id,
            new_value={'status': 'approved', 'remarks': remarks, 'to_bed_id': to_bed_id},
            ip_address=request.remote_addr,
            description=f"Transfer #{transfer_id} for Patient {transfer.get('patient_name')} approved by Dr. {doctor_name}. Remarks: {remarks}"
        )

        # 3. Notify Nurse after Doctor approval
        try:
            Notification.broadcast_to_role(
                role='nurse',
                title=f"[TRANSFER APPROVED] {patient.get('name')}",
                message=f"Transfer for {patient.get('name')} has been approved by Dr. {doctor_name}.",
                notif_type='TRANSFER',
                patient_id=patient_id,
                severity='TRANSFER'
            )
        except Exception as e:
            print(f"[TRANSFER APPROVE] Warning broadcasting nurse notification: {e}")

        updated_transfer = Transfer.get_by_id(transfer_id)
        updated_patient = Patient.get_by_id(patient_id)

        return jsonify({
            'success': True,
            'message': f"Transfer #{transfer_id} approved and executed successfully by Dr. {doctor_name}",
            'status': 'approved',
            'transfer_id': transfer_id,
            'data': updated_transfer,
            'patient': updated_patient
        }), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error executing transfer: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# 5. PUT /transfers/{id}/reject — Doctor Rejection
# ─────────────────────────────────────────────────────────────
@transfer_bp.route('/<int:transfer_id>/reject', methods=['PUT', 'POST'])
@role_required('doctor', 'admin')
def reject_transfer_request(transfer_id):
    """
    Doctor review and rejection of patient transfer request.
    Only authorized Doctors and Administrators can reject.
    Payload:
        {
            "remarks": "Patient unstable for step-down; continue Level 3 ICU care"
        }
    """
    transfer = Transfer.get_by_id(transfer_id)
    if not transfer:
        return jsonify({'success': False, 'error': f'Transfer #{transfer_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    remarks = data.get('remarks') or data.get('reason') or 'Rejected by attending doctor'

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    try:
        Transfer.reject_transfer(
            transfer_id=transfer_id,
            rejected_by=user_id,
            remarks=remarks
        )

        # Audit Log
        AuditLog.log(
            action='reject_transfer',
            user_id=user_id,
            entity_type='transfer',
            entity_id=transfer_id,
            new_value={'status': 'rejected', 'remarks': remarks},
            ip_address=request.remote_addr,
            description=f"Transfer #{transfer_id} for Patient {transfer.get('patient_name')} rejected by Doctor {user.full_name if user else ''}. Remarks: {remarks}"
        )

        updated_transfer = Transfer.get_by_id(transfer_id)

        return jsonify({
            'success': True,
            'message': f"Transfer #{transfer_id} rejected successfully",
            'status': 'rejected',
            'transfer_id': transfer_id,
            'data': updated_transfer
        }), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error rejecting transfer: {str(e)}'}), 500
