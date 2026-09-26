"""
utils/auth_middleware.py — Authentication and Authorization Middlewares/Decorators.
Supports JWT Bearer Tokens (REST APIs) and Flask-Login Session Cookies.
"""

from functools import wraps
from flask import request, jsonify, g, flash, redirect, url_for
from flask_login import current_user
from services.auth_service import AuthService
from models.user_model import User
from utils.constants import ROLES


def get_token_from_header():
    """Extract Bearer token from Authorization header or query param."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return request.args.get('token')


def jwt_required(f):
    """
    Middleware requiring a valid JWT Bearer token in the Authorization header.
    Attaches authenticated User object to flask.g.current_user and request.user.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        if not token:
            return jsonify({
                'success': False,
                'error': 'Missing authentication token. Use header: Authorization: Bearer <token>'
            }), 401

        payload, err = AuthService.decode_access_token(token)
        if err:
            return jsonify({'success': False, 'error': err}), 401

        sub_val = payload.get('sub')
        user_id = int(sub_val) if sub_val is not None else None
        user = User.get_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User associated with token not found'}), 401

        if not user.is_active:
            return jsonify({'success': False, 'error': 'Account has been deactivated'}), 403

        # Store in Flask global context
        g.current_user = user
        g.jwt_payload = payload
        g.jwt_token = token
        request.user = user

        return f(*args, **kwargs)
    return decorated


def auth_required(f):
    """
    Hybrid authentication middleware.
    Checks for JWT Bearer token first; if not present, falls back to Flask-Login session.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Check for JWT token
        token = get_token_from_header()
        if token:
            payload, err = AuthService.decode_access_token(token)
            if err:
                return jsonify({'success': False, 'error': err}), 401

            sub_val = payload.get('sub')
            user_id = int(sub_val) if sub_val is not None else None
            user = User.get_by_id(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 401
            if not user.is_active:
                return jsonify({'success': False, 'error': 'Account deactivated'}), 403

            g.current_user = user
            g.jwt_payload = payload
            g.jwt_token = token
            request.user = user
            return f(*args, **kwargs)

        # 2. Check for Session / Flask-Login
        if current_user and current_user.is_authenticated:
            if not current_user.is_active:
                if _is_api_request():
                    return jsonify({'success': False, 'error': 'Account deactivated'}), 403
                flash('Account deactivated.', 'error')
                return redirect(url_for('auth.login'))

            g.current_user = current_user
            request.user = current_user
            return f(*args, **kwargs)

        # 3. Not authenticated
        if _is_api_request():
            return jsonify({
                'success': False,
                'error': 'Authentication required. Provide Bearer token or log in.'
            }), 401

        flash('Please log in to continue.', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    return decorated


def require_roles(*allowed_roles):
    """
    Authorization decorator restricting access to users with specified roles.
    """
    def decorator(f):
        @wraps(f)
        @auth_required
        def decorated_function(*args, **kwargs):
            user = getattr(g, 'current_user', current_user)
            if not user or not user.is_authenticated:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401

            if user.role not in allowed_roles and 'admin' not in allowed_roles:
                if user.role != 'admin':
                    return jsonify({
                        'success': False,
                        'error': f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
                    }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def _is_api_request():
    """Detect if current request is an API request."""
    return (
        request.path.startswith('/api/') or
        request.accept_mimetypes.best == 'application/json' or
        request.content_type == 'application/json'
    )
