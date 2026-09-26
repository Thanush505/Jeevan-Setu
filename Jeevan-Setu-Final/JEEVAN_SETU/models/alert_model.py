"""
models/alert_model.py — Alert model for patient alerts and notifications.
"""

from database.db import db


class Alert:
    """Model for patient alerts triggered by abnormal vitals."""

    @staticmethod
    def create(patient_id, alert_type, title, message,
               parameter=None, value=None, threshold=None):
        """Create a new alert."""
        return db.execute_query(
            """INSERT INTO alerts (patient_id, alert_type, title, message,
               parameter, value, threshold)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (patient_id, alert_type, title, message, parameter, value, threshold)
        )

    @staticmethod
    def get_active(limit=50):
        """Get all unacknowledged alerts."""
        return db.execute_query(
            """SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.patient_code, p.diagnosis
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               WHERE a.is_acknowledged = FALSE
               ORDER BY 
                 CASE a.alert_type 
                   WHEN 'critical' THEN 1 
                   WHEN 'high' THEN 2 
                   WHEN 'medium' THEN 3 
                   WHEN 'low' THEN 4 
                   ELSE 5 
                 END ASC,
                 a.created_at DESC LIMIT %s""",
            (limit,), fetch=True
        ) or []

    @staticmethod
    def get_acknowledged(limit=50):
        """Get all acknowledged alerts."""
        return db.execute_query(
            """SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.patient_code, p.diagnosis,
                      u.full_name as acknowledged_by_name
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN users u ON a.acknowledged_by = u.user_id
               WHERE a.is_acknowledged = TRUE
               ORDER BY a.acknowledged_at DESC, a.alert_id DESC LIMIT %s""",
            (limit,), fetch=True
        ) or []

    @staticmethod
    def get_by_patient(patient_id):
        """Get alerts for a specific patient."""
        return db.execute_query(
            "SELECT * FROM alerts WHERE patient_id = %s ORDER BY created_at DESC",
            (patient_id,), fetch=True
        ) or []

    @staticmethod
    def acknowledge(alert_id, user_id):
        """Acknowledge an alert."""
        db.execute_query(
            """UPDATE alerts SET is_acknowledged = TRUE,
               acknowledged_by = %s, acknowledged_at = NOW()
               WHERE alert_id = %s""",
            (user_id, alert_id)
        )

    @staticmethod
    def acknowledge_all_non_urgent(user_id):
        """Acknowledge all active non-urgent alerts (medium, low, info)."""
        return db.execute_query(
            """UPDATE alerts SET is_acknowledged = TRUE,
               acknowledged_by = %s, acknowledged_at = NOW()
               WHERE is_acknowledged = FALSE
               AND alert_type IN ('medium', 'low', 'info')""",
            (user_id,)
        )

    @staticmethod
    def get_count_by_type():
        """Get count of active alerts by type."""
        return db.execute_query(
            """SELECT alert_type, COUNT(*) as count
               FROM alerts WHERE is_acknowledged = FALSE
               GROUP BY alert_type""",
            fetch=True
        ) or []

    @staticmethod
    def has_active_alert(patient_id, alert_type='critical', parameter=None):
        """Check if an active (unacknowledged) alert already exists for this patient and alert_type."""
        if parameter:
            res = db.execute_query(
                """SELECT alert_id FROM alerts
                   WHERE patient_id = %s AND alert_type = %s AND parameter = %s AND is_acknowledged = FALSE
                   LIMIT 1""",
                (patient_id, alert_type, parameter), fetch=True
            )
        else:
            res = db.execute_query(
                """SELECT alert_id FROM alerts
                   WHERE patient_id = %s AND alert_type = %s AND is_acknowledged = FALSE
                   LIMIT 1""",
                (patient_id, alert_type), fetch=True
            )
        return bool(res)

    @staticmethod
    def auto_resolve_patient_alerts(patient_id, alert_type='critical'):
        """Automatically resolve active alerts of a given type when patient state normalizes."""
        return db.execute_query(
            """UPDATE alerts SET is_acknowledged = TRUE, acknowledged_at = NOW()
               WHERE patient_id = %s AND alert_type = %s AND is_acknowledged = FALSE""",
            (patient_id, alert_type)
        )

    @staticmethod
    def get_active_emergency_for_user(user=None, limit=20):
        """
        Fetch active, unacknowledged CRITICAL emergency alerts scoped to user role & assigned patients.
        """
        where_clauses = ["a.is_acknowledged = FALSE", "a.alert_type = 'critical'"]
        params = []

        if user:
            role = getattr(user, 'role', '').lower()
            user_id = getattr(user, 'id', getattr(user, 'user_id', None))
            if role == 'doctor' and user_id:
                # Scoped to assigned doctor or hospital patients
                where_clauses.append("(p.assigned_doctor = %s OR p.assigned_doctor IS NULL)")
                params.append(user_id)
            elif role == 'nurse' and user_id:
                # Scoped to assigned nurse or matching ward
                dept = getattr(user, 'department', None)
                if dept:
                    where_clauses.append("(p.assigned_nurse = %s OR p.assigned_nurse IS NULL OR p.ward_type = %s)")
                    params.extend([user_id, dept])
                else:
                    where_clauses.append("(p.assigned_nurse = %s OR p.assigned_nurse IS NULL)")
                    params.append(user_id)
            elif role == 'attendant':
                # Attendants should NOT receive clinical emergency broadcast alerts
                return []

        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        return db.execute_query(
            f"""SELECT a.*, p.name as patient_name, p.patient_code, p.ward_type, p.bed_number,
                      p.diagnosis, p.assigned_doctor, p.assigned_nurse,
                      v.ews_score as latest_ews_score, v.recorded_at as vitals_recorded_at
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN (
                   SELECT v1.patient_id, v1.ews_score, v1.recorded_at
                   FROM vitals v1
                   INNER JOIN (
                       SELECT patient_id, MAX(vital_id) as max_id
                       FROM vitals GROUP BY patient_id
                   ) v2 ON v1.vital_id = v2.max_id
               ) v ON p.patient_id = v.patient_id
               WHERE {where_sql}
               ORDER BY a.created_at DESC LIMIT %s""",
            tuple(params), fetch=True
        ) or []