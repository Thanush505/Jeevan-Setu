"""
models/ews_score_model.py — Early Warning Score calculation records model.
"""

from database.db import db


class EWSScore:
    """EWS Scores tracking and historical analytics."""

    @staticmethod
    def record(patient_id, vital_id, total_score, risk_level,
               hr_score=0, bp_score=0, rr_score=0, temp_score=0, patient_name=None, **kwargs):
        """Record an EWS score entry (4 core parameters: HR, SBP, RR, Temp) with patient_name."""
        r_level = str(risk_level).upper().strip()
        if r_level in ('NORMAL', 'NONE', '0'):
            r_level = 'LOW'
        elif r_level not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
            r_level = 'LOW'

        # Auto-lookup patient_name if not provided
        p_name = patient_name
        if not p_name and patient_id:
            p_res = db.execute_query("SELECT name FROM patients WHERE patient_id = %s", (patient_id,), fetch=True)
            if p_res and p_res[0].get('name'):
                p_name = p_res[0]['name']

        return db.execute_query(
            """INSERT INTO ews_scores (patient_id, patient_name, vital_id, total_score, risk_level,
                                       hr_score, bp_score, rr_score, temp_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (patient_id, p_name, vital_id, total_score, r_level,
             hr_score, bp_score, rr_score, temp_score)
        )

    @staticmethod
    def get_latest(patient_id):
        """Get latest EWS score for a patient."""
        result = db.execute_query(
            "SELECT * FROM ews_scores WHERE patient_id = %s ORDER BY calculated_at DESC, ews_id DESC LIMIT 1",
            (patient_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_history(patient_id, limit=20):
        """Get score history for trends."""
        return db.execute_query(
            "SELECT * FROM ews_scores WHERE patient_id = %s ORDER BY calculated_at DESC, ews_id DESC LIMIT %s",
            (patient_id, limit), fetch=True
        )

    @staticmethod
    def get_high_risk_patients():
        """Get all patients currently in HIGH or CRITICAL risk."""
        query = """
        SELECT e.*, p.name, p.ward_type, p.bed_number, p.diagnosis
        FROM ews_scores e
        JOIN patients p ON e.patient_id = p.patient_id
        INNER JOIN (
            SELECT patient_id, MAX(calculated_at) AS max_time
            FROM ews_scores GROUP BY patient_id
        ) latest ON e.patient_id = latest.patient_id AND e.calculated_at = latest.max_time
        WHERE e.risk_level IN ('HIGH', 'CRITICAL') AND p.status = 'admitted'
        ORDER BY e.total_score DESC
        """
        return db.execute_query(query, fetch=True)
