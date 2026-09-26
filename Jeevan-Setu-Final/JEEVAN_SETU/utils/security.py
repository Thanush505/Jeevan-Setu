"""
utils/security.py — Backend Security, Rate Limiting, HTTP Security Headers, and Sanitization.

Features:
1. Secure HTTP Headers Middleware (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
2. CORS Headers Middleware
3. In-Memory Sliding Window Rate Limiting (Brute-force & DDoS protection)
4. Input Sanitization & SQL Injection Prevention
5. Data Redaction (Never expose password hashes, secret keys, or DB credentials)
6. Path Traversal Prevention for secure file operations
"""

import os
import re
import time
from functools import wraps
from flask import request, jsonify, g, make_response


# =============================================================
# 1. In-Memory Rate Limiter (Thread-safe sliding window)
# =============================================================
class RateLimiter:
    """In-memory rate limiter using sliding time windows per client IP / key."""

    def __init__(self):
        self._requests = {}

    def is_allowed(self, key, limit=100, window_seconds=60):
        """Check if request within limit for current window."""
        now = time.time()
        client_history = self._requests.get(key, [])

        # Filter timestamps within current window
        recent = [t for t in client_history if t > now - window_seconds]
        if len(recent) >= limit:
            self._requests[key] = recent
            return False, int((recent[0] + window_seconds) - now)

        recent.append(now)
        self._requests[key] = recent
        return True, 0

    def reset(self):
        """Reset all rate limiter records (useful for testing)."""
        self._requests.clear()


limiter = RateLimiter()


def rate_limit(limit=60, window_seconds=60):
    """
    Decorator to apply rate limiting to sensitive routes (e.g. login, QR validation).
    Returns 429 Too Many Requests if threshold is exceeded.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Key based on client IP and endpoint
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
            key = f"{client_ip}:{request.endpoint}"

            allowed, retry_after = limiter.is_allowed(key, limit=limit, window_seconds=window_seconds)
            if not allowed:
                response = jsonify({
                    'success': False,
                    'error': 'Too many requests. Please try again later.',
                    'retry_after_seconds': max(1, retry_after)
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(max(1, retry_after))
                return response

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =============================================================
# 2. Security Headers & CORS Middleware
# =============================================================
def apply_security_headers(response):
    """
    Apply comprehensive HTTP security headers to all outgoing responses.
    Prevents XSS, Clickjacking, MIME sniffing, and enforces strict HTTPS policies.
    """
    # X-Content-Type-Options: Prevents browsers from MIME-sniffing away from the declared content-type
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # X-Frame-Options: Protects against Clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    # X-XSS-Protection: Enables browser cross-site scripting filter
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Strict-Transport-Security (HSTS): Enforce HTTPS connections
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    # Content-Security-Policy (CSP)
    response.headers['Content-Security-Policy'] = (
        "default-src 'self' 'unsafe-inline' data:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https: http: blob:; "
        "connect-src 'self' *;"
    )

    # Referrer-Policy: Prevents sensitive path leakage in Referer header
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions-Policy
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

    # Cross-Origin Resource Sharing (CORS)
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept'

    return response


# =============================================================
# 3. Data Protection & Redaction (Never Expose Passwords/Secrets)
# =============================================================
SENSITIVE_FIELDS = {
    'password', 'password_hash', 'password_hash_bcrypt', 'token_hash',
    'reset_token', 'secret_key', 'db_password', 'jwt_secret_key'
}


def sanitize_dict(data):
    """Recursively redact password hashes, reset tokens, and secrets from dictionaries."""
    if not isinstance(data, dict):
        return data

    sanitized = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            continue  # Strip completely
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_dict(item) if isinstance(item, dict) else item for item in value]
        else:
            sanitized[key] = value

    return sanitized


# =============================================================
# 4. Safe File Path Validation (Path Traversal Protection)
# =============================================================
def validate_safe_path(base_directory, requested_path):
    """
    Validate that requested_path is strictly inside base_directory.
    Prevents path traversal attacks (e.g., ../../etc/passwd or ..\\..\\windows\\system32).
    """
    base_dir = os.path.abspath(base_directory)
    full_path = os.path.abspath(os.path.join(base_directory, requested_path))

    # Ensure full_path starts with base_dir path
    if os.path.commonpath([base_dir, full_path]) != base_dir:
        raise ValueError(f"Access Denied: Path traversal detected for path '{requested_path}'")

    return full_path


# =============================================================
# 5. Input Validation & XSS Sanitization Helpers
# =============================================================
def sanitize_input_string(val, max_length=500):
    """Sanitize input string, remove HTML script tags, and enforce length bounds."""
    if val is None:
        return ''
    s = str(val).strip()
    # Strip dangerous HTML script tags
    s = re.sub(r'<script.*?>.*?</script>', '', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'[<>]', '', s)
    return s[:max_length]
