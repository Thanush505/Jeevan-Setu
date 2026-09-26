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
        1. Release old bed (status -> available)
        2. Mark previous allocation as transferred
        3. Allocate target bed (status -> occupied)
        4. Update patient ward_type, ward_id, bed_id, bed_number
        5. Update transfer status -> approved / completed
        6. Send in-app notifications
        """
        transfer = Transfer.get_by_id(transfer_id)
        if not transfer:
            raise ValueError(f"Transfer #{transfer_id} not found")

        if transfer['status'] in ('approved', 'completed'):
            raise ValueError(f"Transfer #{transfer_id} has already been approved")
        if transfer['status'] == 'rejected':
            raise ValueError(f"Transfer #{transfer_id} has been rejected")

        patient_id = transfer['patient_id']
        dest_ward = to_ward or transfer['to_ward']
        target_bed_id = to_bed_id or transfer.get('to_bed_id')

        with db.transaction() as cursor:
            # 1. If target bed provided, check availability and allocate
            target_bed = None
            if target_bed_id:
                cursor.execute("SELECT * FROM beds WHERE bed_id = %s FOR UPDATE", (target_bed_id,))
                target_bed = cursor.fetchone()
                if not target_bed:
                    raise ValueError(f"Target bed #{target_bed_id} not found")
                if target_bed['status'] == 'occupied':
                    raise ValueError(f"Target bed {target_bed['bed_number']} is already occupied")

            # 2. Release previous bed if patient has one
            cursor.execute(
                """UPDATE bed_management SET status = 'transferred', released_at = NOW() 
                   WHERE patient_id = %s AND status IN ('allocated', 'occupied')""",
                (patient_id,)
            )
            if transfer.get('from_bed_id'):
                cursor.execute("UPDATE beds SET status = 'available' WHERE bed_id = %s", (transfer['from_bed_id'],))

            # 3. If target bed allocated, update beds & bed_management
            to_bed_num = target_bed['bed_number'] if target_bed else transfer.get('to_bed_number')
            ward_id_val = target_bed['ward_id'] if target_bed else None

            if target_bed:
                cursor.execute("UPDATE beds SET status = 'occupied' WHERE bed_id = %s", (target_bed_id,))
                cursor.execute(
                    """INSERT INTO bed_management (patient_id, bed_id, ward_id, status, allocated_by, notes)
                       VALUES (%s, %s, %s, 'occupied', %s, %s)""",
                    (patient_id, target_bed_id, target_bed['ward_id'], approved_by,
                     f"Approved Transfer #{transfer_id}. Remarks: {remarks or 'None'}")
                )

            # 4. Update Patient record
            cursor.execute(
                """UPDATE patients 
                   SET ward_type = %s, bed_id = %s, bed_number = %s, ward_id = COALESCE(%s, ward_id)
                   WHERE patient_id = %s""",
                (dest_ward, target_bed_id, to_bed_num, ward_id_val, patient_id)
            )

            # 5. Update Transfer record
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

            # 6. Update recommendation if linked
            if transfer.get('recommendation_id'):
                cursor.execute(
                    """UPDATE recommendations 
                       SET status = 'approved', decided_by = %s, decided_at = NOW() 
                       WHERE recommendation_id = %s""",
                    (approved_by, transfer['recommendation_id'])
                )

        # 7. Post-transaction notifications
        try:
            patient_name = transfer.get('patient_name') or f"Patient #{patient_id}"
            Notification.broadcast_to_role(
                role='nurse',
                title='Patient Transfer Approved',
                message=f"{patient_name} transferred from {transfer['from_ward']} to {dest_ward} (Bed: {to_bed_num or 'TBD'}). Remarks: {remarks or 'None'}",
                notif_type='transfer',
                patient_id=patient_id
            )
            Notification.broadcast_to_role(
                role='doctor',
                title='Transfer Executed',
                message=f"Transfer #{transfer_id} for {patient_name} to {dest_ward} approved and executed.",
                notif_type='transfer',
                patient_id=patient_id
            )
        except Exception:
            pass

        return True

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
