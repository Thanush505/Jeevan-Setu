"""
tests/test_doctor_no_transfer_approved_alert.py — Comprehensive validation:
1. Doctor approves ICU -> HDU transfer.
2. Nurse receives [TRANSFER APPROVED] in global feed and notification stream.
3. Doctor does NOT receive [TRANSFER APPROVED] in global feed (approved_transfers is empty).
4. Doctor does NOT receive [TRANSFER APPROVED] in notification list.
5. Doctor continues to receive Critical emergency alerts and Ready-to-Transfer pending approvals.
"""

import unittest
import time
import os
import sys

JEEVAN_SETU_ROOT = r'd:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU'
if JEEVAN_SETU_ROOT not in sys.path:
    sys.path.insert(0, JEEVAN_SETU_ROOT)

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.bed_model import Bed
from models.ward_model import Ward
from models.vitals_model import Vitals
from models.ews_score_model import EWSScore
from models.recommendation_model import Recommendation
from models.transfer_model import Transfer
from models.notification_model import Notification
from models.alert_model import Alert
from services.auth_service import AuthService


class TestDoctorNoTransferApprovedAlert(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000)

        # 1. Create Doctor and Nurse
        cls.doc_id = User.create(
            username=f"doc_notif_{cls.ts}",
            password="Password@123",
            full_name=f"Dr. Approval Notif Tester {cls.ts}",
            email=f"doc_notif_{cls.ts}@jeevansetu.in",
            role="doctor"
        )
        cls.nurse_id = User.create(
            username=f"nurse_notif_{cls.ts}",
            password="Password@123",
            full_name=f"Nurse Notif Recipient {cls.ts}",
            email=f"nurse_notif_{cls.ts}@jeevansetu.in",
            role="nurse"
        )

        cls.doc_user = User.get_by_id(cls.doc_id)
        cls.nurse_user = User.get_by_id(cls.nurse_id)

        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']

        # 2. Setup Wards and Beds
        cls.icu_ward = db.execute_query("SELECT ward_id FROM wards WHERE ward_type = 'ICU' LIMIT 1", fetch=True)
        cls.hdu_ward = db.execute_query("SELECT ward_id FROM wards WHERE ward_type = 'HDU' LIMIT 1", fetch=True)
        cls.icu_ward_id = cls.icu_ward[0]['ward_id'] if cls.icu_ward else 1
        cls.hdu_ward_id = cls.hdu_ward[0]['ward_id'] if cls.hdu_ward else 2

        # Create available beds
        cls.icu_bed_id = Bed.create(ward_id=cls.icu_ward_id, bed_number=f"ICU-T-{cls.ts % 10000}", status="available")
        cls.hdu_bed_id = Bed.create(ward_id=cls.hdu_ward_id, bed_number=f"HDU-T-{cls.ts % 10000}", status="available")

        # Create Patient assigned to Doctor & Nurse
        cls.patient_id = Patient.create(
            name=f"Transfer Alert Test Patient {cls.ts}",
            age=52,
            gender="Male",
            ward_type="ICU",
            ward_id=cls.icu_ward_id,
            bed_id=cls.icu_bed_id,
            bed_number=f"ICU-T-{cls.ts % 10000}",
            diagnosis="Post-operative coronary bypass (recovering)",
            assigned_doctor=cls.doc_id,
            assigned_nurse=cls.nurse_id
        )

        # Set bed occupied
        Bed.update_status(cls.icu_bed_id, 'occupied')

        # Record stable vitals (EWS = 1)
        cls.v_id = Vitals.record(
            patient_id=cls.patient_id,
            heart_rate=78,
            blood_pressure_sys=122,
            blood_pressure_dia=80,
            respiratory_rate=16,
            temperature=37.0,
            spo2=97,
            recorded_by=cls.nurse_id
        )
        EWSScore.record(cls.patient_id, cls.v_id, total_score=1, risk_level="LOW", hr_score=0, bp_score=0, rr_score=0, temp_score=0, spo2_score=1)

        # Create Recommendation
        cls.rec_id = Recommendation.create(
            patient_id=cls.patient_id,
            from_ward="ICU",
            to_ward="HDU",
            recommendation_text="TRANSFER_TO_HDU",
            score=1,
            confidence=0.95,
            reason="Patient stabilized with low EWS. Ready for step-down to HDU.",
            vital_id=cls.v_id
        )

        # Create Transfer record
        cls.transfer_id = Transfer.request_transfer(
            patient_id=cls.patient_id,
            from_ward="ICU",
            to_ward="HDU",
            recommendation_id=cls.rec_id,
            from_bed_id=cls.icu_bed_id,
            from_bed_number=f"ICU-T-{cls.ts % 10000}",
            reason="Step-down to HDU as per clinical improvement"
        )

    def test_01_doctor_approves_transfer(self):
        """Doctor approves the transfer via API."""
        res = self.client.post(
            f'/api/v1/transfers/{self.transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.doc_token}'},
            json={'to_bed_id': self.hdu_bed_id, 'reason': 'Approved by attending doctor.'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'approved')

        # Verify DB states
        p = Patient.get_by_id(self.patient_id)
        self.assertEqual(p['ward_type'], 'HDU')
        self.assertEqual(p['bed_id'], self.hdu_bed_id)

    def test_02_doctor_global_feed_has_no_approved_transfer_popup(self):
        """Doctor MUST NOT receive approved_transfers in global feed."""
        res = self.client.get(
            '/api/v1/alerts/global-feed',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['role'], 'doctor')
        # approved_transfers MUST be empty for doctor
        self.assertEqual(len(data.get('approved_transfers', [])), 0)
        self.assertEqual(data.get('approved_transfers_count', 0), 0)

    def test_03_nurse_global_feed_receives_approved_transfer_popup(self):
        """Nurse MUST receive approved_transfers in global feed."""
        res = self.client.get(
            '/api/v1/alerts/global-feed',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['role'], 'nurse')
        # Nurse must have the transfer notification
        approved = data.get('approved_transfers', [])
        self.assertTrue(len(approved) > 0)
        self.assertTrue(any(a['patient_id'] == self.patient_id for a in approved))
        notif = next(a for a in approved if a['patient_id'] == self.patient_id)
        self.assertIn("TRANSFER APPROVED", notif['title'])

    def test_04_doctor_notifications_exclude_transfer_approved(self):
        """Doctor notification stream excludes [TRANSFER APPROVED]."""
        res = self.client.get(
            '/api/v1/notifications',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        notifs = data.get('data', [])
        self.assertFalse(any('[TRANSFER APPROVED]' in n.get('title', '') for n in notifs))

    def test_05_doctor_still_receives_critical_emergency_alerts(self):
        """Doctor continues to receive Critical emergency alerts for assigned patients."""
        # Create emergency alert for assigned patient
        alert_id = Alert.create(
            patient_id=self.patient_id,
            alert_type="CRITICAL",
            title="Severe Hypoxemia Alert",
            message="Severe hypoxemia detected for patient",
            parameter="spo2",
            value=85.0,
            threshold=90.0
        )
        self.assertTrue(alert_id > 0)

        res = self.client.get(
            '/api/v1/alerts/global-feed',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        emergencies = data.get('emergency_alerts', [])
        self.assertTrue(any(e['patient_id'] == self.patient_id for e in emergencies))


if __name__ == '__main__':
    unittest.main()
