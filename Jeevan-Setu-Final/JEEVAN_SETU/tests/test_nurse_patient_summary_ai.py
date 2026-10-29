"""
tests/test_nurse_patient_summary_ai.py — End-to-End Functional, Database,
Security, and RBAC Test Suite for the Nurse Patient Summary AI Portal.

Test Matrix:
1. Frontend & Routing:
   - Cloned Nurse page loads (HTTP 200) at /Nurse/Nurse_patient_summary_ai/Nurse_patient_summary_ai.html
   - Route aliases (/Nurse/Nurse_patient_summary_ai, /nurse/summary) resolve cleanly
   - Standard Nurse Sidebar with Patient Care and active Patient Summary (AI)
   - Dr. Setu Assistant Header, Live Telemetry badge, top search input & clear button
   - Live Patient Telemetry & Mode bar (Patient Chat vs General Chat)
   - Quick action handover chips and custom telemetry simulator modal
   - nurse_navigation.js configuration includes patient_summary_ai

2. API & Role-Based Access Control (RBAC):
   - Nurse Priya (ID: 5) receives strictly her 3 assigned patients (IDs: 1, 2, 7)
   - Scoped search returns only assigned patients without PHI data leakage
   - Assigned patient summary retrieval succeeds with HTTP 200
   - IDOR prevention: Unassigned patient summary retrieval rejected with HTTP 403 Forbidden
   - Conversational chat succeeds for assigned patient
   - Conversational chat for unassigned patient is rejected with HTTP 403 Forbidden
   - Cross-nurse role verification (Nurse Arun ID 6 accesses Patient 3, rejected on Patient 1)
   - Unauthenticated requests rejected with HTTP 401 Unauthorized

3. AI & Clinical Telemetry:
   - General healthcare queries in General Mode execute without patient context
   - Custom telemetry simulation evaluates vitals and clearly labels simulated data

4. Database Consistency & Integrity:
   - Clinical context data matches persisted database records for Patient 1
   - Canonical 10-patient hospital census remains completely intact
   - Doctor Patient Summary AI portal (/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html) remains fully functional
"""

import unittest
import json
import os
import sys
import urllib.request
import urllib.error

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JEEVAN_SETU_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if JEEVAN_SETU_ROOT not in sys.path:
    sys.path.insert(0, JEEVAN_SETU_ROOT)

from services.auth_service import AuthService
from models.user_model import User
from models.patient_model import Patient
import database.db as db_module


class TestNursePatientSummaryAI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base_url = "http://127.0.0.1:5000"

        # Generate tokens for tests
        user_priya = User.get_by_id(5)  # Nurse Priya (Patients 1, 2, 7)
        user_arun = User.get_by_id(6)   # Nurse Arun (Patients 3, 4, 8)
        user_doctor = User.get_by_id(2) # Dr. Sharma (Patients 1, 2, 7)

        cls.token_priya = AuthService.generate_access_token(user_priya)['access_token']
        cls.token_arun = AuthService.generate_access_token(user_arun)['access_token']
        cls.token_doctor = AuthService.generate_access_token(user_doctor)['access_token']

    # ─────────────────────────────────────────────────────────────
    # 1. FRONTEND ROUTING & STRUCTURE TESTS
    # ─────────────────────────────────────────────────────────────

    def test_01_nurse_patient_summary_ai_page_loads(self):
        """Verify the cloned Nurse Patient Summary AI page loads with HTTP 200."""
        url = f"{self.base_url}/Nurse/Nurse_patient_summary_ai/Nurse_patient_summary_ai.html"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode('utf-8')

        self.assertIn('<title>Jeevan Setu — Clinical Nurse Assistant & Live Telemetry Rounds</title>', html)
        self.assertIn('Dr. Setu — Clinical Nurse Rounds Assistant', html)
        self.assertIn('LIVE TELEMETRY', html)
        self.assertIn('nurse_navigation.js', html)

    def test_02_route_aliases_resolve(self):
        """Verify friendly route aliases resolve to the nurse summary template."""
        aliases = [
            f"{self.base_url}/Nurse/Nurse_patient_summary_ai",
            f"{self.base_url}/nurse/summary"
        ]
        for url in aliases:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200, f"Failed for alias: {url}")
                html = resp.read().decode('utf-8')
                self.assertIn('Clinical Nurse Assistant', html)

    def test_03_essential_ui_components_present(self):
        """Verify all interactive components, selectors, modals, and toolbars exist in the HTML."""
        url = f"{self.base_url}/Nurse/Nurse_patient_summary_ai/Nurse_patient_summary_ai.html"
        with urllib.request.urlopen(url) as resp:
            html = resp.read().decode('utf-8')

        # Dropdown and patient context bar
        self.assertIn('id="patient-dropdown-btn"', html)
        self.assertIn('id="patient-dropdown-menu"', html)
        self.assertIn('id="patient-dropdown-list"', html)
        self.assertIn('id="bar-patient-name"', html)
        self.assertIn('id="bar-patient-code"', html)
        self.assertIn('id="bar-patient-ward"', html)
        self.assertIn('id="bar-patient-bed"', html)
        self.assertIn('id="bar-patient-ews"', html)
        self.assertIn('id="bar-telemetry-time"', html)
        self.assertIn('id="sync-vitals-btn"', html)
        self.assertIn('id="switch-patient-btn"', html)

        # Mode toggle
        self.assertIn('id="mode-patient-btn"', html)
        self.assertIn('id="mode-general-btn"', html)

        # Search
        self.assertIn('id="top-patient-search"', html)
        self.assertIn('id="search-dropdown"', html)
        self.assertIn('id="clear-search-btn"', html)

        # Chat and Input
        self.assertIn('id="chat-messages"', html)
        self.assertIn('id="chat-form"', html)
        self.assertIn('id="user-input"', html)
        self.assertIn('id="send-btn"', html)
        self.assertIn('id="voice-btn"', html)
        self.assertIn('id="typing-indicator"', html)

        # Quick chips and custom telemetry modal
        self.assertIn('id="quick-chips-container"', html)
        self.assertIn('id="custom-telemetry-modal"', html)
        self.assertIn('loadTelemetryPreset(\'sepsis\')', html)
        self.assertIn('submitCustomTelemetry()', html)

    def test_04_nurse_navigation_config_includes_summary(self):
        """Verify nurse_navigation.js has registered patient_summary_ai."""
        nav_path = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', 'Jeevan_setu_frontend', 'Nurse', 'nurse_navigation.js'))
        with open(nav_path, 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn("id: 'patient_summary_ai'", js)
        self.assertIn("Nurse_patient_summary_ai.html", js)
        self.assertIn("if (path.includes('nurse_patient_summary_ai') || path.includes('patient_summary_ai')) return 'patient_summary_ai';", js)

    # ─────────────────────────────────────────────────────────────
    # 2. API & ROLE-BASED ACCESS CONTROL (RBAC) TESTS
    # ─────────────────────────────────────────────────────────────

    def test_05_nurse_priya_authorized_patients_dropdown(self):
        """Nurse Priya (ID 5) must only receive her 3 assigned patients (1, 2, 7)."""
        url = f"{self.base_url}/chatbot/patients"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {self.token_priya}'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('count'), 3)
        patient_ids = [p.get('patient_id') or p.get('id') for p in data.get('patients', [])]
        self.assertEqual(set(patient_ids), {1, 2, 7})

    def test_06_nurse_patient_search_scoping_no_data_leakage(self):
        """Nurse Priya can find assigned patients, but queries for unassigned patients return 0."""
        # Assigned patient
        url_assigned = f"{self.base_url}/chatbot/patients/search?q=Rajesh"
        req1 = urllib.request.Request(url_assigned, headers={'Authorization': f'Bearer {self.token_priya}'})
        with urllib.request.urlopen(req1) as resp:
            data1 = json.loads(resp.read().decode('utf-8'))
        self.assertEqual(data1.get('count'), 1)
        self.assertEqual(data1['patients'][0]['name'], 'Rajesh Kumar')

        # Unassigned patient (Vikram Singh, assigned to Nurse Arun)
        url_unassigned = f"{self.base_url}/chatbot/patients/search?q=Vikram"
        req2 = urllib.request.Request(url_unassigned, headers={'Authorization': f'Bearer {self.token_priya}'})
        with urllib.request.urlopen(req2) as resp:
            data2 = json.loads(resp.read().decode('utf-8'))
        self.assertEqual(data2.get('count'), 0, "Nurse Priya must not see unassigned patient Vikram Singh")

    def test_07_nurse_summary_access_authorized_patient(self):
        """Nurse Priya can retrieve summary for assigned Patient 1."""
        url = f"{self.base_url}/chatbot/patient/1/summary"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {self.token_priya}'})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))

        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('patient_id'), 1)
        self.assertIn('Rajesh Kumar', data.get('text', ''))
        self.assertIn('context', data)

    def test_08_nurse_summary_idor_prevention_unassigned_patient(self):
        """Nurse Priya accessing unassigned Patient 3 is rejected with HTTP 403 Forbidden."""
        url = f"{self.base_url}/chatbot/patient/3/summary"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {self.token_priya}'})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        body = json.loads(cm.exception.read().decode('utf-8'))
        self.assertFalse(body.get('success'))
        self.assertIn("Nurse is not authorized", body.get('error', ''))

    def test_09_nurse_conversational_chat_authorized_patient(self):
        """Nurse Priya can chat with Dr. Setu regarding assigned Patient 1."""
        url = f"{self.base_url}/chatbot/message"
        payload = json.dumps({
            'message': 'What are the latest vitals?',
            'mode': 'patient',
            'patient_id': 1
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Authorization': f'Bearer {self.token_priya}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))

        self.assertTrue(data.get('success'))
        self.assertIn('Rajesh Kumar', data.get('response', ''))

    def test_10_nurse_conversational_chat_unassigned_patient_rejected(self):
        """Nurse Priya cannot query Dr. Setu about unassigned Patient 3."""
        url = f"{self.base_url}/chatbot/message"
        payload = json.dumps({
            'message': 'What are the latest vitals?',
            'mode': 'patient',
            'patient_id': 3
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Authorization': f'Bearer {self.token_priya}', 'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        body = json.loads(cm.exception.read().decode('utf-8'))
        self.assertFalse(body.get('success'))

    def test_11_cross_nurse_rbac_boundaries(self):
        """Verify Nurse Arun (ID 6) accesses Patient 3 and is rejected for Patient 1."""
        # Arun accesses Patient 3 -> 200
        url_arun_p3 = f"{self.base_url}/chatbot/patient/3/summary"
        req1 = urllib.request.Request(url_arun_p3, headers={'Authorization': f'Bearer {self.token_arun}'})
        with urllib.request.urlopen(req1) as resp:
            self.assertEqual(resp.status, 200)

        # Arun accesses Patient 1 -> 403
        url_arun_p1 = f"{self.base_url}/chatbot/patient/1/summary"
        req2 = urllib.request.Request(url_arun_p1, headers={'Authorization': f'Bearer {self.token_arun}'})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req2)
        self.assertEqual(cm.exception.code, 403)

    def test_12_unauthenticated_request_rejected(self):
        """Unauthenticated request with invalid/expired token is rejected with HTTP 401."""
        url = f"{self.base_url}/chatbot/patient/1/summary"
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer invalid_or_expired_token'})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 401)

    # ─────────────────────────────────────────────────────────────
    # 3. AI & TELEMETRY SIMULATION TESTS
    # ─────────────────────────────────────────────────────────────

    def test_13_general_chat_mode_without_patient(self):
        """Authenticated nurse can ask educational questions in General Mode."""
        url = f"{self.base_url}/chatbot/message"
        payload = json.dumps({
            'message': 'What is EWS and how is it scored?',
            'mode': 'general'
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Authorization': f'Bearer {self.token_priya}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))

        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('mode'), 'general')
        self.assertTrue(len(data.get('response', '')) > 20)

    def test_14_custom_telemetry_simulation_labeled_correctly(self):
        """Custom telemetry simulation evaluates correctly and labels data as simulated."""
        url = f"{self.base_url}/chatbot/message"
        payload = json.dumps({
            'message': 'Evaluate custom telemetry',
            'mode': 'patient',
            'patient_id': 1,
            'custom_vitals': {
                'heart_rate': 128,
                'respiratory_rate': 28,
                'blood_pressure_sys': 85,
                'blood_pressure_dia': 52,
                'temperature': 39.2,
                'spo2': 91
            }
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Authorization': f'Bearer {self.token_priya}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        self.assertTrue(data.get('success'))
        resp_text = data.get('response', '')
        self.assertIn('SIMULATED / USER-PROVIDED DATA', resp_text)
        self.assertIn('Simulated EWS Score', resp_text)

    # ─────────────────────────────────────────────────────────────
    # 4. DATABASE INTEGRITY & REGRESSION TESTS
    # ─────────────────────────────────────────────────────────────

    def test_15_database_patient_context_matches(self):
        """Verify summary context matches persisted database records for Patient 1."""
        url = f"{self.base_url}/chatbot/patient/1/summary"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {self.token_priya}'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        p_db = Patient.get_by_id(1)
        self.assertIsNotNone(p_db)
        ctx = data['context']
        self.assertEqual(ctx['patient']['name'], p_db['name'])
        self.assertEqual(ctx['patient']['patient_code'], p_db['patient_code'])
        self.assertEqual(ctx['patient']['ward_type'], p_db['ward_type'])

    def test_16_canonical_10_patient_census_intact(self):
        """Verify exactly 10 active admitted patients remain intact in the database."""
        db = db_module.get_db()
        rows = db.execute_query("SELECT patient_id, patient_code, name, status FROM patients ORDER BY patient_id ASC", fetch=True)
        self.assertEqual(len(rows), 10, "Hospital census must maintain exactly 10 admitted patients")
        self.assertEqual(rows[0]['patient_code'], 'UHID-2026-00001')
        self.assertEqual(rows[9]['patient_code'], 'UHID-2026-00010')

    def test_17_doctor_portal_regression_unaffected(self):
        """Verify Doctor portal and summary assistant remain fully functional."""
        url_doc_page = f"{self.base_url}/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html"
        with urllib.request.urlopen(url_doc_page) as resp:
            self.assertEqual(resp.status, 200)

        # Doctor 1 accesses Patient 1
        url_doc_api = f"{self.base_url}/chatbot/patient/1/summary"
        req = urllib.request.Request(url_doc_api, headers={'Authorization': f'Bearer {self.token_doctor}'})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(data.get('success'))


if __name__ == '__main__':
    unittest.main()
