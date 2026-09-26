"""
models/patient_model.py — Patient model for CRUD operations, searching, filtering, and clinical history.
"""

import math
from datetime import datetime
from database.db import db
from models.bed_management_model import BedManagement
from modules.scoring_engine import get_risk_level


class Patient:
    """Patient model representing admitted hospital patients."""

    @staticmethod
    def generate_patient_code():
        """Generate unique UHID patient code: UHID-YYYY-XXXXX."""
        now = datetime.now()
        year = now.strftime('%Y')
        prefix = f"UHID-{year}-%"
        res = db.execute_query(
            "SELECT patient_code FROM patients WHERE patient_code LIKE %s ORDER BY patient_id DESC LIMIT 1",
            (prefix,), fetch=True
        )
        max_seq = 0
        if res and res[0].get('patient_code'):
            try:
                max_seq = int(res[0]['patient_code'].split('-')[-1])
            except (ValueError, IndexError):
                max_seq = 0
        count_res = db.execute_query("SELECT COUNT(*) as cnt FROM patients", fetch=True)
        cnt = (count_res[0]['cnt'] if count_res else 0)
        seq = max(max_seq, cnt) + 1
        while True:
            code = f"UHID-{year}-{seq:05d}"
            exists = db.execute_query("SELECT patient_id FROM patients WHERE patient_code = %s", (code,), fetch=True)
            if not exists:
                return code
            seq += 1

    @staticmethod
    def create(name, age, gender, blood_group=None, contact_number=None,
               ward_type='ICU', bed_number=None, diagnosis=None,
               assigned_doctor=None, assigned_nurse=None, created_by=None, patient_code=None,
               emergency_contact=None, ward_id=None, bed_id=None):
        """Register a new patient and optionally allocate bed transactionally."""
        p_code = (patient_code or '').strip()
        if not p_code:
            p_code = Patient.generate_patient_code()

        patient_id = db.execute_query(
            """INSERT INTO patients (name, age, gender, blood_group, contact_number,
               ward_type, bed_number, diagnosis, assigned_doctor, assigned_nurse, created_by,
               patient_code, emergency_contact, ward_id, bed_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (name.strip(), age, gender, blood_group, contact_number,
             ward_type, bed_number, diagnosis, assigned_doctor, assigned_nurse, created_by,
             p_code, emergency_contact, ward_id, bed_id)
        )

        # If bed_id provided, record bed allocation
        if bed_id and ward_id:
            try:
                BedManagement.allocate_bed(patient_id, bed_id, ward_id, allocated_by=created_by)
            except Exception as e:
                print(f"[PATIENT CREATE] Warning bed allocation: {e}")

        return patient_id

    @staticmethod
    def get_by_id(patient_id):
        """Fetch a patient by ID with assigned doctor, nurse, ward, bed details, and full latest monitoring state."""
        from services.decision_service import evaluate

        query = """
        SELECT p.*, u.full_name AS doctor_name, u.email AS doctor_email,
               un.full_name AS nurse_name, un.email AS nurse_email,
               w.name AS ward_name, b.bed_number AS linked_bed_number
        FROM patients p
        LEFT JOIN users u ON p.assigned_doctor = u.user_id
        LEFT JOIN users un ON p.assigned_nurse = un.user_id
        LEFT JOIN wards w ON p.ward_id = w.ward_id
        LEFT JOIN beds b ON p.bed_id = b.bed_id
        WHERE p.patient_id = %s
        """
        result = db.execute_query(query, (patient_id,), fetch=True)
        if not result:
            return None
        
        patient = result[0]
        patient['id'] = patient['patient_id']
        
        # Enrich with latest vitals (4 parameters)
        latest_vitals = db.execute_query(
            "SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC, vital_id DESC LIMIT 1",
            (patient_id,), fetch=True
        )
        if latest_vitals:
            v_rec = latest_vitals[0]
            patient['latest_vitals'] = {
                'vital_id': v_rec.get('vital_id'),
                'heart_rate': v_rec.get('heart_rate'),
                'respiratory_rate': v_rec.get('respiratory_rate'),
                'systolic_bp': v_rec.get('blood_pressure_sys'),
                'temperature': v_rec.get('temperature'),
                'recorded_at': str(v_rec.get('recorded_at', ''))
            }
            patient['ews_score'] = v_rec.get('ews_score', 0) or 0
        else:
            patient['latest_vitals'] = None
            patient['ews_score'] = 0

        # Enrich with latest EWS score breakdown
        latest_ews = db.execute_query(
            "SELECT * FROM ews_scores WHERE patient_id = %s ORDER BY calculated_at DESC, ews_id DESC LIMIT 1",
            (patient_id,), fetch=True
        )
        if latest_ews:
            e_rec = latest_ews[0]
            total_ews = e_rec.get('total_score', patient['ews_score']) or 0
            patient['ews_score'] = total_ews
            patient['ews_risk_level'] = (e_rec.get('risk_level') or get_risk_level(total_ews)).upper()
            patient['scores'] = {
                'respiratory_rate': e_rec.get('rr_score', 0) or 0,
                'heart_rate': e_rec.get('hr_score', 0) or 0,
                'systolic_bp': e_rec.get('bp_score', 0) or 0,
                'temperature': e_rec.get('temp_score', 0) or 0
            }
            patient['latest_ews'] = e_rec
        else:
            patient['scores'] = {'respiratory_rate': 0, 'heart_rate': 0, 'systolic_bp': 0, 'temperature': 0}
            patient['latest_ews'] = None
            patient['ews_risk_level'] = get_risk_level(patient['ews_score']).upper()

        # Decision Service evaluation
        decision = evaluate(patient['ews_score'])
        patient['condition'] = decision['condition']
        patient['recommendation'] = decision['recommendation']

        return patient

    @staticmethod
    def get_filtered(search=None, ward_type=None, status=None, doctor_id=None,
                     nurse_id=None, gender=None, blood_group=None, page=1, limit=20):
        """
        Search, filter, and paginate patients with latest EWS score, condition, and recommendation.
        """
        from services.decision_service import evaluate

        where_clauses = []
        params = []

        if status and status != 'all':
            where_clauses.append("p.status = %s")
            params.append(status)

        if ward_type:
            where_clauses.append("p.ward_type = %s")
            params.append(ward_type)

        if doctor_id:
            where_clauses.append("p.assigned_doctor = %s")
            params.append(int(doctor_id))

        if nurse_id:
            where_clauses.append("p.assigned_nurse = %s")
            params.append(int(nurse_id))

        if gender:
            where_clauses.append("p.gender = %s")
            params.append(gender)

        if blood_group:
            where_clauses.append("p.blood_group = %s")
            params.append(blood_group)

        if search:
            s = f"%{search.strip()}%"
            where_clauses.append("(p.name LIKE %s OR p.patient_code LIKE %s OR p.diagnosis LIKE %s OR p.bed_number LIKE %s)")
            params.extend([s, s, s, s])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Count total
        count_sql = f"SELECT COUNT(*) as total FROM patients p {where_sql}"
        count_res = db.execute_query(count_sql, tuple(params), fetch=True)
        total = count_res[0]['total'] if count_res else 0

        # Pagination calculations
        page = max(1, int(page))
        limit = max(1, min(100, int(limit)))
        offset = (page - 1) * limit
        pages = math.ceil(total / limit) if total > 0 else 1

        # Fetch records with latest vitals join
        query_sql = f"""
            SELECT p.*, u.full_name AS doctor_name, un.full_name AS nurse_name, w.name AS ward_name,
                   v.vital_id, v.ews_score, v.heart_rate, v.respiratory_rate,
                   v.blood_pressure_sys, v.temperature, v.recorded_at AS vitals_recorded_at
            FROM patients p
            LEFT JOIN users u ON p.assigned_doctor = u.user_id
            LEFT JOIN users un ON p.assigned_nurse = un.user_id
            LEFT JOIN wards w ON p.ward_id = w.ward_id
            LEFT JOIN (
                SELECT v1.*
                FROM vitals v1
                INNER JOIN (
                    SELECT patient_id, MAX(vital_id) as max_id
                    FROM vitals GROUP BY patient_id
                ) v2 ON v1.vital_id = v2.max_id
            ) v ON p.patient_id = v.patient_id
            {where_sql}
            ORDER BY p.admission_date DESC, p.patient_id ASC
            LIMIT %s OFFSET %s
        """
        query_params = tuple(params) + (limit, offset)
        patients = db.execute_query(query_sql, query_params, fetch=True) or []

        for pt in patients:
            pt['id'] = pt['patient_id']
            ews = pt.get('ews_score') or 0
            pt['ews_score'] = ews
            pt['ews_risk_level'] = get_risk_level(ews)
            decision = evaluate(ews)
            pt['condition'] = decision['condition']
            pt['recommendation'] = decision['recommendation']
            if pt.get('vital_id'):
                pt['latest_vitals'] = {
                    'heart_rate': pt.get('heart_rate'),
                    'respiratory_rate': pt.get('respiratory_rate'),
                    'systolic_bp': pt.get('blood_pressure_sys'),
                    'temperature': pt.get('temperature'),
                    'recorded_at': str(pt.get('vitals_recorded_at', ''))
                }
            else:
                pt['latest_vitals'] = None

        return {
            'patients': patients,
            'total': total,
            'page': page,
            'limit': limit,
            'pages': pages
        }

    @staticmethod
    def get_all(status='admitted'):
        """Fetch all patients with a given status, enriched with latest vitals and decision."""
        from services.decision_service import evaluate

        query = """
        SELECT p.*, u.full_name AS doctor_name, un.full_name AS nurse_name, w.name AS ward_name,
               v.vital_id, v.ews_score, v.heart_rate, v.respiratory_rate,
               v.blood_pressure_sys, v.temperature, v.recorded_at AS vitals_recorded_at
        FROM patients p
        LEFT JOIN users u ON p.assigned_doctor = u.user_id
        LEFT JOIN users un ON p.assigned_nurse = un.user_id
        LEFT JOIN wards w ON p.ward_id = w.ward_id
        LEFT JOIN (
            SELECT v1.*
            FROM vitals v1
            INNER JOIN (
                SELECT patient_id, MAX(vital_id) as max_id
                FROM vitals GROUP BY patient_id
            ) v2 ON v1.vital_id = v2.max_id
        ) v ON p.patient_id = v.patient_id
        WHERE (%s IS NULL OR p.status = %s)
        ORDER BY p.admission_date DESC, p.patient_id ASC
        """
        status_param = None if status == 'all' else status
        patients = db.execute_query(query, (status_param, status_param), fetch=True) or []
        for pt in patients:
            pt['id'] = pt['patient_id']
            ews = pt.get('ews_score') or 0
            pt['ews_score'] = ews
            pt['ews_risk_level'] = get_risk_level(ews)
            decision = evaluate(ews)
            pt['condition'] = decision['condition']
            pt['recommendation'] = decision['recommendation']
        return patients

    @staticmethod
    def get_by_ward(ward_type):
        """Fetch patients by ward type (ICU/HDU/General)."""
        return db.execute_query(
            """SELECT p.*, u.full_name AS doctor_name, un.full_name AS nurse_name
               FROM patients p
               LEFT JOIN users u ON p.assigned_doctor = u.user_id
               LEFT JOIN users un ON p.assigned_nurse = un.user_id
               WHERE p.ward_type = %s AND p.status = 'admitted' 
               ORDER BY p.bed_number""",
            (ward_type,), fetch=True
        )

    @staticmethod
    def update(patient_id, **kwargs):
        """Update patient details."""
        allowed = ['name', 'age', 'gender', 'blood_group', 'contact_number',
                   'ward_type', 'bed_number', 'diagnosis', 'status', 'assigned_doctor',
                   'assigned_nurse', 'discharge_date', 'patient_code', 'emergency_contact',
                   'ward_id', 'bed_id']
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ', '.join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [patient_id]
        db.execute_query(f"UPDATE patients SET {set_clause} WHERE patient_id = %s", values)

    @staticmethod
    def discharge(patient_id):
        """Discharge a patient and release any allocated bed."""
        with db.transaction() as cursor:
            cursor.execute(
                "UPDATE patients SET status = 'discharged', discharge_date = NOW() WHERE patient_id = %s",
                (patient_id,)
            )
            # Release allocated bed
            cursor.execute(
                """UPDATE bed_management SET status = 'released', released_at = NOW()
                   WHERE patient_id = %s AND status IN ('allocated', 'occupied')""",
                (patient_id,)
            )
            cursor.execute(
                """UPDATE beds b
                   JOIN patients p ON b.bed_id = p.bed_id
                   SET b.status = 'available'
                   WHERE p.patient_id = %s""",
                (patient_id,)
            )

    @staticmethod
    def search(query):
        """Search patients by name, patient code, diagnosis, or bed number, enriched with latest vitals and EWS."""
        from services.decision_service import evaluate
        search_term = f"%{query.strip()}%"
        patients = db.execute_query(
            """SELECT p.*, u.full_name AS doctor_name, w.name AS ward_name,
                      v.vital_id, v.ews_score, v.heart_rate, v.respiratory_rate,
                      v.blood_pressure_sys, v.temperature, v.recorded_at AS vitals_recorded_at
               FROM patients p
               LEFT JOIN users u ON p.assigned_doctor = u.user_id
               LEFT JOIN wards w ON p.ward_id = w.ward_id
               LEFT JOIN (
                   SELECT v1.*
                   FROM vitals v1
                   INNER JOIN (
                       SELECT patient_id, MAX(vital_id) as max_id
                       FROM vitals GROUP BY patient_id
                   ) v2 ON v1.vital_id = v2.max_id
               ) v ON p.patient_id = v.patient_id
               WHERE (p.name LIKE %s OR p.diagnosis LIKE %s OR p.patient_code LIKE %s OR p.bed_number LIKE %s)
               ORDER BY p.status ASC, p.name ASC""",
            (search_term, search_term, search_term, search_term), fetch=True
        ) or []

        for pt in patients:
            pt['id'] = pt['patient_id']
            ews = pt.get('ews_score') or 0
            pt['ews_score'] = ews
            pt['ews_risk_level'] = get_risk_level(ews)
            decision = evaluate(ews)
            pt['condition'] = decision['condition']
            pt['recommendation'] = decision['recommendation']
            if pt.get('vital_id'):
                pt['latest_vitals'] = {
                    'heart_rate': pt.get('heart_rate'),
                    'respiratory_rate': pt.get('respiratory_rate'),
                    'systolic_bp': pt.get('blood_pressure_sys'),
                    'temperature': pt.get('temperature'),
                    'recorded_at': str(pt.get('vitals_recorded_at', ''))
                }
            else:
                pt['latest_vitals'] = None

        return patients

    @staticmethod
    def get_history_timeline(patient_id):
        """Fetch comprehensive patient clinical history."""
        patient = Patient.get_by_id(patient_id)
        if not patient:
            return None

        vitals = db.execute_query(
            "SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT 50",
            (patient_id,), fetch=True
        ) or []

        ews_scores = db.execute_query(
            "SELECT * FROM ews_scores WHERE patient_id = %s ORDER BY calculated_at DESC LIMIT 50",
            (patient_id,), fetch=True
        ) or []

        transfers = db.execute_query(
            """SELECT t.*, u1.full_name AS requester, u2.full_name AS approver
               FROM transfers t
               LEFT JOIN users u1 ON t.requested_by = u1.user_id
               LEFT JOIN users u2 ON t.approved_by = u2.user_id
               WHERE t.patient_id = %s ORDER BY t.created_at DESC""",
            (patient_id,), fetch=True
        ) or []

        bed_history = BedManagement.get_patient_allocation_history(patient_id) or []

        reports = db.execute_query(
            "SELECT * FROM reports WHERE patient_id = %s ORDER BY created_at DESC",
            (patient_id,), fetch=True
        ) or []

        alerts = db.execute_query(
            "SELECT * FROM alerts WHERE patient_id = %s ORDER BY created_at DESC LIMIT 20",
            (patient_id,), fetch=True
        ) or []

        return {
            'patient': patient,
            'vitals_history': vitals,
            'ews_history': ews_scores,
            'transfers': transfers,
            'bed_history': bed_history,
            'reports': reports,
            'alerts': alerts
        }

    @staticmethod
    def count_by_ward():
        """Get patient count per ward."""
        return db.execute_query(
            """SELECT ward_type, COUNT(*) as count
               FROM patients WHERE status = 'admitted'
               GROUP BY ward_type""",
            fetch=True
        )
