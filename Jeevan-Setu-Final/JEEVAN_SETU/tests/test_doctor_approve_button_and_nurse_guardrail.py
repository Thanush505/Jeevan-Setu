import unittest
import json
import sys
import os

# Add JEEVAN_SETU root to sys.path
sys.path.insert(0, r'd:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU')

from app import create_app
from models.user_model import User
from models.patient_model import Patient
from models.recommendation_model import Recommendation
from models.transfer_model import Transfer
from services.auth_service import AuthService

class TestDoctorApproveButtonAndNurseGuardrail(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        cls.doctor = User.get_by_username('doctor')
        if not cls.doctor:
            cls.doctor = User.get_by_username('dr_rahul')
        cls.nurse = User.get_by_username('nurse')
        if not cls.nurse:
            cls.nurse = User.get_by_username('nurse_priya')

        cls.doctor_token = AuthService.generate_access_token(cls.doctor)['access_token'] if cls.doctor else ''
        cls.nurse_token = AuthService.generate_access_token(cls.nurse)['access_token'] if cls.nurse else ''

    def test_01_global_alert_manager_code_structure(self):
        """Verify global_alert_manager.js has role-aware actions and strict Nurse restrictions."""
        js_path = r'd:\Major_Project\JSF\Jeevan-Setu-Final\Jeevan_setu_frontend\global_alert_manager.js'
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Doctor has approve transfer button
        self.assertIn('btn-approve-transfer', js_content)
        self.assertIn('Approve Transfer', js_content)

        # Nurse branch strictly has NO approve transfer button
        self.assertIn('// Nurse View: Review & Dismiss ONLY', js_content)

        # Confirm isNursePortal forces isDoctor to false and isNurse to true
        self.assertIn('if (isNursePortal)', js_content)
        self.assertIn('isNurse = true', js_content)
        self.assertIn('isDoctor = false', js_content)

    def test_02_nurse_cannot_approve_transfer_backend(self):
        """Verify backend returns 403 Forbidden when a nurse attempts transfer approval."""
        if not self.nurse_token:
            self.skipTest('Nurse token not available')

        headers = {
            'Authorization': f'Bearer {self.nurse_token}',
            'Content-Type': 'application/json'
        }
        res = self.client.post('/api/v1/transfers/1/approve', headers=headers, json={'remarks': 'Nurse attempt'})
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data.decode('utf-8'))
        self.assertFalse(data.get('success'))
        self.assertIn('Permission denied', data.get('error', ''))

    def test_03_nurse_cannot_approve_decision_backend(self):
        """Verify backend returns 403 Forbidden when a nurse attempts decision approval."""
        if not self.nurse_token:
            self.skipTest('Nurse token not available')

        headers = {
            'Authorization': f'Bearer {self.nurse_token}',
            'Content-Type': 'application/json'
        }
        res = self.client.post('/api/v1/decision/approve/1', headers=headers, json={'remarks': 'Nurse attempt'})
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data.decode('utf-8'))
        self.assertFalse(data.get('success'))
        self.assertIn('Permission denied', data.get('error', ''))

    def test_04_global_feed_doctor_role_capabilities(self):
        """Verify global feed returns can_approve_transfers=True for doctor and False for nurse."""
        if self.doctor_token:
            res_doc = self.client.get('/api/v1/alerts/global-feed', headers={'Authorization': f'Bearer {self.doctor_token}'})
            data_doc = json.loads(res_doc.data.decode('utf-8'))
            self.assertTrue(data_doc.get('can_approve_transfers'))
            self.assertEqual(data_doc.get('role'), 'doctor')

        if self.nurse_token:
            res_nurse = self.client.get('/api/v1/alerts/global-feed', headers={'Authorization': f'Bearer {self.nurse_token}'})
            data_nurse = json.loads(res_nurse.data.decode('utf-8'))
            self.assertFalse(data_nurse.get('can_approve_transfers'))
            self.assertEqual(data_nurse.get('role'), 'nurse')

if __name__ == '__main__':
    unittest.main()
