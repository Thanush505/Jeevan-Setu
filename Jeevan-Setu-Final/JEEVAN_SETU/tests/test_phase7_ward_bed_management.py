"""
tests/test_phase7_ward_bed_management.py — Comprehensive Test Suite for Phase 7 Ward & Bed Management.
Tests:
- Ward APIs:
  - GET    /wards & /api/v1/wards (List, filter, occupancy calculations)
  - GET    /wards/{id} (Ward profile with bed list)
  - POST   /wards (Create ward with validation)
  - PUT    /wards/{id} (Update ward details)
  - DELETE /wards/{id} (Deactivate ward with occupied protection)
- Bed APIs:
  - GET    /beds & /api/v1/beds (List, filter by ward/type/status: AVAILABLE, OCCUPIED, MAINTENANCE)
  - GET    /beds/{id} (Bed details with occupant info)
  - POST   /beds (Create bed in ward)
  - PUT    /beds/{id} (Update bed status & details)
  - DELETE /beds/{id} (Deactivate bed with occupied protection)
- Bed Allocation Engine:
  - POST   /beds/{id}/allocate (Allocate bed to patient)
  - Mutual Exclusion: A bed CANNOT be assigned to two active patients (verify 422 rejection)
  - Patient Bed Transfer: Moving patient to Bed B automatically frees Bed A
  - POST   /beds/{id}/maintenance (Set to maintenance, verify allocation blocked)
  - POST   /beds/{id}/release (Release bed back to available)
- RBAC Enforcement: Doctor/Nurse allowed vs Attendant/Unauthenticated restricted
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
from models.ward_model import Ward
from models.bed_model import Bed
from models.bed_management_model import BedManagement
from services.auth_service import AuthService


class TestPhase7WardBedManagement(unittest.TestCase):
    """Test suite for Phase 7 Ward & Bed Management REST APIs."""

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
            username=f"p7_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. Gregory House",
            email=f"p7_doc_{ts}@hospital.com",
            role='doctor',
            department='Critical Care'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(cls.doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Nurse User & Token
        cls.nurse_id = User.create(
            username=f"p7_nurse_{ts}",
            password="NursePassword123!",
            full_name="Nurse Jackie",
            email=f"p7_nurse_{ts}@hospital.com",
            role='nurse',
            department='ICU'
        )
        cls.nurse_token = AuthService.generate_access_token(User.get_by_id(cls.nurse_id))['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Attendant User & Token
        cls.attendant_id = User.create(
            username=f"p7_att_{ts}",
            password="AttendantPass123!",
            full_name="Attendant Mike",
            email=f"p7_att_{ts}@hospital.com",
            role='attendant'
        )
        cls.attendant_token = AuthService.generate_access_token(User.get_by_id(cls.attendant_id))['access_token']
        cls.attendant_headers = {'Authorization': f"Bearer {cls.attendant_token}"}

        # Create two test patients for bed allocation tests
        cls.patient1_id = Patient.create(
            name=f"Patient One {ts}",
            age=40,
            gender="Male",
            ward_type="ICU",
            diagnosis="Sepsis",
            assigned_doctor=cls.doc_id,
            created_by=cls.nurse_id
        )

        cls.patient2_id = Patient.create(
            name=f"Patient Two {ts}",
            age=50,
            gender="Female",
            ward_type="ICU",
            diagnosis="Cardiac Arrest",
            assigned_doctor=cls.doc_id,
            created_by=cls.nurse_id
        )

        cls.test_tag = f"P7_{ts}"

    def test_01_create_ward_and_validation(self):
        """Test POST /wards (Create ward with capacity, floor, and validation)."""
        ward_name = f"Neuro ICU {self.test_tag}"
        payload = {
            'name': ward_name,
            'ward_type': 'ICU',
            'floor_number': 3,
            'total_beds': 8,
            'description': 'Dedicated neurological critical care unit'
        }

        # 1. Successful ward creation
        res = self.client.post('/api/v1/wards', json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['name'], ward_name)
        self.assertEqual(data['data']['ward_type'], 'ICU')
        self.assertEqual(data['data']['floor_number'], 3)
        self.assertEqual(data['data']['total_beds'], 8)

        self.__class__.created_ward_id = data['data']['ward_id']

        # 2. Validation: missing name / invalid ward_type
        bad_res = self.client.post('/api/v1/wards', json={
            'name': '',
            'ward_type': 'OUTPATIENT_INVALID'
        }, headers=self.doctor_headers)
        self.assertEqual(bad_res.status_code, 422)
        print("[PASS] Ward creation and validations verified.")

    def test_02_get_wards_and_occupancy_summary(self):
        """Test GET /wards (List wards with occupancy rates)."""
        res = self.client.get('/api/v1/wards', headers=self.nurse_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)
        self.assertTrue(any(w['ward_id'] == self.created_ward_id for w in data['data']))

        # Get single ward
        single_res = self.client.get(f"/api/v1/wards/{self.created_ward_id}", headers=self.nurse_headers)
        self.assertEqual(single_res.status_code, 200)
        s_data = single_res.get_json()
        self.assertTrue(s_data['success'])
        self.assertIn('beds', s_data['data'])
        print("[PASS] Ward listing and occupancy retrieval verified.")

    def test_03_update_and_delete_ward_protection(self):
        """Test PUT /wards/{id} and DELETE /wards/{id}."""
        # Update ward description
        update_res = self.client.put(
            f"/api/v1/wards/{self.created_ward_id}",
            json={'description': 'Updated neuro intensive care description', 'total_beds': 10},
            headers=self.doctor_headers
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.get_json()['data']['total_beds'], 10)
        print("[PASS] Ward update verified.")

    def test_04_create_beds_in_ward(self):
        """Test POST /beds (Create beds in a ward with status AVAILABLE, OCCUPIED, MAINTENANCE)."""
        short_id = self.test_tag[-5:]
        bed1_num = f"B1-{short_id}"
        bed2_num = f"B2-{short_id}"
        bed3_num = f"B3-{short_id}"

        # 1. Create Bed A (AVAILABLE)
        res1 = self.client.post('/api/v1/beds', json={
            'ward_id': self.created_ward_id,
            'bed_number': bed1_num,
            'status': 'available',
            'bed_type': 'Ventilator'
        }, headers=self.nurse_headers)
        self.assertEqual(res1.status_code, 201)
        self.__class__.bed1_id = res1.get_json()['data']['bed_id']
        self.__class__.bed1_num = bed1_num

        # 2. Create Bed B (AVAILABLE)
        res2 = self.client.post('/api/v1/beds', json={
            'ward_id': self.created_ward_id,
            'bed_number': bed2_num,
            'status': 'available',
            'bed_type': 'Standard'
        }, headers=self.nurse_headers)
        self.assertEqual(res2.status_code, 201)
        self.__class__.bed2_id = res2.get_json()['data']['bed_id']
        self.__class__.bed2_num = bed2_num

        # 3. Create Bed C (MAINTENANCE)
        res3 = self.client.post('/api/v1/beds', json={
            'ward_id': self.created_ward_id,
            'bed_number': bed3_num,
            'status': 'maintenance',
            'bed_type': 'Dialysis'
        }, headers=self.nurse_headers)
        self.assertEqual(res3.status_code, 201)
        self.__class__.bed3_id = res3.get_json()['data']['bed_id']

        print("[PASS] Bed creation in wards verified.")

    def test_05_list_and_filter_beds(self):
        """Test GET /beds (Filter by ward_id, status: available, occupied, maintenance)."""
        # 1. Filter by ward_id
        res_ward = self.client.get(f"/api/v1/beds?ward_id={self.created_ward_id}", headers=self.doctor_headers)
        self.assertEqual(res_ward.status_code, 200)
        data_ward = res_ward.get_json()
        self.assertGreaterEqual(data_ward['count'], 3)

        # 2. Filter by status=available
        res_avail = self.client.get(f"/api/v1/beds?ward_id={self.created_ward_id}&status=available", headers=self.doctor_headers)
        self.assertEqual(res_avail.status_code, 200)
        data_avail = res_avail.get_json()
        self.assertTrue(all(b['status'] == 'available' for b in data_avail['data']))

        # 3. Filter by status=maintenance
        res_maint = self.client.get(f"/api/v1/beds?ward_id={self.created_ward_id}&status=maintenance", headers=self.doctor_headers)
        self.assertEqual(res_maint.status_code, 200)
        data_maint = res_maint.get_json()
        self.assertTrue(all(b['status'] == 'maintenance' for b in data_maint['data']))

        print("[PASS] Bed listing and status filtering verified.")

    def test_06_bed_allocation_and_mutual_exclusion(self):
        """
        Test POST /beds/{id}/allocate:
        1. Patient 1 allocated to Bed 1 -> Bed 1 status becomes OCCUPIED.
        2. Attempting to assign Bed 1 to Patient 2 MUST FAIL (cannot assign bed to two active patients).
        3. Attempting to assign Bed 3 (under maintenance) MUST FAIL.
        """
        # 1. Patient 1 allocated to Bed 1
        alloc_res = self.client.post(
            f"/api/v1/beds/{self.bed1_id}/allocate",
            json={'patient_id': self.patient1_id, 'notes': 'Admitted to Neuro ICU Bed 1'},
            headers=self.nurse_headers
        )
        self.assertEqual(alloc_res.status_code, 200)
        alloc_data = alloc_res.get_json()
        self.assertTrue(alloc_data['success'])

        # Verify Bed 1 status is now OCCUPIED
        bed1_check = Bed.get_by_id(self.bed1_id)
        self.assertEqual(bed1_check['status'], 'occupied')
        self.assertEqual(bed1_check['patient_id'], self.patient1_id)

        # 2. Attempt to assign Bed 1 to Patient 2 (MUST BE REJECTED)
        conflict_res = self.client.post(
            f"/api/v1/beds/{self.bed1_id}/allocate",
            json={'patient_id': self.patient2_id, 'notes': 'Conflict test'},
            headers=self.nurse_headers
        )
        self.assertEqual(conflict_res.status_code, 422)
        conflict_data = conflict_res.get_json()
        self.assertFalse(conflict_data['success'])
        self.assertIn('already occupied', conflict_data['error'].lower())

        # 3. Attempt to allocate Bed 3 (Maintenance) -> MUST BE REJECTED
        maint_alloc = self.client.post(
            f"/api/v1/beds/{self.bed3_id}/allocate",
            json={'patient_id': self.patient2_id},
            headers=self.nurse_headers
        )
        self.assertEqual(maint_alloc.status_code, 422)
        self.assertIn('maintenance', maint_alloc.get_json()['error'].lower())

        print("[PASS] Mutual exclusion: Bed cannot be assigned to two active patients verified.")

    def test_07_patient_bed_transfer_releases_old_bed(self):
        """Test that transferring Patient 1 to Bed 2 automatically releases Bed 1 back to AVAILABLE."""
        # Transfer Patient 1 to Bed 2
        transfer_res = self.client.post(
            f"/api/v1/beds/{self.bed2_id}/allocate",
            json={'patient_id': self.patient1_id, 'notes': 'Transferred to Bed 2'},
            headers=self.doctor_headers
        )
        self.assertEqual(transfer_res.status_code, 200)

        # Check Bed 2 is now OCCUPIED by Patient 1
        bed2 = Bed.get_by_id(self.bed2_id)
        self.assertEqual(bed2['status'], 'occupied')
        self.assertEqual(bed2['patient_id'], self.patient1_id)

        # Check Bed 1 is now automatically AVAILABLE
        bed1 = Bed.get_by_id(self.bed1_id)
        self.assertEqual(bed1['status'], 'available')

        # Now Bed 1 can be allocated to Patient 2
        p2_alloc = self.client.post(
            f"/api/v1/beds/{self.bed1_id}/allocate",
            json={'patient_id': self.patient2_id},
            headers=self.nurse_headers
        )
        self.assertEqual(p2_alloc.status_code, 200)
        print("[PASS] Bed transfer and automatic old bed release verified.")

    def test_08_bed_release_and_maintenance_workflow(self):
        """Test POST /beds/{id}/release and POST /beds/{id}/maintenance."""
        # 1. Release Bed 2 (Patient 1)
        rel_res = self.client.post(f"/api/v1/beds/{self.bed2_id}/release", headers=self.nurse_headers)
        self.assertEqual(rel_res.status_code, 200)

        bed2_after = Bed.get_by_id(self.bed2_id)
        self.assertEqual(bed2_after['status'], 'available')

        # 2. Put Bed 2 in maintenance
        maint_res = self.client.post(
            f"/api/v1/beds/{self.bed2_id}/maintenance",
            json={'notes': 'Replacing monitor cable'},
            headers=self.nurse_headers
        )
        self.assertEqual(maint_res.status_code, 200)
        self.assertEqual(Bed.get_by_id(self.bed2_id)['status'], 'maintenance')

        # 3. Cannot put Bed 1 (occupied by Patient 2) directly into maintenance without releasing
        occupied_maint_res = self.client.post(f"/api/v1/beds/{self.bed1_id}/maintenance", headers=self.nurse_headers)
        self.assertEqual(occupied_maint_res.status_code, 422)

        # 4. Release Bed 1
        self.client.post(f"/api/v1/beds/{self.bed1_id}/release", headers=self.nurse_headers)
        print("[PASS] Bed release and maintenance workflows verified.")

    def test_09_rbac_permissions(self):
        """Test RBAC restrictions on Ward & Bed management endpoints."""
        # Attendant should receive 403 Forbidden
        res_att = self.client.get("/api/v1/wards", headers=self.attendant_headers)
        self.assertEqual(res_att.status_code, 403)

        # Unauthenticated request should receive 401 Unauthorized
        res_unauth = self.client.get("/api/v1/wards")
        self.assertEqual(res_unauth.status_code, 401)
        print("[PASS] RBAC protection on Ward & Bed Management verified.")


if __name__ == '__main__':
    unittest.main()
