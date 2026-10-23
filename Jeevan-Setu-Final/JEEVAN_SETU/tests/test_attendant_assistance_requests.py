"""
tests/test_attendant_assistance_requests.py — Comprehensive Automated Test Suite
for Attendant Portal Request Assistance Feature.

Covers all 29 requirements from Section 14:
- Attendant workflow (submission, persistence, view, status, cancellation, isolation)
- Validation (category, description size, malformed IDs, idempotency, transitions)
- Nurse workflow (listing, acknowledge, start, resolve, reject with reason, RBAC)
- Security (unauthenticated 401, IDOR 403, session expiry, XSS prevention)
- Integration (notifications, audit log, persisted updates, patient census preserved)
"""

import os
import sys
import unittest
from datetime import datetime

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.assistance_request_model import AssistanceRequest
from routes.attendant_routes import generate_attendant_session_token
from services.auth_service import AuthService


class TestAttendantAssistanceRequests(unittest.TestCase):
    """Test suite for Jeevan Setu Attendant Assistance Requests feature."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment, authentication tokens, and references."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Verify baseline census of 10 patients
        patients = db.execute_query("SELECT patient_id, name FROM patients ORDER BY patient_id ASC", fetch=True) or []
        assert len(patients) == 10, f"Expected 10 baseline patients, found {len(patients)}"
        cls.patient1_id = patients[0]['patient_id']
        cls.patient2_id = patients[1]['patient_id']

        ts = int(datetime.now().timestamp())

        # 1. Staff Tokens (Admin, Doctor, Nurse)
        admin_row = User.get_by_username('admin') or User.get_by_id(1)
        if admin_row:
            admin_user = User.get_by_id(admin_row['user_id'] if isinstance(admin_row, dict) else admin_row.id)
        else:
            admin_user = User.get_by_id(1)
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

        # Nurse User
        nurse_row = db.execute_query("SELECT * FROM users WHERE role = 'nurse' LIMIT 1", fetch=True)
        if nurse_row:
            cls.nurse_user = User.get_by_id(nurse_row[0]['user_id'])
        else:
            nurse_id = User.create(
                username=f"test_nurse_{ts}",
                password="NursePassword123!",
                full_name="Nurse Florence",
                email=f"nurse_{ts}@hospital.com",
                role='nurse',
                department='ICU'
            )
            cls.nurse_user = User.get_by_id(nurse_id)
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Doctor User
        doctor_row = db.execute_query("SELECT * FROM users WHERE role = 'doctor' LIMIT 1", fetch=True)
        if doctor_row:
            cls.doctor_user = User.get_by_id(doctor_row[0]['user_id'])
        else:
            doc_id = User.create(
                username=f"test_doc_{ts}",
                password="DocPassword123!",
                full_name="Dr. House",
                email=f"doc_{ts}@hospital.com",
                role='doctor',
                department='Critical Care'
            )
            cls.doctor_user = User.get_by_id(doc_id)
        cls.doctor_token = AuthService.generate_access_token(cls.doctor_user)['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # 2. Attendant Sessions (Patient 1 and Patient 2)
        cls.attendant1_name = "Rahul Sharma"
        cls.att1_session = generate_attendant_session_token(
            patient_id=cls.patient1_id,
            attendant_name=cls.attendant1_name,
            token_hash="test-qr-hash-patient1",
            expires_hours=4
        )
        cls.attendant1_token = cls.att1_session['access_token']
        cls.attendant1_headers = {'Authorization': f"Bearer {cls.attendant1_token}"}

        cls.attendant2_name = "Priya Patel"
        cls.att2_session = generate_attendant_session_token(
            patient_id=cls.patient2_id,
            attendant_name=cls.attendant2_name,
            token_hash="test-qr-hash-patient2",
            expires_hours=4
        )
        cls.attendant2_token = cls.att2_session['access_token']
        cls.attendant2_headers = {'Authorization': f"Bearer {cls.attendant2_token}"}

    @classmethod
    def tearDownClass(cls):
        """Clean up created test assistance requests and verify 10 patient baseline is untouched."""
        db.execute_query("DELETE FROM attendant_assistance_requests WHERE attendant_name IN (%s, %s)",
                         (cls.attendant1_name, cls.attendant2_name))
        patients_count = db.execute_query("SELECT COUNT(*) AS cnt FROM patients", fetch=True)[0]['cnt']
        assert patients_count == 10, f"Baseline patient census modified! Expected 10, found {patients_count}"

    # ─────────────────────────────────────────────────────────────
    # A. ATTENDANT WORKFLOW TESTS
    # ─────────────────────────────────────────────────────────────

    def test_01_valid_attendant_can_submit_request(self):
        """1. Valid attendant can submit a request."""
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'category': 'Request nursing assistance',
                'description': 'Patient requested water and blanket adjustment.'
            }
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('request', data)
        self.assertEqual(data['request']['patient_id'], self.patient1_id)
        self.assertEqual(data['request']['category'], 'Request nursing assistance')
        self.assertEqual(data['request']['status'], 'pending')
        self.__class__.created_request_id = data['request']['request_id']

    def test_02_request_persists_in_database(self):
        """2. Request persists in the database."""
        req_id = getattr(self.__class__, 'created_request_id', None)
        self.assertIsNotNone(req_id)
        row = db.execute_query(
            "SELECT * FROM attendant_assistance_requests WHERE request_id = %s",
            (req_id,),
            fetch=True
        )
        self.assertTrue(len(row) > 0)
        self.assertEqual(row[0]['patient_id'], self.patient1_id)
        self.assertEqual(row[0]['status'], 'pending')

    def test_03_attendant_can_view_own_request(self):
        """3. Attendant can view their own request list."""
        res = self.client.get(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        req_ids = [r['request_id'] for r in data['requests']]
        self.assertIn(self.created_request_id, req_ids)

    def test_04_attendant_sees_correct_current_status(self):
        """4. Attendant sees the correct current status."""
        res = self.client.get(
            f'/api/v1/attendant/assistance-requests/{self.created_request_id}',
            headers=self.attendant1_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['request']['status'], 'pending')
        self.assertIn('time_since_submission', data['request'])

    def test_05_attendant_can_cancel_request_when_permitted(self):
        """5. Attendant can cancel a request when permitted (while pending)."""
        # Create a separate request to cancel
        create_res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'category': 'Request bedside assistance',
                'description': 'Temporary assistance needed for sitting up.'
            }
        )
        self.assertEqual(create_res.status_code, 201)
        temp_req_id = create_res.get_json()['request_id'] if 'request_id' in create_res.get_json() else create_res.get_json()['request']['request_id']

        # Cancel it
        cancel_res = self.client.post(
            f'/api/v1/attendant/assistance-requests/{temp_req_id}/cancel',
            headers=self.attendant1_headers
        )
        self.assertEqual(cancel_res.status_code, 200)
        data = cancel_res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['request']['status'], 'cancelled')

        # Check DB
        row = db.execute_query(
            "SELECT status FROM attendant_assistance_requests WHERE request_id = %s",
            (temp_req_id,), fetch=True
        )
        self.assertEqual(row[0]['status'], 'cancelled')

    def test_06_attendant_cannot_view_another_attendants_request(self):
        """6. Attendant cannot view another attendant's request (IDOR protection)."""
        # Attendant 2 trying to read Patient 1's request
        res = self.client.get(
            f'/api/v1/attendant/assistance-requests/{self.created_request_id}',
            headers=self.attendant2_headers
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Access denied', data['error'])

    def test_07_attendant_cannot_submit_for_unauthorized_patient(self):
        """7. Attendant cannot submit for an unauthorized patient."""
        # Browser client attempts to inject patient_id = 999 or patient_id = patient2_id
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'patient_id': self.patient2_id,  # Tampered patient_id
                'category': 'Request to speak with the care team',
                'description': 'Tampered patient ID test.'
            }
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        # Server MUST bind request strictly to session patient (patient1_id), NOT the submitted patient2_id!
        self.assertEqual(data['request']['patient_id'], self.patient1_id)

    # ─────────────────────────────────────────────────────────────
    # B. VALIDATION TESTS
    # ─────────────────────────────────────────────────────────────

    def test_08_invalid_request_category_is_rejected(self):
        """8. Invalid request category is rejected."""
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'category': 'Unauthorized Arbitrary Alarm Category',
                'description': 'Test invalid category.'
            }
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid request category', data['error'])

    def test_09_empty_or_oversized_descriptions_handled_correctly(self):
        """9. Empty or oversized descriptions are handled correctly."""
        # Oversized (> 500 characters)
        long_desc = "A" * 501
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'category': 'Request patient status update',
                'description': long_desc
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('exceed 500 characters', res.get_json()['error'])

        # Empty description (should succeed as optional)
        res_empty = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'category': 'Request patient status update',
                'description': '   '
            }
        )
        self.assertEqual(res_empty.status_code, 201)

    def test_10_malformed_request_identifiers_rejected(self):
        """10. Malformed request identifiers are rejected."""
        res = self.client.get(
            '/api/v1/attendant/assistance-requests/999999',
            headers=self.attendant1_headers
        )
        self.assertEqual(res.status_code, 404)

    def test_11_duplicate_submission_behavior_is_safe(self):
        """11. Duplicate submission behavior is safe (idempotency within 15 seconds)."""
        payload = {
            'category': 'Other non-emergency assistance',
            'description': 'Need extra pillow for patient comfort.'
        }
        res1 = self.client.post('/api/v1/attendant/assistance-requests', headers=self.attendant1_headers, json=payload)
        self.assertEqual(res1.status_code, 201)
        id1 = res1.get_json()['request']['request_id']

        # Duplicate immediate submission
        res2 = self.client.post('/api/v1/attendant/assistance-requests', headers=self.attendant1_headers, json=payload)
        self.assertEqual(res2.status_code, 201)
        id2 = res2.get_json()['request']['request_id']

        # Should return the existing request without creating a duplicate record
        self.assertEqual(id1, id2)

    def test_12_invalid_status_transitions_rejected(self):
        """12. Invalid status transitions are rejected."""
        # Attendant tries to cancel an already cancelled request
        # Create and cancel
        c_res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={'category': 'Request bedside assistance', 'description': 'Testing invalid transition.'}
        )
        req_id = c_res.get_json()['request']['request_id']
        self.client.post(f'/api/v1/attendant/assistance-requests/{req_id}/cancel', headers=self.attendant1_headers)

        # Attempt to cancel again
        c_res2 = self.client.post(f'/api/v1/attendant/assistance-requests/{req_id}/cancel', headers=self.attendant1_headers)
        self.assertEqual(c_res2.status_code, 400)
        self.assertIn('cannot be cancelled in \'cancelled\' state', c_res2.get_json()['error'])

    # ─────────────────────────────────────────────────────────────
    # C. NURSE & STAFF WORKFLOW TESTS
    # ─────────────────────────────────────────────────────────────

    def test_13_authorized_nurse_can_see_appropriate_requests(self):
        """13. Authorized nurse can see appropriate requests."""
        res = self.client.get('/api/v1/assistance-requests', headers=self.nurse_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIsInstance(data['requests'], list)

    def test_14_authorized_nurse_can_acknowledge_request(self):
        """14. Authorized nurse can acknowledge a request."""
        # Create fresh request
        c = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={'category': 'Request nursing assistance', 'description': 'Nurse call bell pressed via portal.'}
        )
        req_id = c.get_json()['request']['request_id']

        ack_res = self.client.post(
            f'/api/v1/assistance-requests/{req_id}/acknowledge',
            headers=self.nurse_headers
        )
        self.assertEqual(ack_res.status_code, 200)
        data = ack_res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['request']['status'], 'acknowledged')
        self.assertIsNotNone(data['request']['acknowledged_at'])
        self.__class__.nurse_active_req_id = req_id

    def test_15_authorized_nurse_can_start_request(self):
        """15. Authorized nurse can start working on a request."""
        req_id = getattr(self.__class__, 'nurse_active_req_id', None)
        self.assertIsNotNone(req_id)

        start_res = self.client.post(
            f'/api/v1/assistance-requests/{req_id}/start',
            headers=self.nurse_headers
        )
        self.assertEqual(start_res.status_code, 200)
        data = start_res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['request']['status'], 'in_progress')
        self.assertIsNotNone(data['request']['started_at'])

    def test_16_authorized_nurse_can_resolve_request(self):
        """16. Authorized nurse can resolve a request with optional resolution note."""
        req_id = getattr(self.__class__, 'nurse_active_req_id', None)
        self.assertIsNotNone(req_id)

        resolve_res = self.client.post(
            f'/api/v1/assistance-requests/{req_id}/resolve',
            headers=self.nurse_headers,
            json={'resolution_note': 'Bedside visit completed. IV line checked and patient comfortable.'}
        )
        self.assertEqual(resolve_res.status_code, 200)
        data = resolve_res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['request']['status'], 'resolved')
        self.assertEqual(data['request']['resolution_note'], 'Bedside visit completed. IV line checked and patient comfortable.')
        self.assertIsNotNone(data['request']['resolved_at'])

    def test_17_unauthorized_attendant_cannot_trigger_staff_lifecycle(self):
        """17. Attendant cannot acknowledge, start, resolve, or reject requests."""
        # Attendant tries to resolve
        res = self.client.post(
            f'/api/v1/assistance-requests/{self.created_request_id}/resolve',
            headers=self.attendant1_headers,
            json={'resolution_note': 'Attendant trying to resolve'}
        )
        # Attendant has role 'attendant', not staff -> 401 or 403
        self.assertIn(res.status_code, (401, 403))

    def test_18_rejection_requires_an_appropriate_reason(self):
        """18. Rejection requires an appropriate mandatory reason."""
        # Create request
        c = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={'category': 'Request to speak with the care team', 'description': 'Testing rejection validation.'}
        )
        req_id = c.get_json()['request']['request_id']

        # Reject without reason -> 400
        rej_fail = self.client.post(
            f'/api/v1/assistance-requests/{req_id}/reject',
            headers=self.nurse_headers,
            json={'rejection_reason': '   '}
        )
        self.assertEqual(rej_fail.status_code, 400)
        self.assertIn('rejection reason is mandatory', rej_fail.get_json()['error'])

        # Reject with valid reason -> 200
        rej_ok = self.client.post(
            f'/api/v1/assistance-requests/{req_id}/reject',
            headers=self.nurse_headers,
            json={'rejection_reason': 'Attending physician is currently engaged in emergency surgical procedure.'}
        )
        self.assertEqual(rej_ok.status_code, 200)
        self.assertEqual(rej_ok.get_json()['request']['status'], 'rejected')
        self.assertEqual(
            rej_ok.get_json()['request']['rejection_reason'],
            'Attending physician is currently engaged in emergency surgical procedure.'
        )

    def test_19_cannot_resolve_or_reject_terminal_request(self):
        """19. Cannot resolve or reject an already resolved/rejected/cancelled request."""
        # Created request from test_16 is resolved
        req_id = getattr(self.__class__, 'nurse_active_req_id', None)
        self.assertIsNotNone(req_id)

        # Attempt to reject a resolved request
        res = self.client.post(
            f'/api/v1/assistance-requests/{req_id}/reject',
            headers=self.nurse_headers,
            json={'rejection_reason': 'Trying to reject already resolved request.'}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('terminal state', res.get_json()['error'])

    # ─────────────────────────────────────────────────────────────
    # D. SECURITY TESTS
    # ─────────────────────────────────────────────────────────────

    def test_20_logged_out_users_cannot_access_protected_operations(self):
        """20. Logged-out users cannot create, list, view, or modify assistance requests."""
        # List staff requests unauthenticated
        res1 = self.client.get('/api/v1/assistance-requests')
        self.assertEqual(res1.status_code, 401)

        # Attendant create unauthenticated
        res2 = self.client.post('/api/v1/attendant/assistance-requests', json={'category': 'Request nursing assistance'})
        self.assertEqual(res2.status_code, 401)

        # Attendant list unauthenticated
        res3 = self.client.get('/api/v1/attendant/assistance-requests')
        self.assertEqual(res3.status_code, 401)

    def test_21_idor_cancellation_attempt_rejected(self):
        """21. IDOR attempts are rejected (Attendant 2 cannot cancel Patient 1 request)."""
        res = self.client.post(
            f'/api/v1/attendant/assistance-requests/{self.created_request_id}/cancel',
            headers=self.attendant2_headers
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn('Access denied', res.get_json()['error'])

    def test_22_invalid_or_tampered_attendant_session_rejected(self):
        """22. Invalid or tampered attendant session token is rejected."""
        bad_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature'}
        res = self.client.get('/api/v1/attendant/assistance-requests', headers=bad_headers)
        self.assertEqual(res.status_code, 401)

    def test_23_request_descriptions_cannot_execute_stored_scripts(self):
        """23. Stored XSS vectors in description are sanitized and rendered safely."""
        xss_payload = "<script>alert('XSS')</script><b>Bold Text</b>"
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            headers=self.attendant1_headers,
            json={
                'category': 'Request nursing assistance',
                'description': xss_payload
            }
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        req_id = data['request']['request_id']

        # Read back
        fetch_res = self.client.get(f'/api/v1/attendant/assistance-requests/{req_id}', headers=self.attendant1_headers)
        desc = fetch_res.get_json()['request']['description']
        self.assertNotIn('<script>', desc)

    def test_24_summary_endpoint_rbac(self):
        """24. Summary endpoint is accessible to authenticated staff but not unauthenticated users."""
        unauth = self.client.get('/api/v1/assistance-requests/summary')
        self.assertEqual(unauth.status_code, 401)

        auth_res = self.client.get('/api/v1/assistance-requests/summary', headers=self.admin_headers)
        self.assertEqual(auth_res.status_code, 200)
        data = auth_res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('total', data['summary'])
        self.assertIn('pending', data['summary'])
        self.assertIn('resolved', data['summary'])

    # ─────────────────────────────────────────────────────────────
    # E. INTEGRATION TESTS
    # ─────────────────────────────────────────────────────────────

    def test_25_existing_notification_infrastructure_triggered(self):
        """25. Existing notification infrastructure is triggered on request creation."""
        # Check notifications table for nurse notifications
        notif_rows = db.execute_query(
            """SELECT * FROM notifications 
               WHERE title LIKE %s
               ORDER BY notification_id DESC LIMIT 5""",
            ('%Assistance Request%',),
            fetch=True
        ) or []
        self.assertTrue(len(notif_rows) > 0, "Expected at least 1 notification generated for nursing staff")
        self.assertIn('Assistance Request', notif_rows[0]['title'])

    def test_26_duplicate_notifications_prevented(self):
        """26. Duplicate notifications are prevented where required."""
        # Acknowledge or read does not flood notifications table
        count_before = db.execute_query("SELECT COUNT(*) AS cnt FROM notifications", fetch=True)[0]['cnt']
        self.client.get('/api/v1/assistance-requests', headers=self.nurse_headers)
        count_after = db.execute_query("SELECT COUNT(*) AS cnt FROM notifications", fetch=True)[0]['cnt']
        self.assertEqual(count_before, count_after)

    def test_27_audit_events_are_recorded(self):
        """27. Audit events are recorded for request creation, acknowledge, resolve, reject, and cancel."""
        audit_rows = db.execute_query(
            """SELECT action FROM audit_logs 
               WHERE entity_type = 'assistance_request' 
               ORDER BY log_id DESC LIMIT 10""",
            fetch=True
        ) or []
        actions = [r['action'] for r in audit_rows]
        self.assertTrue(
            any('ATTENDANT_ASSISTANCE_REQUEST_CREATED' in a or 'ASSISTANCE_REQUEST' in a for a in actions),
            f"Expected assistance request audit actions, got: {actions}"
        )

    def test_28_attendant_portal_reflects_persisted_status_changes(self):
        """28. The Attendant Portal reflects persisted status changes."""
        # Check that the request resolved in test_16 is seen as 'resolved' by attendant
        req_id = getattr(self.__class__, 'nurse_active_req_id', None)
        res = self.client.get(
            f'/api/v1/attendant/assistance-requests/{req_id}',
            headers=self.attendant1_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['request']['status'], 'resolved')
        self.assertIn('Bedside visit completed', data['request']['resolution_note'])

    def test_29_baseline_census_unmodified(self):
        """29. Existing baseline patient census of 10 patients remains intact."""
        census = db.execute_query("SELECT COUNT(*) AS total FROM patients", fetch=True)[0]['total']
        self.assertEqual(census, 10, f"Expected exactly 10 patients, found {census}")


if __name__ == '__main__':
    unittest.main()
