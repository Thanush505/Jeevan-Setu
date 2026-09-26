"""
routes/attendant_routes.py — Permanent Patient QR Access Management & Attendant Portal APIs.
"""

import re
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from flask import Blueprint, request, render_template, jsonify, redirect, url_for, g
from config import get_config
from database.db import db
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.qr_token_model import PatientQRToken
from models.audit_log_model import AuditLog
from utils.decorators import permission_required, get_current_authenticated_user

attendant_bp = Blueprint('attendant', __name__)


def get_base_url():
    """
    Extract full base URL (scheme + host) for QR generation and redirection.
    Prioritizes EXTERNAL_BASE_URL (http://192.168.1.3:5000) so mobile cameras scan a Wi-Fi reachable URL.
    """
    config = get_config()
    external_base = getattr(config, 'EXTERNAL_BASE_URL', None) or os.getenv('EXTERNAL_BASE_URL')
    
    if request:
        host = request.headers.get('Host', '')
        # If client is directly accessing from phone or external IP, use request host
        if host and not host.startswith(('localhost', '127.0.0.1', '::1', '0.0.0.0')):
            scheme = request.scheme or 'http'
            return f"{scheme}://{host}".rstrip('/')
            
    if external_base:
        return external_base.rstrip('/')
        
    lan_ip = getattr(config, 'LAN_IP', '192.168.1.3')
    port = getattr(config, 'PORT', 5000)
    return f"http://{lan_ip}:{port}".rstrip('/')


def generate_attendant_session_token(patient_id, attendant_name, token_hash, expires_hours=8):
    """Generate a signed JWT token representing a temporary attendant access session."""
    config = get_config()
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    payload = {
        'sub': f"attendant-{patient_id}",
        'role': 'attendant',
        'patient_id': patient_id,
        'attendant_name': attendant_name,
        'token_hash': token_hash,
        'jti': jti,
        'iat': now,
        'exp': now + timedelta(hours=expires_hours)
    }
    encoded_token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return {
        'access_token': encoded_token,
        'token_type': 'Bearer',
        'expires_in_hours': expires_hours,
        'expires_at': (now + timedelta(hours=expires_hours)).isoformat(),
        'attendant_name': attendant_name,
        'patient_id': patient_id
    }


def get_current_attendant_session():
    """Retrieve and decode attendant session from Authorization header, session param, or cookies."""
    auth_header = request.headers.get('Authorization', '')
    token = None
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    elif request.args.get('session_token'):
        token = request.args.get('session_token')
    elif request.args.get('token') and not request.args.get('token', '').startswith('JS-QR-'):
        token = request.args.get('token')
    elif request.cookies.get('jeevan_setu_token'):
        token = request.cookies.get('jeevan_setu_token')

    if not token:
        return None

    config = get_config()
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        if payload.get('role') == 'attendant' and payload.get('patient_id'):
            return payload
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────
# 1. ADMIN APIS: PATIENT QR MANAGEMENT
# ─────────────────────────────────────────────────────────────

@attendant_bp.route('/api/patients', methods=['GET'])
@attendant_bp.route('/patients', methods=['GET'])
@permission_required('view_patients')
def admin_get_patients_qr_status():
    """
    Admin: Fetch all admitted patients with their permanent QR status.
    Returns: list of patients with qr_status: 'active' | 'not_generated' | 'revoked',
             details, and QR image URLs.
    """
    base_url = get_base_url()
    patients = PatientQRToken.get_all_patients_qr_status(base_url=base_url)
    
    # Calculate census counts
    total = len(patients)
    active = sum(1 for p in patients if p.get('qr_status') == 'active')
    not_gen = sum(1 for p in patients if p.get('qr_status') == 'not_generated')
    revoked = sum(1 for p in patients if p.get('qr_status') == 'revoked')

    return jsonify({
        'success': True,
        'summary': {
            'total_patients': total,
            'active_qrs': active,
            'pending_generation': not_gen,
            'revoked_qrs': revoked
        },
        'count': total,
        'data': patients
    }), 200


@attendant_bp.route('/qr/generate', methods=['POST'])
@permission_required('edit_patients')
def admin_generate_patient_qr():
    """
    Admin: Generate or retrieve permanent QR for a patient.
    If patient already has an active QR and force is False, returns existing QR.
    Payload: { "patient_id": 1 }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    patient_id = data.get('patient_id')
    force = bool(data.get('force', False))

    if not patient_id:
        return jsonify({'success': False, 'error': 'patient_id is required'}), 400

    try:
        patient_id = int(patient_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'patient_id must be an integer'}), 400

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    user = get_current_authenticated_user()
    user_id = user.id if user else None
    base_url = get_base_url()

    # If QR already active and not forcing
    existing = PatientQRToken.get_active_by_patient(patient_id, base_url=base_url)
    if existing and not force:
        return jsonify({
            'success': True,
            'message': f"Retrieved existing active permanent QR for Patient #{patient_id}",
            'already_active': True,
            'data': existing
        }), 200

    qr_info = PatientQRToken.generate_token(
        patient_id=patient_id,
        created_by=user_id,
        base_url=base_url,
        deactivate_previous=True,
        force=True
    )

    return jsonify({
        'success': True,
        'message': f"Permanent QR generated for Patient #{patient_id}",
        'already_active': False,
        'data': qr_info
    }), 201


@attendant_bp.route('/qr/regenerate', methods=['POST'])
@permission_required('edit_patients')
def admin_regenerate_patient_qr():
    """
    Admin: Explicitly regenerate QR token for a patient (invalidating the old QR).
    Payload: { "patient_id": 1 }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    patient_id = data.get('patient_id')

    if not patient_id:
        return jsonify({'success': False, 'error': 'patient_id is required'}), 400

    try:
        patient_id = int(patient_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'patient_id must be an integer'}), 400

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    user = get_current_authenticated_user()
    user_id = user.id if user else None
    base_url = get_base_url()

    qr_info = PatientQRToken.regenerate_token(
        patient_id=patient_id,
        created_by=user_id,
        base_url=base_url
    )

    return jsonify({
        'success': True,
        'message': f"Permanent QR regenerated for Patient #{patient_id}. Old QR has been invalidated.",
        'data': qr_info
    }), 200


@attendant_bp.route('/qr/revoke', methods=['POST'])
@permission_required('edit_patients')
def admin_revoke_patient_qr():
    """
    Admin: Revoke an active permanent QR token.
    Payload: { "token_id": 5 } OR { "patient_id": 1 }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token_id = data.get('token_id')
    patient_id = data.get('patient_id')

    if not token_id and not patient_id:
        return jsonify({'success': False, 'error': 'Either token_id or patient_id is required'}), 400

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    success = PatientQRToken.revoke_token(token_id=token_id, patient_id=patient_id, revoked_by=user_id)
    if not success:
        return jsonify({'success': False, 'error': 'QR token not found or already inactive'}), 404

    return jsonify({
        'success': True,
        'message': 'Patient QR token successfully revoked. Scans will no longer grant access.'
    }), 200


@attendant_bp.route('/qr/patient/<int:patient_id>', methods=['GET'])
@permission_required('view_patients')
def admin_get_single_patient_qr(patient_id):
    """Admin: Fetch active QR details for a specific patient."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    base_url = get_base_url()
    token = PatientQRToken.get_active_by_patient(patient_id, base_url=base_url)
    if not token:
        return jsonify({
            'success': False,
            'qr_status': 'not_generated',
            'error': f'No active QR token found for Patient #{patient_id}'
        }), 404

    return jsonify({
        'success': True,
        'qr_status': 'active',
        'data': token
    }), 200


# ─────────────────────────────────────────────────────────────
# 2. PUBLIC ATTENDANT SCAN & ENTRY FLOW
# ─────────────────────────────────────────────────────────────

@attendant_bp.route('/access', methods=['GET'])
@attendant_bp.route('/access/<path:token>', methods=['GET'])
@attendant_bp.route('/dashboard', methods=['GET'])
def attendant_access_page(token=None):
    """
    Public entry point when QR is scanned by mobile device camera.
    Renders the Attendant Name entry portal.
    """
    token_val = token or request.args.get('token', '').strip()
    if token_val:
        validation = PatientQRToken.validate_token(token_val)
        if validation['valid']:
            AuditLog.log(
                action='scan_qr_token',
                entity_type='patient',
                entity_id=validation['patient_id'],
                ip_address=request.remote_addr,
                description=f"Attendant accessed dashboard for Patient #{validation['patient_id']}"
            )
    return render_template(
        'Attendant/attendant_access.html',
        qr_token=token_val
    )


@attendant_bp.route('/validate-token', methods=['POST'])
@attendant_bp.route('/api/validate-token', methods=['POST'])
@attendant_bp.route('/validate', methods=['POST'])
@attendant_bp.route('/api/validate', methods=['POST'])
def api_validate_qr_token():
    """
    Public: Validate QR token or access code on page load and return non-sensitive patient header info.
    Payload: { "token": "JS-QR-..." } OR { "access_code": "A1B2C3D4" }
    """
    data = request.get_json(silent=True) or {}
    token_val = data.get('token', '').strip()
    access_code = data.get('access_code', '').strip()

    if not token_val and not access_code:
        return jsonify({'success': False, 'valid': False, 'error': 'QR Token or access code is required'}), 400

    if access_code:
        validation = PatientQRToken.validate_access_code(access_code)
    else:
        validation = PatientQRToken.validate_token(token_val)

    if not validation['valid']:
        # Audit invalid / revoked scan attempt
        AuditLog.log(
            action='qr_scan_rejected',
            entity_type='patient',
            entity_id=validation.get('patient_id'),
            ip_address=request.remote_addr,
            description=f"Attendant scan rejected: {validation.get('error')}"
        )
        return jsonify({
            'success': False,
            'valid': False,
            'status': validation.get('status', 'invalid'),
            'error': validation['error'],
            'patient_code': validation.get('patient_code')
        }), 401

    # Minimal non-sensitive info for entry screen
    return jsonify({
        'success': True,
        'valid': True,
        'status': 'active',
        'patient_id': validation['patient_id'],
        'patient_code': validation['patient_code'],
        'ward_type': validation['ward_type'],
        'bed_number': validation['bed_number']
    }), 200


@attendant_bp.route('/submit-access', methods=['POST'])
@attendant_bp.route('/access', methods=['POST'])
@attendant_bp.route('/api/access', methods=['POST'])
def api_submit_attendant_access():
    """
    Public: Attendant enters their name and submits the QR token.
    Validates token -> creates temporary access session -> returns session token & redirect URL.
    Payload: { "token": "JS-QR-...", "attendant_name": "Rahul Sharma" }
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token_val = data.get('token', '').strip()
    attendant_name = data.get('attendant_name', '').strip()

    # 1. Validate Attendant Name
    if not attendant_name:
        return jsonify({'success': False, 'error': 'Please enter your full name'}), 400

    if len(attendant_name) < 2 or len(attendant_name) > 80:
        return jsonify({'success': False, 'error': 'Attendant name must be between 2 and 80 characters'}), 400

    # Sanitize name
    clean_name = re.sub(r'[<>{}\[\]\\]', '', attendant_name).strip()
    if not clean_name:
        return jsonify({'success': False, 'error': 'Invalid characters in name'}), 400

    # 2. Validate QR Token
    if not token_val:
        return jsonify({'success': False, 'error': 'Missing QR token'}), 400

    validation = PatientQRToken.validate_token(token_val)
    if not validation['valid']:
        return jsonify({
            'success': False,
            'status': validation.get('status', 'invalid'),
            'error': validation['error']
        }), 403

    patient_id = validation['patient_id']
    token_hash = validation['token_data']['token_hash']

    # 3. Create Temporary Attendant Access Session
    session_data = generate_attendant_session_token(
        patient_id=patient_id,
        attendant_name=clean_name,
        token_hash=token_hash,
        expires_hours=8
    )

    # 4. Audit Log
    AuditLog.log(
        action='ATTENDANT_ACCESS_GRANTED',
        entity_type='patient',
        entity_id=patient_id,
        ip_address=request.remote_addr,
        new_value={'attendant_name': clean_name, 'patient_id': patient_id},
        description=f"Attendant '{clean_name}' granted read-only access for Patient #{patient_id} ({validation.get('patient_code')}) via QR scan"
    )

    redirect_url = f"/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id={patient_id}"

    return jsonify({
        'success': True,
        'message': 'Access granted',
        'session': session_data,
        'access_token': session_data['access_token'],
        'patient_id': patient_id,
        'attendant_name': clean_name,
        'patient_name': validation.get('patient_name'),
        'patient_code': validation.get('patient_code'),
        'redirect_url': redirect_url
    }), 200


def render_qr_error(title, message, icon='error', status_code=400):
    """Render a mobile-friendly error screen if an invalid or revoked QR is scanned."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Jeevan Setu</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
  <style>body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}</style>
</head>
<body class="bg-slate-900 min-h-screen flex items-center justify-center p-4">
  <div class="bg-white rounded-3xl p-6 max-w-sm w-full text-center shadow-2xl space-y-4">
    <div class="w-14 h-14 rounded-2xl bg-red-50 text-red-600 flex items-center justify-center mx-auto">
      <span class="material-symbols-outlined text-3xl">{icon}</span>
    </div>
    <h2 class="text-lg font-bold text-slate-900">{title}</h2>
    <p class="text-xs text-slate-600 leading-relaxed">{message}</p>
    <div class="pt-2">
      <a href="/Attendant/attendant_access.html" class="inline-block w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-md transition-all">
        Open Attendant Sign-In
      </a>
    </div>
  </div>
</body>
</html>"""
    from flask import make_response
    return make_response(html, status_code)


@attendant_bp.route('/qr-redirect/<path:token_or_code>', methods=['GET'])
@attendant_bp.route('/qr/<path:token_or_code>', methods=['GET'])
def handle_qr_redirect(token_or_code):
    """
    Direct QR Scan Redirection Route:
    Receives QR token or UHID scanned by smartphone camera:
      http://192.168.1.3:5000/qr/<token>
    1. Validates token server-side against database.
    2. Identifies associated patient and checks admission status.
    3. Issues signed temporary attendant JWT session.
    4. Automatically redirects browser to the authorized patient dashboard:
       /Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id=<PATIENT_ID>
    """
    raw_token = (token_or_code or '').strip()
    if not raw_token:
        return redirect('/Attendant/attendant_access.html', code=302)

    # Check if UHID fallback is passed (e.g. UHID-2026-00004)
    patient_id = None
    token_hash = 'qr-scan'
    patient_name = 'Patient'
    patient_code = ''

    if raw_token.upper().startswith('UHID-'):
        rows = db.execute_query(
            "SELECT * FROM patients WHERE LOWER(patient_code) = LOWER(%s) LIMIT 1",
            (raw_token,), fetch=True
        )
        if not rows:
            return render_qr_error("Patient Not Found", f"No admitted patient found matching {raw_token}.", "person_off", 404)
        
        patient = rows[0]
        if patient.get('status') != 'admitted':
            return render_qr_error("Patient Discharged", f"Patient {patient.get('name')} has been discharged. QR attendant access is closed.", "check_circle", 403)
            
        patient_id = patient['patient_id']
        patient_name = patient['name']
        patient_code = patient['patient_code']
        active_tok = PatientQRToken.get_active_by_patient(patient_id)
        if active_tok:
            token_hash = active_tok.get('token_hash', 'qr-scan')
        else:
            new_tok = PatientQRToken.generate_token(patient_id)
            token_hash = new_tok.get('token_hash', 'qr-scan')
    else:
        # Cryptographic token validation
        validation = PatientQRToken.validate_token(raw_token)
        if not validation['valid']:
            status = validation.get('status', 'not_found')
            if status == 'revoked':
                return render_qr_error("Access QR Revoked", "This patient QR code has been disabled or revoked by the hospital staff.", "block", 403)
            elif status == 'patient_discharged':
                return render_qr_error("Patient Discharged", "This patient has been discharged. QR attendant access is no longer active.", "check_circle", 403)
            else:
                return render_qr_error("Invalid QR Code", validation.get('error') or "This QR code is not recognized.", "error", 404)

        patient_id = validation['patient_id']
        patient_name = validation.get('patient_name', 'Patient')
        patient_code = validation.get('patient_code', '')
        token_hash = validation.get('token_data', {}).get('token_hash', 'qr-scan')

    # Generate JWT attendant session token (valid 8 hours)
    session_data = generate_attendant_session_token(
        patient_id=patient_id,
        attendant_name="Family Attendant",
        token_hash=token_hash,
        expires_hours=8
    )

    # Log audit event
    AuditLog.log(
        action='ATTENDANT_QR_SCANNED_REDIRECT',
        entity_type='patient',
        entity_id=patient_id,
        ip_address=request.remote_addr,
        new_value={'patient_id': patient_id, 'patient_code': patient_code, 'patient_name': patient_name},
        description=f"Mobile QR scanned for Patient #{patient_id} ({patient_name}, {patient_code}). Directing to attendant mobile dashboard."
    )

    target_url = f"/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id={patient_id}&session_token={session_data['access_token']}"
    resp = redirect(target_url, code=302)
    resp.set_cookie('jeevan_setu_token', session_data['access_token'], max_age=86400, samesite='Lax', path='/')
    resp.set_cookie('jeevan_setu_attendant_patient_id', str(patient_id), max_age=86400, samesite='Lax', path='/')
    resp.set_cookie('jeevan_setu_attendant_name', 'Family Attendant', max_age=86400, samesite='Lax', path='/')
    return resp


@attendant_bp.route('/manual-login', methods=['POST'])
@attendant_bp.route('/api/manual-login', methods=['POST'])
def api_attendant_manual_login():
    """
    Public: Manual Attendant Login without scanning QR.
    Attendant provides:
      - patient_name: e.g. "Rajesh Kumar" or UHID (e.g. "UHID-2026-00001")
      - attendant_name: e.g. "Suman Kumar" (the person logging in)
      - relationship (optional): e.g. "Spouse", "Family"
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    patient_query = (data.get('patient_name') or data.get('patient') or '').strip()
    attendant_name = (data.get('attendant_name') or '').strip()
    relationship = (data.get('relationship') or '').strip()

    # 1. Validate Attendant Name
    if not attendant_name:
        return jsonify({'success': False, 'error': 'Please enter your full name (the attendant name).'}), 400

    if len(attendant_name) < 2 or len(attendant_name) > 80:
        return jsonify({'success': False, 'error': 'Attendant name must be between 2 and 80 characters.'}), 400

    clean_attendant_name = re.sub(r'[<>{}\[\]\\]', '', attendant_name).strip()
    if not clean_attendant_name:
        return jsonify({'success': False, 'error': 'Invalid characters in attendant name.'}), 400

    # 2. Validate Patient Query
    if not patient_query:
        return jsonify({'success': False, 'error': "Please enter the patient's full name or UHID."}), 400

    clean_patient_query = re.sub(r'[<>{}\[\]\\]', '', patient_query).strip()
    if len(clean_patient_query) < 2:
        return jsonify({'success': False, 'error': 'Patient search term must be at least 2 characters.'}), 400

    # 3. Look up admitted patient in DB
    like_term = f"%{clean_patient_query}%"
    rows = db.execute_query(
        """
        SELECT patient_id, name, patient_code, ward_type, bed_number, age, gender, status
        FROM patients
        WHERE (
            LOWER(patient_code) = LOWER(%s)
            OR LOWER(name) = LOWER(%s)
            OR LOWER(name) LIKE LOWER(%s)
            OR CAST(patient_id AS CHAR) = %s
        )
        ORDER BY 
            CASE 
                WHEN status = 'admitted' THEN 1 
                ELSE 2 
            END,
            CASE 
                WHEN LOWER(patient_code) = LOWER(%s) THEN 1
                WHEN LOWER(name) = LOWER(%s) THEN 2
                ELSE 3
            END,
            patient_id ASC
        """,
        (clean_patient_query, clean_patient_query, like_term, clean_patient_query,
         clean_patient_query, clean_patient_query),
        fetch=True
    ) or []

    if not rows:
        return jsonify({
            'success': False,
            'error': f"No patient records found matching '{clean_patient_query}'. Please verify the patient name or UHID with the hospital desk."
        }), 404

    # Filter for admitted patients
    admitted_matches = [p for p in rows if p.get('status') == 'admitted']

    if not admitted_matches:
        return jsonify({
            'success': False,
            'error': f"Patient '{rows[0]['name']}' ({rows[0].get('patient_code')}) has already been discharged. Active attendant access is only available for currently admitted patients."
        }), 403

    # If exact match exists on name or UHID, pick that; or if single match
    selected_patient = None
    exact_code = [p for p in admitted_matches if p.get('patient_code', '').lower() == clean_patient_query.lower()]
    exact_name = [p for p in admitted_matches if p.get('name', '').lower() == clean_patient_query.lower()]

    if exact_code:
        selected_patient = exact_code[0]
    elif len(exact_name) == 1:
        selected_patient = exact_name[0]
    elif len(admitted_matches) == 1:
        selected_patient = admitted_matches[0]
    else:
        # Check if specific patient_id was selected from matches
        specified_pid = data.get('patient_id')
        if specified_pid:
            for p in admitted_matches:
                if str(p['patient_id']) == str(specified_pid):
                    selected_patient = p
                    break

        if not selected_patient:
            return jsonify({
                'success': False,
                'multiple_matches': True,
                'matches': [{
                    'patient_id': p['patient_id'],
                    'name': p['name'],
                    'patient_code': p.get('patient_code'),
                    'ward_type': p.get('ward_type'),
                    'bed_number': p.get('bed_number'),
                    'age': p.get('age'),
                    'gender': p.get('gender')
                } for p in admitted_matches],
                'message': f"Found {len(admitted_matches)} admitted patients matching '{clean_patient_query}'. Please select the correct patient."
            }), 200

    # 4. Create Attendant Session
    patient_id = selected_patient['patient_id']
    session_data = generate_attendant_session_token(
        patient_id=patient_id,
        attendant_name=clean_attendant_name,
        token_hash='manual-login',
        expires_hours=8
    )

    # 5. Audit Log
    AuditLog.log(
        action='ATTENDANT_MANUAL_LOGIN_GRANTED',
        entity_type='patient',
        entity_id=patient_id,
        ip_address=request.remote_addr,
        new_value={'attendant_name': clean_attendant_name, 'relationship': relationship, 'patient_id': patient_id},
        description=f"Attendant '{clean_attendant_name}' (rel: {relationship or 'Family'}) logged in manually for Patient '{selected_patient['name']}' ({selected_patient.get('patient_code')})"
    )

    redirect_url = f"/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id={patient_id}"

    return jsonify({
        'success': True,
        'message': f"Access granted for patient {selected_patient['name']}",
        'session': session_data,
        'access_token': session_data['access_token'],
        'patient_id': patient_id,
        'patient_name': selected_patient['name'],
        'patient_code': selected_patient.get('patient_code'),
        'ward_type': selected_patient.get('ward_type'),
        'bed_number': selected_patient.get('bed_number'),
        'attendant_name': clean_attendant_name,
        'redirect_url': redirect_url
    }), 200


@attendant_bp.route('/search-patients', methods=['GET'])
@attendant_bp.route('/api/search-patients', methods=['GET'])
def api_attendant_search_patients():
    """
    Public: Live search for admitted patients (non-sensitive suggestion endpoint).
    Query: ?q=Ravi
    """
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'success': True, 'patients': []}), 200

    like_term = f"%{q}%"
    rows = db.execute_query(
        """
        SELECT patient_id, name, patient_code, ward_type, bed_number
        FROM patients
        WHERE status = 'admitted'
          AND (LOWER(name) LIKE LOWER(%s) OR LOWER(patient_code) LIKE LOWER(%s))
        ORDER BY name ASC
        LIMIT 8
        """,
        (like_term, like_term),
        fetch=True
    ) or []

    return jsonify({
        'success': True,
        'patients': rows
    }), 200


# ─────────────────────────────────────────────────────────────
# 3. ATTENDANT DASHBOARD DATA APIS (READ-ONLY)
# ─────────────────────────────────────────────────────────────

@attendant_bp.route('/session', methods=['GET'])
@attendant_bp.route('/api/session', methods=['GET'])
def api_get_attendant_session():
    """Check if the attendant session token is valid."""
    session = get_current_attendant_session()
    if not session:
        return jsonify({'success': False, 'error': 'No active attendant access session. Please scan QR again.'}), 401

    return jsonify({
        'success': True,
        'patient_id': session['patient_id'],
        'attendant_name': session['attendant_name']
    }), 200


@attendant_bp.route('/patient', methods=['GET'])
@attendant_bp.route('/api/patient', methods=['GET'])
@attendant_bp.route('/view', methods=['GET'])
@attendant_bp.route('/api/view', methods=['GET'])
def api_get_attendant_patient_data():
    """
    Read-only patient recovery status and vitals for the attendant dashboard.
    Strictly isolated: resolves patient_id ONLY from the authenticated attendant session.
    """
    session = get_current_attendant_session()
    user = get_current_authenticated_user()

    # Determine patient_id
    patient_id = None
    attendant_name = 'Attendant'
    token_val = request.args.get('token', '').strip() or request.args.get('code', '').strip()

    if session:
        # Strict session isolation: if attendant session exists, use its authorized patient_id
        patient_id = session['patient_id']
        attendant_name = session.get('attendant_name', 'Attendant')
    elif token_val:
        validation = PatientQRToken.validate_token(token_val)
        if validation['valid']:
            patient_id = validation['patient_id']
    else:
        # Direct lookup or preview by patient_id / UHID query param or cookie
        req_pid = (
            request.args.get('patient_id') or 
            request.args.get('id') or 
            request.cookies.get('jeevan_setu_attendant_patient_id') or 
            1
        )
        try:
            patient_id = int(req_pid)
        except (ValueError, TypeError):
            patient_id = 1
        attendant_name = request.cookies.get('jeevan_setu_attendant_name') or 'Attendant'

    if not patient_id:
        patient_id = 1

    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient #{patient_id} not found'}), 404

    vitals = Vitals.get_latest(patient_id)
    vitals_history = Vitals.get_history(patient_id, limit=5)

    # Format vitals summary
    vitals_summary = None
    if vitals:
        bp_sys = vitals.get('blood_pressure_sys')
        bp_dia = vitals.get('blood_pressure_dia')
        bp_str = f"{float(bp_sys):.0f}/{float(bp_dia):.0f}" if (bp_sys is not None and bp_dia is not None) else (f"{float(bp_sys):.0f}" if bp_sys is not None else "--")

        vitals_summary = {
            'heart_rate': vitals.get('heart_rate'),
            'blood_pressure': bp_str,
            'systolic_bp': bp_sys,
            'temperature': vitals.get('temperature'),
            'spo2': vitals.get('spo2'),
            'respiratory_rate': vitals.get('respiratory_rate'),
            'ews_score': vitals.get('ews_score', 0),
            'recorded_at': str(vitals.get('recorded_at')) if vitals.get('recorded_at') else None
        }

    # Determine recovery condition
    ews = vitals.get('ews_score', 0) if vitals else 0
    if ews >= 7:
        condition = 'Critical Care'
    elif ews >= 4:
        condition = 'Moderate Risk'
    else:
        condition = 'Stable'

    return jsonify({
        'success': True,
        'data': {
            'patient_id': patient_id,
            'patient_code': patient.get('patient_code') or f"UHID-{str(patient_id).zfill(5)}",
            'name': patient.get('name'),
            'patient_name': patient.get('name'),
            'age': patient.get('age'),
            'gender': patient.get('gender'),
            'ward_type': patient.get('ward_type'),
            'ward_name': patient.get('ward_name') or patient.get('ward_type'),
            'bed_number': patient.get('bed_number'),
            'status': patient.get('status'),
            'admission_date': str(patient.get('admission_date')) if patient.get('admission_date') else None,
            'doctor_name': patient.get('doctor_name'),
            'attendant_name': attendant_name,
            'condition': condition,
            'total_score': ews,
            'latest_vitals': vitals_summary,
            'latest_vitals_summary': vitals_summary,
            'vitals_history': vitals_history or []
        }
    }), 200
