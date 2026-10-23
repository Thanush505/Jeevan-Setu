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


@developer_bp.route('/telemetry-simulator/scenarios', methods=['GET'])
def get_all_scenarios():
    """
    Return authoritative current scenarios for all patients, along with supported
    scenario definitions and valid transition metadata.
    """
    try:
        rows = db.execute_query(
            """SELECT p.patient_id, p.name, p.patient_code, p.bed_number, p.status,
                      COALESCE(s.current_scenario, 'STABLE') as current_scenario,
                      s.previous_scenario,
                      s.transition_status,
                      s.last_transition_time
               FROM patients p
               LEFT JOIN simulator_patient_states s ON p.patient_id = s.patient_id
               WHERE p.status = 'admitted'
               ORDER BY p.patient_id ASC""",
            fetch=True
        ) or []

        states = {}
        for r in rows:
            scen = r['current_scenario']
            if scen in ['GRADUAL_DETERIORATION', 'DETERIORATION']:
                scen = 'MODERATE'
            prev = r['previous_scenario']
            if prev in ['GRADUAL_DETERIORATION', 'DETERIORATION']:
                prev = 'MODERATE'
            states[str(r['patient_id'])] = {
                'patient_id': r['patient_id'],
                'name': r['name'],
                'patient_code': r.get('patient_code'),
                'bed_number': r.get('bed_number'),
                'current_scenario': scen,
                'previous_scenario': prev,
                'transition_status': r.get('transition_status') or 'ACTIVE',
                'last_transition_time': str(r['last_transition_time']) if r.get('last_transition_time') else None
            }

        supported_scenarios = ['STABLE', 'MODERATE', 'CRITICAL', 'RECOVERY', 'MANUAL']
        transitions = {
            'STABLE': ['MODERATE', 'CRITICAL', 'RECOVERY', 'MANUAL'],
            'MODERATE': ['STABLE', 'CRITICAL', 'RECOVERY', 'MANUAL'],
            'CRITICAL': ['MODERATE', 'STABLE', 'RECOVERY', 'MANUAL'],
            'RECOVERY': ['STABLE', 'MODERATE', 'CRITICAL', 'MANUAL'],
            'MANUAL': ['STABLE', 'MODERATE', 'CRITICAL', 'RECOVERY']
        }

        return jsonify({
            'success': True,
            'data': {
                'patient_states': states,
                'supported_scenarios': supported_scenarios,
                'allowed_transitions': transitions,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to query simulator scenarios: {str(e)}'
        }), 500


@developer_bp.route('/telemetry-simulator/patients/<int:patient_id>/scenario', methods=['GET'])
def get_patient_scenario(patient_id):
    """Return authoritative current simulator scenario for a single patient."""
    try:
        row = db.execute_query(
            """SELECT p.patient_id, p.name, p.status,
                      COALESCE(s.current_scenario, 'STABLE') as current_scenario,
                      s.previous_scenario,
                      s.transition_status,
                      s.last_transition_time
               FROM patients p
               LEFT JOIN simulator_patient_states s ON p.patient_id = s.patient_id
               WHERE p.patient_id = %s""",
            (patient_id,),
            fetch='one'
        )
        if not row:
            return jsonify({
                'success': False,
                'error': f'Patient ID {patient_id} not found'
            }), 404

        scen = row['current_scenario']
        if scen in ['GRADUAL_DETERIORATION', 'DETERIORATION']:
            scen = 'MODERATE'
        prev = row['previous_scenario']
        if prev in ['GRADUAL_DETERIORATION', 'DETERIORATION']:
            prev = 'MODERATE'

        return jsonify({
            'success': True,
            'data': {
                'patient_id': row['patient_id'],
                'name': row['name'],
                'current_scenario': scen,
                'previous_scenario': prev,
                'transition_status': row.get('transition_status') or 'ACTIVE',
                'last_transition_time': str(row['last_transition_time']) if row.get('last_transition_time') else None
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to query patient scenario: {str(e)}'
        }), 500


@developer_bp.route('/telemetry-simulator/patients/<int:patient_id>/transition', methods=['POST'])
def transition_patient_scenario(patient_id):
    """
    Transition a patient's telemetry simulation scenario.
    Validates patient, checks source/target scenarios, persists new authoritative state,
    and records an audit trail.
    """
    user = get_current_authenticated_user()
    user_id = user.id if (user and user.is_authenticated) else None
    user_role = user.role if (user and user.is_authenticated) else 'DEVELOPER_TESTER'
    user_name = getattr(user, 'username', 'Developer Tester')

    # Ensure patient exists
    patient = db.execute_query(
        "SELECT patient_id, name, status FROM patients WHERE patient_id = %s",
        (patient_id,),
        fetch='one'
    )
    if not patient:
        return jsonify({
            'success': False,
            'error': f'Patient ID {patient_id} does not exist in the database.'
        }), 404

    payload = request.get_json(silent=True) or {}
    raw_target = payload.get('target_scenario') or payload.get('scenario')
    if not raw_target:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: "target_scenario"'
        }), 400

    target_scenario = str(raw_target).strip().upper()
    if target_scenario in ['GRADUAL_DETERIORATION', 'DETERIORATION']:
        target_scenario = 'MODERATE'

    valid_scenarios = ['STABLE', 'MODERATE', 'CRITICAL', 'RECOVERY', 'MANUAL']
    if target_scenario not in valid_scenarios:
        return jsonify({
            'success': False,
            'error': f'Invalid scenario "{raw_target}". Supported scenarios: {valid_scenarios}'
        }), 400

    # Query existing simulator patient state
    curr_state = db.execute_query(
        "SELECT * FROM simulator_patient_states WHERE patient_id = %s",
        (patient_id,),
        fetch='one'
    )
    source_scenario = curr_state['current_scenario'] if curr_state else 'STABLE'
    if source_scenario in ['GRADUAL_DETERIORATION', 'DETERIORATION']:
        source_scenario = 'MODERATE'

    # Check duplicate transition
    if source_scenario == target_scenario:
        return jsonify({
            'success': True,
            'message': f'Patient {patient_id} is already in scenario "{target_scenario}".',
            'data': {
                'patient_id': patient_id,
                'source_scenario': source_scenario,
                'target_scenario': target_scenario,
                'current_scenario': target_scenario,
                'transition_status': 'ACTIVE',
                'is_noop': True,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200

    now_ts = time.strftime('%Y-%m-%d %H:%M:%S')
    meta = {
        'initiated_by': user_name,
        'role': user_role,
        'reason': payload.get('reason', 'Interactive test scenario transition'),
        'client_ip': request.remote_addr
    }

    try:
        # Upsert simulator_patient_states
        db.execute_query(
            """INSERT INTO simulator_patient_states 
               (patient_id, current_scenario, previous_scenario, transition_status, last_transition_time, updated_by)
               VALUES (%s, %s, %s, 'ACTIVE', %s, %s)
               ON DUPLICATE KEY UPDATE 
               previous_scenario = VALUES(previous_scenario),
               current_scenario = VALUES(current_scenario),
               transition_status = 'ACTIVE',
               last_transition_time = VALUES(last_transition_time),
               updated_by = VALUES(updated_by)""",
            (patient_id, target_scenario, source_scenario, now_ts, user_id)
        )

        # Record in simulator_scenario_transitions
        import json
        trans_res = db.execute_query(
            """INSERT INTO simulator_scenario_transitions 
               (patient_id, source_scenario, target_scenario, status, transition_time, initiated_by, user_id, metadata)
               VALUES (%s, %s, %s, 'SUCCESS', %s, %s, %s, %s)""",
            (patient_id, source_scenario, target_scenario, now_ts, user_role, user_id, json.dumps(meta))
        )
        transition_id = trans_res if isinstance(trans_res, int) else None

        # Record system audit trail
        try:
            from models.audit_log_model import AuditLog
            AuditLog.log(
                action='SIMULATOR_SCENARIO_TRANSITION',
                user_id=user_id,
                entity_type='PATIENT',
                entity_id=patient_id,
                old_value={'scenario': source_scenario},
                new_value={'scenario': target_scenario},
                ip_address=request.remote_addr,
                description=f"Transitioned patient {patient_id} ({patient.get('name', 'Patient')}) scenario from {source_scenario} to {target_scenario}"
            )
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': f'Successfully transitioned patient {patient_id} from {source_scenario} to {target_scenario}.',
            'data': {
                'patient_id': patient_id,
                'source_scenario': source_scenario,
                'target_scenario': target_scenario,
                'current_scenario': target_scenario,
                'transition_id': transition_id,
                'transition_status': 'ACTIVE',
                'timestamp': now_ts
            }
        }), 200

    except Exception as e:
        # Record failed transition attempt if possible
        try:
            db.execute_query(
                """INSERT INTO simulator_scenario_transitions 
                   (patient_id, source_scenario, target_scenario, status, error_message, transition_time, initiated_by, user_id)
                   VALUES (%s, %s, %s, 'FAILED', %s, %s, %s, %s)""",
                (patient_id, source_scenario, target_scenario, str(e), now_ts, user_role, user_id)
            )
        except Exception:
            pass

        return jsonify({
            'success': False,
            'error': f'Failed to persist scenario transition: {str(e)}'
        }), 500


@developer_bp.route('/telemetry-simulator/patients/<int:patient_id>/transitions', methods=['GET'])
def get_patient_transitions(patient_id):
    """Return historical scenario transitions for a patient."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        rows = db.execute_query(
            """SELECT transition_id, patient_id, source_scenario, target_scenario,
                      status, error_message, transition_time, initiated_by, user_id, metadata
               FROM simulator_scenario_transitions
               WHERE patient_id = %s
               ORDER BY transition_time DESC
               LIMIT %s""",
            (patient_id, limit),
            fetch=True
        ) or []

        return jsonify({
            'success': True,
            'data': {
                'patient_id': patient_id,
                'transitions': rows,
                'total_records': len(rows)
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to query transition history: {str(e)}'
        }), 500

