"""
routes/ward_routes.py — Phase 7 Ward Management REST APIs & Web Views.
Endpoints:
    GET    /wards & /api/v1/wards         (List wards with occupancy rates & bed counts)
    GET    /wards/{id} & /api/v1/wards/{id} (Get ward details and its beds)
    POST   /wards & /api/v1/wards         (Create new ward)
    PUT    /wards/{id} & /api/v1/wards/{id} (Update ward details)
    DELETE /wards/{id} & /api/v1/wards/{id} (Deactivate/delete ward)
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from models.ward_model import Ward
from models.bed_model import Bed
from models.audit_log_model import AuditLog
from utils.decorators import permission_required, get_current_authenticated_user, _is_api_request

ward_bp = Blueprint('ward', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /wards & /api/v1/wards — List Wards & Occupancy Rates
# ─────────────────────────────────────────────────────────────
@ward_bp.route('/', methods=['GET'])
@ward_bp.route('', methods=['GET'])
@permission_required('view_patients')
def list_wards():
    """
    List all wards with total beds, occupied beds, available beds, and occupancy rate.
    Query Params:
        ward_type: string ('ICU', 'HDU', 'General')
        active_only: bool (default True)
    """
    ward_type = request.args.get('ward_type')
    active_str = request.args.get('active_only', 'true').lower()
    active_only = active_str not in ('false', '0')

    wards = Ward.get_all(active_only=active_only, ward_type=ward_type)

    if _is_api_request():
        return jsonify({
            'success': True,
            'count': len(wards),
            'data': wards
        }), 200

    return render_template('Admin/Admin_beds_wards/Admin_beds_wards.html', wards=wards)


# ─────────────────────────────────────────────────────────────
# 2. GET /wards/{id} & /api/v1/wards/{id} — Single Ward Details & Bed List
# ─────────────────────────────────────────────────────────────
@ward_bp.route('/<int:ward_id>', methods=['GET'])
@permission_required('view_patients')
def get_ward(ward_id):
    """
    Fetch details for a specific ward, including all its beds.
    """
    ward = Ward.get_by_id(ward_id)
    if not ward:
        return jsonify({'success': False, 'error': f'Ward with ID {ward_id} not found'}), 404

    beds = Bed.get_by_ward(ward_id)
    ward['beds'] = beds

    return jsonify({
        'success': True,
        'data': ward
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. POST /wards & /api/v1/wards — Create New Ward
# ─────────────────────────────────────────────────────────────
@ward_bp.route('/', methods=['POST'])
@ward_bp.route('', methods=['POST'])
@permission_required('edit_patients')
def create_ward():
    """
    Create a new ward.
    Payload:
        {
            "name": "Cardiology ICU",
            "ward_type": "ICU",
            "floor_number": 2,
            "total_beds": 12,
            "description": "Critical cardiac care"
        }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    name = data.get('name', '').strip()
    if not name or len(name) < 2:
        return jsonify({'success': False, 'error': 'Ward name is required (min 2 characters).'}), 422

    ward_type = (data.get('ward_type') or 'ICU').strip()
    if ward_type.upper() not in ('ICU', 'HDU', 'GENERAL'):
        return jsonify({'success': False, 'error': 'Ward type must be ICU, HDU, or General.'}), 422

    try:
        floor_number = int(data.get('floor_number', 1))
        total_beds = int(data.get('total_beds', 10))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'floor_number and total_beds must be valid integers.'}), 422

    description = data.get('description')

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    ward_id = Ward.create(
        name=name,
        ward_type=ward_type,
        floor_number=floor_number,
        total_beds=total_beds,
        description=description
    )

    AuditLog.log(
        action='create_ward',
        user_id=user_id,
        entity_type='ward',
        entity_id=ward_id,
        new_value={'name': name, 'ward_type': ward_type, 'total_beds': total_beds},
        ip_address=request.remote_addr,
        description=f"Created ward '{name}' ({ward_type}) with capacity {total_beds}"
    )

    created_ward = Ward.get_by_id(ward_id)
    return jsonify({
        'success': True,
        'message': f"Ward '{name}' created successfully",
        'data': created_ward
    }), 201


# ─────────────────────────────────────────────────────────────
# 4. PUT /wards/{id} & /api/v1/wards/{id} — Update Ward
# ─────────────────────────────────────────────────────────────
@ward_bp.route('/<int:ward_id>', methods=['PUT'])
@permission_required('edit_patients')
def update_ward(ward_id):
    """
    Update ward configuration.
    """
    ward = Ward.get_by_id(ward_id)
    if not ward:
        return jsonify({'success': False, 'error': f'Ward with ID {ward_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    updates = {}

    allowed_fields = ['name', 'ward_type', 'floor_number', 'total_beds', 'description', 'is_active']
    for k in allowed_fields:
        if k in data and data[k] is not None:
            if k in ('floor_number', 'total_beds'):
                try:
                    updates[k] = int(data[k])
                except (ValueError, TypeError):
                    pass
            elif k == 'is_active':
                updates[k] = bool(data[k])
            else:
                updates[k] = str(data[k]).strip()

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields provided for update'}), 400

    Ward.update(ward_id, **updates)

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    AuditLog.log(
        action='update_ward',
        user_id=user_id,
        entity_type='ward',
        entity_id=ward_id,
        old_value=ward,
        new_value=updates,
        ip_address=request.remote_addr,
        description=f"Updated ward '{ward.get('name')}'"
    )

    updated = Ward.get_by_id(ward_id)
    return jsonify({
        'success': True,
        'message': f"Ward '{updated.get('name')}' updated successfully",
        'data': updated
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. DELETE /wards/{id} & /api/v1/wards/{id} — Delete / Deactivate Ward
# ─────────────────────────────────────────────────────────────
@ward_bp.route('/<int:ward_id>', methods=['DELETE'])
@permission_required('edit_patients')
def delete_ward(ward_id):
    """
    Deactivate a ward (only allowed if no occupied beds).
    """
    ward = Ward.get_by_id(ward_id)
    if not ward:
        return jsonify({'success': False, 'error': f'Ward with ID {ward_id} not found'}), 404

    try:
        Ward.delete(ward_id)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 422

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    AuditLog.log(
        action='delete_ward',
        user_id=user_id,
        entity_type='ward',
        entity_id=ward_id,
        ip_address=request.remote_addr,
        description=f"Deactivated ward '{ward.get('name')}'"
    )

    return jsonify({
        'success': True,
        'message': f"Ward '{ward.get('name')}' deactivated successfully"
    }), 200
