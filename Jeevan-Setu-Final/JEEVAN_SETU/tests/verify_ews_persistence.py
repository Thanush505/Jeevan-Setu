import sys
import os
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService


class TestEWSPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        user = User.authenticate('admin', 'admin123')
        cls.token = AuthService.generate_access_token(user)['access_token']
        cls.headers = {'Authorization': f'Bearer {cls.token}'}

    def test_screenshot_scenario(self):
        """
        Scenario from screenshot:
        RR: 55 breaths/min (Score 3)
        HR: 80 bpm (Score 0)
        SBP: 55 mmHg (Score 3)
        Temp: 45 °C (Score 2)
        Total EWS: 8, Condition: Critical, Recommendation: Keep in ICU
        """
        payload = {
            'respiratory_rate': 55.0,
            'heart_rate': 80.0,
            'systolic_bp': 55.0,
            'temperature': 45.0
        }
        res = self.client.post('/api/v1/vitals/patient/1/submit', json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        resp_data = res.get_json()['data']

        # Verify UI-returned values
        self.assertEqual(resp_data['scores']['respiratory_rate'], 3)
        self.assertEqual(resp_data['scores']['heart_rate'], 0)
        self.assertEqual(resp_data['scores']['systolic_bp'], 3)
        self.assertEqual(resp_data['scores']['temperature'], 2)
        self.assertEqual(resp_data['total_score'], 8)
        self.assertEqual(resp_data['condition'], 'Critical')
        self.assertEqual(resp_data['recommendation'], 'Keep in ICU')

        # Verify database record
        vital_id = resp_data['vital_id']
        db_ews = db.execute_query('SELECT * FROM ews_scores WHERE vital_id = %s', (vital_id,), fetch=True)[0]
        self.assertEqual(db_ews['rr_score'], 3)
        self.assertEqual(db_ews['hr_score'], 0)
        self.assertEqual(db_ews['bp_score'], 3)
        self.assertEqual(db_ews['temp_score'], 2)
        self.assertEqual(db_ews['total_score'], 8)
        self.assertEqual(db_ews['risk_level'], 'CRITICAL')
        self.assertEqual(db_ews['patient_id'], 1)
        self.assertEqual(db_ews['patient_name'], 'Rajesh Kumar')

    def test_multi_patient_isolation(self):
        """Test multiple patients do not overwrite each other."""
        patients_data = [
            (1, {'respiratory_rate': 16, 'heart_rate': 70, 'systolic_bp': 120, 'temperature': 36.8}, 0, 'LOW'),
            (2, {'respiratory_rate': 22, 'heart_rate': 105, 'systolic_bp': 95, 'temperature': 38.5}, 5, 'CRITICAL'),
            (3, {'respiratory_rate': 10, 'heart_rate': 45, 'systolic_bp': 75, 'temperature': 35.5}, 5, 'CRITICAL')
        ]
        for pid, vitals, expected_total, expected_risk in patients_data:
            res = self.client.post(f'/api/v1/vitals/patient/{pid}/submit', json=vitals, headers=self.headers)
            self.assertEqual(res.status_code, 201)
            data = res.get_json()['data']
            self.assertEqual(data['total_score'], expected_total)

            db_ews = db.execute_query('SELECT * FROM ews_scores WHERE vital_id = %s', (data['vital_id'],), fetch=True)[0]
            self.assertEqual(db_ews['patient_id'], pid)
            self.assertEqual(db_ews['total_score'], expected_total)
            self.assertEqual(db_ews['risk_level'], expected_risk)

    def test_multi_vital_progression(self):
        """Test sequential vitals for the same patient create distinct linked ews_scores."""
        vitals_sequence = [
            {'respiratory_rate': 16, 'heart_rate': 72, 'systolic_bp': 120, 'temperature': 37.0},  # total 0
            {'respiratory_rate': 22, 'heart_rate': 95, 'systolic_bp': 95, 'temperature': 38.2},   # total 5
            {'respiratory_rate': 26, 'heart_rate': 115, 'systolic_bp': 75, 'temperature': 39.5},  # total 9
        ]
        vital_ids = []
        for v in vitals_sequence:
            res = self.client.post('/api/v1/vitals/patient/1/submit', json=v, headers=self.headers)
            self.assertEqual(res.status_code, 201)
            vital_ids.append(res.get_json()['data']['vital_id'])

        # Verify each vital has its own unique ews_score with matching vital_id
        for vid in vital_ids:
            records = db.execute_query('SELECT * FROM ews_scores WHERE vital_id = %s', (vid,), fetch=True)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['vital_id'], vid)
            self.assertEqual(records[0]['patient_id'], 1)


if __name__ == '__main__':
    unittest.main()
