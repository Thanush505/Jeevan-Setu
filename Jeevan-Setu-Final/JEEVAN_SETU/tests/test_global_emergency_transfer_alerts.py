"""
tests/test_global_emergency_transfer_alerts.py — Comprehensive validation of:
1. Global Emergency Alert System (Critical EWS Detection & Duplicate Prevention)
2. Prolonged Ready-to-Transfer Alert System (Waiting Period Detection)
3. Strict Doctor-Only Transfer Approval (Nurse Block with 403 Forbidden)
4. Stale Transfer Approval Protection (Rejection when clinical state changes)
5. Audit Logging and Nurse Post-Approval Notification
"""

import unittest
import json
import time
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.alert_model import Alert
from models.recommendation_model import Recommendation
from models.transfer_model import Transfer
from models.notification_model import Notification
from models.audit_log_model import AuditLog
from services.auth_service import AuthService
from services.decision_service import evaluate
from modules.alert_engine import (
    create_emergency_critical_alert,
    auto_resolve_patient_critical_alerts,
    check_and_generate_prolonged_transfer_alerts,
    get_active_transfer_alerts_for_user
)
from app import create_app


class TestGlobalEmergencyTransferAlerts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        # Fetch or create test users safely
        cls.doctor_data = User.get_by_username('dr_sharma')
        cls.doctor_id = cls.doctor_data['user_id'] if isinstance(cls.doctor_data, dict) else getattr(cls.doctor_data, 'user_id', getattr(cls.doctor_data, 'id', 2))
        cls.doctor_user = User.get_by_id(cls.doctor_id)

        cls.nurse_data = User.get_by_username('nurse_priya')
        cls.nurse_id = cls.nurse_data['user_id'] if isinstance(cls.nurse_data, dict) else getattr(cls.nurse_data, 'user_id', getattr(cls.nurse_data, 'id', 3))
        cls.nurse_user = User.get_by_id(cls.nurse_id)

        cls.admin_user = User.get_by_id(1)
        cls.admin_id = getattr(cls.admin_user, 'id', 1)

        cls.doctor_token = AuthService.generate_access_token(cls.doctor_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']
        cls.admin_token = AuthService.generate_access_token(cls.admin_user)['access_token']

    def setUp(self):
        # Create a dedicated test patient
        unique_suffix = int(time.time() * 1000) % 100000
        self.patient_id = Patient.create(
            name=f"Emergency Test Patient {unique_suffix}",
            age=52,
            gender='Male',
            ward_type='ICU',
            bed_number='01',
            diagnosis='Acute Respiratory Distress',
            assigned_doctor=self.doctor_id,
            assigned_nurse=self.nurse_id
        )

    def tearDown(self):
        # Cleanup test records
        try:
            db.execute_query("DELETE FROM alerts WHERE patient_id = %s", (self.patient_id,))
            db.execute_query("DELETE FROM notifications WHERE patient_id = %s", (self.patient_id,))
            db.execute_query("DELETE FROM transfers WHERE patient_id = %s", (self.patient_id,))
            db.execute_query("DELETE FROM recommendations WHERE patient_id = %s", (self.patient_id,))
            db.execute_query("DELETE FROM vitals WHERE patient_id = %s", (self.patient_id,))
            db.execute_query("DELETE FROM ews_scores WHERE patient_id = %s", (self.patient_id,))
            db.execute_query("DELETE FROM patients WHERE patient_id = %s", (self.patient_id,))
        except Exception:
            pass

    # =========================================================================
    # 1. CRITICAL EMERGENCY ALERT & DUPLICATE PREVENTION TESTS
    # =========================================================================
    def test_01_critical_ews_generates_emergency_alert(self):
        """Verify submitting critical vitals (EWS >= 5) automatically creates CRITICAL emergency alert."""
        critical_vitals = {
            'respiratory_rate': 32.0,  # Score 3 (Severe tachypnea)
            'heart_rate': 135.0,       # Score 3 (Severe tachycardia)
            'systolic_bp': 80.0,       # Score 2 (Hypotension)
            'temperature': 39.6        # Score 2 (High fever)
        }
        res = self.client.post(
            f'/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json=critical_vitals
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['condition'], 'Critical')
        self.assertGreaterEqual(data['data']['total_score'], 5)

        # Verify alert exists in database
        alerts = db.execute_query(
            "SELECT * FROM alerts WHERE patient_id = %s AND alert_type = 'critical' AND is_acknowledged = FALSE",
            (self.patient_id,), fetch=True
        )
        self.assertTrue(len(alerts) >= 1)
        alert = alerts[0]
        self.assertEqual(alert['alert_type'], 'critical')
        self.assertIn('CRITICAL PATIENT ALERT', alert['title'])
        self.assertEqual(alert['parameter'], 'ews_total')

    def test_02_duplicate_critical_alert_prevention(self):
        """Verify repeated critical vital submissions do not create duplicate active alerts."""
        critical_vitals = {
            'respiratory_rate': 32.0,
            'heart_rate': 135.0,
            'systolic_bp': 80.0,
            'temperature': 39.6
        }
        # First submission
        self.client.post(
            f'/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json=critical_vitals
        )
        # Second submission while patient remains critical
        self.client.post(
            f'/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json=critical_vitals
        )
        # Third submission
        self.client.post(
            f'/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json=critical_vitals
        )

        active_alerts = db.execute_query(
            "SELECT * FROM alerts WHERE patient_id = %s AND alert_type = 'critical' AND parameter = 'ews_total' AND is_acknowledged = FALSE",
            (self.patient_id,), fetch=True
        )
        # Should have exactly 1 active critical alert, not 3!
        self.assertEqual(len(active_alerts), 1)

    def test_03_condition_recovery_auto_resolves_critical_alert(self):
        """Verify patient recovery from Critical to Stable auto-resolves the active critical alert."""
        # Step 1: Submit critical vitals
        self.client.post(
            f'/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={'respiratory_rate': 32.0, 'heart_rate': 135.0, 'systolic_bp': 80.0, 'temperature': 39.6}
        )
        active_before = db.execute_query(
            "SELECT COUNT(*) as cnt FROM alerts WHERE patient_id = %s AND alert_type = 'critical' AND is_acknowledged = FALSE",
            (self.patient_id,), fetch=True
        )[0]['cnt']
        self.assertEqual(active_before, 1)

        # Step 2: Patient stabilizes (Normal vitals: EWS 0, Condition: Stable)
        self.client.post(
            f'/vitals/patient/{self.patient_id}/submit',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={'respiratory_rate': 16.0, 'heart_rate': 75.0, 'systolic_bp': 120.0, 'temperature': 36.8}
        )

        active_after = db.execute_query(
            "SELECT COUNT(*) as cnt FROM alerts WHERE patient_id = %s AND alert_type = 'critical' AND is_acknowledged = FALSE",
            (self.patient_id,), fetch=True
        )[0]['cnt']
        self.assertEqual(active_after, 0)

    # =========================================================================
    # 2. GLOBAL ALERT FEED & SCOPING TESTS
    # =========================================================================
    def test_04_global_feed_returns_critical_alerts_to_doctor_and_nurse(self):
        """Verify GET /api/v1/alerts/global-feed returns active emergency alerts to both Doctor and Nurse."""
        # Create critical alert
        create_emergency_critical_alert(
            patient_id=self.patient_id,
            total_score=8,
            condition='Critical',
            recommendation='Keep in ICU',
            patient_name='Test Critical Patient'
        )

        # Doctor request
        res_doc = self.client.get('/api/v1/alerts/global-feed', headers={'Authorization': f'Bearer {self.doctor_token}'})
        self.assertEqual(res_doc.status_code, 200)
        data_doc = res_doc.get_json()
        self.assertTrue(data_doc['success'])
        self.assertTrue(data_doc['can_approve_transfers'])
        matching_doc = [a for a in data_doc['emergency_alerts'] if a['patient_id'] == self.patient_id]
        self.assertEqual(len(matching_doc), 1)

        # Nurse request
        res_nurse = self.client.get('/api/v1/alerts/global-feed', headers={'Authorization': f'Bearer {self.nurse_token}'})
        self.assertEqual(res_nurse.status_code, 200)
        data_nurse = res_nurse.get_json()
        self.assertTrue(data_nurse['success'])
        self.assertFalse(data_nurse['can_approve_transfers'])
        matching_nurse = [a for a in data_nurse['emergency_alerts'] if a['patient_id'] == self.patient_id]
        self.assertEqual(len(matching_nurse), 1)

    def test_05_emergency_alert_acknowledgement(self):
        """Verify POST /api/v1/alerts/emergency/acknowledge/<id> marks alert acknowledged."""
        alert_id = create_emergency_critical_alert(
            patient_id=self.patient_id,
            total_score=7,
            condition='Critical',
            recommendation='Keep in ICU',
            patient_name='Test Patient'
        )
        self.assertIsNotNone(alert_id)

        res = self.client.post(
            f'/api/v1/alerts/emergency/acknowledge/{alert_id}',
            headers={'Authorization': f'Bearer {self.doctor_token}'}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        row = db.execute_query("SELECT is_acknowledged, acknowledged_by FROM alerts WHERE alert_id = %s", (alert_id,), fetch=True)[0]
        self.assertTrue(row['is_acknowledged'])
        self.assertEqual(row['acknowledged_by'], self.doctor_id)

    # =========================================================================
    # 3. PROLONGED READY-TO-TRANSFER DETECTION TESTS
    # =========================================================================
    def test_06_prolonged_ready_to_transfer_detection(self):
        """Verify patient in Ready-to-Transfer state exceeding waiting period generates approval alert."""
        # Create a recommendation that has been pending for 150 minutes (waiting period: 120 mins)
        rec_id = db.execute_query(
            """INSERT INTO recommendations (patient_id, from_ward, to_ward, score, recommendation_text, status, created_at)
               VALUES (%s, 'ICU', 'HDU', 1, 'Fit for HDU Transfer', 'pending', DATE_SUB(NOW(), INTERVAL 150 MINUTE))""",
            (self.patient_id,)
        )

        generated = check_and_generate_prolonged_transfer_alerts(patient_id=self.patient_id, waiting_period_minutes=120)
        self.assertTrue(len(generated) >= 1)
        self.assertEqual(generated[0]['patient_id'], self.patient_id)

        # Check in active transfer alerts for user
        feed_doc = get_active_transfer_alerts_for_user(self.doctor_user)
        matching = [t for t in feed_doc if t['patient_id'] == self.patient_id]
        self.assertEqual(len(matching), 1)
        self.assertTrue(matching[0]['can_approve'])
        self.assertTrue(matching[0]['is_prolonged'])

        # Nurse gets view-only with can_approve = False
        feed_nurse = get_active_transfer_alerts_for_user(self.nurse_user)
        matching_nurse = [t for t in feed_nurse if t['patient_id'] == self.patient_id]
        self.assertEqual(len(matching_nurse), 1)
        self.assertFalse(matching_nurse[0]['can_approve'])

    # =========================================================================
    # 4. NURSE STRICT 403 FORBIDDEN & DOCTOR APPROVAL TESTS
    # =========================================================================
    def test_07_nurse_cannot_approve_transfer_returns_403(self):
        """Verify Nurse attempting to call transfer approval API is rejected with HTTP 403 Forbidden."""
        rec_id = Recommendation.create(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_text='Fit for HDU Transfer',
            score=1,
            status='pending'
        )
        transfer_id = Transfer.request_transfer(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_id=rec_id
        )

        # 1. Nurse attempts /transfers/{id}/approve
        res_transfer = self.client.post(
            f'/api/v1/transfers/{transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={'remarks': 'Nurse attempt'}
        )
        self.assertEqual(res_transfer.status_code, 403)
        self.assertFalse(res_transfer.get_json()['success'])
        self.assertIn('Nurses are not authorized to approve patient transfers', res_transfer.get_json()['error'])

        # 2. Nurse attempts /decision/approve/{id}
        res_decision = self.client.post(
            f'/api/v1/decision/approve/{rec_id}',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res_decision.status_code, 403)
        self.assertFalse(res_decision.get_json()['success'])

        # Verify transfer remains pending
        tf = Transfer.get_by_id(transfer_id)
        self.assertEqual(tf['status'], 'pending')

        # Verify security audit log recorded
        audit = db.execute_query(
            "SELECT * FROM audit_logs WHERE action = 'UNAUTHORIZED_TRANSFER_APPROVAL_ATTEMPT' AND entity_id = %s",
            (transfer_id,), fetch=True
        )
        self.assertTrue(len(audit) >= 1)

    def test_08_doctor_approves_transfer_and_notifies_nurse(self):
        """Verify authorized Doctor approves transfer, state updates, and Nurse is notified."""
        # Ensure patient has stable vitals (EWS 0)
        Vitals.record(
            patient_id=self.patient_id,
            heart_rate=72.0,
            blood_pressure_sys=118.0,
            respiratory_rate=15.0,
            temperature=36.7,
            ews_score=0
        )

        rec_id = Recommendation.create(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_text='Fit for HDU Transfer',
            score=0,
            status='pending'
        )
        transfer_id = Transfer.request_transfer(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_id=rec_id
        )

        # Doctor approves
        res = self.client.post(
            f'/api/v1/transfers/{transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.doctor_token}'},
            json={'remarks': 'Approved step-down to HDU'}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify transfer status is approved
        tf = Transfer.get_by_id(transfer_id)
        self.assertEqual(tf['status'], 'approved')

        # Verify notification sent to Nurse
        nurse_notifs = Notification.get_by_user(self.nurse_id, notif_type='transfer')
        matching_notif = [n for n in nurse_notifs if n.get('patient_id') == self.patient_id]
        self.assertTrue(len(matching_notif) >= 1)
        self.assertIn('approved', matching_notif[0]['message'].lower())

    # =========================================================================
    # 5. STALE TRANSFER APPROVAL REJECTION TEST
    # =========================================================================
    def test_09_stale_transfer_approval_is_rejected(self):
        """Verify Doctor cannot approve transfer if patient condition deteriorated (stale approval)."""
        # Step 1: Patient was stable & transfer requested
        rec_id = Recommendation.create(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_text='Fit for HDU Transfer',
            score=1,
            status='pending'
        )
        transfer_id = Transfer.request_transfer(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_id=rec_id
        )

        # Step 2: Patient deteriorates (EWS becomes 8, condition becomes Critical)
        Vitals.record(
            patient_id=self.patient_id,
            heart_rate=140.0,
            blood_pressure_sys=80.0,
            respiratory_rate=34.0,
            temperature=39.8,
            ews_score=8
        )

        # Step 3: Doctor attempts to approve old stale transfer
        res = self.client.post(
            f'/api/v1/transfers/{transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.doctor_token}'},
            json={'remarks': 'Attempting approval on deteriorated patient'}
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])
        self.assertIn("Transfer approval is no longer valid", res.get_json()['error'])

        # Verify transfer status remains pending (did NOT complete)
        tf = Transfer.get_by_id(transfer_id)
        self.assertEqual(tf['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
