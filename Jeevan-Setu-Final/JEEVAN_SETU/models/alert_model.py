"""
models/alert_model.py - Alert model for patient alerts and notifications.
"""

from database.db import db


def _extract_user_info(user):
    if not user:
        return '', None
    if isinstance(user, dict):
        role = str(user.get('role', '')).lower()
        user_id = user.get('id') or user.get('user_id')
        return role, user_id
    role = str(getattr(user, 'role', '')).lower()
    user_id = getattr(user, 'id', getattr(user, 'user_id', None))
    return role, user_id


class Alert:
    """Model for patient alerts triggered by abnormal vitals and clinical events."""

    @staticmethod
    def create(patient_id, alert_type, title, message,
               parameter=None, value=None, threshold=None):
        """Create a new alert with ACTIVE status."""
        return db.execute_query(
            """INSERT INTO alerts (patient_id, alert_type, status, title, message,
               parameter, value, threshold, is_acknowledged, is_dismissed)
               VALUES (%s, %s, 'ACTIVE', %s, %s, %s, %s, %s, FALSE, FALSE)""",
            (patient_id, alert_type, title, message, parameter, value, threshold)
        )

    @staticmethod
    def get_active(user=None, limit=50):
        """Get all active (unacknowledged and undismissed) alerts scoped to user role & assigned patients."""
        where_clauses = [
            "a.is_acknowledged = FALSE",
            "a.is_dismissed = FALSE",
            "(a.status = 'ACTIVE' OR a.status IS NULL)"
        ]
        params = []
        role, user_id = _extract_user_info(user)
        if role == 'doctor' and user_id:
            where_clauses.append("p.assigned_doctor = %s")
            params.append(user_id)
        elif role == 'nurse' and user_id:
            where_clauses.append("p.assigned_nurse = %s")
            params.append(user_id)
        elif role == 'attendant':
            return []
        
        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        return db.execute_query(
            f"""SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.patient_code, p.diagnosis, p.assigned_doctor, p.assigned_nurse,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as total_ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as score,
                      COALESCE(e.risk_level, 'LOW') as risk_level
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN (
                   SELECT e1.patient_id, e1.total_score, e1.risk_level, e1.vital_id
                   FROM ews_scores e1
                   INNER JOIN (
                       SELECT patient_id, MAX(ews_id) as max_ews_id
                       FROM ews_scores GROUP BY patient_id
                   ) e2 ON e1.ews_id = e2.max_ews_id
               ) e ON p.patient_id = e.patient_id
               LEFT JOIN (
                   SELECT v1.patient_id, v1.ews_score
                   FROM vitals v1
                   INNER JOIN (
                       SELECT patient_id, MAX(vital_id) as max_id
                       FROM vitals GROUP BY patient_id
                   ) v2 ON v1.vital_id = v2.max_id
               ) v ON p.patient_id = v.patient_id
               WHERE {where_sql}
               ORDER BY 
                 CASE a.alert_type 
                   WHEN 'critical' THEN 1 
                   WHEN 'high' THEN 2 
                   WHEN 'medium' THEN 3 
                   WHEN 'low' THEN 4 
                   ELSE 5 
                 END ASC,
                 a.created_at DESC LIMIT %s""",
            tuple(params), fetch=True
        ) or []

    @staticmethod
    def get_acknowledged(user=None, limit=50):
        """Get acknowledged/dismissed alerts scoped to user."""
        where_clauses = [
            "(a.is_acknowledged = TRUE OR a.is_dismissed = TRUE OR a.status = 'DISMISSED')"
        ]
        params = []
        role, user_id = _extract_user_info(user)
        if role == 'doctor' and user_id:
            where_clauses.append("p.assigned_doctor = %s")
            params.append(user_id)
        elif role == 'nurse' and user_id:
            where_clauses.append("p.assigned_nurse = %s")
            params.append(user_id)
        elif role == 'attendant':
            return []
        
        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        return db.execute_query(
            f"""SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.patient_code, p.diagnosis, p.assigned_doctor, p.assigned_nurse,
                      COALESCE(u.full_name, CONCAT('User #', a.dismissed_by), 'Staff') as dismissed_by_name,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as total_ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as score,
                      COALESCE(e.risk_level, 'LOW') as risk_level
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN users u ON (a.dismissed_by = u.user_id OR a.acknowledged_by = u.user_id)
               LEFT JOIN (
                   SELECT e1.patient_id, e1.total_score, e1.risk_level, e1.vital_id
                   FROM ews_scores e1
                   INNER JOIN (
                       SELECT patient_id, MAX(ews_id) as max_ews_id
                       FROM ews_scores GROUP BY patient_id
                   ) e2 ON e1.ews_id = e2.max_ews_id
               ) e ON p.patient_id = e.patient_id
               LEFT JOIN (
                   SELECT v1.patient_id, v1.ews_score
                   FROM vitals v1
                   INNER JOIN (
                       SELECT patient_id, MAX(vital_id) as max_id
                       FROM vitals GROUP BY patient_id
                   ) v2 ON v1.vital_id = v2.max_id
               ) v ON p.patient_id = v.patient_id
               WHERE {where_sql}
               ORDER BY COALESCE(a.dismissed_at, a.acknowledged_at, a.created_at) DESC LIMIT %s""",
            tuple(params), fetch=True
        ) or []

    @staticmethod
    def get_all_for_user(user=None, limit=100):
        """Get all alerts (both ACTIVE and DISMISSED) scoped to authenticated user."""
        where_clauses = ["1=1"]
        params = []
        role, user_id = _extract_user_info(user)
        if role == 'doctor' and user_id:
            where_clauses.append("p.assigned_doctor = %s")
            params.append(user_id)
        elif role == 'nurse' and user_id:
            where_clauses.append("p.assigned_nurse = %s")
            params.append(user_id)
        elif role == 'attendant':
            return []
        
        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        return db.execute_query(
            f"""SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.patient_code, p.diagnosis, p.assigned_doctor, p.assigned_nurse,
                      COALESCE(u.full_name, CONCAT('Staff #', a.dismissed_by), 'Nurse Staff') as dismissed_by_name,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as total_ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as score,
                      COALESCE(e.risk_level, 'LOW') as risk_level
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN users u ON (a.dismissed_by = u.user_id OR a.acknowledged_by = u.user_id)
               LEFT JOIN (
                   SELECT e1.patient_id, e1.total_score, e1.risk_level, e1.vital_id
                   FROM ews_scores e1
                   INNER JOIN (
                       SELECT patient_id, MAX(ews_id) as max_ews_id
                       FROM ews_scores GROUP BY patient_id
                   ) e2 ON e1.ews_id = e2.max_ews_id
               ) e ON p.patient_id = e.patient_id
               LEFT JOIN (
                   SELECT v1.patient_id, v1.ews_score
                   FROM vitals v1
                   INNER JOIN (
                       SELECT patient_id, MAX(vital_id) as max_id
                       FROM vitals GROUP BY patient_id
                   ) v2 ON v1.vital_id = v2.max_id
               ) v ON p.patient_id = v.patient_id
               WHERE {where_sql}
               ORDER BY 
                 CASE 
                   WHEN a.status = 'ACTIVE' AND a.is_acknowledged = FALSE AND a.is_dismissed = FALSE THEN 0 
                   ELSE 1 
                 END ASC,
                 CASE a.alert_type 
                   WHEN 'critical' THEN 1 
                   WHEN 'high' THEN 2 
                   WHEN 'medium' THEN 3 
                   WHEN 'low' THEN 4 
                   ELSE 5 
                 END ASC,
                 a.created_at DESC LIMIT %s""",
            tuple(params), fetch=True
        ) or []

    @staticmethod
    def get_by_patient(patient_id):
        """Get alerts for a specific patient."""
        return db.execute_query(
            """SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.patient_code, p.diagnosis,
                      COALESCE(u.full_name, CONCAT('Staff #', a.dismissed_by), 'Staff') as dismissed_by_name,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as total_ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as score,
                      COALESCE(e.risk_level, 'LOW') as risk_level
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN users u ON (a.dismissed_by = u.user_id OR a.acknowledged_by = u.user_id)
               LEFT JOIN (
                   SELECT e1.patient_id, e1.total_score, e1.risk_level
                   FROM ews_scores e1
                   INNER JOIN (
                       SELECT patient_id, MAX(ews_id) as max_ews_id
                       FROM ews_scores GROUP BY patient_id
                   ) e2 ON e1.ews_id = e2.max_ews_id
               ) e ON p.patient_id = e.patient_id
               LEFT JOIN (
                   SELECT v1.patient_id, v1.ews_score
                   FROM vitals v1
                   INNER JOIN (
                       SELECT patient_id, MAX(vital_id) as max_id
                       FROM vitals GROUP BY patient_id
                   ) v2 ON v1.vital_id = v2.max_id
               ) v ON p.patient_id = v.patient_id
               WHERE a.patient_id = %s ORDER BY a.created_at DESC""",
            (patient_id,), fetch=True
        ) or []

    @staticmethod
    def dismiss(alert_id, user_id):
        """Dismiss/Acknowledge an alert without deleting the record."""
        return db.execute_query(
            """UPDATE alerts 
               SET status = 'DISMISSED',
                   is_dismissed = TRUE,
                   dismissed_by = %s,
                   dismissed_at = NOW(),
                   is_acknowledged = TRUE,
                   acknowledged_by = %s,
                   acknowledged_at = NOW()
               WHERE alert_id = %s""",
            (user_id, user_id, alert_id)
        )

    @staticmethod
    def acknowledge(alert_id, user_id):
        """Acknowledge an alert (synonymous with persistent dismissal)."""
        return Alert.dismiss(alert_id, user_id)

    @staticmethod
    def acknowledge_all_non_urgent(user_id):
        """Dismiss/Acknowledge all active non-urgent alerts (medium, low, info)."""
        return db.execute_query(
            """UPDATE alerts 
               SET status = 'DISMISSED',
                   is_dismissed = TRUE,
                   dismissed_by = %s,
                   dismissed_at = NOW(),
                   is_acknowledged = TRUE,
                   acknowledged_by = %s,
                   acknowledged_at = NOW()
               WHERE (is_acknowledged = FALSE AND is_dismissed = FALSE)
               AND alert_type IN ('medium', 'low', 'info')""",
            (user_id, user_id)
        )

    @staticmethod
    def get_count_by_type(user=None):
        """Get count of active (undismissed) alerts by type scoped to user."""
        where_clauses = [
            "a.is_acknowledged = FALSE",
            "a.is_dismissed = FALSE",
            "(a.status = 'ACTIVE' OR a.status IS NULL)"
        ]
        params = []
        role, user_id = _extract_user_info(user)
        if role == 'doctor' and user_id:
            where_clauses.append("p.assigned_doctor = %s")
            params.append(user_id)
        elif role == 'nurse' and user_id:
            where_clauses.append("p.assigned_nurse = %s")
            params.append(user_id)
        elif role == 'attendant':
            return []
        
        where_sql = " AND ".join(where_clauses)
        return db.execute_query(
            f"""SELECT a.alert_type, COUNT(*) as count
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               WHERE {where_sql}
               GROUP BY a.alert_type""",
            tuple(params) if params else None, fetch=True
        ) or []

    @staticmethod
    def has_active_alert(patient_id, alert_type='critical', parameter=None):
        """Check if an active (unacknowledged & undismissed) alert already exists for this patient and alert_type."""
        if parameter:
            res = db.execute_query(
                """SELECT alert_id FROM alerts
                   WHERE patient_id = %s AND alert_type = %s AND parameter = %s 
                     AND is_acknowledged = FALSE AND is_dismissed = FALSE
                   LIMIT 1""",
                (patient_id, alert_type, parameter), fetch=True
            )
        else:
            res = db.execute_query(
                """SELECT alert_id FROM alerts
                   WHERE patient_id = %s AND alert_type = %s 
                     AND is_acknowledged = FALSE AND is_dismissed = FALSE
                   LIMIT 1""",
                (patient_id, alert_type), fetch=True
            )
        return bool(res)

    @staticmethod
    def auto_resolve_patient_alerts(patient_id, alert_type='critical'):
        """Automatically resolve active alerts of a given type when patient state normalizes."""
        return db.execute_query(
            """UPDATE alerts 
               SET status = 'DISMISSED',
                   is_dismissed = TRUE,
                   dismissed_at = NOW(),
                   is_acknowledged = TRUE,
                   acknowledged_at = NOW()
               WHERE patient_id = %s AND alert_type = %s AND (is_acknowledged = FALSE AND is_dismissed = FALSE)""",
            (patient_id, alert_type)
        )

    @staticmethod
    def get_active_emergency_for_user(user=None, limit=20):
        """
        Fetch active, unacknowledged & undismissed CRITICAL emergency alerts scoped to user role & assigned patients.
        """
        where_clauses = [
            "a.is_acknowledged = FALSE",
            "a.is_dismissed = FALSE",
            "(a.status = 'ACTIVE' OR a.status IS NULL)",
            "a.alert_type = 'critical'"
        ]
        params = []
        role, user_id = _extract_user_info(user)
        if role == 'doctor' and user_id:
            where_clauses.append("p.assigned_doctor = %s")
            params.append(user_id)
        elif role == 'nurse' and user_id:
            where_clauses.append("p.assigned_nurse = %s")
            params.append(user_id)
        elif role == 'attendant':
            return []

        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        return db.execute_query(
            f"""SELECT a.*, p.name as patient_name, p.patient_code, p.ward_type, p.bed_number,
                      p.diagnosis, p.assigned_doctor, p.assigned_nurse,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as total_ews_score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as score,
                      COALESCE(e.total_score, v.ews_score, CAST(a.value AS SIGNED)) as latest_ews_score,
                      COALESCE(e.risk_level, CASE WHEN a.value >= 7 THEN 'CRITICAL' WHEN a.value >= 5 THEN 'HIGH' WHEN a.value >= 3 THEN 'MEDIUM' ELSE 'LOW' END) as risk_level,
                      v.recorded_at as vitals_recorded_at
               FROM alerts a
               JOIN patients p ON a.patient_id = p.patient_id
               LEFT JOIN (
                   SELECT e1.patient_id, e1.total_score, e1.risk_level, e1.vital_id
                   FROM ews_scores e1
                   INNER JOIN (
                       SELECT patient_id, MAX(ews_id) as max_ews_id
                       FROM ews_scores GROUP BY patient_id
                   ) e2 ON e1.ews_id = e2.max_ews_id
               ) e ON p.patient_id = e.patient_id
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
