"""
routes/patient_routes.py — Phase 6 Patient Management REST APIs & Web Dashboard.
Endpoints:
    GET    /patients & /api/v1/patients         (List, search, filter, paginate)
    GET    /patients/{id} & /api/v1/patients/{id} (Get patient profile)
    POST   /patients & /api/v1/patients         (Register & admit patient)
    PUT    /patients/{id} & /api/v1/patients/{id} (Update patient details)
    DELETE /patients/{id} & /api/v1/patients/{id} (Discharge patient)
    GET    /patients/search & /api/v1/patients/search (Fast search)
    GET    /patients/{id}/history               (Clinical history timeline)
"""

from datetime import datetime
import secrets
from werkzeug.security import generate_password_hash
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from database.db import db
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.audit_log_model import AuditLog
from models.qr_token_model import PatientQRToken
from modules.scoring_engine import get_risk_level
from utils.decorators import permission_required, get_current_authenticated_user, _is_api_request
from utils.validators import validate_patient_data

patient_bp = Blueprint('patient', __name__)


# ─────────────────────────────────────────────────────────────
# 1. GET /patients & /api/v1/patients — List, Filter & Search
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/', methods=['GET'])
@patient_bp.route('', methods=['GET'])
@permission_required('view_patients')
def list_patients():
    """
    List patients with search, ward filtering, status filtering, and pagination.
    Query Params:
        search / q: string (searches name, patient_code, diagnosis, bed)
        ward / ward_type: string ('ICU', 'HDU', 'General')
        status: string ('admitted', 'discharged', 'transferred', 'deceased', 'all')
        doctor_id: int
        nurse_id: int
        gender: string ('Male', 'Female', 'Other')
        blood_group: string ('A+', 'O+', etc.)
        page: int (default 1)
        limit: int (default 20)
    """
    if not _is_api_request() and request.endpoint == 'patient.patient_table':
        ward = request.args.get('ward')
        patients = Patient.get_by_ward(ward) if ward else Patient.get_all()
        return render_template('Doctor/Doctor_all_patients/Doctor_all_patients.html', patients=patients, ward=ward)

    search = request.args.get('search') or request.args.get('q')
    ward_type = request.args.get('ward') or request.args.get('ward_type')
    status = request.args.get('status', 'admitted')
    doctor_id = request.args.get('doctor_id')
    nurse_id = request.args.get('nurse_id')
    gender = request.args.get('gender')
    blood_group = request.args.get('blood_group')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    # Scoping: if authenticated user is a Doctor, restrict strictly to their assigned patients
    user = get_current_authenticated_user()
    if user and getattr(user, 'role', '') == 'doctor':
        doctor_id = user.id

    result = Patient.get_filtered(
        search=search,
        ward_type=ward_type,
        status=status,
        doctor_id=doctor_id,
        nurse_id=nurse_id,
        gender=gender,
        blood_group=blood_group,
        page=page,
        limit=limit
    )

    if _is_api_request():
        return jsonify({
            'success': True,
            'data': result['patients'],
            'patients': result['patients'],
            'total': result['total'],
            'pagination': {
                'total': result['total'],
                'page': result['page'],
                'limit': result['limit'],
                'pages': result['pages']
            }
        }), 200

    return render_template('Doctor/Doctor_all_patients/Doctor_all_patients.html', patients=result['patients'])


# ─────────────────────────────────────────────────────────────
# 2. GET /patients/search — Search Query API
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/search', methods=['GET'])
@permission_required('view_patients')
def search_patients():
    """
    Fast multi-column search by query string.
    Query: ?q=... or ?search=...
    """
    query = request.args.get('q') or request.args.get('search') or ''
    results = Patient.search(query) if query else []
    return jsonify({
        'success': True,
        'query': query,
        'count': len(results),
        'data': results
    }), 200


# ─────────────────────────────────────────────────────────────
# 2b. GET /patients/nurse-search & /api/v1/patients/nurse-search
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/nurse-search', methods=['GET'])
def nurse_patient_search():
    """
    Role-aware patient search for Nurse Portal top header.
    Filters to admitted patients matching query (Name, UHID, Ward, Bed, Diagnosis).
    """
    query = (request.args.get('q') or request.args.get('search') or request.args.get('query') or '').strip()
    if not query:
        return jsonify({
            'success': True,
            'query': '',
            'count': 0,
            'data': []
        }), 200

    results = Patient.search(query)
    formatted = []
    for p in results[:8]:
        formatted.append({
            'patient_id': p.get('patient_id'),
            'name': p.get('name'),
            'patient_code': p.get('patient_code'),
            'ward_name': p.get('ward_name') or p.get('ward_type') or 'ICU',
            'bed_number': p.get('bed_number') or 'Unassigned',
            'diagnosis': p.get('diagnosis') or 'General Observation',
            'status': p.get('status') or 'admitted',
            'ews_score': p.get('ews_score', 0),
            'risk_level': p.get('risk_level') or 'normal'
        })

    return jsonify({
        'success': True,
        'query': query,
        'count': len(formatted),
        'data': formatted
    }), 200



# ─────────────────────────────────────────────────────────────
# 3. GET /patients/{id} — Single Patient Profile
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/<int:patient_id>', methods=['GET'])
@permission_required('view_patients')
def get_patient(patient_id):
    """
    Fetch single patient profile by ID.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        if _is_api_request():
            return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404
        flash('Patient not found.', 'error')
        return redirect(url_for('patient.dashboard'))

    return jsonify({
        'success': True,
        'data': patient
    }), 200


# ─────────────────────────────────────────────────────────────
# 4A. GET /admission-options & /api/v1/patients/admission-options
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/admission-options', methods=['GET'])
@patient_bp.route('/admission-meta', methods=['GET'])
@permission_required('edit_patients')
def get_admission_options():
    """
    Fetch dynamically generated metadata for patient admission:
    - Next unique UHID
    - Current datetime
    - Available wards & bed counts
    - List of available beds per ward
    - Available active doctors + live patient workload
    - Available active nurses + live patient workload
    """
    try:
        next_uhid = Patient.generate_patient_code()
        adm_datetime = datetime.now().strftime('%Y-%m-%dT%H:%M')

        # Wards with available bed counts
        wards = db.execute_query("""
            SELECT w.ward_id, w.name, w.ward_type, w.floor_number, w.total_beds,
                   COUNT(CASE WHEN b.status = 'available' AND (b.is_active IS NULL OR b.is_active = 1) THEN 1 END) AS available_beds
            FROM wards w
            LEFT JOIN beds b ON w.ward_id = b.ward_id
            WHERE w.is_active = 1 OR w.is_active IS NULL
            GROUP BY w.ward_id, w.name, w.ward_type, w.floor_number, w.total_beds
            ORDER BY w.ward_id
        """, fetch=True) or []

        # Available beds only
        available_beds = db.execute_query("""
            SELECT b.bed_id, b.bed_number, b.ward_id, b.status, w.name AS ward_name, w.ward_type
            FROM beds b
            JOIN wards w ON b.ward_id = w.ward_id
            WHERE b.status = 'available' AND (b.is_active IS NULL OR b.is_active = 1)
            ORDER BY w.ward_id, b.bed_number
        """, fetch=True) or []

        # Doctors with active patient workload count
        doctors = db.execute_query("""
            SELECT u.user_id, d.doctor_id, u.full_name, d.specialization, d.qualification,
                   d.experience_years, u.is_active,
                   (SELECT COUNT(*) FROM patients p WHERE p.assigned_doctor = u.user_id AND p.status = 'admitted') AS workload
            FROM users u
            LEFT JOIN doctors d ON u.user_id = d.user_id
            WHERE u.role = 'doctor' AND (u.is_active = 1 OR u.is_active IS NULL)
            ORDER BY u.full_name
        """, fetch=True) or []

        # Nurses with active patient workload count
        nurses = db.execute_query("""
            SELECT u.user_id, n.nurse_id, u.full_name, n.specialization, n.ward_assignment,
                   n.shift, u.is_active,
                   (SELECT COUNT(*) FROM patients p WHERE p.assigned_nurse = u.user_id AND p.status = 'admitted') AS workload
            FROM users u
            LEFT JOIN nurses n ON u.user_id = n.user_id
            WHERE u.role = 'nurse' AND (u.is_active = 1 OR u.is_active IS NULL)
            ORDER BY u.full_name
        """, fetch=True) or []

        return jsonify({
            'success': True,
            'data': {
                'next_uhid': next_uhid,
                'admission_datetime': adm_datetime,
                'wards': wards,
                'available_beds': available_beds,
                'doctors': doctors,
                'nurses': nurses
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to load admission options: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# 4B. POST /admit & /api/v1/patients/admit — Transactional Patient Admission
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/admit', methods=['POST'])
@permission_required('edit_patients')
def admit_patient():
    """
    Transaction-backed complete patient admission:
    - Validates demographics, ward, available bed, assigned doctor & nurse, attendant.
    - Locks bed to prevent race conditions.
    - Creates patient with status = 'admitted'.
    - Updates bed status to 'occupied'.
    - Records bed_management entry.
    - Creates attendant user & attendant mapping with unique access code.
    - Generates QR token and logs audit trail.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    # Basic validations
    name = (data.get('name') or '').strip()
    if not name or len(name) < 2:
        return jsonify({'success': False, 'error': 'Full patient name is required (at least 2 characters).'}), 422

    try:
        age = int(data.get('age', 0))
        if age < 0 or age > 130:
            return jsonify({'success': False, 'error': 'Age must be between 0 and 130.'}), 422
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'A valid age is required.'}), 422

    gender = (data.get('gender') or '').strip()
    if gender not in ('Male', 'Female', 'Other'):
        return jsonify({'success': False, 'error': 'Gender must be Male, Female, or Other.'}), 422

    diagnosis = (data.get('diagnosis') or '').strip()
    if not diagnosis:
        return jsonify({'success': False, 'error': 'Diagnosis is required.'}), 422

    blood_group = (data.get('blood_group') or '').strip() or None
    contact_number = (data.get('contact_number') or '').strip() or None

    # Ward & Bed
    try:
        ward_id = int(data.get('ward_id'))
        bed_id = int(data.get('bed_id'))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Ward and Bed selections are required.'}), 422

    # Staff
    try:
        doctor_user_id = int(data.get('assigned_doctor'))
        nurse_user_id = int(data.get('assigned_nurse'))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Both Doctor and Nurse assignments are required.'}), 422

    # Attendant
    attendant_name = (data.get('attendant_name') or '').strip()
    attendant_rel = (data.get('attendant_relationship') or '').strip()
    attendant_contact = (data.get('attendant_contact') or '').strip()

    if not attendant_name or len(attendant_name) < 2:
        return jsonify({'success': False, 'error': 'Attendant name is required (at least 2 characters).'}), 422
    if not attendant_rel:
        return jsonify({'success': False, 'error': 'Attendant relationship is required.'}), 422
    if not attendant_contact or len(attendant_contact) < 7:
        return jsonify({'success': False, 'error': 'Valid attendant contact number is required.'}), 422

    # Admission date/time
    adm_dt_str = (data.get('admission_date') or '').strip()
    if adm_dt_str:
        try:
            adm_date = datetime.fromisoformat(adm_dt_str)
        except Exception:
            adm_date = datetime.now()
    else:
        adm_date = datetime.now()

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    # Database Transaction
    try:
        with db.transaction() as cursor:
            # 1. Lock and re-verify Bed availability
            cursor.execute(
                "SELECT bed_id, bed_number, ward_id, status FROM beds WHERE bed_id = %s FOR UPDATE",
                (bed_id,)
            )
            bed_row = cursor.fetchone()
            if not bed_row:
                return jsonify({'success': False, 'error': f'Selected bed (ID: {bed_id}) not found.'}), 404
            if bed_row['status'] != 'available':
                return jsonify({'success': False, 'error': f"Bed {bed_row['bed_number']} is no longer available (currently {bed_row['status']})."}), 409
            if int(bed_row['ward_id']) != int(ward_id):
                return jsonify({'success': False, 'error': f"Bed {bed_row['bed_number']} does not belong to the selected ward."}), 400

            # 2. Verify Ward
            cursor.execute("SELECT ward_id, name, ward_type FROM wards WHERE ward_id = %s", (ward_id,))
            ward_row = cursor.fetchone()
            if not ward_row:
                return jsonify({'success': False, 'error': 'Selected ward not found.'}), 404
            ward_type = ward_row.get('ward_type') or 'ICU'

            # 3. Verify Doctor is active
            cursor.execute("SELECT user_id, full_name, is_active FROM users WHERE user_id = %s AND role = 'doctor'", (doctor_user_id,))
            doc_row = cursor.fetchone()
            if not doc_row or (doc_row.get('is_active') is not None and not doc_row['is_active']):
                return jsonify({'success': False, 'error': 'Selected Doctor is inactive or invalid.'}), 400

            # 4. Verify Nurse is active
            cursor.execute("SELECT user_id, full_name, is_active FROM users WHERE user_id = %s AND role = 'nurse'", (nurse_user_id,))
            nurse_row = cursor.fetchone()
            if not nurse_row or (nurse_row.get('is_active') is not None and not nurse_row['is_active']):
                return jsonify({'success': False, 'error': 'Selected Nurse is inactive or invalid.'}), 400

            # 5. Generate Safe Unique UHID
            patient_code = (data.get('patient_code') or '').strip()
            if not patient_code:
                patient_code = Patient.generate_patient_code()
            else:
                cursor.execute("SELECT patient_id FROM patients WHERE patient_code = %s", (patient_code,))
                if cursor.fetchone():
                    patient_code = Patient.generate_patient_code()

            # 6. Insert Patient
            cursor.execute("""
                INSERT INTO patients (patient_code, name, age, gender, blood_group, contact_number,
                                      emergency_contact, admission_date, ward_id, bed_id, ward_type,
                                      bed_number, diagnosis, status, assigned_doctor, assigned_nurse, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'admitted', %s, %s, %s)
            """, (
                patient_code, name, age, gender, blood_group, contact_number,
                attendant_contact, adm_date, ward_id, bed_id, ward_type,
                bed_row['bed_number'], diagnosis, doctor_user_id, nurse_user_id, user_id
            ))
            patient_id = cursor.lastrowid

            # 7. Mark Bed as Occupied
            cursor.execute(
                "UPDATE beds SET status = 'occupied', updated_at = NOW() WHERE bed_id = %s",
                (bed_id,)
            )

            # 8. Record Bed Management Allocation
            cursor.execute("""
                INSERT INTO bed_management (patient_id, bed_id, ward_id, allocated_at, status, allocated_by, notes)
                VALUES (%s, %s, %s, %s, 'occupied', %s, 'Initial patient admission')
            """, (patient_id, bed_id, ward_id, adm_date, user_id))

            # 9. Create Attendant User & Attendants Table Record
            att_username = f"att_{patient_code.lower().replace('-', '_')}"
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (att_username,))
            existing_u = cursor.fetchone()
            if existing_u:
                att_user_id = existing_u['user_id']
            else:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, role_id, role, department, is_active)
                    VALUES (%s, %s, %s, %s, 4, 'attendant', NULL, 1)
                """, (
                    att_username,
                    generate_password_hash('Attendant@123'),
                    attendant_name,
                    f"{att_username}@jeevansetu.in"
                ))
                att_user_id = cursor.lastrowid

            access_code = f"JSACC{secrets.randbelow(90000) + 10000}"
            cursor.execute("""
                INSERT INTO attendants (patient_id, user_id, relationship, access_code, is_active)
                VALUES (%s, %s, %s, %s, 1)
            """, (patient_id, att_user_id, attendant_rel, access_code))

            # 10. QR Token (if table exists)
            raw_token = secrets.token_urlsafe(32)
            try:
                cursor.execute("""
                    INSERT INTO patient_qr_tokens (patient_id, token, access_code, is_active, created_by)
                    VALUES (%s, %s, %s, 1, %s)
                """, (patient_id, raw_token, access_code, user_id))
            except Exception:
                pass

            # 11. Audit Log
            try:
                cursor.execute("""
                    INSERT INTO audit_logs (action, user_id, entity_type, entity_id, description, ip_address)
                    VALUES ('admit_patient', %s, 'patient', %s, %s, %s)
                """, (
                    user_id, patient_id,
                    f"Patient {name} ({patient_code}) admitted to {ward_row['name']} Bed {bed_row['bed_number']}. Assigned Dr. {doc_row['full_name']} & Nurse {nurse_row['full_name']}.",
                    request.remote_addr
                ))
            except Exception:
                pass

        # Transaction committed successfully. Fetch enriched patient object
        created_patient = Patient.get_by_id(patient_id)

        return jsonify({
            'success': True,
            'message': 'Patient admitted successfully.',
            'data': {
                'patient': created_patient,
                'patient_id': patient_id,
                'patient_code': patient_code,
                'assigned_doctor': doc_row['full_name'],
                'assigned_nurse': nurse_row['full_name'],
                'ward': ward_row['name'],
                'bed': bed_row['bed_number'],
                'attendant': {
                    'name': attendant_name,
                    'relationship': attendant_rel,
                    'contact': attendant_contact,
                    'access_code': access_code
                }
            }
        }), 201

    except Exception as e:
        return jsonify({'success': False, 'error': f'Admission failed: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# 4C. POST /patients — Standard Patient Registration
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/', methods=['POST'])
@patient_bp.route('', methods=['POST'])
@permission_required('edit_patients')
def create_patient():
    """
    Register and admit a new patient.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    # If full admission data is passed, route to admit_patient logic
    if data.get('ward_id') and data.get('bed_id') and data.get('assigned_nurse'):
        return admit_patient()

    # Cast age
    try:
        data['age'] = int(data.get('age', 0))
    except (ValueError, TypeError):
        data['age'] = None

    errors = validate_patient_data(data)
    if errors:
        if _is_api_request():
            return jsonify({'success': False, 'errors': errors, 'error': errors[0]}), 422
        for err in errors:
            flash(err, 'error')
        return render_template('add_patient.html')

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    try:
        assigned_doc = int(data['assigned_doctor']) if data.get('assigned_doctor') else None
        assigned_nurse = int(data['assigned_nurse']) if data.get('assigned_nurse') else None
        ward_id = int(data['ward_id']) if data.get('ward_id') else None
        bed_id = int(data['bed_id']) if data.get('bed_id') else None

        patient_id = Patient.create(
            name=data['name'].strip(),
            age=data['age'],
            gender=data['gender'],
            blood_group=data.get('blood_group') or None,
            contact_number=data.get('contact_number') or None,
            ward_type=data.get('ward_type', 'ICU'),
            bed_number=data.get('bed_number') or None,
            diagnosis=data.get('diagnosis') or None,
            assigned_doctor=assigned_doc,
            assigned_nurse=assigned_nurse,
            created_by=user_id,
            patient_code=data.get('patient_code') or None,
            emergency_contact=data.get('emergency_contact') or None,
            ward_id=ward_id,
            bed_id=bed_id
        )

        # Generate attendant QR token
        qr_info = PatientQRToken.generate_token(patient_id, created_by=user_id)

        # Audit Log
        AuditLog.log(
            action='create_patient',
            user_id=user_id,
            entity_type='patient',
            entity_id=patient_id,
            new_value={'name': data['name'], 'ward_type': data.get('ward_type', 'ICU')},
            ip_address=request.remote_addr,
            description=f"Patient {data['name']} registered and admitted to {data.get('ward_type', 'ICU')}"
        )

        patient = Patient.get_by_id(patient_id)

        if _is_api_request():
            return jsonify({
                'success': True,
                'message': 'Patient registered and admitted successfully',
                'data': {
                    'patient': patient,
                    'qr_token': qr_info['raw_token'],
                    'access_code': qr_info['access_code']
                }
            }), 201

        flash(f"Patient registered! Attendant Access Code: {qr_info['access_code']}", 'success')
        return redirect(url_for('patient.dashboard'))

    except Exception as e:
        if _is_api_request():
            return jsonify({'success': False, 'error': f'Error creating patient: {str(e)}'}), 500
        flash(f'Error adding patient: {str(e)}', 'error')
        return render_template('add_patient.html')


# ─────────────────────────────────────────────────────────────
# 5. PUT /patients/{id} — Update Patient Details
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/<int:patient_id>', methods=['PUT'])
@permission_required('edit_patients')
def update_patient(patient_id):
    """
    Update patient details (demographics, diagnosis, doctor assignment, status).
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    updates = {}

    allowed_fields = [
        'name', 'age', 'gender', 'blood_group', 'contact_number',
        'ward_type', 'bed_number', 'diagnosis', 'status', 'assigned_doctor',
        'discharge_date', 'patient_code', 'emergency_contact', 'ward_id', 'bed_id'
    ]

    for k in allowed_fields:
        if k in data and data[k] is not None:
            if k in ('age', 'assigned_doctor', 'ward_id', 'bed_id') and data[k] != '':
                try:
                    updates[k] = int(data[k])
                except (ValueError, TypeError):
                    pass
            else:
                updates[k] = str(data[k]).strip() if isinstance(data[k], str) else data[k]

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields provided for update'}), 400

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    Patient.update(patient_id, **updates)

    AuditLog.log(
        action='update_patient',
        user_id=user_id,
        entity_type='patient',
        entity_id=patient_id,
        old_value=patient,
        new_value=updates,
        ip_address=request.remote_addr,
        description=f"Updated details for patient {patient.get('name')} (ID: {patient_id})"
    )

    updated_patient = Patient.get_by_id(patient_id)
    return jsonify({
        'success': True,
        'message': f"Patient '{updated_patient.get('name')}' updated successfully",
        'data': updated_patient
    }), 200


# ─────────────────────────────────────────────────────────────
# 6. DELETE /patients/{id} — Discharge Patient
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/<int:patient_id>', methods=['DELETE'])
@permission_required('edit_patients')
def delete_patient(patient_id):
    """
    Discharge patient and release allocated bed.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    user = get_current_authenticated_user()
    user_id = user.id if user else None

    Patient.discharge(patient_id)

    AuditLog.log(
        action='discharge_patient',
        user_id=user_id,
        entity_type='patient',
        entity_id=patient_id,
        ip_address=request.remote_addr,
        description=f"Patient {patient.get('name')} discharged by staff"
    )

    return jsonify({
        'success': True,
        'message': f"Patient '{patient.get('name')}' discharged successfully"
    }), 200


# ─────────────────────────────────────────────────────────────
# 7. GET /patients/{id}/history — Patient Clinical Timeline
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/<int:patient_id>/history', methods=['GET'])
@permission_required('view_patients')
def get_patient_history(patient_id):
    """
    Get comprehensive clinical history timeline: vitals, EWS, transfers, beds, alerts.
    """
    history = Patient.get_history_timeline(patient_id)
    if not history:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    return jsonify({
        'success': True,
        'data': history
    }), 200


# ─────────────────────────────────────────────────────────────
# 8. GET /patients/{id}/transfers — Patient Transfers History
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/<int:patient_id>/transfers', methods=['GET'])
@permission_required('view_patients')
def get_patient_transfers(patient_id):
    """
    Get all transfer requests and history for a patient.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': f'Patient with ID {patient_id} not found'}), 404

    from models.transfer_model import Transfer
    transfers = Transfer.get_by_patient(patient_id)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'patient_name': patient.get('name'),
        'count': len(transfers),
        'data': transfers
    }), 200



# ─────────────────────────────────────────────────────────────
# Web UI Dashboard & Forms
# ─────────────────────────────────────────────────────────────
@patient_bp.route('/dashboard')
@permission_required('view_patients')
def dashboard():
    """Main ICU dashboard showing all admitted patients — redirects to role-specific dashboard."""
    user = get_current_authenticated_user()
    if user:
        if user.role == 'admin':
            return redirect('/Admin/Administrator_dashboard_/Administrator_dashboard_.html')
        elif user.role == 'doctor':
            return redirect('/Doctor/Doctor_dashboard_/Doctor_dashboard_.html')
        elif user.role == 'nurse':
            return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')
        elif user.role == 'attendant':
            return redirect('/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html')
    return redirect('/Doctor/Doctor_dashboard_/Doctor_dashboard_.html')


@patient_bp.route('/table')
@permission_required('view_patients')
def patient_table():
    """View all patients in table format."""
    ward = request.args.get('ward')
    patients = Patient.get_by_ward(ward) if ward else Patient.get_all()
    return render_template('Doctor/Doctor_all_patients/Doctor_all_patients.html', patients=patients, ward=ward)


@patient_bp.route('/add', methods=['GET', 'POST'])
@permission_required('edit_patients')
def add_patient():
    """Web form for registering patient."""
    if request.method == 'POST':
        return create_patient()
    return render_template('Admin/Admin_patient_management/Admin_patient_management.html')


@patient_bp.route('/<int:patient_id>/edit', methods=['POST'])
@permission_required('edit_patients')
def edit_patient_form(patient_id):
    """Web edit patient details."""
    update_patient(patient_id)
    return redirect(url_for('patient.patient_table'))


@patient_bp.route('/<int:patient_id>/discharge', methods=['POST'])
@permission_required('edit_patients')
def discharge_patient_form(patient_id):
    """Web discharge patient."""
    delete_patient(patient_id)
    flash("Patient discharged successfully.", 'success')
    return redirect(url_for('patient.dashboard'))
