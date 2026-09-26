"""
tests/test_patient_admission_workflow.py — Test comprehensive patient admission workflow.
"""
import pytest
import json
from app import create_app
from database.db import db
from models.user_model import User
from services.auth_service import AuthService

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def admin_token():
    admin_user = User.get_by_username('admin_js')
    if not admin_user:
        admin_user = User.get_by_id(1)
    token = AuthService.generate_access_token(admin_user)['access_token']
    return token

def test_admission_options_endpoint(client, admin_token):
    res = client.get('/api/v1/patients/admission-options', headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'next_uhid' in data['data']
    assert data['data']['next_uhid'].startswith('UHID-')
    assert len(data['data']['wards']) > 0
    assert len(data['data']['available_beds']) > 0
    assert len(data['data']['doctors']) >= 3
    assert len(data['data']['nurses']) >= 3

    # Check workload fields exist
    for doc in data['data']['doctors']:
        assert 'workload' in doc
        assert doc['workload'] >= 0
    for nurse in data['data']['nurses']:
        assert 'workload' in nurse
        assert nurse['workload'] >= 0

def test_patient_admission_success(client, admin_token):
    # 1. Get options to find an available bed
    opt_res = client.get('/api/v1/patients/admission-options', headers={'Authorization': f'Bearer {admin_token}'})
    opt_data = opt_res.get_json()['data']
    avail_bed = opt_data['available_beds'][0]
    doc = opt_data['doctors'][0]
    nurse = opt_data['nurses'][0]
    uhid = opt_data['next_uhid']

    payload = {
        'patient_code': uhid,
        'name': 'Test Admission Patient',
        'age': 52,
        'gender': 'Male',
        'blood_group': 'O+',
        'contact_number': '9876543299',
        'diagnosis': 'Severe Acute Pancreatitis',
        'ward_id': avail_bed['ward_id'],
        'bed_id': avail_bed['bed_id'],
        'assigned_doctor': doc['user_id'],
        'assigned_nurse': nurse['user_id'],
        'attendant_name': 'Test Attendant Relative',
        'attendant_relationship': 'Spouse',
        'attendant_contact': '9876543200'
    }

    res = client.post('/api/v1/patients/admit', json=payload, headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 201
    res_data = res.get_json()
    assert res_data['success'] is True
    assert res_data['data']['patient']['name'] == 'Test Admission Patient'
    assert res_data['data']['patient_code'] == uhid
    assert res_data['data']['attendant']['access_code'].startswith('JSACC')

    # 2. Verify bed is now occupied
    bed_check = db.execute_query('SELECT status FROM beds WHERE bed_id = %s', (avail_bed['bed_id'],), fetch=True)
    assert bed_check[0]['status'] == 'occupied'

    # 3. Attempting to admit another patient to the same bed should fail with 409
    payload['name'] = 'Second Patient Conflict'
    res_conflict = client.post('/api/v1/patients/admit', json=payload, headers={'Authorization': f'Bearer {admin_token}'})
    assert res_conflict.status_code in (409, 400)
