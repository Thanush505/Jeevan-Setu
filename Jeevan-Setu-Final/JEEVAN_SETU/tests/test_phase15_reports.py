"""
tests/test_phase15_reports.py — Phase 15 Backend Reports Test Suite.

Tests:
1. Patient Report (JSON, CSV, PDF)
2. Transfer Report (JSON, CSV, PDF)
3. Resource Utilization Report (JSON, CSV, PDF)
4. EWS History Report (JSON, CSV, PDF)
5. Report metadata database persistence & retrieval
6. RBAC permissions (Doctor/Admin allowed, Unauthorized 401, Attendant 403)
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
from models.ward_model import Ward
from models.bed_model import Bed
from models.vitals_model import Vitals
from models.transfer_model import Transfer
from models.report_model import Report
from services.auth_service import AuthService


class TestPhase15Reports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000) % 100000

        # Create Doctor
        cls.doc_id = User.create(
            username=f"doc_rep_{cls.ts}",
            email=f"doc_rep_{cls.ts}@hospital.com",
            password="DocPassword123!",
            role="doctor",
            full_name="Dr. Report Tester"
        )
        cls.doctor = User.get_by_id(cls.doc_id)
        cls.doc_token = AuthService.generate_access_token(cls.doctor)['access_token']

        # Create Attendant
        cls.att_id = User.create(
            username=f"att_rep_{cls.ts}",
            email=f"att_rep_{cls.ts}@hospital.com",
            password="AttPassword123!",
            role="attendant",
            full_name="Attendant Tester"
        )
        cls.attendant = User.get_by_id(cls.att_id)
        cls.att_token = AuthService.generate_access_token(cls.attendant)['access_token']

        # Create Ward & Beds
        cls.ward_id = Ward.create(
            name=f"Report Ward {cls.ts}",
            ward_type="ICU",
            total_beds=10,
            floor_number=2
        )
        cls.bed1_id = Bed.create(cls.ward_id, f"RB1-{cls.ts % 10000}")
        cls.bed2_id = Bed.create(cls.ward_id, f"RB2-{cls.ts % 10000}")

        # Create Patient
        cls.patient_id = Patient.create(
            name=f"Report Patient {cls.ts}",
            age=48,
            gender="female",
            blood_group="O+",
            diagnosis="Sepsis & Pneumonia",
            ward_type="ICU",
            ward_id=cls.ward_id,
            bed_id=cls.bed1_id,
            bed_number=f"RB1-{cls.ts % 10000}",
            assigned_doctor=cls.doc_id
        )

        # Record serial vitals for EWS and Patient reports
        Vitals.create(
            patient_id=cls.patient_id,
            heart_rate=125,
            blood_pressure_sys=88,
            blood_pressure_dia=58,
            respiratory_rate=26,
            temperature=38.9,
            spo2=92,
            ews_score=8,
            recorded_by=cls.doc_id
        )
        Vitals.create(
            patient_id=cls.patient_id,
            heart_rate=98,
            blood_pressure_sys=112,
            blood_pressure_dia=72,
            respiratory_rate=18,
            temperature=37.2,
            spo2=97,
            ews_score=2,
            recorded_by=cls.doc_id
        )

        # Create a transfer record for transfer reports
        cls.transfer_id = Transfer.request_transfer(
            patient_id=cls.patient_id,
            from_ward="ICU",
            to_ward="HDU",
            from_bed_id=cls.bed1_id,
            to_bed_id=cls.bed2_id,
            from_bed_number=f"RB1-{cls.ts % 10000}",
            to_bed_number=f"RB2-{cls.ts % 10000}",
            reason="Clinical stabilization",
            requested_by=cls.doc_id
        )

    def auth_headers(self, token):
        return {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

    # ─────────────────────────────────────────────────────────
    # 1. Patient Report
    # ─────────────────────────────────────────────────────────
    def test_01_patient_report_json(self):
        """Test GET /reports/patient/{id} (JSON format)."""
        res = self.client.get(
            f'/reports/patient/{self.patient_id}',
            headers=self.auth_headers(self.doc_token)
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['report_type'], 'patient')
        self.assertIn('patient', data['data'])
        self.assertEqual(data['data']['patient']['name'], f"Report Patient {self.ts}")
        self.assertIn('vitals_summary', data['data'])
        self.assertGreaterEqual(data['data']['total_readings'], 2)

    def test_02_patient_report_csv(self):
        """Test GET /reports/patient/{id}?format=csv."""
        res = self.client.get(
            f'/reports/patient/{self.patient_id}?format=csv',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)
        self.assertIn('attachment; filename=', res.headers.get('Content-Disposition', ''))
        csv_text = res.data.decode('utf-8')
        self.assertIn("JEEVAN SETU PATIENT CLINICAL REPORT", csv_text)
        self.assertIn(f"Report Patient {self.ts}", csv_text)

    def test_03_patient_report_pdf(self):
        """Test GET /reports/patient/{id}?format=pdf."""
        res = self.client.get(
            f'/reports/patient/{self.patient_id}?format=pdf',
            headers={'Authorization': f'Bearer {self.doc_token}'}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/pdf', res.content_type)
        self.assertIn('attachment; filename=', res.headers.get('Content-Disposition', ''))
        self.assertTrue(res.data.startswith(b'%PDF'))
        self.assertGreater(len(res.data), 500)

    # ─────────────────────────────────────────────────────────
    # 2. Transfer Report
    # ─────────────────────────────────────────────────────────
    def test_04_transfer_report_json_and_formats(self):
        """Test GET /reports/transfers across JSON, CSV, and PDF formats."""
        # JSON
        res_json = self.client.get('/reports/transfers', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_json.status_code, 200)
        data = res_json.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['report_type'], 'transfers')
        self.assertIn('summary', data['data'])
        self.assertIn('transfers', data['data'])

        # CSV
        res_csv = self.client.get('/reports/transfers?format=csv', headers={'Authorization': f'Bearer {self.doc_token}'})
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn('text/csv', res_csv.content_type)
        self.assertIn("PATIENT TRANSFER REPORT", res_csv.data.decode('utf-8'))

        # PDF
        res_pdf = self.client.get('/reports/transfers?format=pdf', headers={'Authorization': f'Bearer {self.doc_token}'})
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(res_pdf.data.startswith(b'%PDF'))

    # ─────────────────────────────────────────────────────────
    # 3. Resource Utilization Report
    # ─────────────────────────────────────────────────────────
    def test_05_resource_utilization_report(self):
        """Test GET /reports/resource-utilization (JSON, CSV, PDF)."""
        # JSON
        res = self.client.get('/reports/resource-utilization', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['report_type'], 'resource_utilization')
        self.assertIn('hospital_summary', data['data'])
        self.assertIn('ward_breakdown', data['data'])
        self.assertIn('overall_occupancy_rate_pct', data['data']['hospital_summary'])

        # CSV
        res_csv = self.client.get('/reports/resource-utilization?format=csv', headers={'Authorization': f'Bearer {self.doc_token}'})
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("RESOURCE UTILIZATION REPORT", res_csv.data.decode('utf-8'))

        # PDF
        res_pdf = self.client.get('/reports/resource-utilization?format=pdf', headers={'Authorization': f'Bearer {self.doc_token}'})
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(res_pdf.data.startswith(b'%PDF'))

    # ─────────────────────────────────────────────────────────
    # 4. EWS History Report
    # ─────────────────────────────────────────────────────────
    def test_06_ews_history_report(self):
        """Test GET /reports/ews/{patient_id} (JSON, CSV, PDF)."""
        # JSON
        res = self.client.get(f'/reports/ews/{self.patient_id}', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['report_type'], 'ews')
        self.assertIn('ews_stats', data['data'])
        self.assertIn('history', data['data'])
        self.assertEqual(data['data']['ews_stats']['peak_score'], 8)

        # CSV
        res_csv = self.client.get(f'/reports/ews/{self.patient_id}?format=csv', headers={'Authorization': f'Bearer {self.doc_token}'})
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("EWS LONGITUDINAL REPORT", res_csv.data.decode('utf-8'))

        # PDF
        res_pdf = self.client.get(f'/reports/ews/{self.patient_id}?format=pdf', headers={'Authorization': f'Bearer {self.doc_token}'})
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(res_pdf.data.startswith(b'%PDF'))

    # ─────────────────────────────────────────────────────────
    # 5. Metadata Database Persistence & API Aliases
    # ─────────────────────────────────────────────────────────
    def test_07_metadata_stored_in_database(self):
        """Verify report metadata records are saved in the reports table."""
        res = self.client.get('/reports/history', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['count'], 0)

        # Check single report view
        first_report_id = data['data'][0]['report_id']
        view_res = self.client.get(f'/reports/view/{first_report_id}', headers=self.auth_headers(self.doc_token))
        self.assertEqual(view_res.status_code, 200)
        self.assertTrue(view_res.get_json()['success'])

        # Check /api/v1/reports alias
        v1_res = self.client.get(f'/api/v1/reports/patient/{self.patient_id}', headers=self.auth_headers(self.doc_token))
        self.assertEqual(v1_res.status_code, 200)
        self.assertTrue(v1_res.get_json()['success'])

    # ─────────────────────────────────────────────────────────
    # 6. RBAC & Security Protections
    # ─────────────────────────────────────────────────────────
    def test_08_rbac_restrictions(self):
        """Verify unauthorized users are rejected with 401 and Attendants with 403."""
        # Unauthenticated request
        res_unauth = self.client.get(f'/reports/patient/{self.patient_id}')
        self.assertEqual(res_unauth.status_code, 401)

        # Attendant role forbidden
        res_att = self.client.get(f'/reports/patient/{self.patient_id}', headers=self.auth_headers(self.att_token))
        self.assertEqual(res_att.status_code, 403)


if __name__ == '__main__':
    unittest.main()
