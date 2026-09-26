"""
routes/analytics_routes.py — Phase 16 Analytics REST APIs for Hospital Administrators & Clinicians.

Endpoints:
    GET /analytics/occupancy             (ICU/HDU/General bed occupancy rates & available beds)
    GET /analytics/transfers             (Transfer volume, transition flows, and turnaround times)
    GET /analytics/resource-utilization  (Capacity utilization, critical index, maintenance impact)
    GET /analytics/patient-statistics    (Patient counts, age/gender demographics, ward distribution)
    GET /analytics/ews-statistics        (Risk score distributions, ward averages, parameter impacts)
"""

from flask import Blueprint, jsonify
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
    Get Early Warning Score risk distributions, ward score averages, and parameter triggers.
    Returns:
        - Risk level distribution (Normal, Low, Medium, High, Critical)
        - Hospital average EWS and ward-specific averages (ICU, HDU, General)
        - Active critical patient alerts
        - Parameter deterioration breakdown
    """
    data = AnalyticsEngine.get_ews_statistics_analytics()
    return jsonify({
        'success': True,
        'metric': 'ews_statistics',
        'data': data
    }), 200
