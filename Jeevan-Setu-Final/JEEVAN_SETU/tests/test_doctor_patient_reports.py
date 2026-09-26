"""
tests/test_doctor_patient_reports.py — Comprehensive verification for Doctor Patient Reports page & RBAC
"""

import sys
import os
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from services.auth_service import AuthService


class TestDoctorPatientReports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Doctor 1 (user_id: 2) -> Assigned Patients: 1, 2, 3
        cls.doc1 = User.get_by_id(2)
        cls.token1 = AuthService.generate_access_token(cls.doc1)['access_token']
        cls.headers1 = {'Authorization': f'Bearer {cls.token1}', 'Content-Type': 'application/json'}

        # Doctor 2 (user_id: 3) -> Assigned Patients: 4, 5, 6
        cls.doc2 = User.get_by_id(3)
        cls.token2 = AuthService.generate_access_token(cls.doc2)['access_token']
        cls.headers2 = {'Authorization': f'Bearer {cls.token2}', 'Content-Type': 'application/json'}

        # Doctor 3 (user_id: 4) -> Assigned Patients: 7, 8, 9, 10
        cls.doc3 = User.get_by_id(4)
        cls.token3 = AuthService.generate_access_token(cls.doc3)['access_token']
        cls.headers3 = {'Authorization': f'Bearer {cls.token3}', 'Content-Type': 'application/json'}

        # Admin (user_id: 1) -> All hospital patients
        cls.admin = User.get_by_id(1)
        cls.token_admin = AuthService.generate_access_token(cls.admin)['access_token']
        cls.headers_admin = {'Authorization': f'Bearer {cls.token_admin}', 'Content-Type': 'application/json'}

    def test_01_doctor_1_patient_scoping(self):
        """TEST 1: Doctor 1 (dr_sharma) must ONLY see assigned patients 1, 2, 3."""
        res = self.client.get('/api/v1/patients?limit=100', headers=self.headers1)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        pids = sorted([p['patient_id'] for p in data['data']])
        print(f"\n[TEST 1] Doctor 1 (Dr. Anil Sharma) Patients: {pids}")
        self.assertEqual(pids, [1, 2, 3])

    def test_02_doctor_2_patient_scoping(self):
        """TEST 2: Doctor 2 (dr_patel) must ONLY see assigned patients 4, 5, 6."""
        res = self.client.get('/api/v1/patients?limit=100', headers=self.headers2)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        pids = sorted([p['patient_id'] for p in data['data']])
        print(f"[TEST 2] Doctor 2 (Dr. Kavita Patel) Patients: {pids}")
        self.assertEqual(pids, [4, 5, 6])

    def test_03_doctor_3_patient_scoping(self):
        """TEST 3: Doctor 3 (dr_gupta) must ONLY see assigned patients 7, 8, 9, 10."""
        res = self.client.get('/api/v1/patients?limit=100', headers=self.headers3)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        pids = sorted([p['patient_id'] for p in data['data']])
        print(f"[TEST 3] Doctor 3 (Dr. Rajiv Gupta) Patients: {pids}")
        self.assertEqual(pids, [7, 8, 9, 10])

    def test_04_doctor_1_authorized_pdf_generation(self):
        """TEST 6: Doctor 1 can generate single and multi-patient PDF reports for assigned patients."""
        res = self.client.post('/api/v1/reports/patients/pdf', headers=self.headers1, json={
            'patient_ids': [1, 2],
            'sections': ['vitals', 'ews', 'cds']
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'application/pdf')
        self.assertGreater(len(res.data), 1000)
        print(f"[TEST 6] Doctor 1 Generated multi-patient PDF: {len(res.data)} bytes")

    def test_05_doctor_1_cross_patient_report_rejection(self):
        """TEST 4 & 5: Doctor 1 requesting report for patient 4 (assigned to Doctor 2) must receive 403 Forbidden."""
        # Multi-patient endpoint with unauthorized patient
        res = self.client.post('/api/v1/reports/patients/pdf', headers=self.headers1, json={
            'patient_ids': [1, 4],
            'sections': ['vitals']
        })
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn('Access denied', data.get('error', ''))
        print(f"[TEST 4] Doctor 1 requesting Patient 4 returned 403 Forbidden: {data.get('error')}")

        # Single patient endpoint
        res_single = self.client.get('/api/v1/reports/patient/4', headers=self.headers1)
        self.assertEqual(res_single.status_code, 403)

        # Preview generation endpoint
        res_prev = self.client.post('/api/v1/reports/generate/patient-report', headers=self.headers1, json={
            'patient_ids': [4],
            'sections': ['vitals']
        })
        self.assertEqual(res_prev.status_code, 403)

    def test_06_admin_clinical_reports_unaffected(self):
        """Admin retains hospital-wide multi-patient access across all doctors' patients."""
        res = self.client.post('/api/v1/reports/patients/pdf', headers=self.headers_admin, json={
            'patient_ids': [1, 4, 7],
            'sections': ['vitals', 'ews', 'cds', 'transfers', 'timeline']
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'application/pdf')
        print(f"[TEST 24] Admin cross-doctor patient PDF generation SUCCESS: {len(res.data)} bytes")

    def test_07_doctor_single_patient_pdf(self):
        """Doctor 2 generating single patient PDF for assigned Patient 4."""
        res = self.client.post('/api/v1/reports/patients/pdf', headers=self.headers2, json={
            'patient_ids': [4],
            'sections': ['vitals', 'ews']
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'application/pdf')
        disp = res.headers.get('Content-Disposition', '')
        self.assertIn('Sunita_Rao', disp)
        print(f"[TEST 7] Doctor 2 single-patient PDF filename: {disp}")


if __name__ == '__main__':
    unittest.main()
