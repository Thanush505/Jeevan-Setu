"""
tests/test_api.py — API integration tests for Flask routes.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    """Create a test Flask application."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestAuthRoutes:
    """Test authentication routes."""

    def test_login_page_loads(self, client):
        """GET /auth/login should return 200."""
        response = client.get('/auth/login')
        assert response.status_code == 200

    def test_root_redirects_to_login(self, client):
        """GET / should redirect to login."""
        response = client.get('/')
        assert response.status_code == 302

    def test_logout_requires_auth(self, client):
        """GET /auth/logout should redirect if not logged in."""
        response = client.get('/auth/logout')
        assert response.status_code == 302


class TestProtectedRoutes:
    """Test that protected routes require authentication."""

    def test_dashboard_requires_auth(self, client):
        response = client.get('/patients/dashboard')
        assert response.status_code == 302

    def test_add_patient_requires_auth(self, client):
        response = client.get('/patients/add')
        assert response.status_code == 302

    def test_alerts_require_auth(self, client):
        response = client.get('/alerts/')
        assert response.status_code == 302

    def test_chatbot_requires_auth(self, client):
        response = client.get('/chatbot/')
        assert response.status_code == 302


class TestAttendantRoutes:
    """Test attendant (public) routes."""

    def test_attendant_dashboard_no_code(self, client):
        """Attendant dashboard without code should show error."""
        response = client.get('/attendant/dashboard')
        assert response.status_code == 200

    def test_attendant_invalid_code(self, client):
        """Invalid access code should show error."""
        response = client.get('/attendant/dashboard?code=INVALID')
        assert response.status_code == 200
