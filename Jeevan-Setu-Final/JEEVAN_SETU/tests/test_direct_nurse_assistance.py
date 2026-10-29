"""
tests/test_direct_nurse_assistance.py — End-to-End Verification Test Suite
for Direct Nurse Notification on Attendant Request Assistance (No Popup / No Modal).

Covers all requirements from the Master Prompt:
1. Direct assistance request without popup or manual category/notes entry.
2. Server-side resolution of patient's assigned nurse (patients.assigned_nurse).
3. Persistent assistance request record in attendant_assistance_requests.
4. Notification specifically routed to assigned nurse in notifications table.
5. In-app notification visibility for assigned nurse and strict exclusion for unassigned nurses.
6. Attendant feedback messages (success, no nurse assigned, failure).
7. Non-emergency safety notice permanently retained in UI.
8. Duplicate request throttling / deduplication without duplicate notifications.
9. Security & RBAC: unauthenticated rejection (401), IDOR isolation.
10. Baseline patient census preservation (10 patients).
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
from models.notification_model import Notification
from routes.attendant_routes import generate_attendant_session_token
from services.auth_service import AuthService


class TestDirectNurseAssistance(unittest.TestCase):
    """Automated verification suite for direct nurse assistance workflow."""

    @classmethod
    def setUpClass(cls):
        """Set up test client, staff tokens, and attendant test sessions."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Verify baseline census of 10 patients
        patients = db.execute_query(
            "SELECT patient_id, name, patient_code, assigned_nurse, assigned_doctor FROM patients ORDER BY patient_id ASC",
            fetch=True
        ) or []
        assert len(patients) == 10, f"Expected 10 baseline patients, found {len(patients)}"
        cls.patients = patients
        cls.patient1 = patients[0]  # e.g. Rajesh Kumar, assigned_nurse = 5 (Priya Sharma)
        cls.patient1_id = cls.patient1['patient_id']
        cls.assigned_nurse_id = cls.patient1['assigned_nurse']

        # Ensure patient1 has an assigned nurse
        assert cls.assigned_nurse_id is not None, f"Patient 1 must have an assigned nurse for tests"

        # Retrieve assigned nurse details
        assigned_nurse_row = db.execute_query(
            "SELECT user_id, username, full_name, role FROM users WHERE user_id = %s",
            (cls.assigned_nurse_id,),
            fetch=True
        )
        assert len(assigned_nurse_row) > 0, f"Assigned nurse user {cls.assigned_nurse_id} not found"
        cls.assigned_nurse_user = User.get_by_id(cls.assigned_nurse_id)
        cls.assigned_nurse_token = AuthService.generate_access_token(cls.assigned_nurse_user)['access_token']
        cls.assigned_nurse_headers = {'Authorization': f"Bearer {cls.assigned_nurse_token}"}

        # Find an unassigned nurse (a nurse NOT assigned to patient 1)
        unassigned_nurse_row = db.execute_query(
            "SELECT user_id, username, full_name, role FROM users WHERE role = 'nurse' AND user_id != %s LIMIT 1",
            (cls.assigned_nurse_id,),
            fetch=True
        )
        if unassigned_nurse_row:
            cls.unassigned_nurse_id = unassigned_nurse_row[0]['user_id']
            cls.unassigned_nurse_user = User.get_by_id(cls.unassigned_nurse_id)
        else:
            ts = int(datetime.now().timestamp())
            uid = User.create(
                username=f"nurse_unassigned_{ts}",
                password="TestPassword123!",
                full_name="Nurse Unassigned Test",
                email=f"nurse_unassigned_{ts}@hospital.com",
                role='nurse',
                department='HDU'
            )
            cls.unassigned_nurse_id = uid
            cls.unassigned_nurse_user = User.get_by_id(uid)

        cls.unassigned_nurse_token = AuthService.generate_access_token(cls.unassigned_nurse_user)['access_token']
        cls.unassigned_nurse_headers = {'Authorization': f"Bearer {cls.unassigned_nurse_token}"}

        # Create Attendant Session for Patient 1
        cls.attendant1_name = "Sunita Kumar"
        cls.att1_session = generate_attendant_session_token(
            patient_id=cls.patient1_id,
            attendant_name=cls.attendant1_name,
            token_hash="test-direct-attendant-p1",
            expires_hours=2
        )
        cls.att1_token = cls.att1_session['access_token']
        cls.att1_headers = {'Authorization': f"Bearer {cls.att1_token}"}

        # Find or create a patient with NO assigned nurse for negative testing
        p_no_nurse = db.execute_query(
            "SELECT patient_id, name FROM patients WHERE assigned_nurse IS NULL LIMIT 1",
            fetch=True
        )
        if p_no_nurse:
            cls.patient_no_nurse_id = p_no_nurse[0]['patient_id']
            cls.created_temp_patient = False
        else:
            # Create a temporary test patient with assigned_nurse = None
            res = db.execute_query(
                """INSERT INTO patients (patient_code, name, age, gender, ward_type, bed_number, status, assigned_nurse)
                   VALUES ('TEMP-NO-NURSE-01', 'Temp Test Patient', 45, 'Male', 'ICU', 'ICU-99', 'Admitted', NULL)""",
                fetch=False
            )
            cls.patient_no_nurse_id = res['lastrowid'] if isinstance(res, dict) and 'lastrowid' in res else None
            if not cls.patient_no_nurse_id:
                row = db.execute_query("SELECT patient_id FROM patients WHERE patient_code = 'TEMP-NO-NURSE-01'", fetch=True)
                cls.patient_no_nurse_id = row[0]['patient_id']
            cls.created_temp_patient = True

        cls.att_no_nurse_session = generate_attendant_session_token(
            patient_id=cls.patient_no_nurse_id,
            attendant_name="Attendant No Nurse",
            token_hash="test-no-nurse-hash",
            expires_hours=2
        )
        cls.att_no_nurse_headers = {'Authorization': f"Bearer {cls.att_no_nurse_session['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        """Clean up test artifacts while preserving 10 baseline patients."""
        if hasattr(cls, 'created_temp_patient') and cls.created_temp_patient:
            db.execute_query("DELETE FROM attendant_assistance_requests WHERE patient_id = %s", (cls.patient_no_nurse_id,))
            db.execute_query("DELETE FROM notifications WHERE patient_id = %s", (cls.patient_no_nurse_id,))
            db.execute_query("DELETE FROM patients WHERE patient_id = %s", (cls.patient_no_nurse_id,))

        # Verify census remains 10
        patients = db.execute_query("SELECT patient_id FROM patients ORDER BY patient_id ASC", fetch=True) or []
        assert len(patients) == 10, f"Expected 10 baseline patients after test cleanup, found {len(patients)}"

    def test_01_single_tap_assistance_request_success(self):
        """Test single-tap assistance request without popup inputs: resolves nurse, creates request & notification."""
        # Clean recent requests for patient 1 to avoid duplicate window
        db.execute_query("DELETE FROM attendant_assistance_requests WHERE patient_id = %s", (self.patient1_id,))
        db.execute_query("DELETE FROM notifications WHERE patient_id = %s", (self.patient1_id,))

        # Single tap sends minimal/empty payload
        response = self.client.post(
            '/api/v1/attendant/assistance-requests',
            json={},
            headers=self.att1_headers
        )
        self.assertIn(response.status_code, [200, 201])
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('request', data)
        req = data['request']
        self.assertEqual(req['patient_id'], self.patient1_id)
        self.assertEqual(req['assigned_nurse_id'], self.assigned_nurse_id)
        self.assertEqual(req['category'], 'Request nursing assistance')
        self.assertEqual(req['status'], 'pending')
        self.assertEqual(data.get('assigned_nurse_name'), self.assigned_nurse_user.full_name)

    def test_02_database_persistence_of_assistance_request(self):
        """Verify the request is persistently saved in attendant_assistance_requests with correct columns."""
        rows = db.execute_query(
            """SELECT request_id, patient_id, attendant_name, category, status, assigned_nurse_id, created_at 
               FROM attendant_assistance_requests 
               WHERE patient_id = %s 
               ORDER BY request_id DESC LIMIT 1""",
            (self.patient1_id,),
            fetch=True
        )
        self.assertTrue(len(rows) > 0, "Persistent record not found in attendant_assistance_requests")
        r = rows[0]
        self.assertEqual(r['patient_id'], self.patient1_id)
        self.assertEqual(r['assigned_nurse_id'], self.assigned_nurse_id)
        self.assertEqual(r['category'], 'Request nursing assistance')
        self.assertEqual(r['status'], 'pending')
        self.assertEqual(r['attendant_name'], self.attendant1_name)

    def test_03_notification_created_specifically_for_assigned_nurse(self):
        """Verify notification is created in notifications table specifically for user_id = assigned_nurse_id."""
        notifs = db.execute_query(
            """SELECT notification_id, user_id, patient_id, type, title, message 
               FROM notifications 
               WHERE patient_id = %s 
               ORDER BY notification_id DESC LIMIT 1""",
            (self.patient1_id,),
            fetch=True
        )
        self.assertTrue(len(notifs) > 0, "Notification record not found in notifications table")
        n = notifs[0]
        self.assertEqual(n['user_id'], self.assigned_nurse_id, "Notification user_id must match assigned_nurse_id")
        self.assertEqual(n['patient_id'], self.patient1_id)
        self.assertIn('ASSISTANCE', n['title'].upper())

    def test_04_in_app_notification_visibility_assigned_vs_unassigned(self):
        """Assigned nurse receives notification in API; unassigned nurse does NOT."""
        # 1. Assigned nurse calls /api/v1/notifications
        res_assigned = self.client.get('/api/v1/notifications', headers=self.assigned_nurse_headers)
        self.assertEqual(res_assigned.status_code, 200)
        data_assigned = res_assigned.get_json()
        assigned_notifs = data_assigned.get('notifications') or data_assigned.get('data') or []
        # Check that there is at least one notification for patient1
        p1_notifs = [x for x in assigned_notifs if x.get('patient_id') == self.patient1_id]
        self.assertTrue(len(p1_notifs) > 0, "Assigned nurse must see notification for patient 1")

        # 2. Unassigned nurse calls /api/v1/notifications
        res_unassigned = self.client.get('/api/v1/notifications', headers=self.unassigned_nurse_headers)
        self.assertEqual(res_unassigned.status_code, 200)
        data_unassigned = res_unassigned.get_json()
        unassigned_notifs = data_unassigned.get('notifications') or data_unassigned.get('data') or []
        # Check that unassigned nurse does NOT see notifications for patient 1
        p1_unassigned_notifs = [x for x in unassigned_notifs if x.get('patient_id') == self.patient1_id]
        self.assertEqual(len(p1_unassigned_notifs), 0, "Unassigned nurse must NOT see notifications for patient 1")

    def test_05_staff_assistance_requests_scoping(self):
        """Assigned nurse sees the assistance request in /api/v1/assistance-requests; unassigned nurse does not."""
        # Assigned nurse
        res_assigned = self.client.get('/api/v1/assistance-requests', headers=self.assigned_nurse_headers)
        self.assertEqual(res_assigned.status_code, 200)
        reqs_assigned = res_assigned.get_json().get('requests', [])
        p1_reqs = [r for r in reqs_assigned if r.get('patient_id') == self.patient1_id]
        self.assertTrue(len(p1_reqs) > 0, "Assigned nurse must see assistance request for patient 1")

        # Unassigned nurse
        res_unassigned = self.client.get('/api/v1/assistance-requests', headers=self.unassigned_nurse_headers)
        self.assertEqual(res_unassigned.status_code, 200)
        reqs_unassigned = res_unassigned.get_json().get('requests', [])
        p1_reqs_unassigned = [r for r in reqs_unassigned if r.get('patient_id') == self.patient1_id]
        self.assertEqual(len(p1_reqs_unassigned), 0, "Unassigned nurse must NOT see assistance request for patient 1")

    def test_06_duplicate_request_throttling_no_duplicate_notification(self):
        """Immediate second click within 15s is recognized as duplicate and does NOT create a second notification."""
        # Initial count of notifications for patient 1
        count_before = db.execute_query(
            "SELECT COUNT(*) as cnt FROM notifications WHERE patient_id = %s",
            (self.patient1_id,),
            fetch=True
        )[0]['cnt']

        # Second click immediately
        res2 = self.client.post(
            '/api/v1/attendant/assistance-requests',
            json={},
            headers=self.att1_headers
        )
        self.assertIn(res2.status_code, [200, 201])
        data2 = res2.get_json()
        self.assertTrue(data2.get('is_duplicate'), "Second click within 15s should have is_duplicate = True")

        # Count of notifications must remain unchanged (no duplicate notification)
        count_after = db.execute_query(
            "SELECT COUNT(*) as cnt FROM notifications WHERE patient_id = %s",
            (self.patient1_id,),
            fetch=True
        )[0]['cnt']
        self.assertEqual(count_before, count_after, "Duplicate request must not trigger redundant notification")

    def test_07_no_assigned_nurse_returns_clear_actionable_error(self):
        """Attendant requesting assistance for a patient with no assigned nurse receives clear 400 error."""
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            json={},
            headers=self.att_no_nurse_headers
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn("No nurse assignment was found for this patient", data.get('error', ''))

    def test_08_unauthenticated_request_rejected(self):
        """Unauthenticated requests are strictly rejected with 401."""
        res = self.client.post('/api/v1/attendant/assistance-requests', json={})
        self.assertEqual(res.status_code, 401)

    def test_09_patient_confidentiality_and_idor_prevention(self):
        """Attendant cannot forge patient_id; server derives patient from authorized session token."""
        # Try to pass a different patient_id in body
        other_patient_id = self.patients[1]['patient_id']
        res = self.client.post(
            '/api/v1/attendant/assistance-requests',
            json={'patient_id': other_patient_id},
            headers=self.att1_headers
        )
        # Even if 200/201, the patient_id MUST be patient 1 (derived from token), NEVER other_patient_id
        if res.status_code in [200, 201]:
            data = res.get_json()
            self.assertEqual(data['request']['patient_id'], self.patient1_id)
            self.assertNotEqual(data['request']['patient_id'], other_patient_id)

    def test_10_html_template_modal_removed_and_safety_notice_present(self):
        """Verify the HTML template contains no modal popup and retains non-emergency warning."""
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'Jeevan_setu_frontend', 'Attendant', 'patient_update_mobile_view_replica',
            'patient_update_mobile_view_replica.html'
        )
        self.assertTrue(os.path.exists(template_path), f"Template file {template_path} must exist")
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # Modal must NOT exist
        self.assertNotIn('id="request-assistance-modal"', html, "Modal popup element must be removed")
        self.assertNotIn('openRequestAssistanceModal', html, "openRequestAssistanceModal should not be present")
        self.assertNotIn('handleAssistanceRequestSubmit', html, "Old form submit handler should not be present")

        # Direct function must exist
        self.assertIn('requestAssistanceDirect', html, "Direct assistance handler must be present")
        self.assertIn('onclick="requestAssistanceDirect(this)"', html, "Button must call requestAssistanceDirect")

        # Non-emergency notice must be retained
        self.assertIn('For emergencies or immediate danger', html, "Non-emergency safety warning must be present in UI")
        self.assertIn('Non-Emergency Procedure', html, "Safety warning header must be present")

    def test_11_baseline_census_unaltered(self):
        """Verify that the 10 baseline patients remain intact."""
        patients = db.execute_query("SELECT patient_id, patient_code FROM patients ORDER BY patient_id ASC", fetch=True) or []
        # Filter out temporary patient if any
        real_patients = [p for p in patients if not p['patient_code'].startswith('TEMP-')]
        self.assertEqual(len(real_patients), 10, f"Expected exactly 10 baseline patients, found {len(real_patients)}")


if __name__ == '__main__':
    unittest.main()
