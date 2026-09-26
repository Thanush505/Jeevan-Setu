import requests

BASE = 'http://127.0.0.1:5000'
admin_pages = [
    '/Admin/Administrator_dashboard_/Administrator_dashboard_.html',
    '/Admin/Admin_patient_management/Admin_patient_management.html',
    '/Admin/Admin_beds_wards/Admin_beds_wards.html',
    '/Admin/Admin_users_roles/Admin_users_roles.html',
    '/Admin/Admin_attendant_access/Admin_attendant_access.html',
    '/Admin/Admin_ews_analytics/Admin_ews_analytics.html',
    '/Admin/Admin_clinical_reports/Admin_clinical_reports.html',
    '/Admin/Admin_audit_logs/Admin_audit_logs.html',
    '/Admin/Admin_system_settings/Admin_system_settings.html',
    '/Admin/Admin_notification_settings/Admin_notification_settings.html',
    '/Admin/Admin_backup_restore/Admin_backup_restore.html'
]

print('AUDITING ACTIVE ADMIN PAGES...')
for p in admin_pages:
    r = requests.get(BASE + p)
    assert r.status_code == 200, f'Page {p} returned {r.status_code}'
    content = r.text
    has_script = 'admin_navigation.js' in content
    has_attendant = ('Attendants (QR Access)' in content) or ('Admin_attendant_access' in content)
    name = p.split('/')[2]
    print(f'  [PASS] {name}: 200 OK | script={has_script} | attendant_link={has_attendant}')
    assert has_script, f'Missing admin_navigation.js in {p}'
    assert has_attendant, f'Missing attendant nav in {p}'

# Test merged features on Beds & Wards page
r_bw = requests.get(BASE + '/Admin/Admin_beds_wards/Admin_beds_wards.html')
assert 'Overall Bed Occupancy' in r_bw.text, 'Missing merged Overall Bed Occupancy metric'
assert 'Ward-by-Ward Capacity' in r_bw.text, 'Missing merged Ward-by-Ward Directory'
assert 'Live Bed Matrix' in r_bw.text, 'Missing Live Bed Matrix'
print('  [PASS] Admin_beds_wards merged features verified: Bed Matrix, Resource Telemetry & Ward Directory')

# Test redirect from legacy resource utilization page
r_ru = requests.get(BASE + '/Admin/Admin_resource_utilization/Admin_resource_utilization.html')
assert r_ru.status_code == 200 and 'Admin_beds_wards.html' in r_ru.text
print('  [PASS] Legacy Admin_resource_utilization redirects to Admin_beds_wards.html')

# Test that admin_navigation.js itself loads with 200 OK
r_js = requests.get(BASE + '/Admin/admin_navigation.js')
assert r_js.status_code == 200, f'admin_navigation.js returned {r_js.status_code}'
print('  [PASS] admin_navigation.js: 200 OK')

print('\nALL ADMIN PAGES VERIFIED WITH MERGED BEDS, WARDS & RESOURCE UTILIZATION ARCHITECTURE!')
