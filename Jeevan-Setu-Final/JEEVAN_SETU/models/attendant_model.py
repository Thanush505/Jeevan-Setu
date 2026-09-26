"""
models/attendant_model.py — Attendant model for patient family access.
"""

import secrets
from database.db import db


class Attendant:
    """Model for patient attendants (family members)."""

    @staticmethod
    def create(patient_id, user_id, relationship=None):
        """Register an attendant for a patient with a unique access code."""
        access_code = secrets.token_hex(5).upper()  # 10-char code
        return db.execute_query(
            """INSERT INTO attendants (patient_id, user_id, relationship, access_code)
               VALUES (%s, %s, %s, %s)""",
            (patient_id, user_id, relationship, access_code)
        )

    @staticmethod
    def get_by_access_code(access_code):
        """Fetch attendant details by access code."""
        result = db.execute_query(
            """SELECT a.*, p.name as patient_name, p.ward_type, p.bed_number, p.status
               FROM attendants a
               JOIN patients p ON a.patient_id = p.patient_id
               WHERE a.access_code = %s AND a.is_active = TRUE""",
            (access_code,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_by_patient(patient_id):
        """Get all attendants for a patient."""
        return db.execute_query(
            "SELECT * FROM attendants WHERE patient_id = %s AND is_active = TRUE",
            (patient_id,), fetch=True
        )

    @staticmethod
    def deactivate(attendant_id):
        """Deactivate an attendant's access."""
        db.execute_query(
            "UPDATE attendants SET is_active = FALSE WHERE attendant_id = %s",
            (attendant_id,)
        )
