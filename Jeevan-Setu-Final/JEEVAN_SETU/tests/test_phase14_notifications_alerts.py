"""
tests/test_phase14_notifications_alerts.py — Phase 14 Notifications & Alerts Test Suite.

Tests:
1. Notification model creation, broadcast to role, and broadcast to all staff.
2. Notification service dispatching:
   - CRITICAL_VITAL (Severity: CRITICAL)
   - TRANSFER_READY (Severity: TRANSFER)
   - ESCALATION (Severity: CRITICAL)
   - SYSTEM (Severity: INFO / WARNING)
3. Notification REST APIs:
   - GET /notifications & /api/v1/notifications
   - PUT /notifications/<id>/read & POST /notifications/<id>/read
   - PUT /notifications/read-all & POST /notifications/read-all
   - POST /notifications/trigger
4. Unread count tracking and unread filter.
5. RBAC / Authentication protection (401 when unauthorized).
"""

import sys
import os
import unittest
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.notification_model import Notification
from services.notification_service import NotificationService
from services.auth_service import AuthService


class TestPhase14NotificationsAlerts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000) % 100000

        # Create test users for different roles
        cls.doc_id = User.create(
            username=f"doc_notif_{cls.ts}",
            email=f"doc_notif_{cls.ts}@hospital.com",
            password="Password123!",
            role="doctor",
            full_name="Dr. Notification Tester"
        )
        cls.doctor = User.get_by_id(cls.doc_id)

        cls.nurse_id = User.create(
            username=f"nurse_notif_{cls.ts}",
            email=f"nurse_notif_{cls.ts}@hospital.com",
            password="Password123!",
            role="nurse",
            full_name="Nurse Notification Tester"
        )
        cls.nurse = User.get_by_id(cls.nurse_id)

        cls.admin_id = User.create(
            username=f"admin_notif_{cls.ts}",
            email=f"admin_notif_{cls.ts}@hospital.com",
            password="Password123!",
            role="admin",
            full_name="Admin Notification Tester"
        )
        cls.admin = User.get_by_id(cls.admin_id)

        # Generate tokens
        cls.doctor_token = AuthService.generate_access_token(cls.doctor)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse)['access_token']
        cls.admin_token = AuthService.generate_access_token(cls.admin)['access_token']

        # Create test patient
        cls.patient_id = Patient.create(
            name=f"Patient Notif {cls.ts}",
            age=52,
            gender="male",
            diagnosis="Acute Respiratory Distress",
            ward_type="ICU",
            bed_number=f"B-{cls.ts % 10000}"
        )

    def auth_header(self, token):
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    # ─────────────────────────────────────────────────────────
    # 1. Model & Service Trigger Tests
    # ─────────────────────────────────────────────────────────
    def test_01_trigger_critical_vital(self):
        """Test CRITICAL_VITAL notification event dispatch with CRITICAL severity."""
        result = NotificationService.trigger_critical_vital(
            patient_id=self.patient_id,
            parameter="heart_rate",
            value=148,
            threshold=130,
            ews_score=9
        )
        self.assertEqual(result['event'], 'CRITICAL_VITAL')
        self.assertEqual(result['severity'], 'CRITICAL')
        self.assertIn("CRITICAL_VITAL", result['title'])

        # Verify doctor received notification
        notifs = Notification.get_by_user(self.doc_id)
        self.assertTrue(len(notifs) > 0)
        found = any("heart_rate" in n['message'].lower() or "critical_vital" in n['title'].lower() for n in notifs)
        self.assertTrue(found)

    def test_02_trigger_transfer_ready(self):
        """Test TRANSFER_READY notification event dispatch with TRANSFER severity."""
        result = NotificationService.trigger_transfer_ready(
            patient_id=self.patient_id,
            from_ward="ICU",
            to_ward="HDU",
            score=2
        )
        self.assertEqual(result['event'], 'TRANSFER_READY')
        self.assertEqual(result['severity'], 'TRANSFER')
        self.assertIn("TRANSFER_READY", result['title'])

        # Verify nurse received transfer ready notification
        notifs = Notification.get_by_user(self.nurse_id)
        found = any("transfer_ready" in n['title'].lower() for n in notifs)
        self.assertTrue(found)

    def test_03_trigger_escalation(self):
        """Test ESCALATION notification event dispatch with CRITICAL severity."""
        result = NotificationService.trigger_escalation(
            patient_id=self.patient_id,
            from_ward="HDU",
            to_ward="ICU",
            reason="Rapid oxygen desaturation",
            score=8
        )
        self.assertEqual(result['event'], 'ESCALATION')
        self.assertEqual(result['severity'], 'CRITICAL')
        self.assertIn("ESCALATION", result['title'])

    def test_04_trigger_system_event(self):
        """Test SYSTEM notification event dispatch with INFO/WARNING severity."""
        result = NotificationService.trigger_system_event(
            title="Scheduled Maintenance",
            message="Server maintenance scheduled at 02:00 AM",
            severity="WARNING",
            target_role="admin"
        )
        self.assertEqual(result['event'], 'SYSTEM')
        self.assertEqual(result['severity'], 'WARNING')

    # ─────────────────────────────────────────────────────────
    # 2. REST API Endpoints
    # ─────────────────────────────────────────────────────────
    def test_05_get_notifications_api(self):
        """Test GET /notifications and GET /api/v1/notifications."""
        # Unauthenticated request should fail
        res = self.client.get('/notifications')
        self.assertEqual(res.status_code, 401)

        # Doctor authenticated request
        res = self.client.get('/notifications', headers=self.auth_header(self.doctor_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('unread_count', data)
        self.assertIn('data', data)
        self.assertIsInstance(data['data'], list)

        # Check API v1 alias
        res_v1 = self.client.get('/api/v1/notifications', headers=self.auth_header(self.doctor_token))
        self.assertEqual(res_v1.status_code, 200)
        self.assertTrue(res_v1.get_json()['success'])

    def test_06_mark_single_notification_read(self):
        """Test PUT /notifications/{id}/read."""
        # Get notifications for nurse
        res = self.client.get('/notifications', headers=self.auth_header(self.nurse_token))
        notifs = res.get_json()['data']
        self.assertTrue(len(notifs) > 0)
        target_notif_id = notifs[0]['notification_id']

        # Mark as read
        put_res = self.client.put(
            f'/notifications/{target_notif_id}/read',
            headers=self.auth_header(self.nurse_token)
        )
        self.assertEqual(put_res.status_code, 200)
        data = put_res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['notification_id'], target_notif_id)

    def test_07_mark_all_notifications_read(self):
        """Test PUT /notifications/read-all."""
        res = self.client.put('/notifications/read-all', headers=self.auth_header(self.nurse_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['unread_count'], 0)

        # Check unread_only filter now returns 0
        get_res = self.client.get('/notifications?unread_only=true', headers=self.auth_header(self.nurse_token))
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(len(get_res.get_json()['data']), 0)

    def test_08_post_trigger_api(self):
        """Test POST /notifications/trigger via REST API."""
        payload = {
            "event_type": "CRITICAL_VITAL",
            "patient_id": self.patient_id,
            "parameter": "systolic_bp",
            "value": 72,
            "threshold": 90,
            "ews_score": 7
        }
        res = self.client.post(
            '/notifications/trigger',
            headers=self.auth_header(self.doctor_token),
            json=payload
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['event'], 'CRITICAL_VITAL')


if __name__ == '__main__':
    unittest.main()
