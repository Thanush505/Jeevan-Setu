"""
routes/explanation_routes.py — Phase 11 Explainable Decision Module REST APIs & Views.
Endpoints:
    GET  /explanation/panel/<patient_id>
    GET  /explanation/decision/<decision_id>        & /api/v1/explanation/decision/<decision_id>
    GET  /explanation/patient/<patient_id>          & /api/v1/explanation/patient/<patient_id>
    GET  /explanation/recommendation/<rec_id>       & /api/v1/explanation/recommendation/<rec_id>
    POST /explanation/generate                     & /api/v1/explanation/generate
"""

from flask import Blueprint, request, jsonify, render_template
from models.explanation_model import Explanation
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.decision_model import Decision
from models.recommendation_model import Recommendation
from modules.explanation_engine import generate_explanation, format_text_explanation
from modules.decision_engine import evaluate_decision
from utils.decorators import permission_required, role_required

explanation_bp = Blueprint('explanation', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /explanation/panel/<patient_id>
# ─────────────────────────────────────────────────────────────
@explanation_bp.route('/panel/<int:patient_id>', methods=['GET'])
@permission_required('view_decisions')
def explanation_panel(patient_id):
    """View explanation panel for a patient's latest clinical decisions."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        if request.accept_mimetypes.best == 'application/json' or request.is_json:
            return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404
        return render_template('Doctor/Doctor_ews_trends/Doctor_ews_trends.html', patient_id=patient_id, explanations=[])

    explanations = Explanation.get_by_patient(patient_id)

    # Check if client expects JSON
    if (request.accept_mimetypes.best == 'application/json' or
            request.path.startswith('/api/') or request.is_json):
        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'patient_name': patient.get('name'),
            'count': len(explanations),
            'data': explanations
        }), 200

    return render_template(
        'Doctor/Doctor_ews_trends/Doctor_ews_trends.html',
        patient_id=patient_id,
        patient=patient,
        explanations=explanations
    )


# ─────────────────────────────────────────────────────────────
# 2. GET /explanation/decision/<decision_id>
# ─────────────────────────────────────────────────────────────
@explanation_bp.route('/decision/<int:decision_id>', methods=['GET'])
@explanation_bp.route('/api/decision/<int:decision_id>', methods=['GET'])
@permission_required('view_decisions')
def get_decision_explanation(decision_id):
    """API: Get transparent explanations for a specific decision record."""
    decision = Decision.get_by_id(decision_id)
    if not decision:
        return jsonify({'success': False, 'error': f'Decision #{decision_id} not found'}), 404

    explanations = Explanation.get_by_decision(decision_id)
    
    # Format structured response
    rec_title = decision.get('recommendation', 'RE_EVALUATE')
    contributing_names = [e['feature_name'].replace('_', ' ').title() for e in explanations]

    text_block = (
        f"Recommendation:\n{rec_title}\n\n"
        f"Reason:\n{decision.get('recommendation', '')}\n\n"
        f"Contributing Parameters:\n" + "\n".join(contributing_names)
    )

    return jsonify({
        'success': True,
        'decision_id': decision_id,
        'patient_id': decision.get('patient_id'),
        'recommendation': rec_title,
        'ews_score': decision.get('ews_score'),
        'confidence': decision.get('confidence'),
        'status': decision.get('status'),
        'contributing_parameters': explanations,
        'contributing_parameter_names': contributing_names,
        'text_block': text_block,
        'count': len(explanations)
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. GET /explanation/patient/<patient_id>
# ─────────────────────────────────────────────────────────────
@explanation_bp.route('/patient/<int:patient_id>', methods=['GET'])
@explanation_bp.route('/api/patient/<int:patient_id>', methods=['GET'])
@permission_required('view_decisions')
def get_patient_explanations(patient_id):
    """API: Get recent decision explanations for a patient."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    limit = request.args.get('limit', 50, type=int)
    explanations = Explanation.get_by_patient(patient_id, limit=limit)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'patient_name': patient.get('name'),
        'count': len(explanations),
        'data': explanations
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. GET /explanation/recommendation/<recommendation_id>
# ─────────────────────────────────────────────────────────────
@explanation_bp.route('/recommendation/<int:recommendation_id>', methods=['GET'])
@permission_required('view_decisions')
def get_recommendation_explanation(recommendation_id):
    """API: Get explanation corresponding to a recommendation record."""
    rec = Recommendation.get_by_id(recommendation_id)
    if not rec:
        return jsonify({'success': False, 'error': f'Recommendation #{recommendation_id} not found'}), 404

    patient_id = rec.get('patient_id')
    vitals = Vitals.get_by_id(rec.get('vital_id')) if rec.get('vital_id') else Vitals.get_latest(patient_id)

    exp_info = generate_explanation(
        patient_id=patient_id,
        vitals_data=vitals,
        recommendation=rec.get('recommendation_text'),
        reason=rec.get('reason'),
        save_to_db=False
    )

    return jsonify({
        'success': True,
        'recommendation_id': recommendation_id,
        'patient_id': patient_id,
        'data': exp_info
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. POST /explanation/generate — On-demand Explanation Generation
# ─────────────────────────────────────────────────────────────
@explanation_bp.route('/generate', methods=['POST'])
@permission_required('view_decisions')
def generate_custom_explanation():
    """
    Generate an explainable decision breakdown without inventing patient information.
    Payload:
        {
            "patient_id": 12, (optional)
            "recommendation": "TRANSFER_TO_HDU", (optional, will evaluate if omitted)
            "vitals": {
                "heart_rate": 78,
                "respiratory_rate": 16,
                "blood_pressure_sys": 120,
                "temperature": 36.8
            }
        }
    """
    data = request.get_json(silent=True) or {}
    vitals_data = data.get('vitals')
    patient_id = data.get('patient_id')
    recommendation = data.get('recommendation')
    reason = data.get('reason')

    if patient_id and not vitals_data:
        patient = Patient.get_by_id(patient_id)
        if not patient:
            return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404
        vitals_data = Vitals.get_latest(patient_id)
        if not vitals_data:
            return jsonify({'success': False, 'error': f'No vitals recorded for patient #{patient_id}'}), 404

    if not recommendation and vitals_data:
        # Evaluate decision rules
        current_unit = data.get('current_unit', 'ICU')
        decision = evaluate_decision(current_unit=current_unit, vitals_data=vitals_data)
        recommendation = decision['recommendation']
        reason = decision['reason']

    explanation = generate_explanation(
        patient_id=patient_id,
        vitals_data=vitals_data,
        recommendation=recommendation,
        reason=reason,
        save_to_db=False
    )

    return jsonify({
        'success': True,
        'data': explanation
    }), 200
