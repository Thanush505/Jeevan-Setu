"""
services/auth_service.py — Core Authentication, JWT Token, and Password Reset Service.
"""

import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import jwt
from config import get_config
from database.db import db
from models.user_model import User, hash_pw, verify_pw
from models.audit_log_model import AuditLog


class AuthService:
    """Provides JWT token management, user authentication, and password reset flows."""

    @staticmethod
    def generate_access_token(user, expires_in_seconds=None):
        """Generate a signed JWT access token for a user."""
        config = get_config()
        expires_in = expires_in_seconds or config.JWT_ACCESS_TOKEN_EXPIRES
        now = datetime.now(timezone.utc)
        jti = uuid.uuid4().hex

        user_id = user.id if hasattr(user, 'id') else user['user_id']
        payload = {
            'sub': str(user_id),
            'username': user.username if hasattr(user, 'username') else user['username'],
            'email': user.email if hasattr(user, 'email') else user['email'],
            'role': user.role if hasattr(user, 'role') else user['role'],
            'department': user.department if hasattr(user, 'department') else user.get('department'),
            'jti': jti,
            'iat': now,
            'exp': now + timedelta(seconds=expires_in)
        }

        token = jwt.encode(
            payload,
            config.JWT_SECRET_KEY,
            algorithm=config.JWT_ALGORITHM
        )

        return {
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': expires_in,
            'expires_at': (now + timedelta(seconds=expires_in)).isoformat(),
            'jti': jti
        }

    @staticmethod
    def decode_access_token(token):
        """
        Validate and decode a JWT access token.
        Checks signature, expiration, and checks against the token blacklist.
        """
        config = get_config()
        try:
            payload = jwt.decode(
                token,
                config.JWT_SECRET_KEY,
                algorithms=[config.JWT_ALGORITHM]
            )

            # Check if token JTI is blacklisted
            jti = payload.get('jti')
            if jti and AuthService.is_token_blacklisted(jti):
                return None, 'Token has been revoked/logged out'

            return payload, None
        except jwt.ExpiredSignatureError:
            return None, 'Token has expired'
        except jwt.InvalidTokenError as e:
            return None, f'Invalid token: {str(e)}'

    @staticmethod
    def is_token_blacklisted(jti):
        """Check if a token JTI is present in the blacklist table."""
        try:
            result = db.execute_query(
                "SELECT blacklist_id FROM token_blacklist WHERE token_jti = %s",
                (jti,), fetch=True
            )
            return len(result) > 0
        except Exception:
            return False

    @staticmethod
    def blacklist_token(token_or_jti, user_id=None, expires_at=None):
        """Revoke a token by adding its JTI to the blacklist table."""
        if not token_or_jti:
            return False

        jti = token_or_jti
        if len(token_or_jti) > 64:  # Likely a full JWT string
            payload, _ = AuthService.decode_access_token(token_or_jti)
            if payload:
                jti = payload.get('jti')
                user_id = user_id or payload.get('sub')
                if 'exp' in payload:
                    expires_at = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)

        if not jti:
            return False

        exp = expires_at or (datetime.now(timezone.utc) + timedelta(days=7))
        try:
            db.execute_query(
                """INSERT IGNORE INTO token_blacklist (token_jti, token_type, user_id, expires_at)
                   VALUES (%s, 'access', %s, %s)""",
                (jti, user_id, exp)
            )
            return True
        except Exception as e:
            print(f"[AUTH ERROR] Failed to blacklist token: {e}")
            return False

    @staticmethod
    def authenticate_credentials(username_or_email, password):
        """
        Authenticate user with username or email and password.
        Returns: (user_obj, error_message)
        """
        if not username_or_email or not password:
            return None, 'Username/Email and password are required'

        # Look up by username first, then by email
        user_row = User.get_by_username(username_or_email)
        if not user_row:
            user_row = User.get_by_email(username_or_email)

        if not user_row:
            return None, 'Invalid credentials'

        # Check account active status
        if not user_row.get('is_active', True):
            return None, 'Account has been deactivated. Please contact an administrator.'

        # Verify password hash
        if not verify_pw(password, user_row.get('password_hash', '')):
            return None, 'Invalid credentials'

        user_obj = User(
            user_row['user_id'], user_row['username'], user_row['full_name'],
            user_row['email'], user_row['role'], user_row.get('department'),
            user_row.get('is_active', True), user_row.get('role_id')
        )
        return user_obj, None

    @staticmethod
    def create_password_reset_token(email_or_username):
        """
        Generate a secure time-limited password reset token.
        Returns: (raw_token, user_dict, error)
        """
        user_row = User.get_by_email(email_or_username)
        if not user_row:
            user_row = User.get_by_username(email_or_username)

        if not user_row:
            return None, None, 'User not found with provided identifier'

        if not user_row.get('is_active', True):
            return None, None, 'Account is deactivated'

        config = get_config()
        raw_token = f"RESET-{user_row['user_id']}-{uuid.uuid4().hex}"
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expires_at = datetime.now() + timedelta(seconds=config.PASSWORD_RESET_TIMEOUT)

        # Invalidate old unused reset tokens for this user
        db.execute_query(
            "UPDATE password_reset_tokens SET is_used = TRUE WHERE user_id = %s AND is_used = FALSE",
            (user_row['user_id'],)
        )

        # Insert new reset token
        db.execute_query(
            """INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, is_used)
               VALUES (%s, %s, %s, FALSE)""",
            (user_row['user_id'], token_hash, expires_at)
        )

        return raw_token, user_row, None

    @staticmethod
    def verify_reset_token(raw_token):
        """
        Verify password reset token validity.
        Returns: (user_id, error_message)
        """
        if not raw_token:
            return None, 'Token is required'

        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        result = db.execute_query(
            """SELECT * FROM password_reset_tokens 
               WHERE token_hash = %s AND is_used = FALSE AND expires_at > NOW()""",
            (token_hash,), fetch=True
        )

        if not result:
            return None, 'Password reset token is invalid or has expired'

        return result[0]['user_id'], None

    @staticmethod
    def reset_password_with_token(raw_token, new_password, ip_address=None):
        """
        Reset user password using token in an atomic transaction.
        """
        if not new_password or len(new_password) < 6:
            return False, 'Password must be at least 6 characters long'

        user_id, err = AuthService.verify_reset_token(raw_token)
        if err:
            return False, err

        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        pw_hash = hash_pw(new_password)

        with db.transaction() as cursor:
            # Update password
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE user_id = %s",
                (pw_hash, user_id)
            )

            # Mark token as used
            cursor.execute(
                "UPDATE password_reset_tokens SET is_used = TRUE WHERE token_hash = %s",
                (token_hash,)
            )

        # Log to audit trail
        try:
            AuditLog.log(
                action='password_reset_token_success',
                user_id=user_id,
                entity_type='user',
                entity_id=user_id,
                ip_address=ip_address,
                description='Password reset successfully using reset token'
            )
        except Exception:
            pass

        return True, 'Password has been reset successfully'
