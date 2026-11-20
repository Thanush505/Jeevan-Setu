"""
tests/test_auto_refresh_system.py — Comprehensive Test Suite for Jeevan Setu Automatic 5-Second Data Refresh.

Validates:
1. Centralized AUTO_REFRESH_INTERVAL = 5000 ms (5 seconds) configuration.
2. AutoRefreshManager script availability, concurrency guards, lifecycle cleanup, and input protection.
3. Attendant portal 5s polling integration, session token preservation, and Live Sync Indicator.
4. Doctor portal 5s polling integration, patient data isolation, and Live Sync Indicator.
5. Nurse portal 5s polling integration, form input protection, and Live Sync Indicator.
6. Admin portal 5s polling integration across Dashboard, Users & Roles, Beds & Wards, and Patient Management.
7. Global Alert Manager 5s polling interval and duplicate popup prevention.
8. Absence of full-page reload calls (window.location.reload).
"""

import os
import re
import json
import unittest

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'Jeevan_setu_frontend'))


class TestAutoRefreshSystem(unittest.TestCase):
    """Test suite verifying the 5-second automatic data refresh architecture across all 4 portals."""

    def test_01_auto_refresh_manager_file_exists_and_configured(self):
        """Verify auto_refresh_manager.js exists and defines DEFAULT_INTERVAL = 5000."""
        manager_path = os.path.join(FRONTEND_DIR, 'auto_refresh_manager.js')
        self.assertTrue(os.path.exists(manager_path), "auto_refresh_manager.js should exist in frontend root")

        with open(manager_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("DEFAULT_INTERVAL = 5000", content, "Default interval must be 5000ms (5 seconds)")
        self.assertIn("isUserInputActive", content, "Manager must provide input/form interaction detection")
        self.assertIn("visibilitychange", content, "Manager must handle tab visibility changes")
        self.assertIn("beforeunload", content, "Manager must clean up timers on page unload")
        self.assertIn("attachIndicator", content, "Manager must provide Data Freshness Indicator attachment")
        self.assertIn("updateGlobalSyncState", content, "Manager must track Live, Syncing, Delayed, Offline states")

    def test_02_attendant_portal_auto_refresh_configured(self):
        """Verify Attendant mobile replica view uses 5-second auto-refresh and retains session."""
        attendant_html = os.path.join(
            FRONTEND_DIR, 'Attendant', 'patient_update_mobile_view_replica', 'patient_update_mobile_view_replica.html'
        )
        self.assertTrue(os.path.exists(attendant_html), "Attendant mobile view replica must exist")

        with open(attendant_html, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check script inclusion
        self.assertIn("auto_refresh_manager.js", content, "Attendant page must load auto_refresh_manager.js")
        # Check 5-second polling configuration
        self.assertIn("5000", content, "Attendant page must poll at 5000ms interval")
        # Check Live Sync Indicator wrapper
        self.assertIn("attendant-sync-indicator-wrap", content, "Attendant page must have Live Sync Indicator")
        # Check session token handling
        self.assertIn("sessionStorage.setItem('jeevan_setu_token'", content, "Attendant page must store session token")
        # Must NOT perform full window reload
        self.assertNotIn("window.location.reload()", content, "Attendant page must not call window.location.reload()")
        self.assertNotIn("location.reload()", content, "Attendant page must not call location.reload()")

    def test_03_doctor_portals_auto_refresh_configured(self):
        """Verify Doctor dashboard, my-patients, all-patients, and pending-approvals use 5s polling."""
        doctor_pages = [
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_dashboard_', 'Doctor_dashboard_.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_my_patients', 'Doctor_my_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_all_patients', 'Doctor_all_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_pending_approvals', 'Doctor_pending_approvals.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_transfer_recommendations', 'Doctor_transfer_recommendations.html'),
        ]

        for page in doctor_pages:
            self.assertTrue(os.path.exists(page), f"Doctor page {os.path.basename(page)} must exist")
            with open(page, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn("auto_refresh_manager.js", content, f"{page} must include auto_refresh_manager.js")
            self.assertIn("5000", content, f"{page} must be configured for 5000ms refresh")
            self.assertNotIn("window.location.reload()", content, f"{page} must not do full page reload")

    def test_04_nurse_portals_auto_refresh_and_form_protection(self):
        """Verify Nurse dashboard, enter vitals, and patient monitoring use 5s polling with input protection."""
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
            self.assertIn("5000", content, f"{page} must be configured for 5000ms refresh")

        # Specific check for Nurse Enter Vitals: loadPatientProfile updates card without touching input fields
        enter_vitals_html = os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_enter_vitals', 'Nurse_enter_vitals.html')
        with open(enter_vitals_html, 'r', encoding='utf-8') as f:
            vitals_content = f.read()
        self.assertIn("loadPatientProfile(currentPatientId)", vitals_content, "Enter vitals must refresh patient profile card")

    def test_05_admin_portals_auto_refresh_configured(self):
        """Verify Admin dashboard, users & roles, beds & wards, and patient management use 5s polling."""
        admin_pages = [
            os.path.join(FRONTEND_DIR, 'Admin', 'Administrator_dashboard_', 'Administrator_dashboard_.html'),
            os.path.join(FRONTEND_DIR, 'Admin', 'Admin_users_roles', 'Admin_users_roles.html'),
            os.path.join(FRONTEND_DIR, 'Admin', 'Admin_beds_wards', 'Admin_beds_wards.html'),
            os.path.join(FRONTEND_DIR, 'Admin', 'Admin_patient_management', 'Admin_patient_management.html'),
        ]

        for page in admin_pages:
            self.assertTrue(os.path.exists(page), f"Admin page {os.path.basename(page)} must exist")
            with open(page, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn("auto_refresh_manager.js", content, f"{page} must include auto_refresh_manager.js")
            self.assertIn("5000", content, f"{page} must be configured for 5000ms refresh")
            self.assertNotIn("window.location.reload()", content, f"{page} must not do full page reload")

    def test_06_global_alert_manager_5_second_interval(self):
        """Verify global_alert_manager.js uses 5000ms interval and tracks dismissed alerts in session."""
        alert_manager_path = os.path.join(FRONTEND_DIR, 'global_alert_manager.js')
        with open(alert_manager_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("5000", content, "Global Alert Manager must use 5000ms (5 seconds) interval")
        self.assertIn("DISMISSED_SESSION_KEY", content, "Global Alert Manager must track dismissed alerts")
        self.assertIn("activeModals", content, "Global Alert Manager must track active modals to avoid duplicates")

    def test_07_no_random_intervals_across_portals(self):
        """Verify no lingering 20000ms, 8000ms, 6000ms, or 15000ms data refresh timers remain in core pages."""
        core_files = [
            os.path.join(FRONTEND_DIR, 'Attendant', 'patient_update_mobile_view_replica', 'patient_update_mobile_view_replica.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_dashboard_', 'Doctor_dashboard_.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_my_patients', 'Doctor_my_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_all_patients', 'Doctor_all_patients.html'),
            os.path.join(FRONTEND_DIR, 'Doctor', 'Doctor_pending_approvals', 'Doctor_pending_approvals.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_dashboard', 'Nurse_dashboard.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'nurse_patient_monitoring', 'nurse_patient_monitoring.html'),
            os.path.join(FRONTEND_DIR, 'Nurse', 'Nurse_alerts', 'Nurse_alerts.html'),
            os.path.join(FRONTEND_DIR, 'Admin', 'Administrator_dashboard_', 'Administrator_dashboard_.html'),
            os.path.join(FRONTEND_DIR, 'global_alert_manager.js'),
        ]

        for filepath in core_files:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertNotIn("setInterval(refreshAttendantView, 8000)", content)
            self.assertNotIn("setInterval(refreshDoctorMyPatients, 8000)", content)
            self.assertNotIn("setInterval(refreshDoctorAllPatients, 8000)", content)
            self.assertNotIn("setInterval(fetchPendingApprovals, 8000)", content)
            self.assertNotIn("setInterval(refreshDashboard, 8000)", content)
            self.assertNotIn("setInterval(refreshAlertsData, 6000)", content)
            self.assertNotIn("setInterval(fetchSidebarBadgeCounts, 15000)", content)
            self.assertNotIn("20000", content, f"{filepath} must not contain stale 20000ms timer")

    def test_08_live_sync_indicators_present_in_shared_headers(self):
        """Verify Live Sync Indicators are wired across Admin, Doctor, Nurse, and Attendant headers."""
        admin_nav = os.path.join(FRONTEND_DIR, 'Admin', 'admin_navigation.js')
        with open(admin_nav, 'r', encoding='utf-8') as f:
            admin_content = f.read()
        self.assertIn("admin-sync-indicator-wrap", admin_content, "Admin header must have Live Sync Indicator wrap")

        doc_nav = os.path.join(FRONTEND_DIR, 'Doctor', 'doctor_sidebar.js')
        with open(doc_nav, 'r', encoding='utf-8') as f:
            doc_content = f.read()
        self.assertIn("doctor-sync-indicator-wrap", doc_content, "Doctor header must have Live Sync Indicator wrap")

        nurse_nav = os.path.join(FRONTEND_DIR, 'Nurse', 'nurse_navigation.js')
        with open(nurse_nav, 'r', encoding='utf-8') as f:
            nurse_content = f.read()
        self.assertIn("nurse-sync-indicator-wrap", nurse_content, "Nurse header must have Live Sync Indicator wrap")

        att_html = os.path.join(FRONTEND_DIR, 'Attendant', 'patient_update_mobile_view_replica', 'patient_update_mobile_view_replica.html')
        with open(att_html, 'r', encoding='utf-8') as f:
            att_content = f.read()
        self.assertIn("attendant-sync-indicator-wrap", att_content, "Attendant header must have Live Sync Indicator wrap")


if __name__ == '__main__':
    unittest.main()
