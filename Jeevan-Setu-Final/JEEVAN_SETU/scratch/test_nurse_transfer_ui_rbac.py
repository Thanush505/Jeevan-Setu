"""
scratch/test_nurse_transfer_ui_rbac.py
Comprehensive automated test suite for Nurse Portal transfer UI fix and backend RBAC.
"""

import unittest
import json
import time
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.recommendation_model import Recommendation
from models.transfer_model import Transfer
from models.notification_model import Notification
from services.auth_service import AuthService
from app import create_app


class TestNurseTransferUIRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        cls.doctor_data = User.get_by_username('dr_sharma')
        cls.doctor_id = cls.doctor_data['user_id'] if isinstance(cls.doctor_data, dict) else getattr(cls.doctor_data, 'user_id', 2)
        cls.doctor_user = User.get_by_id(cls.doctor_id)

        cls.nurse_data = User.get_by_username('nurse_priya')
        cls.nurse_id = cls.nurse_data['user_id'] if isinstance(cls.nurse_data, dict) else getattr(cls.nurse_data, 'user_id', 3)
        cls.nurse_user = User.get_by_id(cls.nurse_id)

        cls.doctor_token = AuthService.generate_access_token(cls.doctor_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']

    def setUp(self):
        suffix = int(time.time() * 1000) % 100000
        self.patient_id = Patient.create(
            name=f"Nurse UI Test Patient {suffix}",
            age=48,
            gender='Female',
            ward_type='ICU',
            bed_number='02',
            diagnosis='Post-op Monitoring',
            assigned_doctor=self.doctor_id,
            assigned_nurse=self.nurse_id
        )

    def tearDown(self):
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

    def test_01_frontend_global_alert_manager_nurse_ui_contract(self):
        """Verify global_alert_manager.js strictly adheres to Nurse UI constraints."""
        frontend_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Jeevan_setu_frontend', 'global_alert_manager.js'))
        with open(frontend_js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Check strict role enforcement exists
        self.assertIn("const isNurse = isNursePage || storedRole === 'nurse' || apiRole === 'nurse';", content)
        self.assertIn("if (isNurse) {", content)
        self.assertIn("isDoctor = false;", content)

        # 2. Check Nurse UI action buttons contain Dismiss and Review, but NOT Approve Transfer
        self.assertIn("btn-dismiss-transfer", content)
        self.assertIn("btn-approve-transfer", content)
        self.assertIn("if (isDoctor && !isNurse) {", content)

    def test_02_backend_rejects_nurse_transfer_approval_with_403(self):
        """Verify Nurse attempting POST /api/v1/transfers/<id>/approve receives HTTP 403 Forbidden."""
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

        res = self.client.post(
            f'/api/v1/transfers/{transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={'remarks': 'Nurse attempting approval'}
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Nurses are not authorized to approve patient transfers', data['error'])

        # Verify status did not change
        tf = Transfer.get_by_id(transfer_id)
        self.assertEqual(tf['status'], 'pending')

    def test_03_backend_rejects_nurse_put_transfer_approval_with_403(self):
        """Verify Nurse attempting PUT /api/v1/transfers/<id>/approve receives HTTP 403 Forbidden."""
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

        res = self.client.put(
            f'/api/v1/transfers/{transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.nurse_token}'},
            json={'remarks': 'Nurse attempting PUT approval'}
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Nurses are not authorized to approve patient transfers', data['error'])

    def test_04_backend_rejects_nurse_decision_approval_with_403(self):
        """Verify Nurse attempting POST /api/v1/decision/approve/<id> receives HTTP 403 Forbidden."""
        rec_id = Recommendation.create(
            patient_id=self.patient_id,
            from_ward='ICU',
            to_ward='HDU',
            recommendation_text='Fit for HDU Transfer',
            score=0,
            status='pending'
        )

        res = self.client.post(
            f'/api/v1/decision/approve/{rec_id}',
            headers={'Authorization': f'Bearer {self.nurse_token}'}
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Nurses are not authorized to approve clinical recommendations', data['error'])

    def test_05_doctor_approval_workflow_succeeds_and_notifies(self):
        """Verify Doctor approval workflow remains fully operational."""
        # Record stable vitals
        Vitals.record(
            patient_id=self.patient_id,
            heart_rate=70.0,
            blood_pressure_sys=120.0,
            respiratory_rate=16.0,
            temperature=36.6,
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

        res = self.client.post(
            f'/api/v1/transfers/{transfer_id}/approve',
            headers={'Authorization': f'Bearer {self.doctor_token}'},
            json={'remarks': 'Doctor authorized transfer'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'approved')

        # Check transfer is approved
        tf = Transfer.get_by_id(transfer_id)
        self.assertEqual(tf['status'], 'approved')


if __name__ == '__main__':
    unittest.main()
