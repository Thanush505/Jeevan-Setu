"""
models/qr_token_model.py — Cryptographic Permanent Patient QR token generation, validation, and audit for attendant access.
"""

import io
import base64
import secrets
import hashlib
from datetime import datetime, timedelta
import qrcode
from database.db import db
from models.audit_log_model import AuditLog


class PatientQRToken:
    """Manages permanent patient QR tokens, validation, revocation, and attendant access sessions."""

    PERMANENT_EXPIRY = datetime(2099, 12, 31, 23, 59, 59)

    @staticmethod
    def generate_qr_image_data_url(data_str):
        """Generate base64 data URL for a QR code image containing the given URL/string."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(data_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0a1e4d", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def get_effective_base_url(base_url=None):
        """Determine effective base URL for QR links (default: http://192.168.1.3:5000)."""
        if base_url:
            return base_url.rstrip('/')
        from config import get_config
        import os
        config = get_config()
        ext_base = getattr(config, 'EXTERNAL_BASE_URL', None) or os.getenv('EXTERNAL_BASE_URL')
        if ext_base:
            return ext_base.rstrip('/')
        lan_ip = getattr(config, 'LAN_IP', '192.168.1.3')
        port = getattr(config, 'PORT', 5000)
        return f"http://{lan_ip}:{port}".rstrip('/')

    @staticmethod
    def build_access_url(raw_token, base_url=None):
        """Build the web URL that the QR code points to: http://<LAN-IP>:5000/qr/<token>"""
        clean_base = PatientQRToken.get_effective_base_url(base_url)
        return f"{clean_base}/qr/{raw_token}"

    @staticmethod
    def normalize_qr_url(stored_url, token_hash=None, base_url=None):
        """Normalize stored QR URL so it always uses the reachable LAN base URL and /qr/<token> route."""
        clean_base = PatientQRToken.get_effective_base_url(base_url)
        if stored_url:
            if '/qr/' in stored_url:
                token_tail = stored_url.split('/qr/', 1)[1]
                return f"{clean_base}/qr/{token_tail}"
            elif '/Attendant/attendant_access.html' in stored_url:
                if 'token=' in stored_url:
                    tok = stored_url.split('token=', 1)[1].split('&')[0]
                    return f"{clean_base}/qr/{tok}"
                query_or_tail = stored_url.split('/Attendant/', 1)[1]
                return f"{clean_base}/Attendant/{query_or_tail}"
        if token_hash:
            return f"{clean_base}/qr/{token_hash}"
        return f"{clean_base}/Attendant/attendant_access.html"

    @staticmethod
    def generate_token(patient_id, created_by=None, base_url=None, deactivate_previous=True, force=False, valid_hours=None):
        """
        Generate or retrieve a permanent cryptographically secure QR token for a patient.
        If the patient already has an active permanent QR and force is False, returns existing QR.
        The QR code data contains ONLY the secure access URL, NEVER raw patient PII.
        """
        # If not forcing new token, check if patient already has an active QR
        if not force and valid_hours is None:
            existing = PatientQRToken.get_active_by_patient(patient_id, base_url=base_url)
            if existing:
                return existing

        # Deactivate previous active tokens if requested
        if deactivate_previous or force:
            db.execute_query(
                "UPDATE patient_qr_tokens SET is_active = FALSE WHERE patient_id = %s AND is_active = TRUE",
                (patient_id,)
            )

        # Cryptographically secure random token (64 hex characters)
        random_entropy = secrets.token_hex(24)
        raw_token = f"JS-QR-P{patient_id}-{random_entropy}"
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # 8-character human-friendly backup code
        access_code = secrets.token_hex(4).upper()
        if valid_hours is not None:
            expires_at = datetime.now() + timedelta(hours=valid_hours)
        else:
            expires_at = PatientQRToken.PERMANENT_EXPIRY

        # QR payload contains the direct access URL
        access_url = PatientQRToken.build_access_url(raw_token, base_url)
        qr_image_url = PatientQRToken.generate_qr_image_data_url(access_url)

        token_id = db.execute_query(
            """INSERT INTO patient_qr_tokens 
               (patient_id, token_hash, access_code, qr_code_data, expires_at, is_active, created_by)
               VALUES (%s, %s, %s, %s, %s, TRUE, %s)""",
            (patient_id, token_hash, access_code, access_url, expires_at, created_by)
        )

        # Audit log
        AuditLog.log(
            action='generate_patient_qr',
            user_id=created_by,
            entity_type='patient_qr_token',
            entity_id=token_id,
            new_value={'patient_id': patient_id, 'is_permanent': (valid_hours is None), 'access_code': access_code},
            description=f"Generated permanent patient QR #{token_id} for Patient #{patient_id}"
        )

        return {
            'token_id': token_id,
            'patient_id': patient_id,
            'raw_token': raw_token,
            'token_hash': token_hash,
            'access_code': access_code,
            'access_url': access_url,
            'qr_code_data': access_url,
            'qr_image_data_url': qr_image_url,
            'expires_at': expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_active': True,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_active_by_patient(patient_id, base_url=None):
        """Fetch active permanent QR token for a patient without recreating it."""
        records = db.execute_query(
            """SELECT t.*, p.name AS patient_name, p.patient_code, p.ward_type, 
                      p.bed_number, p.status AS patient_status, p.admission_date,
                      p.assigned_doctor as doctor_id, u.full_name as doctor_name
               FROM patient_qr_tokens t
               JOIN patients p ON t.patient_id = p.patient_id
               LEFT JOIN users u ON p.assigned_doctor = u.user_id
               WHERE t.patient_id = %s AND t.is_active = TRUE
               ORDER BY t.token_id DESC LIMIT 1""",
            (patient_id,), fetch=True
        )

        if not records:
            return None

        token = dict(records[0])
        access_url = PatientQRToken.normalize_qr_url(token.get('qr_code_data'), token.get('token_hash'), base_url)
        qr_image = PatientQRToken.generate_qr_image_data_url(access_url)

        token['access_url'] = access_url
        token['qr_image_data_url'] = qr_image
        token['is_active'] = bool(token.get('is_active'))
        
        # Populate raw_token from access_url if possible
        if access_url and '/qr/' in access_url:
            token['raw_token'] = access_url.split('/qr/', 1)[1].split('?')[0]
        else:
            token['raw_token'] = token.get('token_hash')

        if token.get('created_at'):
            token['created_at'] = str(token['created_at'])
        if token.get('expires_at'):
            token['expires_at'] = str(token['expires_at'])

        return token

    @staticmethod
    def get_all_patients_qr_status(base_url=None):
        """
        Fetch all admitted patients alongside their latest QR token status.
        Returns a rich list for the Admin Patient QR Access Management table.
        """
        rows = db.execute_query(
            """SELECT 
                    p.patient_id, p.patient_code, p.name as patient_name, p.age, p.gender,
                    p.ward_type, p.bed_number, p.diagnosis, p.status as patient_status,
                    p.admission_date, p.assigned_doctor as doctor_id, u.full_name as doctor_name,
                    t.token_id, t.token_hash, t.access_code, t.qr_code_data,
                    t.is_active as qr_is_active, t.created_at as qr_created_at,
                    t.expires_at as qr_expires_at
               FROM patients p
               LEFT JOIN users u ON p.assigned_doctor = u.user_id
               LEFT JOIN (
                    SELECT t1.*
                    FROM patient_qr_tokens t1
                    INNER JOIN (
                        SELECT patient_id, MAX(token_id) as max_token_id
                        FROM patient_qr_tokens
                        GROUP BY patient_id
                    ) t2 ON t1.token_id = t2.max_token_id
               ) t ON p.patient_id = t.patient_id
               WHERE p.status = 'admitted'
               ORDER BY p.patient_id ASC""",
            fetch=True
        ) or []

        result = []
        for r in rows:
            item = dict(r)
            # Determine QR Status
            if item.get('token_id') is None:
                item['qr_status'] = 'not_generated'
            elif item.get('qr_is_active'):
                item['qr_status'] = 'active'
            else:
                item['qr_status'] = 'revoked'

            # Build QR Image URL if active
            if item['qr_status'] == 'active' and item.get('token_id'):
                norm_url = PatientQRToken.normalize_qr_url(item.get('qr_code_data'), item.get('token_hash'), base_url)
                item['qr_image_data_url'] = PatientQRToken.generate_qr_image_data_url(norm_url)
                item['access_url'] = norm_url
            else:
                item['qr_image_data_url'] = None
                item['access_url'] = None

            if item.get('admission_date'):
                item['admission_date'] = str(item['admission_date'])
            if item.get('qr_created_at'):
                item['qr_created_at'] = str(item['qr_created_at'])
            if item.get('qr_expires_at'):
                item['qr_expires_at'] = str(item['qr_expires_at'])

            result.append(item)

        return result

    @staticmethod
    def validate_token(token_hash_or_raw):
        """
        Validate token and check status.
        Returns dict with:
            { 'valid': bool, 'status': 'active' | 'revoked' | 'not_found' | 'patient_discharged',
              'error': str, 'patient': dict, 'token_data': dict }
        """
        if not token_hash_or_raw:
            return {'valid': False, 'status': 'not_found', 'error': 'Token is required', 'token_data': None}

        token_clean = token_hash_or_raw.strip()

        # Calculate hash if raw token passed
        if token_clean.startswith("JS-"):
            h = hashlib.sha256(token_clean.encode('utf-8')).hexdigest()
        else:
            h = token_clean

        records = db.execute_query(
            """SELECT t.*, p.patient_id, p.name AS patient_name, p.patient_code, p.age, p.gender,
                      p.ward_type, p.bed_number, p.status AS patient_status, p.admission_date,
                      p.diagnosis, u.full_name as doctor_name
               FROM patient_qr_tokens t
               JOIN patients p ON t.patient_id = p.patient_id
               LEFT JOIN users u ON p.assigned_doctor = u.user_id
               WHERE t.token_hash = %s OR t.access_code = %s""",
            (h, token_clean), fetch=True
        )

        if not records:
            return {
                'valid': False,
                'status': 'not_found',
                'error': 'This QR code is not recognized. Please contact hospital staff.',
                'token_data': None
            }

        token = dict(records[0])

        # Check if QR has expired
        exp = token.get('expires_at')
        if exp and isinstance(exp, datetime) and exp < datetime.now():
            return {
                'valid': False,
                'status': 'expired',
                'error': 'This QR code has expired. Please contact hospital staff.',
                'token_data': token,
                'patient_id': token['patient_id'],
                'patient_code': token.get('patient_code')
            }

        # Check if QR was explicitly revoked or replaced
        if not token.get('is_active'):
            return {
                'valid': False,
                'status': 'revoked',
                'error': 'This patient access QR has been disabled, revoked or replaced. Please contact hospital staff.',
                'token_data': token,
                'patient_id': token['patient_id'],
                'patient_code': token.get('patient_code')
            }

        # Check patient admission status
        if token.get('patient_status') != 'admitted':
            return {
                'valid': False,
                'status': 'patient_discharged',
                'error': 'Patient has been discharged. QR access session cannot be opened.',
                'token_data': token,
                'patient_id': token['patient_id'],
                'patient_code': token.get('patient_code')
            }

        return {
            'valid': True,
            'status': 'active',
            'error': None,
            'token_data': token,
            'patient_id': token['patient_id'],
            'patient_name': token.get('patient_name'),
            'patient_code': token.get('patient_code'),
            'ward_type': token.get('ward_type'),
            'bed_number': token.get('bed_number'),
            'age': token.get('age'),
            'gender': token.get('gender'),
            'doctor_name': token.get('doctor_name'),
            'admission_date': str(token.get('admission_date')) if token.get('admission_date') else None
        }

    @staticmethod
    def validate_access_code(access_code):
        """
        Validate 8-character attendant backup access code.
        """
        if not access_code:
            return {'valid': False, 'error': 'Access code is required', 'token_data': None}

        code_clean = access_code.strip().upper()

        records = db.execute_query(
            """SELECT t.*, p.name AS patient_name, p.patient_code, p.age, p.gender,
                      p.ward_type, p.bed_number, p.status AS patient_status, p.admission_date,
                      u.full_name as doctor_name
               FROM patient_qr_tokens t
               JOIN patients p ON t.patient_id = p.patient_id
               LEFT JOIN users u ON p.assigned_doctor = u.user_id
               WHERE t.access_code = %s""",
            (code_clean,), fetch=True
        )

        if not records:
            return {'valid': False, 'status': 'not_found', 'error': 'Invalid access code.', 'token_data': None}

        token = dict(records[0])

        if not token.get('is_active'):
            return {'valid': False, 'status': 'revoked', 'error': 'This access code has been deactivated.', 'token_data': token}

        if token.get('patient_status') != 'admitted':
            return {'valid': False, 'status': 'patient_discharged', 'error': 'Patient has been discharged.', 'token_data': token}

        return {
            'valid': True,
            'status': 'active',
            'error': None,
            'token_data': token,
            'patient_id': token['patient_id'],
            'patient_name': token.get('patient_name'),
            'patient_code': token.get('patient_code'),
            'ward_type': token.get('ward_type'),
            'bed_number': token.get('bed_number')
        }

    @staticmethod
    def regenerate_token(patient_id, created_by=None, base_url=None):
        """Regenerate permanent QR token for a patient, revoking previous tokens."""
        AuditLog.log(
            action='regenerate_patient_qr',
            user_id=created_by,
            entity_type='patient',
            entity_id=patient_id,
            description=f"Regenerated permanent attendant QR for Patient #{patient_id} (previous QR invalidated)"
        )
        return PatientQRToken.generate_token(
            patient_id=patient_id,
            created_by=created_by,
            base_url=base_url,
            deactivate_previous=True,
            force=True
        )

    @staticmethod
    def revoke_token(token_id=None, patient_id=None, revoked_by=None):
        """Revoke an active permanent QR token."""
        if token_id:
            token = db.execute_query("SELECT * FROM patient_qr_tokens WHERE token_id = %s", (token_id,), fetch=True)
            if not token:
                return False
            db.execute_query(
                "UPDATE patient_qr_tokens SET is_active = FALSE WHERE token_id = %s",
                (token_id,)
            )
            pid = token[0]['patient_id']
        elif patient_id:
            db.execute_query(
                "UPDATE patient_qr_tokens SET is_active = FALSE WHERE patient_id = %s",
                (patient_id,)
            )
            pid = patient_id
        else:
            return False

        AuditLog.log(
            action='revoke_patient_qr',
            user_id=revoked_by,
            entity_type='patient',
            entity_id=pid,
            description=f"Revoked permanent attendant QR for Patient #{pid}"
        )
        return True

    @staticmethod
    def get_by_patient(patient_id, active_only=True):
        """Get token records for a patient."""
        if active_only:
            return db.execute_query(
                """SELECT * FROM patient_qr_tokens 
                   WHERE patient_id = %s AND is_active = TRUE
                   ORDER BY created_at DESC""",
                (patient_id,), fetch=True
            ) or []

        return db.execute_query(
            """SELECT * FROM patient_qr_tokens 
               WHERE patient_id = %s 
               ORDER BY created_at DESC""",
            (patient_id,), fetch=True
        ) or []

    @staticmethod
    def get_by_id(token_id):
        """Fetch single token record."""
        result = db.execute_query(
            "SELECT * FROM patient_qr_tokens WHERE token_id = %s",
            (token_id,), fetch=True
        )
        return result[0] if result else None
