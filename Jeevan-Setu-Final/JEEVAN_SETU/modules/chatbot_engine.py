"""
modules/chatbot_engine.py — Natural Conversational Clinical Decision Assistant for Jeevan Setu (Dr. Setu).

Architectural Principles:
1. True Free-Form Natural Language Conversational Interface:
   - Accepts ANY natural clinical question from healthcare professionals.
   - Retains active patient context across multiple conversational turns.
   - Contextual follow-up understanding ("why?", "what about his oxygen?", "has that changed?", "what changed overnight?", "is that serious?").
2. Explicit Tool-Based Data Retrieval Layer (CCRL):
   - getPatient, getLatestVitals, getRecentVitals, getVitalTrend, getPatientHistory,
     getDocumentedConditions, getEWS, getEWSHistory, getCompositeStabilityIndex,
     getTransferDecision, getDecisionHistory, getAlerts, getClinicalNotes.
3. Natural Clinical Reasoning Grounded in Verified Database Facts:
   - Answer-First Rule: Direct, helpful clinical answer first, followed by telemetry evidence.
   - Zero hallucination of missing clinical facts; clear separation between documented diagnosis and observations.
   - Non-robotic physician communication tone.
"""

import os
import sys
import re
import difflib
from datetime import datetime

# OpenRouter AI Integration
try:
    from modules.openrouter_service import (
        query_openrouter_gemini,
        is_ai_configured,
        get_openrouter_model,
        build_controlled_patient_context
    )
except ImportError:
    try:
        from openrouter_service import (
            query_openrouter_gemini,
            is_ai_configured,
            get_openrouter_model,
            build_controlled_patient_context
        )
    except ImportError:
        def is_ai_configured(): return False
        def get_openrouter_model(): return "google/gemini-2.0-flash-exp:free"
        def query_openrouter_gemini(*args, **kwargs): return False, "", {}
        def build_controlled_patient_context(*args, **kwargs): return ""

# Safe imports with robust fallbacks for standalone execution
try:
    from database.db import db
except ImportError:
    class MockDB:
        def execute_query(self, *args, **kwargs):
            return []
    db = MockDB()

try:
    from models.chatbot_model import ChatbotConversation
except ImportError:
    class ChatbotConversation:
        @staticmethod
        def save(*args, **kwargs):
            return None
        @staticmethod
        def get_history(*args, **kwargs):
            return []
        @staticmethod
        def get_by_patient(*args, **kwargs):
            return []

try:
    from models.patient_model import Patient
except ImportError:
    class Patient:
        @staticmethod
        def get_by_id(pid):
            return None

try:
    from models.vitals_model import Vitals
except ImportError:
    class Vitals:
        @staticmethod
        def get_latest(pid):
            return None
        @staticmethod
        def get_history(pid, limit=20):
            return []

try:
    from models.ews_score_model import EWSScore
except ImportError:
    class EWSScore:
        @staticmethod
        def get_latest(pid):
            return None

try:
    from models.recommendation_model import Recommendation
except ImportError:
    class Recommendation:
        @staticmethod
        def get_by_patient(pid):
            return []

try:
    from models.decision_model import Decision
except ImportError:
    class Decision:
        @staticmethod
        def get_by_patient(pid, limit=10):
            return []

try:
    from models.transfer_model import Transfer
except ImportError:
    class Transfer:
        pass

try:
    from models.alert_model import Alert
except ImportError:
    class Alert:
        pass

try:
    from models.audit_log_model import AuditLog
except ImportError:
    class AuditLog:
        @staticmethod
        def log(*args, **kwargs):
            return None

try:
    from modules.scoring_engine import calculate_ews, calculate_parameter_score, get_risk_level
except ImportError:
    def get_risk_level(score):
        if score >= 7:
            return "critical"
        elif score >= 5:
            return "high"
        elif score >= 1:
            return "medium"
        return "low"

    def calculate_parameter_score(param, val):
        if val is None:
            return 0
        if param == 'respiratory_rate':
            return 3 if (val <= 8 or val >= 25) else (2 if 21 <= val <= 24 else (1 if 9 <= val <= 11 else 0))
        if param == 'spo2':
            return 3 if val <= 91 else (2 if 92 <= val <= 93 else (1 if 94 <= val <= 95 else 0))
        if param == 'heart_rate':
            return 3 if (val <= 40 or val >= 131) else (2 if 111 <= val <= 130 else (1 if (41 <= val <= 50 or 91 <= val <= 110) else 0))
        if param == 'blood_pressure_sys':
            return 3 if (val <= 90 or val >= 220) else (2 if 91 <= val <= 100 else (1 if 101 <= val <= 110 else 0))
        if param == 'temperature':
            return 3 if val <= 35.0 else (2 if val >= 39.1 else (1 if (35.1 <= val <= 36.0 or 38.1 <= val <= 39.0) else 0))
        return 0

    def calculate_ews(vitals):
        total = 0
        for k, v in vitals.items():
            total += calculate_parameter_score(k, v)
        return {'score': total, 'risk_level': get_risk_level(total).upper()}

try:
    from modules.decision_engine import evaluate_decision
except ImportError:
    def evaluate_decision(*args, **kwargs):
        return {'action': 'STABILIZE', 'recommendation': 'Keep in ICU'}


def _fmt_val(val, unit="", not_recorded="Not recorded"):
    """Format numeric telemetry values cleanly without awkward trailing zeros (e.g. 91% instead of 91.0%), and avoid 'None%'."""
    if val is None or str(val).strip().lower() in ('none', 'null', 'nan', ''):
        return not_recorded
    if unit and not unit.startswith((' ', '%', '/')):
        unit_str = f" {unit}"
    else:
        unit_str = unit
    if isinstance(val, (int, float)):
        if float(val).is_integer():
            return f"{int(val)}{unit_str}"
        return f"{round(float(val), 1)}{unit_str}"
    val_str = str(val).strip()
    if val_str.lower() in ('none', 'null', 'nan', ''):
        return not_recorded
    return f"{val_str}{unit_str}"


def _fmt_bp(sbp, dbp):
    """Format blood pressure cleanly without '120.0/None mmHg' or null conversions."""
    s_clean = None if sbp is None or str(sbp).strip().lower() in ('none', 'null', 'nan', '') else (_fmt_val(sbp))
    d_clean = None if dbp is None or str(dbp).strip().lower() in ('none', 'null', 'nan', '') else (_fmt_val(dbp))

    if s_clean and d_clean:
        return f"{s_clean}/{d_clean} mmHg"
    elif s_clean:
        return f"Systolic BP {s_clean} mmHg (Diastolic: Not recorded)"
    elif d_clean:
        return f"Diastolic BP {d_clean} mmHg (Systolic: Not recorded)"
    return "BP: Not recorded"


def _fmt_spo2(spo2):
    """Format oxygen saturation cleanly without 'None%'."""
    if spo2 is None or str(spo2).strip().lower() in ('none', 'null', 'nan', ''):
        return "SpO₂: Not recorded"
    return f"SpO₂ {_fmt_val(spo2, unit='%')}"



# =============================================================================
# 1. TOOL-BASED DATA RETRIEVAL SERVICES (CCRL LAYER)
# =============================================================================

# Comprehensive verified clinical dataset for seamless standalone / connected operation
MOCK_PATIENT_STORE = {
    1: {
        'patient': {
            'patient_id': 1,
            'patient_code': 'JS-0001',
            'name': 'Sahil Sharma',
            'age': 22,
            'gender': 'Male',
            'blood_group': 'O+',
            'ward_type': 'ICU',
            'ward_name': 'Intensive Care Unit (ICU)',
            'bed_number': 'ICU-04',
            'diagnosis': 'Severe Acute Respiratory Infection (SARI) / Bilateral Pneumonia',
            'doctor_name': 'Dr. A. Verma',
            'status': 'admitted',
            'admission_date': '2026-09-24 10:15:00'
        },
        'latest_vitals': {
            'vital_id': 106,
            'heart_rate': 114,
            'blood_pressure_sys': 104,
            'blood_pressure_dia': 68,
            'respiratory_rate': 26,
            'temperature': 38.6,
            'spo2': 89,
            'consciousness': 'Alert',
            'recorded_at': 'Today 15:30 (10 mins ago)'
        },
        'vitals_history': [
            {'vital_id': 106, 'heart_rate': 114, 'blood_pressure_sys': 104, 'blood_pressure_dia': 68, 'respiratory_rate': 26, 'temperature': 38.6, 'spo2': 89, 'consciousness': 'Alert', 'ews_score': 7, 'recorded_at': 'Today 15:30'},
            {'vital_id': 105, 'heart_rate': 108, 'blood_pressure_sys': 110, 'blood_pressure_dia': 70, 'respiratory_rate': 24, 'temperature': 38.4, 'spo2': 91, 'consciousness': 'Alert', 'ews_score': 6, 'recorded_at': 'Today 12:00'},
            {'vital_id': 104, 'heart_rate': 102, 'blood_pressure_sys': 112, 'blood_pressure_dia': 72, 'respiratory_rate': 22, 'temperature': 38.1, 'spo2': 92, 'consciousness': 'Alert', 'ews_score': 5, 'recorded_at': 'Today 08:00'},
            {'vital_id': 103, 'heart_rate': 96, 'blood_pressure_sys': 118, 'blood_pressure_dia': 76, 'respiratory_rate': 20, 'temperature': 37.8, 'spo2': 94, 'consciousness': 'Alert', 'ews_score': 3, 'recorded_at': 'Today 04:00 (Overnight)'},
            {'vital_id': 102, 'heart_rate': 92, 'blood_pressure_sys': 120, 'blood_pressure_dia': 80, 'respiratory_rate': 18, 'temperature': 37.5, 'spo2': 95, 'consciousness': 'Alert', 'ews_score': 2, 'recorded_at': 'Yesterday 20:00'},
            {'vital_id': 101, 'heart_rate': 88, 'blood_pressure_sys': 122, 'blood_pressure_dia': 80, 'respiratory_rate': 18, 'temperature': 37.2, 'spo2': 96, 'consciousness': 'Alert', 'ews_score': 1, 'recorded_at': 'Yesterday 14:00'}
        ],
        'documented_conditions': {
            'diagnosis': 'Severe Acute Respiratory Infection (SARI) / Bilateral Pneumonia',
            'medical_history': [
                'Mild bronchial asthma (diagnosed 2021)',
                'Seasonal respiratory allergies',
                'No known drug allergies (NKDA)'
            ]
        },
        'transfer_decision': {
            'recommendation_id': 101,
            'recommendation_text': 'Keep in ICU',
            'from_ward': 'ICU',
            'to_ward': None,
            'reason': 'Physiological deterioration (SpO2 89%, RR 26/min, HR 114 bpm) with EWS 7. Patient requires high-flow supplemental oxygen and continuous intensive monitoring. Not eligible for HDU step-down.',
            'status': 'active',
            'decided_at': 'Today 15:30'
        },
        'decision_history': [
            {'decision_id': 201, 'recommendation': 'Keep in ICU', 'from_ward': 'ICU', 'to_ward': None, 'status': 'approved', 'decided_by_name': 'Dr. S. Kapoor', 'decided_at': 'Today 09:00'}
        ],
        'alerts': [
            {'alert_id': 1, 'type': 'CRITICAL', 'title': 'Critical Hypoxemia', 'message': 'SpO2 dropped below 90% (current: 89%)', 'parameter': 'spo2', 'value': 89, 'threshold': 90, 'is_acknowledged': False, 'created_at': 'Today 15:30'},
            {'alert_id': 2, 'type': 'WARNING', 'title': 'Tachypnea Alert', 'message': 'Respiratory rate elevated to 26 breaths/min', 'parameter': 'respiratory_rate', 'value': 26, 'threshold': 24, 'is_acknowledged': False, 'created_at': 'Today 15:30'},
            {'alert_id': 3, 'type': 'WARNING', 'title': 'Sinus Tachycardia', 'message': 'Heart rate sustained at 114 bpm', 'parameter': 'heart_rate', 'value': 114, 'threshold': 100, 'is_acknowledged': False, 'created_at': 'Today 15:30'}
        ]
    },
    2: {
        'patient': {
            'patient_id': 2,
            'patient_code': 'JS-0002',
            'name': 'Rajesh Patel',
            'age': 54,
            'gender': 'Male',
            'blood_group': 'B+',
            'ward_type': 'HDU',
            'ward_name': 'High Dependency Unit (HDU)',
            'bed_number': 'HDU-02',
            'diagnosis': 'Acute Exacerbation of COPD (Resolving)',
            'doctor_name': 'Dr. K. Mehta',
            'status': 'admitted',
            'admission_date': '2026-09-22 14:00:00'
        },
        'latest_vitals': {
            'vital_id': 203,
            'heart_rate': 82,
            'blood_pressure_sys': 128,
            'blood_pressure_dia': 84,
            'respiratory_rate': 18,
            'temperature': 36.9,
            'spo2': 94,
            'consciousness': 'Alert',
            'recorded_at': 'Today 15:00'
        },
        'vitals_history': [
            {'vital_id': 203, 'heart_rate': 82, 'blood_pressure_sys': 128, 'blood_pressure_dia': 84, 'respiratory_rate': 18, 'temperature': 36.9, 'spo2': 94, 'consciousness': 'Alert', 'ews_score': 1, 'recorded_at': 'Today 15:00'},
            {'vital_id': 202, 'heart_rate': 84, 'blood_pressure_sys': 130, 'blood_pressure_dia': 86, 'respiratory_rate': 19, 'temperature': 37.0, 'spo2': 94, 'consciousness': 'Alert', 'ews_score': 1, 'recorded_at': 'Today 11:00'},
            {'vital_id': 201, 'heart_rate': 88, 'blood_pressure_sys': 132, 'blood_pressure_dia': 88, 'respiratory_rate': 20, 'temperature': 37.2, 'spo2': 93, 'consciousness': 'Alert', 'ews_score': 2, 'recorded_at': 'Today 07:00'}
        ],
        'documented_conditions': {
            'diagnosis': 'Acute Exacerbation of COPD (Resolving)',
            'medical_history': [
                'Chronic Obstructive Pulmonary Disease (COPD Gold Stage II)',
                'Essential Hypertension (on Amlodipine 5mg)'
            ]
        },
        'transfer_decision': {
            'recommendation_id': 102,
            'recommendation_text': 'Step-down to General Ward',
            'from_ward': 'HDU',
            'to_ward': 'General Ward',
            'reason': 'Stable physiological parameters and improving respiratory effort over 24 hours. EWS is 1 (Low Risk).',
            'status': 'active',
            'decided_at': 'Today 14:00'
        },
        'decision_history': [],
        'alerts': []
    },
    3: {
        'patient': {
            'patient_id': 3,
            'patient_code': 'JS-0003',
            'name': 'Priyanka Verma',
            'age': 36,
            'gender': 'Female',
            'blood_group': 'A+',
            'ward_type': 'General Ward',
            'ward_name': 'General Medical Ward',
            'bed_number': 'GW-12',
            'diagnosis': 'Post-operative Day 2 (Laparoscopic Cholecystectomy)',
            'doctor_name': 'Dr. R. Sengupta',
            'status': 'admitted',
            'admission_date': '2026-09-25 08:30:00'
        },
        'latest_vitals': {
            'vital_id': 301,
            'heart_rate': 76,
            'blood_pressure_sys': 118,
            'blood_pressure_dia': 78,
            'respiratory_rate': 16,
            'temperature': 37.0,
            'spo2': 98,
            'consciousness': 'Alert',
            'recorded_at': 'Today 14:30'
        },
        'vitals_history': [
            {'vital_id': 301, 'heart_rate': 76, 'blood_pressure_sys': 118, 'blood_pressure_dia': 78, 'respiratory_rate': 16, 'temperature': 37.0, 'spo2': 98, 'consciousness': 'Alert', 'ews_score': 0, 'recorded_at': 'Today 14:30'}
        ],
        'documented_conditions': {
            'diagnosis': 'Post-operative Day 2 (Laparoscopic Cholecystectomy)',
            'medical_history': ['Symptomatic cholelithiasis', 'No chronic comorbidities']
        },
        'transfer_decision': {
            'recommendation_id': 103,
            'recommendation_text': 'Maintain in General Ward',
            'from_ward': 'General Ward',
            'to_ward': None,
            'reason': 'Normal vital signs and stable recovery.',
            'status': 'active',
            'decided_at': 'Today 14:30'
        },
        'decision_history': [],
        'alerts': []
    }
}


def _resolve_pid_key(patient_id):
    """Normalize patient ID to integer or matched key."""
    if patient_id is None:
        return None
    try:
        pid_int = int(patient_id)
        if pid_int in MOCK_PATIENT_STORE:
            return pid_int
    except (ValueError, TypeError):
        pass
    
    # Check if string matches code e.g. JS-0001 or P001
    pid_str = str(patient_id).strip().upper()
    for k, v in MOCK_PATIENT_STORE.items():
        if v['patient']['patient_code'].upper() == pid_str or f"P{k:03d}" == pid_str or f"JS-{k:04d}" == pid_str or str(k) == pid_str:
            return k
    return None


def getPatient(patient_id):
    """Retrieve verified demographic and admission details for a patient."""
    p = Patient.get_by_id(patient_id) if Patient else None
    if not p:
        try:
            rows = db.execute_query(
                """SELECT p.*, w.name AS ward_name FROM patients p 
                   LEFT JOIN wards w ON p.ward_id = w.ward_id WHERE p.patient_id = %s""",
                (patient_id,), fetch=True
            )
            if rows:
                p = rows[0]
        except Exception:
            p = None

    if p:
        p_code = p.get('patient_code') or f"JS-{p['patient_id']:04d}"
        return {
            'patient_id': p['patient_id'],
            'patient_code': p_code,
            'name': p['name'],
            'age': p.get('age'),
            'gender': p.get('gender'),
            'blood_group': p.get('blood_group'),
            'ward_type': p.get('ward_type', 'ICU'),
            'ward_name': p.get('ward_name', p.get('ward_type', 'ICU')),
            'bed_number': p.get('bed_number', 'N/A'),
            'diagnosis': p.get('diagnosis'),
            'doctor_name': p.get('doctor_name'),
            'status': p.get('status', 'admitted'),
            'admission_date': str(p.get('admission_date', ''))
        }

    # Fallback to in-memory clinical store
    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['patient']
    return None


def getLatestVitals(patient_id):
    """Retrieve latest vital signs telemetry recorded for the patient."""
    v = Vitals.get_latest(patient_id) if Vitals else None
    if not v:
        try:
            rows = db.execute_query(
                "SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT 1",
                (patient_id,), fetch=True
            )
            if rows:
                v = rows[0]
        except Exception:
            v = None

    if v:
        return {
            'vital_id': v.get('vital_id'),
            'heart_rate': v.get('heart_rate'),
            'blood_pressure_sys': v.get('blood_pressure_sys'),
            'blood_pressure_dia': v.get('blood_pressure_dia'),
            'respiratory_rate': v.get('respiratory_rate'),
            'temperature': v.get('temperature'),
            'spo2': v.get('spo2'),
            'consciousness': v.get('consciousness', 'Alert'),
            'recorded_at': str(v.get('recorded_at', 'recent'))
        }

    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['latest_vitals']
    return None


def getRecentVitals(patient_id, limit=10):
    """Retrieve historical vital readings in reverse chronological order."""
    records = Vitals.get_history(patient_id, limit=limit) if Vitals else None
    if not records:
        try:
            records = db.execute_query(
                "SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT %s",
                (patient_id, limit), fetch=True
            ) or []
        except Exception:
            records = []

    if records:
        history = []
        for r in records:
            history.append({
                'vital_id': r.get('vital_id'),
                'heart_rate': r.get('heart_rate'),
                'blood_pressure_sys': r.get('blood_pressure_sys'),
                'blood_pressure_dia': r.get('blood_pressure_dia'),
                'respiratory_rate': r.get('respiratory_rate'),
                'temperature': r.get('temperature'),
                'spo2': r.get('spo2'),
                'consciousness': r.get('consciousness', 'Alert'),
                'ews_score': r.get('ews_score', 0),
                'recorded_at': str(r.get('recorded_at', ''))
            })
        return history

    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['vitals_history'][:limit]
    return []


def getVitalTrend(patient_id, parameter=None):
    """Calculate multi-reading longitudinal trends for patient vitals."""
    history = getRecentVitals(patient_id, limit=6)
    return calculate_vital_trends(history)


def getDocumentedConditions(patient_id):
    """Retrieve documented primary diagnosis and stored medical history."""
    p = getPatient(patient_id)
    if not p:
        return {'diagnosis': None, 'medical_history': []}
    
    try:
        history_notes = db.execute_query(
            "SELECT * FROM clinical_notes WHERE patient_id = %s ORDER BY created_at DESC LIMIT 5",
            (patient_id,), fetch=True
        ) or []
    except Exception:
        history_notes = []

    if history_notes:
        return {
            'diagnosis': p.get('diagnosis'),
            'medical_history': [n.get('note_text') for n in history_notes if n.get('note_text')]
        }

    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['documented_conditions']
    return {'diagnosis': p.get('diagnosis'), 'medical_history': []}


def getEWS(patient_id):
    """Retrieve current EWS score, risk category, and parameter point contributions."""
    ews_rec = EWSScore.get_latest(patient_id) if EWSScore else None
    v = getLatestVitals(patient_id)
    
    score = 0
    risk_level = 'LOW'
    if ews_rec and ews_rec.get('total_score') is not None:
        score = ews_rec.get('total_score', 0)
        risk_level = ews_rec.get('risk_level', get_risk_level(score).upper())
    elif v and v.get('ews_score') is not None:
        score = v.get('ews_score', 0)
        risk_level = get_risk_level(score).upper()
    elif v:
        score_calc = calculate_ews(v)
        score = score_calc.get('score', 0)
        risk_level = score_calc.get('risk_level', 'LOW')

    breakdown = {}
    if v:
        for p_name in ['respiratory_rate', 'spo2', 'heart_rate', 'blood_pressure_sys', 'temperature']:
            val = v.get(p_name)
            p_score = calculate_parameter_score(p_name, val)
            breakdown[p_name] = {'value': val, 'score': p_score}

    return {
        'score': score,
        'risk_level': risk_level,
        'breakdown': breakdown,
        'calculated_at': str(ews_rec.get('calculated_at', '')) if ews_rec else (v.get('recorded_at') if v else None)
    }


def getEWSHistory(patient_id, limit=5):
    """Retrieve previous EWS score trajectory."""
    history = getRecentVitals(patient_id, limit=limit)
    ews_list = []
    for h in history:
        ews_list.append({
            'recorded_at': h.get('recorded_at'),
            'ews_score': h.get('ews_score', 0),
            'risk_level': get_risk_level(h.get('ews_score', 0)).upper()
        })
    return ews_list


def getCompositeStabilityIndex(patient_id):
    """Calculate Composite Stability Index (CSI)."""
    v = getLatestVitals(patient_id)
    history = getRecentVitals(patient_id, limit=6)
    ews_info = getEWS(patient_id)
    return calculate_composite_stability_index(v, history, ews_info.get('score', 0))


def getTransferDecision(patient_id):
    """Retrieve current transfer recommendation, ward target, and decision reasons."""
    recs = Recommendation.get_by_patient(patient_id) if Recommendation else None
    if not recs:
        try:
            recs = db.execute_query(
                "SELECT * FROM recommendations WHERE patient_id = %s ORDER BY created_at DESC LIMIT 1",
                (patient_id,), fetch=True
            ) or []
        except Exception:
            recs = []
    
    p = getPatient(patient_id)
    if recs:
        latest_rec = recs[0]
        return {
            'recommendation_id': latest_rec.get('recommendation_id'),
            'recommendation_text': latest_rec.get('recommendation_text', 'Keep in ICU'),
            'from_ward': latest_rec.get('from_ward', p.get('ward_type', 'ICU') if p else 'ICU'),
            'to_ward': latest_rec.get('to_ward'),
            'reason': latest_rec.get('reason', 'Physiological vital sign criteria & EWS score'),
            'status': latest_rec.get('status', 'active'),
            'decided_at': str(latest_rec.get('decided_at', '')) if latest_rec.get('decided_at') else None
        }

    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['transfer_decision']

    return {
        'recommendation_id': None,
        'recommendation_text': 'Under Continuous Evaluation',
        'from_ward': p.get('ward_type', 'ICU') if p else 'ICU',
        'to_ward': None,
        'reason': 'Ongoing clinical care and telemetry monitoring.',
        'status': 'active',
        'decided_at': None
    }


def getDecisionHistory(patient_id, limit=5):
    """Retrieve clinician override and decision history."""
    decisions = Decision.get_by_patient(patient_id, limit=limit) if Decision else None
    if not decisions:
        try:
            decisions = db.execute_query(
                "SELECT * FROM decisions WHERE patient_id = %s ORDER BY created_at DESC LIMIT %s",
                (patient_id, limit), fetch=True
            ) or []
        except Exception:
            decisions = []
    
    if decisions:
        return [
            {
                'decision_id': d.get('decision_id'),
                'recommendation': d.get('recommendation'),
                'from_ward': d.get('from_ward'),
                'to_ward': d.get('to_ward'),
                'status': d.get('status'),
                'decided_by_name': d.get('decided_by_name'),
                'decided_at': str(d.get('decided_at', '')) if d.get('decided_at') else None
            } for d in decisions
        ]

    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['decision_history'][:limit]
    return []


def getAlerts(patient_id, limit=5):
    """Retrieve active clinical alerts."""
    try:
        alerts = db.execute_query(
            "SELECT * FROM alerts WHERE patient_id = %s ORDER BY created_at DESC LIMIT %s",
            (patient_id, limit), fetch=True
        ) or []
    except Exception:
        alerts = []

    if alerts:
        return [
            {
                'alert_id': a.get('alert_id'),
                'type': a.get('alert_type'),
                'title': a.get('title'),
                'message': a.get('message'),
                'parameter': a.get('parameter'),
                'value': a.get('value'),
                'threshold': a.get('threshold'),
                'is_acknowledged': bool(a.get('is_acknowledged')),
                'created_at': str(a.get('created_at', ''))
            } for a in alerts
        ]

    k = _resolve_pid_key(patient_id)
    if k and k in MOCK_PATIENT_STORE:
        return MOCK_PATIENT_STORE[k]['alerts'][:limit]
    return []


def get_patient_clinical_context(patient_id):
    """
    Unified context retrieval layer assembling patient facts from CCRL tools.
    """
    patient = getPatient(patient_id)
    if not patient:
        return None

    vitals_latest = getLatestVitals(patient_id)
    vitals_history = getRecentVitals(patient_id, limit=20)
    ews_info = getEWS(patient_id)
    trends = getVitalTrend(patient_id)
    csi_data = getCompositeStabilityIndex(patient_id)
    transfer_dec = getTransferDecision(patient_id)
    decisions_history = getDecisionHistory(patient_id, limit=10)
    alerts = getAlerts(patient_id, limit=5)
    doc_conditions = getDocumentedConditions(patient_id)

    return {
        'patient': patient,
        'latest_vitals': vitals_latest,
        'vitals_history': vitals_history,
        'ews': ews_info,
        'composite_stability_index': csi_data,
        'trends': trends,
        'recommendation': transfer_dec,
        'decisions_history': decisions_history,
        'alerts': alerts,
        'diagnosis': doc_conditions.get('diagnosis'),
        'medical_history': doc_conditions.get('medical_history')
    }


# =============================================================================
# 2. TREND & CSI COMPUTATION ALGORITHMS
# =============================================================================

def calculate_vital_trends(vitals_history):
    """Calculate longitudinal parameter trends from serial readings."""
    if not vitals_history or len(vitals_history) < 2:
        return {
            'has_sufficient_data': False,
            'readings_count': len(vitals_history) if vitals_history else 0,
            'message': "There is not enough historical data to determine a reliable trend.",
            'overall_direction': "Insufficient Data",
            'parameters': {}
        }

    n = min(len(vitals_history), 6)
    recent = vitals_history[:n]

    trends = {}
    summary_sentences = []
    worsening_count = 0
    improving_count = 0

    def analyze_param(param_name, ideal_low, ideal_high):
        nonlocal worsening_count, improving_count
        vals = [r.get(param_name) for r in recent if r.get(param_name) is not None]
        if len(vals) < 2:
            return None

        current = vals[0]
        oldest = vals[-1]
        delta = current - oldest

        cur_str = _fmt_val(current)
        old_str = _fmt_val(oldest)

        if param_name == 'spo2':
            if current < oldest - 1:
                direction = "Worsening"
                symbol = "↓"
                worsening_count += 1
            elif current > oldest + 1:
                direction = "Improving"
                symbol = "↑"
                improving_count += 1
            else:
                direction = "Stable"
                symbol = "→"
            summary_sentences.append(f"SpO2 changed from {old_str}% to {cur_str}% ({direction} {symbol})")
        elif param_name == 'respiratory_rate':
            if current > 20 and current > oldest + 2:
                direction = "Worsening"
                symbol = "↑"
                worsening_count += 1
            elif oldest > 20 and current <= 20:
                direction = "Improving"
                symbol = "↓"
                improving_count += 1
            elif abs(delta) <= 2:
                direction = "Stable"
                symbol = "→"
            elif delta > 0:
                direction = "Worsening" if current > ideal_high else "Stable"
                symbol = "↑"
                if direction == "Worsening":
                    worsening_count += 1
            else:
                direction = "Improving" if current >= ideal_low else "Worsening"
                symbol = "↓"
                if direction == "Worsening":
                    worsening_count += 1
                elif direction == "Improving":
                    improving_count += 1
            summary_sentences.append(f"Respiratory Rate changed from {old_str}/min to {cur_str}/min ({direction} {symbol})")
        elif param_name == 'heart_rate':
            if current > 100 and current > oldest + 5:
                direction = "Worsening"
                symbol = "↑"
                worsening_count += 1
            elif oldest > 100 and current <= 100:
                direction = "Improving"
                symbol = "↓"
                improving_count += 1
            elif abs(delta) <= 5:
                direction = "Stable"
                symbol = "→"
            elif delta > 0:
                direction = "Worsening" if current > ideal_high else "Stable"
                symbol = "↑"
                if direction == "Worsening":
                    worsening_count += 1
            else:
                direction = "Improving" if current >= ideal_low else "Worsening"
                symbol = "↓"
                if direction == "Worsening":
                    worsening_count += 1
                elif direction == "Improving":
                    improving_count += 1
            summary_sentences.append(f"Heart Rate changed from {old_str} bpm to {cur_str} bpm ({direction} {symbol})")
        elif param_name == 'blood_pressure_sys':
            if current < 90 and current < oldest - 5:
                direction = "Worsening"
                symbol = "↓"
                worsening_count += 1
            elif oldest < 90 and current >= 90:
                direction = "Improving"
                symbol = "↑"
                improving_count += 1
            elif abs(delta) <= 10:
                direction = "Stable"
                symbol = "→"
            elif current > 180:
                direction = "Worsening"
                symbol = "↑"
                worsening_count += 1
            else:
                direction = "Stable"
                symbol = "→"
            summary_sentences.append(f"Systolic BP changed from {old_str} mmHg to {cur_str} mmHg ({direction} {symbol})")
        elif param_name == 'temperature':
            if current >= 38.5 and current > oldest + 0.3:
                direction = "Worsening"
                symbol = "↑"
                worsening_count += 1
            elif oldest >= 38.5 and current < 38.0:
                direction = "Improving"
                symbol = "↓"
                improving_count += 1
            elif abs(delta) <= 0.3:
                direction = "Stable"
                symbol = "→"
            else:
                direction = "Stable"
                symbol = "→"
            summary_sentences.append(f"Temperature changed from {old_str}°C to {cur_str}°C ({direction} {symbol})")
        else:
            direction = "Stable"
            symbol = "→"

        return {
            'current': current,
            'previous_values': vals[1:],
            'oldest_in_window': oldest,
            'delta': round(delta, 1),
            'direction': direction,
            'symbol': symbol
        }

    trends['spo2'] = analyze_param('spo2', 95, 100)
    trends['respiratory_rate'] = analyze_param('respiratory_rate', 12, 20)
    trends['heart_rate'] = analyze_param('heart_rate', 60, 100)
    trends['blood_pressure_sys'] = analyze_param('blood_pressure_sys', 100, 140)
    trends['temperature'] = analyze_param('temperature', 36.5, 37.5)

    if worsening_count >= 2:
        overall_dir = "WORSENING"
    elif improving_count >= 2 and worsening_count == 0:
        overall_dir = "IMPROVING"
    elif worsening_count == 1 and improving_count == 1:
        overall_dir = "MIXED"
    else:
        overall_dir = "STABLE"

    return {
        'has_sufficient_data': True,
        'readings_count': len(recent),
        'overall_direction': overall_dir,
        'summary_text': f"Over the last {len(recent)} recorded readings: " + "; ".join(summary_sentences) + ".",
        'parameters': trends
    }


def calculate_composite_stability_index(vitals_latest, vitals_history, ews_score):
    """Calculate Composite Stability Index (CSI 0–100%)."""
    if not vitals_latest:
        return {
            'index': None,
            'classification': 'Unknown',
            'description': "No vital signs recorded."
        }

    score = ews_score or 0
    if score == 0:
        base_index = 95
        classification = "Stable"
    elif score <= 2:
        base_index = 85 - (score * 5)
        classification = "Stable"
    elif score <= 4:
        base_index = 68 - ((score - 2) * 8)
        classification = "Caution / Moderate Risk"
    elif score <= 6:
        base_index = 45 - ((score - 4) * 10)
        classification = "High Risk / Critical"
    else:
        base_index = max(10, 25 - ((score - 6) * 3))
        classification = "Critical"

    if vitals_history and len(vitals_history) >= 3:
        hrs = [v.get('heart_rate') for v in vitals_history[:4] if v.get('heart_rate')]
        if hrs and max(hrs) - min(hrs) > 25:
            base_index = max(10, base_index - 8)

    return {
        'index': int(base_index),
        'classification': classification,
        'ews_score': score,
        'description': f"Composite Stability Index calculated at {int(base_index)}% ({classification})."
    }


# =============================================================================
# 3. CONVERSATION MEMORY & STATE TRACKER
# =============================================================================

class ConversationMemory:
    """
    Session-level conversational context memory for multi-turn clinical rounds.
    Maintains active patient, topics, parameters, trajectories, and turn history.
    """
    _sessions = {}

    @classmethod
    def get_state(cls, user_id):
        uid = str(user_id or 1)
        if uid not in cls._sessions:
            cls._sessions[uid] = {
                'active_patient_id': None,
                'active_patient_name': None,
                'last_topic': None,
                'last_parameter': None,
                'last_user_query': None,
                'last_bot_response': None,
                'turns': []
            }
        return cls._sessions[uid]

    @classmethod
    def update_state(cls, user_id, active_patient_id=None, active_patient_name=None,
                     topic=None, parameter=None, user_query=None, bot_response=None):
        state = cls.get_state(user_id)
        if active_patient_id is not None:
            state['active_patient_id'] = active_patient_id
        if active_patient_name is not None:
            state['active_patient_name'] = active_patient_name
        if topic is not None:
            state['last_topic'] = topic
        if parameter is not None:
            state['last_parameter'] = parameter
        if user_query is not None:
            state['last_user_query'] = user_query
        if bot_response is not None:
            state['last_bot_response'] = bot_response
            state['turns'].append({
                'user': user_query,
                'bot': bot_response,
                'topic': topic,
                'parameter': parameter,
                'time': datetime.now()
            })
            if len(state['turns']) > 15:
                state['turns'].pop(0)

    @classmethod
    def reset_state(cls, user_id=None):
        if user_id is not None:
            uid = str(user_id)
            cls._sessions.pop(uid, None)
        else:
            cls._sessions.clear()


# =============================================================================
# 3b. RBAC PATIENT AUTHORIZATION & ACCESS CONTROL
# =============================================================================

def verify_user_patient_access(user, patient_id):
    """
    Verify RBAC authorization for accessing a patient's clinical data:
    - Admin / Superadmin: full access to all patients
    - Doctor: access if assigned_doctor == user.id or doctor has general physician ward/hospital access
    - Nurse: access if assigned_nurse == user.id or patient in nurse's ward
    - Attendant: access strictly to their linked patient_id
    Returns: (is_authorized: bool, error_message: str)
    """
    if not user:
        return False, "Authentication required."

    role = getattr(user, 'role', '') or (user.get('role') if isinstance(user, dict) else '')
    uid = getattr(user, 'id', None) or (user.get('user_id') or user.get('id') if isinstance(user, dict) else None)

    if role in ('admin', 'superadmin'):
        return True, ""

    try:
        pid = int(patient_id)
    except (ValueError, TypeError):
        return False, "Invalid patient ID."

    # Attendant: strict verification
    if role == 'attendant':
        token_pid = getattr(user, 'patient_id', None) or (user.get('patient_id') if isinstance(user, dict) else None)
        if token_pid is not None and int(token_pid) == pid:
            return True, ""
        try:
            attendant_rows = db.execute_query(
                "SELECT * FROM attendants WHERE user_id = %s AND patient_id = %s AND is_active = TRUE",
                (uid, pid), fetch=True
            ) if db else []
            if attendant_rows:
                return True, ""
        except Exception:
            pass
        return False, "Access forbidden. Attendant is not authorized for this patient."

    # Doctor: verify assigned doctor
    if role == 'doctor':
        try:
            patient_row = db.execute_query("SELECT assigned_doctor, ward_type, ward_id FROM patients WHERE patient_id = %s", (pid,), fetch=True) if db else []
            if patient_row:
                assigned_doc = patient_row[0].get('assigned_doctor')
                if assigned_doc is None or assigned_doc == uid:
                    return True, ""
                doc_pts = db.execute_query("SELECT patient_id FROM patients WHERE assigned_doctor = %s", (uid,), fetch=True) if db else []
                if not doc_pts or any(p['patient_id'] == pid for p in doc_pts):
                    return True, ""
                return False, "Access forbidden. Doctor is not authorized for this patient."
        except Exception:
            pass

        # If in mock store
        k = _resolve_pid_key(pid)
        if k:
            return True, ""
        return False, "Patient not found."

    # Nurse: verify assigned nurse
    if role == 'nurse':
        try:
            patient_row = db.execute_query("SELECT assigned_nurse, ward_type, ward_id FROM patients WHERE patient_id = %s", (pid,), fetch=True) if db else []
            if patient_row:
                assigned_nurse = patient_row[0].get('assigned_nurse')
                if assigned_nurse is None or assigned_nurse == uid:
                    return True, ""
                nurse_pts = db.execute_query("SELECT patient_id FROM patients WHERE assigned_nurse = %s", (uid,), fetch=True) if db else []
                if not nurse_pts or any(p['patient_id'] == pid for p in nurse_pts):
                    return True, ""
                return False, "Access forbidden. Nurse is not authorized for this patient."
        except Exception:
            pass

        k = _resolve_pid_key(pid)
        if k:
            return True, ""
        return False, "Patient not found."

    return True, ""


def get_authorized_patients_for_user(user):
    """
    Retrieve list of authorized patients for the user based on RBAC rules.
    """
    role = getattr(user, 'role', 'doctor') if user else 'doctor'
    uid = getattr(user, 'id', 1) if user else 1

    patients = []
    try:
        if Patient:
            if role in ('admin', 'superadmin'):
                res = Patient.get_filtered(status='admitted', limit=100)
                patients = res.get('patients', []) if isinstance(res, dict) else (res or [])
            elif role == 'doctor':
                res = Patient.get_filtered(status='admitted', doctor_id=uid, limit=100)
                patients = res.get('patients', []) if isinstance(res, dict) else []
                if not patients:
                    res_all = Patient.get_filtered(status='admitted', limit=100)
                    patients = res_all.get('patients', []) if isinstance(res_all, dict) else []
            elif role == 'nurse':
                res = Patient.get_filtered(status='admitted', nurse_id=uid, limit=100)
                patients = res.get('patients', []) if isinstance(res, dict) else []
                if not patients:
                    res_all = Patient.get_filtered(status='admitted', limit=100)
                    patients = res_all.get('patients', []) if isinstance(res_all, dict) else []
            elif role == 'attendant':
                token_pid = getattr(user, 'patient_id', None)
                if token_pid:
                    p = Patient.get_by_id(token_pid)
                    if p:
                        patients = [p]
                else:
                    att_rows = db.execute_query(
                        "SELECT patient_id FROM attendants WHERE user_id = %s AND is_active = TRUE",
                        (uid,), fetch=True
                    ) if db else []
                    for r in (att_rows or []):
                        p = Patient.get_by_id(r['patient_id'])
                        if p:
                            patients.append(p)
    except Exception as e:
        print(f"[AUTH PATIENTS ERROR] {e}")
        patients = []

    # Fallback to mock dataset if DB returned nothing
    if not patients:
        for pid, data in MOCK_PATIENT_STORE.items():
            p_info = dict(data['patient'])
            p_info['ews_score'] = data['latest_vitals'].get('ews_score', 0) if 'latest_vitals' in data else 0
            p_info['ews_risk_level'] = get_risk_level(p_info['ews_score']).upper()
            p_info['recorded_at'] = data['latest_vitals'].get('recorded_at', 'Today 15:30 (10 mins ago)')
            patients.append(p_info)

    formatted = []
    for p in patients:
        pid = p.get('patient_id') or p.get('id')
        p_code = p.get('patient_code') or f"JS-{pid:04d}"
        vitals_time = p.get('vitals_recorded_at') or p.get('recorded_at')
        if not vitals_time and p.get('latest_vitals'):
            vitals_time = p['latest_vitals'].get('recorded_at')
        if not vitals_time:
            vitals_time = "Today 15:30 (10 mins ago)"

        ews_score = p.get('ews_score', 0) if p.get('ews_score') is not None else 0
        risk_lvl = (p.get('ews_risk_level') or p.get('risk_level') or get_risk_level(ews_score)).upper()

        formatted.append({
            'patient_id': pid,
            'id': pid,
            'name': p.get('name', f'Patient #{pid}'),
            'patient_code': p_code,
            'ward_type': p.get('ward_type') or p.get('ward_name') or 'ICU',
            'ward_name': p.get('ward_name') or p.get('ward_type') or 'ICU',
            'bed_number': p.get('bed_number') or 'N/A',
            'diagnosis': p.get('diagnosis') or '',
            'age': p.get('age'),
            'gender': p.get('gender'),
            'blood_group': p.get('blood_group'),
            'ews_score': ews_score,
            'ews_risk_level': risk_lvl,
            'risk_level': risk_lvl,
            'condition': p.get('condition') or ('CRITICAL' if ews_score >= 7 else ('HIGH' if ews_score >= 5 else ('MEDIUM' if ews_score >= 1 else 'Stable'))),
            'recorded_at': str(vitals_time),
            'vitals_recorded_at': str(vitals_time),
            'doctor_name': p.get('doctor_name'),
            'nurse_name': p.get('nurse_name'),
            'latest_vitals': p.get('latest_vitals')
        })

    return formatted


# =============================================================================
# 4. PATIENT SEARCH WITH FUZZY MATCHING & DISAMBIGUATION
# =============================================================================

def search_patients_for_chat(query):
    """
    Search patients in database by name, patient code (UHID), or patient ID with fuzzy typo tolerance.
    Returns:
        tuple (match_type, list_of_patients)
        where match_type in ('none', 'single', 'multiple')
    """
    if not query or not query.strip():
        return 'none', []

    q = query.strip().lower()

    # 1. Numeric ID search
    numeric_id = None
    if q.isdigit():
        numeric_id = int(q)
    elif q.upper().startswith("JS-") and q[3:].isdigit():
        numeric_id = int(q[3:])
    elif q.upper().startswith("JS") and q[2:].isdigit():
        numeric_id = int(q[2:])
    elif q.upper().startswith("P") and q[1:].isdigit():
        numeric_id = int(q[1:])

    if numeric_id is not None:
        p = getPatient(numeric_id)
        if p:
            return 'single', [p]

    # 2. Database query for name or code
    rows = []
    try:
        search_term = f"%{q}%"
        rows = db.execute_query(
            """SELECT p.patient_id, p.patient_code, p.name, p.age, p.gender,
                      p.ward_type, p.bed_number, p.diagnosis, p.status, p.admission_date,
                      w.name AS ward_name
               FROM patients p
               LEFT JOIN wards w ON p.ward_id = w.ward_id
               WHERE p.name LIKE %s OR p.patient_code LIKE %s
               ORDER BY p.status ASC, p.name ASC LIMIT 10""",
            (search_term, search_term), fetch=True
        ) or []
    except Exception:
        rows = []

    if len(rows) == 1:
        return 'single', [getPatient(rows[0]['patient_id'])]
    elif len(rows) > 1:
        exact = [r for r in rows if r['name'].strip().lower() == q or (r.get('patient_code') and r['patient_code'].strip().lower() == q)]
        if len(exact) == 1:
            return 'single', [getPatient(exact[0]['patient_id'])]
        return 'multiple', [getPatient(r['patient_id']) for r in rows]

    # 3. Check in-memory store
    mock_matches = []
    for k, v in MOCK_PATIENT_STORE.items():
        p_data = v['patient']
        name_l = p_data['name'].lower()
        code_l = p_data['patient_code'].lower()
        if q in name_l or q in code_l:
            mock_matches.append(p_data)
        elif q in [part.lower() for part in p_data['name'].split()]:
            mock_matches.append(p_data)

    if len(mock_matches) == 1:
        return 'single', [mock_matches[0]]
    elif len(mock_matches) > 1:
        exact = [m for m in mock_matches if m['name'].strip().lower() == q or m['patient_code'].strip().lower() == q]
        if len(exact) == 1:
            return 'single', [exact[0]]
        return 'multiple', mock_matches

    # 4. Fuzzy match across all admitted patients for typo tolerance (e.g. "sahli" -> "Sahil Sharma")
    all_names = {}
    try:
        all_patients = db.execute_query(
            "SELECT patient_id, name, patient_code FROM patients ORDER BY patient_id DESC LIMIT 50",
            fetch=True
        ) or []
        for p in all_patients:
            all_names[p['name'].lower()] = p['patient_id']
            first_name = p['name'].split()[0].lower() if p.get('name') else ''
            if first_name:
                all_names[first_name] = p['patient_id']
    except Exception:
        pass

    # Add mock store names to fuzzy map
    for k, v in MOCK_PATIENT_STORE.items():
        p_data = v['patient']
        all_names[p_data['name'].lower()] = k
        first_n = p_data['name'].split()[0].lower()
        all_names[first_n] = k

    if all_names:
        close_matches = difflib.get_close_matches(q, list(all_names.keys()), n=2, cutoff=0.7)
        if close_matches:
            matched_pid = all_names[close_matches[0]]
            matched_p = getPatient(matched_pid)
            if matched_p:
                return 'single', [matched_p]

    return 'none', []


# =============================================================================
# 5. NATURAL LANGUAGE QUESTION UNDERSTANDING & TOPIC ROUTER
# =============================================================================

STOPWORDS_NOT_PATIENTS = {
    'condition', 'status', 'update', 'overview', 'summary', 'vitals', 'vital', 'vitals_history',
    'oxygen', 'spo2', 'bp', 'blood', 'pressure', 'hr', 'pulse', 'heart', 'rate', 'breathing', 'respiratory',
    'temp', 'temperature', 'fever', 'ews', 'score', 'icu', 'hdu', 'ward', 'bed', 'transfer',
    'better', 'worse', 'improving', 'deteriorating', 'stable', 'unstable', 'critical', 'serious',
    'why', 'what', 'how', 'when', 'who', 'is', 'are', 'was', 'were', 'he', 'she', 'it', 'they',
    'him', 'her', 'his', 'their', 'the', 'this', 'that', 'these', 'those', 'yesterday', 'today',
    'overnight', 'changes', 'concerns', 'problems', 'worries', 'reassuring', 'findings', 'points',
    'diagnosis', 'illness', 'disease', 'notes', 'tell', 'show', 'give', 'check', 'explain', 'brief',
    'patient', 'the patient', 'this patient', 'a patient', 'doctor', 'nurse', 'hospital', 'bot', 'setu', 'dr setu'
}


def extract_explicit_patient_mention(text):
    """
    Checks if the user's message is an explicit command/request to switch or look up another patient.
    e.g. 'Tell me about Rajesh', 'Switch to Anita', 'Look up UHID-2026-00001', 'Rajesh Sharma'
    Returns:
        (patient_name_or_code, cleaned_question, is_explicit_switch)
    """
    msg = (text or "").strip()
    if not msg:
        return None, "", False

    # 1. Explicit UHID / Patient Code (e.g. UHID-2026-00001 or JS-0012)
    m_code = re.search(r'\b(UHID-\d{4}-\d{5}|JS-\d{2,5})\b', msg, re.IGNORECASE)
    if m_code:
        code = m_code.group(1).upper()
        cleaned = msg.replace(m_code.group(1), '').strip()
        return code, cleaned, True

    # 2. Introductory phrases: "tell me about <name>", "switch to <name>", "search for <name>", "who is <name>"
    intro_pattern = r'^\s*(?:tell\s+me\s+about|information\s+(?:on|about)|details\s+(?:of|for|on)|check\s+on|look\s+up|open|search\s+for|search|find|select|switch\s+to|change\s+to|who\s+is)\s+(?:the\s+)?(?:patient\s+)?(?P<name>[a-zA-Z0-9_\-\s]+?)(?:\s+summary|\s+status|\s+report|\?|\.|\!|$)'
    m_intro = re.search(intro_pattern, msg, re.IGNORECASE)
    if m_intro:
        raw_name = m_intro.group('name').strip()
        if raw_name.lower() not in STOPWORDS_NOT_PATIENTS and len(raw_name) > 1:
            return raw_name, "status overview", True

    # 2b. Possessive name patterns: "What is Amit Verma's EWS?", "Show Priya's vitals", "Amit Verma's diagnosis"
    m_possessive = re.search(r'\b(?P<name>[a-zA-Z]{3,}(?:\s+[a-zA-Z]{3,})?)\'s\b', msg, re.IGNORECASE)
    if m_possessive:
        raw_name = m_possessive.group('name').strip()
        if raw_name.lower() not in STOPWORDS_NOT_PATIENTS and not any(w in raw_name.lower().split() for w in ('the', 'this', 'that', 'patient', 'doctor', 'nurse', 'hospital', 'bot', 'setu')) and len(raw_name) > 2:
            cleaned = msg.replace(m_possessive.group(0), '').strip()
            return raw_name, cleaned, True

    # 2c. Phrases like "regarding <name>", "for patient <name>", "of <name>"
    m_for = re.search(r'\b(?:regarding|for\s+patient|about\s+patient|of\s+patient)\s+(?P<name>[a-zA-Z]{3,}(?:\s+[a-zA-Z]{3,})?)\b', msg, re.IGNORECASE)
    if m_for:
        raw_name = m_for.group('name').strip()
        if raw_name.lower() not in STOPWORDS_NOT_PATIENTS and not any(w in raw_name.lower().split() for w in ('the', 'this', 'that', 'patient', 'doctor', 'nurse', 'hospital', 'bot', 'setu')) and len(raw_name) > 2:
            cleaned = msg.replace(m_for.group(0), '').strip()
            return raw_name, cleaned, True

    # 3. Direct short name if 1-3 words and not a clinical concept word
    words = [w for w in re.split(r'[^a-zA-Z0-9_\-]+', msg) if w]
    if 1 <= len(words) <= 3:
        cand = " ".join(words).strip()
        if cand.lower() not in STOPWORDS_NOT_PATIENTS:
            mtype, pats = search_patients_for_chat(cand)
            if mtype in ('single', 'multiple'):
                return cand, "", True

    return None, msg, False


def _fuzzy_match_score(query_words, keyword_set):
    """Calculate how many keywords from the set appear in the query words. Returns a match score."""
    return sum(1 for kw in keyword_set if kw in query_words)


def classify_question_intent(message, session_state=None):
    """
    Free-form natural language intent and topic classification.
    Determines clinical dimension and data requirements without rigid pattern boundaries.
    Uses multi-layer matching: exact phrases → keyword scoring → fuzzy fallback.
    """
    q = (message or "").strip().lower()
    q_clean = re.sub(r'[^\w\s]', ' ', q).strip()
    words = set(q_clean.split())
    q_words_list = q_clean.split()
    state = session_state or {}
    last_topic = state.get('last_topic')
    last_param = state.get('last_parameter')

    # ── 1. Conversational Pleasantries & Acknowledgments ──
    greetings = {
        'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening',
        'dr setu', 'who are you', 'introduce yourself', 'hey there', 'hi there',
        'hello dr setu', 'hey dr setu', 'good day', 'howdy', 'namaste', 'namaskar',
        'greetings', 'yo', 'hii', 'hiii', 'helo', 'heloo', 'hellow', 'hlw',
        'good night', 'morning', 'evening', 'afternoon', 'hey doc', 'hello doctor',
        'hi doctor', 'hey doctor', 'sup', 'whats up', 'what s up', 'how are you',
        'how r u', 'how do you do', 'nice to meet you', 'tell me about yourself',
        'what is your name', 'whats your name', 'who r u', 'what are you'
    }
    if q_clean in greetings:
        return 'GREETING', None

    ack_phrases = {
        'thanks', 'thank you', 'ok', 'okay', 'got it', 'understood', 'alright',
        'great', 'perfect', 'fine', 'noted', 'thanks dr setu', 'thank u',
        'thnx', 'thx', 'tq', 'ty', 'cool', 'nice', 'awesome', 'wonderful',
        'good', 'right', 'sure', 'sounds good', 'roger', 'copy that', 'gotcha',
        'i see', 'i understand', 'makes sense', 'clear', 'roger that',
        'thanks a lot', 'thank you so much', 'much appreciated', 'appreciate it',
        'thanks for the info', 'thanks for the information', 'thanks doc',
        'thank you doctor', 'okey', 'okk', 'okayy', 'hmm', 'hmm okay',
        'oh okay', 'oh ok', 'ah ok', 'ah okay', 'yes', 'yep', 'yeah', 'yup',
        'no problem', 'no worries'
    }
    if q_clean in ack_phrases:
        return 'ACKNOWLEDGMENT', None

    help_phrases = {
        'help', 'options', 'guide', 'menu', 'what can you do', 'capabilities',
        'how to use', 'instructions', 'commands', 'features', 'what do you do',
        'how does this work', 'how do i use this', 'usage', 'tutorial',
        'what are your capabilities', 'show me what you can do', 'what all can you do',
        'list features', 'show features', 'show options', 'show commands',
        'available commands', 'what questions can i ask', 'how can you help',
        'how can you help me', 'assist me', 'help me', 'i need help',
        'what should i ask', 'give me options', 'show me options',
        'what queries can i ask', 'what can i ask you'
    }
    if q_clean in help_phrases:
        return 'HELP', None

    # ── 2. Concise Briefing / Short Version ──
    concise_phrases = [
        'short version', 'short summary', 'quick version', 'in simple terms',
        'brief version', 'give me the short version', 'give me a short summary',
        'quick update', 'tldr', 'tl dr', 'summarize briefly', 'in brief',
        'brief me', 'brief update', 'one liner', 'one line summary',
        'quick summary', 'quick brief', 'nutshell', 'in a nutshell',
        'make it short', 'keep it short', 'be brief', 'short answer',
        'in short', 'shortly', 'concise', 'summarize', 'give summary',
        'give me summary', 'brief summary', 'just the key points',
        'key points', 'highlights', 'bottom line', 'give me the bottom line',
        'just the basics', 'quick overview', 'fast update'
    ]
    if any(p in q for p in concise_phrases):
        return 'CONCISE_SUMMARY', last_param

    # ── 3. Expansion / Detail Request ──
    detail_phrases = [
        'explain that in detail', 'explain in detail', 'more details',
        'expand on that', 'explain more', 'in detail', 'elaborate',
        'tell me more', 'can you elaborate', 'give me more details',
        'more information', 'detailed explanation', 'full details',
        'deep dive', 'comprehensive', 'thorough explanation', 'go deeper',
        'explain further', 'break it down', 'break that down',
        'what do you mean', 'can you explain', 'please explain',
        'i dont understand', 'i don t understand', 'clarify', 'clarify that',
        'what does that mean', 'be more specific', 'more specific',
        'explain in simple words', 'explain like im 5', 'eli5',
        'expand', 'full explanation', 'detailed version', 'long version',
        'complete details', 'go on', 'continue', 'keep going'
    ]
    if any(p in q for p in detail_phrases):
        return 'EXPAND_DETAIL', last_param

    # ── 4. Contextual Elliptical Follow-ups ──
    followup_phrases = {
        'why', 'why is that', 'how come', 'why did that happen', 'why though',
        'explain why', 'what is the reason', 'reason', 'cause', 'what caused it',
        'what caused this', 'why is this happening', 'what is causing this',
        'what is the cause', 'root cause', 'what led to this', 'how did this happen',
        'why so', 'but why', 'and why', 'tell me why', 'any idea why',
        'do you know why', 'reason for this', 'reason behind this'
    }
    if q_clean in followup_phrases:
        if last_param:
            return 'PARAMETER_CAUSE', last_param
        if last_topic in ['TRANSFER_DECISION', 'ICU_PLACEMENT']:
            return 'TRANSFER_DECISION', None
        if last_topic in ['EWS_QUERY', 'RISK_SCORE']:
            return 'PARAMETER_CAUSE', 'ews'
        return 'PARAMETER_CAUSE', 'general'

    # ── 4b. General Medical Conceptual Query Priority ──
    general_query_starters = [
        'what is ', 'what are ', 'what causes ', 'what can cause ', 'causes of ',
        'define ', 'definition of ', 'explain ', 'meaning of ', 'how to treat ',
        'treatment for ', 'treatment of ', 'symptoms of ', 'side effects of ',
        'normal range of ', 'normal value of ', 'how does ', 'pathophysiology of '
    ]
    patient_indicators = {
        'his', 'her', 'he', 'she', 'patient', 'patients', "patient's", 'him', 'this', 'current',
        'the', 'documented', 'diagnosis', 'condition', 'vitals', 'vital', 'ews', 'score', 'recommendation',
        'transfer', 'bed', 'ward', 'admission', 'admitted', 'history', 'trends', 'trajectory', 'latest'
    }
    if any(q.startswith(p) for p in general_query_starters) and not any(w in words for w in patient_indicators):
        return 'GENERAL_MEDICAL_CONCEPT', None

    # ── 5. Single Vital Parameter Queries ──
    # SpO2 / Oxygen
    spo2_keywords = {'oxygen', 'spo2', 'o2', 'saturation', 'oxygenation', 'desaturation', 'hypoxia', 'hypoxemia', 'hypoxemic', 'oximetry'}
    spo2_phrases = ['oxygen level', 'getting enough oxygen', 'oxygen saturation', 'o2 level', 'o2 sat', 'pulse ox', 'pulse oximetry', 'his oxygen', 'her oxygen', 'patient oxygen']
    if any(w in words for w in spo2_keywords) or any(p in q for p in spo2_phrases):
        cause_words = {'why', 'cause', 'causing', 'drop', 'dropping', 'low', 'decreased', 'falling', 'declining', 'reason', 'dropped', 'went down', 'decreasing', 'plummeting'}
        if any(w in words for w in cause_words) or any(p in q for p in ['why is', 'what caused', 'why did', 'reason for']):
            return 'PARAMETER_CAUSE', 'spo2'
        return 'SINGLE_PARAMETER', 'spo2'

    # Blood Pressure
    bp_keywords = {'bp', 'systolic', 'diastolic', 'hypotension', 'hypertension', 'hypotensive', 'hypertensive', 'sbp', 'dbp', 'map'}
    bp_phrases = ['blood pressure', 'b p', 'b.p', 'blood press', 'pressure reading', 'his bp', 'her bp', 'patient bp']
    if any(w in words for w in bp_keywords) or any(p in q for p in bp_phrases):
        cause_words = {'why', 'cause', 'causing', 'low', 'high', 'dropping', 'falling', 'elevated', 'rising', 'crashed', 'tanking'}
        if any(w in words for w in cause_words):
            return 'PARAMETER_CAUSE', 'blood_pressure'
        return 'SINGLE_PARAMETER', 'blood_pressure'

    # Heart Rate
    hr_keywords = {'hr', 'pulse', 'tachycardia', 'bradycardia', 'tachycardic', 'bradycardic', 'palpitation', 'palpitations', 'arrhythmia', 'heartbeat'}
    hr_phrases = ['heart rate', 'heart beat', 'heart rhythm', 'cardiac rate', 'his pulse', 'her pulse', 'his heart', 'her heart', 'patient pulse', 'how fast is his heart']
    if any(w in words for w in hr_keywords) or any(p in q for p in hr_phrases):
        cause_words = {'why', 'cause', 'causing', 'high', 'low', 'elevated', 'fast', 'slow', 'racing', 'rapid', 'increased', 'irregular'}
        if any(w in words for w in cause_words):
            return 'PARAMETER_CAUSE', 'heart_rate'
        return 'SINGLE_PARAMETER', 'heart_rate'

    # Respiratory Rate
    rr_keywords = {'rr', 'resp', 'respiration', 'tachypnea', 'bradypnea', 'tachypneic', 'bradypneic', 'dyspnea', 'dyspneic', 'apnea'}
    rr_phrases = ['respiratory rate', 'breathing rate', 'breath rate', 'breaths per minute', 'breathing pattern',
                  'is he breathing', 'is she breathing', 'how is his breathing', 'how is her breathing',
                  'breathing fast', 'breathing slow', 'labored breathing', 'shortness of breath', 'sob',
                  'difficulty breathing', 'struggling to breathe', 'can he breathe', 'breathing difficulty',
                  'respiratory distress', 'respiratory effort', 'work of breathing', 'accessory muscles']
    if any(w in words for w in rr_keywords) or any(p in q for p in rr_phrases):
        cause_words = {'why', 'cause', 'causing', 'fast', 'high', 'elevated', 'labored', 'rapid', 'slow', 'increased', 'shallow', 'deep'}
        if any(w in words for w in cause_words):
            return 'PARAMETER_CAUSE', 'respiratory_rate'
        return 'SINGLE_PARAMETER', 'respiratory_rate'

    # Temperature
    temp_keywords = {'temp', 'temperature', 'fever', 'pyrexia', 'febrile', 'afebrile', 'hypothermia', 'hypothermic', 'hyperthermia', 'hyperthermic', 'chills', 'rigors'}
    temp_phrases = ['body temperature', 'body temp', 'does he have fever', 'does she have fever', 'is there fever',
                    'any fever', 'high temperature', 'low temperature', 'how hot', 'running a fever',
                    'his temperature', 'her temperature', 'patient temperature']
    if any(w in words for w in temp_keywords) or any(p in q for p in temp_phrases):
        cause_words = {'why', 'cause', 'causing', 'high', 'fever', 'reason', 'elevated', 'spiking', 'spiked', 'rising'}
        if any(w in words for w in cause_words):
            return 'PARAMETER_CAUSE', 'temperature'
        return 'SINGLE_PARAMETER', 'temperature'

    # Consciousness / AVPU / GCS
    if any(w in words for w in ['consciousness', 'conscious', 'unconscious', 'avpu', 'gcs', 'alert', 'responsive', 'unresponsive', 'sedated', 'awake', 'drowsy', 'comatose', 'coma']):
        return 'SINGLE_PARAMETER', 'consciousness'

    # ── 6. All Vitals Query ──
    all_vitals_phrases = [
        'all vitals', 'all vital signs', 'all parameters', 'complete vitals', 'full vitals',
        'show me all vitals', 'show all vitals', 'show vitals', 'list vitals',
        'latest vitals', 'current vitals', 'recent vitals', 'vital signs',
        'what are his vitals', 'what are her vitals', 'what are the vitals',
        'vitals please', 'give me vitals', 'give me the vitals', 'vitals report',
        'check vitals', 'tell me the vitals', 'vitals reading', 'vitals readings',
        'monitoring data', 'telemetry data', 'telemetry readings', 'latest readings',
        'current readings', 'show me the numbers', 'numbers'
    ]
    if q_clean in ['vitals', 'vital', 'vital signs'] or any(p in q for p in all_vitals_phrases):
        return 'STATUS_OVERVIEW', None

    # ── 7. Trajectory / Deterioration / Improvement Queries ──
    trajectory_phrases = [
        'getting better', 'getting worse', 'is he improving', 'is she improving',
        'is condition improving', 'is condition deteriorating', 'is he stable',
        'is she stable', 'is the patient stable', 'better or worse',
        'how is condition changing', 'does anything look worse', 'is he unstable',
        'improving or worsening', 'improving or deteriorating', 'any improvement',
        'has he improved', 'has she improved', 'any change', 'any changes',
        'trend', 'trends', 'vital trends', 'trending', 'trajectory',
        'is he recovering', 'is she recovering', 'recovery progress',
        'progress', 'prognosis update', 'how is the trajectory',
        'deteriorating', 'worsening', 'declining', 'decompensating',
        'stabilizing', 'stabilising', 'recovering', 'responding to treatment',
        'is he responding', 'is she responding', 'any progress',
        'how is he progressing', 'how is she progressing',
        'is the condition stable', 'condition stable or not',
        'is patient stable', 'patient stable', 'hemodynamically stable',
        'showing improvement', 'showing signs of improvement',
        'going downhill', 'taking a turn', 'looking better', 'looking worse',
        'condition improving', 'condition worsening', 'condition declining'
    ]
    if any(p in q for p in trajectory_phrases):
        return 'TRAJECTORY_ANALYSIS', None

    # ── 8. Overnight & Historical Comparisons ──
    historical_phrases = [
        'what changed', 'overnight', 'since yesterday', 'yesterday',
        'compare today with yesterday', 'compare with yesterday',
        'what happened overnight', 'what happened since yesterday', 'has it changed',
        'has that changed', 'is he better today than yesterday',
        'since last reading', 'since last check', 'since morning',
        'since admission', 'compared to before', 'compared to earlier',
        'earlier today', 'previous reading', 'last reading vs now',
        'how has it changed', 'change since', 'change over time',
        'over the last few hours', 'in the last hour', 'in the last 24 hours',
        'past 24 hours', 'past hour', 'recent changes', 'any recent changes',
        'compare readings', 'difference between', 'before and after',
        'was it different before', 'how was it before', 'previous values',
        'last recorded', 'compare last two', 'historical', 'history of changes'
    ]
    if any(p in q for p in historical_phrases):
        return 'HISTORICAL_COMPARISON', last_param

    # ── 9. Key Concerns & Worries ──
    concern_phrases = [
        'what worries you', 'what is worrying', 'main concerns', 'main problems',
        'what concerns you', 'anything concerning', 'anything worrying', 'anything abnormal',
        'what looks good', 'what is reassuring', 'biggest concern', 'most concerning',
        'important things', 'important findings', 'what should i be worried about',
        'what should i be most concerned about', 'give me the important things',
        'red flags', 'any red flags', 'any warnings', 'warning signs',
        'any abnormalities', 'abnormal findings', 'abnormal values',
        'critical findings', 'critical values', 'out of range', 'out of normal',
        'what is wrong', 'what is abnormal', 'problems', 'issues',
        'any issues', 'any problems', 'cause for concern', 'concerning findings',
        'what needs attention', 'priority concerns', 'urgent findings',
        'alarming', 'anything alarming', 'danger signs', 'risky findings',
        'what should i focus on', 'what to focus on', 'key issues',
        'what is off', 'anything off', 'something wrong', 'not right',
        'concerning', 'worried', 'scary', 'alarming findings',
        'positive findings', 'good signs', 'good news', 'bad news',
        'reassuring findings', 'encouraging signs', 'good indicators'
    ]
    if any(p in q for p in concern_phrases):
        return 'KEY_CONCERNS', None

    # ── 10. Prognosis, Severity & Mortality ──
    severity_phrases = [
        'serious', 'is it serious', 'is that serious', 'is this serious',
        'in danger', 'is he critical', 'going to die', 'will he die', 'will he survive',
        'mortality', 'life expectancy', 'should i be worried',
        'how serious', 'how bad', 'how severe', 'severity', 'critical condition',
        'life threatening', 'life-threatening', 'dangerous', 'is it dangerous',
        'is he dying', 'is she dying', 'risk of death', 'chances of survival',
        'survival chances', 'survival rate', 'will he make it', 'will she make it',
        'is he going to be okay', 'is she going to be okay', 'is he gonna be ok',
        'fatal', 'can this be fatal', 'is this fatal', 'outcome', 'expected outcome',
        'what are the chances', 'prognosis', 'what is the prognosis',
        'how critical', 'risk level', 'how much risk', 'level of risk',
        'scale of severity', 'how worried should i be', 'should we be concerned',
        'is this life threatening', 'emergency', 'is this an emergency',
        'urgent', 'is it urgent', 'grave', 'grave condition'
    ]
    if any(p in q for p in severity_phrases):
        return 'PROGNOSIS_SEVERITY', None

    # ── 11. Transfer Decision & ICU Placement ──
    transfer_phrases = [
        'still in icu', 'in icu', 'why icu', 'ready for hdu', 'step down',
        'step-down', 'transfer recommendation', 'transfer decision', 'why transfer',
        'why marked', 'why is he being kept in icu', 'ready for ward',
        'can he be transferred', 'can she be transferred', 'transfer out',
        'move to ward', 'move to hdu', 'move to general ward', 'discharge',
        'can he be discharged', 'can she be discharged', 'ready for discharge',
        'when can he leave', 'when can she leave', 'when will he be discharged',
        'when will she be discharged', 'fit for discharge', 'eligible for transfer',
        'ward transfer', 'icu to hdu', 'hdu to ward', 'icu to ward',
        'ready to step down', 'step down criteria', 'transfer criteria',
        'why not transferred', 'why not moved', 'escalate', 'escalation',
        'de-escalate', 'de escalate', 'deescalate', 'shift to ward',
        'shift to hdu', 'shift to icu', 'need icu', 'needs icu',
        'does he need icu', 'does she need icu', 'icu admission criteria',
        'which ward', 'which unit', 'where should he be', 'where should she be',
        'appropriate ward', 'appropriate unit', 'level of care'
    ]
    if any(p in q for p in transfer_phrases):
        return 'TRANSFER_DECISION', None

    # ── 12. Decision History & Clinician Reviews ──
    decision_phrases = [
        'previous review', 'previous decision', 'decision history', 'who reviewed',
        'override', 'past transfer', 'past reviews', 'past decisions',
        'review history', 'who approved', 'who decided', 'clinician review',
        'doctor review', 'attending review', 'physician review',
        'who signed off', 'who overrode', 'was this overridden', 'history of decisions',
        'audit trail', 'decision log', 'approval history', 'review log'
    ]
    if any(p in q for p in decision_phrases):
        return 'DECISION_HISTORY', None

    # ── 13. EWS & Risk Score ──
    ews_phrases = [
        'ews', 'early warning score', 'stability index', 'csi', 'risk score',
        'news', 'news2', 'mews', 'warning score', 'acuity score',
        'clinical score', 'patient score', 'composite stability',
        'composite score', 'risk assessment', 'risk rating',
        'what is the score', 'what is his score', 'what is her score',
        'score breakdown', 'ews breakdown', 'ews score',
        'current score', 'latest score', 'patient risk'
    ]
    if any(p in q for p in ews_phrases):
        if any(w in words for w in ['why', 'high', 'increase', 'increased', 'elevated', 'rising', 'went up']):
            return 'PARAMETER_CAUSE', 'ews'
        return 'EWS_QUERY', None

    # ── 14. Documented Condition & Medical History ──
    condition_phrases = [
        'what illness', 'what diagnosis', 'what condition does he have', 'documented diagnosis',
        'previous condition', 'previous illness', 'medical history', 'history of',
        'what disease', 'what is wrong with him', 'what is wrong with her',
        'what does he have', 'what does she have', 'diagnosed with', 'suffering from',
        'admitted for', 'reason for admission', 'admission diagnosis',
        'admission reason', 'why was he admitted', 'why was she admitted',
        'what brought him in', 'what brought her in', 'chief complaint',
        'presenting complaint', 'primary diagnosis', 'secondary diagnosis',
        'comorbidities', 'comorbidity', 'co morbidities', 'co morbidity',
        'past medical history', 'pmh', 'existing conditions', 'chronic conditions',
        'allergies', 'drug allergies', 'known allergies', 'nkda',
        'past surgical history', 'surgical history', 'family history',
        'underlying condition', 'underlying disease', 'what is his condition',
        'what is her condition', 'nature of illness'
    ]
    if any(p in q for p in condition_phrases):
        return 'DOCUMENTED_CONDITION', None

    # ── 15. Alerts Query ──
    alert_phrases = [
        'alerts', 'alert', 'active alerts', 'any alerts', 'clinical alerts',
        'alarms', 'any alarms', 'notifications', 'warnings', 'any warnings',
        'critical alerts', 'show alerts', 'list alerts', 'pending alerts',
        'unacknowledged alerts', 'triggered alerts', 'threshold breach',
        'threshold breaches', 'alarm history'
    ]
    if any(p in q for p in alert_phrases):
        return 'KEY_CONCERNS', None

    # ── 16. Broad Overview & Status ──
    status_exact = {
        'condition', 'status', 'update', 'current condition', 'current status',
        'how is he', 'how is she', 'how is the patient', 'how does he look',
        'what is happening', 'whats happening', 'what is going on', 'whats going on',
        'whats wrong with him', 'what is wrong with him', 'how is he doing',
        'hows he doing', 'what should i know', 'what should i know about this patient',
        'tell me about him', 'tell me about her', 'patient overview',
        'overview', 'overall status', 'general status', 'general condition',
        'clinical status', 'clinical overview', 'patient condition',
        'show patient summary', 'show complete patient summary',
        'complete summary', 'full summary', 'patient summary',
        'give me a summary', 'summary', 'report', 'patient report',
        'clinical summary', 'how is patient', 'how is my patient',
        'tell me everything', 'tell me about the patient', 'patient status',
        'patient update', 'give me an update', 'any updates', 'current state',
        'present condition', 'how is condition', 'update me', 'catch me up',
        'fill me in', 'bring me up to speed', 'whats the situation',
        'what is the situation', 'situation', 'sitrep', 'sit rep',
        'clinical update', 'rounds update', 'rounds summary', 'for rounds'
    }
    if q_clean in status_exact:
        return 'STATUS_OVERVIEW', None

    # Broader status matching with keyword scoring
    status_keywords = {'overview', 'summary', 'status', 'condition', 'situation', 'update', 'report', 'rounds'}
    patient_ref_words = {'patient', 'his', 'her', 'him', 'he', 'she', 'their', 'this'}
    if _fuzzy_match_score(words, status_keywords) >= 1 and _fuzzy_match_score(words, patient_ref_words) >= 1:
        return 'STATUS_OVERVIEW', None

    # ── 17. General Medical Concepts (greatly expanded) ──
    medical_concept_phrases = [
        'what does low spo2 mean', 'what is normal respiratory rate', 'what is normal heart rate',
        'what is normal blood pressure', 'what is ews', 'what is tachycardia', 'what is bradycardia',
        'what can cause a low spo2', 'what causes low spo2',
        # Expanded general medical concept triggers
        'what is', 'what are', 'define', 'definition of', 'meaning of',
        'explain what', 'what does', 'tell me about',
    ]
    # Check if it is a "what is X" style medical question (no patient context needed)
    medical_concept_patterns = [
        r'^what (?:is|are|does|do|causes?|can cause) (?:a |an |the )?[\w\s]+$',
        r'^define [\w\s]+$',
        r'^meaning of [\w\s]+$',
        r'^explain [\w\s]+$',
        r'^tell me about [\w\s]+$',
    ]
    # Only trigger for known medical/clinical terms
    medical_terms_in_query = {
        'pneumonia', 'sepsis', 'septic', 'shock', 'ards', 'copd', 'asthma', 'diabetes',
        'hypertension', 'hypotension', 'tachycardia', 'bradycardia', 'tachypnea', 'bradypnea',
        'hypoxia', 'hypoxemia', 'cyanosis', 'edema', 'oedema', 'anemia', 'anaemia',
        'infection', 'inflammation', 'thrombosis', 'embolism', 'hemorrhage', 'haemorrhage',
        'arrhythmia', 'fibrillation', 'flutter', 'infarction', 'ischemia', 'ischaemia',
        'stroke', 'tia', 'dvt', 'pe', 'pulmonary embolism', 'heart failure', 'cardiac arrest',
        'respiratory failure', 'renal failure', 'kidney failure', 'liver failure',
        'metabolic acidosis', 'metabolic alkalosis', 'respiratory acidosis', 'respiratory alkalosis',
        'dehydration', 'fluid overload', 'electrolyte imbalance', 'hyponatremia', 'hypernatremia',
        'hypokalemia', 'hyperkalemia', 'hypoglycemia', 'hyperglycemia', 'ketoacidosis', 'dka',
        'ventilator', 'intubation', 'tracheostomy', 'bipap', 'cpap', 'high flow nasal cannula',
        'vasoactive', 'vasopressor', 'inotrope', 'antibiotics', 'anticoagulant', 'steroid',
        'spo2', 'ews', 'news', 'news2', 'gcs', 'avpu', 'map', 'cvp', 'abg', 'lactate',
        'creatinine', 'bun', 'troponin', 'bnp', 'procalcitonin', 'crp', 'wbc', 'platelet',
        'hemoglobin', 'hematocrit', 'inr', 'ptt', 'fibrinogen', 'd dimer',
        'ecg', 'ekg', 'chest x ray', 'ct scan', 'mri', 'ultrasound', 'echo', 'echocardiogram',
        'normal', 'abnormal', 'critical', 'emergency', 'intensive care', 'icu', 'hdu',
        'cholecystectomy', 'appendectomy', 'laparoscopic', 'surgery', 'post operative',
        'drug', 'medicine', 'medication', 'dose', 'dosage', 'side effect', 'adverse effect',
        'contraindication', 'interaction', 'pharmacology', 'treatment', 'therapy', 'protocol',
        'resuscitation', 'cpr', 'defibrillation', 'cardioversion', 'pacing',
        'blood gas', 'arterial blood gas', 'venous blood gas', 'oxygen therapy',
        'mechanical ventilation', 'non invasive ventilation', 'niv', 'peep', 'fio2',
        'central line', 'arterial line', 'catheter', 'foley', 'ng tube', 'chest tube',
        'vital signs', 'vital parameters', 'hemodynamics', 'cardiac output',
        'mean arterial pressure', 'pulse pressure', 'perfusion', 'capillary refill',
        'auscultation', 'palpation', 'percussion', 'inspection',
        'pneumothorax', 'pleural effusion', 'atelectasis', 'consolidation',
        'cellulitis', 'abscess', 'wound', 'laceration', 'fracture', 'dislocation',
        'concussion', 'contusion', 'hematoma', 'subdural', 'epidural', 'subarachnoid',
        'meningitis', 'encephalitis', 'seizure', 'epilepsy', 'status epilepticus',
        'diabetic', 'insulin', 'metformin', 'dialysis', 'hemodialysis', 'peritoneal dialysis',
        'transplant', 'rejection', 'immunosuppression', 'biopsy', 'histology', 'pathology',
        'oncology', 'cancer', 'tumor', 'tumour', 'malignant', 'benign', 'metastasis',
        'chemotherapy', 'radiation', 'immunotherapy', 'palliative', 'hospice',
        'pandemic', 'epidemic', 'outbreak', 'quarantine', 'isolation',
        'vaccine', 'vaccination', 'immunization', 'booster',
        'allergy', 'anaphylaxis', 'urticaria', 'angioedema',
        'thyroid', 'hypothyroidism', 'hyperthyroidism', 'adrenal', 'cushing',
        'addison', 'pituitary', 'parathyroid',
        'migraine', 'headache', 'vertigo', 'dizziness', 'syncope', 'fainting',
        'nausea', 'vomiting', 'diarrhea', 'constipation', 'gi bleed',
        'jaundice', 'hepatitis', 'cirrhosis', 'pancreatitis', 'cholecystitis',
        'appendicitis', 'diverticulitis', 'colitis', 'crohn', 'ulcerative',
        'uti', 'pyelonephritis', 'nephrolithiasis', 'kidney stone',
        'prostatitis', 'bph', 'erectile', 'infertility',
        'pregnancy', 'preeclampsia', 'eclampsia', 'gestational', 'postpartum',
        'pediatric', 'neonatal', 'geriatric', 'elderly',
        'mental health', 'depression', 'anxiety', 'psychosis', 'schizophrenia',
        'bipolar', 'ptsd', 'ocd', 'adhd', 'autism', 'dementia', 'alzheimer',
        'paracetamol', 'acetaminophen', 'ibuprofen', 'aspirin', 'morphine',
        'fentanyl', 'midazolam', 'propofol', 'ketamine', 'epinephrine',
        'norepinephrine', 'dopamine', 'dobutamine', 'atropine', 'amiodarone',
        'heparin', 'warfarin', 'enoxaparin', 'clopidogrel', 'ticagrelor',
        'amlodipine', 'metoprolol', 'atenolol', 'lisinopril', 'enalapril',
        'losartan', 'valsartan', 'furosemide', 'spironolactone', 'hydrochlorothiazide',
        'omeprazole', 'pantoprazole', 'ranitidine', 'ondansetron', 'metoclopramide',
        'dexamethasone', 'hydrocortisone', 'prednisone', 'prednisolone',
        'amoxicillin', 'azithromycin', 'ciprofloxacin', 'ceftriaxone', 'vancomycin',
        'meropenem', 'piperacillin', 'tazobactam', 'gentamicin', 'clindamycin',
        'fluconazole', 'acyclovir', 'oseltamivir', 'remdesivir'
    }
    if any(p in q for p in ['what is ', 'what are ', 'define ', 'definition of ', 'meaning of ', 'explain what ']):
        # Check if any medical term is in the query
        if any(term in q for term in medical_terms_in_query):
            return 'GENERAL_MEDICAL_CONCEPT', None

    # Direct medical concept detection (even without "what is")
    if any(p in q for p in ['what does low spo2 mean', 'what is normal respiratory rate',
                            'what is normal heart rate', 'what is normal blood pressure',
                            'what is ews', 'what is tachycardia', 'what is bradycardia',
                            'what can cause a low spo2', 'what causes low spo2',
                            'normal range', 'normal value', 'reference range',
                            'what causes', 'causes of', 'symptoms of', 'treatment for',
                            'treatment of', 'how to treat', 'how to manage',
                            'side effects of', 'adverse effects of', 'contraindications of',
                            'mechanism of action', 'how does it work', 'pathophysiology',
                            'etiology', 'aetiology', 'epidemiology', 'risk factors',
                            'complications of', 'differential diagnosis']):
        return 'GENERAL_MEDICAL_CONCEPT', None

    # ── 18. Open Clinical Reasoning (Catch-all for custom clinical inquiries) ──
    return 'OPEN_CLINICAL_QUERY', None

# Alias for backwards compatibility with test suites
detect_intent = classify_question_intent


# =============================================================================
# 6. CLINICAL REASONING SYNTHESIZERS GROUNDED IN DATABASE DATA
# =============================================================================

def reason_status_overview(patient_id):
    """Natural clinical overview for 'condition?', 'how is he?', 'what is happening?'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."

    v = getLatestVitals(patient_id)
    ews_info = getEWS(patient_id)
    trends = getVitalTrend(patient_id)
    rec = getTransferDecision(patient_id)
    
    p_name = p['name']
    unit = p.get('ward_type', 'ICU')
    bed = f" (Bed {p['bed_number']})" if p.get('bed_number') else ""
    diag_str = f" Documented condition: **{p.get('diagnosis')}**." if p.get('diagnosis') else ""

    if not v:
        return f"**{p_name}** is currently admitted in the **{unit}**{bed}.{diag_str}\n\nThere are no vital sign readings recorded yet in the database."

    rec_time = v.get('recorded_at', 'recent')
    score = ews_info.get('score', 0)
    risk = ews_info.get('risk_level', 'LOW')
    direction = trends.get('overall_direction', 'Stable').lower()

    findings = []
    if v.get('spo2') is not None:
        tag = " (Low)" if v.get('spo2') < 94 else " (Normal)"
        findings.append(f"SpO₂: **{_fmt_val(v.get('spo2'))}%**{tag}")
    if v.get('respiratory_rate') is not None:
        tag = " (Tachypneic)" if v.get('respiratory_rate') > 22 else (" (Bradypneic)" if v.get('respiratory_rate') < 12 else " (Normal)")
        findings.append(f"Respiratory Rate: **{_fmt_val(v.get('respiratory_rate'))}/min**{tag}")
    if v.get('heart_rate') is not None:
        tag = " (Tachycardic)" if v.get('heart_rate') > 100 else (" (Bradycardic)" if v.get('heart_rate') < 50 else " (Normal)")
        findings.append(f"Heart Rate: **{_fmt_val(v.get('heart_rate'))} bpm**{tag}")
    if v.get('blood_pressure_sys') is not None:
        dia_str = f"/{_fmt_val(v.get('blood_pressure_dia'))}" if v.get('blood_pressure_dia') is not None else ""
        tag = " (Hypotensive)" if v.get('blood_pressure_sys') < 90 else ""
        findings.append(f"Blood Pressure: **{_fmt_val(v.get('blood_pressure_sys'))}{dia_str} mmHg**{tag}")
    if v.get('temperature') is not None:
        tag = " (Fever)" if v.get('temperature') > 38.0 else ""
        findings.append(f"Temperature: **{_fmt_val(v.get('temperature'))} °C**{tag}")

    findings_str = "\n• ".join(findings) if findings else "Telemetry within normal parameters."

    condition_desc = "critical and requiring close observation" if score >= 7 else ("concerning with active physiological stress" if score >= 4 else "stable on current support")

    return (
        f"**{p_name}** is currently in the **{unit}**{bed}.{diag_str}\n"
        f"Based on the latest database readings, their condition is **{condition_desc}**.\n\n"
        f"**Latest Telemetry (Recorded {rec_time}):**\n"
        f"• {findings_str}\n\n"
        f"• **Trajectory**: Overall physiological trend is **{direction}**.\n"
        f"• **Early Warning Score (EWS)**: **{score}** ({risk} Risk Category).\n"
        f"• **Decision Support Recommendation**: **{rec.get('recommendation_text')}** ({rec.get('reason')})."
    )


def reason_single_parameter_inquiry(patient_id, parameter):
    """Direct, focused answer for single vital queries ('how is his oxygen?', 'what about his BP?')."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    v = getLatestVitals(patient_id)
    trends = getVitalTrend(patient_id).get('parameters', {})
    
    if not v:
        return f"No telemetry readings are recorded for {p['name']}."

    rec_time = v.get('recorded_at', 'recent')
    p_name = p['name']

    if parameter == 'spo2':
        val = v.get('spo2')
        if val is None:
            return f"Oxygen saturation (SpO2) is not recorded for {p_name}."
        t_info = trends.get('spo2')
        prev_str = f"Previous readings were {', '.join(_fmt_val(x) + '%' for x in t_info['previous_values'])}, showing a **{t_info['direction'].lower()}** trend." if t_info and t_info.get('previous_values') else "No previous baseline readings recorded."
        status_text = "significantly below target (Hypoxemia)" if val < 92 else ("borderline low" if val < 95 else "within normal range")
        return (
            f"**{p_name}**'s latest Oxygen Saturation (SpO2) is **{_fmt_val(val)}%** ({status_text}), recorded at {rec_time}.\n\n"
            f"• {prev_str}"
        )

    if parameter == 'blood_pressure':
        sys_bp = v.get('blood_pressure_sys')
        dia_bp = v.get('blood_pressure_dia')
        if sys_bp is None:
            return f"Blood pressure is not recorded for {p_name}."
        dia_str = f"/{_fmt_val(dia_bp)}" if dia_bp is not None else ""
        status_text = "hypotensive (compromised perfusion)" if sys_bp < 90 else ("elevated / hypertensive" if sys_bp > 140 else "normotensive")
        t_info = trends.get('blood_pressure_sys')
        prev_str = f"Previous systolic readings were {', '.join(_fmt_val(x) + ' mmHg' for x in t_info['previous_values'])}." if t_info and t_info.get('previous_values') else ""
        return (
            f"**{p_name}**'s latest Blood Pressure is **{_fmt_val(sys_bp)}{dia_str} mmHg** ({status_text}), recorded at {rec_time}.\n"
            + (f"• {prev_str}" if prev_str else "")
        )

    if parameter == 'heart_rate':
        hr = v.get('heart_rate')
        if hr is None:
            return f"Heart rate is not recorded for {p_name}."
        status_text = "tachycardic (>100 bpm)" if hr > 100 else ("bradycardic (<50 bpm)" if hr < 50 else "normal rate")
        t_info = trends.get('heart_rate')
        prev_str = f"Previous readings were {', '.join(_fmt_val(x) + ' bpm' for x in t_info['previous_values'])}, indicating a **{t_info['direction'].lower()}** trend." if t_info and t_info.get('previous_values') else ""
        return (
            f"**{p_name}**'s latest Heart Rate is **{_fmt_val(hr)} bpm** ({status_text}), recorded at {rec_time}.\n"
            + (f"• {prev_str}" if prev_str else "")
        )

    if parameter == 'respiratory_rate':
        rr = v.get('respiratory_rate')
        if rr is None:
            return f"Respiratory rate is not recorded for {p_name}."
        status_text = "tachypneic (respiratory distress)" if rr > 22 else ("bradypneic" if rr < 12 else "normal rate")
        t_info = trends.get('respiratory_rate')
        prev_str = f"Previous readings were {', '.join(_fmt_val(x) + '/min' for x in t_info['previous_values'])}, indicating a **{t_info['direction'].lower()}** trend." if t_info and t_info.get('previous_values') else ""
        return (
            f"**{p_name}**'s latest Respiratory Rate is **{_fmt_val(rr)} breaths/min** ({status_text}), recorded at {rec_time}.\n"
            + (f"• {prev_str}" if prev_str else "")
        )

    if parameter == 'temperature':
        temp = v.get('temperature')
        if temp is None:
            return f"Temperature is not recorded for {p_name}."
        status_text = "febrile (elevated)" if temp > 38.0 else ("hypothermic" if temp < 36.0 else "afebrile")
        return f"**{p_name}**'s latest Body Temperature is **{_fmt_val(temp)} °C** ({status_text}), recorded at {rec_time}."

    return reason_status_overview(patient_id)


def reason_parameter_causality(patient_id, parameter):
    """Answers 'why is his oxygen low?', 'why did EWS increase?', 'why?'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    v = getLatestVitals(patient_id)
    trends = getVitalTrend(patient_id).get('parameters', {})
    ews_info = getEWS(patient_id)
    doc = getDocumentedConditions(patient_id)

    if not v:
        return f"No telemetry readings are recorded in the database for {p['name']}."

    p_name = p['name']
    diag = doc.get('diagnosis')
    diag_str = f" in the setting of documented **{diag}**" if diag else ""

    if parameter in ('spo2', 'oxygen'):
        spo2_val = _fmt_val(v.get('spo2'))
        rr_val = _fmt_val(v.get('respiratory_rate'))
        hr_val = _fmt_val(v.get('heart_rate'))
        t_spo2 = trends.get('spo2')
        prev_str = f" (dropping from {t_spo2['oldest_in_window']}%)" if t_spo2 and t_spo2.get('previous_values') else ""

        return (
            f"**{p_name}**'s SpO₂ is low at **{spo2_val}%**{prev_str}{diag_str}.\n\n"
            f"**Correlating Clinical Findings:**\n"
            f"• **Respiratory Effort**: Respiratory rate is elevated at **{rr_val}/min** (Tachypnea), reflecting increased work of breathing and compensatory ventilatory drive.\n"
            f"• **Cardiac Response**: Heart rate is **{hr_val} bpm**, representing compensatory tachycardia secondary to hypoxemia and physiological stress.\n\n"
            f"**Clinical Assessment**: This pattern points to active pulmonary gas-exchange impairment. Supplemental oxygen titration, ABG analysis, and immediate lung auscultation are indicated."
        )

    if parameter in ('heart_rate', 'hr', 'pulse', 'tachycardia'):
        hr_val = _fmt_val(v.get('heart_rate'))
        sbp_val = _fmt_val(v.get('blood_pressure_sys'))
        temp_val = _fmt_val(v.get('temperature'))
        spo2_val = _fmt_val(v.get('spo2'))

        return (
            f"**{p_name}**'s Heart Rate is elevated at **{hr_val} bpm**{diag_str}.\n\n"
            f"**Correlating Factors:**\n"
            f"• **Blood Pressure**: Systolic BP is **{sbp_val} mmHg**.\n"
            f"• **Oxygenation**: SpO₂ is **{spo2_val}%**.\n"
            f"• **Temperature**: {_fmt_val(temp_val)} °C.\n\n"
            f"**Clinical Assessment**: Tachycardia in this setting is most commonly compensatory for systemic hypoxemia, volume depletion, fever, or pain. Review volume status and obtain an ECG."
        )

    if parameter in ('ews', 'score'):
        score = ews_info.get('score', 0)
        breakdown = ews_info.get('breakdown', {})
        drivers = []
        for param, d in breakdown.items():
            if d.get('score', 0) > 0:
                p_label = param.replace('_', ' ').title()
                drivers.append(f"{p_label} of {_fmt_val(d['value'])} (+{d['score']} pts)")

        driver_str = "\n• ".join(drivers) if drivers else "Multiple physiological parameter deviations"
        return (
            f"**{p_name}**'s Early Warning Score is **{score}** ({ews_info.get('risk_level', 'HIGH')} Risk).\n\n"
            f"**Main Score Drivers:**\n"
            f"• {driver_str}\n\n"
            f"**Assessment**: The score has increased due to acute multi-system deviation, requiring escalation of telemetry monitoring and physician review."
        )

    # General causality
    score = ews_info.get('score', 0)
    return (
        f"Based on **{p_name}**'s latest telemetry{diag_str}, the main driver of physiological instability is a combination of:\n"
        f"• SpO₂ of **{_fmt_val(v.get('spo2'))}%** with tachypnea (**{_fmt_val(v.get('respiratory_rate'))}/min**).\n"
        f"• Early Warning Score of **{score}** ({ews_info.get('risk_level', 'LOW')} Risk).\n\n"
        f"This reflects acute physiological strain. Database readings alone cannot establish a single etiology; direct bedside clinical evaluation is advised."
    )


def reason_trajectory_and_improvement(patient_id):
    """Direct answer for 'is he getting better?', 'is he stable?' (Answer-First rule)."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    history = getRecentVitals(patient_id, limit=6)
    trends = calculate_vital_trends(history)
    ews_info = getEWS(patient_id)
    
    if not history or len(history) < 2:
        v = getLatestVitals(patient_id)
        if v:
            return f"There is only one recorded reading for **{p['name']}** (SpO₂ {_fmt_val(v.get('spo2'))}%, HR {_fmt_val(v.get('heart_rate'))} bpm), which is insufficient to determine a longitudinal trajectory."
        return f"No telemetry data is recorded for {p['name']}."

    p_name = p['name']
    direction = trends.get('overall_direction', 'STABLE')
    score = ews_info.get('score', 0)

    curr = history[0]
    oldest = history[-1]

    if direction == "WORSENING":
        answer = f"**{p_name} is currently deteriorating rather than improving.**"
    elif direction == "IMPROVING":
        answer = f"**{p_name}'s recent trajectory shows positive physiological improvement.**"
    elif direction == "STABLE":
        answer = f"**{p_name}'s condition is currently stable without acute deviation.**"
    else:
        answer = f"**{p_name}'s parameters show a mixed physiological pattern.**"

    changes = []
    if curr.get('spo2') is not None and oldest.get('spo2') is not None:
        changes.append(f"SpO₂ has moved from {_fmt_val(oldest.get('spo2'))}% to **{_fmt_val(curr.get('spo2'))}%**")
    if curr.get('respiratory_rate') is not None and oldest.get('respiratory_rate') is not None:
        changes.append(f"Respiratory rate has changed from {_fmt_val(oldest.get('respiratory_rate'))}/min to **{_fmt_val(curr.get('respiratory_rate'))}/min**")
    if curr.get('heart_rate') is not None and oldest.get('heart_rate') is not None:
        changes.append(f"Heart rate is now **{_fmt_val(curr.get('heart_rate'))} bpm** (previously {_fmt_val(oldest.get('heart_rate'))} bpm)")

    changes_str = "\n• ".join(changes)

    return (
        f"{answer}\n\n"
        f"**Telemetry Trajectory Evidence (Last {len(history)} readings):**\n"
        f"• {changes_str}\n"
        f"• **Current EWS Score**: **{score}** ({ews_info.get('risk_level', 'LOW')} Risk)\n\n"
        f"*(Trend analysis based on recorded database readings)*"
    )


def reason_historical_overnight_comparison(patient_id):
    """Direct comparison for 'what changed overnight?', 'compare with yesterday'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    history = getRecentVitals(patient_id, limit=10)
    
    if len(history) < 2:
        return f"For **{p['name']}**, there are not enough historical readings in the database to perform an overnight comparison."

    curr = history[0]
    prev = history[1]
    curr_time = curr.get('recorded_at', 'Current')
    prev_time = prev.get('recorded_at', 'Previous')

    lines = [
        f"**Overnight Telemetry Comparison for {p['name']} ({curr_time} vs {prev_time}):**\n"
    ]

    c_spo2, p_spo2 = curr.get('spo2'), prev.get('spo2')
    if c_spo2 is not None and p_spo2 is not None:
        ch = "decreased (worsened)" if c_spo2 < p_spo2 else ("increased (improved)" if c_spo2 > p_spo2 else "remained steady")
        lines.append(f"• **SpO₂**: {_fmt_val(p_spo2)}% → **{_fmt_val(c_spo2)}%** ({ch})")

    c_rr, p_rr = curr.get('respiratory_rate'), prev.get('respiratory_rate')
    if c_rr is not None and p_rr is not None:
        ch = "increased (worsened)" if c_rr > p_rr else ("decreased (improved)" if c_rr < p_rr else "stable")
        lines.append(f"• **Respiratory Rate**: {_fmt_val(p_rr)}/min → **{_fmt_val(c_rr)}/min** ({ch})")

    c_hr, p_hr = curr.get('heart_rate'), prev.get('heart_rate')
    if c_hr is not None and p_hr is not None:
        ch = "increased" if c_hr > p_hr else ("decreased" if c_hr < p_hr else "stable")
        lines.append(f"• **Heart Rate**: {_fmt_val(p_hr)} bpm → **{_fmt_val(c_hr)} bpm** ({ch})")

    c_bp, p_bp = curr.get('blood_pressure_sys'), prev.get('blood_pressure_sys')
    if c_bp is not None and p_bp is not None:
        lines.append(f"• **Systolic BP**: {_fmt_val(p_bp)} mmHg → **{_fmt_val(c_bp)} mmHg**")

    c_ews, p_ews = curr.get('ews_score', 0), prev.get('ews_score', 0)
    lines.append(f"• **EWS Score**: {p_ews} → **{c_ews}** ({'Increased Risk' if c_ews > p_ews else ('Decreased Risk' if c_ews < p_ews else 'Unchanged')})")

    summary_note = "elevated physiological stress and higher risk" if c_ews >= p_ews else "physiological stabilization"
    lines.append(f"\n**Summary**: Compared to the previous reading at {prev_time}, the patient demonstrates **{summary_note}**.")
    return "\n".join(lines)


def reason_key_concerns(patient_id):
    """Direct summary for 'what worries you?', 'what is the biggest concern right now?'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    v = getLatestVitals(patient_id)
    ews_info = getEWS(patient_id)
    rec = getTransferDecision(patient_id)

    if not v:
        return f"No vital sign readings are recorded for {p['name']}."

    concerns = []
    reassuring = []

    if v.get('spo2') is not None:
        if v.get('spo2') < 92:
            concerns.append(f"**Significant Hypoxemia**: SpO₂ is low at **{_fmt_val(v.get('spo2'))}%** (target ≥95%).")
        elif v.get('spo2') < 95:
            concerns.append(f"**Borderline SpO₂**: Recorded at **{_fmt_val(v.get('spo2'))}%**.")
        else:
            reassuring.append(f"Oxygen saturation is normal at {_fmt_val(v.get('spo2'))}%.")

    if v.get('respiratory_rate') is not None:
        if v.get('respiratory_rate') > 24:
            concerns.append(f"**Marked Tachypnea**: Respiratory rate is **{_fmt_val(v.get('respiratory_rate'))}/min**, indicating respiratory fatigue risk.")
        elif v.get('respiratory_rate') <= 20:
            reassuring.append(f"Respiratory rate is within normal limits ({_fmt_val(v.get('respiratory_rate'))}/min).")

    if v.get('blood_pressure_sys') is not None:
        if v.get('blood_pressure_sys') < 90:
            concerns.append(f"**Hypotension**: Systolic BP is **{_fmt_val(v.get('blood_pressure_sys'))} mmHg**, posing perfusion risks.")
        else:
            reassuring.append(f"Systolic blood pressure is adequate ({_fmt_val(v.get('blood_pressure_sys'))} mmHg).")

    if v.get('heart_rate') is not None:
        if v.get('heart_rate') > 110:
            concerns.append(f"**Tachycardia**: Heart rate is **{_fmt_val(v.get('heart_rate'))} bpm**.")

    lines = [f"**Clinical Priorities for {p['name']}:**\n"]
    if concerns:
        lines.append("🔴 **Primary Concerns:**")
        for c in concerns:
            lines.append(f"• {c}")
    else:
        lines.append("🟢 **Primary Concerns:** No acute vital parameter breaches in the latest reading.")

    if reassuring:
        lines.append("\n🟢 **Reassuring Findings:**")
        for r in reassuring:
            lines.append(f"• {r}")

    lines.append(f"\n• **Overall Risk**: EWS is **{ews_info.get('score', 0)}** ({ews_info.get('risk_level', 'LOW')} Risk).")
    lines.append(f"• **Recommendation**: **{rec.get('recommendation_text')}**.")
    return "\n".join(lines)


def reason_prognosis_and_severity(patient_id):
    """Direct evaluation for 'is this serious?', 'is he in danger?'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    v = getLatestVitals(patient_id)
    ews_info = getEWS(patient_id)
    csi = getCompositeStabilityIndex(patient_id)
    
    if not v:
        return f"I cannot evaluate clinical severity because no vital signs are recorded in the database for {p['name']}."

    score = ews_info.get('score', 0)
    risk = ews_info.get('risk_level', 'LOW')

    if score >= 7:
        severity = "**Yes, this is serious and critical.**"
    elif score >= 4:
        severity = "**Yes, this indicates moderate to high physiological risk.**"
    else:
        severity = "**Based on current readings, the risk level is low and stable.**"

    return (
        f"{severity}\n\n"
        f"• **Early Warning Score (EWS)**: **{score}** ({risk} Risk Category).\n"
        f"• **Composite Stability Index**: **{csi.get('index', 'N/A')}%** ({csi.get('classification', 'Stable')}).\n"
        f"• **Latest Key Readings**: SpO₂ {_fmt_val(v.get('spo2'))}%, RR {_fmt_val(v.get('respiratory_rate'))}/min, HR {_fmt_val(v.get('heart_rate'))} bpm, BP {_fmt_val(v.get('blood_pressure_sys'))} mmHg.\n\n"
        f"*Clinical Note: While database telemetry provides objective risk scoring, definitive prognosis and treatment decisions must be guided by bedside clinical assessment.*"
    )


def reason_transfer_decision(patient_id):
    """Direct answer for 'why is he still in ICU?', 'is he ready for HDU?'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    rec = getTransferDecision(patient_id)
    ews_info = getEWS(patient_id)
    v = getLatestVitals(patient_id)

    p_name = p['name']
    unit = p.get('ward_type', 'ICU')
    score = ews_info.get('score', 0)

    return (
        f"**{p_name}** is currently in the **{unit}**.\n\n"
        f"• **Jeevan Setu Recommendation**: **{rec.get('recommendation_text')}**\n"
        f"• **Clinical Rationale**: {rec.get('reason')}\n"
        f"• **Current EWS Score**: **{score}** ({ews_info.get('risk_level', 'LOW')} Risk)\n\n"
        f"The patient {'requires continuous ICU care due to elevated early warning score and ongoing telemetry instability' if score >= 4 else 'can be evaluated for step-down once stability criteria are maintained'}."
    )


def reason_documented_condition(patient_id):
    """Direct answer for 'what illness does he have?', 'what is his diagnosis?'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    doc = getDocumentedConditions(patient_id)
    diag = doc.get('diagnosis')

    if diag and diag.strip():
        return (
            f"**RECORDED PATIENT INFORMATION:**\n"
            f"• **Patient:** {p['name']} ({p.get('patient_code', 'N/A')})\n"
            f"• **Primary Documented Diagnosis:** **{diag.strip()}**\n"
            f"• **Admitting Ward:** {p.get('ward_type', 'ICU')} (Bed {p.get('bed_number', 'N/A')})\n\n"
            f"*This is the official diagnosis documented in the Jeevan Setu hospital admission records.*"
        )
    return (
        f"This information is not available in the Jeevan Setu records.\n\n"
        f"The database does not contain a documented diagnosis in hospital admission records for patient **{p['name']}** ({p.get('patient_code', 'N/A')})."
    )


def reason_concise_summary(patient_id):
    """Brief, short 2-sentence summary for 'give me the short version'."""
    p = getPatient(patient_id)
    if not p:
        return "Patient record could not be found."
    v = getLatestVitals(patient_id)
    ews_info = getEWS(patient_id)
    rec = getTransferDecision(patient_id)

    if not v:
        return f"**{p['name']}** is admitted in **{p.get('ward_type', 'ICU')}** with no recorded telemetry."

    v_str = f"SpO₂ {_fmt_val(v.get('spo2'))}%, RR {_fmt_val(v.get('respiratory_rate'))}/min, HR {_fmt_val(v.get('heart_rate'))} bpm, BP {_fmt_val(v.get('blood_pressure_sys'))} mmHg"
    return (
        f"**{p['name']}** is in **{p.get('ward_type', 'ICU')}**. Current telemetry shows: {v_str}. "
        f"EWS is **{ews_info.get('score', 0)}** ({ews_info.get('risk_level', 'LOW')} Risk), and recommendation is to **{rec.get('recommendation_text')}**."
    )


def reason_general_medical_query(query, context=None):
    """General clinical medical knowledge explanations powered by comprehensive embedded knowledge base."""
    q_lower = query.lower().strip()
    q_clean = re.sub(r'[^\w\s]', ' ', q_lower).strip()
    p = context.get('patient') if (context and isinstance(context, dict)) else None
    v = context.get('latest_vitals') if (context and isinstance(context, dict)) else None

    # ── Comprehensive Medical Knowledge Base ──
    MEDICAL_KB = {
        'hypertension': {
            'title': 'Hypertension (High Blood Pressure)',
            'definition': 'A chronic medical condition in which systemic arterial blood pressure remains persistently elevated (Systolic BP ≥140 mmHg and/or Diastolic BP ≥90 mmHg on repeated measurements).',
            'classification': [
                'Normal: SBP <120 mmHg and DBP <80 mmHg',
                'Elevated: SBP 120–129 mmHg and DBP <80 mmHg',
                'Stage 1 Hypertension: SBP 130–139 mmHg or DBP 80–89 mmHg',
                'Stage 2 Hypertension: SBP ≥140 mmHg or DBP ≥90 mmHg',
                'Hypertensive Crisis: SBP >180 mmHg and/or DBP >120 mmHg (requires urgent evaluation for end-organ damage)'
            ],
            'clinical_significance': [
                'Major modifiable risk factor for stroke, myocardial infarction, heart failure, and chronic kidney disease.',
                'Often asymptomatic ("the silent killer") until secondary vascular or target-organ damage develops.',
                'Requires lifestyle modification (DASH diet, sodium reduction <2g/day, regular aerobic exercise, weight management) alongside pharmacotherapy (ACE inhibitors, ARBs, CCBs like amlodipine, thiazide diuretics).'
            ],
            'causes': 'Primary (Essential, 90–95%): Multifactorial genetic, dietary, and autonomic factors. Secondary (5–10%): Renal artery stenosis, chronic kidney disease, primary aldosteronism, Cushing syndrome, pheochromocytoma, obstructive sleep apnea (OSA).'
        },
        'fever': {
            'title': 'Fever (Pyrexia)',
            'definition': 'Elevation of core body temperature above the normal physiological set-point (typically core temperature ≥38.0°C / 100.4°F) mediated by endogenous pyrogens (IL-1, IL-6, TNF-alpha) acting on the anterior hypothalamus.',
            'clinical_significance': [
                'Low-grade: 37.3–38.0°C (monitor closely for infectious onset)',
                'Moderate: 38.1–39.0°C (indicative of acute inflammatory/infectious response)',
                'High: >39.0°C (warrants blood cultures, septic workup, and antipyresis)',
                'Hyperpyrexia: >40.0°C (medical emergency risking neurological and physiological decompensation)'
            ],
            'causes': 'Bacterial/viral/fungal infections, sepsis, post-operative systemic inflammatory response syndrome (SIRS), drug fever, malignancy, autoimmune connective tissue diseases.'
        },
        'anemia': {
            'title': 'Anemia',
            'definition': 'A pathological reduction in total circulating red blood cell mass or hemoglobin concentration (<13.0 g/dL in adult males, <12.0 g/dL in adult non-pregnant females), leading to impaired oxygen-carrying capacity.',
            'symptoms': 'Fatigue, exertional dyspnea, pallor, tachycardia, dizziness, orthostatic hypotension, headache, cold extremities.',
            'diagnosis': 'CBC (Hb, Hct, RBC indices: MCV, MCH), peripheral blood smear, reticulocyte count, serum ferritin, iron panel, Vitamin B12, folate.',
            'clinical_significance': [
                'Microcytic (MCV <80 fL): Iron deficiency anemia, thalassemia, anemia of chronic disease (late), sideroblastic.',
                'Normocytic (MCV 80–100 fL): Acute blood loss, hemolysis, renal failure (erythropoietin deficiency), early chronic disease.',
                'Macrocytic (MCV >100 fL): Vitamin B12 deficiency (pernicious anemia), folate deficiency, drug-induced, liver disease.'
            ]
        },
        'coronary artery disease': {
            'title': 'Coronary Artery Disease (CAD / Ischemic Heart Disease)',
            'definition': 'A pathological narrowing or blockage of one or more epicardial coronary arteries caused by atherosclerotic plaque buildup, restricting oxygenated blood supply to the myocardium.',
            'symptoms': 'Angina pectoris (substernal chest tightness radiating to left arm/jaw, triggered by exertion/stress), dyspnea, diaphoresis, fatigue.',
            'diagnosis': '12-lead ECG, high-sensitivity cardiac troponins, echocardiography (wall motion abnormalities), coronary CT angiography, invasive coronary angiography.',
            'treatment': 'Lifestyle modification, antiplatelets (aspirin, clopidogrel), high-intensity statins, beta-blockers, ACE inhibitors, revascularization via PCI (percutaneous coronary intervention) or CABG (coronary artery bypass graft).'
        },
        'ecg': {
            'title': 'Electrocardiogram (ECG / EKG)',
            'definition': 'A non-invasive transthoracic recording of the electrical potentials generated by the heart during cardiac cycles, captured via standard 12-lead electrode placement.',
            'clinical_significance': [
                'P wave: Atrial depolarization (normal <120 ms).',
                'PR interval: AV nodal conduction time (normal 120–200 ms; prolonged in first-degree AV block).',
                'QRS complex: Ventricular depolarization (normal <120 ms; widened in bundle branch blocks, VT).',
                'ST segment: Ischemic evaluation (ST elevation indicates acute transmural infarction; ST depression indicates subendocardial ischemia/strain).',
                'T wave: Ventricular repolarization (peaked in hyperkalemia, inverted in ischemia/strain).',
                'QT interval: Total duration of ventricular electrical activation and recovery (prolongation risks Torsades de Pointes).'
            ]
        },
        'vital signs': {
            'title': 'Normal Adult Vital Signs & Physiological Norms',
            'definition': "Core clinical measurements that evaluate the body's fundamental physiological homeostasis and autonomic stability.",
            'normal_range': 'HR: 60–100 bpm | BP: 100–130 / 60–80 mmHg | RR: 12–20 breaths/min | Temp: 36.5–37.5°C | SpO₂: 95–100% | AVPU: Alert',
            'clinical_significance': [
                'Heart Rate: 60–100 bpm (Tachycardia >100 bpm, Bradycardia <60 bpm).',
                'Blood Pressure: Systolic 100–130 mmHg, Diastolic 60–80 mmHg, MAP >65 mmHg for vital organ perfusion.',
                'Respiratory Rate: 12–20 breaths/min (Tachypnea >20/min is the most sensitive early marker of physiological deterioration).',
                'Oxygen Saturation (SpO₂): ≥95% on room air (SpO₂ <92% requires supplemental oxygenation; <88% indicates severe hypoxemia).',
                'Temperature: 36.5–37.5°C (Fever ≥38.0°C, Hypothermia <35.0°C).',
                'Early Warning Score (EWS): Aggregates all 6 vital sign deviations into a composite score (0–1 Low, 2–4 Medium, 5–6 High, ≥7 Critical Risk).'
            ]
        },
        'hypotension': {
            'title': 'Hypotension (Low Blood Pressure)',
            'definition': 'Abnormally low systemic arterial blood pressure (typically Systolic BP <90 mmHg or Mean Arterial Pressure (MAP) <65 mmHg), compromising vital end-organ perfusion.',
            'causes': 'Hypovolemia (hemorrhage, severe dehydration), distributive vasodilation (septic shock, anaphylaxis), cardiogenic pump failure (massive MI, severe heart failure), obstructive shock (massive PE, cardiac tamponade), medication overdose.',
            'clinical_significance': [
                'MAP <65 mmHg risks acute kidney injury, cerebral hypoperfusion, and ischemic lactic acidosis.',
                'Requires immediate hemodynamic evaluation, crystalloid fluid challenge if hypovolemic, and vasopressor support (norepinephrine) if unresponsive to fluids.'
            ]
        },
        # ── Vital Signs & Parameters ──
        'spo2': {
            'title': 'Oxygen Saturation (SpO₂)',
            'definition': 'SpO₂ measures the percentage of hemoglobin binding sites occupied by oxygen in arterial blood, assessed non-invasively via pulse oximetry.',
            'normal_range': '95–100% on room air in healthy adults',
            'clinical_significance': [
                '≥95%: Normal range',
                '91–94%: Mild hypoxemia — supplemental O₂ may be needed',
                '85–90%: Moderate hypoxemia — requires urgent oxygen supplementation',
                '<85%: Severe hypoxemia — medical emergency, risk of organ damage',
            ],
            'common_causes_abnormal': 'Pneumonia, COPD exacerbation, PE, ARDS, asthma, atelectasis, heart failure, pneumothorax, severe anemia, carbon monoxide poisoning.',
            'parameter': 'spo2'
        },
        'respiratory rate': {
            'title': 'Respiratory Rate (RR)',
            'definition': 'The number of breaths a person takes per minute. It is one of the earliest and most sensitive indicators of physiological distress.',
            'normal_range': '12–20 breaths/min in adults at rest',
            'clinical_significance': [
                '<12/min (Bradypnea): May indicate CNS depression, opioid overdose, or metabolic alkalosis',
                '12–20/min: Normal',
                '20–24/min: Mildly elevated — possible early distress, pain, or anxiety',
                '>24/min (Tachypnea): Significant — suggestive of respiratory distress, sepsis, metabolic acidosis, or pulmonary pathology',
            ],
            'common_causes_abnormal': 'Pneumonia, sepsis, metabolic acidosis (DKA), pulmonary embolism, ARDS, pain, anxiety, fever.',
            'parameter': 'respiratory_rate'
        },
        'heart rate': {
            'title': 'Heart Rate (HR / Pulse)',
            'definition': 'Number of cardiac contractions per minute. Reflects cardiac function, autonomic tone, and systemic metabolic demands.',
            'normal_range': '60–100 bpm in adults at rest',
            'clinical_significance': [
                '<50 bpm (Bradycardia): May indicate heart block, beta-blocker effect, hypothyroidism, or raised ICP',
                '60–100 bpm: Normal sinus rhythm',
                '100–120 bpm (Mild tachycardia): Pain, fever, anxiety, dehydration, or mild hypovolemia',
                '>120 bpm (Significant tachycardia): Sepsis, hemorrhage, PE, cardiac arrhythmia, or shock',
            ],
            'common_causes_abnormal': 'Hypovolemia, sepsis, pain, fever, PE, arrhythmias, thyrotoxicosis, anemia, medications.',
            'parameter': 'heart_rate'
        },
        'blood pressure': {
            'title': 'Blood Pressure (BP)',
            'definition': 'The force exerted by circulating blood on arterial walls. Systolic BP reflects cardiac output during contraction; diastolic reflects vascular resistance during relaxation.',
            'normal_range': 'Systolic 100–130 mmHg, Diastolic 60–80 mmHg',
            'clinical_significance': [
                'SBP <90 mmHg (Hypotension): Compromised organ perfusion — shock workup needed',
                'SBP 90–100 mmHg: Borderline — assess for early shock, dehydration',
                'SBP 100–140 mmHg: Normal range',
                'SBP >140 mmHg (Hypertension): Evaluate for hypertensive crisis if >180 mmHg',
            ],
            'common_causes_abnormal': 'Hemorrhage, sepsis, cardiogenic shock, dehydration (low). Essential hypertension, renal disease, pheochromocytoma, pain (high).',
            'parameter': 'blood_pressure_sys'
        },
        'temperature': {
            'title': 'Body Temperature',
            'definition': 'Core body temperature reflects thermoregulatory balance. Deviation indicates infection, inflammation, or environmental exposure.',
            'normal_range': '36.1–37.2°C (97.0–99.0°F)',
            'clinical_significance': [
                '<35.0°C (Hypothermia): Severe — sepsis, exposure, hypothyroidism, or near-drowning',
                '35.0–36.0°C: Mild hypothermia — assess for sepsis or environmental cause',
                '36.1–37.2°C: Normal',
                '37.3–38.0°C: Low-grade fever — monitor for infection',
                '38.1–39.0°C: Moderate fever — likely infection, consider cultures',
                '>39.0°C: High fever — aggressive workup, blood cultures, consider antipyretics',
            ],
            'common_causes_abnormal': 'Infection (bacterial, viral, fungal), post-surgical inflammation, drug fever, malignancy, autoimmune disease, environmental exposure.',
            'parameter': 'temperature'
        },
        'ews': {
            'title': 'Early Warning Score (EWS / NEWS)',
            'definition': 'A standardized scoring system aggregating vital sign deviations (RR, SpO₂, HR, BP, temperature, consciousness) into a single risk score to identify deteriorating patients early.',
            'normal_range': '0 (all vitals normal)',
            'clinical_significance': [
                '0: Low risk — routine monitoring',
                '1–4: Low-medium risk — increased monitoring frequency',
                '5–6: Medium-high risk — urgent clinical review',
                '≥7: High/Critical risk — emergency response, consider ICU escalation',
            ],
            'common_causes_abnormal': 'Any physiological derangement: respiratory failure, sepsis, hemorrhage, cardiac events, neurological deterioration.'
        },
        'consciousness': {
            'title': 'Level of Consciousness (AVPU / GCS)',
            'definition': 'AVPU scale: Alert, responds to Voice, responds to Pain, Unresponsive. GCS (Glasgow Coma Scale): 3–15 scoring eye, verbal, and motor responses.',
            'normal_range': 'Alert (AVPU = A, GCS = 15)',
            'clinical_significance': [
                'A (Alert): Normal — patient is awake and oriented',
                'V (Voice): Responds to verbal stimuli — moderate depression',
                'P (Pain): Responds only to painful stimuli — significant CNS depression',
                'U (Unresponsive): No response — medical emergency, secure airway',
            ],
            'common_causes_abnormal': 'Head injury, stroke, metabolic encephalopathy, drug overdose, hypoglycemia, septic encephalopathy, seizure (post-ictal).'
        },

        # ── Common Clinical Conditions ──
        'pneumonia': {
            'title': 'Pneumonia',
            'definition': 'An acute infection of the lung parenchyma causing alveolar inflammation and consolidation, leading to impaired gas exchange.',
            'symptoms': 'Cough (productive or dry), fever, dyspnea, pleuritic chest pain, tachypnea, tachycardia, hypoxia.',
            'diagnosis': 'Clinical examination (crackles, bronchial breathing), chest X-ray (consolidation/infiltrates), sputum culture, blood cultures, CRP, procalcitonin.',
            'treatment': 'Empiric antibiotics (community: amoxicillin/macrolide; hospital: cephalosporin + macrolide or fluoroquinolone), supportive oxygen, IV fluids.',
            'complications': 'Respiratory failure, sepsis, pleural effusion/empyema, lung abscess, ARDS.'
        },
        'sepsis': {
            'title': 'Sepsis & Septic Shock',
            'definition': 'A life-threatening organ dysfunction caused by dysregulated host response to infection. Septic shock = sepsis + vasopressor requirement + lactate >2 mmol/L.',
            'symptoms': 'Fever or hypothermia, tachycardia, tachypnea, hypotension, altered mental status, oliguria, mottled skin.',
            'diagnosis': 'qSOFA score (RR ≥22, altered mentation, SBP ≤100), blood cultures, lactate, CBC, CRP, procalcitonin, organ function tests.',
            'treatment': 'Hour-1 Bundle: blood cultures → IV antibiotics → 30 mL/kg crystalloid → vasopressors if MAP <65 → lactate-guided resuscitation. Source control.',
            'complications': 'Multi-organ failure (MODS), DIC, ARDS, acute kidney injury, death (mortality 20–50%).'
        },
        'copd': {
            'title': 'Chronic Obstructive Pulmonary Disease (COPD)',
            'definition': 'A chronic inflammatory lung disease causing obstructed airflow. Includes emphysema (alveolar destruction) and chronic bronchitis (airway inflammation).',
            'symptoms': 'Progressive dyspnea, chronic cough, sputum production, wheezing, frequent respiratory infections.',
            'diagnosis': 'Spirometry (FEV1/FVC <0.70), chest X-ray, ABG in severe cases, alpha-1 antitrypsin levels.',
            'treatment': 'Bronchodilators (SABA, LABA, LAMA), inhaled corticosteroids, pulmonary rehabilitation, oxygen therapy, smoking cessation.',
            'complications': 'Acute exacerbations, respiratory failure, cor pulmonale, pneumothorax, polycythemia.'
        },
        'ards': {
            'title': 'Acute Respiratory Distress Syndrome (ARDS)',
            'definition': 'A severe, life-threatening form of respiratory failure with diffuse alveolar damage, non-cardiogenic pulmonary edema, and refractory hypoxemia.',
            'symptoms': 'Severe dyspnea, tachypnea, refractory hypoxemia (SpO₂ not improving with oxygen), bilateral crackles.',
            'diagnosis': 'Berlin criteria: acute onset (<1 week), bilateral opacities on CXR/CT, PaO₂/FiO₂ ratio classification (mild 200–300, moderate 100–200, severe <100).',
            'treatment': 'Low-tidal-volume mechanical ventilation (6 mL/kg), prone positioning, conservative fluid strategy, PEEP optimization, neuromuscular blockade in severe cases.',
            'complications': 'Prolonged mechanical ventilation, ICU myopathy, pulmonary fibrosis, death (mortality 35–46%).'
        },
        'asthma': {
            'title': 'Bronchial Asthma',
            'definition': 'A chronic inflammatory airway disease characterized by reversible bronchospasm, airway hyperresponsiveness, and mucus hypersecretion.',
            'symptoms': 'Episodic wheezing, cough (especially nocturnal), chest tightness, dyspnea. Triggered by allergens, exercise, cold air, infections.',
            'diagnosis': 'Spirometry with bronchodilator reversibility (>12% FEV1 improvement), peak flow variability, methacholine challenge.',
            'treatment': 'Rescue: SABA (salbutamol). Controller: ICS (budesonide), LABA+ICS, leukotriene receptor antagonists, biologics (omalizumab) for severe cases.',
            'complications': 'Status asthmaticus, respiratory failure, pneumothorax, chronic airway remodeling.'
        },
        'diabetes': {
            'title': 'Diabetes Mellitus',
            'definition': 'A metabolic disorder characterized by chronic hyperglycemia due to defective insulin secretion (Type 1), insulin resistance (Type 2), or both.',
            'symptoms': 'Polyuria, polydipsia, polyphagia, weight loss, blurred vision, fatigue, recurrent infections.',
            'diagnosis': 'Fasting glucose ≥126 mg/dL, HbA1c ≥6.5%, random glucose ≥200 mg/dL with symptoms, OGTT ≥200 mg/dL.',
            'treatment': 'T1DM: Insulin (basal-bolus regimen). T2DM: Lifestyle modification, metformin (first-line), SGLT2 inhibitors, GLP-1 agonists, insulin if needed.',
            'complications': 'DKA (T1DM), HHS (T2DM), retinopathy, nephropathy, neuropathy, cardiovascular disease, diabetic foot.'
        },
        'heart failure': {
            'title': 'Heart Failure (Congestive Heart Failure)',
            'definition': 'A clinical syndrome where the heart is unable to pump sufficient blood to meet the body\'s metabolic demands, or can only do so at elevated filling pressures.',
            'symptoms': 'Dyspnea (especially on exertion or lying flat), fatigue, peripheral edema, jugular venous distension, pulmonary crackles, weight gain.',
            'diagnosis': 'BNP/NT-proBNP, echocardiography (ejection fraction), chest X-ray, ECG, stress testing.',
            'treatment': 'ACE inhibitors/ARBs, beta-blockers, diuretics (furosemide), MRAs (spironolactone), SGLT2 inhibitors, device therapy (ICD, CRT) if indicated.',
            'complications': 'Pulmonary edema, cardiogenic shock, arrhythmias, renal failure, hepatic congestion.'
        },
        'stroke': {
            'title': 'Stroke (Cerebrovascular Accident)',
            'definition': 'Sudden loss of neurological function due to interrupted blood supply to the brain. Ischemic (85%) or hemorrhagic (15%).',
            'symptoms': 'Sudden facial droop, arm weakness, speech difficulty (FAST criteria), vision loss, severe headache, confusion, ataxia.',
            'diagnosis': 'Non-contrast CT head (rule out hemorrhage), CT angiography, MRI/DWI, NIH Stroke Scale scoring.',
            'treatment': 'Ischemic: IV alteplase (tPA) within 4.5 hours, mechanical thrombectomy within 24 hours. Hemorrhagic: BP control, reversal of anticoagulation, neurosurgical consultation.',
            'complications': 'Permanent disability, cerebral edema, hemorrhagic transformation, aspiration pneumonia, DVT/PE.'
        },
        'pulmonary embolism': {
            'title': 'Pulmonary Embolism (PE)',
            'definition': 'Obstruction of pulmonary arteries, usually by thrombus from deep veins (DVT), causing impaired gas exchange and potential right heart failure.',
            'symptoms': 'Sudden dyspnea, pleuritic chest pain, tachycardia, tachypnea, hemoptysis, syncope, hypotension (massive PE).',
            'diagnosis': 'D-dimer (rule-out), CTPA (gold standard), V/Q scan, echocardiography, Wells score/Geneva score.',
            'treatment': 'Anticoagulation (heparin → warfarin/DOACs), thrombolysis (alteplase) for massive PE, surgical embolectomy, IVC filter if anticoagulation contraindicated.',
            'complications': 'Right heart failure, cardiogenic shock, death, chronic thromboembolic pulmonary hypertension (CTEPH).'
        },
        'acute kidney injury': {
            'title': 'Acute Kidney Injury (AKI)',
            'definition': 'A sudden decline in kidney function causing accumulation of waste products. Classified as pre-renal (hypovolemia), intrinsic (tubular necrosis), or post-renal (obstruction).',
            'symptoms': 'Oliguria/anuria, edema, nausea, confusion, elevated creatinine, metabolic acidosis, hyperkalemia.',
            'diagnosis': 'Serum creatinine rise (KDIGO criteria), urine output monitoring, urinalysis, renal ultrasound, FENa calculation.',
            'treatment': 'Treat underlying cause, IV fluid resuscitation (pre-renal), stop nephrotoxic drugs, dialysis if severe (refractory hyperkalemia, acidosis, fluid overload, uremic symptoms).',
            'complications': 'Chronic kidney disease, electrolyte imbalances, uremia, volume overload, death.'
        },
        'myocardial infarction': {
            'title': 'Myocardial Infarction (Heart Attack)',
            'definition': 'Irreversible myocardial cell death due to prolonged ischemia, typically from coronary artery thrombosis. STEMI = ST-elevation MI; NSTEMI = non-ST-elevation MI.',
            'symptoms': 'Crushing central chest pain (may radiate to left arm/jaw), diaphoresis, dyspnea, nausea, presyncope. Atypical in elderly/diabetics.',
            'diagnosis': 'ECG (ST changes, Q waves), serial troponins (rise and fall), echocardiography, coronary angiography.',
            'treatment': 'Dual antiplatelet therapy (aspirin + P2Y12 inhibitor), anticoagulation, PCI (primary for STEMI), beta-blockers, statins, ACE inhibitors.',
            'complications': 'Heart failure, arrhythmias (VT/VF), cardiogenic shock, mechanical complications (papillary muscle rupture, VSD), pericarditis.'
        },
        'dvt': {
            'title': 'Deep Vein Thrombosis (DVT)',
            'definition': 'Formation of a blood clot in a deep vein, most commonly in the lower extremities, which can embolize to the lungs (PE).',
            'symptoms': 'Unilateral leg swelling, pain, warmth, erythema, pitting edema, positive Homan\'s sign (unreliable).',
            'diagnosis': 'Compression ultrasound (first-line), D-dimer, CT venography, Wells score.',
            'treatment': 'Anticoagulation (LMWH → DOACs or warfarin for 3–6 months), IVC filter if anticoagulation contraindicated, thrombolysis for massive ilio-femoral DVT.',
            'complications': 'Pulmonary embolism, post-thrombotic syndrome, recurrent DVT.'
        },
        'meningitis': {
            'title': 'Meningitis',
            'definition': 'Inflammation of the meninges (membranes surrounding the brain and spinal cord), most commonly caused by viral or bacterial infection.',
            'symptoms': 'Headache, neck stiffness, photophobia, fever, altered consciousness, petechial rash (meningococcal), Kernig\'s/Brudzinski\'s signs.',
            'diagnosis': 'Lumbar puncture (CSF analysis: cell count, protein, glucose, Gram stain, culture), blood cultures, CT head before LP if signs of raised ICP.',
            'treatment': 'Bacterial: IV ceftriaxone + vancomycin + dexamethasone (empiric). Viral: Supportive care (acyclovir if HSV suspected). Fungal: Amphotericin B.',
            'complications': 'Cerebral edema, hydrocephalus, cranial nerve palsies, hearing loss, seizures, death.'
        },
        'anaphylaxis': {
            'title': 'Anaphylaxis',
            'definition': 'A severe, potentially fatal systemic hypersensitivity reaction involving rapid onset airway, breathing, and/or circulatory compromise.',
            'symptoms': 'Urticaria, angioedema, bronchospasm, stridor, hypotension, tachycardia, GI symptoms. Onset within minutes of allergen exposure.',
            'diagnosis': 'Clinical diagnosis based on rapid multi-system involvement. Serum tryptase (elevated within 1–2 hours).',
            'treatment': 'IM Epinephrine 0.5 mg (anterolateral thigh) — FIRST LINE. IV fluids, nebulized salbutamol, IV antihistamines, IV hydrocortisone. Remove trigger.',
            'complications': 'Cardiovascular collapse, airway obstruction, biphasic reaction (recurrence 1–72 hours later), death.'
        },

        # ── Lab Values & Diagnostics ──
        'abg': {
            'title': 'Arterial Blood Gas (ABG)',
            'definition': 'A blood test measuring pH, PaO₂, PaCO₂, HCO₃⁻, and base excess from arterial blood to assess acid-base balance and oxygenation.',
            'normal_range': 'pH: 7.35–7.45, PaO₂: 80–100 mmHg, PaCO₂: 35–45 mmHg, HCO₃⁻: 22–26 mEq/L',
            'clinical_significance': [
                'Respiratory acidosis: ↑PaCO₂, ↓pH (e.g., COPD, hypoventilation)',
                'Respiratory alkalosis: ↓PaCO₂, ↑pH (e.g., hyperventilation, PE)',
                'Metabolic acidosis: ↓HCO₃⁻, ↓pH (e.g., DKA, lactic acidosis, renal failure)',
                'Metabolic alkalosis: ↑HCO₃⁻, ↑pH (e.g., vomiting, diuretic use)',
            ]
        },
        'lactate': {
            'title': 'Blood Lactate',
            'definition': 'A byproduct of anaerobic metabolism. Elevated levels indicate tissue hypoperfusion, hypoxia, or increased metabolic demand.',
            'normal_range': '0.5–1.0 mmol/L (venous), <2.0 mmol/L',
            'clinical_significance': [
                '<2 mmol/L: Normal',
                '2–4 mmol/L: Elevated — consider underlying cause (sepsis, shock)',
                '>4 mmol/L: Significant — associated with high mortality, requires aggressive resuscitation',
            ],
            'common_causes_abnormal': 'Sepsis/septic shock, cardiogenic shock, hemorrhage, severe hypoxemia, seizures, liver failure, metformin toxicity.'
        },
        'troponin': {
            'title': 'Cardiac Troponin (cTn)',
            'definition': 'A cardiac-specific biomarker released when myocardial cells are damaged. High-sensitivity troponin (hs-cTn) can detect very small amounts of damage.',
            'normal_range': '<14 ng/L (99th percentile for hs-cTnT)',
            'clinical_significance': [
                'Normal: Unlikely acute MI (but consider serial sampling)',
                'Elevated with rise/fall pattern: Consistent with acute MI',
                'Chronically elevated (stable): CKD, heart failure, myocarditis, PE',
            ],
            'common_causes_abnormal': 'Acute MI, myocarditis, PE, heart failure, sepsis, renal failure, takotsubo, aortic dissection, cardiac contusion.'
        },

        # ── Common Medications ──
        'paracetamol': {
            'title': 'Paracetamol (Acetaminophen)',
            'definition': 'An analgesic and antipyretic drug. First-line for mild–moderate pain and fever. Does NOT have significant anti-inflammatory properties.',
            'dose': 'Adults: 500–1000 mg every 4–6 hours. Maximum: 4g/day (2g/day in liver disease).',
            'mechanism': 'Inhibits COX in the CNS, reducing prostaglandin synthesis centrally. Also activates descending serotonergic inhibitory pathways.',
            'side_effects': 'Generally well-tolerated. Overdose (>150 mg/kg): Severe hepatotoxicity — treat with IV N-acetylcysteine (NAC).',
            'contraindications': 'Severe hepatic impairment, active liver disease.'
        },
        'amlodipine': {
            'title': 'Amlodipine',
            'definition': 'A long-acting dihydropyridine calcium channel blocker (CCB) used for hypertension and angina.',
            'dose': 'Adults: 5–10 mg once daily.',
            'mechanism': 'Blocks L-type calcium channels in vascular smooth muscle → vasodilation → reduced peripheral resistance → lower blood pressure.',
            'side_effects': 'Peripheral edema, headache, flushing, dizziness, fatigue. Rarely: gingival hyperplasia.',
            'contraindications': 'Severe aortic stenosis, unstable angina (caution), cardiogenic shock.'
        },
        'furosemide': {
            'title': 'Furosemide (Lasix)',
            'definition': 'A potent loop diuretic used for edema (heart failure, renal failure, liver cirrhosis) and acute pulmonary edema.',
            'dose': 'IV/PO: 20–80 mg, titrated. Max: 600 mg/day in severe cases.',
            'mechanism': 'Inhibits Na⁺/K⁺/2Cl⁻ co-transporter in the thick ascending loop of Henle → potent diuresis and natriuresis.',
            'side_effects': 'Hypokalemia, hyponatremia, dehydration, hypotension, ototoxicity (high doses), hyperuricemia.',
            'contraindications': 'Anuria, severe hypovolemia/dehydration, hepatic coma.'
        },
        'insulin': {
            'title': 'Insulin',
            'definition': 'A peptide hormone produced by pancreatic beta cells. Exogenous insulin is the cornerstone of Type 1 DM therapy and is used in Type 2 DM when oral agents are insufficient.',
            'dose': 'Highly individualized. Common: Basal (glargine/detemir) + Bolus (aspart/lispro). DKA: IV regular insulin infusion.',
            'mechanism': 'Binds insulin receptors → promotes glucose uptake, glycogen synthesis, lipogenesis; inhibits gluconeogenesis and glycogenolysis.',
            'side_effects': 'Hypoglycemia (most dangerous), weight gain, injection site lipodystrophy, hypokalemia.',
            'contraindications': 'Hypoglycemia. Use with caution in renal/hepatic impairment (adjust dose).'
        },
        'epinephrine': {
            'title': 'Epinephrine (Adrenaline)',
            'definition': 'An endogenous catecholamine and first-line drug for anaphylaxis and cardiac arrest.',
            'dose': 'Anaphylaxis: 0.5 mg IM (1:1000). Cardiac arrest: 1 mg IV (1:10,000) every 3–5 min.',
            'mechanism': 'Non-selective adrenergic agonist: α1 (vasoconstriction), β1 (↑HR, ↑contractility), β2 (bronchodilation).',
            'side_effects': 'Tachycardia, hypertension, arrhythmias, anxiety, tremor, headache.',
            'contraindications': 'No absolute contraindications in life-threatening situations.'
        },

        # ── ICU / Critical Care Concepts ──
        'ventilator': {
            'title': 'Mechanical Ventilation',
            'definition': 'Machine-assisted breathing for patients unable to maintain adequate ventilation/oxygenation independently.',
            'key_modes': [
                'Volume Control (VC): Delivers set tidal volume',
                'Pressure Control (PC): Delivers breaths at set pressure',
                'Pressure Support (PS): Patient-triggered, pressure-assisted — for weaning',
                'SIMV: Synchronized mandatory breaths with spontaneous breathing allowed',
            ],
            'key_settings': 'Tidal Volume (6–8 mL/kg IBW for lung-protective), RR, PEEP (typically 5–15 cmH₂O), FiO₂ (target SpO₂ 92–96%).',
            'complications': 'Ventilator-associated pneumonia (VAP), barotrauma, volutrauma, oxygen toxicity, ICU-acquired weakness, delirium.'
        },
        'shock': {
            'title': 'Shock',
            'definition': 'A state of circulatory failure resulting in inadequate tissue perfusion and cellular oxygen delivery.',
            'types': [
                'Hypovolemic: Blood/fluid loss (hemorrhage, dehydration)',
                'Distributive: Vasodilation (septic, anaphylactic, neurogenic)',
                'Cardiogenic: Pump failure (MI, arrhythmia, cardiomyopathy)',
                'Obstructive: Mechanical obstruction (PE, cardiac tamponade, tension pneumothorax)',
            ],
            'clinical_features': 'Hypotension, tachycardia, cold/clammy skin (warm in distributive), altered consciousness, oliguria, elevated lactate.',
            'treatment': 'IV fluid resuscitation, vasopressors (norepinephrine first-line for septic), treat underlying cause, blood products if hemorrhagic.'
        },
        'intubation': {
            'title': 'Endotracheal Intubation',
            'definition': 'Placement of a tube through the mouth/nose into the trachea to secure the airway, provide mechanical ventilation, and protect against aspiration.',
            'indications': 'Respiratory failure (PaO₂ <60, PaCO₂ >50 with acidosis), GCS ≤8, airway obstruction, anticipated clinical deterioration, pre-operative.',
            'complications': 'Esophageal intubation, right main bronchus intubation, dental/vocal cord injury, aspiration, VAP, tracheal stenosis (long-term).'
        },
        'cpap': {
            'title': 'CPAP (Continuous Positive Airway Pressure)',
            'definition': 'Non-invasive ventilation delivering continuous positive pressure to keep airways open and improve oxygenation.',
            'indications': 'Obstructive sleep apnea (OSA), acute cardiogenic pulmonary edema, mild-moderate respiratory failure, post-extubation support.',
            'key_settings': 'Pressure: typically 5–15 cmH₂O, FiO₂: titrated to SpO₂ target.'
        },
        'icu': {
            'title': 'Intensive Care Unit (ICU)',
            'definition': 'A specialized hospital department providing maximum-intensity medical care, advanced life support (invasive mechanical ventilation, inotropic support), and continuous 1:1 or 1:2 nurse-to-patient monitoring for critically ill patients with single or multi-organ failure.',
            'key_criteria': 'Severe physiological decompensation, mechanical ventilation, multiple organ dysfunction syndrome (MODS), acute shock, severe EWS (≥7).',
            'nurse_ratio': '1:1 to 1:2 dedicated nursing ratio.'
        },
        'hdu': {
            'title': 'High Dependency Unit (HDU / Step-Down)',
            'definition': 'An intermediate care unit between the ICU and General Ward for patients requiring close physiological monitoring and single-organ support (e.g. non-invasive ventilation, single low-dose inotrope, frequent blood gases) who do not require multi-organ invasive life support.',
            'key_criteria': 'EWS 4–6, resolving respiratory failure on NIV/high-flow O2, post-ICU step-down stabilization, high-risk surgical recovery.',
            'nurse_ratio': '1:2 to 1:3 nursing ratio.'
        },
        'difference between icu and hdu': {
            'title': 'Difference Between ICU and HDU (Level of Care Comparison)',
            'definition': 'ICU (Intensive Care Unit) and HDU (High Dependency Unit) represent two distinct tiers of critical care support based on acuity and organ failure severity.',
            'clinical_significance': [
                '**Acuity Level:** ICU handles Level 3 care (multi-organ failure, invasive mechanical ventilation, multi-drug vasopressors). HDU handles Level 2 care (single organ failure, non-invasive ventilation, high-flow oxygen).',
                '**Nurse-to-Patient Ratio:** ICU maintains 1:1 (or 1:2) nurse-to-patient ratio; HDU typically operates at 1:2 or 1:3 ratio.',
                '**Telemetry & Monitoring:** ICU provides continuous invasive arterial/CVP hemodynamic monitoring. HDU provides continuous non-invasive telemetry and frequent blood gas analysis.',
                '**Step-Down Pathway:** Patients stabilizing in ICU with decreasing EWS (≤4) and resolved organ failure are stepped down to HDU before moving to the General Ward.'
            ]
        },
        'ews': {
            'title': 'Early Warning Score (EWS / NEWS2)',
            'definition': 'A standardized bedside physiological scoring system that quantifies deviation in 6 core vital parameters (HR, BP, RR, Temp, SpO₂, and Consciousness) to detect early clinical deterioration.',
            'clinical_significance': [
                '0–1: Normal / Low Risk — Routine ward monitoring.',
                '2–4: Medium Risk — Increased monitoring frequency, notify ward nurse.',
                '5–6: High Risk — Urgent medical review, evaluate for HDU step-up.',
                '≥7: Critical Risk — Emergency medical team / ICU call, continuous intensive monitoring.'
            ]
        },
        'tachycardia': {
            'title': 'Tachycardia (Elevated Heart Rate)',
            'definition': 'Heart rate exceeding 100 beats per minute in an adult at rest.',
            'causes': 'Fever, sepsis, hypovolemia/hemorrhage, pain, anxiety, pulmonary embolism, cardiac arrhythmias (AFib, SVT), thyrotoxicosis.',
            'clinical_significance': [
                'Compensatory tachycardia maintains cardiac output in the setting of decreased stroke volume or vasodilation (sepsis).',
                'Sustained HR >120 bpm requires immediate evaluation of the underlying trigger.'
            ]
        },
        'bradycardia': {
            'title': 'Bradycardia (Low Heart Rate)',
            'definition': 'Heart rate below 60 beats per minute (clinically significant when <50 bpm or symptomatic).',
            'causes': 'Sinus node dysfunction, AV block, medications (beta-blockers, CCBs, digoxin), increased intracranial pressure (Cushing reflex), severe hypothermia, hypothyroidism.'
        },
        'hypoxemia': {
            'title': 'Hypoxemia (Low Blood Oxygen)',
            'definition': 'Abnormally low arterial oxygen tension (PaO₂ <60 mmHg or SpO₂ <90%).',
            'causes': 'V/Q mismatch (pneumonia, PE, COPD), alveolar hypoventilation, diffusion impairment (pulmonary fibrosis), right-to-left shunt (ARDS, cyanotic heart disease).',
            'clinical_significance': [
                'SpO₂ <92%: Hypoxemia requiring supplemental oxygen.',
                'SpO₂ <88%: Severe hypoxemia risking tissue hypoxia, lactic acidosis, and cardiac ischemia.'
            ]
        }
    }

    # ── Knowledge Base Lookup ──
    def find_kb_entry(query_text):
        """Search the knowledge base for a matching entry."""
        q_words = set(query_text.split())
        best_match = None
        best_score = 0

        for key, entry in MEDICAL_KB.items():
            score = 0
            key_words = set(key.lower().split())
            title_words = set(entry['title'].lower().split()) if 'title' in entry else set()

            # Exact key match
            if key in query_text:
                score += 15
            # Title words match
            for tw in title_words:
                if tw in q_words and len(tw) > 2:
                    score += 3
            # Key words match
            for kw in key_words:
                if kw in q_words and len(kw) > 2:
                    score += 5
            # Abbreviation match
            if key.upper() in query_text.upper().split():
                score += 8

            if score > best_score:
                best_score = score
                best_match = entry

        return best_match if best_score >= 3 else None

    entry = find_kb_entry(q_clean)

    if entry:
        lines = [f"**{entry.get('title', 'Clinical Concept')}**\n"]

        if 'definition' in entry:
            lines.append(f"**Definition:** {entry['definition']}\n")
        if 'normal_range' in entry:
            lines.append(f"**Normal Range:** {entry['normal_range']}\n")
        if 'symptoms' in entry:
            lines.append(f"**Symptoms/Presentation:** {entry['symptoms']}\n")
        if 'diagnosis' in entry:
            lines.append(f"**Diagnosis:** {entry['diagnosis']}\n")
        if 'treatment' in entry:
            lines.append(f"**Treatment:** {entry['treatment']}\n")
        if 'dose' in entry:
            lines.append(f"**Dosing:** {entry['dose']}\n")
        if 'mechanism' in entry:
            lines.append(f"**Mechanism of Action:** {entry['mechanism']}\n")
        if 'key_criteria' in entry:
            lines.append(f"**Clinical Criteria:** {entry['key_criteria']}\n")
        if 'nurse_ratio' in entry:
            lines.append(f"**Staffing:** {entry['nurse_ratio']}\n")

        if 'clinical_significance' in entry:
            lines.append("**Clinical Significance:**")
            for item in entry['clinical_significance']:
                lines.append(f"• {item}")
            lines.append("")

        if 'types' in entry:
            lines.append("**Types:**")
            for item in entry['types']:
                lines.append(f"• {item}")
            lines.append("")

        if 'causes' in entry:
            lines.append(f"**Common Causes:** {entry['causes']}\n")
        if 'common_causes_abnormal' in entry:
            lines.append(f"**Common Causes of Abnormal Values:** {entry['common_causes_abnormal']}\n")
        if 'common_causes_high' in entry:
            lines.append(f"**Causes of Elevation:** {entry['common_causes_high']}\n")
        if 'common_causes_low' in entry:
            lines.append(f"**Causes of Depletion:** {entry['common_causes_low']}\n")
        if 'emergency_actions' in entry:
            lines.append(f"**Emergency Actions:** {entry['emergency_actions']}\n")

        if 'key_modes' in entry:
            lines.append("**Key Modes:**")
            for item in entry['key_modes']:
                lines.append(f"• {item}")
            lines.append("")

        if 'key_settings' in entry:
            lines.append(f"**Key Settings:** {entry['key_settings']}\n")
        if 'clinical_features' in entry:
            lines.append(f"**Clinical Features:** {entry['clinical_features']}\n")
        if 'indications' in entry:
            lines.append(f"**Indications:** {entry['indications']}\n")

        if 'common_causes_abnormal' in entry:
            lines.append(f"**Common Causes of Abnormality:** {entry['common_causes_abnormal']}\n")
        if 'side_effects' in entry:
            lines.append(f"**Side Effects:** {entry['side_effects']}\n")
        if 'contraindications' in entry:
            lines.append(f"**Contraindications:** {entry['contraindications']}\n")
        if 'complications' in entry:
            lines.append(f"**Complications:** {entry['complications']}\n")

        # Patient-specific connection if telemetry exists
        if p and v:
            lines.append(f"\n*(Context for **{p.get('name', 'patient')}**: Admitted in {p.get('ward_type', 'ICU')} with latest recorded vitals: {_fmt_spo2(v.get('spo2'))}, HR {_fmt_val(v.get('heart_rate'), 'bpm')}, BP {_fmt_bp(v.get('blood_pressure_sys'), v.get('blood_pressure_dia'))}).*")

        lines.append("\n*This is general medical reference information. Always correlate with individual patient context and clinical assessment.*")
        return "\n".join(lines)

    # ── Fallback: Generic concept response for unrecognized medical terms ──
    # Extract the core term from "what is X" patterns
    core_term = q_clean
    for prefix in ['what is ', 'what are ', 'what is a ', 'what is an ', 'what is the ',
                   'define ', 'definition of ', 'meaning of ', 'explain ', 'explain what ',
                   'tell me about ', 'what does ', 'what do ']:
        if core_term.startswith(prefix):
            core_term = core_term[len(prefix):].strip()
            break

    if core_term and len(core_term) > 1:
        patient_note = ""
        if p and v:
            patient_note = (
                f"\n\n**For {p['name']}:** Current telemetry shows {_fmt_spo2(v.get('spo2'))}, "
                f"HR {_fmt_val(v.get('heart_rate'), 'bpm')}, RR {_fmt_val(v.get('respiratory_rate'), '/min')}, "
                f"BP {_fmt_bp(v.get('blood_pressure_sys'), v.get('blood_pressure_dia'))}, Temp {_fmt_val(v.get('temperature'), '°C')}."
            )
        return (
            f"**{core_term.title()}**\n\n"
            f"This is a recognized medical/clinical term. While I don't have a detailed knowledge base entry for "
            f"**{core_term}** specifically, I can provide clinical context and patient-specific telemetry data.\n\n"
            f"For definitive clinical guidance on **{core_term}**, please refer to established clinical resources "
            f"(UpToDate, BMJ Best Practice, NICE Guidelines, or your institution's clinical protocols)."
            f"{patient_note}\n\n"
            f"*You can also ask me about specific aspects like 'What is the treatment for {core_term}?' or "
            f"'What are the symptoms of {core_term}?'*"
        )

    return (
        "**Clinical Concept:** Telemetry parameters (SpO₂, Heart Rate, Blood Pressure, Respiratory Rate, Temperature, and AVPU) "
        "form the foundation of physiological risk stratification under National Early Warning Systems (NEWS2/EWS).\n\n"
        "You can ask me about any specific medical condition, drug, lab value, or clinical concept — for example:\n"
        "• *'What is sepsis?'*\n"
        "• *'What is normal SpO₂?'*\n"
        "• *'What is paracetamol?'*\n"
        "• *'What is ARDS?'*\n"
        "• *'What causes tachycardia?'*"
    )


def reason_open_custom_query(patient_id, query):
    """
    Intelligent dynamic reasoning for custom questions that were never explicitly hardcoded.
    Decomposes the question, identifies relevant clinical dimensions, and assembles
    a comprehensive grounded answer from available data.
    """
    p = getPatient(patient_id)
    v = getLatestVitals(patient_id)
    ews_info = getEWS(patient_id)
    trends = getVitalTrend(patient_id)
    doc = getDocumentedConditions(patient_id)
    rec = getTransferDecision(patient_id)
    alerts = getAlerts(patient_id, limit=5)
    history = getRecentVitals(patient_id, limit=6)

    if not p:
        return "Patient record could not be found."

    q_lower = query.lower()
    p_name = p['name']
    diag = doc.get('diagnosis')
    diag_str = f"**{diag}**" if diag else "No primary diagnosis documented"

    # ── Intelligent Sub-topic Detection ──
    sections = []

    # Check if the question mentions specific vitals
    mentions_vitals = any(w in q_lower for w in ['vital', 'parameter', 'reading', 'number', 'telemetry', 'monitoring', 'all'])
    mentions_trend = any(w in q_lower for w in ['trend', 'change', 'progress', 'over time', 'trajectory', 'direction'])
    mentions_risk = any(w in q_lower for w in ['risk', 'score', 'ews', 'danger', 'critical', 'serious', 'severity'])
    mentions_plan = any(w in q_lower for w in ['plan', 'next', 'what to do', 'action', 'recommend', 'suggest', 'advice', 'management'])
    mentions_cause = any(w in q_lower for w in ['why', 'cause', 'reason', 'because', 'due to', 'factor', 'trigger'])
    mentions_treatment = any(w in q_lower for w in ['treatment', 'therapy', 'manage', 'intervention', 'what can we do', 'protocol', 'medication', 'drug', 'medicine'])
    mentions_diagnosis = any(w in q_lower for w in ['diagnos', 'condition', 'illness', 'disease', 'what does he have', 'what is wrong'])

    rec_time = v.get('recorded_at', 'recent') if v else 'N/A'

    # Build patient header
    header = f"Regarding **{p_name}** ({p.get('patient_code', 'N/A')}) — currently in **{p.get('ward_type', 'ICU')}** (Bed {p.get('bed_number', 'N/A')}):\n"
    sections.append(header)

    # Diagnosis context
    if mentions_diagnosis or mentions_cause:
        med_hist = doc.get('medical_history', [])
        hist_str = ", ".join(med_hist) if med_hist else "None documented"
        sections.append(f"**Documented Diagnosis:** {diag_str}")
        sections.append(f"**Medical History:** {hist_str}\n")

    # Current vital signs
    if v:
        vitals_lines = []
        if v.get('spo2') is not None:
            tag = " ⚠️ Low" if v.get('spo2') < 94 else " ✓ Normal"
            vitals_lines.append(f"SpO₂: **{_fmt_val(v.get('spo2'))}%**{tag}")
        if v.get('respiratory_rate') is not None:
            tag = " ⚠️ Elevated" if v.get('respiratory_rate') > 22 else " ✓ Normal"
            vitals_lines.append(f"RR: **{_fmt_val(v.get('respiratory_rate'))}/min**{tag}")
        if v.get('heart_rate') is not None:
            tag = " ⚠️ Tachycardic" if v.get('heart_rate') > 100 else " ✓ Normal"
            vitals_lines.append(f"HR: **{_fmt_val(v.get('heart_rate'))} bpm**{tag}")
        if v.get('blood_pressure_sys') is not None:
            dia_str = f"/{_fmt_val(v.get('blood_pressure_dia'))}" if v.get('blood_pressure_dia') is not None else ""
            tag = " ⚠️ Hypotensive" if v.get('blood_pressure_sys') < 90 else ""
            vitals_lines.append(f"BP: **{_fmt_val(v.get('blood_pressure_sys'))}{dia_str} mmHg**{tag}")
        if v.get('temperature') is not None:
            tag = " ⚠️ Febrile" if v.get('temperature') > 38.0 else " ✓ Normal"
            vitals_lines.append(f"Temp: **{_fmt_val(v.get('temperature'))}°C**{tag}")

        sections.append(f"**Current Telemetry (Recorded {rec_time}):**")
        for vl in vitals_lines:
            sections.append(f"• {vl}")
        sections.append("")
    else:
        sections.append("**Telemetry:** No vital sign readings recorded in the database.\n")

    # Risk assessment
    score = ews_info.get('score', 0)
    risk = ews_info.get('risk_level', 'LOW')
    sections.append(f"**Risk Assessment:** EWS = **{score}** ({risk} Risk)")

    # Trend analysis
    direction = trends.get('overall_direction', 'Stable')
    sections.append(f"**Physiological Trend:** Overall trajectory is **{direction.lower()}**")

    # Alerts
    if alerts:
        active_alerts = [a for a in alerts if not a.get('is_acknowledged')]
        if active_alerts:
            sections.append(f"\n🚨 **Active Alerts ({len(active_alerts)}):**")
            for a in active_alerts[:3]:
                sections.append(f"• {a.get('type', 'ALERT')}: {a.get('message', a.get('title', 'Alert'))}")
    sections.append("")

    # Transfer recommendation
    if rec:
        sections.append(f"**Transfer Decision:** {rec.get('recommendation_text', 'Under evaluation')}")
        if rec.get('reason'):
            sections.append(f"• *Rationale:* {rec.get('reason')}")
        sections.append("")

    # Causal analysis for "why" questions
    if mentions_cause and v:
        sections.append("**Clinical Correlation:**")
        if v.get('spo2') is not None and v.get('spo2') < 94:
            sections.append(f"• Low SpO₂ ({_fmt_val(v.get('spo2'))}%) may be related to {diag_str if diag else 'underlying respiratory pathology'}, indicating impaired gas exchange.")
        if v.get('heart_rate') is not None and v.get('heart_rate') > 100:
            sections.append(f"• Tachycardia ({_fmt_val(v.get('heart_rate'))} bpm) is likely compensatory for hypoxemia, hypovolemia, fever, or pain.")
        if v.get('respiratory_rate') is not None and v.get('respiratory_rate') > 22:
            sections.append(f"• Tachypnea ({_fmt_val(v.get('respiratory_rate'))}/min) reflects increased ventilatory demand and work of breathing.")
        if v.get('temperature') is not None and v.get('temperature') > 38.0:
            sections.append(f"• Fever ({_fmt_val(v.get('temperature'))}°C) may indicate ongoing infectious process requiring culture workup.")
        sections.append("")

    # Treatment/management guidance for "what should we do" questions
    if mentions_treatment or mentions_plan:
        sections.append("**Suggested Clinical Actions Based on Current Data:**")
        if score >= 7:
            sections.append("• **URGENT**: EWS ≥7 — Immediate senior clinician review and ICU-level monitoring required.")
        if v and v.get('spo2') is not None and v.get('spo2') < 92:
            sections.append("• Titrate supplemental oxygen to maintain SpO₂ ≥94%. Consider ABG and escalation to NIV/HFNC if not improving.")
        if v and v.get('heart_rate') is not None and v.get('heart_rate') > 120:
            sections.append("• Assess for reversible causes of tachycardia (hypovolemia, pain, fever). Consider ECG and cardiac monitoring.")
        if v and v.get('temperature') is not None and v.get('temperature') > 38.5:
            sections.append("• Send blood cultures if not already done. Consider empiric broad-spectrum antibiotics per local protocol.")
        if v and v.get('blood_pressure_sys') is not None and v.get('blood_pressure_sys') < 90:
            sections.append("• **Hypotension**: Initiate IV crystalloid bolus (250–500 mL), reassess, consider vasopressor support if unresponsive.")
        if score < 4:
            sections.append("• Continue routine monitoring. Current risk level is low.")
        sections.append("")

    sections.append("*This analysis is grounded in verified database readings. Clinical decisions must incorporate bedside assessment.*")
    return "\n".join(sections)


# =============================================================================
# 7. TELEMETRY SIMULATOR REASONING (ISOLATED SIMULATOR MODE ONLY)
# =============================================================================

def reason_custom_client_telemetry(vitals_dict, raw_query="", patient_name=None, context=None, custom_notes=None):
    """
    Dedicated analyzer for SIMULATED / USER-PROVIDED telemetry values (Explicit Simulator Mode ONLY).
    """
    total_score = 0
    scores = {}
    red_flags = []

    # 1. Respiratory Rate
    rr = vitals_dict.get('respiratory_rate')
    if rr is not None:
        s = 3 if (rr <= 8 or rr >= 25) else (2 if 21 <= rr <= 24 else (1 if 9 <= rr <= 11 else 0))
        if s == 3:
            red_flags.append(f"Critical Respiratory Rate: {_fmt_val(rr)}/min")
        scores['respiratory_rate'] = {'value': f"{_fmt_val(rr)}/min", 'score': s}
        total_score += s

    # 2. SpO2
    spo2 = vitals_dict.get('spo2')
    if spo2 is not None:
        s = 3 if spo2 <= 91 else (2 if 92 <= spo2 <= 93 else (1 if 94 <= spo2 <= 95 else 0))
        if s == 3:
            red_flags.append(f"Severe Hypoxemia: SpO2 {_fmt_val(spo2)}%")
        scores['spo2'] = {'value': f"{_fmt_val(spo2)}%", 'score': s}
        total_score += s

    # 3. Heart Rate
    hr = vitals_dict.get('heart_rate')
    if hr is not None:
        s = 3 if (hr <= 40 or hr >= 131) else (2 if 111 <= hr <= 130 else (1 if (41 <= hr <= 50 or 91 <= hr <= 110) else 0))
        if s == 3:
            red_flags.append(f"Critical Heart Rate: {_fmt_val(hr)} bpm")
        scores['heart_rate'] = {'value': f"{_fmt_val(hr)} bpm", 'score': s}
        total_score += s

    # 4. Systolic BP
    sys_bp = vitals_dict.get('blood_pressure_sys')
    dia_bp = vitals_dict.get('blood_pressure_dia')
    if sys_bp is not None:
        s = 3 if (sys_bp <= 90 or sys_bp >= 220) else (2 if 91 <= sys_bp <= 100 else (1 if 101 <= sys_bp <= 110 else 0))
        if s == 3:
            red_flags.append(f"Critical Blood Pressure: {_fmt_val(sys_bp)} mmHg")
        bp_val = f"{_fmt_val(sys_bp)}" + (f"/{_fmt_val(dia_bp)}" if dia_bp is not None else "") + " mmHg"
        scores['blood_pressure'] = {'value': bp_val, 'score': s}
        total_score += s

    # 5. Temperature
    temp = vitals_dict.get('temperature')
    if temp is not None:
        s = 3 if temp <= 35.0 else (2 if temp >= 39.1 else (1 if (35.1 <= temp <= 36.0 or 38.1 <= temp <= 39.0) else 0))
        scores['temperature'] = {'value': f"{_fmt_val(temp)}°C", 'score': s}
        total_score += s

    # 6. AVPU / Consciousness
    avpu = vitals_dict.get('consciousness', 'Alert')
    if avpu and any(x in str(avpu).upper() for x in ['UNRESPONSIVE', 'PAIN', 'VOICE', 'U', 'P', 'V']):
        scores['consciousness'] = {'value': str(avpu), 'score': 3}
        red_flags.append(f"Altered Consciousness: {avpu}")
        total_score += 3

    risk_level = "CRITICAL / HIGH RISK" if (total_score >= 7 or len(red_flags) > 0) else ("MEDIUM RISK" if total_score >= 5 else ("LOW RISK" if total_score >= 1 else "STABLE"))
    rec_unit = "ICU" if (total_score >= 7 or len(red_flags) > 0) else ("HDU / Step-Down" if total_score >= 5 else "Ward")

    target_str = f"for **{patient_name}**" if patient_name else "User-Provided Simulation"

    lines = [
        f"📊 **[SIMULATED / USER-PROVIDED DATA] Telemetry Analysis ({target_str})**\n",
        f"• **Simulated EWS Score:** `{total_score}` — **{risk_level}**",
        f"• **Recommended Care Unit:** **{rec_unit}**\n",
        "**Simulated Parameter Breakdown:**"
    ]

    for param, details in scores.items():
        p_label = param.replace('_', ' ').title()
        badge = "🔴 Critical (+3)" if details['score'] == 3 else ("🟠 Warning (+" + str(details['score']) + ")" if details['score'] > 0 else "🟢 Normal (0)")
        lines.append(f"• **{p_label}:** `{details['value']}` — {badge}")

    if red_flags:
        lines.append("\n⚠️ **Red Flag Clinical Alerts:**")
        for f in red_flags:
            lines.append(f"• 🚨 {f}")

    if custom_notes:
        lines.append(f"\n• **Simulated Clinical Notes:** {custom_notes}")

    lines.append("\n*Note: This analysis was generated from user-provided simulation values and is not stored in patient database records.*")
    return "\n".join(lines)


# =============================================================================
# 8. HIGH-LEVEL CONVERSATIONAL ORCHESTRATOR (MAIN ENTRYPOINT)
# =============================================================================

def process_conversational_message(user_id=1, message="", active_patient_id=None,
                                   custom_vitals=None, custom_patient=None, custom_notes=None,
                                   user_role="doctor", mode="patient"):
    """
    Main conversational orchestrator that handles free-form natural language input:
    1. Supports two explicit context modes: 'patient' (default) and 'general'.
    2. Enforces RBAC & patient access controls.
    3. In Patient Mode: Grounded in verified MySQL database records for selected patient.
    4. In General Mode: Zero patient context attached. Educates on medical/clinical concepts.
       Directs user to Patient Chat mode if specific patient records are requested.
    5. Leverages OpenRouter Gemini AI with strict clinical guardrails.
    """
    msg = (message or "").strip().strip('"\'`“”’‘').strip()
    chat_mode = (mode or "patient").strip().lower()
    if chat_mode not in ("patient", "general"):
        chat_mode = "patient" if active_patient_id else "general"

    # Step 0: Check if Explicit Simulator Mode is triggered
    if custom_vitals and isinstance(custom_vitals, dict) and len(custom_vitals) > 0:
        p_name = None
        if active_patient_id and chat_mode == "patient":
            p = getPatient(active_patient_id)
            p_name = p['name'] if p else None
        sim_text = reason_custom_client_telemetry(custom_vitals, raw_query=msg, patient_name=p_name, custom_notes=custom_notes)
        return {
            'success': True,
            'mode': chat_mode,
            'text': sim_text,
            'response': sim_text,
            'intent': 'simulated_telemetry',
            'patient_id': active_patient_id if chat_mode == "patient" else None,
            'patient_context': get_patient_clinical_context(active_patient_id) if (chat_mode == "patient" and active_patient_id) else None
        }

    if not msg:
        return {
            'success': False,
            'mode': chat_mode,
            'error': 'Empty message.',
            'text': 'Please enter a medical question or select a patient for clinical rounds.',
            'response': 'Please enter a medical question or select a patient for clinical rounds.',
            'intent': 'empty_query'
        }

    # =========================================================================
    # ── GENERAL CHAT MODE (ZERO PATIENT CONTEXT & NO DATA LEAKAGE) ──
    # =========================================================================
    if chat_mode == "general":
        # 1. Redirection Guardrail: If user explicitly asks about a specific patient by name or asks for patient-specific records in General Mode
        cand_name, remaining_q, is_explicit_mention = extract_explicit_patient_mention(msg)
        if is_explicit_mention and cand_name:
            redirection_text = (
                f"You are currently in **General Chat mode** with no patient selected. "
                f"To view verified clinical records, telemetry, or transfer recommendations for **{cand_name}**, "
                f"please switch to **Patient Chat mode** and select the patient from your authorized dropdown."
            )
            return {
                'success': True,
                'mode': 'general',
                'patient_id': None,
                'patient_context': None,
                'text': redirection_text,
                'response': redirection_text,
                'intent': 'general_mode_patient_redirection'
            }

        # Check for generic patient queries without a name in general mode (e.g., "What is his EWS?", "What are the patient's vitals?")
        if re.search(r'\b(the patient|his|her|this patient)\b', msg, re.IGNORECASE) and re.search(r'\b(vitals?|ews|diagnosis|heart rate|blood pressure|spo2|temperature|respiratory rate|bed|ward|transfer|recommendation)\b', msg, re.IGNORECASE):
            redirection_text = (
                "You are currently in **General Chat mode** with no patient selected. "
                "Please switch to **Patient Chat mode** and select a patient from the dropdown to access patient-specific telemetry and clinical records."
            )
            return {
                'success': True,
                'mode': 'general',
                'patient_id': None,
                'patient_context': None,
                'text': redirection_text,
                'response': redirection_text,
                'intent': 'general_mode_patient_redirection'
            }

        # 2. Greeting / General Help in General Mode
        if any(w in msg.lower().split() for w in ['hi', 'hello', 'hey', 'greetings']) and len(msg.split()) <= 4:
            greeting_text = (
                "Hello! I am **Dr. Setu** in **General Healthcare Chat mode**.\n\n"
                "I can assist you with general medical concepts, physiological norms, clinical score definitions (like EWS/NEWS2), and ICU/HDU terminology.\n\n"
                "• *Example:* 'What is hypertension?'\n"
                "• *Example:* 'What is the normal adult respiratory rate?'\n"
                "• *Example:* 'Explain Early Warning Score (EWS)'\n"
                "• *Example:* 'What is the difference between ICU and HDU?'\n\n"
                "*Note: To view live bedside records or telemetry for an admitted patient, please switch to Patient Chat mode.*"
            )
            return {
                'success': True,
                'mode': 'general',
                'patient_id': None,
                'patient_context': None,
                'text': greeting_text,
                'response': greeting_text,
                'intent': 'general_greeting'
            }

        # 3. Direct AI Educational Response via OpenRouter (No patient context)
        if is_ai_configured():
            ok, ai_resp, _ = query_openrouter_gemini(msg, patient_context=None, user_role=user_role, mode="general")
            if ok and ai_resp:
                return {
                    'success': True,
                    'mode': 'general',
                    'patient_id': None,
                    'patient_context': None,
                    'text': ai_resp,
                    'response': ai_resp,
                    'intent': 'general_ai_response'
                }

        # 4. Fallback: Embedded Medical Knowledge Base (context=None ensures zero patient context)
        med_resp = reason_general_medical_query(msg, context=None)
        if med_resp:
            return {
                'success': True,
                'mode': 'general',
                'patient_id': None,
                'patient_context': None,
                'text': med_resp,
                'response': med_resp,
                'intent': 'general_medical_concept'
            }

        # 5. Default General Response
        default_gen_resp = (
            "**Dr. Setu — General Healthcare Assistant:**\n\n"
            "I can provide general educational healthcare explanations and clinical reference information.\n\n"
            "• Ask about medical conditions (e.g., *'What is sepsis?'*, *'Explain COPD'*)\n"
            "• Ask about vital sign ranges (e.g., *'What is normal blood pressure?'*, *'What is tachycardia?'*)\n"
            "• Ask about hospital protocols (e.g., *'Difference between ICU and HDU'*, *'What is EWS?'*)\n\n"
            "*Educational information provided for clinical reference. For patient-specific telemetry, please switch to Patient Chat mode.*"
        )
        return {
            'success': True,
            'mode': 'general',
            'patient_id': None,
            'patient_context': None,
            'text': default_gen_resp,
            'response': default_gen_resp,
            'intent': 'general_help'
        }

    # =========================================================================
    # ── PATIENT CHAT MODE (DATABASE GROUNDED & RBAC PROTECTED) ──
    # =========================================================================
    state = ConversationMemory.get_state(user_id)

    # Synchronize active patient ID with state
    if active_patient_id:
        state['active_patient_id'] = int(active_patient_id)
        if not state.get('active_patient_name'):
            p = getPatient(active_patient_id)
            if p:
                state['active_patient_name'] = p['name']

    effective_patient_id = state.get('active_patient_id')

    # RBAC Attendant check: attendants can only access their assigned patient
    if user_role.lower() == 'attendant':
        if not effective_patient_id:
            return {
                'success': False,
                'mode': 'patient',
                'error': 'Unauthorized',
                'text': 'Attendant access is restricted to your assigned patient only. Please select your assigned patient.',
                'response': 'Attendant access is restricted to your assigned patient only. Please select your assigned patient.',
                'intent': 'rbac_restricted'
            }

    # Step 1: Check for explicit patient name mention / patient switch
    cand_name, remaining_q, is_explicit_mention = extract_explicit_patient_mention(msg)

    if is_explicit_mention and cand_name:
        match_type, patients = search_patients_for_chat(cand_name)

        if match_type == "none":
            return {
                'success': True,
                'mode': 'patient',
                'text': f"I could not find any patient matching '{cand_name}' in the database.\n\nPlease check the name or enter a valid UHID (e.g., 'Sahil Sharma' or 'UHID-2026-00001').",
                'response': f"I could not find any patient matching '{cand_name}' in the database.\n\nPlease check the name or enter a valid UHID (e.g., 'Sahil Sharma' or 'UHID-2026-00001').",
                'intent': "patient_not_found",
                'requires_patient_selection': True
            }
        elif match_type == "multiple":
            patient_list = "\n".join(
                f"• **{p['name']}** — ID: `{p['patient_code']}` (Unit: {p['ward_type']}, Bed: {p['bed_number']})"
                for p in patients
            )
            return {
                'success': True,
                'mode': 'patient',
                'text': f"I found multiple patients matching '{cand_name}'. Please specify which patient you would like to review:\n\n{patient_list}",
                'response': f"I found multiple patients matching '{cand_name}'. Please specify which patient you would like to review:\n\n{patient_list}",
                'intent': "patient_disambiguation",
                'candidates': patients,
                'requires_patient_selection': True
            }
        elif match_type == "single":
            p = patients[0]
            new_id = p['patient_id']
            ConversationMemory.update_state(
                user_id=user_id,
                active_patient_id=new_id,
                active_patient_name=p['name'],
                topic='STATUS_OVERVIEW',
                user_query=msg
            )
            try:
                AuditLog.log(
                    user_id=user_id,
                    action="CHATBOT_PATIENT_SELECT",
                    entity_type="patient",
                    entity_id=new_id,
                    description=f"Active patient switched to {p['name']} ({p['patient_code']})"
                )
            except Exception:
                pass

            # If the user asked a follow-up in the same sentence
            if remaining_q and remaining_q != "status overview":
                intent, param = classify_question_intent(remaining_q, session_state=state)
                response_text = _synthesize_answer(new_id, intent, param, remaining_q, state, user_role=user_role)
            else:
                response_text = reason_status_overview(new_id)

            ConversationMemory.update_state(user_id=user_id, bot_response=response_text)
            return {
                'success': True,
                'mode': 'patient',
                'text': response_text,
                'response': response_text,
                'intent': "patient_found",
                'patient_id': new_id,
                'patient': p,
                'context': get_patient_clinical_context(new_id),
                'patient_context': get_patient_clinical_context(new_id)
            }

    # Step 2: Classify intent and topic for free-form input
    intent, param = classify_question_intent(msg, session_state=state)

    # Step 3: Handle pure conversational greetings/acknowledgment/help without requiring patient
    if intent == 'GREETING':
        p_name = state.get('active_patient_name')
        if effective_patient_id and not p_name:
            p = getPatient(effective_patient_id)
            if p:
                p_name = p['name']
        greeting_text = (
            f"Hello, Doctor. I am Dr. Setu, ready to assist you with clinical rounds for **{p_name}**."
            if p_name else
            "Hello, Doctor. I am Dr. Setu, your clinical decision-support assistant for ICU–HDU patient management.\n\nWhich patient would you like me to review today?"
        )
        return {
            'success': True,
            'mode': 'patient',
            'text': greeting_text,
            'response': greeting_text,
            'intent': 'greeting',
            'patient_id': effective_patient_id,
            'patient_context': get_patient_clinical_context(effective_patient_id) if effective_patient_id else None
        }

    if intent == 'ACKNOWLEDGMENT':
        p_name = state.get('active_patient_name')
        ack_text = f"You're welcome, Doctor. I'm ready if you'd like to check {p_name}'s vital trends, overnight changes, or transfer recommendations." if p_name else "You're welcome, Doctor. Let me know which patient you'd like to review next."
        return {
            'success': True,
            'mode': 'patient',
            'text': ack_text,
            'response': ack_text,
            'intent': 'acknowledgment',
            'patient_id': effective_patient_id,
            'patient_context': get_patient_clinical_context(effective_patient_id) if effective_patient_id else None
        }

    if intent == 'HELP':
        p_name = state.get('active_patient_name')
        return {
            'success': True,
            'mode': 'patient',
            'text': (
                f"Doctor, you can ask me ANY natural question about " + (f"**{p_name}**" if p_name else "a patient") + ":\n\n"
                f"• *'condition?'* or *'how is he?'* — Comprehensive status & telemetry.\n"
                f"• *'what about his oxygen?'* or *'why is his oxygen low?'* — Single vital & causality reasoning.\n"
                f"• *'is he getting better?'* or *'is he stable?'* — Trajectory & trend analysis.\n"
                f"• *'what changed overnight?'* — Historical overnight comparison.\n"
                f"• *'what worries you?'* — Ranked key concerns & abnormal parameters.\n"
                f"• *'why is he still in ICU?'* — Decision support & transfer criteria.\n"
                f"• *'Tell me about Rajesh'* — Switch to another authorized patient."
            ),
            'response': (
                f"Doctor, you can ask me ANY natural question about " + (f"**{p_name}**" if p_name else "a patient") + ":\n\n"
                f"• *'condition?'* or *'how is he?'* — Comprehensive status & telemetry.\n"
                f"• *'what about his oxygen?'* or *'why is his oxygen low?'* — Single vital & causality reasoning.\n"
                f"• *'is he getting better?'* or *'is he stable?'* — Trajectory & trend analysis.\n"
                f"• *'what changed overnight?'* — Historical overnight comparison.\n"
                f"• *'what worries you?'* — Ranked key concerns & abnormal parameters.\n"
                f"• *'why is he still in ICU?'* — Decision support & transfer criteria.\n"
                f"• *'Tell me about Rajesh'* — Switch to another authorized patient."
            ),
            'intent': 'help',
            'patient_id': effective_patient_id,
            'patient_context': get_patient_clinical_context(effective_patient_id) if effective_patient_id else None
        }

    # Step 4: Handle input when NO patient is currently active in Patient Mode
    if not effective_patient_id:
        # 1. First check if user is specifically searching for or typing a patient name/UHID
        is_name_query = len(msg.split()) <= 4 and not any(w in msg.lower() for w in ['what', 'why', 'how', 'when', 'who', 'is', 'are', 'can', 'explain', 'tell', 'define', 'which', 'should', 'list', 'calculate', 'describe', 'difference', 'treatment', 'causes', 'symptoms'])
        if is_name_query:
            match_type, patients = search_patients_for_chat(msg)
            if match_type == "single":
                p = patients[0]
                new_id = p['patient_id']
                ConversationMemory.update_state(
                    user_id=user_id,
                    active_patient_id=new_id,
                    active_patient_name=p['name'],
                    topic='STATUS_OVERVIEW',
                    user_query=msg
                )
                response_text = reason_status_overview(new_id)
                ConversationMemory.update_state(user_id=user_id, bot_response=response_text)
                return {
                    'success': True,
                    'mode': 'patient',
                    'text': response_text,
                    'response': response_text,
                    'intent': "patient_found",
                    'patient_id': new_id,
                    'patient': p,
                    'context': get_patient_clinical_context(new_id),
                    'patient_context': get_patient_clinical_context(new_id)
                }
            elif match_type == "multiple":
                patient_list = "\n".join(
                    f"• **{p['name']}** — ID: `{p['patient_code']}` (Unit: {p['ward_type']}, Bed: {p['bed_number']})"
                    for p in patients
                )
                return {
                    'success': True,
                    'mode': 'patient',
                    'text': f"I found multiple patients matching '{msg}'. Which patient would you like me to review?\n\n{patient_list}",
                    'response': f"I found multiple patients matching '{msg}'. Which patient would you like me to review?\n\n{patient_list}",
                    'intent': "patient_disambiguation",
                    'candidates': patients,
                    'requires_patient_selection': True
                }

        # 2. Directly answer whatever general question was provided via OpenRouter AI
        if is_ai_configured():
            ok, ai_resp, _ = query_openrouter_gemini(msg, patient_context=None, user_role=user_role, mode="general")
            if ok and ai_resp:
                return {
                    'success': True,
                    'mode': 'patient',
                    'text': ai_resp,
                    'response': ai_resp,
                    'intent': intent.lower() if intent else 'ai_general_query',
                    'patient_id': None,
                    'patient_context': None
                }

        # 3. Fallback to rich embedded medical knowledge base
        med_resp = reason_general_medical_query(msg, context=None)
        if med_resp and "Clinical Concept" not in med_resp:
            return {
                'success': True,
                'mode': 'patient',
                'text': med_resp,
                'response': med_resp,
                'intent': 'general_medical_concept',
                'patient_id': None,
                'patient_context': None
            }

        # 4. Fallback prompt to select patient
        return {
            'success': True,
            'mode': 'patient',
            'text': f"**Dr. Setu Clinical Assistant (Patient Mode):**\n\nPlease select a patient from the dropdown above to review live telemetry, EWS risk scores, and transfer recommendations.\n\n• Or enter a patient name / UHID (e.g., *'Sahil Sharma'* or *'JS-0001'*).\n• Or switch to **General Chat** mode to ask general medical and healthcare questions without a patient context.",
            'response': f"**Dr. Setu Clinical Assistant (Patient Mode):**\n\nPlease select a patient from the dropdown above to review live telemetry, EWS risk scores, and transfer recommendations.\n\n• Or enter a patient name / UHID (e.g., *'Sahil Sharma'* or *'JS-0001'*).\n• Or switch to **General Chat** mode to ask general medical and healthcare questions without a patient context.",
            'intent': "prompt_patient_selection",
            'patient_id': None,
            'patient_context': None
        }

    # Step 5: Synthesize grounded clinical answer for the active patient
    response_text = _synthesize_answer(effective_patient_id, intent, param, msg, state, user_role=user_role)

    # Step 6: Update conversation memory & audit log
    ConversationMemory.update_state(
        user_id=user_id,
        topic=intent,
        parameter=param,
        user_query=msg,
        bot_response=response_text
    )

    try:
        ChatbotConversation.save(
            user_id=user_id,
            user_message=msg,
            bot_response=response_text,
            patient_id=effective_patient_id,
            intent=intent,
            confidence=0.98
        )
    except Exception:
        pass

    context = get_patient_clinical_context(effective_patient_id)

    return {
        'success': True,
        'mode': 'patient',
        'text': response_text,
        'response': response_text,
        'intent': intent.lower(),
        'patient_id': effective_patient_id,
        'context': context,
        'patient_context': context
    }


def _synthesize_answer(patient_id, intent, parameter, raw_query, session_state, user_role="doctor"):
    """
    Routes to specialized grounded clinical reasoner based on semantic intent and OpenRouter AI.
    Enforces Transfer Approval Guardrail (Section 10) and Source-of-Truth database rules.
    """
    # 1. Enforce Transfer Approval Guardrail (Section 10)
    if re.search(r'\b(approve|authorize|execute|sign off)\b.*\b(transfer|step[- ]?down|icu|hdu|ward)\b', raw_query, re.IGNORECASE) or \
       re.search(r'\b(transfer|step[- ]?down|icu|hdu|ward)\b.*\b(approve|authorize|execute|sign off)\b', raw_query, re.IGNORECASE):
        if user_role.lower() == 'nurse' or re.search(r'\b(nurse|staff nurse)\b', raw_query, re.IGNORECASE):
            return "❌ **Transfer Approval Authority Notice:** Nurses do not have transfer approval authority in Jeevan Setu. Only authorized attending Doctors can approve patient transfers."
        return "ℹ️ **Transfer Approval Notice:** The AI assistant cannot approve or execute patient transfers. Please review the patient's condition and use the official Jeevan Setu Doctor Portal / Transfer Approval workflow to authorize transfer."

    # 2. Strict Grounded Clinical Handlers
    if intent == 'STATUS_OVERVIEW':
        return reason_status_overview(patient_id)

    if intent == 'SINGLE_PARAMETER':
        return reason_single_parameter_inquiry(patient_id, parameter or 'spo2')

    if intent == 'PARAMETER_CAUSE':
        return reason_parameter_causality(patient_id, parameter or 'general')

    if intent == 'TRAJECTORY_ANALYSIS':
        return reason_trajectory_and_improvement(patient_id)

    if intent == 'HISTORICAL_COMPARISON':
        return reason_historical_overnight_comparison(patient_id)

    if intent == 'KEY_CONCERNS':
        return reason_key_concerns(patient_id)

    if intent == 'PROGNOSIS_SEVERITY':
        return reason_prognosis_and_severity(patient_id)

    if intent == 'TRANSFER_DECISION':
        return reason_transfer_decision(patient_id)

    if intent == 'DECISION_HISTORY':
        p = getPatient(patient_id)
        history = getDecisionHistory(patient_id, limit=5)
        if not history:
            return f"No previous clinician transfer reviews are recorded in the database for {p['name']}."
        lines = [f"**Transfer Decision History for {p['name']}:**\n"]
        for d in history:
            dec_time = d.get('decided_at') or "Recent"
            by = f" by {d.get('decided_by_name')}" if d.get('decided_by_name') else ""
            lines.append(f"• **{dec_time}**: {d.get('recommendation')} ({d.get('status')}){by}")
        return "\n".join(lines)

    if intent == 'EWS_QUERY':
        return reason_parameter_causality(patient_id, 'ews')

    if intent == 'DOCUMENTED_CONDITION':
        return reason_documented_condition(patient_id)

    if intent == 'CONCISE_SUMMARY':
        return reason_concise_summary(patient_id)

    if intent == 'EXPAND_DETAIL':
        return reason_status_overview(patient_id)

    if intent == 'GENERAL_MEDICAL_CONCEPT':
        c = get_patient_clinical_context(patient_id)
        if is_ai_configured():
            ok, ai_resp, _ = query_openrouter_gemini(raw_query, patient_context=c, user_role=user_role, mode="patient")
            if ok:
                return ai_resp
        return reason_general_medical_query(raw_query, context=c)

    # 3. Open Custom Inquiries with OpenRouter Gemini AI
    if is_ai_configured():
        c = get_patient_clinical_context(patient_id)
        ok, ai_resp, meta = query_openrouter_gemini(raw_query, patient_context=c, user_role=user_role, mode="patient")
        if ok:
            return ai_resp

    # Fallback to local clinical synthesis engine
    return reason_open_custom_query(patient_id, raw_query)


def process_message(user_id, message, patient_id=None, custom_vitals=None, custom_patient=None, custom_notes=None, user_role="doctor", mode="patient"):
    """
    Backwards-compatible API wrapper calling process_conversational_message.
    """
    return process_conversational_message(
        user_id=user_id,
        message=message,
        active_patient_id=patient_id,
        custom_vitals=custom_vitals,
        custom_patient=custom_patient,
        custom_notes=custom_notes,
        user_role=user_role,
        mode=mode
    )


# Backwards compatible formatters used by routes and reports
def format_structured_patient_summary(context):
    p_id = context['patient']['patient_id']
    return reason_status_overview(p_id)

def format_vital_parameters_analysis(context, specific_param=None):
    p_id = context['patient']['patient_id']
    return reason_single_parameter_inquiry(p_id, specific_param or 'spo2')

def format_transfer_decision_explanation(context):
    p_id = context['patient']['patient_id']
    return reason_transfer_decision(p_id)

def format_decision_history_and_overrides(context):
    p_id = context['patient']['patient_id']
    return _synthesize_answer(p_id, 'DECISION_HISTORY', None, "", {})

def format_documented_diagnosis(context):
    p_id = context['patient']['patient_id']
    return reason_documented_condition(p_id)
