"""
routes/bed_routes.py — Phase 7 Bed Management REST APIs & Allocation Engine.
Endpoints:
    GET    /beds & /api/v1/beds                 (List beds, filter by ward/status)
    GET    /beds/{id} & /api/v1/beds/{id}       (Get bed details & current occupant)
    POST   /beds & /api/v1/beds                 (Create new bed in a ward)
    PUT    /beds/{id} & /api/v1/beds/{id}       (Update bed details or status)
    DELETE /beds/{id} & /api/v1/beds/{id}       (Deactivate/delete bed)
    POST   /beds/{id}/allocate                  (Allocate bed to patient)
    POST   /beds/{id}/release                   (Release bed)
    POST   /beds/{id}/maintenance               (Put bed in maintenance)
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from models.bed_model import Bed
from models.ward_model import Ward
from models.patient_model import Patient
from models.bed_management_model import BedManagement
from models.audit_log_model import AuditLog
from utils.decorators import permission_required, get_current_authenticated_user, _is_api_request

bed_bp = Blueprint('bed', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /beds & /api/v1/beds — List & Filter Beds
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/', methods=['GET'])
@bed_bp.route('', methods=['GET'])
@permission_required('view_patients')
def list_beds():
    """
    List beds filtered by ward_id, ward_type, status, or active state.
    Query Params:
        ward_id: int
        ward_type: string ('ICU', 'HDU', 'General')
        status: string ('available', 'occupied', 'maintenance', 'reserved', 'all')
        active_only: bool (default True)
    """
    ward_id = request.args.get('ward_id')
    ward_type = request.args.get('ward_type')
    status = request.args.get('status')
    active_str = request.args.get('active_only', 'true').lower()
    active_only = active_str not in ('false', '0')

    beds = Bed.get_all(
        ward_id=ward_id,
        ward_type=ward_type,
        status=status,
        active_only=active_only
    )

    if _is_api_request():
        return jsonify({
            'success': True,
            'count': len(beds),
            'data': beds
        }), 200

    return render_template('Admin/Admin_beds_wards/Admin_beds_wards.html', beds=beds)


# ─────────────────────────────────────────────────────────────
# 2. GET /beds/{id} & /api/v1/beds/{id} — Single Bed Details
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/<int:bed_id>', methods=['GET'])
@permission_required('view_patients')
def get_bed(bed_id):
    """
    Fetch bed details by ID including current patient occupant info.
    """
    bed = Bed.get_by_id(bed_id)
    if not bed:
        return jsonify({'success': False, 'error': f'Bed with ID {bed_id} not found'}), 404

    return jsonify({
        'success': True,
        'data': bed
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. POST /beds & /api/v1/beds — Create Bed
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/', methods=['POST'])
@bed_bp.route('', methods=['POST'])
@permission_required('edit_patients')
def create_bed():
    """
    Create a new bed in a ward.
    Payload:
        {
            "ward_id": 1,
            "bed_number": "ICU-105",
            "status": "available",
            "bed_type": "Standard"
        }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    ward_id = data.get('ward_id')
    if not ward_id:
        return jsonify({'success': False, 'error': 'ward_id is required.'}), 422

    try:
        ward_id = int(ward_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'ward_id must be a valid integer.'}), 422

    ward = Ward.get_by_id(ward_id)
    if not ward:
        return jsonify({'success': False, 'error': f'Ward with ID {ward_id} not found.'}), 404

    bed_number = (data.get('bed_number') or '').strip()
    if not bed_number:
        return jsonify({'success': False, 'error': 'bed_number is required.'}), 422

    status = (data.get('status') or 'available').strip().lower()
    if status not in Bed.VALID_STATUSES:
        return jsonify({'success': False, 'error': f"Invalid status '{status}'. Must be one of: {', '.join(Bed.VALID_STATUSES)}"}), 422

    bed_type = data.get('bed_type', 'Standard')

    try:
        bed_id = Bed.create(ward_id=ward_id, bed_number=bed_number, status=status, bed_type=bed_type)
    except Exception as e:
        return jsonify({'success': False, 'error': f"Error creating bed: {str(e)}"}), 422

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    AuditLog.log(
        action='create_bed',
        user_id=user_id,
        entity_type='bed',
        entity_id=bed_id,
        new_value={'ward_id': ward_id, 'bed_number': bed_number, 'status': status},
        ip_address=request.remote_addr,
        description=f"Created bed '{bed_number}' in ward '{ward.get('name')}'"
    )

    created_bed = Bed.get_by_id(bed_id)
    return jsonify({
        'success': True,
        'message': f"Bed '{bed_number}' created successfully",
        'data': created_bed
    }), 201


# ─────────────────────────────────────────────────────────────
# 4. PUT /beds/{id} & /api/v1/beds/{id} — Update Bed
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/<int:bed_id>', methods=['PUT'])
@permission_required('edit_patients')
def update_bed(bed_id):
    """
    Update bed details or change status (AVAILABLE, OCCUPIED, MAINTENANCE, RESERVED).
    """
    bed = Bed.get_by_id(bed_id)
    if not bed:
        return jsonify({'success': False, 'error': f'Bed with ID {bed_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    updates = {}

    allowed_fields = ['bed_number', 'status', 'ward_id', 'bed_type', 'is_active']
    for k in allowed_fields:
        if k in data and data[k] is not None:
            if k == 'ward_id':
                try:
                    updates[k] = int(data[k])
                except (ValueError, TypeError):
                    pass
            elif k == 'is_active':
                updates[k] = bool(data[k])
            elif k == 'status':
                stat = str(data[k]).strip().lower()
                if stat not in Bed.VALID_STATUSES:
                    return jsonify({'success': False, 'error': f"Invalid status '{data[k]}'. Allowed: {', '.join(Bed.VALID_STATUSES)}"}), 422
                updates[k] = stat
            else:
                updates[k] = str(data[k]).strip()

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields provided for update'}), 400

    try:
        Bed.update(bed_id, **updates)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 422

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    AuditLog.log(
        action='update_bed',
        user_id=user_id,
        entity_type='bed',
        entity_id=bed_id,
        old_value=bed,
        new_value=updates,
        ip_address=request.remote_addr,
        description=f"Updated bed {bed.get('bed_number')} (ID: {bed_id})"
    )

    updated = Bed.get_by_id(bed_id)
    return jsonify({
        'success': True,
        'message': f"Bed '{updated.get('bed_number')}' updated successfully",
        'data': updated
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. DELETE /beds/{id} & /api/v1/beds/{id} — Delete Bed
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/<int:bed_id>', methods=['DELETE'])
@permission_required('edit_patients')
def delete_bed(bed_id):
    """
    Deactivate a bed (only allowed if not occupied).
    """
    bed = Bed.get_by_id(bed_id)
    if not bed:
        return jsonify({'success': False, 'error': f'Bed with ID {bed_id} not found'}), 404

    try:
        Bed.delete(bed_id)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 422

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    AuditLog.log(
        action='delete_bed',
        user_id=user_id,
        entity_type='bed',
        entity_id=bed_id,
        ip_address=request.remote_addr,
        description=f"Deactivated bed '{bed.get('bed_number')}'"
    )

    return jsonify({
        'success': True,
        'message': f"Bed '{bed.get('bed_number')}' deactivated successfully"
    }), 200


# ─────────────────────────────────────────────────────────────
# 6. POST /beds/{id}/allocate — Allocate Bed to Patient
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/<int:bed_id>/allocate', methods=['POST'])
@permission_required('edit_patients')
def allocate_bed(bed_id):
    """
    Allocate a bed to a patient (ensuring no two active patients share a bed).
    Payload:
        {
            "patient_id": 4,
            "notes": "Admitted directly from ER"
        }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    patient_id = data.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'patient_id is required for bed allocation.'}), 422

    try:
        patient_id = int(patient_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'patient_id must be a valid integer.'}), 422

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    if patient.get('status') != 'admitted':
        return jsonify({'success': False, 'error': f"Cannot allocate bed: patient status is '{patient.get('status')}', must be 'admitted'."}), 422

    user = get_current_authenticated_user()
    user_id = user.id if user else None
    notes = data.get('notes')

    try:
        allocation_id = BedManagement.allocate_bed(
            patient_id=patient_id,
            bed_id=bed_id,
            allocated_by=user_id,
            notes=notes
        )
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 422
    except Exception as e:
        return jsonify({'success': False, 'error': f"Allocation failed: {str(e)}"}), 500

    bed = Bed.get_by_id(bed_id)

    AuditLog.log(
        action='allocate_bed',
        user_id=user_id,
        entity_type='bed',
        entity_id=bed_id,
        new_value={'patient_id': patient_id, 'allocation_id': allocation_id},
        ip_address=request.remote_addr,
        description=f"Allocated bed {bed.get('bed_number')} to patient {patient.get('name')} (ID: {patient_id})"
    )

    return jsonify({
        'success': True,
        'message': f"Bed '{bed.get('bed_number')}' successfully allocated to '{patient.get('name')}'",
        'data': {
            'allocation_id': allocation_id,
            'bed': bed,
            'patient_id': patient_id
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 7. POST /beds/{id}/release — Release Bed
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/<int:bed_id>/release', methods=['POST'])
@permission_required('edit_patients')
def release_bed(bed_id):
    """
    Release an occupied bed.
    """
    bed = Bed.get_by_id(bed_id)
    if not bed:
        return jsonify({'success': False, 'error': f'Bed with ID {bed_id} not found'}), 404

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    BedManagement.release_bed(bed_id=bed_id)

    AuditLog.log(
        action='release_bed',
        user_id=user_id,
        entity_type='bed',
        entity_id=bed_id,
        ip_address=request.remote_addr,
        description=f"Released bed {bed.get('bed_number')}"
    )

    updated_bed = Bed.get_by_id(bed_id)
    return jsonify({
        'success': True,
        'message': f"Bed '{bed.get('bed_number')}' released successfully",
        'data': updated_bed
    }), 200


# ─────────────────────────────────────────────────────────────
# 8. POST /beds/{id}/maintenance — Set Bed Maintenance Mode
# ─────────────────────────────────────────────────────────────
@bed_bp.route('/<int:bed_id>/maintenance', methods=['POST'])
@permission_required('edit_patients')
def set_bed_maintenance(bed_id):
    """
    Set a bed to maintenance mode.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    notes = data.get('notes')

    try:
        Bed.set_maintenance(bed_id, notes=notes)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 422

    user = get_current_authenticated_user()
    user_id = user.id if user else None
    bed = Bed.get_by_id(bed_id)

    AuditLog.log(
        action='set_bed_maintenance',
        user_id=user_id,
        entity_type='bed',
        entity_id=bed_id,
        ip_address=request.remote_addr,
        description=f"Bed {bed.get('bed_number')} marked under maintenance"
    )

    return jsonify({
        'success': True,
        'message': f"Bed '{bed.get('bed_number')}' is now under maintenance",
        'data': bed
    }), 200
