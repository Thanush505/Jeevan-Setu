"""
Test Suite: Doctor Patient Summary AI Access Control & Confidentiality (RBAC & IDOR Prevention)
Location: tests/test_doctor_patient_summary_access.py

Validates that:
1. Logged-in doctors (e.g., Dr. Sunita Mehta, Dr. Kavita Patel, Dr. Ananya Gupta)
   only receive and view patients strictly assigned to them under hospital RBAC.
2. IDOR protection prevents doctors from querying unassigned patients across:
   - /chatbot/patients (Dropdown)
   - /chatbot/patients/search (Autocomplete)
   - /chatbot/patient/<id>/summary (Clinical briefing)
   - /chatbot/patient/<id>/vitals (Bedside telemetry)
   - /chatbot/patient/<id>/trends (Longitudinal trends)
   - /chatbot/patient/<id>/decisions (Transfer decisions & explainability)
   - /chatbot/context/<id> (Ground truth facts)
   - /chatbot/message (Dual-mode conversational AI)
   - /chatbot/query (Strict clinical query)
3. Zero-assignment doctors receive 0 patients and cannot view any patient data.
4. Unauthenticated requests are rejected with HTTP 401 Unauthorized.
5. Baseline canonical 10 patients are strictly preserved.
"""

import unittest
import json
import urllib.request
import urllib.error
import os
import sys

from dotenv import load_dotenv
_root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
_backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
if os.path.isfile(_root_env):
    load_dotenv(_root_env, override=True)
elif os.path.isfile(_backend_env):
    load_dotenv(_backend_env, override=True)

sys.path.insert(0, 'c:/Major_Project/JSF-Web_Broswer_simulator/Jeevan-Setu-Final/JEEVAN_SETU')
from services.auth_service import AuthService
from models.user_model import User
from database.db import get_db

BASE_URL = "http://127.0.0.1:5000"


class TestDoctorPatientSummaryAccess(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

        # Dr. Sunita Mehta (user_id=2, role='doctor')
        # Assigned patients in baseline: 1, 2, 7
        user_mehta = User.get_by_id(2)
        cls.mehta_token = AuthService.generate_access_token(user_mehta)['access_token']

        # Dr. Kavita Patel (user_id=3, role='doctor')
        # Assigned patients in baseline: 3, 4, 8
        user_patel = User.get_by_id(3)
        cls.patel_token = AuthService.generate_access_token(user_patel)['access_token']

        # Dr. Ananya Gupta (user_id=4, role='doctor')
        # Assigned patients in baseline: 5, 6, 9, 10
        user_gupta = User.get_by_id(4)
        cls.gupta_token = AuthService.generate_access_token(user_gupta)['access_token']

        # Doctor with zero assigned patients
        user_zero = User.get_by_id(1241) or User.get_by_username('dr_zero_test')
        if not user_zero:
            User.create(username='dr_zero_test', password='Password123!', full_name='Dr. Zero Assignment', email='dr_zero@test.com', role='doctor')
            user_zero = User.get_by_username('dr_zero_test')
        cls.zero_doc_token = AuthService.generate_access_token(user_zero)['access_token']

        # Admin (user_id=1, role='admin')
        user_admin = User.get_by_id(1)
        cls.admin_token = AuthService.generate_access_token(user_admin)['access_token']

    def _make_request(self, path, method="GET", token=None, body=None):
        url = f"{BASE_URL}{path}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                code = resp.getcode()
                raw = resp.read().decode("utf-8")
                return code, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_raw = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_raw)
            except Exception:
                err_json = {"error": err_raw}
            return e.code, err_json

    # ─────────────────────────────────────────────────────────────
    # 1. Patient List Scoping Tests
    # ─────────────────────────────────────────────────────────────
    def test_01_dr_mehta_sees_only_assigned_patients(self):
        """Dr. Sunita Mehta must only receive her assigned patients (1, 2, 7)."""
        code, data = self._make_request("/chatbot/patients", token=self.mehta_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        patient_ids = {p.get("patient_id") or p.get("id") for p in data.get("patients", [])}
        self.assertEqual(patient_ids, {1, 2, 7})
        self.assertEqual(data.get("count"), 3)

    def test_02_dr_patel_sees_only_assigned_patients(self):
        """Dr. Kavita Patel must only receive her assigned patients (3, 4, 8)."""
        code, data = self._make_request("/chatbot/patients", token=self.patel_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        patient_ids = {p.get("patient_id") or p.get("id") for p in data.get("patients", [])}
        self.assertEqual(patient_ids, {3, 4, 8})
        self.assertEqual(data.get("count"), 3)

    def test_03_dr_gupta_sees_only_assigned_patients(self):
        """Dr. Ananya Gupta must only receive her assigned patients (5, 6, 9, 10)."""
        code, data = self._make_request("/chatbot/patients", token=self.gupta_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        patient_ids = {p.get("patient_id") or p.get("id") for p in data.get("patients", [])}
        self.assertEqual(patient_ids, {5, 6, 9, 10})
        self.assertEqual(data.get("count"), 4)

    def test_04_zero_patient_doctor_sees_empty_list(self):
        """A doctor with 0 assigned patients must NOT receive other doctors' patients."""
        code, data = self._make_request("/chatbot/patients", token=self.zero_doc_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(len(data.get("patients", [])), 0)
        self.assertEqual(data.get("count"), 0)

    def test_05_admin_sees_all_patients(self):
        """Admin must receive all 10 hospital patients."""
        code, data = self._make_request("/chatbot/patients", token=self.admin_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        patient_ids = {p.get("patient_id") or p.get("id") for p in data.get("patients", [])}
        self.assertTrue({1, 2, 3, 4, 5, 6, 7, 8, 9, 10}.issubset(patient_ids))

    # ─────────────────────────────────────────────────────────────
    # 2. Search Autocomplete Scoping Tests
    # ─────────────────────────────────────────────────────────────
    def test_06_dr_mehta_search_assigned_patient_success(self):
        """Dr. Mehta searching for 'Rajesh' finds Patient 1."""
        code, data = self._make_request("/chatbot/patients/search?q=Rajesh", token=self.mehta_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 1)
        p = data.get("patients", [])[0]
        self.assertEqual(p.get("patient_id"), 1)

    def test_07_dr_mehta_search_unassigned_patient_returns_empty(self):
        """Dr. Mehta searching for 'Vikram' (assigned to Dr. Patel) yields 0 results."""
        code, data = self._make_request("/chatbot/patients/search?q=Vikram", token=self.mehta_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 0)
        self.assertEqual(data.get("match_type"), "none")
        self.assertEqual(len(data.get("patients", [])), 0)

    def test_08_dr_patel_search_assigned_patient_success(self):
        """Dr. Patel searching for 'Vikram' finds Patient 3."""
        code, data = self._make_request("/chatbot/patients/search?q=Vikram", token=self.patel_token)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 1)
        p = data.get("patients", [])[0]
        self.assertEqual(p.get("patient_id"), 3)

    # ─────────────────────────────────────────────────────────────
    # 3. IDOR Prevention Tests on Clinical Endpoints
    # ─────────────────────────────────────────────────────────────
    def test_09_dr_mehta_access_assigned_endpoints_success(self):
        """Dr. Mehta can access clinical summary, vitals, trends, and decisions for Patient 1."""
        for endpoint in ["summary", "vitals", "trends", "decisions"]:
            code, data = self._make_request(f"/chatbot/patient/1/{endpoint}", token=self.mehta_token)
            self.assertEqual(code, 200, f"Failed accessing /chatbot/patient/1/{endpoint}")
            self.assertTrue(data.get("success"))

        code_ctx, data_ctx = self._make_request("/chatbot/context/1", token=self.mehta_token)
        self.assertEqual(code_ctx, 200)
        self.assertTrue(data_ctx.get("success"))

    def test_10_dr_mehta_idor_unassigned_endpoints_forbidden(self):
        """Dr. Mehta must be rejected with HTTP 403 on all endpoints for Patient 3 (Dr. Patel)."""
        for endpoint in ["summary", "vitals", "trends", "decisions"]:
            code, data = self._make_request(f"/chatbot/patient/3/{endpoint}", token=self.mehta_token)
            self.assertEqual(code, 403, f"Expected 403 on /chatbot/patient/3/{endpoint}, got {code}")
            self.assertFalse(data.get("success"))
            self.assertIn("not authorized", data.get("error", "").lower())

        code_ctx, data_ctx = self._make_request("/chatbot/context/3", token=self.mehta_token)
        self.assertEqual(code_ctx, 403)
        self.assertFalse(data_ctx.get("success"))

    def test_11_dr_patel_idor_unassigned_endpoints_forbidden(self):
        """Dr. Patel must be rejected with HTTP 403 when attempting to access Patient 1 (Dr. Mehta)."""
        for endpoint in ["summary", "vitals", "trends", "decisions"]:
            code, data = self._make_request(f"/chatbot/patient/1/{endpoint}", token=self.patel_token)
            self.assertEqual(code, 403, f"Expected 403 on /chatbot/patient/1/{endpoint}, got {code}")
            self.assertFalse(data.get("success"))
            self.assertIn("not authorized", data.get("error", "").lower())

    def test_12_zero_patient_doctor_idor_forbidden(self):
        """A doctor with zero assignments must be rejected on any patient."""
        code, data = self._make_request("/chatbot/patient/1/summary", token=self.zero_doc_token)
        self.assertEqual(code, 403)
        self.assertFalse(data.get("success"))

    # ─────────────────────────────────────────────────────────────
    # 4. IDOR Prevention on Conversational / AI Query Endpoints
    # ─────────────────────────────────────────────────────────────
    def test_13_dr_mehta_query_assigned_patient_success(self):
        """Dr. Mehta querying assigned Patient 1 via /chatbot/query succeeds."""
        payload = {
            "patient_id": 1,
            "message": "What is the current EWS score?",
            "mode": "patient"
        }
        code, data = self._make_request("/chatbot/query", method="POST", token=self.mehta_token, body=payload)
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))

    def test_14_dr_mehta_query_unassigned_patient_forbidden(self):
        """Dr. Mehta querying unassigned Patient 3 via /chatbot/query returns 403."""
        payload = {
            "patient_id": 3,
            "message": "What is the current EWS score?",
            "mode": "patient"
        }
        code, data = self._make_request("/chatbot/query", method="POST", token=self.mehta_token, body=payload)
        self.assertEqual(code, 403)
        self.assertFalse(data.get("success"))
        self.assertIn("not authorized", data.get("error", "").lower())

    def test_15_dr_mehta_message_unassigned_patient_forbidden(self):
        """Dr. Mehta passing patient_id=3 in /chatbot/message returns 403."""
        payload = {
            "patient_id": 3,
            "message": "Show full patient summary",
            "mode": "patient"
        }
        code, data = self._make_request("/chatbot/message", method="POST", token=self.mehta_token, body=payload)
        self.assertEqual(code, 403)
        self.assertFalse(data.get("success"))
        self.assertIn("not authorized", data.get("error", "").lower())

    def test_16_dr_mehta_mention_unassigned_patient_in_text_protected(self):
        """Dr. Mehta typing 'Vikram Singh' in message body cannot leak Patient 3's records."""
        payload = {
            "message": "Vikram Singh",
            "mode": "patient"
        }
        code, data = self._make_request("/chatbot/message", method="POST", token=self.mehta_token, body=payload)
        self.assertEqual(code, 200)
        # Should not switch active context to Patient 3
        self.assertNotEqual(data.get("patient_id"), 3)
        # Should inform that patient was not found in authorized patients
        self.assertIn("could not find", data.get("text", "").lower())

    # ─────────────────────────────────────────────────────────────
    # 5. Unauthenticated Access Tests
    # ─────────────────────────────────────────────────────────────
    def test_17_unauthenticated_requests_return_401(self):
        """Requests without authorization token or session must return HTTP 401."""
        endpoints = [
            ("/chatbot/patients", "GET"),
            ("/chatbot/patients/search?q=Rajesh", "GET"),
            ("/chatbot/patient/1/summary", "GET"),
            ("/chatbot/patient/1/vitals", "GET"),
            ("/chatbot/query", "POST")
        ]
        for path, method in endpoints:
            body = {"patient_id": 1, "message": "hello"} if method == "POST" else None
            code, _ = self._make_request(path, method=method, token=None, body=body)
            self.assertEqual(code, 401, f"Expected 401 for unauthenticated {method} {path}, got {code}")


if __name__ == '__main__':
    unittest.main()
