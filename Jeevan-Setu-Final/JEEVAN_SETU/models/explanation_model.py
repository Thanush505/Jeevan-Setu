"""
models/explanation_model.py — Model for Explainable AI (XAI) records.
"""

from database.db import db


class Explanation:
    """Model for storing AI decision explanations and feature contributions."""

    @staticmethod
    def create(decision_id, patient_id, feature_name, feature_value,
               contribution, importance_rank=None, explanation_text=None):
        """Store an explanation entry for a decision."""
        return db.execute_query(
            """INSERT INTO explanations (decision_id, patient_id, feature_name,
               feature_value, contribution, importance_rank, explanation_text)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (decision_id, patient_id, feature_name, feature_value,
             contribution, importance_rank, explanation_text)
        )

    @staticmethod
    def get_by_decision(decision_id):
        """Get all explanations for a specific decision."""
        return db.execute_query(
            """SELECT * FROM explanations WHERE decision_id = %s
               ORDER BY importance_rank ASC, explanation_id ASC""",
            (decision_id,), fetch=True
        ) or []

    @staticmethod
    def get_by_patient(patient_id, limit=50):
        """Get recent explanations for a patient."""
        return db.execute_query(
            """SELECT e.*, d.recommendation, d.confidence, d.ews_score, d.status AS decision_status
               FROM explanations e
               LEFT JOIN decisions d ON e.decision_id = d.decision_id
               WHERE e.patient_id = %s
               ORDER BY e.created_at DESC, e.importance_rank ASC LIMIT %s""",
            (patient_id, limit), fetch=True
        ) or []

    @staticmethod
    def delete_by_decision(decision_id):
        """Delete explanations for a decision."""
        return db.execute_query(
            "DELETE FROM explanations WHERE decision_id = %s",
            (decision_id,)
        )
