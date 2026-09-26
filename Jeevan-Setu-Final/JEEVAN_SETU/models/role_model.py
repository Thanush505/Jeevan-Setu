"""
models/role_model.py — Role model for Role-Based Access Control (RBAC).
"""

from database.db import db


class Role:
    """Role model representing system roles (admin, doctor, nurse, attendant)."""

    @staticmethod
    def get_all():
        """Fetch all available roles."""
        return db.execute_query("SELECT * FROM roles ORDER BY role_id ASC", fetch=True)

    @staticmethod
    def get_by_id(role_id):
        """Fetch a role by ID."""
        result = db.execute_query("SELECT * FROM roles WHERE role_id = %s", (role_id,), fetch=True)
        return result[0] if result else None

    @staticmethod
    def get_by_name(name):
        """Fetch a role by its slug/name."""
        result = db.execute_query("SELECT * FROM roles WHERE name = %s", (name,), fetch=True)
        return result[0] if result else None

    @staticmethod
    def create(name, display_name, description=None):
        """Create a new role."""
        return db.execute_query(
            "INSERT INTO roles (name, display_name, description) VALUES (%s, %s, %s)",
            (name, display_name, description)
        )
