"""
models/ward_model.py — Ward model for ICU/HDU/General ward management.
"""

from database.db import db


class Ward:
    """Ward model representing hospital wards."""

    @staticmethod
    def create(name, ward_type='ICU', floor_number=1, total_beds=10, description=None):
        """Create a new ward."""
        return db.execute_query(
            """INSERT INTO wards (name, ward_type, floor_number, total_beds, description)
               VALUES (%s, %s, %s, %s, %s)""",
            (name.strip(), ward_type.strip().upper() if ward_type.upper() in ('ICU', 'HDU') else ward_type.strip().capitalize(),
             floor_number, total_beds, description)
        )

    @staticmethod
    def get_by_id(ward_id):
        """Fetch ward by ID with bed counts and occupancy rate."""
        query = """
        SELECT 
            w.*,
            w.name AS ward_name,
            COUNT(CASE WHEN b.is_active = TRUE THEN 1 END) AS actual_beds,
            COUNT(CASE WHEN b.status = 'occupied' AND b.is_active = TRUE THEN 1 END) AS occupied_beds,
            COUNT(CASE WHEN b.status = 'available' AND b.is_active = TRUE THEN 1 END) AS available_beds,
            COUNT(CASE WHEN b.status = 'maintenance' AND b.is_active = TRUE THEN 1 END) AS maintenance_beds,
            ROUND(
                (COUNT(CASE WHEN b.status = 'occupied' AND b.is_active = TRUE THEN 1 END) / 
                 NULLIF(COUNT(CASE WHEN b.is_active = TRUE THEN 1 END), 0)) * 100, 
                1
            ) AS occupancy_rate
        FROM wards w
        LEFT JOIN beds b ON w.ward_id = b.ward_id
        WHERE w.ward_id = %s
        GROUP BY w.ward_id
        """
        result = db.execute_query(query, (ward_id,), fetch=True)
        if not result:
            return None
        ward = result[0]
        ward['id'] = ward['ward_id']
        return ward

    @staticmethod
    def get_all(active_only=True, ward_type=None):
        """Fetch all wards with occupancy statistics."""
        where_clauses = []
        params = []

        if active_only:
            where_clauses.append("w.is_active = TRUE")
        if ward_type:
            where_clauses.append("w.ward_type = %s")
            params.append(ward_type)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
        SELECT 
            w.ward_id,
            w.name,
            w.name AS ward_name,
            w.ward_type,
            w.floor_number,
            w.total_beds,
            w.description,
            w.is_active,
            w.created_at,
            w.updated_at,
            w.ward_id AS id,
            COUNT(CASE WHEN b.is_active = TRUE THEN 1 END) AS actual_beds,
            COUNT(CASE WHEN b.status = 'occupied' AND b.is_active = TRUE THEN 1 END) AS occupied_beds,
            COUNT(CASE WHEN b.status = 'available' AND b.is_active = TRUE THEN 1 END) AS available_beds,
            COUNT(CASE WHEN b.status = 'maintenance' AND b.is_active = TRUE THEN 1 END) AS maintenance_beds,
            ROUND(
                (COUNT(CASE WHEN b.status = 'occupied' AND b.is_active = TRUE THEN 1 END) / 
                 NULLIF(COUNT(CASE WHEN b.is_active = TRUE THEN 1 END), 0)) * 100, 
                1
            ) AS occupancy_rate
        FROM wards w
        LEFT JOIN beds b ON w.ward_id = b.ward_id
        {where_sql}
        GROUP BY w.ward_id, w.name, w.ward_type, w.floor_number, w.total_beds, w.description, w.is_active, w.created_at, w.updated_at
        ORDER BY w.ward_type, w.name
        """
        return db.execute_query(query, tuple(params) if params else None, fetch=True) or []

    @staticmethod
    def get_by_type(ward_type):
        """Fetch wards by type (ICU, HDU, General)."""
        return Ward.get_all(active_only=True, ward_type=ward_type)

    @staticmethod
    def update(ward_id, **kwargs):
        """Update ward details."""
        allowed = ['name', 'ward_type', 'floor_number', 'total_beds', 'description', 'is_active']
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ', '.join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [ward_id]
        db.execute_query(f"UPDATE wards SET {set_clause} WHERE ward_id = %s", values)

    @staticmethod
    def delete(ward_id):
        """Deactivate ward if no occupied beds exist."""
        # Check if occupied beds exist
        occupied = db.execute_query(
            "SELECT COUNT(*) AS cnt FROM beds WHERE ward_id = %s AND status = 'occupied' AND is_active = TRUE",
            (ward_id,), fetch=True
        )
        if occupied and occupied[0]['cnt'] > 0:
            raise ValueError(f"Cannot delete ward with {occupied[0]['cnt']} currently occupied bed(s). Please transfer or discharge patients first.")

        # Soft delete (deactivate)
        db.execute_query("UPDATE wards SET is_active = FALSE WHERE ward_id = %s", (ward_id,))
        db.execute_query("UPDATE beds SET is_active = FALSE WHERE ward_id = %s AND status != 'occupied'", (ward_id,))

    @staticmethod
    def get_occupancy_summary():
        """Get ward occupancy rates with total, occupied, and available bed counts."""
        return Ward.get_all(active_only=True)
