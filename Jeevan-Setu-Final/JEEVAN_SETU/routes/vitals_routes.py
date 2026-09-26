"""
routes/vitals_routes.py — Phase 8 Vital Signs Management REST APIs & EWS Pipeline.
Endpoints:
    POST   /vitals & /api/v1/vitals                 (Submit patient vitals & trigger EWS engine)
    GET    /vitals/{patient_id} & /api/v1/vitals/{patient_id} (Get all vitals for patient)
    GET    /vitals/{patient_id}/latest              (Get most recent vitals + EWS)
    GET    /vitals/{patient_id}/history             (Get vital signs history timeline)
    GET    /vitals/critical                         (Get all critical patients)
"""

import json
import logging
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from models.vitals_model import Vitals
from models.patient_model import Patient
from models.ews_score_model import EWSScore
from modules.scoring_engine import calculate_ews
from modules.alert_engine import check_vitals_and_alert
from models.audit_log_model import AuditLog
from utils.decorators import permission_required, get_current_authenticated_user, _is_api_request
from utils.validators import validate_vitals_data

logger = logging.getLogger(__name__)
vitals_bp = Blueprint('vitals', __name__)


# ─────────────────────────────────────────────────────────────
# 1. POST /vitals & /api/v1/vitals — Record Vitals & Calculate EWS
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/', methods=['POST'])
@vitals_bp.route('', methods=['POST'])
@permission_required('record_vitals')
def create_vitals():
    """
    Submit vital signs for a patient and automatically compute EWS score and trigger alerts.
    Payload:
        {
            "patient_id": 1,
            "heart_rate": 84,
            "blood_pressure_sys": 120,
            "blood_pressure_dia": 80,
            "respiratory_rate": 16,
            "temperature": 37.0,
            "spo2": 98,
            "consciousness": "Alert",
            "urine_output": 200,
            "blood_sugar": 110
        }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    # 1. Check patient existence
    patient_id = data.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'patient_id is required.'}), 422

    try:
        patient_id = int(patient_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'patient_id must be a valid integer.'}), 422

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    # 2. Validate clinical ranges and types
    errors = validate_vitals_data(data)
    if errors:
        return jsonify({'success': False, 'errors': errors, 'error': errors[0]}), 422

    # 3. Parse numeric parameters safely
    def _to_float(k):
        v = data.get(k)
        if v is not None and str(v).strip() != '':
            try:
                return float(v)
            except (ValueError, TypeError):
                return None
        return None

    vitals_data = {
        'heart_rate': _to_float('heart_rate'),
        'blood_pressure_sys': _to_float('blood_pressure_sys') or _to_float('systolic_bp'),
        'respiratory_rate': _to_float('respiratory_rate'),
        'temperature': _to_float('temperature'),
    }

    # 4. Pipeline: Vitals -> EWS Calculation (4 parameters)
    ews_result = calculate_ews(vitals_data)
    total_score = ews_result['total_score']
    risk_level = ews_result['risk_level']
    breakdown = ews_result['breakdown']
    vitals_data['ews_score'] = total_score

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    # 5. Insert vitals record (4 parameters)
    vital_id = Vitals.record(
        patient_id=patient_id,
        recorded_by=user_id,
        **vitals_data
    )

    # 6. Insert EWS score breakdown record (4 parameters)
    EWSScore.record(
        patient_id=patient_id,
        vital_id=vital_id,
        total_score=total_score,
        risk_level=risk_level.upper(),
        hr_score=breakdown.get('heart_rate', {}).get('score', 0),
        bp_score=breakdown.get('blood_pressure_sys', {}).get('score', 0),
        rr_score=breakdown.get('respiratory_rate', {}).get('score', 0),
        temp_score=breakdown.get('temperature', {}).get('score', 0)
    )

    # 7. Check and trigger real-time alerts if abnormal
    alerts = check_vitals_and_alert(patient_id, vitals_data, patient['name'])

    # 8. Audit trail
    AuditLog.log(
        action='record_vitals',
        user_id=user_id,
        entity_type='vitals',
        entity_id=vital_id,
        new_value={'patient_id': patient_id, 'ews_score': total_score, 'risk_level': risk_level},
        ip_address=request.remote_addr,
        description=f"Vitals recorded for {patient['name']} (EWS: {total_score} - {risk_level})"
    )

    latest_record = Vitals.get_by_id(vital_id)

    return jsonify({
        'success': True,
        'message': f"Vitals recorded. EWS score: {total_score} ({risk_level})",
        'data': {
            'vital_id': vital_id,
            'vitals': latest_record,
            'ews': {
                'total_score': total_score,
                'risk_level': risk_level,
                'breakdown': breakdown
            },
            'alerts_triggered': len(alerts) if alerts else 0
        }
    }), 201


# ─────────────────────────────────────────────────────────────
# 2. GET /vitals/{patient_id} & /api/v1/vitals/{patient_id} — All Vitals
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/<int:patient_id>', methods=['GET'])
@permission_required('view_vitals')
def get_patient_vitals(patient_id):
    """
    Get vital sign recordings for a patient.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    limit = request.args.get('limit', 50, type=int)
    history = Vitals.get_history(patient_id, limit=limit)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'count': len(history),
        'data': history
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. GET /vitals/{patient_id}/latest — Most Recent Vitals + EWS
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/<int:patient_id>/latest', methods=['GET'])
@vitals_bp.route('/latest/<int:patient_id>', methods=['GET'])
@permission_required('view_vitals')
def get_latest_vitals(patient_id):
    """
    Get the most recent vital sign entry and current EWS status for a patient.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    vitals = Vitals.get_latest(patient_id)
    if not vitals:
        return jsonify({
            'success': True,
            'message': 'No vitals recorded yet for this patient.',
            'data': None
        }), 200

    ews_info = EWSScore.get_latest(patient_id)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'data': {
            'vitals': vitals,
            'ews': ews_info
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. GET /vitals/{patient_id}/history — Historical Trends
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/<int:patient_id>/history', methods=['GET'])
@vitals_bp.route('/history/<int:patient_id>', methods=['GET'])
@permission_required('view_vitals')
def get_vitals_history(patient_id):
    """
    Get vital signs history with EWS progression.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    limit = request.args.get('limit', 50, type=int)
    history = Vitals.get_history(patient_id, limit=limit)
    ews_history = EWSScore.get_history(patient_id, limit=limit)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'data': {
            'vitals_history': history,
            'ews_history': ews_history
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. GET /vitals/critical — Critical Patients
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/critical', methods=['GET'])
@permission_required('view_vitals')
def critical_patients():
    """Get all patients with critical EWS scores."""
    patients = Vitals.get_critical_patients()
    return jsonify({
        'success': True,
        'count': len(patients),
        'data': patients
    }), 200


# ─────────────────────────────────────────────────────────────
# 6. POST /vitals/patient/{patient_id}/submit — Core Clinical Data Flow
#    4-Parameter Vital Submission with EWS + Decision (Transactional)
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/patient/<int:patient_id>/submit', methods=['POST'])
@permission_required('record_vitals')
def submit_patient_vitals(patient_id):
    """
    Core Clinical Data Flow: Submit 4 vital parameters, calculate EWS,
    determine condition/recommendation, and save everything transactionally.

    Required JSON payload:
        {
            "respiratory_rate": 18,
            "heart_rate": 82,
            "systolic_bp": 120,
            "temperature": 36.8
        }

    Returns complete calculated result including individual scores,
    total EWS, condition, and recommendation.
    """
    from services.ews_service import calculate_ews as ews_calculate
    from services.decision_service import evaluate, get_risk_level_from_condition, get_alert_type_from_condition
    from database.db import db
    from models.recommendation_model import Recommendation

    # 1. Verify patient exists
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    # 2. Parse request data
    data = request.get_json(silent=True) or {}

    # 3. Validate all four parameters are present
    required_fields = ['respiratory_rate', 'heart_rate', 'systolic_bp', 'temperature']
    missing = [f for f in required_fields if f not in data or data[f] is None or str(data[f]).strip() == '']
    if missing:
        return jsonify({
            'success': False,
            'error': f'Missing required parameters: {", ".join(missing)}',
            'missing_fields': missing
        }), 422

    # 4. Validate numeric types and clinical ranges
    ranges = {
        'respiratory_rate': (4, 80, 'Respiratory Rate'),
        'heart_rate': (20, 300, 'Heart Rate'),
        'systolic_bp': (40, 300, 'Systolic BP'),
        'temperature': (25.0, 45.0, 'Temperature'),
    }
    errors = []
    parsed = {}
    for field, (low, high, name) in ranges.items():
        try:
            val = float(data[field])
            if val < low or val > high:
                errors.append(f'{name} must be between {low} and {high}.')
            parsed[field] = val
        except (ValueError, TypeError):
            errors.append(f'{name} must be a valid number.')

    if errors:
        return jsonify({'success': False, 'errors': errors, 'error': errors[0]}), 422

    # 5. Calculate individual parameter scores and total EWS
    ews_result = ews_calculate(
        respiratory_rate=parsed['respiratory_rate'],
        heart_rate=parsed['heart_rate'],
        systolic_bp=parsed['systolic_bp'],
        temperature=parsed['temperature']
    )

    total_score = ews_result['total_score']

    # 6. Determine condition and recommendation
    decision = evaluate(total_score)
    condition = decision['condition']
    recommendation = decision['recommendation']
    risk_level = get_risk_level_from_condition(condition)

    # 7. Get authenticated user
    user = get_current_authenticated_user()
    user_id = user.id if user else None

    # 8. Transactional save: vitals → ews_scores → recommendation → alert
    try:
        with db.transaction() as cursor:
            # 8a. Insert vitals record
            cursor.execute(
                """INSERT INTO vitals (patient_id, heart_rate, blood_pressure_sys,
                   respiratory_rate, temperature, ews_score, recorded_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (patient_id, parsed['heart_rate'], parsed['systolic_bp'],
                 parsed['respiratory_rate'], parsed['temperature'],
                 total_score, user_id)
            )
            vital_id = cursor.lastrowid

            # 8b. Insert EWS score breakdown with patient_name
            patient_name = patient.get('name') if patient else None
            cursor.execute(
                """INSERT INTO ews_scores (patient_id, patient_name, vital_id, total_score, risk_level,
                   hr_score, bp_score, rr_score, temp_score)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (patient_id, patient_name, vital_id, total_score, risk_level,
                 ews_result['heart_rate_score'], ews_result['systolic_bp_score'],
                 ews_result['respiratory_rate_score'], ews_result['temperature_score'])
            )
            ews_id = cursor.lastrowid

            # 8c. Insert recommendation record
            from_ward = patient.get('ward_type', 'ICU')
            to_ward = 'HDU' if condition == 'Stable' else from_ward
            cursor.execute(
                """INSERT INTO recommendations (patient_id, vital_id, ews_id,
                   from_ward, to_ward, score, recommendation_text, reason, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (patient_id, vital_id, ews_id, from_ward, to_ward,
                 total_score, recommendation,
                 f'EWS Total: {total_score} — Condition: {condition}',
                 'auto')
            )

            # 8d. Create emergency alert if condition is Critical (with duplicate suppression)
            from modules.alert_engine import create_emergency_critical_alert, auto_resolve_patient_critical_alerts
            if condition == 'Critical' or total_score >= 5:
                create_emergency_critical_alert(
                    patient_id=patient_id,
                    total_score=total_score,
                    condition=condition,
                    recommendation=recommendation,
                    patient_name=patient['name'],
                    abnormal_parameters=ews_result.get('abnormal_parameters'),
                    cursor=cursor
                )
            else:
                # Patient is Stable or Moderate Risk -> auto-resolve any previous active critical alert
                auto_resolve_patient_critical_alerts(patient_id, cursor=cursor)

                alert_type = get_alert_type_from_condition(condition)
                if alert_type:
                    abnormal_names = ', '.join(
                        p['name'] for p in ews_result['abnormal_parameters']
                    ) or 'Multiple parameters'
                    cursor.execute(
                        """INSERT INTO alerts (patient_id, alert_type, title, message,
                           parameter, value, threshold)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (patient_id, alert_type,
                         f'{alert_type.upper()}: EWS Alert — {patient["name"]}',
                         f'EWS Score: {total_score} ({condition}). '
                         f'Abnormal: {abnormal_names}. '
                         f'Recommendation: {recommendation}.',
                         'ews_total', total_score, 3)
                    )

            # 8e. Audit log (Valid JSON required for MySQL JSON column)
            audit_payload = json.dumps({
                'patient_id': patient_id,
                'ews_score': total_score,
                'condition': condition,
                'recommendation': recommendation
            })
            cursor.execute(
                """INSERT INTO audit_logs (user_id, action, entity_type, entity_id,
                   new_value, ip_address, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, 'submit_vitals', 'vitals', vital_id,
                 audit_payload,
                 request.remote_addr,
                 f'Vitals submitted for {patient["name"]} '
                 f'(EWS: {total_score} — {condition})')
            )

    except Exception as e:
        logger.exception("Error saving vitals transaction for patient %s: %s", patient_id, e)
        # Transaction is automatically rolled back by db.transaction() context manager
        return jsonify({
            'success': False,
            'error': f'Failed to save vital records: {str(e)}',
        }), 500

    # 9. Return complete calculated result
    return jsonify({
        'success': True,
        'message': f'Vitals recorded. EWS: {total_score} ({condition})',
        'data': {
            'patient_id': patient_id,
            'vital_id': vital_id,
            'vitals': {
                'respiratory_rate': parsed['respiratory_rate'],
                'heart_rate': parsed['heart_rate'],
                'systolic_bp': parsed['systolic_bp'],
                'temperature': parsed['temperature']
            },
            'scores': {
                'respiratory_rate': ews_result['respiratory_rate_score'],
                'heart_rate': ews_result['heart_rate_score'],
                'systolic_bp': ews_result['systolic_bp_score'],
                'temperature': ews_result['temperature_score']
            },
            'total_score': total_score,
            'condition': condition,
            'recommendation': recommendation,
            'abnormal_parameters': ews_result['abnormal_parameters'],
            'recorded_at': None  # Will be set by MySQL CURRENT_TIMESTAMP
        }
    }), 201


# ─────────────────────────────────────────────────────────────
# 7. GET /vitals/patient/{patient_id}/latest-status — Latest Patient Status
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/patient/<int:patient_id>/latest-status', methods=['GET'])
@permission_required('view_vitals')
def get_patient_latest_status(patient_id):
    """
    Get the latest vital signs, individual scores, total EWS, condition,
    and recommendation for a patient. Single authoritative endpoint for
    all dashboards (nurse, doctor, attendant).
    """
    from services.decision_service import evaluate
    from database.db import db

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    # Get latest vitals
    vitals = Vitals.get_latest(patient_id)
    if not vitals:
        return jsonify({
            'success': True,
            'message': 'No vitals recorded yet for this patient.',
            'data': None
        }), 200

    # Get latest EWS breakdown
    ews_info = EWSScore.get_latest(patient_id)

    # Determine condition and recommendation from total score
    total_score = ews_info['total_score'] if ews_info else (vitals.get('ews_score', 0) or 0)
    decision = evaluate(total_score)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'data': {
            'patient_id': patient_id,
            'patient_name': patient.get('name'),
            'ward_type': patient.get('ward_type'),
            'bed_number': patient.get('bed_number'),
            'latest_vitals': {
                'respiratory_rate': vitals.get('respiratory_rate'),
                'heart_rate': vitals.get('heart_rate'),
                'systolic_bp': vitals.get('blood_pressure_sys'),
                'temperature': vitals.get('temperature')
            },
            'scores': {
                'respiratory_rate': ews_info.get('rr_score', 0) if ews_info else 0,
                'heart_rate': ews_info.get('hr_score', 0) if ews_info else 0,
                'systolic_bp': ews_info.get('bp_score', 0) if ews_info else 0,
                'temperature': ews_info.get('temp_score', 0) if ews_info else 0
            },
            'total_score': total_score,
            'condition': decision['condition'],
            'recommendation': decision['recommendation'],
            'recorded_at': str(vitals.get('recorded_at', ''))
        }
    }), 200


# ─────────────────────────────────────────────────────────────
# 8. GET /vitals/patient/{patient_id}/history — Historical Records with Scores
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/patient/<int:patient_id>/history', methods=['GET'])
@permission_required('view_vitals')
def get_patient_vitals_history(patient_id):
    """
    Get historical vital sign records with individual scores, total EWS,
    condition, and recommendation. Ordered newest first.
    """
    from services.decision_service import evaluate
    from database.db import db

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found.'}), 404

    limit = request.args.get('limit', 50, type=int)

    # Join vitals with ews_scores for complete records
    records = db.execute_query(
        """SELECT v.vital_id, v.patient_id, v.respiratory_rate, v.heart_rate,
                  v.blood_pressure_sys, v.temperature, v.ews_score, v.recorded_at,
                  e.rr_score, e.hr_score, e.bp_score, e.temp_score,
                  e.total_score, e.risk_level
           FROM vitals v
           LEFT JOIN ews_scores e ON v.vital_id = e.vital_id
           WHERE v.patient_id = %s
           ORDER BY v.recorded_at DESC, v.vital_id DESC
           LIMIT %s""",
        (patient_id, limit), fetch=True
    ) or []

    # Enrich each record with condition and recommendation
    history = []
    for rec in records:
        total = rec.get('total_score') or rec.get('ews_score', 0) or 0
        decision = evaluate(total)
        history.append({
            'vital_id': rec.get('vital_id'),
            'respiratory_rate': rec.get('respiratory_rate'),
            'heart_rate': rec.get('heart_rate'),
            'systolic_bp': rec.get('blood_pressure_sys'),
            'temperature': rec.get('temperature'),
            'scores': {
                'respiratory_rate': rec.get('rr_score', 0) or 0,
                'heart_rate': rec.get('hr_score', 0) or 0,
                'systolic_bp': rec.get('bp_score', 0) or 0,
                'temperature': rec.get('temp_score', 0) or 0
            },
            'total_score': total,
            'condition': decision['condition'],
            'recommendation': decision['recommendation'],
            'recorded_at': str(rec.get('recorded_at', ''))
        })

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'count': len(history),
        'data': history
    }), 200


# ─────────────────────────────────────────────────────────────
# Web UI View for Vitals Entry
# ─────────────────────────────────────────────────────────────
@vitals_bp.route('/enter/<int:patient_id>', methods=['GET', 'POST'])
@permission_required('record_vitals')
def enter_vitals(patient_id):
    """Web UI form to enter vitals."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        flash('Patient not found.', 'error')
        return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')

    if request.method == 'POST':
        res = create_vitals()
        if isinstance(res, tuple) and res[1] in (400, 422, 500):
            flash(res[0].get_json().get('error', 'Error recording vitals'), 'error')
            return render_template('Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html', patient=patient)
        flash('Vitals recorded successfully.', 'success')
        return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')

    return render_template('Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html', patient=patient)
