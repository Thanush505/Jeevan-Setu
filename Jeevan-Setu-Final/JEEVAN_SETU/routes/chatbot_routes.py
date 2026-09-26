"""
routes/chatbot_routes.py — Phase 17 Medical Patient Assistant Chatbot REST APIs.

Endpoints:
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
    format_documented_diagnosis
)
from models.chatbot_model import ChatbotConversation
from models.audit_log_model import AuditLog
from utils.decorators import permission_required, get_current_authenticated_user

chatbot_bp = Blueprint('chatbot', __name__)


# ─────────────────────────────────────────────────────────────
# 1. POST /chatbot/message & /api/v1/chatbot/message
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/message', methods=['POST'])
@chatbot_bp.route('/api/v1/chatbot/message', methods=['POST'])
@permission_required('use_chatbot')
def conversational_message():
    """
    Unified conversational message handler supporting:
    - Initial greeting / patient search by name or ID
    - Patient disambiguation selection
    - Clinical follow-up questions on the selected patient
    - Quick actions execution
    """
    user = get_current_authenticated_user()
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or data.get('query') or '').strip()
    active_patient_id = data.get('patient_id') or data.get('active_patient_id')

    if active_patient_id:
        try:
            active_patient_id = int(active_patient_id)
        except (ValueError, TypeError):
            active_patient_id = None

    response = process_conversational_message(
        user_id=user.id if user else 1,
        message=message,
        active_patient_id=active_patient_id
    )

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
    Execute a clinical query with mandatory patient-specific context.
    Payload:
        {
            "patient_id": 101,
            "message": "What are the latest vitals?"
        }
    """
    user = get_current_authenticated_user()
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or data.get('query') or '').strip()
    patient_id = data.get('patient_id')

    if not patient_id:
        return jsonify({
            'success': False,
            'error': 'Patient ID is required. Chatbot operates strictly on patient-specific context.'
        }), 400

    if not message:
        return jsonify({
            'success': False,
            'error': 'Message text cannot be empty.'
        }), 400

    response = process_message(
        user_id=user.id if user else 1,
        message=message,
        patient_id=int(patient_id)
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
    query = request.args.get('query') or request.args.get('q') or ''
    match_type, patients = search_patients_for_chat(query)

    return jsonify({
        'success': True,
        'query': query,
        'match_type': match_type,
        'count': len(patients),
        'patients': patients
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. Structured Clinical Endpoints
# ─────────────────────────────────────────────────────────────
@chatbot_bp.route('/patient/<int:patient_id>/summary', methods=['GET'])
@permission_required('use_chatbot')
def get_patient_summary_endpoint(patient_id):
    """Retrieve 6-section structured clinical summary."""
    user = get_current_authenticated_user()
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
    history = ChatbotConversation.get_history(user.id if user else 1, limit=20) if ChatbotConversation else []
    try:
        return render_template('Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html', history=history)
    except Exception:
        return render_template('Doctor_patient_summary_ai.html', history=history)
