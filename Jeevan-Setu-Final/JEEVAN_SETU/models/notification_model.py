"""
models/notification_model.py — Notification model for staff alerts and clinical events.
"""

from database.db import db


class Notification:
    """In-app notifications and alerts for doctors, nurses, and administrators."""

    TYPE_MAPPING = {
        'CRITICAL_VITAL': 'alert',
        'ESCALATION': 'alert',
        'TRANSFER_READY': 'transfer',
        'TRANSFER': 'transfer',
        'SYSTEM': 'system',
        'INFO': 'system',
        'WARNING': 'alert',
        'CRITICAL': 'alert'
    }

    @staticmethod
    def create(user_id, title, message, notif_type='system', patient_id=None, severity=None):
        """Send a notification to a specific user."""
        db_type = Notification.TYPE_MAPPING.get(str(notif_type).upper(), str(notif_type).lower())
        if db_type not in ('alert', 'transfer', 'system', 'ews', 'broadcast'):
            db_type = 'system'

        formatted_title = title
        if severity and not title.startswith(f"[{severity}]"):
            formatted_title = f"[{severity.upper()}] {title}"

        return db.execute_query(
            """INSERT INTO notifications (user_id, title, message, type, patient_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, formatted_title, message, db_type, patient_id)
        )

    @staticmethod
    def broadcast_to_role(role, title, message, notif_type='alert', patient_id=None, severity=None):
        """Broadcast a notification to all active users with a specified role."""
        users = db.execute_query(
            "SELECT user_id FROM users WHERE role = %s AND is_active = TRUE",
            (role,), fetch=True
        ) or []

        if not users:
            return 0

        db_type = Notification.TYPE_MAPPING.get(str(notif_type).upper(), str(notif_type).lower())
        if db_type not in ('alert', 'transfer', 'system', 'ews', 'broadcast'):
            db_type = 'alert'

        formatted_title = title
        if severity and not title.startswith(f"[{severity}]"):
            formatted_title = f"[{severity.upper()}] {title}"

        data = [(u['user_id'], formatted_title, message, db_type, patient_id) for u in users]
        return db.execute_many(
            """INSERT INTO notifications (user_id, title, message, type, patient_id)
               VALUES (%s, %s, %s, %s, %s)""",
            data
        )

    @staticmethod
    def broadcast_to_all_staff(title, message, notif_type='alert', patient_id=None, severity=None):
        """Broadcast notification to all active staff (Doctors, Nurses, Admins)."""
        users = db.execute_query(
            "SELECT user_id FROM users WHERE role IN ('doctor', 'nurse', 'admin') AND is_active = TRUE",
            fetch=True
        ) or []

        if not users:
            return 0

        db_type = Notification.TYPE_MAPPING.get(str(notif_type).upper(), str(notif_type).lower())
        if db_type not in ('alert', 'transfer', 'system', 'ews', 'broadcast'):
            db_type = 'alert'

        formatted_title = title
        if severity and not title.startswith(f"[{severity}]"):
            formatted_title = f"[{severity.upper()}] {title}"

        data = [(u['user_id'], formatted_title, message, db_type, patient_id) for u in users]
        return db.execute_many(
            """INSERT INTO notifications (user_id, title, message, type, patient_id)
               VALUES (%s, %s, %s, %s, %s)""",
            data
        )

    @staticmethod
    def get_by_user(user_id, unread_only=False, notif_type=None, limit=50):
        """Fetch notifications for a user with optional unread filter and categorization."""
        conditions = ["user_id = %s"]
        params = [user_id]

        if unread_only:
            conditions.append("is_read = FALSE")

        if notif_type:
            db_type = Notification.TYPE_MAPPING.get(str(notif_type).upper(), str(notif_type).lower())
            conditions.append("type = %s")
            params.append(db_type)

        where_clause = " AND ".join(conditions)
        params.append(limit)

        notifications = db.execute_query(
            f"""SELECT n.*, p.name AS patient_name, p.ward_type, p.bed_number
                FROM notifications n
                LEFT JOIN patients p ON n.patient_id = p.patient_id
                WHERE {where_clause}
                ORDER BY n.created_at DESC LIMIT %s""",
            tuple(params), fetch=True
        ) or []

        # Enrich with parsed event_type and severity for clients
        for notif in notifications:
            title = notif.get('title', '')
            if title.startswith('[') and ']' in title:
                sev = title[1:title.index(']')]
                notif['severity'] = sev
            else:
                db_t = notif.get('type', 'system')
                if db_t == 'alert':
                    notif['severity'] = 'CRITICAL'
                elif db_t == 'transfer':
                    notif['severity'] = 'TRANSFER'
                else:
                    notif['severity'] = 'INFO'

        return notifications

    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications for a user."""
        res = db.execute_query(
            "SELECT COUNT(*) AS unread_count FROM notifications WHERE user_id = %s AND is_read = FALSE",
            (user_id,), fetch=True
        )
        return res[0]['unread_count'] if res else 0

    @staticmethod
    def mark_as_read(notification_id, user_id=None):
        """Mark a specific notification as read."""
        if user_id:
            return db.execute_query(
                "UPDATE notifications SET is_read = TRUE, read_at = NOW() WHERE notification_id = %s AND user_id = %s",
                (notification_id, user_id)
            )
        return db.execute_query(
            "UPDATE notifications SET is_read = TRUE, read_at = NOW() WHERE notification_id = %s",
            (notification_id,)
        )

    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all unread notifications as read for a user."""
        return db.execute_query(
            "UPDATE notifications SET is_read = TRUE, read_at = NOW() WHERE user_id = %s AND is_read = FALSE",
            (user_id,)
        )
