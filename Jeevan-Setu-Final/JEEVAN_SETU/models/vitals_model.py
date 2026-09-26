"""
models/vitals_model.py — Vitals model for patient vital sign records.
"""

from database.db import db


class Vitals:
    """Model for patient vital sign recordings."""

    @staticmethod
    def record(patient_id, heart_rate=None, blood_pressure_sys=None,
               respiratory_rate=None, temperature=None,
               ews_score=0, recorded_by=None, **kwargs):
        """Record a new set of vitals for a patient (4 core parameters: HR, SBP, RR, Temp)."""
        return db.execute_query(
            """INSERT INTO vitals (patient_id, heart_rate, blood_pressure_sys,
               respiratory_rate, temperature, ews_score, recorded_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (patient_id, heart_rate, blood_pressure_sys,
             respiratory_rate, temperature, ews_score, recorded_by)
        )

    create = record
    record_vitals = record

    @staticmethod
    def get_latest(patient_id):
        """Get the most recent vitals for a patient."""
        result = db.execute_query(
            """SELECT * FROM vitals WHERE patient_id = %s
               ORDER BY recorded_at DESC, vital_id DESC LIMIT 1""",
            (patient_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_history(patient_id, limit=50):
        """Get vital sign history for a patient."""
        return db.execute_query(
            """SELECT * FROM vitals WHERE patient_id = %s
               ORDER BY recorded_at DESC, vital_id DESC LIMIT %s""",
            (patient_id, limit), fetch=True
        )

    @staticmethod
    def get_by_id(vital_id):
        """Fetch a specific vital record by ID."""
        result = db.execute_query(
            "SELECT * FROM vitals WHERE vital_id = %s", (vital_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_critical_patients():
        """Get patients with critical EWS scores (latest vitals only)."""
        return db.execute_query(
            """SELECT v.*, p.name, p.ward_type, p.bed_number
               FROM vitals v
               INNER JOIN patients p ON v.patient_id = p.patient_id
               WHERE v.vital_id IN (
                   SELECT MAX(vital_id) FROM vitals GROUP BY patient_id
               )
               AND v.ews_score >= 7
               AND p.status = 'admitted'
               ORDER BY v.ews_score DESC""",
            fetch=True
        )

    @staticmethod
    def update_ews(vital_id, ews_score):
        """Update the EWS score for a vital record."""
        db.execute_query(
            "UPDATE vitals SET ews_score = %s WHERE vital_id = %s",
            (ews_score, vital_id)
        )
