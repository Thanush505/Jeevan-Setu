"""
routes/analytics_routes.py — Phase 16 Analytics REST APIs for Hospital Administrators & Clinicians.

Endpoints:
    GET /analytics/occupancy             (ICU/HDU/General bed occupancy rates & available beds)
    GET /analytics/transfers             (Transfer volume, transition flows, and turnaround times)
    GET /analytics/resource-utilization  (Capacity utilization, critical index, maintenance impact)
    GET /analytics/patient-statistics    (Patient counts, age/gender demographics, ward distribution)
    GET /analytics/ews-statistics        (Risk score distributions, ward averages, parameter impacts)
"""

from flask import Blueprint, jsonify, request, Response
from modules.analytics_engine import AnalyticsEngine
from utils.decorators import permission_required

analytics_bp = Blueprint('analytics', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /analytics/occupancy
# ─────────────────────────────────────────────────────────────
@analytics_bp.route('/occupancy', methods=['GET'])
@permission_required('view_analytics')
def get_occupancy_analytics():
    """
    Get hospital-wide, ICU, HDU, and ward-specific bed occupancy analytics.
    Returns:
        - Hospital total beds, occupied beds, available beds, maintenance beds, occupancy rate %
        - ICU occupancy & HDU occupancy breakdown
        - Granular ward-level breakdown
    """
    data = AnalyticsEngine.get_occupancy_analytics()
    return jsonify({
        'success': True,
        'metric': 'occupancy',
        'data': data
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. GET /analytics/transfers
# ─────────────────────────────────────────────────────────────
@analytics_bp.route('/transfers', methods=['GET'])
@permission_required('view_analytics')
def get_transfer_analytics():
    """
    Get patient transfer statistics, transition flows, and turnaround metrics.
    Returns:
        - Total transfers and status distribution (completed, approved, pending, rejected)
        - Route flows (ICU -> HDU, HDU -> ICU, etc.)
        - Top transfer reasons
        - Average turnaround time (hours)
    """
    data = AnalyticsEngine.get_transfer_analytics()
    return jsonify({
        'success': True,
        'metric': 'transfers',
        'data': data
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. GET /analytics/resource-utilization
# ─────────────────────────────────────────────────────────────
@analytics_bp.route('/resource-utilization', methods=['GET'])
@permission_required('view_analytics')
def get_resource_utilization_analytics():
    """
    Get hospital resource utilization metrics and capacity alerts.
    Returns:
        - Overall utilization rate %
        - Critical care bed utilization % (ICU + HDU)
        - Maintenance bed impact %
        - High-occupancy ward alert list (>85% occupancy)
    """
    data = AnalyticsEngine.get_resource_utilization_analytics()
    return jsonify({
        'success': True,
        'metric': 'resource_utilization',
        'data': data
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. GET /analytics/patient-statistics
# ─────────────────────────────────────────────────────────────
@analytics_bp.route('/patient-statistics', methods=['GET'])
@permission_required('view_analytics')
def get_patient_statistics_analytics():
    """
    Get patient population demographics, ward distribution, and admission diagnoses.
    Returns:
        - Total registered, active admitted, and discharged counts
        - Active ward distribution (ICU, HDU, General)
        - Gender distribution & age demographics
        - Top admission diagnoses
    """
    data = AnalyticsEngine.get_patient_statistics_analytics()
    return jsonify({
        'success': True,
        'metric': 'patient_statistics',
        'data': data
    }), 200


# ─────────────────────────────────────────────────────────────
# 5. GET /analytics/ews-statistics
# ─────────────────────────────────────────────────────────────
@analytics_bp.route('/ews-statistics', methods=['GET'])
@permission_required('view_analytics')
def get_ews_statistics_analytics():
    """
    Get Early Warning Score risk distributions, ward score averages, trends,
    clinical escalations, response times, and high-risk patient analytics.
    """
    time_range = request.args.get('range', '7d')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    ward_filter = request.args.get('ward')

    data = AnalyticsEngine.get_ews_statistics_analytics(
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        ward_filter=ward_filter,
    )
    return jsonify({
        'success': True,
        'metric': 'ews_statistics',
        'data': data
    }), 200


@analytics_bp.route('/ews-statistics/export', methods=['GET'])
@permission_required('view_analytics')
def export_ews_statistics_csv():
    """Export EWS Analytics summary and high-risk patient table as CSV."""
    import csv
    import io

    time_range = request.args.get('range', '7d')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    ward_filter = request.args.get('ward')

    data = AnalyticsEngine.get_ews_statistics_analytics(
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        ward_filter=ward_filter,
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Jeevan Setu EWS Analytics Report'])
    writer.writerow(['Generated At', data.get('timestamp')])
    writer.writerow(['Date Range', f"{data['filters']['range']} ({data['filters']['start_date']} to {data['filters']['end_date']})"])
    writer.writerow(['Ward Filter', data['filters']['ward']])
    writer.writerow([])
    writer.writerow(['KPI Summary'])
    kpis = data.get('kpis', {})
    writer.writerow(['Evaluated Patients', data.get('total_evaluated_patients', 0)])
    writer.writerow(['High-Risk Patients (EWS >= 5)', kpis.get('high_risk_patients', 0)])
    writer.writerow(['Average EWS Score', kpis.get('average_ews', 0)])
    writer.writerow(['Clinical Escalations', kpis.get('clinical_escalations', 0)])
    writer.writerow(['Avg Alert Ack Response (min)', kpis.get('avg_response_time_minutes') if kpis.get('avg_response_time_minutes') is not None else 'N/A'])
    writer.writerow(['Patients Requiring Review', kpis.get('patients_requiring_review', 0)])
    writer.writerow([])
    writer.writerow(['Risk Distribution', 'Count'])
    for k, v in (data.get('risk_distribution') or {}).items():
        writer.writerow([k, v])
    writer.writerow([])
    writer.writerow(['High-Risk / Review Patients'])
    writer.writerow(['Patient Code', 'Patient Name', 'Ward', 'Bed', 'EWS Score', 'Risk Category', 'Unacked Alerts', 'Calculated At'])
    for row in data.get('high_risk_patients_table', []):
        writer.writerow([
            row.get('patient_code'),
            row.get('patient_name'),
            row.get('ward_name'),
            row.get('bed_number'),
            row.get('ews_score'),
            row.get('risk_category'),
            row.get('unacked_alerts'),
            row.get('calculated_at') or '',
        ])

    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename="jeevan_setu_ews_analytics.csv"'}
    )
