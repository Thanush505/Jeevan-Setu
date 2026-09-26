"""
models/bed_management_model.py — Bed allocation and tracking model with concurrency controls.
"""

from database.db import db


class BedManagement:
    """Bed allocation management and historical tracking."""

    @staticmethod
    def allocate_bed(patient_id, bed_id, ward_id=None, allocated_by=None, notes=None):
        """
        Allocate a bed to a patient and update bed status to occupied inside a transaction.
        Enforces strict rule: A bed CANNOT be assigned to two active patients.
        """
        with db.transaction() as cursor:
            # 1. Lock and fetch target bed
            cursor.execute("SELECT * FROM beds WHERE bed_id = %s FOR UPDATE", (bed_id,))
            bed = cursor.fetchone()
            if not bed:
                raise ValueError(f"Bed with ID {bed_id} does not exist.")

            target_ward_id = ward_id or bed['ward_id']

            # 2. Check maintenance status
            if bed['status'] == 'maintenance':
                raise ValueError(f"Bed {bed['bed_number']} is currently under maintenance and cannot be allocated.")

            # 3. Check if bed is already assigned to another active admitted patient
            cursor.execute(
                """SELECT bm.patient_id, p.name, p.patient_code 
                   FROM bed_management bm
                   JOIN patients p ON bm.patient_id = p.patient_id
                   WHERE bm.bed_id = %s AND bm.status IN ('allocated', 'occupied') 
                     AND p.status = 'admitted' AND bm.patient_id != %s""",
                (bed_id, patient_id)
            )
            existing = cursor.fetchone()
            if existing:
                raise ValueError(
                    f"Bed {bed['bed_number']} is already occupied by active patient '{existing['name']}' ({existing['patient_code']})."
                )

            # 4. Release any previous active bed of THIS patient (for internal bed transfers)
            cursor.execute(
                """SELECT bed_id FROM bed_management 
                   WHERE patient_id = %s AND status IN ('allocated', 'occupied') AND bed_id != %s""",
                (patient_id, bed_id)
            )
            old_allocs = cursor.fetchall()
            for old_a in old_allocs:
                old_bed_id = old_a['bed_id']
                cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id = %s", (old_bed_id,))

            cursor.execute(
                """UPDATE bed_management 
                   SET status = 'transferred', released_at = NOW() 
                   WHERE patient_id = %s AND status IN ('allocated', 'occupied') AND bed_id != %s""",
                (patient_id, bed_id)
            )

            # 5. Insert new allocation
            cursor.execute(
                """INSERT INTO bed_management (patient_id, bed_id, ward_id, status, allocated_by, notes)
                   VALUES (%s, %s, %s, 'occupied', %s, %s)""",
                (patient_id, bed_id, target_ward_id, allocated_by, notes)
            )
            allocation_id = cursor.lastrowid

            # 6. Mark target bed as occupied
            cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id = %s", (bed_id,))

            # 7. Update patient record
            cursor.execute(
                """UPDATE patients 
                   SET bed_id = %s, ward_id = %s, bed_number = %s 
                   WHERE patient_id = %s""",
                (bed_id, target_ward_id, bed['bed_number'], patient_id)
            )

            return allocation_id

    @staticmethod
    def release_bed(patient_id=None, bed_id=None):
        """Release a bed from a patient and reset bed status to available."""
        with db.transaction() as cursor:
            if bed_id and not patient_id:
                cursor.execute(
                    """UPDATE bed_management 
                       SET status = 'released', released_at = NOW() 
                       WHERE bed_id = %s AND status IN ('allocated', 'occupied')""",
                    (bed_id,)
                )
                cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id = %s", (bed_id,))
                cursor.execute("UPDATE patients SET bed_id = NULL, bed_number = NULL WHERE bed_id = %s", (bed_id,))
            elif patient_id:
                if bed_id:
                    cursor.execute(
                        """UPDATE bed_management 
                           SET status = 'released', released_at = NOW() 
                           WHERE patient_id = %s AND bed_id = %s AND status IN ('allocated', 'occupied')""",
                        (patient_id, bed_id)
                    )
                    cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id = %s", (bed_id,))
                else:
                    cursor.execute(
                        """SELECT bed_id FROM bed_management 
                           WHERE patient_id = %s AND status IN ('allocated', 'occupied')""",
                        (patient_id,)
                    )
                    allocations = cursor.fetchall()
                    for alloc in allocations:
                        cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id = %s", (alloc['bed_id'],))
                    cursor.execute(
                        """UPDATE bed_management 
                           SET status = 'released', released_at = NOW() 
                           WHERE patient_id = %s AND status IN ('allocated', 'occupied')""",
                        (patient_id,)
                    )

                cursor.execute("UPDATE patients SET bed_id = NULL, bed_number = NULL WHERE patient_id = %s", (patient_id,))

    @staticmethod
    def get_patient_allocation_history(patient_id):
        """Get complete bed history for a patient."""
        query = """
        SELECT bm.*, b.bed_number, w.name AS ward_name, w.ward_type, u.full_name AS allocated_by_name
        FROM bed_management bm
        JOIN beds b ON bm.bed_id = b.bed_id
        JOIN wards w ON bm.ward_id = w.ward_id
        LEFT JOIN users u ON bm.allocated_by = u.user_id
        WHERE bm.patient_id = %s
        ORDER BY bm.allocated_at DESC
        """
        return db.execute_query(query, (patient_id,), fetch=True)
