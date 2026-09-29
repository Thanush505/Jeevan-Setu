"""
routes/attendant_routes.py - Permanent Patient QR Access Management & Attendant Portal APIs.
"""

import os
import re
import uuid
import secrets
from datetime import datetime, timezone, timedelta
import jwt
from flask import Blueprint, request, render_template, jsonify, redirect, url_for, g, make_response
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
    Dynamically resolves active LAN IP (e.g. 172.20.10.2) or client request host.
    """
    if request:
        host = request.headers.get('Host', '')
        if host and not host.startswith(('localhost', '127.0.0.1', '::1', '0.0.0.0')):
            scheme = request.scheme or 'http'
            return f"{scheme}://{host}".rstrip('/')
            
    from config import get_config, get_lan_ip
    config = get_config()
    external_base = getattr(config, 'EXTERNAL_BASE_URL', None) or os.getenv('EXTERNAL_BASE_URL')
    if external_base and not '192.168.1.3' in external_base and not '127.0.0.1' in external_base:
        return external_base.rstrip('/')
        
    lan_ip = getattr(config, 'LAN_IP', None) or get_lan_ip()
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


# =============================================================
# 1. ADMIN APIS: PATIENT QR MANAGEMENT
# =============================================================

@attendant_bp.route('/patients', methods=['GET'])
@permission_required('view_patients')
def admin_get_patients_qr_status():
    """
    Admin: Fetch all admitted patients with their permanent QR status.
    """
    base_url = get_base_url()
    patients = PatientQRToken.get_all_patients_qr_status(base_url=base_url)
    
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
    """Admin: Generate permanent QR for a patient."""
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
    """Admin: Explicitly regenerate QR token for a patient."""
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
    """Admin: Revoke an active permanent QR token."""
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


# =============================================================
# 2. PUBLIC ATTENDANT ACCESS & QR GATE FLOW
# =============================================================

def render_qr_error(title, message, icon='error', status_code=400):
    """Render a clean, mobile-friendly error screen when an invalid, expired, or revoked QR is scanned."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Jeevan Setu</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>body {{ font-family: 'Inter', sans-serif; }}</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 antialiased">
  <div class="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-sm w-full text-center shadow-2xl space-y-4">
    <div class="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center mx-auto text-3xl">
      ⚠️
    </div>
    <div>
      <h2 class="text-lg font-bold text-white font-headline tracking-tight">{title}</h2>
      <p class="text-xs text-slate-400 leading-relaxed mt-1.5">{message}</p>
    </div>
    <div class="pt-3">
      <a href="/Attendant/attendant_access.html" class="inline-flex items-center justify-center w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold text-xs rounded-xl shadow-lg transition-all">
        Open Attendant Sign-In
      </a>
    </div>
    <p class="text-[11px] text-slate-500 font-medium">Jeevan Setu Attendant Safety Portal</p>
  </div>
</body>
</html>"""
    return make_response(html, status_code)


def render_name_entry_screen(qr_token_val):
    """
    Renders the Attendant Name Entry Screen after QR scanning.
    Strict Security: DOES NOT EXPOSE any patient name, vitals, diagnosis, EWS, bed, or medical data.
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Attendant Access — Jeevan Setu</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', sans-serif; }}
    .font-headline {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 sm:p-6 antialiased">
  
  <div class="w-full max-w-sm mx-auto">
    <!-- Brand Card Container -->
    <div class="bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
      
      <!-- Hospital Logo & Heading -->
      <div class="text-center space-y-2">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600/10 border border-blue-500/20 mb-1">
          <img src="/assets/jeevan_setu_logo.png" onerror="this.onerror=null; this.src='/Attendant/jeevan_setu_logo.png';" alt="Jeevan Setu Logo" class="w-9 h-9 object-contain">
        </div>
        <h1 class="text-xl font-extrabold text-white font-headline tracking-tight uppercase">
          JEEVAN SETU
        </h1>
        <h2 class="text-base font-bold text-blue-400">
          Attendant Access
        </h2>
        <p class="text-xs text-slate-400 font-medium">
          Please enter your name to continue.
        </p>
      </div>

      <!-- Error Alert Box -->
      <div id="validation-error-box" class="hidden p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-semibold flex items-center gap-2">
        <span class="text-sm">⚠️</span>
        <span id="validation-error-text">Please enter your name to continue.</span>
      </div>

      <!-- Name Entry Form -->
      <form id="attendant-name-form" onsubmit="handleNameSubmission(event)" class="space-y-4">
        <input type="hidden" id="qr-token-hidden" value="{qr_token_val}">

        <div class="space-y-1.5">
          <label for="attendant-name-input" class="block text-xs font-bold text-slate-300 uppercase tracking-wider">
            Name <span class="text-red-400">*</span>
          </label>
          <div class="relative">
            <input 
              type="text" 
              id="attendant-name-input" 
              name="attendant_name"
              required 
              placeholder="e.g. Rahul Kumar" 
              autocomplete="name"
              autofocus
              class="w-full px-4 py-3 bg-slate-950/80 text-white placeholder-slate-500 text-sm font-medium rounded-xl border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
            >
          </div>
        </div>

        <!-- Submit Button -->
        <button 
          type="submit" 
          id="submit-btn" 
          class="w-full py-3.5 px-4 bg-blue-600 hover:bg-blue-500 active:scale-[0.98] text-white font-bold text-sm rounded-xl shadow-lg shadow-blue-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer"
        >
          <span id="submit-btn-text">SUBMIT</span>
        </button>
      </form>

      <!-- Security / Trust Footer -->
      <div class="pt-2 border-t border-slate-800/80 text-center">
        <div class="inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
          <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
          <span>Hospital QR Access Verified</span>
        </div>
      </div>

    </div>
  </div>

  <script>
    async function handleNameSubmission(e) {{
      e.preventDefault();
      
      const nameInput = document.getElementById('attendant-name-input');
      const errBox = document.getElementById('validation-error-box');
      const errText = document.getElementById('validation-error-text');
      const submitBtn = document.getElementById('submit-btn');
      const submitBtnText = document.getElementById('submit-btn-text');
      const token = document.getElementById('qr-token-hidden').value;

      errBox.classList.add('hidden');

      const nameVal = (nameInput.value || '').trim();

      // Frontend validation: reject empty or whitespace-only
      if (!nameVal) {{
        errText.textContent = 'Please enter your name to continue.';
        errBox.classList.remove('hidden');
        nameInput.focus();
        return;
      }}

      if (nameVal.length < 2) {{
        errText.textContent = 'Name must be at least 2 characters.';
        errBox.classList.remove('hidden');
        nameInput.focus();
        return;
      }}

      if (nameVal.length > 80) {{
        errText.textContent = 'Name must be under 80 characters.';
        errBox.classList.remove('hidden');
        nameInput.focus();
        return;
      }}

      // Show Loading state
      submitBtn.disabled = true;
      submitBtnText.innerHTML = `
        <svg class="animate-spin h-4 w-4 text-white inline-block mr-1.5" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg> Verifying access...
      `;

      try {{
        const res = await fetch('/api/v1/attendant/qr-access/verify', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            token: token,
            attendant_name: nameVal
          }})
        }});

        const data = await res.json();

        if (res.ok && data.success && data.access_granted) {{
          if (data.access_token) {{
            sessionStorage.setItem('jeevan_setu_token', data.access_token);
            sessionStorage.setItem('jeevan_setu_attendant_session', JSON.stringify(data.session || {{}}));
            sessionStorage.setItem('jeevan_setu_attendant_name', data.attendant_name);
            sessionStorage.setItem('jeevan_setu_attendant_patient_id', data.patient_id);
            localStorage.setItem('jeevan_setu_token', data.access_token);
          }}

          submitBtnText.textContent = 'Access Granted! Opening...';
          const redirectUrl = data.redirect_url || `/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id=${{data.patient_id}}`;
          setTimeout(() => {{
            window.location.href = redirectUrl;
          }}, 250);
        }} else {{
          errText.textContent = data.error || 'Unable to verify access. Please try again.';
          errBox.classList.remove('hidden');
          submitBtn.disabled = false;
          submitBtnText.textContent = 'SUBMIT';
        }}
      }} catch (err) {{
        errText.textContent = 'Unable to verify access right now. Please check your connection and try again.';
        errBox.classList.remove('hidden');
        submitBtn.disabled = false;
        submitBtnText.textContent = 'SUBMIT';
      }}
    }}
  </script>
</body>
</html>"""
    return make_response(html, 200)


@attendant_bp.route('/qr-redirect/<path:token_or_code>', methods=['GET'])
@attendant_bp.route('/qr/<path:token_or_code>', methods=['GET'])
def handle_qr_redirect(token_or_code):
    """
    Direct QR Scan Route:
    Receives QR token or access code scanned by smartphone camera:
      http://<LAN-IP>:5000/qr/<token>
    1. Validates token server-side against database.
    2. Checks token exists, is active, not revoked, not expired, and patient is admitted.
    3. Serves the Attendant Name Entry Screen (NO patient medical data exposed!).
    """
    raw_token = (token_or_code or '').strip()
    if not raw_token:
        return redirect('/Attendant/attendant_access.html', code=302)

    # Cryptographic / Access token validation
    validation = PatientQRToken.validate_token(raw_token)
    if not validation['valid']:
        status = validation.get('status', 'not_found')
        if status == 'revoked':
            return render_qr_error("This QR access has been revoked.", "This patient access QR code has been disabled or replaced by hospital staff.", "block", 403)
        elif status == 'expired':
            return render_qr_error("This QR access has expired.", "This patient access QR code has expired. Please contact hospital staff.", "schedule", 403)
        elif status == 'patient_discharged':
            return render_qr_error("Patient Discharged", "This patient has been discharged. QR attendant access is no longer active.", "check_circle", 403)
        else:
            return render_qr_error("This QR code is invalid.", validation.get('error') or "This QR code is not recognized.", "error", 404)

    # Valid token: Return Name Entry Screen (Patient dashboard remains completely hidden until name is submitted)
    return render_name_entry_screen(raw_token)


@attendant_bp.route('/access', methods=['GET'])
@attendant_bp.route('/access/<path:token>', methods=['GET'])
@attendant_bp.route('/dashboard', methods=['GET'])
def attendant_access_page(token=None):
    """Public entry point when navigating to attendant portal."""
    token_val = token or request.args.get('token', '').strip()
    if token_val:
        validation = PatientQRToken.validate_token(token_val)
        if validation['valid']:
            return render_name_entry_screen(token_val)
    return redirect('/Attendant/attendant_access.html', code=302)


@attendant_bp.route('/qr-access/verify', methods=['POST'])
@attendant_bp.route('/verify', methods=['POST'])
@attendant_bp.route('/access', methods=['POST'])
@attendant_bp.route('/submit-access', methods=['POST'])
def api_verify_qr_access_and_name():
    """
    Public API: Attendant submits their name after QR scan.
    1. Validates submitted name (mandatory, trimmed, 2-80 chars).
    2. Validates QR token server-side (cryptographic token from database).
    3. Resolves patient strictly from validated token.
    4. Creates temporary attendant session token.
    5. Records attendant access & audit log.
    6. Returns authorized redirect result.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token_val = (data.get('token') or data.get('qr_token') or '').strip()
    attendant_name = (data.get('attendant_name') or '').strip()

    # 1. Validate Attendant Name
    if not attendant_name:
        return jsonify({'success': False, 'access_granted': False, 'error': 'Please enter your name to continue.'}), 400

    if len(attendant_name) < 2 or len(attendant_name) > 80:
        return jsonify({'success': False, 'access_granted': False, 'error': 'Attendant name must be between 2 and 80 characters.'}), 400

    # Sanitize name
    clean_name = re.sub(r'[<>{}[\]\\]', '', attendant_name).strip()
    if not clean_name:
        return jsonify({'success': False, 'access_granted': False, 'error': 'Invalid characters in name. Please enter a valid name.'}), 400

    # 2. Validate QR Token
    if not token_val:
        return jsonify({'success': False, 'access_granted': False, 'error': 'Missing or invalid QR token.'}), 400

    validation = PatientQRToken.validate_token(token_val)
    if not validation['valid']:
        status = validation.get('status', 'invalid')
        err_msg = validation.get('error') or "Invalid QR token"
        if status == 'revoked':
            err_msg = "This QR access has been revoked."
        elif status == 'expired':
            err_msg = "This QR access has expired."
        elif status == 'patient_discharged':
            err_msg = "This patient has been discharged. QR attendant access is closed."
        return jsonify({
            'success': False,
            'access_granted': False,
            'status': status,
            'error': err_msg
        }), 403

    patient_id = validation['patient_id']
    patient_code = validation.get('patient_code', f'P{patient_id}')
    patient_name = validation.get('patient_name', 'Patient')
    token_hash = validation.get('token_data', {}).get('token_hash', 'qr-scan')

    # 3. Create Temporary Attendant Access Session
    session_data = generate_attendant_session_token(
        patient_id=patient_id,
        attendant_name=clean_name,
        token_hash=token_hash,
        expires_hours=8
    )

    # 4. Update attendant record name if exists
    try:
        db.execute_query(
            """UPDATE users u
               JOIN attendants a ON u.user_id = a.user_id
               SET u.full_name = %s
               WHERE a.patient_id = %s""",
            (clean_name, patient_id)
        )
    except Exception:
        pass

    # 5. Audit Log
    AuditLog.log(
        action='ATTENDANT_QR_ACCESS',
        entity_type='patient',
        entity_id=patient_id,
        ip_address=request.remote_addr,
        new_value={'attendant_name': clean_name, 'patient_id': patient_id},
        description=f"Attendant '{clean_name}' verified QR access for Patient #{patient_id} ({patient_name}, {patient_code})"
    )

    redirect_url = f"/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id={patient_id}"

    resp = jsonify({
        'success': True,
        'access_granted': True,
        'message': 'Access granted',
        'session': session_data,
        'access_token': session_data['access_token'],
        'patient_id': patient_id,
        'attendant_name': clean_name,
        'patient_code': patient_code,
        'redirect_url': redirect_url
    })

    resp.set_cookie('jeevan_setu_token', session_data['access_token'], max_age=28800, samesite='Lax', path='/')
    resp.set_cookie('jeevan_setu_attendant_patient_id', str(patient_id), max_age=28800, samesite='Lax', path='/')
    resp.set_cookie('jeevan_setu_attendant_name', clean_name, max_age=28800, samesite='Lax', path='/')

    return resp, 200


@attendant_bp.route('/validate-token', methods=['POST'])
def api_validate_qr_token():
    """
    Public: Validate QR token or access code on page load.
    DOES NOT EXPOSE patient medical information.
    """
    data = request.get_json(silent=True) or {}
    token_val = (data.get('token') or data.get('qr_token') or '').strip()
    access_code = data.get('access_code', '').strip()

    if not token_val and not access_code:
        return jsonify({'success': False, 'valid': False, 'error': 'QR Token or access code is required'}), 400

    if access_code:
        validation = PatientQRToken.validate_access_code(access_code)
    else:
        validation = PatientQRToken.validate_token(token_val)

    if not validation['valid']:
        return jsonify({
            'success': False,
            'valid': False,
            'status': validation.get('status', 'invalid'),
            'error': validation['error']
        }), 401

    return jsonify({
        'success': True,
        'valid': True,
        'status': 'active'
    }), 200


@attendant_bp.route('/manual-login', methods=['POST'])
def api_attendant_manual_login():
    """Public: Manual Attendant Login without scanning QR."""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    attendant_name = (data.get('attendant_name') or '').strip()
    patient_query = (data.get('patient_query') or data.get('patient_name') or data.get('uhid') or '').strip()
    relationship = (data.get('relationship') or 'Family').strip()

    if not attendant_name:
        return jsonify({'success': False, 'error': 'Please enter your name to continue.'}), 400

    if len(attendant_name) < 2 or len(attendant_name) > 80:
        return jsonify({'success': False, 'error': 'Attendant name must be between 2 and 80 characters.'}), 400

    clean_attendant_name = re.sub(r'[<>{}[\]\\]', '', attendant_name).strip()
    if not clean_attendant_name:
        return jsonify({'success': False, 'error': 'Invalid characters in attendant name.'}), 400

    if not patient_query:
        return jsonify({'success': False, 'error': "Please enter the patient's full name or UHID."}), 400

    clean_patient_query = re.sub(r'[<>{}[\]\\]', '', patient_query).strip()
    if len(clean_patient_query) < 2:
        return jsonify({'success': False, 'error': 'Patient search term must be at least 2 characters.'}), 400

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

    admitted_matches = [p for p in rows if p.get('status') == 'admitted']

    if not admitted_matches:
        return jsonify({
            'success': False,
            'error': f"Patient '{rows[0]['name']}' ({rows[0].get('patient_code')}) has already been discharged. Active attendant access is only available for currently admitted patients."
        }), 403

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

    patient_id = selected_patient['patient_id']
    session_data = generate_attendant_session_token(
        patient_id=patient_id,
        attendant_name=clean_attendant_name,
        token_hash='manual-login',
        expires_hours=8
    )

    AuditLog.log(
        action='ATTENDANT_MANUAL_LOGIN_GRANTED',
        entity_type='patient',
        entity_id=patient_id,
        ip_address=request.remote_addr,
        new_value={'attendant_name': clean_attendant_name, 'relationship': relationship, 'patient_id': patient_id},
        description=f"Attendant '{clean_attendant_name}' (rel: {relationship or 'Family'}) logged in manually for Patient '{selected_patient['name']}' ({selected_patient.get('patient_code')})"
    )

    redirect_url = f"/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id={patient_id}"

    resp = jsonify({
        'success': True,
        'access_granted': True,
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
    })

    resp.set_cookie('jeevan_setu_token', session_data['access_token'], max_age=28800, samesite='Lax', path='/')
    resp.set_cookie('jeevan_setu_attendant_patient_id', str(patient_id), max_age=28800, samesite='Lax', path='/')
    resp.set_cookie('jeevan_setu_attendant_name', clean_attendant_name, max_age=28800, samesite='Lax', path='/')

    return resp, 200


@attendant_bp.route('/search-patients', methods=['GET'])
def api_attendant_search_patients():
    """Public: Live search for admitted patients."""
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


# =============================================================
# 3. ATTENDANT DASHBOARD DATA APIS (READ-ONLY WITH ISOLATION)
# =============================================================

@attendant_bp.route('/session', methods=['GET'])
def api_get_attendant_session():
    """Check if the attendant session token is valid."""
    session = get_current_attendant_session()
    if not session:
        return jsonify({'success': False, 'error': 'Attendant access required. Please scan the patient\'s QR code.'}), 401

    return jsonify({
        'success': True,
        'patient_id': session['patient_id'],
        'attendant_name': session['attendant_name']
    }), 200


@attendant_bp.route('/patient', methods=['GET'])
@attendant_bp.route('/view', methods=['GET'])
def api_get_attendant_patient_data():
    """
    Read-only patient recovery status and vitals for the attendant dashboard.
    Strictly isolated:
    - Resolves patient_id strictly from the verified attendant session token.
    - Direct URL access without a valid session returns 401 Unauthorized with
      'Attendant access required. Please scan the patient\'s QR code.'
    - Cross-patient URL tampering (?patient_id=X) is ignored and the verified patient is returned.
    """
    session = get_current_attendant_session()
    
    # Only check staff user if explicit Authorization header is passed with a staff token
    auth_header = request.headers.get('Authorization', '')
    user = None
    if auth_header.startswith('Bearer ') and not session:
        user = get_current_authenticated_user()

    patient_id = None
    attendant_name = 'Attendant'

    if session:
        # Strict session isolation: use the authorized patient_id encoded in the signed JWT
        patient_id = session['patient_id']
        attendant_name = session.get('attendant_name', 'Attendant')
    elif user and getattr(user, 'role', '').lower() in ('doctor', 'nurse', 'admin'):
        # Explicit clinical staff token preview
        req_pid = request.args.get('patient_id') or request.args.get('id') or 1
        try:
            patient_id = int(req_pid)
        except (ValueError, TypeError):
            patient_id = 1
        attendant_name = getattr(user, 'full_name', 'Clinical Staff')
    else:
        # Unauthenticated direct access is blocked
        return jsonify({
            'success': False,
            'error': 'Attendant access required. Please scan the patient\'s QR code.'
        }), 401

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
            'systolic_bp': vitals.get('blood_pressure_sys'),
            'diastolic_bp': vitals.get('blood_pressure_dia'),
            'blood_pressure': bp_str,
            'temperature': vitals.get('temperature'),
            'respiratory_rate': vitals.get('respiratory_rate'),
            'spo2': vitals.get('spo2'),
            'ews_score': vitals.get('ews_score', 0),
            'recorded_at': vitals.get('recorded_at').isoformat() if vitals.get('recorded_at') else None
        }

    # Latest EWS
    ews_row = db.execute_query(
        "SELECT * FROM ews_scores WHERE patient_id = %s ORDER BY calculated_at DESC, ews_id DESC LIMIT 1",
        (patient_id,), fetch=True
    )
    total_score = ews_row[0]['total_score'] if ews_row else (vitals.get('ews_score', 0) if vitals else 0)
    risk_level = ews_row[0]['risk_level'] if ews_row else ('CRITICAL' if total_score >= 7 else ('HIGH' if total_score >= 5 else ('MEDIUM' if total_score >= 3 else 'LOW')))

    condition = "Stable"
    if total_score >= 7 or risk_level == 'CRITICAL':
        condition = "Critical Care"
    elif total_score >= 4 or risk_level in ('HIGH', 'MEDIUM'):
        condition = "Moderate Risk"

    return jsonify({
        'success': True,
        'data': {
            'patient_id': patient['patient_id'],
            'name': patient['name'],
            'patient_name': patient['name'],
            'patient_code': patient['patient_code'],
            'age': patient['age'],
            'gender': patient['gender'],
            'ward_type': patient['ward_type'],
            'bed_number': patient['bed_number'],
            'diagnosis': patient.get('diagnosis', 'Clinical Care'),
            'admission_date': str(patient['admission_date']) if patient.get('admission_date') else None,
            'status': patient['status'],
            'total_score': total_score,
            'risk_level': risk_level,
            'condition': condition,
            'attendant_name': attendant_name,
            'latest_vitals': vitals_summary,
            'vitals_history': vitals_history
        }
    }), 200
