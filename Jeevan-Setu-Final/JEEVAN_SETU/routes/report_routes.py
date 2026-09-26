"""
routes/report_routes.py — Phase 15 Reports REST APIs & PDF Generation.

Endpoints:
    POST /reports/patients/pdf           (Multi/Single-Patient Professional PDF Report)
    GET  /reports/patients/pdf           (Query parameter download for patient PDFs)
    POST /reports/generate/patient-report(Generate patient report data)
    GET  /reports/patient/{id}           (Patient Clinical Report)
    GET  /reports/transfers              (Patient Transfers Report)
    GET  /reports/resource-utilization   (Hospital & Ward Utilization Report)
    GET  /reports/ews/{patient_id}       (Serial EWS History Report)
    GET  /reports/history                (List all stored report metadata)
    GET  /reports/view/{id}              (View single stored report metadata)

Supported Output Formats:
    - JSON (default API response)
    - CSV  (?format=csv)
    - PDF  (?format=pdf or direct PDF endpoint)
"""

from datetime import datetime
from flask import Blueprint, request, jsonify, Response, render_template
from models.report_model import Report
from models.patient_model import Patient
from models.audit_log_model import AuditLog
from modules.report_engine import (
    generate_patient_report_data,
    generate_multi_patient_report_data,
    generate_transfer_report_data,
    generate_ews_history_data,
    generate_resource_utilization_data,
    render_report_csv,
    render_report_pdf,
    render_multi_patient_pdf
)
from utils.decorators import permission_required, get_current_authenticated_user

report_bp = Blueprint('report', __name__)


def _render_formatted_response(report_type, report_result, default_filename):
    """Render report in requested format: json, csv, or pdf."""
    export_format = request.args.get('format', 'json').lower()

    if export_format == 'csv':
        csv_data = render_report_csv(report_type, report_result)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{default_filename}.csv"',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )

    elif export_format == 'pdf':
        pdf_bytes = render_report_pdf(report_type, report_result)
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{default_filename}.pdf"',
                'Content-Type': 'application/pdf'
            }
        )

    # Default: JSON response
    return jsonify({
        'success': True,
        'report_id': report_result.get('report_id'),
        'report_type': report_result.get('report_type'),
        'title': report_result.get('title'),
        'generated_at': report_result.get('generated_at'),
        'data': report_result.get('data') or report_result
    }), 200


import re

def sanitize_filename_part(name):
    """Sanitize patient name for use in filenames (e.g. 'Ravi Kumar' -> 'Ravi_Kumar')."""
    if not name:
        return 'Patient'
    cleaned = re.sub(r'[\s/\\:\*\?"<>\|\.,]+', '_', str(name).strip())
    cleaned = re.sub(r'[^a-zA-Z0-9_-]', '', cleaned)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or 'Patient'


# ─────────────────────────────────────────────────────────────
# 1. Multi-Patient & Single-Patient PDF Generation Endpoint
# ─────────────────────────────────────────────────────────────
@report_bp.route('/patients/pdf', methods=['GET', 'POST'])
@report_bp.route('/generate/patients-pdf', methods=['GET', 'POST'])
@report_bp.route('/patient-report/pdf', methods=['GET', 'POST'])
@permission_required('view_reports')
def generate_patients_pdf_endpoint():
    """
    Generate and download professional hospital PDF report for one or multiple patients.
    Accepts:
      - POST body JSON: { "patient_ids": [1, 2, 3], "sections": ["vitals", "ews", "cds"] }
      - GET query: ?patient_ids=1,2,3&sections=vitals,ews or ?patient_id=1
    """
    user = get_current_authenticated_user()
    patient_ids = []
    sections = None

    if request.method == 'POST':
        body = request.get_json(silent=True) or {}
        patient_ids = body.get('patient_ids') or []
        if not patient_ids and body.get('patient_id'):
            patient_ids = [body.get('patient_id')]
        if 'sections' in body:
            sections = body.get('sections')
    else:
        # GET request
        p_ids_param = request.args.get('patient_ids') or request.args.get('patient_id') or ''
        if p_ids_param:
            patient_ids = [p.strip() for p in str(p_ids_param).split(',') if p.strip()]
        if 'sections' in request.args:
            sections = request.args.get('sections')

    if not patient_ids:
        return jsonify({
            'success': False,
            'error': 'Please select at least one patient to generate the report.'
        }), 400

    if sections is not None:
        if isinstance(sections, (list, tuple, set)) and len(sections) == 0:
            return jsonify({
                'success': False,
                'error': 'Please select at least one report section.'
            }), 400
        elif isinstance(sections, str) and not sections.strip():
            return jsonify({
                'success': False,
                'error': 'Please select at least one report section.'
            }), 400

    # RBAC: If doctor, enforce that all requested patient IDs belong to this doctor
    if user and getattr(user, 'role', '') == 'doctor':
        for pid in patient_ids:
            try:
                pid_int = int(pid)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': f'Invalid patient ID: {pid}'}), 400
            pt = Patient.get_by_id(pid_int)
            if not pt or pt.get('assigned_doctor') != user.id:
                return jsonify({
                    'success': False,
                    'error': f'Access denied: You are not authorized to generate reports for patient #{pid}.'
                }), 403

    user_id = getattr(user, 'id', None)
    user_name = getattr(user, 'full_name', None) or getattr(user, 'username', 'Administrator')

    try:
        report_data = generate_multi_patient_report_data(
            patient_ids=patient_ids,
            sections=sections,
            generated_by=user_id,
            generated_by_name=user_name
        )
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Unable to generate the report at this time. Please try again.'
        }), 500

    if 'error' in report_data:
        return jsonify({'success': False, 'error': report_data['error']}), 404

    # Build PDF binary
    try:
        pdf_bytes = render_multi_patient_pdf(report_data, sections=sections)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        print(f"[REPORT PDF ERROR] {e}")
        return jsonify({
            'success': False,
            'error': 'Error compiling report PDF document. Please try again.'
        }), 500

    # Audit log entry
    try:
        patients_list = report_data.get('patients', [])
        p_codes = [p.get('patient_code', f"ID-{p.get('patient_id')}") for p in patients_list]
        AuditLog.log(
            action='PATIENT_REPORT_GENERATED',
            user_id=user_id,
            entity_type='patient_report',
            entity_id=report_data.get('report_id'),
            new_value={'patient_ids': report_data.get('patient_ids'), 'patient_codes': p_codes, 'sections': report_data.get('sections')},
            description=f"Generated clinical PDF report for {len(patients_list)} patient(s): {', '.join(p_codes[:5])}"
        )
    except Exception as log_err:
        print(f"[REPORT AUDIT WARNING] {log_err}")

    # Patient-based automatic filename
    pts = report_data.get('patients', [])
    num_pts = len(pts)
    if num_pts == 1:
        p0_name = pts[0].get('name', 'Patient')
        clean_name = sanitize_filename_part(p0_name)
        filename = f"JeevanSetu_{clean_name}.pdf"
    else:
        filename = "JeevanSetu_Patient_Reports.pdf"

    # Check if download or inline preview requested
    disposition = 'inline' if request.args.get('preview') == 'true' else 'attachment'

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'{disposition}; filename="{filename}"',
            'Content-Type': 'application/pdf',
            'Access-Control-Expose-Headers': 'Content-Disposition',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )


# ─────────────────────────────────────────────────────────────
# 2. GET /reports/patient/<int:patient_id>
# ─────────────────────────────────────────────────────────────
@report_bp.route('/patient/<int:patient_id>', methods=['GET'])
@permission_required('view_reports')
def patient_report(patient_id):
    """
    Generate and retrieve patient clinical summary report.
    Supports formats: ?format=json | csv | pdf.
    """
    user = get_current_authenticated_user()
    if user and getattr(user, 'role', '') == 'doctor':
        pt = Patient.get_by_id(patient_id)
        if not pt or pt.get('assigned_doctor') != user.id:
            return jsonify({
                'success': False,
                'error': f'Access denied: You are not authorized to access reports for patient #{patient_id}.'
            }), 403

    result = generate_patient_report_data(patient_id, generated_by=user.id if user else None)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 404

    return _render_formatted_response('patient', result, f"patient_{patient_id}_report")


# ─────────────────────────────────────────────────────────────
# 3. GET /reports/transfers
# ─────────────────────────────────────────────────────────────
@report_bp.route('/transfers', methods=['GET'])
@permission_required('view_reports')
def transfer_report():
    """
    Generate and retrieve hospital transfer report.
    Optional query params:
        - patient_id (int): Filter transfers for a specific patient.
        - format: json | csv | pdf
    """
    user = get_current_authenticated_user()
    patient_id = request.args.get('patient_id', type=int)
    if patient_id and user and getattr(user, 'role', '') == 'doctor':
        pt = Patient.get_by_id(patient_id)
        if not pt or pt.get('assigned_doctor') != user.id:
            return jsonify({
                'success': False,
                'error': f'Access denied: You are not authorized to access transfer reports for patient #{patient_id}.'
            }), 403

    result = generate_transfer_report_data(patient_id=patient_id, generated_by=user.id if user else None)

    return _render_formatted_response('transfers', result, "hospital_transfer_report")


# ─────────────────────────────────────────────────────────────
# 4. GET /reports/resource-utilization
# ─────────────────────────────────────────────────────────────
@report_bp.route('/resource-utilization', methods=['GET'])
@permission_required('view_reports')
def resource_utilization_report():
    """
    Generate and retrieve hospital resource utilization report (wards, beds, occupancy %).
    Supports formats: ?format=json | csv | pdf.
    """
    user = get_current_authenticated_user()
    result = generate_resource_utilization_data(generated_by=user.id if user else None)

    return _render_formatted_response('resource_utilization', result, "resource_utilization_report")


# ─────────────────────────────────────────────────────────────
# 5. GET /reports/ews/<int:patient_id>
# ─────────────────────────────────────────────────────────────
@report_bp.route('/ews/<int:patient_id>', methods=['GET'])
@permission_required('view_reports')
def ews_history_report(patient_id):
    """
    Generate and retrieve serial EWS history & risk trend report for a patient.
    Supports formats: ?format=json | csv | pdf.
    """
    user = get_current_authenticated_user()
    if user and getattr(user, 'role', '') == 'doctor':
        pt = Patient.get_by_id(patient_id)
        if not pt or pt.get('assigned_doctor') != user.id:
            return jsonify({
                'success': False,
                'error': f'Access denied: You are not authorized to access EWS reports for patient #{patient_id}.'
            }), 403

    result = generate_ews_history_data(patient_id, generated_by=user.id if user else None)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 404

    return _render_formatted_response('ews', result, f"patient_{patient_id}_ews_report")


# ─────────────────────────────────────────────────────────────
# 6. Metadata & Historical Reports Listing
# ─────────────────────────────────────────────────────────────
@report_bp.route('/history', methods=['GET'])
@report_bp.route('/', methods=['GET'])
@report_bp.route('/list', methods=['GET'], endpoint='report_list')
@permission_required('view_reports')
def list_reports():
    """List stored report metadata and history."""
    user = get_current_authenticated_user()
    report_type = request.args.get('type')
    limit = request.args.get('limit', 50, type=int)
    doctor_id = user.id if (user and getattr(user, 'role', '') == 'doctor') else None
    reports = Report.get_all(report_type=report_type, limit=limit, doctor_id=doctor_id)

    return jsonify({
        'success': True,
        'count': len(reports),
        'data': reports
    }), 200


@report_bp.route('/view/<int:report_id>', methods=['GET'], endpoint='view_report')
@report_bp.route('/detail/<int:report_id>', methods=['GET'])
@permission_required('view_reports')
def view_stored_report(report_id):
    """View metadata and stored payload of a single report."""
    user = get_current_authenticated_user()
    report = Report.get_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'error': f'Report #{report_id} not found'}), 404

    if user and getattr(user, 'role', '') == 'doctor':
        if report.get('generated_by') != user.id:
            pid = report.get('patient_id')
            if pid:
                pt = Patient.get_by_id(pid)
                if not pt or pt.get('assigned_doctor') != user.id:
                    return jsonify({'success': False, 'error': 'Access denied: You are not authorized to view this report.'}), 403
            else:
                return jsonify({'success': False, 'error': 'Access denied: You are not authorized to view this report.'}), 403

    return jsonify({
        'success': True,
        'data': report
    }), 200


# ─────────────────────────────────────────────────────────────
# 7. Direct Generation Endpoints (generate_reports permission)
# ─────────────────────────────────────────────────────────────
@report_bp.route('/generate/patient-report', methods=['POST'])
@permission_required('generate_reports')
def generate_patient_report_json():
    """Generate structured patient report JSON payload for frontend preview."""
    user = get_current_authenticated_user()
    body = request.get_json(silent=True) or {}
    patient_ids = body.get('patient_ids') or []
    if not patient_ids and body.get('patient_id'):
        patient_ids = [body.get('patient_id')]

    sections = body.get('sections')

    if not patient_ids:
        return jsonify({'success': False, 'error': 'Please select at least one patient to generate the report.'}), 400

    if sections is not None:
        if isinstance(sections, (list, tuple, set)) and len(sections) == 0:
            return jsonify({'success': False, 'error': 'Please select at least one report section.'}), 400
        elif isinstance(sections, str) and not sections.strip():
            return jsonify({'success': False, 'error': 'Please select at least one report section.'}), 400

    # RBAC check for doctors
    if user and getattr(user, 'role', '') == 'doctor':
        for pid in patient_ids:
            try:
                pid_int = int(pid)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': f'Invalid patient ID: {pid}'}), 400
            pt = Patient.get_by_id(pid_int)
            if not pt or pt.get('assigned_doctor') != user.id:
                return jsonify({
                    'success': False,
                    'error': f'Access denied: You are not authorized to preview reports for patient #{pid}.'
                }), 403

    user_id = getattr(user, 'id', None)
    user_name = getattr(user, 'full_name', None) or 'Administrator'
    result = generate_multi_patient_report_data(patient_ids, sections=sections, generated_by=user_id, generated_by_name=user_name)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 404

    return jsonify({'success': True, 'data': result}), 200


@report_bp.route('/generate/daily/<int:patient_id>', methods=['POST'])
@permission_required('generate_reports')
def generate_daily_report_endpoint(patient_id):
    """Generate daily report for a patient (Doctors and Admins only)."""
    user = get_current_authenticated_user()
    if user and getattr(user, 'role', '') == 'doctor':
        pt = Patient.get_by_id(patient_id)
        if not pt or pt.get('assigned_doctor') != user.id:
            return jsonify({
                'success': False,
                'error': f'Access denied: You are not authorized to generate reports for patient #{patient_id}.'
            }), 403

    result = generate_patient_report_data(patient_id, generated_by=user.id if user else None)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': result}), 200


@report_bp.route('/generate/discharge/<int:patient_id>', methods=['POST'])
@permission_required('generate_reports')
def generate_discharge_report_endpoint(patient_id):
    """Generate discharge report for a patient (Doctors and Admins only)."""
    user = get_current_authenticated_user()
    if user and getattr(user, 'role', '') == 'doctor':
        pt = Patient.get_by_id(patient_id)
        if not pt or pt.get('assigned_doctor') != user.id:
            return jsonify({
                'success': False,
                'error': f'Access denied: You are not authorized to generate reports for patient #{patient_id}.'
            }), 403

    result = generate_patient_report_data(patient_id, generated_by=user.id if user else None)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': result}), 200


# ─────────────────────────────────────────────────────────────
# 8. GET /reports/audit-logs & /audit/logs — Audit Trail Search API
# ─────────────────────────────────────────────────────────────
@report_bp.route('/audit-logs', methods=['GET'])
@report_bp.route('/audit/logs', methods=['GET'])
def get_audit_logs():
    """Retrieve and search system audit logs."""
    from models.audit_log_model import AuditLog
    query = request.args.get('search') or request.args.get('q') or ''
    action = request.args.get('action')
    role = request.args.get('role')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    logs = AuditLog.search(query=query, action=action, role=role, limit=limit, offset=offset)
    return jsonify({
        'success': True,
        'count': len(logs),
        'data': logs
    }), 200
