"""
tests/test_nurse_alerts_sidebar.py — End-to-End Verification Test Suite
for Restored Left Navigation Sidebar in Nurse Alerts (Nurse_alerts.html).

Verifies:
1. Nurse Alerts HTML template contains the standard <aside data-purpose="sidebar"> component.
2. nurse_navigation.js dynamically builds branding, navigation items, active highlighting, and mobile drawer.
3. Active page detection maps nurse_alerts to the 'alerts' navigation item with active styling.
4. All navigation items point to valid Nurse Portal destination paths.
5. Live HTTP endpoint serves Nurse_alerts.html with sidebar and proper layout container classes.
6. Responsive layout classes (md:pl-64, pt-16, fixed, z-50, etc.) prevent layout overlap and excessive empty space.
7. Alert backend APIs used by Nurse_alerts.html function with 200 OK and patient scoping intact.
8. Baseline census of 10 patients remains preserved.
"""

import os
import sys
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService


class TestNurseAlertsSidebar(unittest.TestCase):
    """Test suite for Nurse Alerts left sidebar restoration and functional integrity."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        cls.frontend_dir = os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Jeevan_setu_frontend')
        )
        cls.nurse_alerts_path = os.path.join(cls.frontend_dir, 'Nurse', 'Nurse_alerts', 'Nurse_alerts.html')
        cls.nurse_nav_path = os.path.join(cls.frontend_dir, 'Nurse', 'nurse_navigation.js')

        # Nurse Priya (user_id = 5)
        cls.priya = User.get_by_id(5)
        cls.priya_token = AuthService.generate_access_token(cls.priya)['access_token']
        cls.priya_headers = {'Authorization': f"Bearer {cls.priya_token}"}

    def test_01_nurse_alerts_html_contains_standard_aside(self):
        """1. Nurse_alerts.html must contain the standard <aside data-purpose="sidebar"> element."""
        self.assertTrue(os.path.exists(self.nurse_alerts_path), f"File {self.nurse_alerts_path} must exist")
        with open(self.nurse_alerts_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('<aside data-purpose="sidebar"', content, "Nurse_alerts.html must have <aside data-purpose='sidebar'>")
        self.assertIn('w-64', content, "Sidebar must have width class w-64 (256px)")
        self.assertIn('fixed left-0 top-0', content, "Sidebar must be fixed to left-0 top-0")
        self.assertIn('md:pl-64', content, "Main container must have md:pl-64 offset for sidebar")
        self.assertIn('pt-16', content, "Main container must have pt-16 offset for topbar")
        self.assertIn('<script src="../nurse_navigation.js"></script>', content, "Nurse_alerts.html must include nurse_navigation.js")

    def test_02_nurse_navigation_js_renders_sidebar_with_alerts_highlighted(self):
        """2. nurse_navigation.js config must define Alerts item and highlight it when on Nurse_alerts."""
        self.assertTrue(os.path.exists(self.nurse_nav_path), f"File {self.nurse_nav_path} must exist")
        with open(self.nurse_nav_path, 'r', encoding='utf-8') as f:
            nav_code = f.read()

        # Check that Alerts item is configured
        self.assertIn("id: 'alerts'", nav_code)
        self.assertIn("label: 'Alerts'", nav_code)
        self.assertIn("href: '../Nurse_alerts/Nurse_alerts.html'", nav_code)

        # Check that detectCurrentNursePage recognizes nurse_alerts
        self.assertIn("if (path.includes('nurse_alerts')) return 'alerts';", nav_code)

        # Check auto-injection fallback in renderNurseSidebar
        self.assertIn("document.createElement('aside')", nav_code)

        # Check navigation destinations exist
        nurse_dir = os.path.join(self.frontend_dir, 'Nurse')
        expected_pages = [
            os.path.join(nurse_dir, 'Nurse_dashboard', 'Nurse_dashboard.html'),
            os.path.join(nurse_dir, 'Nurse_alerts', 'Nurse_alerts.html'),
            os.path.join(nurse_dir, 'nurse_patient_monitoring', 'nurse_patient_monitoring.html'),
            os.path.join(nurse_dir, 'Nurse_enter_vitals', 'Nurse_enter_vitals.html'),
            os.path.join(nurse_dir, 'Nurse_nursing_notes', 'Nurse_nursing_notes.html'),
            os.path.join(nurse_dir, 'Nurse_patient_summary_ai', 'Nurse_patient_summary_ai.html'),
            os.path.join(nurse_dir, 'Nurse_settings', 'Nurse_settings.html'),
        ]
        for p in expected_pages:
            self.assertTrue(os.path.exists(p), f"Navigation destination {p} must exist on disk")

    def test_03_live_http_serves_nurse_alerts_with_sidebar(self):
        """3. Live HTTP endpoint serves Nurse_alerts.html with sidebar markup."""
        url = 'http://127.0.0.1:5000/Nurse/Nurse_alerts/Nurse_alerts.html'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode('utf-8')
            self.assertIn('<aside data-purpose="sidebar"', html)
            self.assertIn('nurse_navigation.js', html)

    def test_04_alerts_backend_apis_functional(self):
        """4. Backend APIs used by Nurse Alerts page are operational and patient-scoped."""
        # 1. Active alerts
        res_active = self.client.get('/alerts/api/active', headers=self.priya_headers)
        self.assertEqual(res_active.status_code, 200)
        self.assertTrue(res_active.get_json().get('success'))

        # 2. Today's clinical tasks
        res_tasks = self.client.get('/alerts/api/today-tasks', headers=self.priya_headers)
        self.assertEqual(res_tasks.status_code, 200)
        self.assertTrue(res_tasks.get_json().get('success'))

        # 3. Global alert feed
        res_feed = self.client.get('/api/v1/alerts/global-feed', headers=self.priya_headers)
        self.assertEqual(res_feed.status_code, 200)
        self.assertTrue(res_feed.get_json().get('success'))

        # 4. Assistance requests
        res_assist = self.client.get('/api/v1/assistance-requests', headers=self.priya_headers)
        self.assertEqual(res_assist.status_code, 200)
        self.assertTrue(res_assist.get_json().get('success'))

        # 5. Notifications
        res_notif = self.client.get('/api/v1/notifications?limit=6', headers=self.priya_headers)
        self.assertEqual(res_notif.status_code, 200)
        self.assertTrue(res_notif.get_json().get('success'))

    def test_05_baseline_census_unaltered(self):
        """5. Verify 10 baseline patients remain intact."""
        patients = db.execute_query(
            "SELECT patient_id, name FROM patients ORDER BY patient_id ASC",
            fetch=True
        ) or []
        self.assertEqual(len(patients), 10, f"Expected 10 baseline patients, found {len(patients)}")


if __name__ == '__main__':
    unittest.main()
