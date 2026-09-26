"""
models/decision_model.py — Database model for clinical transfer decisions.
"""

from database.db import db


class Decision:
    """Model representing transfer decisions and automated recommendations."""

    @staticmethod
    def create(patient_id, from_ward, to_ward, recommendation, vital_id=None,
               ews_score=None, confidence=None, status='pending', decided_by=None,
               patient_name=None):
        """Create a new decision record with patient_name."""
        p_name = patient_name
        if not p_name and patient_id:
            p_res = db.execute_query("SELECT name FROM patients WHERE patient_id = %s", (patient_id,), fetch=True)
            if p_res and p_res[0].get('name'):
                p_name = p_res[0]['name']

        return db.execute_query(
            """INSERT INTO decisions 
               (patient_id, patient_name, from_ward, to_ward, recommendation, vital_id, 
                ews_score, confidence, status, decided_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (patient_id, p_name, from_ward, to_ward, recommendation, vital_id,
             ews_score, confidence, status, decided_by)
        )

    @staticmethod
    def get_by_id(decision_id):
        """Fetch decision by ID."""
        result = db.execute_query(
            "SELECT * FROM decisions WHERE decision_id = %s",
            (decision_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_by_patient(patient_id, limit=20):
        """Fetch decisions for a patient."""
        return db.execute_query(
            """SELECT d.*, u.full_name AS decided_by_name
               FROM decisions d
               LEFT JOIN users u ON d.decided_by = u.user_id
               WHERE d.patient_id = %s
               ORDER BY d.created_at DESC LIMIT %s""",
            (patient_id, limit), fetch=True
        ) or []

    @staticmethod
    def update_status(decision_id, status, decided_by=None):
        """Update decision status."""
        return db.execute_query(
            """UPDATE decisions 
               SET status = %s, decided_by = %s, decided_at = NOW()
               WHERE decision_id = %s""",
            (status, decided_by, decision_id)
        )
