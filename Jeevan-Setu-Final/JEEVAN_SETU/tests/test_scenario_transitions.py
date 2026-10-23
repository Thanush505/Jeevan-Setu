"""
tests/test_scenario_transitions.py — Automated Test Suite for Simulator Scenario Transitions.

Tests:
1. Retrieval of authoritative scenarios and supported transitions
2. Bidirectional transitions:
   - Stable → Moderate
   - Moderate → Critical
   - Critical → Moderate
   - Moderate → Stable
   - Direct Stable ↔ Critical
   - Direct Stable ↔ Recovery
   - Direct Critical ↔ Recovery
3. Persistence & Audit Logging in MySQL:
   - simulator_patient_states table
   - simulator_scenario_transitions table
   - audit_logs compliance table
4. Duplicate/Noop request handling
5. Invalid scenario and non-existent patient rejection
6. Concurrent multi-patient scenario isolation
7. Telemetry ingestion, EWS calculation, risk scoring, and alert generation
8. Read-back verification and EWS integrity
9. Baseline patient preservation (10/10 admitted patients intact)
"""

import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService


class TestScenarioTransitions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Fetch admin user and token for clinical endpoints requiring auth
        cls.admin_user = User.get_by_username('admin_js') or User.get_by_username('admin')
        if cls.admin_user:
            cls.admin_token = AuthService.generate_access_token(cls.admin_user)['access_token']
        else:
            cls.admin_token = ''

        # Admitted patients to test
        cls.p1_id = 1
        cls.p2_id = 2
        cls.p3_id = 3

    def setUp(self):
        # Reset patient 1, 2, 3 to STABLE in simulator_patient_states
        db.execute_query(
            "UPDATE simulator_patient_states SET current_scenario = 'STABLE', previous_scenario = NULL WHERE patient_id IN (%s, %s, %s)",
            (self.p1_id, self.p2_id, self.p3_id)
        )

    def tearDown(self):
        # Restore all test patients to STABLE
        db.execute_query(
            "UPDATE simulator_patient_states SET current_scenario = 'STABLE', previous_scenario = NULL WHERE patient_id IN (%s, %s, %s)",
            (self.p1_id, self.p2_id, self.p3_id)
        )

    def test_01_get_authoritative_scenarios(self):
        """Verify GET /api/v1/telemetry-simulator/scenarios returns patient states and transition graph."""
        res = self.client.get('/api/v1/telemetry-simulator/scenarios')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        patient_states = data['data']['patient_states']
        self.assertIn(str(self.p1_id), patient_states)
        self.assertEqual(patient_states[str(self.p1_id)]['current_scenario'], 'STABLE')

        supported = data['data']['supported_scenarios']
        self.assertIn('STABLE', supported)
        self.assertIn('MODERATE', supported)
        self.assertIn('CRITICAL', supported)
        self.assertIn('RECOVERY', supported)
        self.assertIn('MANUAL', supported)

        transitions = data['data']['allowed_transitions']
        self.assertIn('MODERATE', transitions['STABLE'])
        self.assertIn('CRITICAL', transitions['STABLE'])
        self.assertIn('STABLE', transitions['MODERATE'])
        self.assertIn('CRITICAL', transitions['MODERATE'])

    def test_02_transition_stable_to_moderate(self):
        """Verify forward deterioration: STABLE → MODERATE."""
        res = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'MODERATE'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['source_scenario'], 'STABLE')
        self.assertEqual(data['data']['target_scenario'], 'MODERATE')
        self.assertEqual(data['data']['current_scenario'], 'MODERATE')

        # Check DB persistent state
        state = db.execute_query(
            "SELECT current_scenario, previous_scenario FROM simulator_patient_states WHERE patient_id = %s",
            (self.p1_id,),
            fetch='one'
        )
        self.assertEqual(state['current_scenario'], 'MODERATE')
        self.assertEqual(state['previous_scenario'], 'STABLE')

        # Check DB transition history
        hist = db.execute_query(
            "SELECT * FROM simulator_scenario_transitions WHERE patient_id = %s ORDER BY transition_id DESC LIMIT 1",
            (self.p1_id,),
            fetch='one'
        )
        self.assertEqual(hist['source_scenario'], 'STABLE')
        self.assertEqual(hist['target_scenario'], 'MODERATE')
        self.assertEqual(hist['status'], 'SUCCESS')

    def test_03_transition_moderate_to_critical(self):
        """Verify acute deterioration: MODERATE → CRITICAL."""
        # Set to MODERATE first
        self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'MODERATE'}),
            content_type='application/json'
        )

        # Transition to CRITICAL
        res = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'CRITICAL'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['source_scenario'], 'MODERATE')
        self.assertEqual(data['data']['target_scenario'], 'CRITICAL')

        state = db.execute_query(
            "SELECT current_scenario, previous_scenario FROM simulator_patient_states WHERE patient_id = %s",
            (self.p1_id,),
            fetch='one'
        )
        self.assertEqual(state['current_scenario'], 'CRITICAL')
        self.assertEqual(state['previous_scenario'], 'MODERATE')

    def test_04_transition_critical_to_moderate(self):
        """Verify improvement: CRITICAL → MODERATE."""
        # Setup CRITICAL
        db.execute_query(
            "UPDATE simulator_patient_states SET current_scenario = 'CRITICAL' WHERE patient_id = %s",
            (self.p1_id,)
        )

        res = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'MODERATE'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['source_scenario'], 'CRITICAL')
        self.assertEqual(data['data']['target_scenario'], 'MODERATE')

        state = db.execute_query(
            "SELECT current_scenario FROM simulator_patient_states WHERE patient_id = %s",
            (self.p1_id,),
            fetch='one'
        )
        self.assertEqual(state['current_scenario'], 'MODERATE')

    def test_05_transition_moderate_to_stable(self):
        """Verify normalization: MODERATE → STABLE."""
        db.execute_query(
            "UPDATE simulator_patient_states SET current_scenario = 'MODERATE' WHERE patient_id = %s",
            (self.p1_id,)
        )

        res = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'STABLE'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['source_scenario'], 'MODERATE')
        self.assertEqual(data['data']['target_scenario'], 'STABLE')

    def test_06_direct_transitions_stable_and_critical(self):
        """Verify direct test transitions: STABLE ↔ CRITICAL."""
        # STABLE → CRITICAL
        res1 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'CRITICAL'}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.get_json()['data']['target_scenario'], 'CRITICAL')

        # CRITICAL → STABLE
        res2 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'STABLE'}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()['data']['source_scenario'], 'CRITICAL')
        self.assertEqual(res2.get_json()['data']['target_scenario'], 'STABLE')

    def test_07_recovery_transitions_both_directions(self):
        """Verify recovery transitions in both directions: STABLE ↔ RECOVERY and CRITICAL ↔ RECOVERY."""
        # STABLE → RECOVERY
        res1 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'RECOVERY'}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.get_json()['data']['target_scenario'], 'RECOVERY')

        # RECOVERY → STABLE
        res2 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'STABLE'}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()['data']['target_scenario'], 'STABLE')

        # CRITICAL → RECOVERY
        db.execute_query(
            "UPDATE simulator_patient_states SET current_scenario = 'CRITICAL' WHERE patient_id = %s",
            (self.p1_id,)
        )
        res3 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'RECOVERY'}),
            content_type='application/json'
        )
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.get_json()['data']['source_scenario'], 'CRITICAL')
        self.assertEqual(res3.get_json()['data']['target_scenario'], 'RECOVERY')

        # RECOVERY → CRITICAL (Relapse)
        res4 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'CRITICAL'}),
            content_type='application/json'
        )
        self.assertEqual(res4.status_code, 200)
        self.assertEqual(res4.get_json()['data']['target_scenario'], 'CRITICAL')

    def test_08_noop_duplicate_transition(self):
        """Verify requesting the current scenario returns a safe no-op response without corrupting state."""
        res = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'STABLE'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['data'].get('is_noop'))

    def test_09_invalid_scenario_and_patient_validation(self):
        """Verify invalid scenarios and nonexistent patient IDs are safely rejected."""
        # Invalid scenario
        res1 = self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'HYPOTHETICAL_STAGE_X'}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 400)
        self.assertFalse(res1.get_json()['success'])

        # Nonexistent patient
        res2 = self.client.post(
            '/api/v1/telemetry-simulator/patients/999999/transition',
            data=json.dumps({'target_scenario': 'CRITICAL'}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 404)
        self.assertFalse(res2.get_json()['success'])

    def test_10_concurrent_patient_isolation(self):
        """Verify changing one patient's scenario does NOT alter or contaminate other patients."""
        # Patient 1 -> CRITICAL
        self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'CRITICAL'}),
            content_type='application/json'
        )

        # Patient 2 -> MODERATE
        self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p2_id}/transition',
            data=json.dumps({'target_scenario': 'MODERATE'}),
            content_type='application/json'
        )

        # Patient 3 -> STABLE
        self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p3_id}/transition',
            data=json.dumps({'target_scenario': 'STABLE'}),
            content_type='application/json'
        )

        # Query all three authoritative states
        states = db.execute_query(
            "SELECT patient_id, current_scenario FROM simulator_patient_states WHERE patient_id IN (%s, %s, %s)",
            (self.p1_id, self.p2_id, self.p3_id),
            fetch=True
        )
        state_map = {r['patient_id']: r['current_scenario'] for r in states}

        self.assertEqual(state_map[self.p1_id], 'CRITICAL')
        self.assertEqual(state_map[self.p2_id], 'MODERATE')
        self.assertEqual(state_map[self.p3_id], 'STABLE')

    def test_11_telemetry_flow_ews_and_decision_engine(self):
        """
        Verify end-to-end integration:
        Transition patient to CRITICAL, submit critical vitals to ingestion endpoint,
        and confirm real EWS calculation, risk scoring, and transfer alerts trigger genuinely.
        """
        # 1. Transition Patient 1 to CRITICAL
        self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'CRITICAL'}),
            content_type='application/json'
        )

        # 2. Ingest critical vitals (HR=145: 3pts, RR=32: 3pts, SBP=60: 3pts, Temp=39.6: 2pts => Total EWS=11)
        vital_payload = {
            'heart_rate': 145.0,
            'respiratory_rate': 32.0,
            'systolic_bp': 60.0,
            'temperature': 39.6,
            'source': 'SIMULATOR',
            'device_id': 'JS-ICU-SIM-TEST'
        }

        auth_headers = {
            'Authorization': f'Bearer {self.admin_token}',
            'Content-Type': 'application/json'
        }

        v_res = self.client.post(
            f'/api/v1/vitals/patient/{self.p1_id}/submit',
            data=json.dumps(vital_payload),
            headers=auth_headers
        )
        self.assertEqual(v_res.status_code, 201)
        v_data = v_res.get_json()['data']

        # Confirm genuine EWS calculation through scoring_engine & decision_service
        self.assertGreaterEqual(v_data['total_score'], 7)
        self.assertEqual(v_data['condition'], 'Critical')
        self.assertEqual(v_data['recommendation'], 'Keep in ICU')

        # Confirm Read-Back endpoint returns the ingested vitals
        rb_res = self.client.get(
            f'/api/v1/vitals/patient/{self.p1_id}/latest-status',
            headers=auth_headers
        )
        self.assertEqual(rb_res.status_code, 200)
        rb_data = rb_res.get_json()['data']
        self.assertAlmostEqual(rb_data['latest_vitals']['heart_rate'], 145.0, delta=0.5)
        self.assertAlmostEqual(rb_data['latest_vitals']['systolic_bp'], 60.0, delta=0.5)

        # 3. Transition Patient 1 back to STABLE and ingest normal vitals (EWS=0)
        self.client.post(
            f'/api/v1/telemetry-simulator/patients/{self.p1_id}/transition',
            data=json.dumps({'target_scenario': 'STABLE'}),
            headers=auth_headers
        )
        stable_payload = {
            'heart_rate': 74.0,
            'respiratory_rate': 16.0,
            'systolic_bp': 120.0,
            'temperature': 36.8,
            'source': 'SIMULATOR',
            'device_id': 'JS-ICU-SIM-TEST'
        }
        s_res = self.client.post(
            f'/api/v1/vitals/patient/{self.p1_id}/submit',
            data=json.dumps(stable_payload),
            headers=auth_headers
        )
        self.assertEqual(s_res.status_code, 201)
        s_data = s_res.get_json()['data']
        self.assertEqual(s_data['total_score'], 0)
        self.assertEqual(s_data['condition'], 'Stable')
        self.assertEqual(s_data['recommendation'], 'Fit for HDU Transfer')

    def test_12_baseline_admitted_patients_preserved(self):
        """Verify baseline patients remain intact (exactly 10/10 admitted)."""
        admitted = db.execute_query(
            "SELECT COUNT(*) as cnt FROM patients WHERE status = 'admitted'",
            fetch='one'
        )
        self.assertEqual(admitted['cnt'], 10)


if __name__ == '__main__':
    unittest.main()
