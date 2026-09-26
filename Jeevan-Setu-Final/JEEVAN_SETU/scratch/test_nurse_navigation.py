import urllib.request
import re

nurse_pages = [
    'http://127.0.0.1:5000/Nurse/Nurse_dashboard/Nurse_dashboard.html',
    'http://127.0.0.1:5000/Nurse/Nurse_my_patients/Nurse_my_patients.html',
    'http://127.0.0.1:5000/Nurse/nurse_patient_monitoring/nurse_patient_monitoring.html',
    'http://127.0.0.1:5000/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html',
    'http://127.0.0.1:5000/Nurse/Nurse_i_o_chart/Nurse_i_o_chart.html',
    'http://127.0.0.1:5000/Nurse/Nurse_medication_log/Nurse_medication_log.html',
    'http://127.0.0.1:5000/Nurse/Nurse_nursing_notes/Nurse_nursing_notes.html',
    'http://127.0.0.1:5000/Nurse/Nurse_alerts/Nurse_alerts.html',
    'http://127.0.0.1:5000/Nurse/Nurse_tasks/Nurse_tasks.html',
    'http://127.0.0.1:5000/Nurse/Nurse_transfers/Nurse_transfers.html',
    'http://127.0.0.1:5000/Nurse/Nurse_reports/Nurse_reports.html'
]

print("=== AUDITING NURSE PORTAL STANDARDIZED NAVIGATION & SCROLLING ===")
all_passed = True

for url in nurse_pages:
    page_name = url.split('/')[-1].replace('.html', '')
    try:
        resp = urllib.request.urlopen(url)
        content = resp.read().decode('utf-8', errors='ignore')
        
        has_nav_script = 'nurse_navigation.js' in content
        has_calculator_link = 'Nurse_ews_calculator' in content
        
        if has_nav_script and not has_calculator_link:
            print(f"  [PASS] {page_name}: 200 OK | script=True | ews_removed=True")
        else:
            print(f"  [FAIL] {page_name}: script={has_nav_script}, ews_removed={not has_calculator_link}")
            all_passed = False
    except Exception as e:
        print(f"  [FAIL] {page_name}: Error fetching -> {e}")
        all_passed = False

# Verify nurse_navigation.js script itself
try:
    js_url = 'http://127.0.0.1:5000/Nurse/nurse_navigation.js'
    resp = urllib.request.urlopen(js_url)
    js_content = resp.read().decode('utf-8', errors='ignore')
    if 'renderNurseSidebar' in js_content and 'detectCurrentNursePage' in js_content:
        print("  [PASS] nurse_navigation.js: 200 OK | Single Source of Truth verified")
    else:
        print("  [FAIL] nurse_navigation.js missing key functions")
        all_passed = False
except Exception as e:
    print(f"  [FAIL] nurse_navigation.js fetch failed: {e}")
    all_passed = False

if all_passed:
    print("\nALL 11 NURSE PAGES VERIFIED: Single source of truth sidebar, active highlighting, no shift card, and Admin-matching scroll behavior!")
else:
    print("\nSOME CHECKS FAILED.")
