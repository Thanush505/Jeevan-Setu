import requests

BASE = 'http://127.0.0.1:5000'

# 1. Test Admin HTML page
r_html = requests.get(f'{BASE}/Admin/Admin_attendant_access/Admin_attendant_access.html')
assert r_html.status_code == 200, f'HTML Page error: {r_html.status_code}'
print('[PASS] 1. Admin Attendant Access HTML page loads (200 OK)')

# 2. Test Admin Patients QR list
r_list = requests.get(f'{BASE}/api/v1/attendant/patients')
assert r_list.status_code == 200, f'List error: {r_list.status_code}'
data_list = r_list.json()
print(f'[PASS] 2. Admin Patients list returned {len(data_list["data"])} patients, summary: {data_list["summary"]}')

# 3. Generate QR for Patient 1
r_gen1 = requests.post(f'{BASE}/api/v1/attendant/qr/generate', json={'patient_id': 1})
assert r_gen1.status_code in (200, 201), f'Gen error: {r_gen1.status_code}'
token_data1 = r_gen1.json()['data']
raw_token1 = token_data1.get('raw_token') or token_data1.get('token_hash')
print(f'[PASS] 3. Generated QR for Patient 1. Token ID: {token_data1.get("token_id")}')

# 4. Test Static QR (Calling generate again returns same QR)
r_gen2 = requests.post(f'{BASE}/api/v1/attendant/qr/generate', json={'patient_id': 1})
assert r_gen2.status_code == 200, f'Static QR check failed: {r_gen2.status_code}'
token_data2 = r_gen2.json()['data']
assert token_data1.get('token_id') == token_data2.get('token_id'), 'Token ID changed unexpectedly!'
print('[PASS] 4. Static QR confirmed: Re-requesting returns existing active QR without recreating')

# 5. Test Attendant entry page & validate token
r_val = requests.post(f'{BASE}/api/v1/attendant/validate-token', json={'token': raw_token1})
assert r_val.status_code == 200 and r_val.json()['valid'] == True, f'Validation failed: {r_val.text}'
print(f'[PASS] 5. Token validation succeeded on scan for {r_val.json()["patient_code"]}')

# 6. Test Attendant Name submission & session creation
r_acc = requests.post(f'{BASE}/api/v1/attendant/access', json={'token': raw_token1, 'attendant_name': 'Ramesh Kumar'})
assert r_acc.status_code == 200, f'Access submission failed: {r_acc.text}'
acc_data = r_acc.json()
attendant_token = acc_data['access_token']
print(f'[PASS] 6. Access session created for attendant "{acc_data["attendant_name"]}", redirect: {acc_data["redirect_url"]}')

# 7. Test Attendant Patient data retrieval with session
att_headers = {'Authorization': f'Bearer {attendant_token}'}
r_pat = requests.get(f'{BASE}/api/v1/attendant/patient', headers=att_headers)
assert r_pat.status_code == 200, f'Patient data fetch failed: {r_pat.text}'
pat_data = r_pat.json()['data']
assert pat_data['patient_id'] == 1, 'Patient ID mismatch!'
print(f'[PASS] 7. Attendant dashboard fetched read-only data for: {pat_data["name"]} ({pat_data["patient_code"]}) - Condition: {pat_data["condition"]}')

# 8. Test Revocation
r_rev = requests.post(f'{BASE}/api/v1/attendant/qr/revoke', json={'patient_id': 1})
assert r_rev.status_code == 200, f'Revocation failed: {r_rev.text}'
r_val_rev = requests.post(f'{BASE}/api/v1/attendant/validate-token', json={'token': raw_token1})
assert r_val_rev.json()['valid'] == False and r_val_rev.json()['status'] == 'revoked', 'Revoked token still accepted!'
print('[PASS] 8. Revocation verified: Scan on revoked QR properly returns revoked error')

# 9. Test Regeneration
r_regen = requests.post(f'{BASE}/api/v1/attendant/qr/regenerate', json={'patient_id': 1})
assert r_regen.status_code == 200, f'Regeneration failed: {r_regen.text}'
new_token_data = r_regen.json()['data']
new_raw_token = new_token_data['raw_token']
assert new_token_data['token_id'] != token_data1['token_id'], 'Token ID was not updated on regeneration!'

r_val_new = requests.post(f'{BASE}/api/v1/attendant/validate-token', json={'token': new_raw_token})
assert r_val_new.json()['valid'] == True, 'New regenerated token not valid!'
print(f'[PASS] 9. Regeneration verified: Old QR invalid, new QR active (#{new_token_data["token_id"]})')

# 10. Test Attendant Access HTML entry page
r_entry_html = requests.get(f'{BASE}/Attendant/attendant_access.html?token={new_raw_token}')
assert r_entry_html.status_code == 200, f'Entry HTML failed: {r_entry_html.status_code}'
print('[PASS] 10. Attendant Access Entry HTML page loads (200 OK)')

print('\n======================================================')
print('  SUCCESS: ALL 10 ATTENDANT QR ACCESS TESTS PASSED PERFECTLY!')
print('======================================================')
