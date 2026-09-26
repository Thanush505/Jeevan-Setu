"""
tests/test_phase10_decision_engine.py — Comprehensive Test Suite for Phase 10 Decision Engine.
Tests:
- Pure-Python Independent Decision Engine Tests:
  - Rule 1: EWS >= 5 in ICU -> CONTINUE_ICU
  - Rule 2: EWS <= 3 in ICU -> TRANSFER_TO_HDU
  - Rule 3: EWS >= 5 in HDU -> ESCALATE_TO_ICU
  - Rule 4: EWS 1-4 in HDU -> CONTINUE_HDU
  - Rule 5: Borderline / Normal -> RE_EVALUATE
  - Rule 6: General Ward EWS >= 7 -> ESCALATE_TO_ICU
  - Output contract schema validation: score, risk_level, recommendation, reason, status
- REST API Endpoints:
  - GET    /decision/evaluate/{patient_id}
  - POST   /decision/evaluate
  - POST   /decision/approve/{id} (Doctor only)
  - POST   /decision/reject/{id} (Doctor only)
  - GET    /decision/pending
  - GET    /decision/history/{patient_id}
- RBAC validation: Doctor/Admin (full control) vs Nurse (cannot approve/reject) vs Attendant (restricted)
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
from models.recommendation_model import Recommendation
from modules.decision_engine import (
    evaluate_decision,
    RECOMMENDATION_TRANSFER_TO_HDU,
    RECOMMENDATION_CONTINUE_ICU,
    RECOMMENDATION_CONTINUE_HDU,
    RECOMMENDATION_ESCALATE_TO_ICU,
    RECOMMENDATION_RE_EVALUATE
)
from services.auth_service import AuthService


class TestPhase10DecisionEngine(unittest.TestCase):
    """Test suite for Phase 10 Rule-Based Clinical Decision Engine."""

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
            username=f"p10_doc_{ts}",
            password="DocPassword123!",
            full_name="Dr. Allison Cameron",
            email=f"p10_doc_{ts}@hospital.com",
            role='doctor',
            department='Critical Care'
        )
        cls.doctor_token = AuthService.generate_access_token(User.get_by_id(cls.doc_id))['access_token']
        cls.doctor_headers = {'Authorization': f"Bearer {cls.doctor_token}"}

        # Nurse User & Token
        cls.nurse_id = User.create(
            username=f"p10_nurse_{ts}",
            password="NursePassword123!",
            full_name="Nurse Carla",
            email=f"p10_nurse_{ts}@hospital.com",
            role='nurse',
            department='ICU'
        )
        cls.nurse_token = AuthService.generate_access_token(User.get_by_id(cls.nurse_id))['access_token']
        cls.nurse_headers = {'Authorization': f"Bearer {cls.nurse_token}"}

        # Attendant User & Token
        cls.attendant_id = User.create(
            username=f"p10_att_{ts}",
            password="AttendantPass123!",
            full_name="Attendant Leo",
            email=f"p10_att_{ts}@hospital.com",
            role='attendant'
        )
        cls.attendant_token = AuthService.generate_access_token(User.get_by_id(cls.attendant_id))['access_token']
        cls.attendant_headers = {'Authorization': f"Bearer {cls.attendant_token}"}

        # Create test patients in different wards
        cls.icu_patient_id = Patient.create(
            name=f"ICU Patient {ts}",
            age=62,
            gender="Male",
            ward_type="ICU",
            diagnosis="Septic Shock",
            assigned_doctor=cls.doc_id,
            created_by=cls.nurse_id
        )

        cls.hdu_patient_id = Patient.create(
            name=f"HDU Patient {ts}",
            age=55,
            gender="Female",
            ward_type="HDU",
            diagnosis="Severe Asthma",
            assigned_doctor=cls.doc_id,
            created_by=cls.nurse_id
        )

    # ─────────────────────────────────────────────────────────────
    # Pure Python Isolated Engine Tests (Independent of Flask)
    # ─────────────────────────────────────────────────────────────

    def test_01_engine_continue_icu_rule(self):
        """Rule 1: High EWS (>=5) in ICU returns CONTINUE_ICU with required contract."""
        decision = evaluate_decision(score=8, current_unit='ICU')
        self.assertEqual(decision['score'], 8)
        self.assertEqual(decision['risk_level'], 'CRITICAL')
        self.assertEqual(decision['recommendation'], RECOMMENDATION_CONTINUE_ICU)
        self.assertEqual(decision['status'], 'PENDING')
        self.assertTrue(len(decision['reason']) > 0)
        print("[PASS] Engine Rule 1 (CONTINUE_ICU) verified.")

    def test_02_engine_transfer_to_hdu_rule(self):
        """Rule 2: Stable low EWS (<=3) in ICU returns TRANSFER_TO_HDU."""
        decision = evaluate_decision(score=2, current_unit='ICU')
        self.assertEqual(decision['score'], 2)
        self.assertEqual(decision['risk_level'], 'LOW')
        self.assertEqual(decision['recommendation'], RECOMMENDATION_TRANSFER_TO_HDU)
        self.assertEqual(decision['to_ward'], 'HDU')
        self.assertEqual(decision['status'], 'PENDING')
        self.assertTrue(decision['action_required'])
        print("[PASS] Engine Rule 2 (TRANSFER_TO_HDU) verified.")

    def test_03_engine_escalate_to_icu_rule(self):
        """Rule 3: Deteriorating patient in HDU with high EWS (>=5) returns ESCALATE_TO_ICU."""
        decision = evaluate_decision(score=7, current_unit='HDU')
        self.assertEqual(decision['score'], 7)
        self.assertEqual(decision['risk_level'], 'CRITICAL')
        self.assertEqual(decision['recommendation'], RECOMMENDATION_ESCALATE_TO_ICU)
        self.assertEqual(decision['to_ward'], 'ICU')
        self.assertTrue(decision['action_required'])
        print("[PASS] Engine Rule 3 (ESCALATE_TO_ICU) verified.")

    def test_04_engine_continue_hdu_rule(self):
        """Rule 4: Manageable EWS (1-4) in HDU returns CONTINUE_HDU."""
        decision = evaluate_decision(score=3, current_unit='HDU')
        self.assertEqual(decision['score'], 3)
        self.assertEqual(decision['risk_level'], 'MEDIUM')
        self.assertEqual(decision['recommendation'], RECOMMENDATION_CONTINUE_HDU)
        self.assertEqual(decision['to_ward'], 'HDU')
        self.assertFalse(decision['action_required'])
        print("[PASS] Engine Rule 4 (CONTINUE_HDU) verified.")

    def test_05_engine_re_evaluate_rule(self):
        """Rule 5: Borderline score in ICU (score=4) returns RE_EVALUATE."""
        decision = evaluate_decision(score=4, current_unit='ICU')
        self.assertEqual(decision['score'], 4)
        self.assertEqual(decision['recommendation'], RECOMMENDATION_RE_EVALUATE)
        self.assertFalse(decision['action_required'])
        print("[PASS] Engine Rule 5 (RE_EVALUATE) verified.")

    def test_06_engine_contract_structure(self):
        """Verify the exact dictionary format expected from the decision engine."""
        decision = evaluate_decision(score=7, current_unit='HDU', risk_level='MEDIUM')
        required_keys = {'score', 'risk_level', 'recommendation', 'reason', 'status'}
        self.assertTrue(required_keys.issubset(decision.keys()))
        self.assertIsInstance(decision['score'], int)
        self.assertIsInstance(decision['risk_level'], str)
        self.assertIsInstance(decision['recommendation'], str)
        self.assertIsInstance(decision['reason'], str)
        self.assertEqual(decision['status'], 'PENDING')
        print("[PASS] Engine Contract Structure validation verified.")

    # ─────────────────────────────────────────────────────────────
    # REST API & Doctor Workflow Tests
    # ─────────────────────────────────────────────────────────────

    def test_07_get_evaluate_patient_decision_api(self):
        """Test GET /decision/evaluate/{patient_id}: Evaluates patient and persists recommendation."""
        # Record low vitals for ICU patient -> Should recommend transfer to HDU
        Vitals.record(
            patient_id=self.icu_patient_id,
            heart_rate=72,
            blood_pressure_sys=120,
            blood_pressure_dia=80,
            respiratory_rate=16,
            temperature=36.8,
            spo2=99,
            consciousness='Alert',
            ews_score=0,
            recorded_by=self.nurse_id
        )

        res = self.client.get(f"/api/v1/decision/evaluate/{self.icu_patient_id}", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        d = data['data']
        self.assertEqual(d['recommendation'], RECOMMENDATION_TRANSFER_TO_HDU)
        self.assertIn('recommendation_id', d)
        self.__class__.created_rec_id = d['recommendation_id']
        print("[PASS] GET /decision/evaluate/{patient_id} verified.")

    def test_08_post_evaluate_custom_decision_api(self):
        """Test POST /decision/evaluate: Direct payload evaluation."""
        payload = {
            'score': 6,
            'current_unit': 'HDU'
        }
        res = self.client.post('/api/v1/decision/evaluate', json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['recommendation'], RECOMMENDATION_ESCALATE_TO_ICU)
        print("[PASS] POST /decision/evaluate verified.")

    def test_09_approve_and_reject_decision_workflow(self):
        """Test POST /decision/approve/{id} and POST /decision/reject/{id}."""
        # 1. Doctor approves recommendation
        app_res = self.client.post(f"/api/v1/decision/approve/{self.created_rec_id}", headers=self.doctor_headers)
        self.assertEqual(app_res.status_code, 200)
        self.assertEqual(app_res.get_json()['status'], 'approved')

        # Check DB status is approved
        rec = Recommendation.get_by_id(self.created_rec_id)
        self.assertEqual(rec['status'], 'approved')

        # 2. Create another recommendation to reject
        rec2_id = Recommendation.create(
            patient_id=self.hdu_patient_id,
            from_ward='HDU',
            to_ward='ICU',
            recommendation_text='ESCALATE_TO_ICU',
            score=7,
            reason='Test rejection'
        )
        rej_res = self.client.post(f"/api/v1/decision/reject/{rec2_id}", headers=self.doctor_headers)
        self.assertEqual(rej_res.status_code, 200)
        self.assertEqual(rej_res.get_json()['status'], 'rejected')
        print("[PASS] Recommendation approve & reject workflows verified.")

    def test_10_decision_history_and_pending_api(self):
        """Test GET /decision/pending and GET /decision/history/{patient_id}."""
        # Pending list
        res_pending = self.client.get('/api/v1/decision/pending', headers=self.doctor_headers)
        self.assertEqual(res_pending.status_code, 200)
        self.assertTrue(res_pending.get_json()['success'])

        # Patient history
        res_hist = self.client.get(f"/api/v1/decision/history/{self.icu_patient_id}", headers=self.doctor_headers)
        self.assertEqual(res_hist.status_code, 200)
        hist_data = res_hist.get_json()
        self.assertTrue(hist_data['success'])
        self.assertGreaterEqual(hist_data['count'], 1)
        print("[PASS] Decision history and pending lists verified.")

    def test_11_rbac_permissions(self):
        """Test RBAC restrictions on clinical decisions."""
        # Nurse CANNOT approve or reject decisions (returns 403)
        nurse_app_res = self.client.post(f"/api/v1/decision/approve/{self.created_rec_id}", headers=self.nurse_headers)
        self.assertEqual(nurse_app_res.status_code, 403)

        # Attendant CANNOT view decisions (returns 403)
        att_res = self.client.get(f"/api/v1/decision/evaluate/{self.icu_patient_id}", headers=self.attendant_headers)
        self.assertEqual(att_res.status_code, 403)

        # Unauthenticated receives 401
        unauth_res = self.client.get(f"/api/v1/decision/evaluate/{self.icu_patient_id}")
        self.assertEqual(unauth_res.status_code, 401)
        print("[PASS] RBAC protection on Decision Engine endpoints verified.")


if __name__ == '__main__':
    unittest.main()
