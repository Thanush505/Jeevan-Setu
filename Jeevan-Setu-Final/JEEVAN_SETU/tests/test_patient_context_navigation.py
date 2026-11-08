"""
tests/test_patient_context_navigation.py — End-to-End Regression Test Suite
Ensures that all patient navigation, data fetching, and page bindings
strictly use the correct patient ID, isolate patient records, and prevent
any hardcoding, fallbacks, or cross-patient substitution.
"""

import os
import re
import pytest
from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService


@pytest.fixture(scope='module')
def app_instance():
    """Create Flask application instance for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture(scope='module')
def client(app_instance):
    """Test client."""
    return app_instance.test_client()


@pytest.fixture(scope='module')
def doctor_headers():
    """Valid auth headers for Dr. Sunita Mehta (user_id=2)."""
    user = User.get_by_id(2)
    token = AuthService.generate_access_token(user)['access_token']
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


@pytest.fixture(scope='module')
def other_doctor_headers():
    """Valid auth headers for Dr. Ananya Gupta (user_id=4)."""
    user = User.get_by_id(4)
    token = AuthService.generate_access_token(user)['access_token']
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


@pytest.fixture(scope='module')
def admin_headers():
    """Valid auth headers for Admin (user_id=1)."""
    user = User.get_by_id(1)
    token = AuthService.generate_access_token(user)['access_token']
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


# ─────────────────────────────────────────────────────────────
# 1. Test Specific Patient Record Fetching & Data Accuracy
# ─────────────────────────────────────────────────────────────
def test_fetch_patient_1_returns_rajesh_kumar(client, doctor_headers):
    """Verify that requesting patient_id=1 returns Rajesh Kumar, not Ravi Kumar."""
    res = client.get('/api/v1/patients/1', headers=doctor_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('success') is True
    patient = data.get('data')
    assert patient['patient_id'] == 1
    assert patient['name'] == 'Rajesh Kumar'
    assert 'Ravi' not in patient['name']
    assert patient['patient_code'] == 'UHID-2026-00001'


def test_fetch_patient_2_returns_anita_devi(client, doctor_headers):
    """Verify that requesting patient_id=2 returns Anita Devi, completely isolated from patient 1."""
    res = client.get('/api/v1/patients/2', headers=doctor_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('success') is True
    patient = data.get('data')
    assert patient['patient_id'] == 2
    assert patient['name'] == 'Anita Devi'
    assert patient['patient_code'] == 'UHID-2026-00002'


def test_fetch_nonexistent_patient_returns_404_never_default(client, doctor_headers):
    """Verify that an invalid/non-existent patient ID returns 404, never falling back to patient 1."""
    res = client.get('/api/v1/patients/999999', headers=doctor_headers)
    assert res.status_code == 404
    data = res.get_json()
    assert data.get('success') is False
    assert 'not found' in data.get('error', '').lower()


# ─────────────────────────────────────────────────────────────
# 2. Test Clinical Decision & Evaluation for Correct Patient
# ─────────────────────────────────────────────────────────────
def test_decision_evaluate_patient_1(client, doctor_headers):
    """Verify evaluating decision for patient 1 returns Rajesh Kumar."""
    res = client.get('/decision/evaluate/1', headers=doctor_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('success') is True
    assert data.get('patient_id') == 1
    assert data.get('patient_name') == 'Rajesh Kumar'
    assert 'condition' in data
    assert 'recommendation' in data


def test_decision_evaluate_nonexistent_patient_returns_404(client, doctor_headers):
    """Verify evaluating decision for non-existent patient returns 404, never default."""
    res = client.get('/decision/evaluate/888888', headers=doctor_headers)
    assert res.status_code == 404
    data = res.get_json()
    assert data.get('success') is False


# ─────────────────────────────────────────────────────────────
# 3. Test RBAC & Cross-Doctor IDOR Isolation
# ─────────────────────────────────────────────────────────────
def test_cross_doctor_access_forbidden(client, other_doctor_headers):
    """
    Verify Dr. Ananya Gupta (user_id=4) cannot access Patient 1 (assigned to Dr. Sunita Mehta user_id=2).
    Enforces that patient data is never leaked to unassigned clinicians.
    """
    res = client.get('/api/v1/patients/1', headers=other_doctor_headers)
    assert res.status_code == 403
    data = res.get_json()
    assert data.get('success') is False
    assert 'not assigned' in data.get('error', '').lower() or 'forbidden' in data.get('error', '').lower()


def test_admin_can_access_any_patient(client, admin_headers):
    """Verify Administrator can access Patient 1."""
    res = client.get('/api/v1/patients/1', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('success') is True
    assert data['data']['name'] == 'Rajesh Kumar'


# ─────────────────────────────────────────────────────────────
# 4. Test Attendant Route Missing Patient ID
# ─────────────────────────────────────────────────────────────
def test_attendant_missing_patient_id_fails_no_default(client):
    """Verify attendant endpoint without patient_id returns 400 error rather than defaulting to patient 1."""
    res = client.get('/api/v1/attendant/patient')
    assert res.status_code in (400, 401)
    data = res.get_json()
    assert data.get('success') is False


# ─────────────────────────────────────────────────────────────
# 5. Frontend Files Static Code Audits
# ─────────────────────────────────────────────────────────────
def test_doctor_transfer_recommendations_has_no_hardcoded_ravi():
    """Verify Doctor_transfer_recommendations.html has no hardcoded 'Ravi Kumar'."""
    filepath = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\Jeevan_setu_frontend\Doctor\Doctor_transfer_recommendations\Doctor_transfer_recommendations.html"
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "Ravi Kumar" not in content, "Found hardcoded Ravi Kumar in Doctor_transfer_recommendations.html"
    assert "P001" not in content, "Found hardcoded P001 in Doctor_transfer_recommendations.html"
    assert "JeevanSetuPatientContext" in content, "Doctor_transfer_recommendations.html must use JeevanSetuPatientContext"
    assert "patient_context.js" in content, "Doctor_transfer_recommendations.html must include patient_context.js"
    assert "loadPatientRecommendation" in content


def test_doctor_ews_trends_has_no_hardcoded_ravi():
    """Verify Doctor_ews_trends.html has no hardcoded 'Ravi Kumar'."""
    filepath = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\Jeevan_setu_frontend\Doctor\Doctor_ews_trends\Doctor_ews_trends.html"
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "Ravi Kumar" not in content, "Found hardcoded Ravi Kumar in Doctor_ews_trends.html"
    assert "JeevanSetuPatientContext" in content
    assert "patient_context.js" in content


def test_doctor_ews_calculator_has_no_hardcoded_default_1():
    """Verify Doctor_ews_calculator.html does not hardcode let currentPatientId = 1."""
    filepath = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\Jeevan_setu_frontend\Doctor\Doctor_ews_calculator\Doctor_ews_calculator.html"
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    assert not re.search(r'let\s+currentPatientId\s*=\s*1\s*;', content), "Found hardcoded let currentPatientId = 1"


def test_nurse_enter_vitals_has_no_hardcoded_default_1():
    """Verify Nurse_enter_vitals.html does not hardcode let currentPatientId = 1."""
    filepath = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\Jeevan_setu_frontend\Nurse\Nurse_enter_vitals\Nurse_enter_vitals.html"
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    assert not re.search(r'let\s+currentPatientId\s*=\s*1\s*;', content), "Found hardcoded let currentPatientId = 1"


def test_patient_context_utility_exists():
    """Verify patient_context.js exists in static directories."""
    path1 = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\JEEVAN_SETU\static\js\patient_context.js"
    path2 = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\Jeevan_setu_frontend\static\js\patient_context.js"
    assert os.path.exists(path1)
    assert os.path.exists(path2)
    with open(path1, 'r', encoding='utf-8') as f:
        js = f.read()
    assert 'getPatientIdFromUrl' in js
    assert 'fetchPatient' in js
    assert 'renderPatientError' in js
