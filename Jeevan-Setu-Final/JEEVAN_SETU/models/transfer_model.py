"""
models/transfer_model.py — Patient ward and bed transfers management.
"""

from database.db import db
from models.bed_model import Bed
from models.patient_model import Patient
from models.notification_model import Notification
from models.audit_log_model import AuditLog


class Transfer:
    """Patient transfer requests, approvals, and execution."""

    @staticmethod
    def request_transfer(patient_id, from_ward, to_ward, requested_by=None,
                         recommendation_id=None, from_bed_id=None, to_bed_id=None,
                         from_bed_number=None, to_bed_number=None, reason=None):
        """Create a transfer request."""
        # Auto-detect from_ward and from_bed if missing
        patient = Patient.get_by_id(patient_id)
        if patient:
            if not from_ward:
                from_ward = patient.get('ward_type', 'ICU')
            if not from_bed_id and patient.get('bed_id'):
                from_bed_id = patient.get('bed_id')
                from_bed_number = patient.get('bed_number')

        return db.execute_query(
            """INSERT INTO transfers 
               (patient_id, from_ward, to_ward, requested_by, recommendation_id,
                from_bed_id, to_bed_id, from_bed_number, to_bed_number, transfer_reason, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')""",
            (patient_id, from_ward, to_ward, requested_by, recommendation_id,
             from_bed_id, to_bed_id, from_bed_number, to_bed_number, reason)
        )

    @staticmethod
    def approve_transfer(transfer_id, approved_by, to_bed_id=None, to_ward=None, remarks=None):
        """
        Approve and execute patient transfer in an atomic transaction:
        1. Lock transfer and patient records
        2. Concurrency-safe selection and locking of target HDU bed
        3. Release patient's previous ICU bed (status -> 'available')
        4. Mark previous bed allocation as 'transferred' with released_at timestamp
        5. Allocate target HDU bed (status -> 'occupied') and log in bed_management
        6. Update patient ward_type='HDU', ward_id, bed_id, bed_number, status='admitted'
        7. Update transfer status -> 'approved', to_bed_id, to_bed_number, completed_at
        8. Update recommendation if linked -> status='approved'
        9. Acknowledge and resolve pending transfer alerts
        10. Create persistent targeted in-app notification for assigned nurse
        """
        from models.user_model import User
        from models.patient_model import Patient

        transfer = Transfer.get_by_id(transfer_id)
        if not transfer:
            raise ValueError(f"Transfer #{transfer_id} not found")

        if transfer['status'] in ('approved', 'completed'):
            raise ValueError(f"Transfer #{transfer_id} has already been approved")
        if transfer['status'] == 'rejected':
            raise ValueError(f"Transfer #{transfer_id} has been rejected")

        patient_id = transfer['patient_id']
        patient = Patient.get_by_id(patient_id)
        if not patient:
            raise ValueError(f"Patient #{patient_id} not found")

        dest_ward = to_ward or transfer.get('to_ward') or 'HDU'
        target_bed_id = to_bed_id or transfer.get('to_bed_id')

        with db.transaction() as cursor:
            # 1. Concurrency-Safe Target HDU Bed Selection & Row Locking
            target_bed = None
            if target_bed_id:
                cursor.execute("SELECT b.*, w.name as ward_name, w.ward_type FROM beds b JOIN wards w ON b.ward_id = w.ward_id WHERE b.bed_id = %s FOR UPDATE", (target_bed_id,))
                target_bed = cursor.fetchone()
                if not target_bed:
                    raise ValueError(f"Target bed #{target_bed_id} not found")
                if target_bed['status'] == 'occupied':
                    raise ValueError(f"Target bed {target_bed['bed_number']} is already occupied")
            else:
                # Find available HDU bed with row-level locking
                cursor.execute(
                    """SELECT b.*, w.name as ward_name, w.ward_type 
                       FROM beds b
                       JOIN wards w ON b.ward_id = w.ward_id
                       WHERE (w.ward_type = 'HDU' OR w.name LIKE '%HDU%')
                         AND b.status = 'available' AND b.is_active = 1
                       ORDER BY b.bed_id ASC
                       LIMIT 1
                       FOR UPDATE"""
                )
                target_bed = cursor.fetchone()
                if not target_bed:
                    raise ValueError("Transfer approval failed: No available HDU beds found. All HDU beds are currently occupied.")
                target_bed_id = target_bed['bed_id']

            to_bed_num = target_bed['bed_number']
            ward_id_val = target_bed['ward_id']

            # 2. Release Previous ICU Bed
            prev_bed_id = transfer.get('from_bed_id') or patient.get('bed_id')
            if prev_bed_id:
                cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id = %s", (prev_bed_id,))

            cursor.execute(
                """UPDATE bed_management SET status = 'transferred', released_at = NOW() 
                   WHERE patient_id = %s AND status IN ('allocated', 'occupied')""",
                (patient_id,)
            )

            # 3. Allocate and Occupy Selected HDU Bed
            cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id = %s", (target_bed_id,))
            cursor.execute(
                """INSERT INTO bed_management (patient_id, bed_id, ward_id, status, allocated_by, notes)
                   VALUES (%s, %s, %s, 'occupied', %s, %s)""",
                (patient_id, target_bed_id, ward_id_val, approved_by,
                 f"Approved Transfer #{transfer_id}. Remarks: {remarks or 'None'}")
            )

            # 4. Update Patient Record (Location -> HDU, Bed -> new HDU bed)
            cursor.execute(
                """UPDATE patients 
                   SET ward_type = %s, bed_id = %s, bed_number = %s, ward_id = %s, status = 'admitted'
                   WHERE patient_id = %s""",
                (dest_ward, target_bed_id, to_bed_num, ward_id_val, patient_id)
            )

            # 5. Update Transfer Record
            reason_text = transfer.get('transfer_reason') or ''
            if remarks:
                reason_text = f"{reason_text} | Doctor Remarks: {remarks}".strip(' |')

            cursor.execute(
                """UPDATE transfers 
                   SET status = 'approved', approved_by = %s, to_bed_id = %s,
                       to_bed_number = %s, to_ward = %s, transfer_reason = %s, completed_at = NOW()
                   WHERE transfer_id = %s""",
                (approved_by, target_bed_id, to_bed_num, dest_ward, reason_text, transfer_id)
            )

            # 6. Update Recommendation Record if linked
            if transfer.get('recommendation_id'):
                cursor.execute(
                    """UPDATE recommendations 
                       SET status = 'approved', decided_by = %s, decided_at = NOW() 
                       WHERE recommendation_id = %s""",
                    (approved_by, transfer['recommendation_id'])
                )

            # 7. Acknowledge / Deactivate Pending Transfer Alerts for Patient
            cursor.execute(
                """UPDATE alerts 
                   SET is_acknowledged = TRUE, acknowledged_by = %s, acknowledged_at = NOW()
                   WHERE patient_id = %s AND (parameter = 'transfer_pending' OR alert_type = 'TRANSFER') AND is_acknowledged = FALSE""",
                (approved_by, patient_id)
            )

            # 8. Create Targeted Persistent Nurse Notification
            assigned_nurse_id = patient.get('assigned_nurse')
            doctor_user = User.get_by_id(approved_by) if approved_by else None
            doctor_name = getattr(doctor_user, 'full_name', 'Doctor') if doctor_user else 'Attending Doctor'
            patient_name = patient.get('name') or transfer.get('patient_name') or f"Patient #{patient_id}"

            if assigned_nurse_id:
                cursor.execute(
                    """INSERT INTO notifications (user_id, patient_id, type, title, message, is_read, created_at)
                       VALUES (%s, %s, 'transfer', %s, %s, 0, NOW())""",
                    (
                        assigned_nurse_id,
                        patient_id,
                        f"[TRANSFER APPROVED] {patient_name}",
                        f"Dr. {doctor_name} approved the ICU → HDU transfer. The patient is ready to transfer to HDU. Assigned HDU Bed: {to_bed_num}."
                    )
                )

        return {
            'success': True,
            'transfer_id': transfer_id,
            'patient_id': patient_id,
            'patient_name': patient_name,
            'from_bed_id': prev_bed_id,
            'to_bed_id': target_bed_id,
            'to_bed_number': to_bed_num,
            'dest_ward': dest_ward,
            'status': 'approved'
        }

    @staticmethod
    def reject_transfer(transfer_id, rejected_by, remarks=None):
        """Reject a pending transfer request with doctor remarks."""
        transfer = Transfer.get_by_id(transfer_id)
        if not transfer:
            raise ValueError(f"Transfer #{transfer_id} not found")

        if transfer['status'] != 'pending':
            raise ValueError(f"Transfer #{transfer_id} is already {transfer['status']}")

        reason_text = transfer.get('transfer_reason') or ''
        if remarks:
            reason_text = f"{reason_text} | Rejection Remarks: {remarks}".strip(' |')

        with db.transaction() as cursor:
            cursor.execute(
                """UPDATE transfers 
                   SET status = 'rejected', approved_by = %s, transfer_reason = %s, completed_at = NOW()
                   WHERE transfer_id = %s""",
                (rejected_by, reason_text, transfer_id)
            )

            if transfer.get('recommendation_id'):
                cursor.execute(
                    """UPDATE recommendations 
                       SET status = 'rejected', decided_by = %s, decided_at = NOW() 
                       WHERE recommendation_id = %s""",
                    (rejected_by, transfer['recommendation_id'])
                )

        # Notification
        try:
            patient_name = transfer.get('patient_name') or f"Patient #{transfer['patient_id']}"
            Notification.broadcast_to_role(
                role='nurse',
                title='Patient Transfer Rejected',
                message=f"Transfer #{transfer_id} for {patient_name} to {transfer['to_ward']} was rejected. Reason: {remarks or 'None'}",
                notif_type='transfer',
                patient_id=transfer['patient_id']
            )
        except Exception:
            pass

        return True

    @staticmethod
    def get_by_id(transfer_id):
        """Fetch transfer details with patient and user info."""
        result = db.execute_query(
            """SELECT t.*, p.name AS patient_name, p.patient_code, p.diagnosis,
                      u1.full_name AS requester_name, u2.full_name AS approver_name
               FROM transfers t
               JOIN patients p ON t.patient_id = p.patient_id
               LEFT JOIN users u1 ON t.requested_by = u1.user_id
               LEFT JOIN users u2 ON t.approved_by = u2.user_id
               WHERE t.transfer_id = %s""",
            (transfer_id,), fetch=True
        )
        return result[0] if result else None

    @staticmethod
    def get_all(status=None, limit=100):
        """Fetch all transfers with optional status filter."""
        if status:
            return db.execute_query(
                """SELECT t.*, p.name AS patient_name, p.patient_code, p.diagnosis,
                          u1.full_name AS requester_name, u2.full_name AS approver_name
                   FROM transfers t
                   JOIN patients p ON t.patient_id = p.patient_id
                   LEFT JOIN users u1 ON t.requested_by = u1.user_id
                   LEFT JOIN users u2 ON t.approved_by = u2.user_id
                   WHERE t.status = %s
                   ORDER BY t.created_at DESC LIMIT %s""",
                (status, limit), fetch=True
            ) or []

        return db.execute_query(
            """SELECT t.*, p.name AS patient_name, p.patient_code, p.diagnosis,
                      u1.full_name AS requester_name, u2.full_name AS approver_name
               FROM transfers t
               JOIN patients p ON t.patient_id = p.patient_id
               LEFT JOIN users u1 ON t.requested_by = u1.user_id
               LEFT JOIN users u2 ON t.approved_by = u2.user_id
               ORDER BY t.created_at DESC LIMIT %s""",
            (limit,), fetch=True
        ) or []

    @staticmethod
    def get_by_patient(patient_id):
        """Fetch all transfer records for a specific patient."""
        return db.execute_query(
            """SELECT t.*, p.name AS patient_name, p.patient_code,
                      u1.full_name AS requester_name, u2.full_name AS approver_name
               FROM transfers t
               JOIN patients p ON t.patient_id = p.patient_id
               LEFT JOIN users u1 ON t.requested_by = u1.user_id
               LEFT JOIN users u2 ON t.approved_by = u2.user_id
               WHERE t.patient_id = %s
               ORDER BY t.created_at DESC""",
            (patient_id,), fetch=True
        ) or []
