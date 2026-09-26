"""
tests/test_phase16_analytics.py — Phase 16 Analytics Test Suite.

Tests:
1. GET /analytics/occupancy (ICU/HDU/General occupancy, total/available beds)
2. GET /analytics/transfers (Transfer metrics, transition flows, turnaround time)
3. GET /analytics/resource-utilization (Capacity, critical utilization, maintenance impact)
4. GET /analytics/patient-statistics (Demographics, active ward distribution, age cohorts)
5. GET /analytics/ews-statistics (Risk level distribution, ward averages, parameter impacts)
6. RBAC access control (Admin/Doctor allowed, Unauthorized 401, Attendant 403)
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
from models.ews_score_model import EWSScore
from services.auth_service import AuthService


class TestPhase16Analytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time() * 1000) % 100000

        # Create Admin
        cls.admin_id = User.create(
            username=f"admin_an_{cls.ts}",
            email=f"admin_an_{cls.ts}@hospital.com",
            password="AdminPassword123!",
            role="admin",
            full_name="Administrator Analytics"
        )
        cls.admin = User.get_by_id(cls.admin_id)
        cls.admin_token = AuthService.generate_access_token(cls.admin)['access_token']

        # Create Doctor
        cls.doc_id = User.create(
            username=f"doc_an_{cls.ts}",
            email=f"doc_an_{cls.ts}@hospital.com",
            password="DocPassword123!",
            role="doctor",
            full_name="Dr. Analytics Clinician"
        )
        cls.doctor = User.get_by_id(cls.doc_id)
        cls.doc_token = AuthService.generate_access_token(cls.doctor)['access_token']

        # Create Attendant
        cls.att_id = User.create(
            username=f"att_an_{cls.ts}",
            email=f"att_an_{cls.ts}@hospital.com",
            password="AttPassword123!",
            role="attendant",
            full_name="Attendant Test"
        )
        cls.attendant = User.get_by_id(cls.att_id)
        cls.att_token = AuthService.generate_access_token(cls.attendant)['access_token']

        # Create ICU and HDU Wards & Beds
        cls.icu_ward_id = Ward.create(
            name=f"ICU Analytics {cls.ts}",
            ward_type="ICU",
            total_beds=4,
            floor_number=1
        )
        cls.icu_bed1 = Bed.create(cls.icu_ward_id, f"IB1-{cls.ts % 10000}")
        cls.icu_bed2 = Bed.create(cls.icu_ward_id, f"IB2-{cls.ts % 10000}")

        cls.hdu_ward_id = Ward.create(
            name=f"HDU Analytics {cls.ts}",
            ward_type="HDU",
            total_beds=4,
            floor_number=2
        )
        cls.hdu_bed1 = Bed.create(cls.hdu_ward_id, f"HB1-{cls.ts % 10000}")
        cls.hdu_bed2 = Bed.create(cls.hdu_ward_id, f"HB2-{cls.ts % 10000}")

        # Create Patients
        cls.p1_id = Patient.create(
            name=f"ICU Critical Patient {cls.ts}",
            age=62,
            gender="male",
            diagnosis="Cardiogenic Shock",
            ward_type="ICU",
            ward_id=cls.icu_ward_id,
            bed_id=cls.icu_bed1,
            bed_number=f"IB1-{cls.ts % 10000}",
            assigned_doctor=cls.doc_id
        )

        cls.p2_id = Patient.create(
            name=f"HDU Stepdown Patient {cls.ts}",
            age=34,
            gender="female",
            diagnosis="Post-Operative Recovery",
            ward_type="HDU",
            ward_id=cls.hdu_ward_id,
            bed_id=cls.hdu_bed1,
            bed_number=f"HB1-{cls.ts % 10000}",
            assigned_doctor=cls.doc_id
        )

        # Record vitals & EWS
        v1_id = Vitals.create(
            patient_id=cls.p1_id,
            heart_rate=142,
            blood_pressure_sys=78,
            blood_pressure_dia=48,
            respiratory_rate=30,
            temperature=39.2,
            spo2=88,
            ews_score=9,
            recorded_by=cls.doc_id
        )
        EWSScore.record(cls.p1_id, v1_id, 9, 'CRITICAL', hr_score=3, bp_score=3, rr_score=3)

        v2_id = Vitals.create(
            patient_id=cls.p2_id,
            heart_rate=78,
            blood_pressure_sys=120,
            blood_pressure_dia=80,
            respiratory_rate=16,
            temperature=36.8,
            spo2=99,
            ews_score=0,
            recorded_by=cls.doc_id
        )
        EWSScore.record(cls.p2_id, v2_id, 0, 'LOW', hr_score=0, bp_score=0, rr_score=0)

        # Create a transfer record
        cls.transfer_id = Transfer.request_transfer(
            patient_id=cls.p2_id,
            from_ward="ICU",
            to_ward="HDU",
            reason="Step-down stabilization",
            requested_by=cls.doc_id
        )

    def auth_headers(self, token):
        return {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

    # ─────────────────────────────────────────────────────────
    # 1. Occupancy Analytics
    # ─────────────────────────────────────────────────────────
    def test_01_get_occupancy_analytics(self):
        """Test GET /analytics/occupancy and API alias."""
        res = self.client.get('/analytics/occupancy', headers=self.auth_headers(self.admin_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['metric'], 'occupancy')

        d = data['data']
        self.assertIn('hospital_summary', d)
        self.assertIn('icu_occupancy', d)
        self.assertIn('hdu_occupancy', d)
        self.assertIn('general_occupancy', d)
        self.assertIn('ward_breakdown', d)

        # Verify ICU and HDU occupancy structure
        self.assertIn('total_beds', d['icu_occupancy'])
        self.assertIn('occupied_beds', d['icu_occupancy'])
        self.assertIn('available_beds', d['icu_occupancy'])
        self.assertIn('occupancy_rate_pct', d['icu_occupancy'])

        # Verify API alias
        res_v1 = self.client.get('/api/v1/analytics/occupancy', headers=self.auth_headers(self.doc_token))
        self.assertEqual(res_v1.status_code, 200)
        self.assertTrue(res_v1.get_json()['success'])

    # ─────────────────────────────────────────────────────────
    # 2. Transfer Analytics
    # ─────────────────────────────────────────────────────────
    def test_02_get_transfer_analytics(self):
        """Test GET /analytics/transfers."""
        res = self.client.get('/analytics/transfers', headers=self.auth_headers(self.admin_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['metric'], 'transfers')

        d = data['data']
        self.assertIn('total_transfers', d)
        self.assertIn('status_distribution', d)
        self.assertIn('transition_flows', d)
        self.assertIn('top_transfer_reasons', d)
        self.assertIn('average_turnaround_hours', d)
        self.assertGreaterEqual(d['total_transfers'], 1)

    # ─────────────────────────────────────────────────────────
    # 3. Resource Utilization Analytics
    # ─────────────────────────────────────────────────────────
    def test_03_get_resource_utilization_analytics(self):
        """Test GET /analytics/resource-utilization."""
        res = self.client.get('/analytics/resource-utilization', headers=self.auth_headers(self.admin_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['metric'], 'resource_utilization')

        d = data['data']
        self.assertIn('overall_utilization_rate_pct', d)
        self.assertIn('critical_care_utilization_pct', d)
        self.assertIn('available_critical_beds', d)
        self.assertIn('maintenance_impact_pct', d)
        self.assertIn('high_occupancy_wards', d)

    # ─────────────────────────────────────────────────────────
    # 4. Patient Statistics Analytics
    # ─────────────────────────────────────────────────────────
    def test_04_get_patient_statistics_analytics(self):
        """Test GET /analytics/patient-statistics."""
        res = self.client.get('/analytics/patient-statistics', headers=self.auth_headers(self.admin_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['metric'], 'patient_statistics')

        d = data['data']
        self.assertIn('total_registered_patients', d)
        self.assertIn('active_admitted_patients', d)
        self.assertIn('active_ward_distribution', d)
        self.assertIn('gender_distribution', d)
        self.assertIn('age_cohorts', d)
        self.assertIn('average_age', d)
        self.assertIn('top_admission_diagnoses', d)
        self.assertGreaterEqual(d['total_registered_patients'], 2)

    # ─────────────────────────────────────────────────────────
    # 5. EWS Statistics Analytics
    # ─────────────────────────────────────────────────────────
    def test_05_get_ews_statistics_analytics(self):
        """Test GET /analytics/ews-statistics."""
        res = self.client.get('/analytics/ews-statistics', headers=self.auth_headers(self.admin_token))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['metric'], 'ews_statistics')

        d = data['data']
        self.assertIn('risk_distribution', d)
        self.assertIn('hospital_average_ews', d)
        self.assertIn('ward_average_ews', d)
        self.assertIn('critical_patients_count', d)
        self.assertIn('parameter_impact_breakdown', d)
        self.assertGreaterEqual(d['critical_patients_count'], 1)

    # ─────────────────────────────────────────────────────────
    # 6. RBAC & Security Protections
    # ─────────────────────────────────────────────────────────
    def test_06_rbac_protections(self):
        """Verify unauthorized users receive 401 and Attendants receive 403."""
        # Unauthenticated request
        res_unauth = self.client.get('/analytics/occupancy')
        self.assertEqual(res_unauth.status_code, 401)

        # Attendant role forbidden
        res_att = self.client.get('/analytics/occupancy', headers=self.auth_headers(self.att_token))
        self.assertEqual(res_att.status_code, 403)


if __name__ == '__main__':
    unittest.main()
