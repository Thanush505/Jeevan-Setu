"""
Comprehensive Mobile Responsiveness & Cross-Portal Verification Test Suite
==========================================================================
Verifies mobile responsiveness, viewport configuration, collapsible drawer
navigation, horizontal overflow prevention, responsive tables/grids/modals,
relative API paths (zero hardcoded localhost/127.0.0.1 in frontend code),
and live backend/database end-to-end integration across all 44 HTML pages,
19 JS files, and 2 CSS files in Jeevan Setu.
"""

import os
import re
import sys

# Ensure project root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
FRONTEND_ROOT = os.path.join(PROJECT_ROOT, "Jeevan_setu_frontend")

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService


def get_all_frontend_files(ext):
    found = []
    for root, _, files in os.walk(FRONTEND_ROOT):
        for f in files:
            if f.endswith(ext):
                found.append(os.path.join(root, f))
    return sorted(found)


def test_1_all_44_html_pages_have_viewport_meta():
    """Verify every HTML page across all 6 portals has a valid responsive viewport meta tag."""
    html_files = get_all_frontend_files(".html")
    assert len(html_files) == 44, f"Expected 44 HTML files, found {len(html_files)}"

    missing = []
    for path in html_files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if not re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*content=["\'][^"\']*width=device-width', content, re.I) and \
           not re.search(r'<meta[^>]*content=["\'][^"\']*width=device-width[^>]*name=["\']viewport["\']', content, re.I):
            missing.append(os.path.relpath(path, FRONTEND_ROOT))

    assert not missing, f"Pages missing responsive viewport meta tag: {missing}"
    print(f"[PASS] Test 1: All {len(html_files)}/44 HTML files have <meta name='viewport' content='width=device-width, initial-scale=1.0'>")


def test_2_no_hardcoded_localhost_in_frontend_assets():
    """Verify no frontend HTML or JS file hardcodes 127.0.0.1 or localhost URLs so LAN mobile devices work."""
    html_files = get_all_frontend_files(".html")
    js_files = get_all_frontend_files(".js")

    violations = []
    for path in html_files + js_files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        matches = re.findall(r'https?://(?:127\.0\.0\.1|localhost)(?::\d+)?', content, re.I)
        if matches:
            violations.append((os.path.relpath(path, FRONTEND_ROOT), matches))

    assert not violations, f"Hardcoded localhost/127.0.0.1 URLs found: {violations}"
    print(f"[PASS] Test 2: Zero hardcoded localhost/127.0.0.1 URLs across {len(html_files)} HTML and {len(js_files)} JS files")


def test_3_doctor_portal_mobile_drawer_and_responsive_rules():
    """Verify Doctor Portal shared navigation (doctor_sidebar.js) provides off-canvas drawer, hamburger toggle, backdrop, and table wrappers."""
    doctor_js_path = os.path.join(FRONTEND_ROOT, "Doctor", "doctor_sidebar.js")
    assert os.path.exists(doctor_js_path), "Doctor/doctor_sidebar.js missing"

    with open(doctor_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    required_markers = [
        "doctor-responsive-theme-styles",
        "toggleMobileDoctorSidebar",
        "setupMobileDoctorDrawer",
        "doctor-sidebar-backdrop",
        "doctor-sidebar-close-btn",
        "doctor-mobile-menu-btn",
        "sidebar-mobile-open",
        "@media (max-width: 1024px)",
        "@media (max-width: 767px)",
        "overflow-x: hidden",
        "overflow-x-auto",
    ]
    for marker in required_markers:
        assert marker in js, f"Missing marker '{marker}' in Doctor/doctor_sidebar.js"

    # Verify all 14 Doctor HTML pages include doctor_sidebar.js
    doctor_html = [p for p in get_all_frontend_files(".html") if os.sep + "Doctor" + os.sep in p]
    assert len(doctor_html) == 14, f"Expected 14 Doctor HTML pages, found {len(doctor_html)}"
    for p in doctor_html:
        with open(p, "r", encoding="utf-8") as f:
            c = f.read()
        assert "doctor_sidebar.js" in c, f"{os.path.relpath(p, FRONTEND_ROOT)} does not load doctor_sidebar.js"

    print(f"[PASS] Test 3: Doctor Portal ({len(doctor_html)} pages) mobile drawer, hamburger button, backdrop, and responsive styles verified")


def test_4_admin_portal_mobile_drawer_and_responsive_rules():
    """Verify Admin Portal shared navigation (admin_navigation.js) provides off-canvas drawer, backdrop, close button, and constrained dropdowns."""
    admin_js_path = os.path.join(FRONTEND_ROOT, "Admin", "admin_navigation.js")
    assert os.path.exists(admin_js_path), "Admin/admin_navigation.js missing"

    with open(admin_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    required_markers = [
        "admin-sidebar-backdrop",
        "admin-sidebar-close-btn",
        "admin-sidebar-toggle",
        "sidebar-mobile-open",
        "@media (max-width: 1024px)",
        "@media (max-width: 640px)",
        "calc(100vw - 24px)",
        "overflow-x-auto",
    ]
    for marker in required_markers:
        assert marker in js, f"Missing marker '{marker}' in Admin/admin_navigation.js"

    # Verify Admin Dashboard tables are wrapped in overflow-x-auto
    admin_dash_path = os.path.join(FRONTEND_ROOT, "Admin", "Administrator_dashboard_", "Administrator_dashboard_.html")
    with open(admin_dash_path, "r", encoding="utf-8") as f:
        dash_html = f.read()
    assert dash_html.count('<div class="overflow-x-auto">') >= 3, "Expected all 3 tables in Administrator_dashboard_.html to be wrapped in overflow-x-auto"

    print("[PASS] Test 4: Admin Portal mobile drawer, backdrop, close button, dropdown constraints, and scrollable tables verified")


def test_5_nurse_portal_mobile_drawer_and_responsive_rules():
    """Verify Nurse Portal shared navigation (nurse_navigation.js) provides off-canvas drawer, hamburger toggle, backdrop, and constrained dropdowns."""
    nurse_js_path = os.path.join(FRONTEND_ROOT, "Nurse", "nurse_navigation.js")
    assert os.path.exists(nurse_js_path), "Nurse/nurse_navigation.js missing"

    with open(nurse_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    required_markers = [
        "toggleMobileNurseSidebar",
        "nurse-sidebar-backdrop",
        "nurse-sidebar-toggle",
        "sidebar-mobile-open",
        "@media (max-width: 767px)",
        "calc(100vw - 24px)",
        "max-width: 82vw",
    ]
    for marker in required_markers:
        assert marker in js, f"Missing marker '{marker}' in Nurse/nurse_navigation.js"

    print("[PASS] Test 5: Nurse Portal mobile drawer, backdrop, hamburger toggle, and mobile dropdown constraints verified")


def test_6_global_alert_manager_mobile_popup_responsiveness():
    """Verify all 4 copies of global_alert_manager.js include mobile viewport containment (@media (max-width: 640px))."""
    alert_js_paths = [
        os.path.join(FRONTEND_ROOT, "global_alert_manager.js"),
        os.path.join(FRONTEND_ROOT, "Doctor", "global_alert_manager.js"),
        os.path.join(FRONTEND_ROOT, "Nurse", "global_alert_manager.js"),
        os.path.join(BACKEND_ROOT, "static", "js", "global_alert_manager.js"),
    ]
    for p in alert_js_paths:
        assert os.path.exists(p), f"Missing {p}"
        with open(p, "r", encoding="utf-8") as f:
            c = f.read()
        assert "@media (max-width: 640px)" in c, f"Missing mobile media query in {p}"
        assert "calc(100vw - 20px)" in c, f"Missing mobile width constraint in {p}"
        assert "js-alert-actions" in c, f"Missing mobile action button wrapper class in {p}"

    print("[PASS] Test 6: All 4 copies of global_alert_manager.js have mobile-responsive popup rules")


def test_7_patient_summary_ai_and_simulator_mobile_responsiveness():
    """Verify Doctor & Nurse Patient Summary AI pages and Developer Telemetry Simulator have mobile-friendly headers and CSS."""
    doc_ai = os.path.join(FRONTEND_ROOT, "Doctor", "Doctor_patient_summary_ai", "Doctor_patient_summary_ai.html")
    nurse_ai = os.path.join(FRONTEND_ROOT, "Nurse", "Nurse_patient_summary_ai", "Nurse_patient_summary_ai.html")
    sim_html = os.path.join(FRONTEND_ROOT, "Developer", "Telemetry_Simulator", "Telemetry_Simulator.html")
    sim_css = os.path.join(FRONTEND_ROOT, "Developer", "Telemetry_Simulator", "Telemetry_Simulator.css")

    with open(doc_ai, "r", encoding="utf-8") as f:
        doc_c = f.read()
    assert "px-3 sm:px-6" in doc_c and "flex-wrap" in doc_c and "w-full sm:w-72 lg:w-96" in doc_c, "Doctor Patient Summary AI header should use responsive padding, flex-wrap, and responsive search bar"

    with open(nurse_ai, "r", encoding="utf-8") as f:
        nurse_c = f.read()
    assert "px-3 sm:px-6" in nurse_c and "flex-wrap" in nurse_c, "Nurse Patient Summary AI telemetry bar should use responsive padding and flex-wrap"

    with open(sim_html, "r", encoding="utf-8") as f:
        sim_h = f.read()
    assert "flex-wrap" in sim_h, "Telemetry Simulator header should wrap on mobile"

    with open(sim_css, "r", encoding="utf-8") as f:
        sim_c = f.read()
    assert "@media (max-width: 640px)" in sim_c, "Telemetry Simulator CSS should include mobile breakpoint adjustments"

    print("[PASS] Test 7: Doctor & Nurse Patient Summary AI and Developer Telemetry Simulator mobile layouts verified")


def test_8_live_routes_and_api_endpoints_across_all_portals():
    """Verify Flask serves all major portal pages and API endpoints with HTTP 200 and preserves the 10 baseline patients."""
    app = create_app()
    client = app.test_client()

    routes_to_check = [
        "/Login/Login.html",
        "/Admin/Administrator_dashboard_/Administrator_dashboard_.html",
        "/Admin/Admin_patient_management/Admin_patient_management.html",
        "/Admin/Admin_beds_wards/Admin_beds_wards.html",
        "/Admin/Admin_users_roles/Admin_users_roles.html",
        "/Admin/Admin_attendant_access/Admin_attendant_access.html",
        "/Admin/admin_navigation.js",
        "/Doctor/Doctor_dashboard_/Doctor_dashboard_.html",
        "/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html",
        "/Doctor/Doctor_pending_approvals/Doctor_pending_approvals.html",
        "/Doctor/Doctor_my_patients/Doctor_my_patients.html",
        "/Doctor/doctor_sidebar.js",
        "/Nurse/Nurse_dashboard/Nurse_dashboard.html",
        "/Nurse/Nurse_alerts/Nurse_alerts.html",
        "/Nurse/Nurse_patient_summary_ai/Nurse_patient_summary_ai.html",
        "/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html",
        "/Nurse/nurse_navigation.js",
        "/Attendant/attendant_login_mobile_revised/attendant_login_mobile_revised.html",
        "/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html",
        "/Developer/Telemetry_Simulator/Telemetry_Simulator.html",
        "/Developer/Telemetry_Simulator/Telemetry_Simulator.css",
    ]

    for route in routes_to_check:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} returned {res.status_code}"

    # Verify Admin authentication and check 10 canonical baseline patients
    admin_user = User.get_by_id(1)
    assert admin_user is not None, "Admin user (ID 1) must exist"
    token = AuthService.generate_access_token(admin_user)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patients_res = client.get("/api/v1/patients?limit=50", headers=headers)
    assert patients_res.status_code == 200, f"/api/v1/patients returned {patients_res.status_code}"

    # Verify all 10 canonical baseline patients in database
    db_patients = db.execute_query("SELECT patient_id, name FROM patients ORDER BY patient_id ASC", fetch=True) or []
    assert len(db_patients) == 10, f"Expected 10 baseline patients in DB, found {len(db_patients)}"

    print(f"[PASS] Test 8: All {len(routes_to_check)} portal HTML/JS/CSS routes and live API endpoints verified with all 10 baseline patients intact")


if __name__ == "__main__":
    print("=" * 72)
    print("RUNNING JEEVAN SETU MOBILE RESPONSIVENESS & CROSS-PORTAL TEST SUITE")
    print("=" * 72)
    test_1_all_44_html_pages_have_viewport_meta()
    test_2_no_hardcoded_localhost_in_frontend_assets()
    test_3_doctor_portal_mobile_drawer_and_responsive_rules()
    test_4_admin_portal_mobile_drawer_and_responsive_rules()
    test_5_nurse_portal_mobile_drawer_and_responsive_rules()
    test_6_global_alert_manager_mobile_popup_responsiveness()
    test_7_patient_summary_ai_and_simulator_mobile_responsiveness()
    test_8_live_routes_and_api_endpoints_across_all_portals()
    print("=" * 72)
    print("ALL 8 MOBILE RESPONSIVENESS TEST GROUPS PASSED SUCCESSFULLY!")
    print("=" * 72)
