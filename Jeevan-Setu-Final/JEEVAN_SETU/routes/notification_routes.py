"""
routes/notification_routes.py — Phase 14 Notifications & Alerts REST APIs.
Endpoints:
    GET  /notifications & /api/v1/notifications         (List user notifications, counts)
    PUT  /notifications/{id}/read & POST ...            (Mark single notification as read)
    PUT  /notifications/read-all & POST ...             (Mark all notifications as read)
    POST /notifications/trigger & /api/v1/...           (Trigger backend event notification)
"""

from flask import Blueprint, request, jsonify
from models.notification_model import Notification
from services.notification_service import NotificationService
from utils.decorators import permission_required, get_current_authenticated_user

notification_bp = Blueprint('notification', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /notifications & /api/v1/notifications
# ─────────────────────────────────────────────────────────────
@notification_bp.route('/', methods=['GET'])
@notification_bp.route('', methods=['GET'])
def list_user_notifications():
    """
    Fetch notifications for current authenticated user.
    Query params:
        - unread_only (bool): If true, filters only unread notifications.
        - type (str): Filter by type/event (CRITICAL_VITAL, TRANSFER_READY, ESCALATION, SYSTEM).
        - limit (int): Max records (default: 50).
    """
    user = get_current_authenticated_user()
    if not user or not user.is_authenticated:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    unread_only_param = request.args.get('unread_only', '').lower() in ('true', '1', 'yes')
    notif_type = request.args.get('type')
    limit = request.args.get('limit', 50, type=int)

    notifications = Notification.get_by_user(
        user_id=user.id,
        unread_only=unread_only_param,
        notif_type=notif_type,
        limit=limit
    )
    unread_count = Notification.get_unread_count(user.id)

    return jsonify({
        'success': True,
        'user_id': user.id,
        'unread_count': unread_count,
        'count': len(notifications),
        'data': notifications
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. PUT /notifications/{id}/read & POST /notifications/{id}/read
# ─────────────────────────────────────────────────────────────
@notification_bp.route('/<int:notification_id>/read', methods=['PUT', 'POST'])
def mark_notification_read(notification_id):
    """Mark a single notification as read for current user."""
    user = get_current_authenticated_user()
    if not user or not user.is_authenticated:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    Notification.mark_as_read(notification_id=notification_id, user_id=user.id)
    unread_count = Notification.get_unread_count(user.id)

    return jsonify({
        'success': True,
        'message': f'Notification #{notification_id} marked as read',
        'notification_id': notification_id,
        'unread_count': unread_count
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. PUT /notifications/read-all & POST /notifications/read-all
# ─────────────────────────────────────────────────────────────
@notification_bp.route('/read-all', methods=['PUT', 'POST'])
def mark_all_notifications_read():
    """Mark all unread notifications as read for current user."""
    user = get_current_authenticated_user()
    if not user or not user.is_authenticated:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    Notification.mark_all_as_read(user_id=user.id)

    return jsonify({
        'success': True,
        'message': 'All notifications marked as read',
        'unread_count': 0
    }), 200


# ─────────────────────────────────────────────────────────────
# 4. POST /notifications/trigger — Event-driven trigger
# ─────────────────────────────────────────────────────────────
@notification_bp.route('/trigger', methods=['POST'])
def trigger_notification_event():
    """
    Trigger notification event dispatch from backend events.
    Payload:
        {
            "event_type": "CRITICAL_VITAL" | "TRANSFER_READY" | "ESCALATION" | "SYSTEM",
            "patient_id": 12, (optional)
            "title": "...",
            "message": "...",
            "severity": "CRITICAL" | "WARNING" | "INFO" | "TRANSFER",
            "parameter": "heart_rate", (optional for vitals)
            "value": 145,              (optional for vitals)
            "from_ward": "ICU",        (optional for transfers)
            "to_ward": "HDU"           (optional for transfers)
        }
    """
    user = get_current_authenticated_user()
    if not user or not user.is_authenticated:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    event_type = str(data.get('event_type') or data.get('type') or 'SYSTEM').upper()
    patient_id = data.get('patient_id')
    severity = data.get('severity', 'INFO')

    if event_type == 'CRITICAL_VITAL':
        res = NotificationService.trigger_critical_vital(
            patient_id=patient_id or 1,
            parameter=data.get('parameter', 'heart_rate'),
            value=data.get('value', 140),
            threshold=data.get('threshold', 130),
            ews_score=data.get('ews_score', 8)
        )
    elif event_type == 'TRANSFER_READY':
        res = NotificationService.trigger_transfer_ready(
            patient_id=patient_id or 1,
            from_ward=data.get('from_ward', 'ICU'),
            to_ward=data.get('to_ward', 'HDU'),
            score=data.get('score', 2)
        )
    elif event_type == 'ESCALATION':
        res = NotificationService.trigger_escalation(
            patient_id=patient_id or 1,
            from_ward=data.get('from_ward', 'HDU'),
            to_ward=data.get('to_ward', 'ICU'),
            reason=data.get('reason', 'Acute deterioration'),
            score=data.get('score', 7)
        )
    else:
        res = NotificationService.trigger_system_event(
            title=data.get('title', 'System Notification'),
            message=data.get('message', 'System operational event triggered'),
            severity=severity,
            target_role=data.get('target_role')
        )

    return jsonify({
        'success': True,
        'message': f"Notification event '{event_type}' dispatched successfully",
        'data': res
    }), 201
