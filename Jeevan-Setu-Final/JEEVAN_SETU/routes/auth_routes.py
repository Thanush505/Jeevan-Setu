"""
routes/auth_routes.py — Authentication and user management routes.
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models.user_model import User
from models.audit_log_model import AuditLog
from utils.decorators import role_required
from utils.validators import validate_email, validate_username

auth_bp = Blueprint('auth', __name__)


# ─────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login and redirect to role-specific dashboard."""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect('/Admin/Administrator_dashboard_/Administrator_dashboard_.html')
        elif current_user.role == 'doctor':
            return redirect('/Doctor/Doctor_dashboard_/Doctor_dashboard_.html')
        elif current_user.role == 'nurse':
            return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')
        elif current_user.role == 'attendant':
            return redirect('/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html')
        return redirect('/Doctor/Doctor_dashboard_/Doctor_dashboard_.html')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('Login/Login.html')

        user = User.authenticate(username, password)
        if user:
            if not user.is_active:
                flash('Your account has been deactivated. Contact an admin.', 'error')
                return render_template('Login/Login.html')

            login_user(user)
            AuditLog.log(
                action='login',
                user_id=user.id,
                ip_address=request.remote_addr,
                description=f'User {username} logged in'
            )
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            if next_page and not next_page.endswith('/patients/dashboard') and not next_page.endswith('/patients/'):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect('/Admin/Administrator_dashboard_/Administrator_dashboard_.html')
            elif user.role == 'doctor':
                return redirect('/Doctor/Doctor_dashboard_/Doctor_dashboard_.html')
            elif user.role == 'nurse':
                return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')
            elif user.role == 'attendant':
                return redirect('/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html')
            return redirect('/Doctor/Doctor_dashboard_/Doctor_dashboard_.html')
        else:
            flash('Invalid username or password.', 'error')

    return render_template('Login/Login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    AuditLog.log(
        action='logout',
        user_id=current_user.id,
        ip_address=request.remote_addr,
        description=f'User {current_user.username} logged out'
    )
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────
# User Management (Admin Only)
# ─────────────────────────────────────────────

@auth_bp.route('/users')
@role_required('admin')
def user_list():
    """List all users (admin only)."""
    users = User.get_all()
    return render_template('Admin/Admin_users_roles/Admin_users_roles.html', users=users)


@auth_bp.route('/register', methods=['GET', 'POST'])
@role_required('admin')
def register():
    """Register a new user (admin only)."""
    if request.method == 'POST':
        data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', 'nurse')
        department = data.get('department', '').strip() or None

        # Validation
        errors = []
        if not username or not validate_username(username):
            errors.append('Username must be 3-50 alphanumeric characters.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if not full_name or len(full_name) < 2:
            errors.append('Full name is required (min 2 characters).')
        if not email or not validate_email(email):
            errors.append('A valid email is required.')
        if role not in ('admin', 'doctor', 'nurse', 'attendant'):
            errors.append('Invalid role selected.')

        # Check duplicates
        if not errors:
            if User.get_by_username(username):
                errors.append(f'Username "{username}" is already taken.')
            existing_email = User.get_by_email(email)
            if existing_email:
                errors.append(f'Email "{email}" is already registered.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('Admin/Admin_users_roles/Admin_users_roles.html')

        try:
            user_id = User.create(
                username=username,
                password=password,
                full_name=full_name,
                email=email,
                role=role,
                department=department
            )
            AuditLog.log(
                action='create_user',
                user_id=current_user.id,
                entity_type='user',
                entity_id=user_id,
                ip_address=request.remote_addr,
                description=f'Created user {username} with role {role}'
            )
            flash(f'User "{username}" registered successfully!', 'success')
            return redirect(url_for('auth.user_list'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')

    return render_template('Admin/Admin_users_roles/Admin_users_roles.html')


@auth_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(user_id):
    """Activate/deactivate a user (admin only)."""
    if user_id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('auth.user_list'))

    user = User.get_by_id(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.user_list'))

    new_status = not user.is_active
    User.update(user_id, is_active=new_status)

    action = 'activated' if new_status else 'deactivated'
    AuditLog.log(
        action=f'{action}_user',
        user_id=current_user.id,
        entity_type='user',
        entity_id=user_id,
        ip_address=request.remote_addr,
        description=f'User {user.username} {action}'
    )
    flash(f'User "{user.username}" has been {action}.', 'success')
    return redirect(url_for('auth.user_list'))


@auth_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@role_required('admin')
def edit_user(user_id):
    """Edit user details (admin only)."""
    data = request.form
    role = data.get('role')
    department = data.get('department', '').strip() or None

    if role and role not in ('admin', 'doctor', 'nurse', 'attendant'):
        flash('Invalid role.', 'error')
        return redirect(url_for('auth.user_list'))

    updates = {}
    if role:
        updates['role'] = role
    if department is not None:
        updates['department'] = department

    if updates:
        User.update(user_id, **updates)
        AuditLog.log(
            action='edit_user',
            user_id=current_user.id,
            entity_type='user',
            entity_id=user_id,
            ip_address=request.remote_addr,
            description=f'Updated user {user_id}: {updates}'
        )
        flash('User updated successfully.', 'success')

    return redirect(url_for('auth.user_list'))
