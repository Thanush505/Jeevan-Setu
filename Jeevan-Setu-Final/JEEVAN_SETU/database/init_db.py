"""
database/init_db.py — Initialize the database and create tables.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from mysql.connector import Error
from config import get_config
from database.migration_manager import MigrationManager
from models.user_model import hash_pw


def init_database():
    """Create the database and all tables from schema.sql and run migrations."""
    config = get_config()

    try:
        # Connect without specifying a database to create it
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD
        )
        cursor = conn.cursor()

        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {config.DB_NAME}")
        print(f"[OK] Database '{config.DB_NAME}' ready.")

        # Read and execute schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        for statement in statements:
            lines = [line for line in statement.splitlines()
                     if line.strip() and not line.strip().startswith('--')]
            clean_stmt = '\n'.join(lines).strip()
            if clean_stmt:
                try:
                    cursor.execute(clean_stmt)
                except Error as e:
                    if e.errno in (1061, 1050):
                        continue
                    print(f"[WARN] Statement warning: {e}")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("[OK] All tables from schema.sql created successfully.")

        # Run migration manager to mark migrations
        mm = MigrationManager()
        mm.run_migrations()

        # Insert default admin user and roles
        insert_default_data(cursor, conn)

        cursor.close()
        conn.close()
        print("[OK] Database initialization complete!")

    except Error as e:
        print(f"[ERROR] Database initialization failed: {e}")
        sys.exit(1)


def insert_default_data(cursor, conn):
    """Insert default roles, admin, doctor, and nurse accounts if they don't exist."""
    # 1. Seed Roles
    roles = [
        ('admin', 'System Administrator', 'Full administrative access'),
        ('doctor', 'Attending Physician', 'Clinical decision and patient diagnosis'),
        ('nurse', 'Staff Nurse', 'Vitals logging and patient monitoring'),
        ('attendant', 'Patient Attendant', 'Restricted patient view access')
    ]
    for name, display, desc in roles:
        cursor.execute("SELECT role_id FROM roles WHERE name = %s", (name,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO roles (name, display_name, description) VALUES (%s, %s, %s)",
                (name, display, desc)
            )

    # 2. Seed Default Admin
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        pw_hash = hash_pw('admin123')
        cursor.execute(
            """INSERT INTO users (username, password_hash, full_name, email, role, department)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('admin', pw_hash, 'System Administrator', 'admin@jeevansetu.com', 'admin', 'Administration')
        )
        print("[OK] Default admin user created (username: admin, password: admin123)")

    # 3. Seed Default Doctor
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'doctor'")
    if cursor.fetchone()[0] == 0:
        doc_hash = hash_pw('doctor123')
        cursor.execute(
            """INSERT INTO users (username, password_hash, full_name, email, role, department)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('doctor', doc_hash, 'Dr. Rajesh Sharma', 'dr.rajesh@jeevansetu.com', 'doctor', 'Critical Care')
        )
        print("[OK] Default doctor user created (username: doctor, password: doctor123)")

    # 4. Seed Default Nurse
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'nurse'")
    if cursor.fetchone()[0] == 0:
        nurse_hash = hash_pw('nurse123')
        cursor.execute(
            """INSERT INTO users (username, password_hash, full_name, email, role, department)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('nurse', nurse_hash, 'Nurse Priya Singh', 'priya.nurse@jeevansetu.com', 'nurse', 'ICU Ward 1')
        )
        print("[OK] Default nurse user created (username: nurse, password: nurse123)")

    # 5. Seed Default Wards
    wards = [
        ('ICU Ward 1', 'ICU', 1, 10, 'Main Intensive Care Unit'),
        ('HDU Ward 1', 'HDU', 1, 10, 'High Dependency Unit 1'),
        ('General Ward 1', 'General', 2, 20, 'General Medicine Ward')
    ]
    for w_name, w_type, floor, beds_count, desc in wards:
        cursor.execute("SELECT ward_id FROM wards WHERE name = %s", (w_name,))
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO wards (name, ward_type, floor_number, total_beds, description)
                   VALUES (%s, %s, %s, %s, %s)""",
                (w_name, w_type, floor, beds_count, desc)
            )

    # 6. Seed Default Beds
    cursor.execute("SELECT ward_id, ward_type FROM wards WHERE ward_type = 'ICU' LIMIT 1")
    icu_row = cursor.fetchone()
    if icu_row:
        icu_id = icu_row[0]
        for b_num in ['ICU-01', 'ICU-02', 'ICU-03', 'ICU-04', 'ICU-05']:
            cursor.execute("SELECT bed_id FROM beds WHERE ward_id = %s AND bed_number = %s", (icu_id, b_num))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO beds (ward_id, bed_number, status) VALUES (%s, %s, 'occupied')", (icu_id, b_num))

    cursor.execute("SELECT ward_id, ward_type FROM wards WHERE ward_type = 'HDU' LIMIT 1")
    hdu_row = cursor.fetchone()
    if hdu_row:
        hdu_id = hdu_row[0]
        for b_num in ['HDU-01', 'HDU-02', 'HDU-03', 'HDU-04', 'HDU-05']:
            cursor.execute("SELECT bed_id FROM beds WHERE ward_id = %s AND bed_number = %s", (hdu_id, b_num))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO beds (ward_id, bed_number, status) VALUES (%s, %s, 'available')", (hdu_id, b_num))

    # 7. Initial Patient Check
    cursor.execute("SELECT COUNT(*) FROM patients")
    pt_count = cursor.fetchone()[0]
    print(f"[OK] Patient count in database: {pt_count}")

    conn.commit()


if __name__ == '__main__':
    print("==================================================")
    print("Initializing Jeevan Setu Database (Phase 2)...")
    print("==================================================")
    init_database()
