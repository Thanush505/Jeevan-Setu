"""
models/audit_log_model.py — Model for audit trail and compliance activity logging.
"""

import json
from database.db import db


class AuditLog:
    """Model for recording system actions and compliance audit trails."""

    @staticmethod
    def log(action, user_id=None, entity_type=None, entity_id=None,
            old_value=None, new_value=None, ip_address=None, description=None):
        """Create an audit log entry."""
        val_old = json.dumps(old_value, default=str) if (old_value and not isinstance(old_value, str)) else old_value
        val_new = json.dumps(new_value, default=str) if (new_value and not isinstance(new_value, str)) else new_value
        
        try:
            return db.execute_query(
                """INSERT INTO audit_logs (user_id, action, entity_type, entity_id,
                   old_value, new_value, ip_address, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, action, entity_type, entity_id, val_old, val_new, ip_address, description)
            )
        except Exception:
            # Fallback to audit_log table if alias used
            return db.execute_query(
                """INSERT INTO audit_log (user_id, action, entity_type, entity_id,
                   old_value, new_value, ip_address, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, action, entity_type, entity_id, val_old, val_new, ip_address, description)
            )

    @staticmethod
    def get_recent(limit=100):
        """Get recent audit log entries."""
        try:
            return db.execute_query(
                """SELECT al.*, u.full_name as user_name
                   FROM audit_logs al
                   LEFT JOIN users u ON al.user_id = u.user_id
                   ORDER BY al.created_at DESC LIMIT %s""",
                (limit,), fetch=True
            )
        except Exception:
            return db.execute_query(
                """SELECT al.*, u.full_name as user_name
                   FROM audit_log al
                   LEFT JOIN users u ON al.user_id = u.user_id
                   ORDER BY al.created_at DESC LIMIT %s""",
                (limit,), fetch=True
            )

    @staticmethod
    def get_by_user(user_id, limit=50):
        """Get audit logs for a specific user."""
        try:
            return db.execute_query(
                "SELECT * FROM audit_logs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit), fetch=True
            )
        except Exception:
            return db.execute_query(
                "SELECT * FROM audit_log WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit), fetch=True
            )

    @staticmethod
    def get_by_entity(entity_type, entity_id):
        """Get audit logs for a specific entity."""
        try:
            return db.execute_query(
                """SELECT * FROM audit_logs
                   WHERE entity_type = %s AND entity_id = %s
                   ORDER BY created_at DESC""",
                (entity_type, entity_id), fetch=True
            )
        except Exception:
            return db.execute_query(
                """SELECT * FROM audit_log
                   WHERE entity_type = %s AND entity_id = %s
                   ORDER BY created_at DESC""",
                (entity_type, entity_id), fetch=True
            )

    @staticmethod
    def search(query=None, action=None, role=None, limit=100, offset=0):
        """Search and filter audit logs safely with parameterized query."""
        where_clauses = []
        params = []

        if action and action != 'all':
            where_clauses.append("al.action = %s")
            params.append(action)

        if role and role != 'all':
            where_clauses.append("u.role = %s")
            params.append(role)

        if query:
            q = f"%{query.strip()}%"
            where_clauses.append("(al.action LIKE %s OR al.description LIKE %s OR u.full_name LIKE %s OR u.username LIKE %s OR CAST(al.entity_id AS CHAR) LIKE %s OR al.ip_address LIKE %s)")
            params.extend([q, q, q, q, q, q])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = f"""
            SELECT al.*, u.full_name as user_name, u.role as user_role, u.username
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.user_id
            {where_sql}
            ORDER BY al.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        try:
            return db.execute_query(sql, tuple(params), fetch=True) or []
        except Exception:
            sql_fallback = f"""
                SELECT al.*, u.full_name as user_name, u.role as user_role, u.username
                FROM audit_log al
                LEFT JOIN users u ON al.user_id = u.user_id
                {where_sql}
                ORDER BY al.created_at DESC
                LIMIT %s OFFSET %s
            """
            return db.execute_query(sql_fallback, tuple(params), fetch=True) or []

