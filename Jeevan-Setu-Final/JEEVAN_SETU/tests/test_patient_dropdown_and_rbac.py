"""
tests/test_patient_dropdown_and_rbac.py — Comprehensive tests for:
1. Patient dropdown and database-backed patient list
2. RBAC authorization (Doctor, Nurse, Attendant, Admin)
3. 403 Forbidden enforcement on unauthorized patient access
4. Dynamic patient context switching without data mixing
5. Persisted EWS telemetry verification
6. PDF Report button removal verification on /chatbot UI
"""

import unittest
import json
import os
import sys
import urllib.request
import urllib.error

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
JEEVAN_SETU_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, '..', '..', '..', '..', 'Major_Project', 'JSF', 'Jeevan-Setu-Final', 'JEEVAN_SETU'))
if not os.path.exists(JEEVAN_SETU_ROOT):
    JEEVAN_SETU_ROOT = r'd:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU'

if os.path.exists(JEEVAN_SETU_ROOT) and JEEVAN_SETU_ROOT not in sys.path:
    sys.path.insert(0, JEEVAN_SETU_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.chatbot_engine import (
    verify_user_patient_access,
    get_authorized_patients_for_user,
    getPatient,
    getEWS,
    get_patient_clinical_context
)
from services.auth_service import AuthService
from models.user_model import User


class TestPatientDropdownAndRBAC(unittest.TestCase):

    def setUp(self):
        self.base_url = "http://localhost:6060"

    def test_01_chatbot_html_no_pdf_button_and_has_dropdown(self):
        """Verify PDF Report button is removed and patient dropdown container exists in /chatbot HTML."""
        req = urllib.request.Request(f"{self.base_url}/chatbot")
        with urllib.request.urlopen(req) as resp:
            html = resp.read().decode('utf-8')

        # PDF Report button must be removed from /chatbot
        self.assertNotIn('export-pdf-btn', html, "export-pdf-btn ID must not exist in HTML")
        self.assertNotIn('PDF Report', html, "PDF Report button text must not exist in HTML")
        self.assertNotIn('picture_as_pdf', html, "PDF icon should not be in active bar")

        # Patient dropdown must exist
        self.assertIn('patient-dropdown-btn', html, "patient-dropdown-btn must exist in HTML")
        self.assertIn('patient-dropdown-menu', html, "patient-dropdown-menu must exist in HTML")
        self.assertIn('patient-dropdown-list', html, "patient-dropdown-list must exist in HTML")
        self.assertIn('bar-patient-name', html, "bar-patient-name must exist")
        self.assertIn('bar-patient-ews', html, "bar-patient-ews must exist")

    def test_02_patient_list_endpoint_database_backed(self):
        """Verify /chatbot/patients returns database-backed patients with persisted EWS and vitals."""
        req = urllib.request.Request(f"{self.base_url}/chatbot/patients")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))

        self.assertTrue(data.get('success'))
        self.assertGreater(data.get('count', 0), 0, "Must return at least one authorized patient")
        patients = data.get('patients', [])
        
        # Check first patient fields
        p0 = patients[0]
        self.assertIn('patient_id', p0)
        self.assertIn('name', p0)
        self.assertIn('patient_code', p0)
        self.assertIn('ward_type', p0)
        self.assertIn('ews_score', p0)
        self.assertIn('recorded_at', p0)
        print(f"\n[TEST 02] Loaded {len(patients)} authorized patients. First patient: {p0['name']} ({p0['patient_code']}) | EWS: {p0['ews_score']}")

    def test_03_patient_context_switching_no_data_mixing(self):
        """Verify switching from Patient 1 to Patient 2 changes context strictly without data mixing."""
        # Patient 1 (Rajesh Kumar)
        req1 = urllib.request.Request(f"{self.base_url}/chatbot/patient/1/summary")
        with urllib.request.urlopen(req1) as resp1:
            data1 = json.loads(resp1.read().decode('utf-8'))
            name1 = data1['context']['patient']['name']
            code1 = data1['context']['patient']['patient_code']
            diag1 = data1['context']['patient']['diagnosis']

        # Patient 2 (Anita Devi)
        req2 = urllib.request.Request(f"{self.base_url}/chatbot/patient/2/summary")
        with urllib.request.urlopen(req2) as resp2:
            data2 = json.loads(resp2.read().decode('utf-8'))
            name2 = data2['context']['patient']['name']
            code2 = data2['context']['patient']['patient_code']
            diag2 = data2['context']['patient']['diagnosis']

        self.assertNotEqual(name1, name2, "Patient names must be distinct")
        self.assertNotEqual(code1, code2, "Patient codes must be distinct")
        self.assertNotEqual(diag1, diag2, "Patient diagnoses must be distinct")

        # Test Chatbot Query for Patient 1
        body1 = json.dumps({'message': 'What is the patient diagnosis?', 'patient_id': 1}).encode('utf-8')
        req_chat1 = urllib.request.Request(f"{self.base_url}/chatbot/message", data=body1, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_chat1) as resp_chat1:
            res1 = json.loads(resp_chat1.read().decode('utf-8'))
            text1 = res1.get('text', res1.get('response', ''))
            self.assertTrue(res1.get('success'))

        # Test Chatbot Query for Patient 2
        body2 = json.dumps({'message': 'What is the patient diagnosis?', 'patient_id': 2}).encode('utf-8')
        req_chat2 = urllib.request.Request(f"{self.base_url}/chatbot/message", data=body2, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_chat2) as resp_chat2:
            res2 = json.loads(resp_chat2.read().decode('utf-8'))
            text2 = res2.get('text', res2.get('response', ''))
            self.assertTrue(res2.get('success'))

        print(f"\n[TEST 03] Patient 1 ({name1}): {diag1}")
        print(f"[TEST 03] Patient 2 ({name2}): {diag2}")

    def test_04_rbac_attendant_access_control_and_403_enforcement(self):
        """Verify Attendant user role cannot access unauthorized patient and receives 403 Forbidden."""
        class MockAttendantUser:
            id = 99
            user_id = 99
            username = "attendant_sunita"
            email = "sunita@family.care"
            department = "Attendant"
            role = 'attendant'
            patient_id = 1  # Authorized ONLY for patient 1

        # Check Python RBAC authorization logic
        is_auth_1, _ = verify_user_patient_access(MockAttendantUser(), 1)
        self.assertTrue(is_auth_1, "Attendant must be authorized for their own patient (patient 1)")

        is_auth_2, err2 = verify_user_patient_access(MockAttendantUser(), 2)
        self.assertFalse(is_auth_2, "Attendant must NOT be authorized for other patients (patient 2)")
        self.assertIn("Access forbidden", err2)

        # Generate signed Attendant JWT token for patient 1
        user_inst = MockAttendantUser()
        token_attendant = AuthService.generate_access_token(user_inst)['access_token']

        # Requesting authorized patient 1 with token -> 200 OK
        req_auth = urllib.request.Request(
            f"{self.base_url}/chatbot/patient/1/summary",
            headers={'Authorization': f"Bearer {token_attendant}"}
        )
        with urllib.request.urlopen(req_auth) as resp:
            self.assertEqual(resp.status, 200)

        # Requesting unauthorized patient 2 with attendant token -> 403 Forbidden
        req_unauth = urllib.request.Request(
            f"{self.base_url}/chatbot/patient/2/summary",
            headers={'Authorization': f"Bearer {token_attendant}"}
        )
        try:
            with urllib.request.urlopen(req_unauth) as resp:
                self.fail("Expected 403 Forbidden for unauthorized patient access")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403, "Must return HTTP 403 Forbidden for unauthorized patient")
            err_data = json.loads(e.read().decode('utf-8'))
            self.assertFalse(err_data.get('success'))
            print("\n[TEST 04] Successfully enforced HTTP 403 Forbidden for unauthorized attendant patient request.")

    def test_05_persisted_ews_retrieval(self):
        """Verify chatbot retrieves persisted EWS score directly from database records."""
        ews_1 = getEWS(1)
        self.assertIn('score', ews_1)
        self.assertIn('risk_level', ews_1)
        self.assertIn('breakdown', ews_1)
        print(f"\n[TEST 05] Persisted EWS for Patient 1: Score={ews_1['score']} (Risk={ews_1['risk_level']})")


if __name__ == '__main__':
    unittest.main()
