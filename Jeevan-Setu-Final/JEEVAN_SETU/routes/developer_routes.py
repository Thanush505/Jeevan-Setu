"""
routes/developer_routes.py — Developer Tools & Telemetry Simulator Diagnostics APIs.
RBAC: Restricted to Administrator / Developer privileges only.
"""

import time
from flask import Blueprint, jsonify, request
from database.db import db
from utils.decorators import get_current_authenticated_user

developer_bp = Blueprint('developer', __name__)


@developer_bp.route('/telemetry-simulator/verify-access', methods=['GET'])
def verify_access():
    """Return caller authentication details for the telemetry simulator."""
    user = get_current_authenticated_user()
    if user and user.is_authenticated:
        return jsonify({
            'success': True,
            'message': f'Access granted ({user.role}).',
            'data': {
                'authenticated': True,
                'user_id': user.id,
                'username': user.username,
                'full_name': getattr(user, 'full_name', user.username),
                'role': user.role
            }
        }), 200

    return jsonify({
        'success': True,
        'message': 'Public testing mode (unauthenticated).',
        'data': {
            'authenticated': False,
            'user_id': None,
            'username': 'Guest / Developer',
            'full_name': 'Developer Tester',
            'role': 'DEVELOPER_TESTER'
        }
    }), 200


@developer_bp.route('/telemetry-simulator/health', methods=['GET'])
def get_db_health():
    """
    Database Health & Diagnostics check for simulator testing.
    Measures SQL execution round-trip latency without exposing credentials.
    """

    start_time = time.perf_counter()
    try:
        res = db.execute_query("SELECT 1 AS ping", fetch='one')
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        pool_active = getattr(db, '_pool', None) is not None

        return jsonify({
            'success': True,
            'data': {
                'status': 'connected',
                'query_success': bool(res and res.get('ping') == 1),
                'latency_ms': elapsed_ms,
                'pool_active': pool_active,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return jsonify({
            'success': False,
            'data': {
                'status': 'disconnected',
                'query_success': False,
                'latency_ms': elapsed_ms,
                'error': 'Database query failed'
            }
        }), 503
