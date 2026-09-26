"""
tests/test_patient_pdf_report.py — Comprehensive Unit & Integration Tests for Admin Patient PDF Report Generation.
"""

import os
import json
import pytest
from app import create_app
from database.db import db
from modules.report_engine import (
    generate_multi_patient_report_data,
    render_multi_patient_pdf
)
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.user_model import User
from services.auth_service import AuthService


@pytest.fixture
def app_instance():
    """Create Flask application instance."""
    app = create_app()
    with app.app_context():
        yield app


@pytest.fixture
def client(app_instance):
    """Test client."""
    return app_instance.test_client()


@pytest.fixture
def admin_token(app_instance):
    """Generate valid Admin JWT Bearer token."""
    with app_instance.app_context():
        # Look for an admin user or create token with admin role
        admin_user = db.execute_query(
            "SELECT * FROM users WHERE role = 'admin' LIMIT 1",
            fetch=True
        )
        if admin_user:
            token_data = AuthService.generate_access_token(admin_user[0])
            return token_data['access_token'], admin_user[0]['user_id']
        else:
            mock_user = {
                'user_id': 1,
                'username': 'admin',
                'email': 'admin@jeevansetu.org',
                'role': 'admin',
                'department': 'Administration'
            }
            token_data = AuthService.generate_access_token(mock_user)
            return token_data['access_token'], 1


def test_generate_multi_patient_report_data(app_instance):
    """Test fetching patient clinical data from MySQL."""
    with app_instance.app_context():
        # Fetch up to 3 real patients from MySQL
        pts = db.execute_query("SELECT patient_id FROM patients LIMIT 3", fetch=True) or []
        if not pts:
            pytest.skip("No patients in database for test")

        p_ids = [p['patient_id'] for p in pts]
        res = generate_multi_patient_report_data(p_ids, generated_by=1, generated_by_name="Chief Administrator")

        assert 'error' not in res
        assert res['patient_count'] == len(p_ids)
        assert len(res['patients']) == len(p_ids)

        for p_data in res['patients']:
            assert 'patient_code' in p_data
            assert 'name' in p_data
            assert 'ews_breakdown' in p_data
            assert 'decision_support' in p_data
            assert 'vitals_history' in p_data
            assert 'transfers' in p_data


def test_render_multi_patient_pdf(app_instance):
    """Test ReportLab PDF binary generation with permanent repeating hospital header."""
    with app_instance.app_context():
        pts = db.execute_query("SELECT patient_id FROM patients LIMIT 2", fetch=True) or []
        if not pts:
            pytest.skip("No patients in database for test")

        p_ids = [p['patient_id'] for p in pts]
        report_data = generate_multi_patient_report_data(p_ids, generated_by=1, generated_by_name="Chief Administrator")
        assert 'error' not in report_data

        pdf_bytes = render_multi_patient_pdf(report_data)

        # PDF binary starts with %PDF-
        assert pdf_bytes.startswith(b'%PDF-')
        assert len(pdf_bytes) > 2000  # Valid PDF size


def test_empty_patient_selection_returns_400(client, admin_token):
    """Test that submitting an empty patient list returns HTTP 400."""
    token, _ = admin_token
    response = client.post(
        '/api/v1/reports/patients/pdf',
        headers={'Authorization': f'Bearer {token}'},
        json={'patient_ids': []}
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'select at least one patient' in data['error'].lower()


def test_patient_pdf_endpoint_success(client, admin_token, app_instance):
    """Test full HTTP POST endpoint returning application/pdf with custom filename."""
    token, _ = admin_token
    with app_instance.app_context():
        pts = db.execute_query("SELECT patient_id FROM patients LIMIT 2", fetch=True) or []
        if not pts:
            pytest.skip("No patients in database for test")

        p_ids = [p['patient_id'] for p in pts]

    response = client.post(
        '/api/v1/reports/patients/pdf',
        headers={'Authorization': f'Bearer {token}'},
        json={'patient_ids': p_ids}
    )

    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert response.data.startswith(b'%PDF-')
    disp = response.headers.get('Content-Disposition', '')
    assert 'attachment' in disp
    assert '.pdf' in disp
