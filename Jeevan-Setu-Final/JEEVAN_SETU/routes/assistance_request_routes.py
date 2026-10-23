"""
routes/assistance_request_routes.py — REST API for Attendant Assistance Requests.
Provides complete request lifecycle management for Attendant and Hospital Staff portals:
- Attendant: create, view my requests, cancel. Strictly isolated to verified session patient.
- Staff: list, filter, summary metrics, acknowledge, start, resolve, reject (with reason).
"""

import html
import re
from flask import Blueprint, request, jsonify
from models.assistance_request_model import AssistanceRequest
from models.patient_model import Patient
from models.notification_model import Notification
from models.audit_log_model import AuditLog
from routes.attendant_routes import get_current_attendant_session
from utils.decorators import get_current_authenticated_user

assistance_request_bp = Blueprint('assistance_request', __name__)


def sanitize_input(text):
    """Sanitize user input to prevent stored XSS and strip whitespace."""
    if text is None:
        return None
    val = str(text).strip()
    return html.escape(val)


# =============================================================
# 1. ATTENDANT PORTAL APIS (STRICTLY SESSION-ISOLATED)
# =============================================================

@assistance_request_bp.route('/attendant/assistance-requests', methods=['POST'])
@assistance_request_bp.route('/api/v1/attendant/assistance-requests', methods=['POST'])
def attendant_create_assistance_request():
    """
    Attendant: Submit a non-emergency assistance request.
    1. Validates active attendant session token.
    2. Strictly resolves patient_id and attendant identity server-side.
    3. Validates category and character limits.
    4. Creates persistent database record.
    5. Dispatches notification to nursing team.
    6. Records audit trail.
    """
    session = get_current_attendant_session()
    if not session:
        return jsonify({
            'success': False,
            'error': 'Attendant access required. Please scan the patient QR code to establish a session.'
        }), 401

    patient_id = session.get('patient_id')
    attendant_name = session.get('attendant_name', 'Attendant')

    if not patient_id:
        return jsonify({'success': False, 'error': 'Invalid attendant session: missing patient reference.'}), 401

    # Verify patient exists and is admitted
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    if patient.get('status') != 'admitted':
        return jsonify({
            'success': False,
            'error': f"Patient '{patient.get('name')}' is no longer admitted. Assistance requests can only be placed for admitted patients."
        }), 403

    data = request.get_json(silent=True) or request.form.to_dict() or {}

    category = data.get('category')
    if not category:
        return jsonify({'success': False, 'error': 'Request category is required.'}), 400

    raw_description = data.get('description')
    clean_description = None
    if raw_description is not None:
        raw_stripped = str(raw_description).strip()
        if len(raw_stripped) > 500:
            return jsonify({
                'success': False,
                'error': f'Description cannot exceed 500 characters (currently {len(raw_stripped)}).'
            }), 400
        if raw_stripped:
            clean_description = sanitize_input(raw_stripped)

    try:
        new_request = AssistanceRequest.create(
            patient_id=patient_id,
            attendant_name=attendant_name,
            category=category,
            description=clean_description
        )
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'An internal error occurred while creating the request.'}), 500

    req_id = new_request['request_id']
    req_cat = new_request['category']
    p_name = new_request.get('patient_name', patient.get('name', 'Patient'))
    p_code = new_request.get('patient_code', patient.get('patient_code', ''))
    ward = new_request.get('ward_type', patient.get('ward_type', 'ICU'))
    bed = new_request.get('bed_number', patient.get('bed_number', ''))

    # Dispatch notification to nursing staff
    try:
        notif_severity = 'HIGH' if 'nursing' in req_cat.lower() else 'INFO'
        Notification.broadcast_to_role(
            role='nurse',
            title=f"Assistance Request #{req_id}: {req_cat}",
            message=f"Patient {p_name} ({p_code}) in {ward} Bed {bed}: {req_cat}. Requested by {attendant_name}.",
            notif_type='alert',
            patient_id=patient_id,
            severity=notif_severity
        )
    except Exception:
        pass

    # Record Audit Log
    try:
        AuditLog.log(
            action='ATTENDANT_ASSISTANCE_REQUEST_CREATED',
            user_id=None,
            entity_type='assistance_request',
            entity_id=req_id,
            new_value={
                'request_id': req_id,
                'patient_id': patient_id,
                'category': req_cat,
                'attendant_name': attendant_name
            },
            ip_address=request.remote_addr,
            description=f"Attendant '{attendant_name}' submitted assistance request #{req_id} for Patient #{patient_id} ({req_cat})"
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': 'Your assistance request has been submitted.',
        'request': new_request
    }), 201


@assistance_request_bp.route('/attendant/assistance-requests', methods=['GET'])
@assistance_request_bp.route('/api/v1/attendant/assistance-requests', methods=['GET'])
def attendant_list_my_requests():
    """
    Attendant: View requests belonging strictly to the currently authenticated patient session.
    Strictly prevents cross-attendant and cross-patient data exposure (IDOR prevention).
    """
    session = get_current_attendant_session()
    if not session:
        return jsonify({
            'success': False,
            'error': 'Attendant access required. Please scan the patient QR code to establish a session.'
        }), 401

    patient_id = session.get('patient_id')
    status_filter = request.args.get('status')

    requests_list = AssistanceRequest.get_by_patient(patient_id=patient_id, status=status_filter)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'requests': requests_list,
        'count': len(requests_list)
    }), 200


@assistance_request_bp.route('/attendant/assistance-requests/<int:request_id>', methods=['GET'])
@assistance_request_bp.route('/api/v1/attendant/assistance-requests/<int:request_id>', methods=['GET'])
def attendant_get_single_request(request_id):
    """
    Attendant: View details of a specific request.
    Strictly verifies ownership against the session patient_id.
    """
    session = get_current_attendant_session()
    if not session:
        return jsonify({
            'success': False,
            'error': 'Attendant access required. Please scan the patient QR code to establish a session.'
        }), 401

    session_patient_id = session.get('patient_id')

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    # IDOR Protection: verify request belongs to this attendant's authorized patient
    if int(req_data['patient_id']) != int(session_patient_id):
        return jsonify({
            'success': False,
            'error': 'Access denied: You are not authorized to view requests for another patient.'
        }), 403

    return jsonify({
        'success': True,
        'request': req_data
    }), 200


@assistance_request_bp.route('/attendant/assistance-requests/<int:request_id>/cancel', methods=['POST'])
@assistance_request_bp.route('/api/v1/attendant/assistance-requests/<int:request_id>/cancel', methods=['POST'])
def attendant_cancel_request(request_id):
    """
    Attendant: Cancel an assistance request.
    Only permitted while request is in 'submitted', 'pending', or 'acknowledged' state.
    Strictly enforces patient ownership.
    """
    session = get_current_attendant_session()
    if not session:
        return jsonify({
            'success': False,
            'error': 'Attendant access required. Please scan the patient QR code to establish a session.'
        }), 401

    session_patient_id = session.get('patient_id')
    attendant_name = session.get('attendant_name', 'Attendant')

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    if int(req_data['patient_id']) != int(session_patient_id):
        return jsonify({
            'success': False,
            'error': 'Access denied: You can only cancel requests for your authorized patient.'
        }), 403

    old_status = req_data.get('status')

    try:
        updated = AssistanceRequest.cancel(
            request_id=request_id,
            patient_id=session_patient_id,
            attendant_name=attendant_name
        )
    except (ValueError, PermissionError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to cancel assistance request.'}), 500

    # Audit Log
    try:
        AuditLog.log(
            action='ATTENDANT_ASSISTANCE_REQUEST_CANCELLED',
            user_id=None,
            entity_type='assistance_request',
            entity_id=request_id,
            old_value={'status': old_status},
            new_value={'status': 'cancelled'},
            ip_address=request.remote_addr,
            description=f"Attendant '{attendant_name}' cancelled assistance request #{request_id} for Patient #{session_patient_id}"
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': 'Assistance request successfully cancelled.',
        'request': updated
    }), 200


# =============================================================
# 2. HOSPITAL STAFF APIS (NURSE, DOCTOR, ADMIN)
# =============================================================

@assistance_request_bp.route('/assistance-requests', methods=['GET'])
@assistance_request_bp.route('/api/v1/assistance-requests', methods=['GET'])
def staff_list_assistance_requests():
    """
    Hospital Staff: List assistance requests with status, ward, and search filters.
    Requires authenticated staff user (Nurse, Doctor, Admin).
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required. Please log in as hospital staff.'}), 401

    role = getattr(user, 'role', '').lower()
    if role not in ('nurse', 'doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Access restricted to authorized hospital staff.'}), 403

    status_filter = request.args.get('status')
    ward_filter = request.args.get('ward')
    patient_id_filter = request.args.get('patient_id')
    query_filter = request.args.get('q') or request.args.get('search')
    limit = request.args.get('limit', 100)
    offset = request.args.get('offset', 0)

    try:
        limit = int(limit)
        offset = int(offset)
    except (ValueError, TypeError):
        limit = 100
        offset = 0

    requests_list = AssistanceRequest.get_for_staff(
        status=status_filter,
        ward=ward_filter,
        patient_id=patient_id_filter,
        q=query_filter,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'success': True,
        'requests': requests_list,
        'count': len(requests_list)
    }), 200


@assistance_request_bp.route('/assistance-requests/summary', methods=['GET'])
@assistance_request_bp.route('/api/v1/assistance-requests/summary', methods=['GET'])
def staff_assistance_requests_summary():
    """
    Hospital Staff & Admin: Summary statistics of assistance requests.
    Exposes operational counts without sensitive clinical patient data.
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    stats = AssistanceRequest.get_summary_stats()
    return jsonify({
        'success': True,
        'summary': stats
    }), 200


@assistance_request_bp.route('/assistance-requests/<int:request_id>', methods=['GET'])
@assistance_request_bp.route('/api/v1/assistance-requests/<int:request_id>', methods=['GET'])
def staff_get_assistance_request(request_id):
    """
    Hospital Staff: Retrieve details of a specific assistance request.
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    return jsonify({
        'success': True,
        'request': req_data
    }), 200


@assistance_request_bp.route('/assistance-requests/<int:request_id>/acknowledge', methods=['POST'])
@assistance_request_bp.route('/api/v1/assistance-requests/<int:request_id>/acknowledge', methods=['POST'])
def staff_acknowledge_request(request_id):
    """
    Staff / Nurse: Acknowledge an incoming assistance request.
    Transitions request from 'pending' to 'acknowledged'.
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    role = getattr(user, 'role', '').lower()
    if role not in ('nurse', 'doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized: Only clinical staff can acknowledge requests.'}), 403

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    old_status = req_data.get('status')

    try:
        updated = AssistanceRequest.acknowledge(request_id=request_id, user_id=user.id)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to acknowledge request.'}), 500

    # Audit Log
    try:
        AuditLog.log(
            action='ASSISTANCE_REQUEST_ACKNOWLEDGED',
            user_id=user.id,
            entity_type='assistance_request',
            entity_id=request_id,
            old_value={'status': old_status},
            new_value={'status': 'acknowledged', 'assigned_user_id': user.id},
            ip_address=request.remote_addr,
            description=f"Staff '{user.full_name}' ({user.role}) acknowledged assistance request #{request_id}"
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': f'Request #{request_id} acknowledged.',
        'request': updated
    }), 200


@assistance_request_bp.route('/assistance-requests/<int:request_id>/start', methods=['POST'])
@assistance_request_bp.route('/api/v1/assistance-requests/<int:request_id>/start', methods=['POST'])
def staff_start_request(request_id):
    """
    Staff / Nurse: Mark assistance request as in-progress.
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    role = getattr(user, 'role', '').lower()
    if role not in ('nurse', 'doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized: Only clinical staff can update requests.'}), 403

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    old_status = req_data.get('status')

    try:
        updated = AssistanceRequest.start(request_id=request_id, user_id=user.id)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to mark request in progress.'}), 500

    # Audit Log
    try:
        AuditLog.log(
            action='ASSISTANCE_REQUEST_STARTED',
            user_id=user.id,
            entity_type='assistance_request',
            entity_id=request_id,
            old_value={'status': old_status},
            new_value={'status': 'in_progress', 'assigned_user_id': user.id},
            ip_address=request.remote_addr,
            description=f"Staff '{user.full_name}' ({user.role}) started working on assistance request #{request_id}"
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': f'Request #{request_id} is now in progress.',
        'request': updated
    }), 200


@assistance_request_bp.route('/assistance-requests/<int:request_id>/resolve', methods=['POST'])
@assistance_request_bp.route('/api/v1/assistance-requests/<int:request_id>/resolve', methods=['POST'])
def staff_resolve_request(request_id):
    """
    Staff / Nurse: Mark assistance request as resolved.
    Accepts optional resolution_note.
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    role = getattr(user, 'role', '').lower()
    if role not in ('nurse', 'doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized: Only clinical staff can resolve requests.'}), 403

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    old_status = req_data.get('status')

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    note = data.get('resolution_note') or data.get('note')

    try:
        updated = AssistanceRequest.resolve(request_id=request_id, user_id=user.id, resolution_note=note)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to resolve assistance request.'}), 500

    # Audit Log
    try:
        AuditLog.log(
            action='ASSISTANCE_REQUEST_RESOLVED',
            user_id=user.id,
            entity_type='assistance_request',
            entity_id=request_id,
            old_value={'status': old_status},
            new_value={'status': 'resolved', 'closed_by_user_id': user.id, 'resolution_note': note},
            ip_address=request.remote_addr,
            description=f"Staff '{user.full_name}' ({user.role}) marked assistance request #{request_id} as resolved"
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': f'Request #{request_id} resolved.',
        'request': updated
    }), 200


@assistance_request_bp.route('/assistance-requests/<int:request_id>/reject', methods=['POST'])
@assistance_request_bp.route('/api/v1/assistance-requests/<int:request_id>/reject', methods=['POST'])
def staff_reject_request(request_id):
    """
    Staff / Nurse: Reject assistance request with a mandatory reason.
    Returns 400 if reason is missing.
    """
    user = get_current_authenticated_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    role = getattr(user, 'role', '').lower()
    if role not in ('nurse', 'doctor', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized: Only clinical staff can reject requests.'}), 403

    req_data = AssistanceRequest.get_by_id(request_id)
    if not req_data:
        return jsonify({'success': False, 'error': f'Request #{request_id} not found.'}), 404

    old_status = req_data.get('status')

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    reason = data.get('rejection_reason') or data.get('reason')

    if not reason or not str(reason).strip():
        return jsonify({'success': False, 'error': 'A rejection reason is mandatory to reject a request.'}), 400

    try:
        updated = AssistanceRequest.reject(request_id=request_id, user_id=user.id, rejection_reason=reason)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to reject assistance request.'}), 500

    # Audit Log
    try:
        AuditLog.log(
            action='ASSISTANCE_REQUEST_REJECTED',
            user_id=user.id,
            entity_type='assistance_request',
            entity_id=request_id,
            old_value={'status': old_status},
            new_value={'status': 'rejected', 'closed_by_user_id': user.id, 'rejection_reason': reason},
            ip_address=request.remote_addr,
            description=f"Staff '{user.full_name}' ({user.role}) rejected assistance request #{request_id}. Reason: {reason}"
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': f'Request #{request_id} rejected.',
        'request': updated
    }), 200
