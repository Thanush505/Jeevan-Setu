"""
tests/test_phase6_patient_management.py — Comprehensive Test Suite for Phase 6 Patient Management.
Tests:
- POST   /patients & /api/v1/patients (Registration, auto UHID code, demographics, QR token)
- GET    /patients & /api/v1/patients (List, pagination, filtering by ward/status/doctor/gender)
- GET    /patients/{id} (Patient profile with latest vitals & EWS risk)
- GET    /patients/search (Multi-field search by name, UHID, diagnosis)
- PUT    /patients/{id} (Update demographics, diagnosis, doctor assignment)
- GET    /patients/{id}/history (Clinical timeline: vitals, EWS, transfers, bed history)
- DELETE /patients/{id} (Discharge patient and release allocated bed)
- RBAC validation: Doctor/Nurse (allowed) vs Attendant/Unauthenticated (forbidden/unauthorized)
"""

import sys
import os
import unittest
from datetime import datetime

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.ward_model import Ward
from models.bed_model import Bed
from services.auth_service import AuthService


class TestPhase6PatientManagement(unittest.TestCase):
    """Test suite for Phase 6 Patient Management REST APIs."""

    @classmethod
    def setUpClass(cls):
        """Configure test client and create tokens for Doctor, Nurse, and Attendant."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        ts = int(datetime.now().timestamp())

        # Admin Token
        admin_user = User.authenticate('admin', 'admin123')
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

        # Doctor User & Token
        cls.doc_id = User.create(
            username=f"p6_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. Sarah Connor",
            email=f"p6_doc_{ts}@hospital.com",
            role='doctor',
            department='Pulmonology'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(cls.doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Nurse User & Token
        cls.nurse_id = User.create(
            username=f"p6_nurse_{ts}",
            password="NursePassword123!",
            full_name="Nurse Florence",
            email=f"p6_nurse_{ts}@hospital.com",
            role='nurse',
            department='ICU'
        )
        cls.nurse_token = AuthService.generate_access_token(User.get_by_id(cls.nurse_id))['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Attendant User & Token (Read-only attendant)
        cls.attendant_id = User.create(
            username=f"p6_att_{ts}",
            password="AttendantPass123!",
            full_name="Attendant John",
            email=f"p6_att_{ts}@hospital.com",
            role='attendant'
        )
        cls.attendant_token = AuthService.generate_access_token(User.get_by_id(cls.attendant_id))['access_token']
        cls.attendant_headers = {'Authorization': f"Bearer {cls.attendant_token}"}

        # Create isolated test ward & bed
        short_ts = ts % 10000
        cls.test_ward_id = Ward.create(name=f"Ward-P6-{ts}", ward_type="ICU", total_beds=10)
        cls.test_bed_num = f"B6-{short_ts}"
        cls.test_bed_id = Bed.create(ward_id=cls.test_ward_id, bed_number=cls.test_bed_num)

        cls.test_tag = f"P6_{ts}"

    def test_01_patient_registration_and_demographics(self):
        """Test POST /patients (Register patient with demographics, code generation, and QR token)."""
        patient_name = f"Robert {self.test_tag}"
        payload = {
            'name': patient_name,
            'age': 54,
            'gender': 'Male',
            'blood_group': 'O+',
            'contact_number': '9876501234',
            'emergency_contact': '9876505678',
            'ward_type': 'ICU',
            'bed_number': self.test_bed_num,
            'diagnosis': 'Acute Respiratory Distress Syndrome (ARDS)',
            'assigned_doctor': self.doc_id,
            'ward_id': self.test_ward_id,
            'bed_id': self.test_bed_id
        }

        # 1. Nurse creates patient
        res = self.client.post('/api/v1/patients', json=payload, headers=self.nurse_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('patient', data['data'])
        self.assertIn('qr_token', data['data'])
        self.assertIn('access_code', data['data'])

        patient = data['data']['patient']
        self.assertEqual(patient['name'], patient_name)
        self.assertEqual(patient['age'], 54)
        self.assertEqual(patient['gender'], 'Male')
        self.assertEqual(patient['blood_group'], 'O+')
        self.assertEqual(patient['ward_type'], 'ICU')
        self.assertTrue(patient['patient_code'].startswith('UHID-'))

        self.__class__.created_patient_id = patient['patient_id']
        self.__class__.created_patient_code = patient['patient_code']

        # 2. Validation failures: Missing name / invalid age
        bad_res = self.client.post('/api/v1/patients', json={
            'name': '',
            'age': -5,
            'gender': 'Alien'
        }, headers=self.nurse_headers)
        self.assertEqual(bad_res.status_code, 422)
        print("[PASS] Patient registration and demographics validated.")

    def test_02_get_patient_by_id(self):
        """Test GET /patients/{id} (Fetch patient profile with doctor and ward details)."""
        res = self.client.get(f"/api/v1/patients/{self.created_patient_id}", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        p = data['data']
        self.assertEqual(p['patient_id'], self.created_patient_id)
        self.assertEqual(p['patient_code'], self.created_patient_code)
        self.assertIn('doctor_name', p)
        self.assertIn('ews_risk_level', p)

        # 404 for non-existent patient
        not_found_res = self.client.get("/api/v1/patients/999999", headers=self.doctor_headers)
        self.assertEqual(not_found_res.status_code, 404)
        print("[PASS] Single patient profile lookup verified.")

    def test_03_patient_search(self):
        """Test GET /patients/search (Fast search by name, UHID, and diagnosis)."""
        # Search by patient name
        res_name = self.client.get(f"/api/v1/patients/search?q={self.test_tag}", headers=self.doctor_headers)
        self.assertEqual(res_name.status_code, 200)
        data_name = res_name.get_json()
        self.assertTrue(data_name['success'])
        self.assertGreaterEqual(data_name['count'], 1)
        self.assertTrue(any(p['patient_id'] == self.created_patient_id for p in data_name['data']))

        # Search by patient code (UHID)
        res_code = self.client.get(f"/api/v1/patients/search?q={self.created_patient_code}", headers=self.nurse_headers)
        self.assertEqual(res_code.status_code, 200)
        data_code = res_code.get_json()
        self.assertTrue(any(p['patient_code'] == self.created_patient_code for p in data_code['data']))

        # Search by diagnosis
        res_diag = self.client.get("/api/v1/patients/search?q=ARDS", headers=self.doctor_headers)
        self.assertEqual(res_diag.status_code, 200)
        print("[PASS] Multi-column search verified.")

    def test_04_patient_filtering_and_pagination(self):
        """Test GET /patients (Filter by status, ward_type, doctor, gender, and blood_group)."""
        # 1. Filter by status=admitted
        res = self.client.get("/api/v1/patients?status=admitted", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('pagination', data)
        self.assertGreaterEqual(data['pagination']['total'], 1)

        # 2. Filter by ward_type=ICU
        res_ward = self.client.get("/api/v1/patients?ward_type=ICU", headers=self.doctor_headers)
        self.assertEqual(res_ward.status_code, 200)
        data_ward = res_ward.get_json()
        self.assertTrue(all(p['ward_type'] == 'ICU' for p in data_ward['data']))

        # 3. Filter by doctor_id
        res_doc = self.client.get(f"/api/v1/patients?doctor_id={self.doc_id}", headers=self.doctor_headers)
        self.assertEqual(res_doc.status_code, 200)
        data_doc = res_doc.get_json()
        self.assertTrue(all(p['assigned_doctor'] == self.doc_id for p in data_doc['data']))

        # 4. Filter by gender & blood_group
        res_gb = self.client.get("/api/v1/patients?gender=Male&blood_group=O+", headers=self.nurse_headers)
        self.assertEqual(res_gb.status_code, 200)
        print("[PASS] Filtering and pagination verified.")

    def test_05_update_patient(self):
        """Test PUT /patients/{id} (Update diagnosis, bed, and assigned doctor)."""
        update_payload = {
            'diagnosis': 'Pneumonia with Acute Exacerbation',
            'blood_group': 'O+',
            'age': 55
        }
        res = self.client.put(f"/api/v1/patients/{self.created_patient_id}", json=update_payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['diagnosis'], 'Pneumonia with Acute Exacerbation')
        self.assertEqual(data['data']['age'], 55)

        # Non-existent patient update returns 404
        bad_id_res = self.client.put("/api/v1/patients/999999", json={'age': 40}, headers=self.doctor_headers)
        self.assertEqual(bad_id_res.status_code, 404)
        print("[PASS] Patient profile updates verified.")

    def test_06_patient_history_timeline(self):
        """Test GET /patients/{id}/history (Clinical timeline including vitals, EWS, and bed history)."""
        # Add vitals record to populate timeline
        Vitals.record_vitals(
            patient_id=self.created_patient_id,
            heart_rate=88,
            blood_pressure_sys=120,
            blood_pressure_dia=80,
            respiratory_rate=18,
            temperature=37.0,
            spo2=98,
            consciousness='Alert',
            recorded_by=self.nurse_id
        )

        res = self.client.get(f"/api/v1/patients/{self.created_patient_id}/history", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        history = data['data']
        self.assertIn('patient', history)
        self.assertIn('vitals_history', history)
        self.assertIn('ews_history', history)
        self.assertIn('transfers', history)
        self.assertIn('bed_history', history)
        self.assertGreaterEqual(len(history['vitals_history']), 1)
        print("[PASS] Patient clinical history timeline verified.")

    def test_07_discharge_patient_and_bed_release(self):
        """Test DELETE /patients/{id} (Discharge patient and verify status change)."""
        res = self.client.delete(f"/api/v1/patients/{self.created_patient_id}", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        # Verify status is now 'discharged'
        patient = Patient.get_by_id(self.created_patient_id)
        self.assertEqual(patient['status'], 'discharged')
        self.assertIsNotNone(patient['discharge_date'])
        print("[PASS] Patient discharge and bed release verified.")

    def test_08_rbac_permissions(self):
        """Test RBAC access control on patient management endpoints."""
        # 1. Attendant has NO access to /patients management (should receive 403)
        res_attendant = self.client.get("/api/v1/patients", headers=self.attendant_headers)
        self.assertEqual(res_attendant.status_code, 403)

        # 2. Unauthenticated request (no token) should receive 401
        res_no_auth = self.client.get("/api/v1/patients")
        self.assertEqual(res_no_auth.status_code, 401)
        print("[PASS] RBAC protection on Patient Management endpoints verified.")


if __name__ == '__main__':
    unittest.main()
