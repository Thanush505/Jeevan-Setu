"""
models/report_model.py — Report model for database persistence and querying of report metadata.
"""

from database.db import db


class Report:
    """Model for patient, clinical, and system reports."""

    TYPE_MAPPING = {
        'patient': 'daily',
        'daily': 'daily',
        'weekly': 'weekly',
        'discharge': 'discharge',
        'transfer': 'transfer',
        'transfers': 'transfer',
        'ews': 'custom',
        'utilization': 'custom',
        'resource_utilization': 'custom',
        'custom': 'custom'
    }

    @staticmethod
    def create(report_type, title, content=None, patient_id=None,
               file_path=None, generated_by=None):
        """Create a new report metadata record."""
        db_type = Report.TYPE_MAPPING.get(str(report_type).lower(), 'custom')
        return db.execute_query(
            """INSERT INTO reports (patient_id, report_type, title, content,
               file_path, generated_by)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (patient_id, db_type, title, content, file_path, generated_by)
        )

    @staticmethod
    def get_by_id(report_id):
        """Fetch a report by ID with patient and generator details."""
        result = db.execute_query(
            """SELECT r.*, p.name AS patient_name, p.patient_code, u.full_name AS generated_by_name
               FROM reports r
               LEFT JOIN patients p ON r.patient_id = p.patient_id
               LEFT JOIN users u ON r.generated_by = u.user_id
               WHERE r.report_id = %s""",
            (report_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_by_patient(patient_id):
        """Get all reports for a patient."""
        return db.execute_query(
            """SELECT r.*, u.full_name AS generated_by_name
               FROM reports r
               LEFT JOIN users u ON r.generated_by = u.user_id
               WHERE r.patient_id = %s
               ORDER BY r.created_at DESC""",
            (patient_id,), fetch=True
        )

    @staticmethod
    def get_all(report_type=None, limit=50, doctor_id=None):
        """Get all reports, optionally filtered by type and doctor_id."""
        clauses = []
        params = []
        if report_type:
            clauses.append("r.report_type = %s")
            params.append(report_type)
        if doctor_id:
            clauses.append("(r.generated_by = %s OR p.assigned_doctor = %s)")
            params.extend([doctor_id, doctor_id])
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""SELECT r.*, p.name AS patient_name, p.patient_code, u.full_name AS generated_by_name
                  FROM reports r
                  LEFT JOIN patients p ON r.patient_id = p.patient_id
                  LEFT JOIN users u ON r.generated_by = u.user_id
                  {where_sql}
                  ORDER BY r.created_at DESC LIMIT %s"""
        params.append(limit)
        return db.execute_query(sql, tuple(params), fetch=True)
