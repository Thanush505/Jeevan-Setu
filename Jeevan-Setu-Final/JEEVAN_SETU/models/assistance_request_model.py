"""
models/assistance_request_model.py — Model for Attendant Assistance Requests.
Supports full lifecycle: submitted/pending -> acknowledged -> in_progress -> resolved,
with cancellation (by attendant) and rejection (by staff with mandatory reason).
"""

import re
from datetime import datetime
from database.db import db
from models.patient_model import Patient


class AssistanceRequest:
    """Model for managing patient attendant assistance requests."""

    CATEGORY_MAP = {
        'nursing': 'Request nursing assistance',
        'nursing_assistance': 'Request nursing assistance',
        'request nursing assistance': 'Request nursing assistance',
        'status': 'Request patient status update',
        'status_update': 'Request patient status update',
        'patient_status': 'Request patient status update',
        'request patient status update': 'Request patient status update',
        'speak_care_team': 'Request to speak with the care team',
        'care_team': 'Request to speak with the care team',
        'request to speak with the care team': 'Request to speak with the care team',
        'bedside': 'Request bedside assistance',
        'bedside_assistance': 'Request bedside assistance',
        'request bedside assistance': 'Request bedside assistance',
        'other': 'Other non-emergency assistance',
        'other_non_emergency': 'Other non-emergency assistance',
        'other non-emergency assistance': 'Other non-emergency assistance'
    }

    VALID_CATEGORIES = [
        'Request nursing assistance',
        'Request patient status update',
        'Request to speak with the care team',
        'Request bedside assistance',
        'Other non-emergency assistance'
    ]

    VALID_STATUSES = [
        'submitted',
        'pending',
        'acknowledged',
        'in_progress',
        'resolved',
        'cancelled',
        'rejected'
    ]

    CANCELLABLE_STATUSES = ['submitted', 'pending', 'acknowledged']

    @classmethod
    def normalize_category(cls, cat_input):
        """Map canonical or human-readable category strings to standardized names."""
        if not cat_input:
            return None
        cleaned = str(cat_input).strip()
        lower = cleaned.lower()
        if lower in cls.CATEGORY_MAP:
            return cls.CATEGORY_MAP[lower]
        for val in cls.VALID_CATEGORIES:
            if lower == val.lower():
                return val
        return None

    @classmethod
    def create(cls, patient_id, attendant_name, category, description=None, attendant_id=None):
        """
        Create a new assistance request for an authorized patient.
        """
        # Validate patient
        patient = Patient.get_by_id(patient_id)
        if not patient:
            raise ValueError(f"Patient #{patient_id} not found.")

        # Normalize & validate category
        norm_category = cls.normalize_category(category)
        if not norm_category:
            raise ValueError(
                f"Invalid request category '{category}'. Must be one of: {', '.join(cls.VALID_CATEGORIES)}"
            )

        # Sanitize & validate attendant name
        clean_name = str(attendant_name or '').strip()
        if not clean_name or len(clean_name) < 2:
            raise ValueError("Attendant name must be at least 2 characters.")

        # Sanitize & validate description (max 500 characters)
        clean_desc = None
        if description is not None:
            clean_desc = str(description).strip()
            if len(clean_desc) > 500:
                raise ValueError("Request description cannot exceed 500 characters.")
            if not clean_desc:
                clean_desc = None

        # Resolve ward/bed info from patient
        ward_id = None
        assigned_nurse_id = patient.get('assigned_nurse')

        # Check for recent duplicate submission (within 15 seconds) to prevent accidental double clicks
        dup = db.execute_query(
            """SELECT request_id, status, created_at
               FROM attendant_assistance_requests
               WHERE patient_id = %s
                 AND category = %s
                 AND (description = %s OR (description IS NULL AND %s IS NULL))
                 AND created_at >= NOW() - INTERVAL 15 SECOND
               LIMIT 1""",
            (patient_id, norm_category, clean_desc, clean_desc),
            fetch=True
        )
        if dup and len(dup) > 0:
            return cls.get_by_id(dup[0]['request_id'])

        # Insert new request record with 'pending' status
        req_id = db.execute_query(
            """INSERT INTO attendant_assistance_requests
               (patient_id, attendant_name, attendant_id, category, description,
                status, assigned_ward_id, assigned_nurse_id, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, NOW())""",
            (patient_id, clean_name, attendant_id, norm_category, clean_desc, ward_id, assigned_nurse_id)
        )

        return cls.get_by_id(req_id)

    @classmethod
    def get_by_id(cls, request_id):
        """Fetch assistance request detail by ID."""
        rows = db.execute_query(
            """SELECT r.*,
                      p.name AS patient_name,
                      p.patient_code,
                      p.ward_type,
                      p.bed_number,
                      p.age AS patient_age,
                      p.gender AS patient_gender,
                      u_assign.full_name AS assigned_user_name,
                      u_close.full_name AS closed_by_user_name
               FROM attendant_assistance_requests r
               JOIN patients p ON r.patient_id = p.patient_id
               LEFT JOIN users u_assign ON r.assigned_user_id = u_assign.user_id
               LEFT JOIN users u_close ON r.closed_by_user_id = u_close.user_id
               WHERE r.request_id = %s""",
            (request_id,),
            fetch=True
        )
        if not rows:
            return None
        return cls._format_record(rows[0])

    @classmethod
    def get_by_patient(cls, patient_id, status=None):
        """Fetch assistance requests for an authorized patient."""
        params = [patient_id]
        where_clause = "WHERE r.patient_id = %s"

        if status:
            if status in cls.VALID_STATUSES:
                where_clause += " AND r.status = %s"
                params.append(status)

        query = f"""
            SELECT r.*,
                   p.name AS patient_name,
                   p.patient_code,
                   p.ward_type,
                   p.bed_number,
                   u_assign.full_name AS assigned_user_name,
                   u_close.full_name AS closed_by_user_name
            FROM attendant_assistance_requests r
            JOIN patients p ON r.patient_id = p.patient_id
            LEFT JOIN users u_assign ON r.assigned_user_id = u_assign.user_id
            LEFT JOIN users u_close ON r.closed_by_user_id = u_close.user_id
            {where_clause}
            ORDER BY r.created_at DESC
        """
        rows = db.execute_query(query, tuple(params), fetch=True) or []
        return [cls._format_record(r) for r in rows]

    @classmethod
    def get_for_staff(cls, status=None, ward=None, patient_id=None, q=None, limit=100, offset=0):
        """
        Fetch requests for authorized staff members (Nurse, Doctor, Admin).
        Supports filtering by status, ward, patient_id, and search terms.
        """
        clauses = []
        params = []

        if status and status != 'all':
            if status in cls.VALID_STATUSES:
                clauses.append("r.status = %s")
                params.append(status)
            elif status == 'active':
                clauses.append("r.status IN ('submitted', 'pending', 'acknowledged', 'in_progress')")

        if ward and ward != 'all':
            clauses.append("p.ward_type = %s")
            params.append(ward)

        if patient_id:
            clauses.append("r.patient_id = %s")
            params.append(patient_id)

        if q:
            term = f"%{q.strip()}%"
            clauses.append("(p.name LIKE %s OR p.patient_code LIKE %s OR CAST(r.request_id AS CHAR) = %s OR r.category LIKE %s)")
            params.extend([term, term, q.strip(), term])

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        query = f"""
            SELECT r.*,
                   p.name AS patient_name,
                   p.patient_code,
                   p.ward_type,
                   p.bed_number,
                   p.age AS patient_age,
                   p.gender AS patient_gender,
                   u_assign.full_name AS assigned_user_name,
                   u_close.full_name AS closed_by_user_name
            FROM attendant_assistance_requests r
            JOIN patients p ON r.patient_id = p.patient_id
            LEFT JOIN users u_assign ON r.assigned_user_id = u_assign.user_id
            LEFT JOIN users u_close ON r.closed_by_user_id = u_close.user_id
            {where_sql}
            ORDER BY 
                CASE 
                    WHEN r.status = 'pending' THEN 1
                    WHEN r.status = 'submitted' THEN 2
                    WHEN r.status = 'acknowledged' THEN 3
                    WHEN r.status = 'in_progress' THEN 4
                    ELSE 5
                END,
                r.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([int(limit), int(offset)])
        rows = db.execute_query(query, tuple(params), fetch=True) or []
        return [cls._format_record(r) for r in rows]

    @classmethod
    def acknowledge(cls, request_id, user_id):
        """Acknowledge a pending assistance request."""
        req = cls.get_by_id(request_id)
        if not req:
            raise ValueError(f"Request #{request_id} not found.")

        current_status = req.get('status')
        if current_status not in ('submitted', 'pending'):
            if current_status in ('acknowledged', 'in_progress', 'resolved'):
                raise ValueError(f"Request #{request_id} is already {current_status}.")
            raise ValueError(f"Cannot acknowledge request in '{current_status}' state.")

        db.execute_query(
            """UPDATE attendant_assistance_requests
               SET status = 'acknowledged',
                   acknowledged_at = NOW(),
                   assigned_user_id = %s
               WHERE request_id = %s""",
            (user_id, request_id)
        )
        return cls.get_by_id(request_id)

    @classmethod
    def start(cls, request_id, user_id):
        """Mark assistance request as in-progress."""
        req = cls.get_by_id(request_id)
        if not req:
            raise ValueError(f"Request #{request_id} not found.")

        current_status = req.get('status')
        if current_status not in ('acknowledged', 'pending', 'submitted'):
            if current_status == 'in_progress':
                return req
            raise ValueError(f"Cannot start working on request in '{current_status}' state.")

        db.execute_query(
            """UPDATE attendant_assistance_requests
               SET status = 'in_progress',
                   started_at = NOW(),
                   assigned_user_id = %s
               WHERE request_id = %s""",
            (user_id, request_id)
        )
        return cls.get_by_id(request_id)

    @classmethod
    def resolve(cls, request_id, user_id, resolution_note=None):
        """Mark assistance request as resolved with optional resolution note."""
        req = cls.get_by_id(request_id)
        if not req:
            raise ValueError(f"Request #{request_id} not found.")

        current_status = req.get('status')
        if current_status in ('resolved', 'cancelled', 'rejected'):
            raise ValueError(f"Request #{request_id} is already in terminal state '{current_status}'.")

        clean_note = str(resolution_note).strip() if resolution_note else None

        db.execute_query(
            """UPDATE attendant_assistance_requests
               SET status = 'resolved',
                   resolved_at = NOW(),
                   closed_by_user_id = %s,
                   resolution_note = %s
               WHERE request_id = %s""",
            (user_id, clean_note, request_id)
        )
        return cls.get_by_id(request_id)

    @classmethod
    def reject(cls, request_id, user_id, rejection_reason):
        """Reject assistance request with a mandatory reason."""
        req = cls.get_by_id(request_id)
        if not req:
            raise ValueError(f"Request #{request_id} not found.")

        current_status = req.get('status')
        if current_status in ('resolved', 'cancelled', 'rejected'):
            raise ValueError(f"Request #{request_id} is already in terminal state '{current_status}'.")

        clean_reason = str(rejection_reason or '').strip()
        if not clean_reason or len(clean_reason) < 3:
            raise ValueError("A clear rejection reason of at least 3 characters is mandatory.")

        db.execute_query(
            """UPDATE attendant_assistance_requests
               SET status = 'rejected',
                   rejected_at = NOW(),
                   closed_by_user_id = %s,
                   rejection_reason = %s
               WHERE request_id = %s""",
            (user_id, clean_reason, request_id)
        )
        return cls.get_by_id(request_id)

    @classmethod
    def cancel(cls, request_id, patient_id=None, attendant_name=None):
        """
        Cancel assistance request by attendant.
        Only allowed when request is in submitted, pending, or acknowledged state.
        Strictly validates patient_id ownership if provided.
        """
        req = cls.get_by_id(request_id)
        if not req:
            raise ValueError(f"Request #{request_id} not found.")

        if patient_id is not None and int(req['patient_id']) != int(patient_id):
            raise PermissionError("Access denied: You can only cancel requests for your authorized patient.")

        current_status = req.get('status')
        if current_status not in cls.CANCELLABLE_STATUSES:
            raise ValueError(
                f"Request cannot be cancelled in '{current_status}' state (only allowed when pending or acknowledged)."
            )

        db.execute_query(
            """UPDATE attendant_assistance_requests
               SET status = 'cancelled',
                   cancelled_at = NOW()
               WHERE request_id = %s""",
            (request_id,)
        )
        return cls.get_by_id(request_id)

    @classmethod
    def get_summary_stats(cls):
        """Aggregate summary metrics for Nurse and Admin portals."""
        counts = db.execute_query(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN status IN ('submitted', 'pending') THEN 1 ELSE 0 END) AS pending,
                 SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) AS acknowledged,
                 SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
                 SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved,
                 SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                 SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                 SUM(CASE WHEN status IN ('submitted', 'pending', 'acknowledged', 'in_progress') THEN 1 ELSE 0 END) AS active
               FROM attendant_assistance_requests""",
            fetch=True
        ) or [{}]
        stat = counts[0]

        # Category breakdown
        cat_rows = db.execute_query(
            """SELECT category, COUNT(*) as cnt
               FROM attendant_assistance_requests
               GROUP BY category""",
            fetch=True
        ) or []

        # Average resolution time in minutes
        avg_row = db.execute_query(
            """SELECT 
                 ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, acknowledged_at)), 1) AS avg_ack_minutes,
                 ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, resolved_at)), 1) AS avg_resolve_minutes
               FROM attendant_assistance_requests
               WHERE resolved_at IS NOT NULL""",
            fetch=True
        ) or [{}]

        return {
            'total': int(stat.get('total') or 0),
            'pending': int(stat.get('pending') or 0),
            'acknowledged': int(stat.get('acknowledged') or 0),
            'in_progress': int(stat.get('in_progress') or 0),
            'resolved': int(stat.get('resolved') or 0),
            'cancelled': int(stat.get('cancelled') or 0),
            'rejected': int(stat.get('rejected') or 0),
            'active': int(stat.get('active') or 0),
            'categories': {r['category']: r['cnt'] for r in cat_rows},
            'avg_ack_minutes': avg_row[0].get('avg_ack_minutes'),
            'avg_resolve_minutes': avg_row[0].get('avg_resolve_minutes')
        }

    @staticmethod
    def _format_record(row):
        """Format raw DB record into clean API output dict."""
        if not row:
            return None
        rec = dict(row)

        # Elapsed time calculation
        created_at = rec.get('created_at')
        if created_at and isinstance(created_at, datetime):
            now = datetime.now()
            diff = now - created_at
            minutes = max(0, int(diff.total_seconds() / 60))
            if minutes < 1:
                elapsed_str = "Just now"
            elif minutes < 60:
                elapsed_str = f"{minutes}m ago"
            elif minutes < 1440:
                elapsed_str = f"{minutes // 60}h {minutes % 60}m ago"
            else:
                elapsed_str = f"{minutes // 1440}d ago"
            rec['elapsed_minutes'] = minutes
            rec['time_since_submission'] = elapsed_str
            rec['created_at_iso'] = created_at.isoformat()
        else:
            rec['elapsed_minutes'] = 0
            rec['time_since_submission'] = ""
            rec['created_at_iso'] = str(created_at) if created_at else None

        # Clean timestamps for JSON
        for k in ('acknowledged_at', 'started_at', 'resolved_at', 'cancelled_at', 'rejected_at', 'updated_at'):
            v = rec.get(k)
            if v and isinstance(v, datetime):
                rec[f"{k}_iso"] = v.isoformat()
            else:
                rec[f"{k}_iso"] = str(v) if v else None

        return rec
