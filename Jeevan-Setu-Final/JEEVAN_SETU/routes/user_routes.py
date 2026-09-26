"""
routes/user_routes.py — Phase 5 Administrator User Management REST APIs.
Endpoints:
    GET    /api/v1/users              (Search, filter, paginate)
    GET    /api/v1/users/{id}         (Get single user)
    POST   /api/v1/users              (Create user & role assignment)
    PUT    /api/v1/users/{id}         (Update user details)
    DELETE /api/v1/users/{id}         (Deactivate/delete user)
    PATCH  /api/v1/users/{id}/status  (Update user active status)
    POST   /api/v1/users/{id}/reset-password (Admin direct password reset)
"""

from flask import Blueprint, request, jsonify
from database.db import db
from models.user_model import User
from models.role_model import Role
from models.patient_model import Patient
from models.audit_log_model import AuditLog
from utils.decorators import role_required, get_current_authenticated_user
from utils.validators import validate_email, validate_username

user_mgmt_bp = Blueprint('user_mgmt', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /api/v1/users — Search, Filter & Paginate
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/', methods=['GET'])
@user_mgmt_bp.route('', methods=['GET'])
@role_required('admin')
def list_users():
    """
    List all users with search, role filtering, status filtering, and pagination.
    Query Params:
        search: string (searches username, full_name, email, department)
        role: string ('admin', 'doctor', 'nurse', 'attendant')
        status / is_active: boolean ('true', 'false', '1', '0')
        department: string
        page: int (default 1)
        limit: int (default 20)
    """
    search = request.args.get('search') or request.args.get('q')
    role = request.args.get('role')
    is_active = request.args.get('is_active') if request.args.get('is_active') is not None else request.args.get('status')
    department = request.args.get('department')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    result = User.get_filtered(
        search=search,
        role=role,
        is_active=is_active,
        department=department,
        page=page,
        limit=limit
    )

    return jsonify({
        'success': True,
        'data': result['users'],
        'pagination': {
            'total': result['total'],
            'page': result['page'],
            'limit': result['limit'],
            'pages': result['pages']
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. GET /api/v1/users/{id} — Single User Details
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/<int:user_id>', methods=['GET'])
@role_required('admin')
def get_user(user_id):
    """
    Get single user details by ID.
    """
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'error': f'User with ID {user_id} not found'}), 404

    return jsonify({
        'success': True,
        'data': user.to_dict()
    }), 200


# ─────────────────────────────────────────────────────────────
# 2b. GET /api/v1/users/roles-summary — Roles & Metadata
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/roles-summary', methods=['GET'])
@role_required('admin')
def get_roles_summary():
    """
    Get summary of all roles with counts of users, plus system departments and wards.
    """
    roles = Role.get_all()
    roles_data = []
    for r in roles:
        r_name = r['name']
        count_res = db.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE role = %s AND is_active = TRUE",
            (r_name,), fetch=True
        )
        count = count_res[0]['count'] if count_res else 0
        roles_data.append({
            'role_id': r['role_id'],
            'name': r['name'],
            'display_name': r['display_name'],
            'description': r.get('description'),
            'active_users_count': count
        })

    # Wards for nurse assignment
    wards_res = db.execute_query("SELECT ward_id, name, ward_type FROM wards ORDER BY name", fetch=True) or []
    
    # Common departments
    departments = [
        'Administration', 'Cardiology', 'Pulmonology', 'Critical Care / ICU',
        'High Dependency Unit (HDU)', 'General Medicine', 'Emergency Dept',
        'Neurology', 'Nephrology', 'Infectious Disease', 'Pathology', 'IT Services'
    ]

    return jsonify({
        'success': True,
        'data': {
            'roles': roles_data,
            'departments': departments,
            'wards': wards_res
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. POST /api/v1/users — Create User & Role Assignment
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/', methods=['POST'])
@user_mgmt_bp.route('', methods=['POST'])
@role_required('admin')
def create_user():
    """
    Create a new user and assign role.
    Payload:
        {
            "username": "dr_smith",
            "password": "Password123!",
            "full_name": "Dr. John Smith",
            "email": "jsmith@hospital.com",
            "role": "doctor",
            "department": "Critical Care",
            "is_active": true,
            "specialization": "Cardiology",
            "license_number": "MED-2026-991",
            "qualification": "MBBS, MD",
            "experience_years": 8,
            "ward_assignment": "ICU",
            "shift": "Day"
        }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    role = (data.get('role') or 'nurse').strip().lower()
    department = (data.get('department') or '').strip() or None
    is_active = data.get('is_active', True)
    if isinstance(is_active, str):
        is_active = is_active.lower() in ('true', '1', 'yes', 'active')
    else:
        is_active = bool(is_active)

    specialization = (data.get('specialization') or '').strip() or None
    license_number = (data.get('license_number') or '').strip() or None
    qualification = (data.get('qualification') or '').strip() or None
    experience_years = data.get('experience_years', 0)
    try:
        experience_years = int(experience_years)
    except (ValueError, TypeError):
        experience_years = 0
    ward_assignment = (data.get('ward_assignment') or '').strip() or None
    shift = (data.get('shift') or 'Rotating').strip()

    # Input validations
    errors = []
    if not username or not validate_username(username):
        errors.append('Username must be 3-50 alphanumeric characters (letters, numbers, underscores).')
    if not password or len(password) < 6:
        errors.append('Password must be at least 6 characters long.')
    if confirm_password and password != confirm_password:
        errors.append('Passwords do not match.')
    if not full_name or len(full_name) < 2:
        errors.append('Full name is required (minimum 2 characters).')
    if not email or not validate_email(email):
        errors.append('A valid email address is required.')
    if role not in ('admin', 'doctor', 'nurse', 'attendant'):
        errors.append("Invalid role. Must be one of: 'admin', 'doctor', 'nurse', 'attendant'.")

    # Check uniqueness
    if not errors:
        if User.get_by_username(username):
            errors.append(f"Username '{username}' is already taken.")
        if User.get_by_email(email):
            errors.append(f"Email '{email}' is already registered.")

    if errors:
        return jsonify({'success': False, 'errors': errors, 'error': errors[0]}), 422

    # Map role to role_id if available
    role_obj = Role.get_by_name(role)
    role_id = role_obj['role_id'] if role_obj else None

    current_admin = get_current_authenticated_user()
    user_id = User.create(
        username=username,
        password=password,
        full_name=full_name,
        email=email,
        role=role,
        department=department,
        role_id=role_id,
        is_active=is_active,
        specialization=specialization,
        license_number=license_number,
        qualification=qualification,
        experience_years=experience_years,
        ward_assignment=ward_assignment,
        shift=shift
    )

    # Log to audit trail
    AuditLog.log(
        action='admin_create_user',
        user_id=current_admin.id if current_admin else None,
        entity_type='user',
        entity_id=user_id,
        new_value={
            'username': username,
            'email': email,
            'role': role,
            'department': department,
            'is_active': is_active,
            'specialization': specialization
        },
        ip_address=request.remote_addr,
        description=f"Admin created user {username} ({full_name}) with role {role}"
    )

    new_user = User.get_by_id(user_id)
    return jsonify({
        'success': True,
        'message': f"User '{username}' created successfully",
        'data': new_user.to_dict() if new_user else {'user_id': user_id}
    }), 201


# ─────────────────────────────────────────────────────────────
# 4. PUT /api/v1/users/{id} — Update User Details
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/<int:user_id>', methods=['PUT'])
@role_required('admin')
def update_user(user_id):
    """
    Update existing user profile and role assignment.
    Payload:
        {
            "full_name": "Dr. J. Smith",
            "email": "drsmith_new@hospital.com",
            "role": "doctor",
            "department": "Cardiology"
        }
    """
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'error': f'User with ID {user_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    updates = {}

    if 'full_name' in data and data['full_name']:
        updates['full_name'] = data['full_name'].strip()

    if 'email' in data and data['email']:
        new_email = data['email'].strip().lower()
        if not validate_email(new_email):
            return jsonify({'success': False, 'error': 'Invalid email format'}), 422
        existing = User.get_by_email(new_email)
        if existing and existing['user_id'] != user_id:
            return jsonify({'success': False, 'error': f"Email '{new_email}' is already in use"}), 422
        updates['email'] = new_email

    if 'role' in data and data['role']:
        new_role = data['role'].strip().lower()
        if new_role not in ('admin', 'doctor', 'nurse', 'attendant'):
            return jsonify({'success': False, 'error': 'Invalid role specified'}), 422
        updates['role'] = new_role
        role_obj = Role.get_by_name(new_role)
        if role_obj:
            updates['role_id'] = role_obj['role_id']

    if 'department' in data:
        updates['department'] = data['department'].strip() if data['department'] else None

    if 'contact_number' in data:
        updates['contact_number'] = data['contact_number'].strip() if data['contact_number'] else None

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields provided for update'}), 400

    current_admin = get_current_authenticated_user()
    old_data = user.to_dict()
    User.update(user_id, **updates)

    AuditLog.log(
        action='admin_update_user',
        user_id=current_admin.id if current_admin else None,
        entity_type='user',
        entity_id=user_id,
        old_value=old_data,
        new_value=updates,
        ip_address=request.remote_addr,
        description=f"Admin updated user {user.username} (ID: {user_id})"
    )

    updated_user = User.get_by_id(user_id)
    return jsonify({
        'success': True,
        'message': f"User '{user.username}' updated successfully",
        'data': updated_user.to_dict()
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. DELETE /api/v1/users/{id} — Deactivate / Soft Delete
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user(user_id):
    """
    Deactivate a user. Admins cannot deactivate their own account.
    """
    current_admin = get_current_authenticated_user()
    if current_admin and current_admin.id == user_id:
        return jsonify({'success': False, 'error': 'Cannot deactivate your own administrator account'}), 400

    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'error': f'User with ID {user_id} not found'}), 404

    User.delete(user_id)

    AuditLog.log(
        action='admin_deactivate_user',
        user_id=current_admin.id if current_admin else None,
        entity_type='user',
        entity_id=user_id,
        ip_address=request.remote_addr,
        description=f"Admin deactivated user {user.username} (ID: {user_id})"
    )

    return jsonify({
        'success': True,
        'message': f"User '{user.username}' has been deactivated"
    }), 200


# ─────────────────────────────────────────────────────────────
# 6. PATCH /api/v1/users/{id}/status — Update User Status
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/<int:user_id>/status', methods=['PATCH'])
@role_required('admin')
def update_user_status(user_id):
    """
    Toggle or explicitly set user active status.
    Payload:
        { "is_active": true } or { "is_active": false }
    """
    current_admin = get_current_authenticated_user()
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'error': f'User with ID {user_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    if 'is_active' in data:
        new_status = bool(data['is_active'])
    else:
        # Toggle if not explicitly specified
        new_status = not user.is_active

    if not new_status and current_admin and current_admin.id == user_id:
        return jsonify({'success': False, 'error': 'Cannot deactivate your own administrator account'}), 400

    User.set_status(user_id, new_status)

    action_label = 'activated' if new_status else 'deactivated'
    AuditLog.log(
        action=f"admin_{action_label}_user",
        user_id=current_admin.id if current_admin else None,
        entity_type='user',
        entity_id=user_id,
        new_value={'is_active': new_status},
        ip_address=request.remote_addr,
        description=f"Admin {action_label} user {user.username} (ID: {user_id})"
    )

    updated_user = User.get_by_id(user_id)
    return jsonify({
        'success': True,
        'message': f"User '{user.username}' is now {action_label}",
        'data': updated_user.to_dict()
    }), 200


# ─────────────────────────────────────────────────────────────
# 7. POST /api/v1/users/{id}/reset-password — Admin Password Reset
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/<int:user_id>/reset-password', methods=['POST'])
@role_required('admin')
def admin_reset_password(user_id):
    """
    Directly set a new password for a user.
    Payload:
        { "new_password": "NewSecurePassword123!" }
    """
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'error': f'User with ID {user_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    new_password = data.get('new_password', '')

    if not new_password or len(new_password) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters long'}), 422

    current_admin = get_current_authenticated_user()
    User.update_password(user_id, new_password)

    AuditLog.log(
        action='admin_reset_user_password',
        user_id=current_admin.id if current_admin else None,
        entity_type='user',
        entity_id=user_id,
        ip_address=request.remote_addr,
        description=f"Admin reset password for user {user.username} (ID: {user_id})"
    )

    return jsonify({
        'success': True,
        'message': f"Password for user '{user.username}' has been updated successfully"
    }), 200


# ─────────────────────────────────────────────────────────────
# 8. GET /api/v1/users/global-search & /api/v1/admin/global-search
# ─────────────────────────────────────────────────────────────
@user_mgmt_bp.route('/global-search', methods=['GET'])
@user_mgmt_bp.route('/admin/global-search', methods=['GET'])
def admin_global_search():
    """
    Unified global search endpoint for Admin top navbar search bar.
    Searches across Patients, Beds/Wards, and Users/Staff in real-time.
    Query params: ?q=... or ?search=...
    """
    q = (request.args.get('q') or request.args.get('query') or request.args.get('search') or '').strip()
    if not q:
        return jsonify({
            'success': True,
            'query': '',
            'results': {'patients': [], 'beds': [], 'users': []},
            'total': 0
        }), 200

    # 1. Search Patients
    try:
        patients = Patient.search(q)[:6]
        formatted_patients = []
        for p in patients:
            formatted_patients.append({
                'id': p.get('patient_id'),
                'name': p.get('name'),
                'patient_code': p.get('patient_code'),
                'ward': p.get('ward_name') or p.get('ward_type') or 'General',
                'bed': p.get('bed_number') or 'Unassigned',
                'diagnosis': p.get('diagnosis') or 'Under Observation',
                'status': p.get('status') or 'admitted',
                'risk_level': p.get('risk_level') or 'normal'
            })
    except Exception as e:
        formatted_patients = []

    # 2. Search Users & Staff
    try:
        users = User.search(q)[:6]
        formatted_users = []
        for u in users:
            formatted_users.append({
                'id': u.get('user_id') or u.get('id'),
                'name': u.get('full_name') or u.get('username'),
                'username': u.get('username'),
                'role': u.get('role'),
                'department': u.get('department') or 'General',
                'is_active': u.get('is_active', True)
            })
    except Exception as e:
        formatted_users = []

    # 3. Search Beds & Wards
    try:
        bed_term = f"%{q}%"
        beds = db.execute_query(
            """SELECT b.bed_id, b.bed_number, b.status, w.name AS ward_name, w.ward_type
               FROM beds b
               LEFT JOIN wards w ON b.ward_id = w.ward_id
               WHERE b.bed_number LIKE %s OR w.name LIKE %s
               ORDER BY b.bed_number ASC LIMIT 6""",
            (bed_term, bed_term), fetch=True
        ) or []
    except Exception as e:
        beds = []

    total_count = len(formatted_patients) + len(formatted_users) + len(beds)

    return jsonify({
        'success': True,
        'query': q,
        'results': {
            'patients': formatted_patients,
            'beds': beds,
            'users': formatted_users
        },
        'total': total_count
    }), 200
