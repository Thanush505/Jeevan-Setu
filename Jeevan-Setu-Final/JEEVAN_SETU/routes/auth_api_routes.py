"""
routes/auth_api_routes.py — REST API endpoints for Jeevan Setu Phase 3 Authentication.
Endpoints:
    POST /api/v1/auth/login
    POST /api/v1/auth/logout
    POST /api/v1/auth/forgot-password
    POST /api/v1/auth/reset-password
    GET  /api/v1/auth/me
"""

from flask import Blueprint, request, jsonify, g
from flask_login import logout_user
from services.auth_service import AuthService
from database.db import db
from models.user_model import User, verify_pw, hash_pw
from models.audit_log_model import AuditLog
from utils.auth_middleware import auth_required, get_token_from_header
from utils.validators import validate_email
from utils.constants import ROLES

auth_api_bp = Blueprint('auth_api', __name__)


# ─────────────────────────────────────────────────────────────
# 1. POST /api/v1/auth/login
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/login', methods=['POST'])
def api_login():
    """
    Authenticate user and return JWT access token and profile info.
    Payload:
        { "username": "admin", "password": "admin123" }
        or
        { "email": "admin@jeevansetu.com", "password": "admin123" }
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({
            'success': False,
            'error': 'Missing JSON body. Provide username/email and password.'
        }), 400

    identifier = (data.get('username') or data.get('email') or '').strip()
    password = data.get('password', '')

    if not identifier or not password:
        return jsonify({
            'success': False,
            'error': 'Both username/email and password are required'
        }), 422

    user, err = AuthService.authenticate_credentials(identifier, password)
    if err:
        status_code = 403 if 'deactivated' in err.lower() else 401
        return jsonify({'success': False, 'error': err}), status_code

    # Generate JWT access token
    token_data = AuthService.generate_access_token(user)

    # Log login to audit trail
    AuditLog.log(
        action='api_login',
        user_id=user.id,
        entity_type='user',
        entity_id=user.id,
        ip_address=request.remote_addr,
        description=f"User {user.username} authenticated via REST API"
    )

    return jsonify({
        'success': True,
        'message': 'Authentication successful',
        'data': {
            'token': token_data['access_token'],
            'token_type': token_data['token_type'],
            'expires_in': token_data['expires_in'],
            'expires_at': token_data['expires_at'],
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'department': user.department,
                'is_active': user.is_active,
                'permissions': ROLES.get(user.role, [])
            }
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. POST /api/v1/auth/logout
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/logout', methods=['POST'])
@auth_required
def api_logout():
    """
    Revoke JWT access token and terminate session.
    Header:
        Authorization: Bearer <token>
    """
    user = getattr(g, 'current_user', None)
    token = get_token_from_header() or getattr(g, 'jwt_token', None)

    if token:
        AuthService.blacklist_token(token, user_id=user.id if user else None)

    try:
        logout_user()
    except Exception:
        pass

    if user:
        AuditLog.log(
            action='api_logout',
            user_id=user.id,
            entity_type='user',
            entity_id=user.id,
            ip_address=request.remote_addr,
            description=f"User {user.username} logged out via REST API"
        )

    return jsonify({
        'success': True,
        'message': 'Successfully logged out. Token has been revoked.'
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. POST /api/v1/auth/forgot-password
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/forgot-password', methods=['POST'])
def api_forgot_password():
    """
    Initiate password reset process by generating a time-limited reset token.
    Payload:
        { "email": "user@example.com" } or { "username": "dr_sharma" }
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({
            'success': False,
            'error': 'Missing JSON body. Provide email or username.'
        }), 400

    identifier = (data.get('email') or data.get('username') or '').strip()
    if not identifier:
        return jsonify({
            'success': False,
            'error': 'Email or username is required'
        }), 422

    raw_token, user_dict, err = AuthService.create_password_reset_token(identifier)
    if err:
        # Avoid user enumeration in public API response while logging internal
        return jsonify({
            'success': False,
            'error': err
        }), 404

    # Log password reset request
    AuditLog.log(
        action='password_reset_requested',
        user_id=user_dict['user_id'],
        entity_type='user',
        entity_id=user_dict['user_id'],
        ip_address=request.remote_addr,
        description=f"Password reset token requested for user {user_dict['username']}"
    )

    return jsonify({
        'success': True,
        'message': 'Password reset token generated successfully. In production, this is emailed to the user.',
        'data': {
            'reset_token': raw_token,
            'user_id': user_dict['user_id'],
            'email': user_dict['email']
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. POST /api/v1/auth/reset-password
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/reset-password', methods=['POST'])
def api_reset_password():
    """
    Reset password using a valid reset token.
    Payload:
        { "token": "RESET-...", "new_password": "NewSecurePassword123!" }
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({
            'success': False,
            'error': 'Missing JSON body. Provide token and new_password.'
        }), 400

    token = (data.get('token') or data.get('reset_token') or '').strip()
    new_password = data.get('new_password', '')

    if not token or not new_password:
        return jsonify({
            'success': False,
            'error': 'Both reset token and new_password are required'
        }), 422

    if len(new_password) < 6:
        return jsonify({
            'success': False,
            'error': 'New password must be at least 6 characters long'
        }), 422

    success, msg = AuthService.reset_password_with_token(
        token,
        new_password,
        ip_address=request.remote_addr
    )

    if not success:
        return jsonify({'success': False, 'error': msg}), 400

    return jsonify({
        'success': True,
        'message': 'Password has been reset successfully. You may now log in with your new password.'
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. GET /api/v1/auth/me — Current Authenticated Profile & Details
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/me', methods=['GET'])
@auth_required
def api_get_current_user():
    """
    Fetch details, role-specific metadata, and permissions of the currently authenticated user.
    Header:
        Authorization: Bearer <token>
    """
    user = getattr(g, 'current_user', None)
    if not user:
        return jsonify({'success': False, 'error': 'User context not found'}), 401

    permissions = ROLES.get(user.role, [])

    # Fetch role-specific details
    nurse_details = None
    doctor_details = None

    if user.role == 'nurse':
        n_res = db.execute_query(
            "SELECT nurse_id, specialization, license_number, qualification, ward_assignment, shift, experience_years FROM nurses WHERE user_id = %s OR username = %s LIMIT 1",
            (user.id, user.username), fetch=True
        )
        if n_res:
            nurse_details = n_res[0]

    elif user.role == 'doctor':
        d_res = db.execute_query(
            "SELECT doctor_id, specialization, license_number, qualification, experience_years FROM doctors WHERE user_id = %s OR username = %s LIMIT 1",
            (user.id, user.username), fetch=True
        )
        if d_res:
            doctor_details = d_res[0]

    # Fetch user preferences
    pref_res = db.execute_query(
        "SELECT in_app_notifications, critical_patient_alerts, ews_alerts, task_notifications, sound_alerts, theme FROM user_preferences WHERE user_id = %s",
        (user.id,), fetch=True
    )
    preferences = {
        'in_app_notifications': True,
        'critical_patient_alerts': True,
        'ews_alerts': True,
        'task_notifications': True,
        'sound_alerts': True,
        'theme': 'light'
    }
    if pref_res:
        p = pref_res[0]
        preferences = {
            'in_app_notifications': bool(p.get('in_app_notifications', 1)),
            'critical_patient_alerts': bool(p.get('critical_patient_alerts', 1)),
            'ews_alerts': bool(p.get('ews_alerts', 1)),
            'task_notifications': bool(p.get('task_notifications', 1)),
            'sound_alerts': bool(p.get('sound_alerts', 1)),
            'theme': p.get('theme') or 'light'
        }

    # Determine ward / specialization / qualification convenience attributes
    ward = user.department or ''
    specialization = None
    qualification = None
    avatar = '../nurse_avatar.jpg' if user.role == 'nurse' else ''

    if user.role == 'nurse' and nurse_details:
        ward = nurse_details.get('ward_assignment') or user.department or 'ICU'
        specialization = nurse_details.get('specialization')
        qualification = nurse_details.get('qualification')

    return jsonify({
        'success': True,
        'data': {
            'id': user.id,
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role,
            'department': user.department,
            'ward': ward,
            'specialization': specialization,
            'qualification': qualification,
            'avatar': avatar,
            'is_active': user.is_active,
            'permissions': permissions,
            'nurse_details': nurse_details,
            'doctor_details': doctor_details,
            'preferences': preferences
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 6. PUT /api/v1/auth/profile — Update Own Profile
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/profile', methods=['PUT', 'POST'])
@auth_required
def api_update_profile():
    """
    Allow authenticated user (e.g. Nurse) to update their allowed profile fields.
    Payload:
        { "full_name": "Sr. Nurse Priya Sharma", "email": "priya@jeevansetu.org", "phone": "9876543210", "qualification": "B.Sc Nursing" }
    """
    user = getattr(g, 'current_user', None)
    if not user:
        return jsonify({'success': False, 'error': 'User context not found'}), 401

    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({'success': False, 'error': 'Missing request body'}), 400

    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    qualification = (data.get('qualification') or '').strip()
    specialization = (data.get('specialization') or '').strip()

    if not full_name:
        return jsonify({'success': False, 'error': 'Full name cannot be empty'}), 422

    if email and not validate_email(email):
        return jsonify({'success': False, 'error': 'Invalid email address format'}), 422

    # Check if email is used by another user
    if email:
        existing = db.execute_query("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (email, user.id), fetch=True)
        if existing:
            return jsonify({'success': False, 'error': 'This email is already in use by another account'}), 409

    # Update users table (prevent modifying role, role_id, is_active)
    update_fields = ["full_name = %s"]
    update_params = [full_name]

    if email:
        update_fields.append("email = %s")
        update_params.append(email)

    update_params.append(user.id)
    db.execute_query(f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s", tuple(update_params))

    # Sync with role-specific tables (e.g. nurses)
    if user.role == 'nurse':
        nurse_updates = ["full_name = %s"]
        nurse_params = [full_name]
        if email:
            nurse_updates.append("email = %s")
            nurse_params.append(email)
        if qualification:
            nurse_updates.append("qualification = %s")
            nurse_params.append(qualification)
        if specialization:
            nurse_updates.append("specialization = %s")
            nurse_params.append(specialization)
        nurse_params.append(user.id)
        db.execute_query(f"UPDATE nurses SET {', '.join(nurse_updates)} WHERE user_id = %s", tuple(nurse_params))

    elif user.role == 'doctor':
        doc_updates = ["full_name = %s"]
        doc_params = [full_name]
        if email:
            doc_updates.append("email = %s")
            doc_params.append(email)
        if qualification:
            doc_updates.append("qualification = %s")
            doc_params.append(qualification)
        if specialization:
            doc_updates.append("specialization = %s")
            doc_params.append(specialization)
        doc_params.append(user.id)
        db.execute_query(f"UPDATE doctors SET {', '.join(doc_updates)} WHERE user_id = %s", tuple(doc_params))

    AuditLog.log(
        action='update_profile',
        user_id=user.id,
        entity_type='user',
        entity_id=user.id,
        ip_address=request.remote_addr,
        description=f"User #{user.id} ({user.username}) updated their profile details"
    )

    # Return refreshed user state
    return jsonify({
        'success': True,
        'message': 'Profile updated successfully',
        'data': {
            'id': user.id,
            'user_id': user.id,
            'username': user.username,
            'full_name': full_name,
            'email': email or user.email,
            'role': user.role,
            'department': user.department
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 7. POST /api/v1/auth/change-password — Self Password Change
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/change-password', methods=['POST'])
@auth_required
def api_change_password():
    """
    Secure password change for the logged-in user.
    Payload:
        { "current_password": "...", "new_password": "...", "confirm_password": "..." }
    """
    user = getattr(g, 'current_user', None)
    if not user:
        return jsonify({'success': False, 'error': 'User context not found'}), 401

    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({'success': False, 'error': 'Missing JSON body'}), 400

    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    confirm_pw = data.get('confirm_password', '')

    if not current_pw or not new_pw or not confirm_pw:
        return jsonify({'success': False, 'error': 'Current password, new password, and confirmation are required'}), 422

    if new_pw != confirm_pw:
        return jsonify({'success': False, 'error': 'New password and confirmation do not match'}), 422

    if len(new_pw) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters long'}), 422

    # Fetch stored password hash
    user_rows = db.execute_query("SELECT password_hash FROM users WHERE user_id = %s", (user.id,), fetch=True)
    if not user_rows or not user_rows[0].get('password_hash'):
        return jsonify({'success': False, 'error': 'User account not found'}), 404

    stored_hash = user_rows[0]['password_hash']
    if not verify_pw(current_pw, stored_hash):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400

    # Hash new password and update
    new_hash = hash_pw(new_pw)
    db.execute_query("UPDATE users SET password_hash = %s WHERE user_id = %s", (new_hash, user.id))

    # Sync with nurses/doctors if applicable
    if user.role == 'nurse':
        db.execute_query("UPDATE nurses SET password_hash = %s WHERE user_id = %s", (new_hash, user.id))
    elif user.role == 'doctor':
        db.execute_query("UPDATE doctors SET password_hash = %s WHERE user_id = %s", (new_hash, user.id))

    AuditLog.log(
        action='change_password',
        user_id=user.id,
        entity_type='user',
        entity_id=user.id,
        ip_address=request.remote_addr,
        description=f"User #{user.id} ({user.username}) changed their password"
    )

    return jsonify({
        'success': True,
        'message': 'Password has been changed successfully.'
    }), 200


# ─────────────────────────────────────────────────────────────
# 8. GET & PUT /api/v1/auth/preferences — User Notification & UI Settings
# ─────────────────────────────────────────────────────────────
@auth_api_bp.route('/preferences', methods=['GET', 'PUT', 'POST'])
@auth_required
def api_user_preferences():
    """
    Get or update notification and display preferences for current user.
    """
    user = getattr(g, 'current_user', None)
    if not user:
        return jsonify({'success': False, 'error': 'User context not found'}), 401

    if request.method == 'GET':
        pref_res = db.execute_query(
            "SELECT in_app_notifications, critical_patient_alerts, ews_alerts, task_notifications, sound_alerts, theme FROM user_preferences WHERE user_id = %s",
            (user.id,), fetch=True
        )
        if pref_res:
            p = pref_res[0]
            data = {
                'in_app_notifications': bool(p.get('in_app_notifications', 1)),
                'critical_patient_alerts': bool(p.get('critical_patient_alerts', 1)),
                'ews_alerts': bool(p.get('ews_alerts', 1)),
                'task_notifications': bool(p.get('task_notifications', 1)),
                'sound_alerts': bool(p.get('sound_alerts', 1)),
                'theme': p.get('theme') or 'light'
            }
        else:
            data = {
                'in_app_notifications': True,
                'critical_patient_alerts': True,
                'ews_alerts': True,
                'task_notifications': True,
                'sound_alerts': True,
                'theme': 'light'
            }
        return jsonify({'success': True, 'data': data}), 200

    # PUT / POST update preferences
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    in_app = 1 if data.get('in_app_notifications', True) in (True, 'true', 1, '1') else 0
    critical = 1 if data.get('critical_patient_alerts', True) in (True, 'true', 1, '1') else 0
    ews = 1 if data.get('ews_alerts', True) in (True, 'true', 1, '1') else 0
    tasks = 1 if data.get('task_notifications', True) in (True, 'true', 1, '1') else 0
    sound = 1 if data.get('sound_alerts', True) in (True, 'true', 1, '1') else 0
    theme = data.get('theme', 'light')

    db.execute_query(
        """INSERT INTO user_preferences (user_id, in_app_notifications, critical_patient_alerts, ews_alerts, task_notifications, sound_alerts, theme)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
               in_app_notifications = VALUES(in_app_notifications),
               critical_patient_alerts = VALUES(critical_patient_alerts),
               ews_alerts = VALUES(ews_alerts),
               task_notifications = VALUES(task_notifications),
               sound_alerts = VALUES(sound_alerts),
               theme = VALUES(theme)""",
        (user.id, in_app, critical, ews, tasks, sound, theme)
    )

    return jsonify({
        'success': True,
        'message': 'Preferences saved successfully.',
        'data': {
            'in_app_notifications': bool(in_app),
            'critical_patient_alerts': bool(critical),
            'ews_alerts': bool(ews),
            'task_notifications': bool(tasks),
            'sound_alerts': bool(sound),
            'theme': theme
        }
    }), 200

