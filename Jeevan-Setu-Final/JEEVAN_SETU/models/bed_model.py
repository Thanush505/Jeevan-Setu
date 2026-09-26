"""
models/bed_model.py — Bed model for ICU/HDU/General hospital bed management.
"""

from database.db import db


class Bed:
    """Bed model representing physical beds in ICU/HDU/General wards."""

    VALID_STATUSES = ('available', 'occupied', 'maintenance', 'reserved')

    @staticmethod
    def create(ward_id, bed_number, status='available', bed_type='Standard'):
        """Register a new bed in a ward."""
        status_norm = (status or 'available').strip().lower()
        if status_norm not in Bed.VALID_STATUSES:
            raise ValueError(f"Invalid bed status '{status}'. Must be one of: {', '.join(Bed.VALID_STATUSES)}")

        return db.execute_query(
            "INSERT INTO beds (ward_id, bed_number, status) VALUES (%s, %s, %s)",
            (ward_id, bed_number.strip(), status_norm)
        )

    @staticmethod
    def get_by_id(bed_id):
        """Fetch a bed by ID with ward and occupant details."""
        query = """
        SELECT 
            b.*,
            b.bed_id AS id,
            w.name AS ward_name,
            w.ward_type,
            w.floor_number,
            p.patient_id,
            p.patient_code,
            p.name AS patient_name,
            p.gender AS patient_gender,
            p.age AS patient_age,
            p.admission_date,
            bm.allocated_at,
            u.full_name AS doctor_name
        FROM beds b
        JOIN wards w ON b.ward_id = w.ward_id
        LEFT JOIN (
            SELECT * FROM bed_management 
            WHERE status IN ('allocated', 'occupied')
        ) bm ON b.bed_id = bm.bed_id
        LEFT JOIN patients p ON bm.patient_id = p.patient_id AND p.status = 'admitted'
        LEFT JOIN users u ON p.assigned_doctor = u.user_id
        WHERE b.bed_id = %s
        """
        result = db.execute_query(query, (bed_id,), fetch=True)
        return result[0] if result else None

    @staticmethod
    def get_all(ward_id=None, ward_type=None, status=None, active_only=True):
        """Fetch beds filtered by ward, type, or status."""
        where_clauses = []
        params = []

        if active_only:
            where_clauses.append("b.is_active = TRUE")
        if ward_id:
            where_clauses.append("b.ward_id = %s")
            params.append(int(ward_id))
        if ward_type:
            where_clauses.append("w.ward_type = %s")
            params.append(ward_type)
        if status and status.lower() != 'all':
            where_clauses.append("b.status = %s")
            params.append(status.lower())

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
        SELECT 
            b.*,
            b.bed_id AS id,
            w.name AS ward_name,
            w.ward_type,
            p.patient_id,
            p.patient_code,
            p.name AS patient_name,
            p.diagnosis AS patient_diagnosis,
            bm.allocated_at
        FROM beds b
        JOIN wards w ON b.ward_id = w.ward_id
        LEFT JOIN (
            SELECT bm1.* 
            FROM bed_management bm1
            INNER JOIN (
                SELECT bed_id, MAX(allocated_at) AS max_alloc
                FROM bed_management 
                WHERE status IN ('allocated', 'occupied')
                GROUP BY bed_id
            ) bm2 ON bm1.bed_id = bm2.bed_id AND bm1.allocated_at = bm2.max_alloc
        ) bm ON b.bed_id = bm.bed_id AND b.status = 'occupied'
        LEFT JOIN patients p ON bm.patient_id = p.patient_id AND p.status = 'admitted'
        {where_sql}
        ORDER BY w.ward_type, w.name, b.bed_number
        """
        return db.execute_query(query, tuple(params) if params else None, fetch=True) or []

    @staticmethod
    def get_by_ward(ward_id, status=None):
        """Fetch all beds in a ward, optionally filtered by status."""
        return Bed.get_all(ward_id=ward_id, status=status)

    @staticmethod
    def get_available_beds(ward_type=None):
        """Fetch available beds across hospital or within a ward type."""
        return Bed.get_all(ward_type=ward_type, status='available')

    @staticmethod
    def update(bed_id, **kwargs):
        """Update bed fields."""
        allowed = ['bed_number', 'status', 'ward_id', 'is_active']
        fields = {}
        for k, v in kwargs.items():
            if k in allowed:
                if k == 'status' and v:
                    status_norm = str(v).strip().lower()
                    if status_norm not in Bed.VALID_STATUSES:
                        raise ValueError(f"Invalid bed status '{v}'. Allowed: {', '.join(Bed.VALID_STATUSES)}")
                    fields[k] = status_norm
                else:
                    fields[k] = v

        if not fields:
            return

        set_clause = ', '.join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [bed_id]
        db.execute_query(f"UPDATE beds SET {set_clause} WHERE bed_id = %s", values)

    @staticmethod
    def update_status(bed_id, status):
        """Update bed status ('available', 'occupied', 'maintenance', 'reserved')."""
        Bed.update(bed_id, status=status)

    @staticmethod
    def set_maintenance(bed_id, notes=None):
        """Set bed into maintenance mode (must not be currently occupied)."""
        bed = Bed.get_by_id(bed_id)
        if not bed:
            raise ValueError(f"Bed with ID {bed_id} not found.")
        if bed['status'] == 'occupied':
            raise ValueError(f"Cannot put bed {bed['bed_number']} into maintenance: currently occupied by patient '{bed.get('patient_name')}'.")
        Bed.update(bed_id, status='maintenance')

    @staticmethod
    def delete(bed_id):
        """Deactivate/delete a bed (must not be currently occupied)."""
        bed = Bed.get_by_id(bed_id)
        if not bed:
            raise ValueError(f"Bed with ID {bed_id} not found.")
        if bed['status'] == 'occupied':
            raise ValueError(f"Cannot delete bed {bed['bed_number']}: currently occupied by patient '{bed.get('patient_name')}'.")

        db.execute_query("UPDATE beds SET is_active = FALSE WHERE bed_id = %s", (bed_id,))
