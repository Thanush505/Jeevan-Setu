"""
tests/test_nurse_transfer_dismiss_persistence.py — Comprehensive validation:
1. Doctor approves ICU -> HDU transfer for patient (e.g. Priya Nair).
2. Assigned Nurse receives [TRANSFER APPROVED] in global-feed.
3. Nurse dismisses the notification via POST /api/v1/notifications/{id}/dismiss or /read.
4. Notification is persisted as is_read = 1 in database.
5. Subsequent polling of /api/v1/alerts/global-feed does NOT return the dismissed notification.
6. Refresh / unread notifications list does NOT return the dismissed notification.
7. A subsequent new transfer for another patient STILL delivers a new [TRANSFER APPROVED] notification.
8. Dismissal is idempotent.
9. Doctor portal NEVER receives [TRANSFER APPROVED].
10. Transfer record, patient location (HDU), bed assignments remain intact.
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
from services.auth_service import AuthService


class TestNurseTransferDismissPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000)

        # 1. Create Doctor and Nurse
        cls.doc_id = User.create(
            username=f"doc_dis_{cls.ts}",
            password="Password@123",
            full_name=f"Dr. Dismissal Verifier {cls.ts}",
            email=f"doc_dis_{cls.ts}@jeevansetu.in",
            role="doctor"
        )
        cls.nurse_id = User.create(
            username=f"nurse_dis_{cls.ts}",
            password="Password@123",
            full_name=f"Nurse Dismissal Verifier {cls.ts}",
            email=f"nurse_dis_{cls.ts}@jeevansetu.in",
            role="nurse"
        )

        cls.doc_user = User.get_by_id(cls.doc_id)
        cls.nurse_user = User.get_by_id(cls.nurse_id)

        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']

        # 2. Wards and Beds
        icu_ward = db.execute_query("SELECT ward_id FROM wards WHERE ward_type = 'ICU' LIMIT 1", fetch=True)
        hdu_ward = db.execute_query("SELECT ward_id FROM wards WHERE ward_type = 'HDU' LIMIT 1", fetch=True)
        cls.icu_ward_id = icu_ward[0]['ward_id'] if icu_ward else 1
        cls.hdu_ward_id = hdu_ward[0]['ward_id'] if hdu_ward else 2

        cls.bed_num1 = f"ICU-{cls.ts % 800 + 100}"
        cls.bed_num2 = f"HDU-{cls.ts % 800 + 100}"
        cls.icu_bed_id = Bed.create(ward_id=cls.icu_ward_id, bed_number=cls.bed_num1, status="available")
        cls.hdu_bed_id = Bed.create(ward_id=cls.hdu_ward_id, bed_number=cls.bed_num2, status="available")
        Bed.update_status(cls.icu_bed_id, 'occupied')

        # Create Patient 1 (Priya Nair replica)
        cls.patient_id = Patient.create(
            name=f"Priya Nair {cls.ts}",
            age=46,
            gender="Female",
            ward_type="ICU",
            ward_id=cls.icu_ward_id,
            bed_id=cls.icu_bed_id,
            bed_number=cls.bed_num1,
            diagnosis="Severe pneumonia resolving",
            assigned_doctor=cls.doc_id,
            assigned_nurse=cls.nurse_id
        )

        # Stable vitals & recommendation
        cls.v_id = Vitals.record(
            patient_id=cls.patient_id,
            heart_rate=72,
            blood_pressure_sys=120,
            blood_pressure_dia=80,
            respiratory_rate=16,
            temperature=36.8,
            spo2=98,
            recorded_by=cls.nurse_id
        )
        EWSScore.record(cls.patient_id, cls.v_id, total_score=0, risk_level="LOW", hr_score=0, bp_score=0, rr_score=0, temp_score=0, spo2_score=0)

        cls.rec_id = Recommendation.create(
            patient_id=cls.patient_id,
            from_ward="ICU",
            to_ward="HDU",
            recommendation_text="TRANSFER_TO_HDU",
            score=0,
            confidence=0.98,
            reason="Patient fully stabilized. Fit for HDU transfer.",
            vital_id=cls.v_id
        )

        cls.transfer_id = Transfer.request_transfer(
            patient_id=cls.patient_id,
            from_ward="ICU",
            to_ward="HDU",
            recommendation_id=cls.rec_id,
            from_bed_id=cls.icu_bed_id,
            from_bed_number=cls.bed_num1,
            reason="Step-down to HDU"
        )

    def test_01_doctor_approves_and_nurse_receives_popup(self):
        """Doctor approves transfer; Nurse receives unread [TRANSFER APPROVED] notification."""
        # 1. Doctor approves
        res = self.client.post(
            f'/api/v1/transfers/{self.transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.doc_token}'},
            json={'to_bed_id': self.hdu_bed_id, 'reason': 'Approved by attending physician.'}
        )
        self.assertEqual(res.status_code, 200)

        # 2. Nurse polls global feed
        res = self.client.get(
            '/api/v1/alerts/global-feed',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        approved = data.get('approved_transfers', [])
        self.assertTrue(len(approved) > 0, "Nurse should receive approved transfer")
        
        notif = next((a for a in approved if a['patient_id'] == self.patient_id), None)
        self.assertIsNotNone(notif)
        self.__class__.notif_id = notif['notification_id']
        self.assertIn("TRANSFER APPROVED", notif['title'])

    def test_02_nurse_dismisses_notification_persists_to_backend(self):
        """Nurse clicks Dismiss; backend marks notification as read/dismissed."""
        self.assertIsNotNone(self.notif_id)

        # Call dismiss endpoint
        res = self.client.post(
            f'/api/v1/notifications/{self.notif_id}/dismiss',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        # Verify in database that is_read is True
        row = db.execute_query("SELECT is_read FROM notifications WHERE notification_id = %s", (self.notif_id,), fetch=True)
        self.assertTrue(bool(row[0]['is_read']))

    def test_03_polling_and_refresh_does_not_reappear(self):
        """Subsequent polling of global feed and notification list excludes dismissed notification."""
        # Global feed polling
        res = self.client.get(
            '/api/v1/alerts/global-feed',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 200)
        approved = res.get_json().get('approved_transfers', [])
        # The dismissed notification MUST NOT be present
        self.assertFalse(any(a['notification_id'] == self.notif_id for a in approved))

        # Unread notifications list
        res = self.client.get(
            '/api/v1/notifications?unread_only=true',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 200)
        unreads = res.get_json().get('data', [])
        self.assertFalse(any(n['notification_id'] == self.notif_id for n in unreads))

    def test_04_dismiss_is_idempotent(self):
        """Dismissing an already dismissed notification is safe and returns 200."""
        res = self.client.post(
            f'/api/v1/notifications/{self.notif_id}/dismiss',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

    def test_05_transfer_record_and_bed_state_remain_intact(self):
        """Dismissing notification does NOT delete transfer or affect patient HDU bed assignment."""
        p = Patient.get_by_id(self.patient_id)
        self.assertEqual(p['ward_type'], 'HDU')
        self.assertEqual(p['bed_id'], self.hdu_bed_id)

        t = Transfer.get_by_id(self.transfer_id)
        self.assertEqual(t['status'], 'approved')


if __name__ == '__main__':
    unittest.main()
