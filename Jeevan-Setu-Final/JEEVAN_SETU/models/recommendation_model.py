"""
models/recommendation_model.py — Clinical recommendations and transfer decisions.
"""

from database.db import db


class Recommendation:
    """Clinical decision support recommendations (ICU to HDU, HDU to ICU, etc.)."""

    @staticmethod
    def create(patient_id, from_ward, to_ward, recommendation_text, score=0, confidence=0.0,
               reason=None, vital_id=None, ews_id=None, status='pending', decided_by=None):
        """Create a new clinical recommendation."""
        return db.execute_query(
            """INSERT INTO recommendations 
               (patient_id, from_ward, to_ward, recommendation_text, score, confidence,
                reason, vital_id, ews_id, status, decided_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (patient_id, from_ward, to_ward, recommendation_text, score, confidence,
             reason, vital_id, ews_id, status, decided_by)
        )

    @staticmethod
    def get_by_id(recommendation_id):
        """Fetch recommendation by ID."""
        result = db.execute_query(
            "SELECT * FROM recommendations WHERE recommendation_id = %s",
            (recommendation_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_pending():
        """Get all pending transfer recommendations."""
        query = """
        SELECT r.*, p.name AS patient_name, p.ward_type, p.bed_number, p.diagnosis
        FROM recommendations r
        JOIN patients p ON r.patient_id = p.patient_id
        WHERE r.status = 'pending' AND p.status = 'admitted'
        ORDER BY r.created_at DESC
        """
        return db.execute_query(query, fetch=True)

    @staticmethod
    def get_by_patient(patient_id):
        """Fetch all recommendations for a specific patient."""
        query = """
        SELECT r.*, u.full_name AS decided_by_name
        FROM recommendations r
        LEFT JOIN users u ON r.decided_by = u.user_id
        WHERE r.patient_id = %s
        ORDER BY r.created_at DESC
        """
        return db.execute_query(query, (patient_id,), fetch=True) or []

    @staticmethod
    def update_status(recommendation_id, status, decided_by=None):
        """Approve or reject a recommendation."""
        return db.execute_query(
            """UPDATE recommendations 
               SET status = %s, decided_by = %s, decided_at = NOW() 
               WHERE recommendation_id = %s""",
            (status, decided_by, recommendation_id)
        )
