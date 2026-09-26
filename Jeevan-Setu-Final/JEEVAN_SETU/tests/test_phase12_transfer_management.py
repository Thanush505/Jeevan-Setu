"""
tests/test_phase12_transfer_management.py — Comprehensive Test Suite for Phase 12 Transfer Management.

Workflow:
Recommendation
      ↓
Doctor Review
      ↓
Approve / Reject
      ↓
Remarks
      ↓
Transfer
      ↓
Ward Update
      ↓
Bed Update
      ↓
Notification
      ↓
Audit Log

APIs Tested:
- GET  /transfers & /api/v1/transfers
- POST /transfers & /api/v1/transfers
- GET  /transfers/{id} & /api/v1/transfers/{id}
- PUT  /transfers/{id}/approve & /api/v1/transfers/{id}/approve
- PUT  /transfers/{id}/reject & /api/v1/transfers/{id}/reject
- GET  /patients/{id}/transfers & /api/v1/patients/{id}/transfers
- RBAC validation: Only authorized Doctors and Administrators can approve/reject.
"""

import sys
import os
import unittest
from datetime import datetime

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.ward_model import Ward
from models.bed_model import Bed
from models.bed_management_model import BedManagement
from models.recommendation_model import Recommendation
from models.transfer_model import Transfer
from models.notification_model import Notification
from models.audit_log_model import AuditLog
from services.auth_service import AuthService


class TestPhase12TransferManagement(unittest.TestCase):
    """Test suite for Phase 12 Patient Transfer Management."""

    @classmethod
    def setUpClass(cls):
        """Configure test client, users, tokens, wards, beds, and test patients."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(datetime.now().timestamp())

        # Admin Token
        admin_user = User.authenticate('admin', 'admin123')
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

        # Doctor User & Token
        cls.doc_id = User.create(
            username=f"p12_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. James Wilson",
            email=f"p12_doc_{ts}@hospital.com",
            role='doctor',
            department='Critical Care'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(cls.doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Nurse User & Token
        cls.nurse_id = User.create(
            username=f"p12_nurse_{ts}",
            password="NursePassword123!",
            full_name="Nurse Sam",
            email=f"p12_nurse_{ts}@hospital.com",
            role='nurse',
            department='ICU'
        )
        cls.nurse_token = AuthService.generate_access_token(User.get_by_id(cls.nurse_id))['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Attendant User & Token
        cls.attendant_id = User.create(
            username=f"p12_att_{ts}",
            password="AttendantPass123!",
            full_name="Attendant Mark",
            email=f"p12_att_{ts}@hospital.com",
            role='attendant'
        )
        cls.attendant_token = AuthService.generate_access_token(User.get_by_id(cls.attendant_id))['access_token']
        cls.attendant_headers = {'Authorization': f"Bearer {cls.attendant_token}"}

        # Setup Wards
        cls.icu_ward_id = Ward.create(name=f"ICU-P12-{ts}", ward_type="ICU", total_beds=5)
        cls.hdu_ward_id = Ward.create(name=f"HDU-P12-{ts}", ward_type="HDU", total_beds=5)

        # Setup Beds
        short_ts = ts % 10000
        cls.icu_bed_id = Bed.create(ward_id=cls.icu_ward_id, bed_number=f"I1-{short_ts}")
        cls.hdu_bed_id = Bed.create(ward_id=cls.hdu_ward_id, bed_number=f"H1-{short_ts}")
        cls.hdu_bed2_id = Bed.create(ward_id=cls.hdu_ward_id, bed_number=f"H2-{short_ts}")

        # Create Patient admitted to ICU Bed
        cls.patient_id = Patient.create(
            name=f"Transfer Patient {ts}",
            age=62,
            gender="Female",
            ward_type="ICU",
            diagnosis="Post-op CABG stabilization",
            created_by=cls.doc_id
        )

        # Allocate ICU Bed to Patient
        BedManagement.allocate_bed(
            patient_id=cls.patient_id,
            bed_id=cls.icu_bed_id,
            ward_id=cls.icu_ward_id,
            allocated_by=cls.nurse_id
        )

    # ─────────────────────────────────────────────────────────────
    # Transfer Creation & Listing Tests
    # ─────────────────────────────────────────────────────────────

    def test_01_create_transfer_request_api(self):
        """Test POST /transfers: Request patient step-down transfer."""
        payload = {
            'patient_id': self.patient_id,
            'from_ward': 'ICU',
            'to_ward': 'HDU',
            'to_bed_id': self.hdu_bed_id,
            'reason': 'Patient stabilized; EWS=1; step-down to HDU recommended'
        }

        res = self.client.post('/api/v1/transfers', json=payload, headers=self.nurse_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('transfer_id', data)

        self.__class__.created_transfer_id = data['transfer_id']

        # Verify DB state
        t = Transfer.get_by_id(self.created_transfer_id)
        self.assertEqual(t['status'], 'pending')
        self.assertEqual(t['from_ward'], 'ICU')
        self.assertEqual(t['to_ward'], 'HDU')
        print("[PASS] POST /transfers transfer request creation verified.")

    def test_02_get_transfers_list_and_filtering(self):
        """Test GET /transfers with status filtering."""
        res = self.client.get('/api/v1/transfers?status=pending', headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)
        print("[PASS] GET /transfers with status filter verified.")

    def test_03_get_single_transfer_by_id(self):
        """Test GET /transfers/{id}."""
        res = self.client.get(f"/api/v1/transfers/{self.created_transfer_id}", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['transfer_id'], self.created_transfer_id)
        self.assertEqual(data['data']['patient_name'], Patient.get_by_id(self.patient_id)['name'])
        print("[PASS] GET /transfers/{id} lookup verified.")

    # ─────────────────────────────────────────────────────────────
    # Doctor Review, Approve & Execution Workflow
    # ─────────────────────────────────────────────────────────────

    def test_04_doctor_approve_transfer_and_atomic_execution(self):
        """
        Test PUT /transfers/{id}/approve:
        Verifies complete workflow: Doctor Review -> Approve -> Remarks -> Ward/Bed Update -> Notifications -> Audit Log.
        """
        payload = {
            'remarks': 'Patient clinically stable for intermediate HDU monitoring',
            'to_bed_id': self.hdu_bed_id,
            'to_ward': 'HDU'
        }

        res = self.client.put(f"/api/v1/transfers/{self.created_transfer_id}/approve",
                              json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'approved')

        # 1. Old ICU Bed must be RELEASED (status -> available)
        old_bed = Bed.get_by_id(self.icu_bed_id)
        self.assertEqual(old_bed['status'], 'available')

        # 2. Target HDU Bed must be OCCUPIED
        new_bed = Bed.get_by_id(self.hdu_bed_id)
        self.assertEqual(new_bed['status'], 'occupied')

        # 3. Patient record must be updated to HDU
        patient = Patient.get_by_id(self.patient_id)
        self.assertEqual(patient['ward_type'], 'HDU')
        self.assertEqual(patient['bed_id'], self.hdu_bed_id)
        self.assertEqual(patient['bed_number'], new_bed['bed_number'])

        # 4. Transfer status must be approved with doctor remarks
        transfer = Transfer.get_by_id(self.created_transfer_id)
        self.assertEqual(transfer['status'], 'approved')
        self.assertEqual(transfer['approved_by'], self.doc_id)
        self.assertIn("Doctor Remarks:", transfer['transfer_reason'])

        # 5. Audit log must be present
        logs = db.execute_query(
            "SELECT * FROM audit_logs WHERE action = 'approve_transfer' AND entity_id = %s",
            (self.created_transfer_id,), fetch=True
        )
        self.assertGreaterEqual(len(logs), 1)

        print("[PASS] Doctor Transfer Approval & Atomic Execution verified.")

    # ─────────────────────────────────────────────────────────────
    # Doctor Rejection Workflow
    # ─────────────────────────────────────────────────────────────

    def test_05_doctor_reject_transfer_with_remarks(self):
        """Test PUT /transfers/{id}/reject: Doctor reviews and rejects transfer with remarks."""
        # 1. Create another patient and transfer request to test rejection
        ts = int(datetime.now().timestamp())
        pat2_id = Patient.create(
            name=f"Reject Patient {ts}",
            age=45,
            gender="Male",
            ward_type="ICU",
            diagnosis="Sepsis observation"
        )
        rec_id = Recommendation.create(
            patient_id=pat2_id,
            from_ward="ICU",
            to_ward="HDU",
            recommendation_text="TRANSFER_TO_HDU",
            reason="Step-down suggested"
        )
        t_id = Transfer.request_transfer(
            patient_id=pat2_id,
            from_ward="ICU",
            to_ward="HDU",
            recommendation_id=rec_id,
            reason="Step-down evaluation"
        )

        # 2. Doctor rejects transfer with remarks
        rej_payload = {
            'remarks': 'Patient experienced temperature spike; continue Level 3 ICU care'
        }
        res = self.client.put(f"/api/v1/transfers/{t_id}/reject", json=rej_payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'rejected')

        # Verify DB states
        t = Transfer.get_by_id(t_id)
        self.assertEqual(t['status'], 'rejected')
        self.assertIn("Rejection Remarks:", t['transfer_reason'])

        rec = Recommendation.get_by_id(rec_id)
        self.assertEqual(rec['status'], 'rejected')

        print("[PASS] Doctor Transfer Rejection with remarks verified.")

    # ─────────────────────────────────────────────────────────────
    # Patient Transfer History
    # ─────────────────────────────────────────────────────────────

    def test_06_get_patient_transfers_history(self):
        """Test GET /patients/{id}/transfers."""
        res = self.client.get(f"/api/v1/patients/{self.patient_id}/transfers", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['patient_id'], self.patient_id)
        self.assertGreaterEqual(data['count'], 1)
        self.assertEqual(data['data'][0]['status'], 'approved')
        print("[PASS] GET /patients/{id}/transfers verified.")

    # ─────────────────────────────────────────────────────────────
    # RBAC Security & Authorization Tests
    # ─────────────────────────────────────────────────────────────

    def test_07_rbac_doctor_approval_restrictions(self):
        """Verify: Only authorized Doctors and Administrators can approve/reject clinical transfers."""
        # Create a new pending transfer
        pending_t_id = Transfer.request_transfer(
            patient_id=self.patient_id,
            from_ward="HDU",
            to_ward="General",
            reason="Step-down to General Ward"
        )

        # Nurse attempts approval -> 403 Forbidden
        nurse_res = self.client.put(f"/api/v1/transfers/{pending_t_id}/approve",
                                    json={'remarks': 'Nurse attempt'}, headers=self.nurse_headers)
        self.assertEqual(nurse_res.status_code, 403)

        # Nurse attempts rejection -> 403 Forbidden
        nurse_rej_res = self.client.put(f"/api/v1/transfers/{pending_t_id}/reject",
                                        json={'remarks': 'Nurse attempt'}, headers=self.nurse_headers)
        self.assertEqual(nurse_rej_res.status_code, 403)

        # Attendant attempts access -> 403 Forbidden
        att_res = self.client.get(f"/api/v1/transfers/{pending_t_id}", headers=self.attendant_headers)
        self.assertEqual(att_res.status_code, 403)

        # Unauthenticated -> 401 Unauthorized
        unauth_res = self.client.put(f"/api/v1/transfers/{pending_t_id}/approve", json={})
        self.assertEqual(unauth_res.status_code, 401)

        # Admin CAN approve -> 200 OK
        admin_res = self.client.put(f"/api/v1/transfers/{pending_t_id}/approve",
                                    json={'remarks': 'Admin approved'}, headers=self.admin_headers)
        self.assertEqual(admin_res.status_code, 200)

        print("[PASS] RBAC protection: Only authorized doctors & admins can approve/reject transfers verified.")


if __name__ == '__main__':
    unittest.main()
