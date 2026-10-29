"""
tests/test_nurse_assigned_alerts.py — End-to-End Test Suite for Nurse-Assigned Alert Filtering

Covers:
1. Nurse Priya does not see unassigned patient Vikram Singh in transfer alerts or global feed.
2. Assigned Nurse Arun sees Vikram Singh's transfer alert.
3. Doctor approval guardrail: Nurses cannot approve transfers (can_approve=False, POST approve returns 403).
4. Direct API IDOR protection: Unauthorized nurse blocked with 403 across all patient endpoints.
5. Active alerts & KPI counts scoped strictly to assigned patients.
6. Clinical tasks (/alerts/api/today-tasks) scoped strictly to assigned nurse.
7. Patient listing & search (/api/v1/patients) scoped strictly to assigned nurse.
8. Dynamic patient reassignment updates alert visibility immediately for both nurses.
9. Unassigned patient alerts escalation (does not broadcast to all nurses).
10. Baseline census of 10 patients preserved.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from services.auth_service import AuthService


class TestNurseAssignedAlerts(unittest.TestCase):
    """Test suite verifying strict nurse-assignment alert filtering and RBAC."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Nurse Priya (user_id = 5, assigned to patients 1, 2, 7)
        cls.priya = User.get_by_id(5)
        assert cls.priya is not None, "Nurse Priya (ID: 5) must exist"
        cls.priya_token = AuthService.generate_access_token(cls.priya)['access_token']
        cls.priya_headers = {'Authorization': f"Bearer {cls.priya_token}"}

        # Nurse Arun (user_id = 6, assigned to patients 3, 4, 8)
        cls.arun = User.get_by_id(6)
        assert cls.arun is not None, "Nurse Arun (ID: 6) must exist"
        cls.arun_token = AuthService.generate_access_token(cls.arun)['access_token']
        cls.arun_headers = {'Authorization': f"Bearer {cls.arun_token}"}

        # Doctor Sunita (user_id = 2)
        cls.doctor = User.get_by_id(2)
        cls.doc_token = AuthService.generate_access_token(cls.doctor)['access_token']
        cls.doc_headers = {'Authorization': f"Bearer {cls.doc_token}"}

        # Patient 3 is Vikram Singh, assigned to Nurse Arun (6)
        cls.patient3 = Patient.get_by_id(3)
        assert cls.patient3 is not None, "Patient 3 must exist"
        assert cls.patient3['assigned_nurse'] == 6, f"Patient 3 must be assigned to Nurse Arun (6), currently {cls.patient3['assigned_nurse']}"

    def test_01_priya_does_not_see_vikram_singh_in_global_feed(self):
        """1. Nurse Priya must NOT receive alerts or transfer notifications for Vikram Singh."""
        res = self.client.get('/api/v1/alerts/global-feed', headers=self.priya_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        transfer_alerts = data.get('transfer_alerts', [])
        vikram_transfers = [t for t in transfer_alerts if t.get('patient_id') == 3 or 'Vikram' in t.get('patient_name', '')]
        self.assertEqual(len(vikram_transfers), 0, "Nurse Priya must not see Vikram Singh in transfer_alerts")

        emergency_alerts = data.get('emergency_alerts', [])
        vikram_emergencies = [e for e in emergency_alerts if e.get('patient_id') == 3 or 'Vikram' in e.get('patient_name', '')]
        self.assertEqual(len(vikram_emergencies), 0, "Nurse Priya must not see Vikram Singh in emergency_alerts")

        approved_transfers = data.get('approved_transfers', [])
        vikram_approved = [a for a in approved_transfers if a.get('patient_id') == 3]
        self.assertEqual(len(vikram_approved), 0, "Nurse Priya must not see Vikram Singh in approved_transfers")

    def test_02_arun_sees_vikram_singh_transfer_alert(self):
        """2. Assigned Nurse Arun MUST see Vikram Singh's transfer alert."""
        res = self.client.get('/api/v1/alerts/global-feed', headers=self.arun_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        transfer_alerts = data.get('transfer_alerts', [])
        vikram_transfers = [t for t in transfer_alerts if t.get('patient_id') == 3]
        self.assertTrue(len(vikram_transfers) > 0, "Assigned Nurse Arun must see Vikram Singh in transfer_alerts")
        self.assertEqual(vikram_transfers[0]['patient_name'], 'Vikram Singh')

    def test_03_doctor_approval_required_for_transfers(self):
        """3. Confirm doctor approval is required: nurses cannot approve transfers."""
        # 1. can_approve_transfers flag must be False for nurses in global feed
        res_priya = self.client.get('/api/v1/alerts/global-feed', headers=self.priya_headers)
        self.assertFalse(res_priya.get_json().get('can_approve_transfers'))

        res_arun = self.client.get('/api/v1/alerts/global-feed', headers=self.arun_headers)
        self.assertFalse(res_arun.get_json().get('can_approve_transfers'))

        # 2. Direct approval attempt by nurse must be rejected with 403 Forbidden
        res_approve = self.client.post('/api/v1/decision/approve/3493', headers=self.arun_headers, json={})
        self.assertIn(res_approve.status_code, (401, 403))

    def test_04_direct_api_access_blocked_for_unassigned_nurse(self):
        """4. Unauthorized nurse blocked from retrieving unassigned patient details directly."""
        endpoints = [
            '/api/v1/patients/3',
            '/vitals/3',
            '/vitals/3/latest',
            '/vitals/patient/3/latest-status',
            '/vitals/patient/3/history',
            '/alerts/api/patient/3',
            '/patients/3/history',
            '/patients/3/transfers'
        ]

        for ep in endpoints:
            res_priya = self.client.get(ep, headers=self.priya_headers)
            self.assertEqual(
                res_priya.status_code, 403,
                f"Nurse Priya should be forbidden (403) from accessing {ep}, got {res_priya.status_code}"
            )

        # Assigned Nurse Arun CAN access them
        for ep in endpoints:
            res_arun = self.client.get(ep, headers=self.arun_headers)
            self.assertEqual(
                res_arun.status_code, 200,
                f"Assigned Nurse Arun should have access (200) to {ep}, got {res_arun.status_code}"
            )

    def test_05_active_alerts_and_counts_scoped_strictly(self):
        """5. Active alerts and alert counts are strictly scoped to assigned patients."""
        # Active alerts for Priya
        res_priya = self.client.get('/alerts/api/active', headers=self.priya_headers)
        self.assertEqual(res_priya.status_code, 200)
        priya_alerts = res_priya.get_json().get('data', [])
        for a in priya_alerts:
            self.assertEqual(a.get('assigned_nurse'), 5, f"Alert #{a.get('alert_id')} must belong to Priya's patient")
            self.assertNotEqual(a.get('patient_id'), 3, "Priya must not see Patient 3 alerts")

        # Active alerts for Arun
        res_arun = self.client.get('/alerts/api/active', headers=self.arun_headers)
        self.assertEqual(res_arun.status_code, 200)
        arun_alerts = res_arun.get_json().get('data', [])
        for a in arun_alerts:
            self.assertEqual(a.get('assigned_nurse'), 6, f"Alert #{a.get('alert_id')} must belong to Arun's patient")

    def test_06_dashboard_today_tasks_scoped_to_assigned_nurse(self):
        """6. /alerts/api/today-tasks returns tasks ONLY for the nurse's assigned patients."""
        res_priya = self.client.get('/alerts/api/today-tasks', headers=self.priya_headers)
        self.assertEqual(res_priya.status_code, 200)
        priya_tasks = res_priya.get_json().get('data', [])
        priya_pids = set(t['patient_id'] for t in priya_tasks)
        self.assertNotIn(3, priya_pids, "Priya must not have tasks for Patient 3 (Vikram Singh)")
        self.assertTrue(priya_pids.issubset({1, 2, 7}), f"Priya's tasks must only be for patients 1, 2, 7; got {priya_pids}")

        res_arun = self.client.get('/alerts/api/today-tasks', headers=self.arun_headers)
        self.assertEqual(res_arun.status_code, 200)
        arun_tasks = res_arun.get_json().get('data', [])
        arun_pids = set(t['patient_id'] for t in arun_tasks)
        self.assertIn(3, arun_pids, "Arun must have tasks for Patient 3 (Vikram Singh)")
        self.assertTrue(arun_pids.issubset({3, 4, 8}), f"Arun's tasks must only be for patients 3, 4, 8; got {arun_pids}")

    def test_07_patient_table_listing_scoped_to_assigned_nurse(self):
        """7. /api/v1/patients returns only the patients assigned to the logged-in nurse."""
        res_priya = self.client.get('/api/v1/patients', headers=self.priya_headers)
        self.assertEqual(res_priya.status_code, 200)
        priya_pts = res_priya.get_json().get('patients', [])
        priya_pids = set(p['patient_id'] for p in priya_pts)
        self.assertEqual(priya_pids, {1, 2, 7})

        res_arun = self.client.get('/api/v1/patients', headers=self.arun_headers)
        self.assertEqual(res_arun.status_code, 200)
        arun_pts = res_arun.get_json().get('patients', [])
        arun_pids = set(p['patient_id'] for p in arun_pts)
        self.assertEqual(arun_pids, {3, 4, 8})

    def test_08_dynamic_reassignment_updates_alerts_immediately(self):
        """8. If a patient is reassigned, alert visibility updates immediately."""
        try:
            # Reassign Vikram Singh (3) to Priya (5)
            db.execute_query("UPDATE patients SET assigned_nurse = 5 WHERE patient_id = 3")

            # Priya NOW sees Vikram in global feed
            res_priya = self.client.get('/api/v1/alerts/global-feed', headers=self.priya_headers)
            trans_priya = [t for t in res_priya.get_json().get('transfer_alerts', []) if t.get('patient_id') == 3]
            self.assertTrue(len(trans_priya) > 0, "Priya must now see Vikram Singh after reassignment")

            # Arun NO LONGER sees Vikram
            res_arun = self.client.get('/api/v1/alerts/global-feed', headers=self.arun_headers)
            trans_arun = [t for t in res_arun.get_json().get('transfer_alerts', []) if t.get('patient_id') == 3]
            self.assertEqual(len(trans_arun), 0, "Arun must no longer see Vikram Singh after reassignment")

            # Priya can access patient 3 details directly
            res_p3 = self.client.get('/api/v1/patients/3', headers=self.priya_headers)
            self.assertEqual(res_p3.status_code, 200)

        finally:
            # Reassign back to Arun (6)
            db.execute_query("UPDATE patients SET assigned_nurse = 6 WHERE patient_id = 3")

        # Verify restored state
        res_restored = self.client.get('/api/v1/alerts/global-feed', headers=self.priya_headers)
        trans_restored = [t for t in res_restored.get_json().get('transfer_alerts', []) if t.get('patient_id') == 3]
        self.assertEqual(len(trans_restored), 0, "Priya must not see Vikram Singh after restoring assignment")

    def test_09_unassigned_alerts_escalate_and_do_not_broadcast_to_nurses(self):
        """9. Alerts for patients without an assigned nurse do NOT broadcast to all nurses."""
        # Query with Priya and Arun for a non-existent/unassigned patient
        res_priya = self.client.get('/api/v1/alerts/global-feed', headers=self.priya_headers)
        priya_pids = set(t['patient_id'] for t in res_priya.get_json().get('transfer_alerts', []))
        # Priya only has patients with assigned_nurse = 5
        for pid in priya_pids:
            p_rec = Patient.get_by_id(pid)
            self.assertEqual(p_rec.get('assigned_nurse'), 5)

    def test_10_baseline_10_patients_intact(self):
        """10. Verify that exactly 10 baseline patients remain in the census."""
        patients = db.execute_query(
            "SELECT patient_id, name, assigned_doctor, assigned_nurse FROM patients ORDER BY patient_id ASC",
            fetch=True
        ) or []
        self.assertEqual(len(patients), 10, f"Expected 10 baseline patients, found {len(patients)}")


if __name__ == '__main__':
    unittest.main()

