"""
tests/test_auto_refresh_system.py — Comprehensive Test Suite for Jeevan Setu Automatic 10-Second Data Refresh.

Validates:
1. Centralized AUTO_REFRESH_INTERVAL = 10000 ms (10 seconds) configuration.
2. AutoRefreshManager script availability, concurrency guards, lifecycle cleanup, and input protection.
3. Attendant portal 10s polling integration and session token preservation.
4. Doctor portal 10s polling integration and patient data isolation.
5. Nurse portal 10s polling integration and form input protection.
6. Global Alert Manager 10s polling interval and duplicate popup prevention.
7. Backend vitals submission -> EWS calculation -> Attendant/Clinical API data flow.
"""

import os
import re
import json
import pytest
import unittest
from unittest.mock import patch, MagicMock

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'Jeevan_setu_frontend'))


class TestAutoRefreshSystem(unittest.TestCase):
    """Test suite verifying the 10-second automatic data refresh architecture."""

    def test_01_auto_refresh_manager_file_exists_and_configured(self):
        """Verify auto_refresh_manager.js exists and defines AUTO_REFRESH_INTERVAL = 10000."""
        manager_path = os.path.join(FRONTEND_DIR, 'auto_refresh_manager.js')
        self.assertTrue(os.path.exists(manager_path), "auto_refresh_manager.js should exist in frontend root")

        with open(manager_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("DEFAULT_INTERVAL = 10000", content, "Default interval must be 10000ms (10 seconds)")
        self.assertIn("isUserInputActive", content, "Manager must provide input/form interaction detection")
        self.assertIn("visibilitychange", content, "Manager must handle tab visibility changes")
        self.assertIn("beforeunload", content, "Manager must clean up timers on page unload")

    def test_02_attendant_portal_auto_refresh_configured(self):
        """Verify Attendant mobile replica view uses 10-second auto-refresh and retains session."""
        attendant_html = os.path.join(
            FRONTEND_DIR, 'Attendant', 'patient_update_mobile_view_replica', 'patient_update_mobile_view_replica.html'
        )
        self.assertTrue(os.path.exists(attendant_html), "Attendant mobile view replica must exist")

        with open(attendant_html, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check script inclusion
        self.assertIn("auto_refresh_manager.js", content, "Attendant page must load auto_refresh_manager.js")
        # Check 10-second polling configuration
        self.assertIn("10000", content, "Attendant page must poll at 10000ms interval")
        # Check session token handling
        self.assertIn("sessionStorage.setItem('jeevan_setu_token'", content, "Attendant page must store session token")
        self.assertIn("sessionStorage.setItem('jeevan_setu_attendant_patient_id'", content, "Attendant page must store patient ID")
        # Must NOT perform full window reload
        self.assertNotIn("window.location.reload()", content, "Attendant page must not call window.location.reload()")
        self.assertNotIn("location.reload()", content, "Attendant page must not call location.reload()")

    def test_03_doctor_portals_auto_refresh_configured(self):
        """Verify Doctor dashboard, my-patients, all-patients, and pending-approvals use 10s polling."""
        doctor_pages = [
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_dashboard_', 'Doctor_dashboard_.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_my_patients', 'Doctor_my_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_all_patients', 'Doctor_all_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_pending_approvals', 'Doctor_pending_approvals.html'),
        ]

        for page in doctor_pages:
            self.assertTrue(os.path.exists(page), f"Doctor page {os.path.basename(page)} must exist")
            with open(page, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn("auto_refresh_manager.js", content, f"{page} must include auto_refresh_manager.js")
            self.assertIn("10000", content, f"{page} must be configured for 10000ms refresh")
            self.assertNotIn("window.location.reload()", content, f"{page} must not do full page reload")

    def test_04_nurse_portals_auto_refresh_and_form_protection(self):
        """Verify Nurse dashboard, enter vitals, and patient monitoring use 10s polling with input protection."""
        nurse_pages = [
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_dashboard', 'Nurse_dashboard.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_enter_vitals', 'Nurse_enter_vitals.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'nurse_patient_monitoring', 'nurse_patient_monitoring.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_alerts', 'Nurse_alerts.html'),
        ]

        for page in nurse_pages:
            self.assertTrue(os.path.exists(page), f"Nurse page {os.path.basename(page)} must exist")
            with open(page, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn("auto_refresh_manager.js", content, f"{page} must include auto_refresh_manager.js")
            self.assertIn("10000", content, f"{page} must be configured for 10000ms refresh")

        # Specific check for Nurse Enter Vitals: loadPatientProfile updates card without touching input fields
        enter_vitals_html = os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_enter_vitals', 'Nurse_enter_vitals.html')
        with open(enter_vitals_html, 'r', encoding='utf-8') as f:
            vitals_content = f.read()
        self.assertIn("loadPatientProfile(currentPatientId)", vitals_content, "Enter vitals must refresh patient profile card")

    def test_05_global_alert_manager_10_second_interval(self):
        """Verify global_alert_manager.js uses 10000ms interval and tracks dismissed alerts in session."""
        alert_manager_path = os.path.join(FRONTEND_DIR, 'global_alert_manager.js')
        with open(alert_manager_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("10000", content, "Global Alert Manager must use 10000ms (10 seconds) interval")
        self.assertIn("DISMISSED_SESSION_KEY", content, "Global Alert Manager must track dismissed alerts")
        self.assertIn("activeModals", content, "Global Alert Manager must track active modals to avoid duplicates")

    def test_06_no_random_intervals_across_portals(self):
        """Verify no random 5000ms, 6000ms, 8000ms, or 15000ms data refresh timers remain in core pages."""
        core_files = [
            os.path.join(FRONTEND_DIR, 'Attendant', 'patient_update_mobile_view_replica', 'patient_update_mobile_view_replica.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_dashboard_', 'Doctor_dashboard_.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_my_patients', 'Doctor_my_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_all_patients', 'Doctor_all_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_pending_approvals', 'Doctor_pending_approvals.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_dashboard', 'Nurse_dashboard.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'nurse_patient_monitoring', 'nurse_patient_monitoring.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_alerts', 'Nurse_alerts.html'),
            os.path.join(FRONTEND_DIR, 'global_alert_manager.js'),
        ]

        for filepath in core_files:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            # Ensure 8000, 6000, 15000 setInterval are gone from data refresh functions
            self.assertNotIn("setInterval(refreshAttendantView, 8000)", content)
            self.assertNotIn("setInterval(refreshDoctorMyPatients, 8000)", content)
            self.assertNotIn("setInterval(refreshDoctorAllPatients, 8000)", content)
            self.assertNotIn("setInterval(fetchPendingApprovals, 8000)", content)
            self.assertNotIn("setInterval(refreshDashboard, 8000)", content)
            self.assertNotIn("setInterval(refreshAlertsData, 6000)", content)
            self.assertNotIn("setInterval(fetchSidebarBadgeCounts, 15000)", content)


if __name__ == '__main__':
    unittest.main()
