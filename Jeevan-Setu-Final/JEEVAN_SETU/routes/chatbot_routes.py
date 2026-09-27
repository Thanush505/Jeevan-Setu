"""
routes/chatbot_routes.py — Phase 17 Medical Patient Assistant Chatbot REST APIs.

Endpoints:
    GET  /chatbot/patients & /api/v1/chatbot/patients   (RBAC Authorized Patient List for Dropdown)
    POST /chatbot/message & /api/v1/chatbot/message   (High-level conversational chat & patient search)
    POST /chatbot/query & /api/v1/chatbot/query       (Submit patient-specific clinical query)
    POST /chatbot/api/send                            (Legacy send alias)
    GET  /chatbot/patients/search                     (Search and disambiguate patients)
    GET  /chatbot/patient/<id>/summary                (Structured patient summary)
    GET  /chatbot/patient/<id>/vitals                 (Current & historical vitals telemetry)
    GET  /chatbot/patient/<id>/trends                 (Longitudinal trend analysis)
    GET  /chatbot/patient/<id>/decisions              (Transfer recommendation & clinician override history)
    GET  /chatbot/context/{patient_id}                (Retrieve verified clinical context)
    GET  /chatbot/history/{patient_id}                (Patient-specific conversation log)
    GET  /chatbot/history                             (User conversation history)
    GET  /chatbot/                                    (Chatbot Web UI)
"""

from flask import Blueprint, request, render_template, jsonify, redirect, url_for
from modules.chatbot_engine import (
    process_message,
    process_conversational_message,
    get_patient_clinical_context,
    search_patients_for_chat,
    format_structured_patient_summary,
    format_vital_parameters_analysis,
    format_transfer_decision_explanation,
    format_decision_history_and_overrides,
    format_documented_diagnosis,
    verify_user_patient_access,
    get_authorized_patients_for_user
)
from models.chatbot_model import ChatbotConversation

try:
    from models.audit_log_model import AuditLog
except ImportError:
    class AuditLog:
        @staticmethod
        def log(*args, **kwargs):
            return None

try:
    from utils.decorators import permission_required, get_current_authenticated_user
except ImportError:
    def permission_required(perm):
        def decorator(f):
            def wrapped(*args, **kwargs):
                return f(*args, **kwargs)
            wrapped.__name__ = f.__name__
            return wrapped
        return decorator

    def get_current_authenticated_user():
        class MockUser:
            id = 1
            user_id = 1
            role = 'doctor'
            username = 'dr_default'
        return MockUser()

chatbot_bp = Blueprint('chatbot', __name__)


# ─────────────────────────────────────────────────────────────
# 0. GET /chatbot/patients & /api/v1/chatbot/patients (RBAC Authorized Dropdown List)
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/patients', methods=['GET'])
@chatbot_bp.route('/api/v1/chatbot/patients', methods=['GET'])
@permission_required('use_chatbot')
def get_authorized_patients_endpoint():
    """
    Retrieve list of patients the authenticated user is authorized to access based on RBAC:
    - Admin: all admitted patients
    - Doctor: assigned patients (or all if general ward/physician)
    - Nurse: assigned patients (or all in assigned ward)
    - Attendant: strictly the patient associated with the attendant
    """
    user = get_current_authenticated_user()
    patients = get_authorized_patients_for_user(user)
    return jsonify({
        'success': True,
        'count': len(patients),
        'patients': patients
    }), 200


# ─────────────────────────────────────────────────────────────
# 1. POST /chatbot/message & /api/v1/chatbot/message
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/message', methods=['POST'])
@chatbot_bp.route('/api/v1/chatbot/message', methods=['POST'])
@permission_required('use_chatbot')
def conversational_message():
    """
    Unified conversational message handler supporting:
    - Custom telemetry and 'what-if' vital simulations from client input
    - Initial greeting / patient search by name or ID
    - Patient disambiguation selection
    - Clinical follow-up questions on the selected patient
    - Quick actions execution
    """
    user = get_current_authenticated_user()
    user_role = getattr(user, 'role', 'doctor') if user else 'doctor'
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or data.get('query') or '').strip()
    active_patient_id = data.get('patient_id') or data.get('active_patient_id')
    custom_vitals = data.get('custom_vitals') or data.get('vitals')
    custom_patient = data.get('custom_patient') or data.get('patient_data')
    custom_notes = data.get('custom_notes') or data.get('notes')

    if active_patient_id:
        try:
            active_patient_id = int(active_patient_id)
            is_auth, err_msg = verify_user_patient_access(user, active_patient_id)
            if not is_auth:
                return jsonify({
                    'success': False,
                    'error': err_msg or 'Access forbidden: Unauthorized patient access.'
                }), 403
        except (ValueError, TypeError):
            active_patient_id = None

    response = process_conversational_message(
        user_id=user.id if user else 1,
        message=message,
        active_patient_id=active_patient_id,
        custom_vitals=custom_vitals,
        custom_patient=custom_patient,
        custom_notes=custom_notes,
        user_role=user_role
    )

    if 'response' not in response and 'text' in response:
        response['response'] = response['text']
    status_code = 200 if response.get('success', True) else 400
    return jsonify(response), status_code


# ─────────────────────────────────────────────────────────────
# 2. POST /chatbot/query & /api/v1/chatbot/query (Strict Context)
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/query', methods=['POST'])
@chatbot_bp.route('/api/send', methods=['POST'])
@permission_required('use_chatbot')
def chatbot_query():
    """
    Execute a clinical query with mandatory patient-specific context or custom client telemetry.
    Payload:
        {
            "patient_id": 101,
            "message": "What are the latest vitals?",
            "custom_vitals": {"spo2": 88, "heart_rate": 120}
        }
    """
    user = get_current_authenticated_user()
    user_role = getattr(user, 'role', 'doctor') if user else 'doctor'
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or data.get('query') or '').strip()
    patient_id = data.get('patient_id')
    custom_vitals = data.get('custom_vitals') or data.get('vitals')
    custom_patient = data.get('custom_patient') or data.get('patient_data')
    custom_notes = data.get('custom_notes') or data.get('notes')

    if not patient_id and not custom_vitals:
        return jsonify({
            'success': False,
            'error': 'Patient ID or custom vitals are required.'
        }), 400

    if not message and not custom_vitals:
        return jsonify({
            'success': False,
            'error': 'Message text cannot be empty.'
        }), 400

    if patient_id:
        try:
            pid = int(patient_id)
            is_auth, err_msg = verify_user_patient_access(user, pid)
            if not is_auth:
                return jsonify({
                    'success': False,
                    'error': err_msg or 'Access forbidden: Unauthorized patient access.'
                }), 403
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid patient ID.'}), 400

    response = process_message(
        user_id=user.id if user else 1,
        message=message,
        patient_id=int(patient_id) if patient_id else None,
        custom_vitals=custom_vitals,
        custom_patient=custom_patient,
        custom_notes=custom_notes,
        user_role=user_role
    )

    if not response.get('success'):
        status_code = 404 if response.get('intent') == 'patient_not_found' else 400
        return jsonify(response), status_code

    return jsonify(response), 200


# ─────────────────────────────────────────────────────────────
# 3. GET /chatbot/patients/search (Patient Search & Disambiguation)
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/patients/search', methods=['GET'])
@chatbot_bp.route('/api/v1/chatbot/patients/search', methods=['GET'])
@permission_required('use_chatbot')
def search_patients_endpoint():
    """Search patients by name or ID for chatbot selection without data leakage."""
    user = get_current_authenticated_user()
    query = request.args.get('query') or request.args.get('q') or ''
    match_type, patients = search_patients_for_chat(query)

    # Scoping for non-admins
    if getattr(user, 'role', '') not in ('admin', 'superadmin'):
        auth_pats = get_authorized_patients_for_user(user)
        auth_ids = {p['patient_id'] for p in auth_pats}
        patients = [p for p in patients if p.get('patient_id') in auth_ids or p.get('id') in auth_ids]
        match_type = 'single' if len(patients) == 1 else ('multiple' if len(patients) > 1 else 'none')

    return jsonify({
        'success': True,
        'query': query,
        'match_type': match_type,
        'count': len(patients),
        'patients': patients
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. Structured Clinical Endpoints (RBAC Enforced)
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/patient/<int:patient_id>/summary', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_summary_endpoint(patient_id):
    """Retrieve 6-section structured clinical summary."""
    user = get_current_authenticated_user()
    is_auth, err_msg = verify_user_patient_access(user, patient_id)
    if not is_auth:
        return jsonify({'success': False, 'error': err_msg or 'Access forbidden: Unauthorized patient.'}), 403

    context = get_patient_clinical_context(patient_id)
    if not context:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    # Audit Log
    try:
        AuditLog.log(
            user_id=user.id if user else 1,
            action="CHATBOT_VIEW_PATIENT_SUMMARY",
            entity_type="patient",
            entity_id=patient_id,
            description=f"Viewed structured patient summary via clinical assistant"
        )
    except Exception:
        pass

    summary_text = format_structured_patient_summary(context)
    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'text': summary_text,
        'context': context
    }), 200


@chatbot_bp.route('/patient/<int:patient_id>/vitals', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_vitals_endpoint(patient_id):
    """Retrieve current and historical vitals telemetry."""
    user = get_current_authenticated_user()
    is_auth, err_msg = verify_user_patient_access(user, patient_id)
    if not is_auth:
        return jsonify({'success': False, 'error': err_msg or 'Access forbidden: Unauthorized patient.'}), 403

    context = get_patient_clinical_context(patient_id)
    if not context:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    vitals_text = format_vital_parameters_analysis(context)
    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'text': vitals_text,
        'latest_vitals': context.get('latest_vitals'),
        'vitals_history': context.get('vitals_history'),
        'trends': context.get('trends')
    }), 200


@chatbot_bp.route('/patient/<int:patient_id>/trends', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_trends_endpoint(patient_id):
    """Retrieve vital parameters trend analysis."""
    user = get_current_authenticated_user()
    is_auth, err_msg = verify_user_patient_access(user, patient_id)
    if not is_auth:
        return jsonify({'success': False, 'error': err_msg or 'Access forbidden: Unauthorized patient.'}), 403

    context = get_patient_clinical_context(patient_id)
    if not context:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    trends = context.get('trends', {})
    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'trends': trends
    }), 200


@chatbot_bp.route('/patient/<int:patient_id>/decisions', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_decisions_endpoint(patient_id):
    """Retrieve transfer recommendation, explainability, and clinician override history."""
    user = get_current_authenticated_user()
    is_auth, err_msg = verify_user_patient_access(user, patient_id)
    if not is_auth:
        return jsonify({'success': False, 'error': err_msg or 'Access forbidden: Unauthorized patient.'}), 403

    context = get_patient_clinical_context(patient_id)
    if not context:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found.'}), 404

    explanation_text = format_transfer_decision_explanation(context)
    history_text = format_decision_history_and_overrides(context)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'recommendation': context.get('recommendation'),
        'explanation_text': explanation_text,
        'history_text': history_text,
        'recommendations_history': context.get('recommendations_history'),
        'decisions_history': context.get('decisions_history')
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. GET /chatbot/context/{patient_id}
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/context/<int:patient_id>', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_context(patient_id):
    """Retrieve verified factual clinical context for a specific patient."""
    user = get_current_authenticated_user()
    is_auth, err_msg = verify_user_patient_access(user, patient_id)
    if not is_auth:
        return jsonify({'success': False, 'error': err_msg or 'Access forbidden: Unauthorized patient.'}), 403

    context = get_patient_clinical_context(patient_id)
    if not context:
        return jsonify({
            'success': False,
            'error': f'Patient #{patient_id} not found.'
        }), 404

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'data': context
    }), 200


# ─────────────────────────────────────────────────────────────
# 6. GET /chatbot/history/<int:patient_id> & GET /chatbot/history
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/history/<int:patient_id>', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_chat_history(patient_id):
    """Get conversation history for a specific patient."""
    user = get_current_authenticated_user()
    is_auth, err_msg = verify_user_patient_access(user, patient_id)
    if not is_auth:
        return jsonify({'success': False, 'error': err_msg or 'Access forbidden.'}), 403

    limit = request.args.get('limit', 20, type=int)
    history = ChatbotConversation.get_by_patient(patient_id, limit=limit)
    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'count': len(history),
        'data': history
    }), 200


@chatbot_bp.route('/history', methods=['GET'])
@permission_required('use_chatbot')
def get_user_chat_history():
    """Get conversation history for the current authenticated user."""
    user = get_current_authenticated_user()
    limit = request.args.get('limit', 20, type=int)
    history = ChatbotConversation.get_history(user.id if user else 1, limit=limit)
    return jsonify({
        'success': True,
        'count': len(history),
        'data': history
    }), 200


# ─────────────────────────────────────────────────────────────
# 7. Web Interface Route (Browser UI)
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/', methods=['GET'])
@permission_required('use_chatbot')
def chatbot_page():
    """Render the clinical assistant chatbot UI interface."""
    user = get_current_authenticated_user()
    history = ChatbotConversation.get_history(user.id if user else 1, limit=20)
    return render_template('Doctor_patient_summary_ai.html', history=history)
