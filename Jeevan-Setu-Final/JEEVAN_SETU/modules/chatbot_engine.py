"""
modules/chatbot_engine.py — Advanced Clinical Reasoning Assistant for Jeevan Setu (Dr. Setu).

Architectural Workflow:
    1. Question / Intent Understanding (16-Category Intent Classification)
    2. Intent-Specific Clinical Context Retrieval Layer (CCRL):
       - GREETING: No heavy patient DB lookups required.
       - SINGLE_PARAMETER: Fetches specific vital, timestamp, threshold band, and short delta.
       - CAUSE_ANALYSIS: Multi-parameter cross-system correlation (SpO2 + RR + HR + BP + Diagnosis + EWS + Decisions).
       - TREND_ANALYSIS / DETERIORATION: Longitudinal multi-reading comparison with Answer-First Rule.
       - HISTORICAL_DATA: Previous vitals and past EWS records clearly marked as historical.
       - EWS_QUERY: Early Warning Score point breakdown and Composite Stability Index.
       - TRANSFER_DECISION: Unit location, Decision Engine factors, and clinician override history.
       - DOCUMENTED_CONDITION: Stored diagnosis or explicit absence notice (zero inferring).
       - PROGNOSIS_MORTALITY: Severe telemetry breakdown with strict clinical uncertainty.
       - EMERGENCY_CRITICAL: High-urgency ABC emergency protocol escalation.
       - PATIENT_SUMMARY: Full 6-part clinical rounds handover (only when requested).
       - GENERAL_QUERY / UNKNOWN: Clean helpful conversational response without dumping patient summaries.
    3. Multi-Parameter Reasoning Pipeline & Anti-Hallucination Guardrails
    4. RBAC & Audit Logging
"""

import os
import sys

# Ensure application root is in sys.path for direct script execution
_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

import re
from datetime import datetime
from database.db import db
from models.chatbot_model import ChatbotConversation
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.ews_score_model import EWSScore
from models.recommendation_model import Recommendation
from models.decision_model import Decision
from models.transfer_model import Transfer
from models.alert_model import Alert
from models.audit_log_model import AuditLog
from modules.scoring_engine import calculate_ews, calculate_parameter_score, get_risk_level
from modules.decision_engine import evaluate_decision


def _fmt_val(val, unit=""):
    """Format numeric telemetry values cleanly without awkward trailing zeros (e.g. 91% instead of 91.0%)."""
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        if float(val).is_integer():
            return f"{int(val)}{unit}"
        return f"{round(float(val), 1)}{unit}"
    return f"{val}{unit}"


# =============================================================================
# 1. 20-CATEGORY CONVERSATIONAL CLINICAL INTENT DEFINITIONS & KEYWORDS
# =============================================================================
INTENT_PATTERNS = {
    # 1. Greeting / Conversational pleasantries (Strictly no patient summary)
    "greeting": [
        "how are you", "how are u", "how do you do", "hi", "hello", "hey",
        "good morning", "good afternoon", "good evening", "greetings", "dr setu",
        "who are you", "what can you do", "what are your capabilities", "introduce yourself"
    ],
    # 2. Conversational Acknowledgment / Closing
    "acknowledgment": [
        "thanks", "thank you", "okay", "ok", "got it", "that's helpful", "understood",
        "alright", "great", "okay thanks", "ok thanks", "thank you doctor", "thanks dr setu",
        "perfect", "fine", "noted"
    ],
    # 3. Current Clinical Status / Condition / Overview ('condition?', 'how is he?', 'status?')
    "current_status_overview": [
        "condition", "current condition", "status", "current status", "update", "clinical update",
        "quick update", "give me an update", "give me a quick update", "what's the latest status",
        "what is the latest status", "what's the latest update", "what is the latest update",
        "what is the latest condition", "what's the latest condition", "how is he", "how is she", "how are they", "how's he doing",
        "how is he doing", "how's she doing", "how is she doing", "how is the patient doing",
        "how is the patient", "how is sahil doing", "how is sahil", "how is rajesh",
        "how does he look", "how does she look", "how does the patient look", "how do they look",
        "is he okay", "is she okay", "is the patient okay", "is he stable", "is she stable",
        "is the patient stable", "what's happening", "what is happening", "what's going on",
        "what is going on", "what's happening with him", "what's happening with her",
        "what is happening with him", "what is happening with her", "what is happening with the patient",
        "tell me about him", "tell me about her", "tell me about the patient", "tell me what's happening",
        "what do you know about him", "what do you know about her", "what should i know about him",
        "what should i know", "what's his condition", "what is his condition", "how's his condition",
        "how is condition", "how is patient", "what is his current status", "what is his current condition",
        "are there any problems", "any problems", "how is he right now"
    ],
    # 4. Emergency / Critical Protocol
    "emergency_critical": [
        "unconscious", "arrest", "crashing", "collapsed", "cyanosis", "code blue",
        "stopped breathing", "no pulse", "unresponsive", "gasping", "emergency", "urgent",
        "spo2 is 7", "spo2 is 6", "spo2 7", "spo2 6", "what should i do"
    ],
    # 5. Prognosis / Mortality Risk / Severity / 'Is it serious?'
    "prognosis_mortality": [
        "serious", "is it serious", "is that serious", "is this serious", "is he serious",
        "how serious is this", "should i be worried", "is he critical", "is she in danger",
        "is he in danger", "is this dangerous", "going to die", "will he die", "will she die",
        "is he dying", "is she dying", "will he survive", "will she survive", "survival rate",
        "is this fatal", "mortality risk", "life expectancy", "chances of survival",
        "is he going to make it", "is the patient dying"
    ],
    # 6. Historical Data / Previous Vitals & EWS
    "historical_data": [
        "yesterday", "previous vitals", "vitals yesterday", "previous ews", "past vitals",
        "what was his ews yesterday", "what were his vitals yesterday", "earlier readings",
        "readings yesterday", "past readings", "what happened before", "historical vitals",
        "previous readings", "last recorded yesterday", "what was it yesterday"
    ],
    # 7. Historical Comparison ('Compare today with yesterday', 'What changed overnight?')
    "historical_comparison": [
        "what changed", "what changed overnight", "what happened overnight", "what changed today",
        "compare today with yesterday", "compare with yesterday", "what changed since yesterday",
        "compare that with yesterday", "compare today to yesterday", "changes since yesterday",
        "difference from yesterday", "show me what changed since yesterday",
        "compare his morning and evening readings", "what changed after the last transfer review",
        "compare him with yesterday", "compare readings", "compare today and yesterday", "changes",
        "what's changed"
    ],
    # 8. Cause / Reason Analysis ('Why?', 'What could be causing it?')
    "cause_reason": [
        "why is", "why are", "what is causing", "what could be causing", "reason for",
        "why did", "what caused", "why low", "why high", "why dropping", "why falling",
        "why increasing", "why deteriorating", "why worsening", "why is oxygen low",
        "why is spo2 low", "why is heart rate high", "why is bp low", "why is respiratory rate high",
        "why is blood pressure low", "why high heart rate", "why low oxygen", "what could be causing it",
        "what could be causing this", "could this be because of his condition", "what is causing this",
        "what is causing it", "what caused this", "why did that happen", "could his current condition explain",
        "why did the score increase", "why is it that high", "why is it high", "why is score high",
        "explain why"
    ],
    # 9. Deterioration / Trajectory / Improvement ('Is he getting better?')
    "deterioration_improvement": [
        "is he getting better", "is she getting better", "is he getting worse",
        "is she getting worse", "is condition improving", "is condition deteriorating",
        "is patient improving", "is patient worsening", "has he improved", "has she improved",
        "getting better", "getting worse", "improving or worsening", "better or worse",
        "how is his condition changing", "is condition getting worse", "is his condition improving",
        "is his spo2 improving", "is he stable", "is patient stable", "is she stable",
        "does anything look worse", "is anything getting worse", "is he improving", "better", "worse", "improving"
    ],
    # 10. Key Concerns & Abnormalities Summary ('what are the main concerns', 'anything worrying')
    "key_concerns_summary": [
        "what are the main concerns", "main concerns", "what's worrying you", "what is worrying you",
        "anything worrying", "anything concerning", "anything abnormal", "are there any problems",
        "any problems", "what should i be worried about", "summarize the important things",
        "summarize only the concerning findings", "give me the important points", "give me the reassuring findings",
        "what's the most important thing i should know", "what is the most important thing",
        "key takeaways", "important findings", "key findings", "summarize the important findings",
        "give me the important findings", "summarize important things", "summarize findings",
        "summarize concerning findings", "important points", "key points"
    ],
    # 11. Clinical Synthesis & Assessment ('What do you think is going on?')
    "clinical_synthesis": [
        "what do you think is going on", "what do you think", "what is your assessment",
        "what do you think about him", "what's your assessment", "what is your opinion",
        "what's your opinion", "what do you think is happening", "what do you think is causing",
        "clinical synthesis", "your thoughts"
    ],
    # 12. Longitudinal Trends Query
    "trends_query": [
        "vital trends", "show trends", "trend", "trends", "trajectory", "progression",
        "how has", "over time", "serial vitals", "last readings",
        "last 4", "last 5", "last 6", "readings history", "telemetry history"
    ],
    # 13. Transfer Decision & Unit Placement Rationale
    "recommendation_query": [
        "why is he being kept in icu", "why is he still in icu", "why in icu",
        "why is he in icu", "why is she in icu", "why icu", "can he move to hdu", "why transfer",
        "why hdu", "why re-evaluate", "why continue icu", "transfer recommendation",
        "transfer decision", "why marked", "why transfer pending", "is transfer pending",
        "why did jeevan setu recommend", "step down", "step-down", "escalat",
        "why did you recommend keeping him in icu"
    ],
    # 14. Decision History & Clinician Overrides
    "decision_history": [
        "previous transfer review", "what happened in his previous transfer review",
        "previous decision", "previous transfer", "decision history", "past decisions",
        "who reviewed", "reviewed by", "override", "overridden", "clinician decision",
        "accepted", "rejected", "what happened after", "transfer history"
    ],
    # 15. EWS & Composite Stability Index Query
    "ews_query": [
        "what is his ews", "what is the ews", "what is his ews score", "what is the ews score",
        "why is his ews high", "why is ews high", "why is the ews high", "ews score", "early warning",
        "warning score", "composite stability", "csi", "stability index", "risk score", "score breakdown"
    ],
    # 16. Documented Diagnosis / Illness Query
    "diagnosis_query": [
        "what illness does he have", "what is his diagnosis", "what condition does he have",
        "what illness", "what disease", "what condition", "medical condition", "diagnosis",
        "admitting diagnosis", "documented diagnosis", "documented condition",
        "history of", "past medical history"
    ],
    # 17. Abnormal Vitals & Red Flags
    "abnormal_vitals": [
        "what parameters are abnormal", "abnormal readings", "critical readings",
        "abnormal", "last critical", "alert", "red flag", "warning", "out of range",
        "abnormalities"
    ],
    # 18. Single Vital Query
    "vitals_query": [
        "what is his spo2", "what is the patient's current spo2", "what is the current spo2",
        "what is his heart rate", "what is his blood pressure", "what is his respiratory rate",
        "what is his temperature", "what is current hr", "what is current bp",
        "vital", "vitals", "heart rate", "hr", "pulse", "bp", "blood pressure",
        "systolic", "diastolic", "resp", "respiratory", "rr", "breathing",
        "temp", "temperature", "spo2", "oxygen", "o2", "saturation", "consciousness",
        "current vitals", "show vitals", "latest vitals", "what about his oxygen",
        "what about his breathing", "what about his heart rate", "how is his breathing",
        "how's his oxygen", "how is his oxygen level", "is he getting enough oxygen",
        "what about his bp", "what about his pulse"
    ],
    # 19. General Medical Concept Query
    "general_medical": [
        "what does low spo2 mean", "what is normal respiratory rate", "what is ews",
        "what does tachycardia mean", "what is normal blood pressure", "what does ews mean",
        "what is high blood pressure", "what is normal heart rate", "can low oxygen be dangerous",
        "is low oxygen dangerous", "what does bradycardia mean", "what is tachycardia",
        "what is bradycardia", "what is hypertension", "what is hypotension"
    ],
    # 20. Explicit Patient Summary Request
    "patient_summary": [
        "give me the patient summary", "give me the complete patient summary", "show complete patient summary",
        "give me a clinical overview", "tell me everything about this patient", "what is the patient's current status",
        "show summary", "view summary", "full summary", "patient summary", "complete summary",
        "briefing", "condition synthesis", "clinical overview", "condition overview", "who is", "profile",
        "tell me everything", "give me everything"
    ],
    "report_generation": [
        "report", "generate report", "download report", "export report", "pdf",
        "summary report", "clinical report"
    ],
    "help": [
        "help", "what can you do", "options", "guide", "menu", "instructions", "commands"
    ]
}


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
                'last_intent': None,
                'last_topic': None,
                'last_parameters': [],
                'last_assessment': None,
                'last_user_query': None,
                'last_bot_response': None,
                'turns': []
            }
        return cls._sessions[uid]

    @classmethod
    def update_state(cls, user_id, active_patient_id=None, active_patient_name=None,
                     intent=None, topic=None, parameters=None, assessment=None,
                     user_query=None, bot_response=None):
        state = cls.get_state(user_id)
        if active_patient_id is not None:
            state['active_patient_id'] = active_patient_id
        if active_patient_name is not None:
            state['active_patient_name'] = active_patient_name
        if intent is not None:
            state['last_intent'] = intent
        if topic is not None:
            state['last_topic'] = topic
        if parameters is not None:
            state['last_parameters'] = parameters
        if assessment is not None:
            state['last_assessment'] = assessment
        if user_query is not None:
            state['last_user_query'] = user_query
        if bot_response is not None:
            state['last_bot_response'] = bot_response
            state['turns'].append({'user': user_query, 'bot': bot_response, 'time': datetime.now()})
            if len(state['turns']) > 15:
                state['turns'].pop(0)

    @classmethod
    def reset_state(cls, user_id=None):
        if user_id is not None:
            uid = str(user_id)
            cls._sessions.pop(uid, None)
        else:
            cls._sessions.clear()

    @classmethod
    def clear_state(cls, user_id=None):
        cls.reset_state(user_id)


# =============================================================================
# 2. PATIENT SEARCH & DISAMBIGUATION
# =============================================================================

def search_patients_for_chat(query):
    """
    Search patients in database by name, patient code (UHID), or patient ID.
    Returns:
        tuple (match_type, list_of_patients)
        where match_type in ('none', 'single', 'multiple')
    """
    if not query or not query.strip():
        return 'none', []

    q = query.strip()

    # Try numeric ID search
    numeric_id = None
    if q.isdigit():
        numeric_id = int(q)
    elif q.upper().startswith("JS-") and q[3:].isdigit():
        numeric_id = int(q[3:])
    elif q.upper().startswith("JS") and q[2:].isdigit():
        numeric_id = int(q[2:])

    if numeric_id is not None:
        p = Patient.get_by_id(numeric_id)
        if p:
            return 'single', [_format_search_patient_item(p)]

    # Search by code or name
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

    if not rows:
        return 'none', []
    elif len(rows) == 1:
        return 'single', [_format_search_patient_item(rows[0])]
    else:
        # Check if there is an exact match
        exact_matches = [r for r in rows if r['name'].strip().lower() == q.lower() or (r.get('patient_code') and r['patient_code'].strip().lower() == q.lower())]
        if len(exact_matches) == 1:
            return 'single', [_format_search_patient_item(exact_matches[0])]
        return 'multiple', [_format_search_patient_item(r) for r in rows]


def _format_search_patient_item(p):
    """Format minimal safe patient summary for disambiguation."""
    p_id = p['patient_id']
    p_code = p.get('patient_code') or f"JS-{p_id:04d}"
    return {
        'patient_id': p_id,
        'patient_code': p_code,
        'name': p['name'],
        'age': p['age'],
        'gender': p['gender'],
        'ward_type': p.get('ward_type', 'ICU'),
        'ward_name': p.get('ward_name') or p.get('ward_type', 'ICU'),
        'bed_number': p.get('bed_number', 'N/A'),
        'status': p.get('status', 'admitted'),
        'admission_date': str(p.get('admission_date', ''))
    }


# =============================================================================
# 3. CLINICAL CONTEXT RETRIEVAL LAYER (CCRL)
# =============================================================================

def get_patient_clinical_context(patient_id):
    """
    Retrieve verified factual clinical context for a single patient from MySQL.
    Guarantees zero cross-patient data leakage and zero fabricated information.
    """
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return None

    # 1. Latest Vitals & Historical Vitals
    vitals_latest = Vitals.get_latest(patient_id)
    vitals_history = Vitals.get_history(patient_id, limit=20) or []

    # 2. EWS Record
    ews_record = EWSScore.get_latest(patient_id)

    # 3. Recommendations & Transfers History
    recommendations = Recommendation.get_by_patient(patient_id) or []
    latest_rec = recommendations[0] if recommendations else None
    transfers = db.execute_query(
        """SELECT t.*, u1.full_name AS requested_by_name, u2.full_name AS approved_by_name
           FROM transfers t
           LEFT JOIN users u1 ON t.requested_by = u1.user_id
           LEFT JOIN users u2 ON t.approved_by = u2.user_id
           WHERE t.patient_id = %s ORDER BY t.created_at DESC LIMIT 10""",
        (patient_id,), fetch=True
    ) or []

    # 4. Decisions History
    decisions = Decision.get_by_patient(patient_id, limit=10) or []

    # 5. Active Alerts
    alerts = db.execute_query(
        """SELECT * FROM alerts WHERE patient_id = %s ORDER BY created_at DESC LIMIT 5""",
        (patient_id,), fetch=True
    ) or []

    # Calculate EWS and Risk Level
    ews_score = 0
    risk_level = 'LOW'
    if ews_record and ews_record.get('total_score') is not None:
        ews_score = ews_record.get('total_score', 0)
        risk_level = ews_record.get('risk_level', get_risk_level(ews_score).upper())
    elif vitals_latest and vitals_latest.get('ews_score') is not None:
        ews_score = vitals_latest.get('ews_score', 0)
        risk_level = get_risk_level(ews_score).upper()

    # Calculate Vital Trends & Composite Stability Index
    trends = calculate_vital_trends(vitals_history)
    csi_data = calculate_composite_stability_index(vitals_latest, vitals_history, ews_score)

    p_code = patient.get('patient_code') or f"JS-{patient['patient_id']:04d}"

    freshness_note = "Latest available telemetry recorded in database."
    if vitals_latest and vitals_latest.get('recorded_at'):
        rec_time_str = str(vitals_latest.get('recorded_at'))
        freshness_note = f"Latest recorded vital signs: {rec_time_str}"

    return {
        'patient': {
            'patient_id': patient['patient_id'],
            'patient_code': p_code,
            'name': patient['name'],
            'age': patient['age'],
            'gender': patient['gender'],
            'blood_group': patient.get('blood_group'),
            'ward_type': patient.get('ward_type', 'ICU'),
            'ward_name': patient.get('ward_name', patient.get('ward_type', 'ICU')),
            'bed_number': patient.get('bed_number'),
            'diagnosis': patient.get('diagnosis'),
            'doctor_name': patient.get('doctor_name'),
            'status': patient.get('status', 'admitted'),
            'admission_date': str(patient.get('admission_date', ''))
        },
        'latest_vitals': {
            'vital_id': vitals_latest.get('vital_id') if vitals_latest else None,
            'heart_rate': vitals_latest.get('heart_rate') if vitals_latest else None,
            'blood_pressure_sys': vitals_latest.get('blood_pressure_sys') if vitals_latest else None,
            'blood_pressure_dia': vitals_latest.get('blood_pressure_dia') if vitals_latest else None,
            'respiratory_rate': vitals_latest.get('respiratory_rate') if vitals_latest else None,
            'temperature': vitals_latest.get('temperature') if vitals_latest else None,
            'spo2': vitals_latest.get('spo2') if vitals_latest else None,
            'consciousness': vitals_latest.get('consciousness', 'Alert') if vitals_latest else None,
            'recorded_at': str(vitals_latest.get('recorded_at', '')) if vitals_latest else None,
            'freshness_note': freshness_note
        } if vitals_latest else None,
        'vitals_history': [
            {
                'vital_id': v.get('vital_id'),
                'heart_rate': v.get('heart_rate'),
                'blood_pressure_sys': v.get('blood_pressure_sys'),
                'blood_pressure_dia': v.get('blood_pressure_dia'),
                'respiratory_rate': v.get('respiratory_rate'),
                'temperature': v.get('temperature'),
                'spo2': v.get('spo2'),
                'consciousness': v.get('consciousness', 'Alert'),
                'ews_score': v.get('ews_score', 0),
                'recorded_at': str(v.get('recorded_at', ''))
            } for v in vitals_history
        ],
        'ews': {
            'score': ews_score,
            'risk_level': risk_level,
            'calculated_at': str(ews_record.get('calculated_at', '')) if ews_record else (str(vitals_latest.get('recorded_at', '')) if vitals_latest else None)
        },
        'composite_stability_index': csi_data,
        'trends': trends,
        'recommendation': {
            'recommendation_id': latest_rec.get('recommendation_id') if latest_rec else None,
            'recommendation_text': latest_rec.get('recommendation_text') if latest_rec else 'No active transfer recommendation',
            'from_ward': latest_rec.get('from_ward') if latest_rec else patient.get('ward_type'),
            'to_ward': latest_rec.get('to_ward') if latest_rec else None,
            'reason': latest_rec.get('reason') if latest_rec else None,
            'status': latest_rec.get('status', 'none') if latest_rec else 'none',
            'decided_by_name': latest_rec.get('decided_by_name') if latest_rec else None,
            'decided_at': str(latest_rec.get('decided_at', '')) if latest_rec and latest_rec.get('decided_at') else None,
            'created_at': str(latest_rec.get('created_at', '')) if latest_rec else None
        } if latest_rec else None,
        'recommendations_history': [
            {
                'recommendation_id': r.get('recommendation_id'),
                'recommendation_text': r.get('recommendation_text'),
                'from_ward': r.get('from_ward'),
                'to_ward': r.get('to_ward'),
                'reason': r.get('reason'),
                'status': r.get('status'),
                'decided_by_name': r.get('decided_by_name'),
                'decided_at': str(r.get('decided_at', '')) if r.get('decided_at') else None,
                'created_at': str(r.get('created_at', ''))
            } for r in recommendations
        ],
        'decisions_history': [
            {
                'decision_id': d.get('decision_id'),
                'recommendation': d.get('recommendation'),
                'from_ward': d.get('from_ward'),
                'to_ward': d.get('to_ward'),
                'status': d.get('status'),
                'decided_by_name': d.get('decided_by_name'),
                'decided_at': str(d.get('decided_at', '')) if d.get('decided_at') else None,
                'created_at': str(d.get('created_at', ''))
            } for d in decisions
        ],
        'transfers_history': [
            {
                'transfer_id': t.get('transfer_id'),
                'from_ward': t.get('from_ward'),
                'to_ward': t.get('to_ward'),
                'from_bed_number': t.get('from_bed_number'),
                'to_bed_number': t.get('to_bed_number'),
                'reason': t.get('transfer_reason'),
                'status': t.get('status'),
                'requested_by_name': t.get('requested_by_name'),
                'approved_by_name': t.get('approved_by_name'),
                'requested_at': str(t.get('requested_at', '')) if t.get('requested_at') else None,
                'completed_at': str(t.get('completed_at', '')) if t.get('completed_at') else None
            } for t in transfers
        ],
        'alerts': [
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
    }


# =============================================================================
# 4. TREND & COMPOSITE STABILITY INDEX (CSI) ANALYTICS
# =============================================================================

def calculate_vital_trends(vitals_history):
    """
    Calculate factual trends across historical vital records.
    Returns trend status: 'Improving', 'Stable', 'Worsening', or 'Insufficient Data'.
    """
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
    """
    Calculate Composite Stability Index (CSI 0–100%) and classification.
    """
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
# 5. INTENT DETECTION & INTENT RESOLUTION
# =============================================================================

def _matches_pattern(pattern_list, text):
    """
    Check if any pattern in pattern_list matches text using strict word boundaries.
    Prevents false positive substring matches (e.g. 'hi' matching 'his' or 'history').
    """
    text_clean = re.sub(r'[^\w\s]', ' ', text.lower()).strip()
    words = set(text_clean.split())
    for p in pattern_list:
        p_clean = re.sub(r'[^\w\s]', ' ', p.lower()).strip()
        if not p_clean:
            continue
        if ' ' not in p_clean:
            if p_clean in words:
                return True
        else:
            if re.search(r'\b' + re.escape(p_clean) + r'\b', text_clean):
                return True
    return False


def _is_pure_acknowledgment(text):
    """
    Returns True if the text is solely conversational acknowledgment/closing
    (e.g., 'okay', 'thanks', 'thank you dr setu', 'got it'), without any substantive question.
    """
    if not text:
        return False
    # Remove standard acknowledgment and greeting tokens, plus doctor/setu tokens
    cleaned = re.sub(r'\b(thanks|thank you|thx|okay|ok|got it|understood|alright|great|perfect|fine|noted|dr setu|doctor|doc)\b', ' ', text.lower())
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned).strip()
    return len(cleaned) == 0


def detect_intent(message):
    """
    Detect clinical intent from user message using prioritized pattern matching with word boundaries.
    Returns:
        tuple: (intent_name, confidence)
    """
    msg = (message or "").strip().lower()

    # 1. Emergency / Critical Protocol (Highest Priority)
    if _matches_pattern(INTENT_PATTERNS['emergency_critical'], msg):
        return 'emergency_critical', 0.98

    # 2. Pure Conversational Acknowledgment (Strict: only if no substantive clinical question remains)
    if _is_pure_acknowledgment(msg):
        return 'acknowledgment', 0.99

    # 3. Prognosis / Mortality Risk / Criticality / 'Is it serious?'
    if _matches_pattern(INTENT_PATTERNS['prognosis_mortality'], msg):
        return 'prognosis_mortality', 0.98

    # 4. Historical Comparison ('Compare today with yesterday')
    if _matches_pattern(INTENT_PATTERNS['historical_comparison'], msg):
        return 'historical_comparison', 0.96

    # 5. Historical Telemetry & Past EWS Data
    if _matches_pattern(INTENT_PATTERNS['historical_data'], msg):
        return 'historical_data', 0.96

    # 6. Decision History & Clinician Reviews
    if _matches_pattern(INTENT_PATTERNS['decision_history'], msg):
        return 'decision_history', 0.95

    # 7. Transfer Decision / ICU/HDU Recommendation Rationale
    if _matches_pattern(INTENT_PATTERNS['recommendation_query'], msg):
        return 'recommendation_query', 0.95

    # 8. Documented Diagnosis / Illness Query
    if _matches_pattern(INTENT_PATTERNS['diagnosis_query'], msg):
        return 'diagnosis_query', 0.95

    # 9. Key Concerns & Critical Abnormalities Summary
    if _matches_pattern(INTENT_PATTERNS['key_concerns_summary'], msg):
        return 'key_concerns_summary', 0.95

    # 10. Clinical Decision Support Synthesis ('What do you think is going on?')
    if _matches_pattern(INTENT_PATTERNS['clinical_synthesis'], msg):
        return 'clinical_synthesis', 0.95

    # 11. Cause / Reason Analysis ('Why is his SpO2 low?', 'Why is HR high?')
    if _matches_pattern(INTENT_PATTERNS['cause_reason'], msg):
        return 'cause_reason', 0.95

    # 12. Deterioration / Trajectory / Improvement (Answer-First)
    if _matches_pattern(INTENT_PATTERNS['deterioration_improvement'], msg):
        return 'deterioration_improvement', 0.95

    # 13. Current Clinical Status / Overview ('How is he doing?', 'How is Sahil?')
    if _matches_pattern(INTENT_PATTERNS['current_status_overview'], msg):
        return 'current_status_overview', 0.95

    # 14. Explicit Patient Summary Request ONLY
    if _matches_pattern(INTENT_PATTERNS['patient_summary'], msg):
        return 'patient_summary', 0.95

    # 15. Longitudinal Trends Query
    if _matches_pattern(INTENT_PATTERNS['trends_query'], msg):
        return 'trends_query', 0.92

    # 16. General Medical Concept Query
    if _matches_pattern(INTENT_PATTERNS['general_medical'], msg):
        return 'general_medical', 0.95

    # 17. EWS Score & CSI Query
    if _matches_pattern(INTENT_PATTERNS['ews_query'], msg):
        return 'ews_query', 0.95

    # 18. Abnormal Vitals & Red Flags
    if _matches_pattern(INTENT_PATTERNS['abnormal_vitals'], msg):
        return 'abnormal_vitals', 0.92

    # 19. Single Vital Query
    if _matches_pattern(INTENT_PATTERNS['vitals_query'], msg):
        return 'vitals_query', 0.92

    # 20. Greetings / Pleasantries
    if _matches_pattern(INTENT_PATTERNS['greeting'], msg):
        return 'greeting', 0.99

    # 21. Report Generation / Help
    if _matches_pattern(INTENT_PATTERNS['report_generation'], msg):
        return 'report_generation', 0.95
    if _matches_pattern(INTENT_PATTERNS['help'], msg):
        return 'help', 0.95

    return 'general_query', 0.50


def detect_contextual_intent(message, session_state=None):
    """
    Context-aware intent classifier that resolves elliptical follow-ups, short queries,
    and natural-language variations using conversation state.
    """
    msg = (message or "").strip().lower()
    msg_clean = re.sub(r'[^\w\s]', ' ', msg).strip()
    state = session_state or {}

    # 1. Pure conversational acknowledgments
    if _is_pure_acknowledgment(msg):
        return 'acknowledgment', 0.99

    # 2. Short condition / status queries ('condition?', 'status?', 'how is he?', 'is he okay?')
    if msg_clean in ['condition', 'current condition', 'status', 'current status', 'update', 'clinical update',
                     'quick update', 'how is he', 'how is she', 'how is the patient', 'how is sahil',
                     'how does he look', 'is he okay', 'is he stable', 'what is happening', 'whats happening',
                     'what is going on', 'whats going on', 'whats the latest', 'what is the latest',
                     'whats his condition', 'what is his condition', 'tell me about him', 'give me an update']:
        return 'current_status_overview', 0.98

    # 3. Short single vital queries ('oxygen?', 'spo2?', 'bp?', 'heart rate?', 'pulse?', 'breathing?')
    if msg_clean in ['oxygen', 'spo2', 'o2', 'saturation', 'what about his oxygen', 'how is his oxygen', 'is he getting enough oxygen']:
        return 'vitals_query', 0.98
    if msg_clean in ['bp', 'blood pressure', 'systolic', 'diastolic', 'what about his bp']:
        return 'vitals_query', 0.98
    if msg_clean in ['hr', 'heart rate', 'pulse', 'what about his heart rate', 'what about his pulse']:
        return 'vitals_query', 0.98
    if msg_clean in ['rr', 'resp', 'respiratory rate', 'breathing', 'how is his breathing', 'what about his breathing']:
        return 'vitals_query', 0.98
    if msg_clean in ['temp', 'temperature']:
        return 'vitals_query', 0.98

    # 4. Short trajectory & improvement queries ('better?', 'worse?', 'is he getting better?', 'is he stable?')
    if msg_clean in ['better', 'worse', 'improving', 'deteriorating', 'stable', 'is he getting better', 'is he getting worse', 'is he stable']:
        return 'deterioration_improvement', 0.98

    # 5. Short severity / mortality queries ('serious?', 'is it serious?', 'should i be worried?', 'is he in danger?')
    if msg_clean in ['serious', 'is it serious', 'is that serious', 'is this serious', 'should i be worried', 'is he in danger', 'is he critical', 'is he going to die', 'will he die', 'will he survive']:
        return 'prognosis_mortality', 0.98

    # 6. Short historical / changes queries ('what changed?', 'what changed overnight?', 'what happened yesterday?')
    if msg_clean in ['what changed', 'what changed overnight', 'what happened overnight', 'what happened yesterday', 'what was it yesterday', 'compare today with yesterday', 'compare with yesterday', 'changes']:
        return 'historical_comparison', 0.98

    # 7. Elliptical 'Why?' / 'How come?' / 'Why is that?' follow-up
    if msg_clean in ['why', 'how come', 'why is that', 'why did that happen', 'why though', 'explain why']:
        last_intent = state.get('last_intent')
        if last_intent in ['recommendation_query']:
            return 'recommendation_query', 0.95
        if last_intent in ['ews_query']:
            return 'cause_reason', 0.95
        if last_intent in ['vitals_query']:
            return 'cause_reason', 0.95
        return 'cause_reason', 0.95

    # 8. 'What could be causing it?' / 'What is causing this?' / 'Could this be because of his condition?'
    if any(q in msg for q in ['what could be causing', 'what is causing', 'could this be because', 'what caused this', 'what is the cause', 'what caused']):
        return 'cause_reason', 0.95

    # 9. Key concerns / abnormalities / 'anything worrying?' / 'what are the main concerns?'
    if any(q in msg for q in ['main concerns', 'what are the main concerns', 'what is worrying you', 'whats worrying you', 'anything worrying', 'anything concerning', 'anything abnormal', 'are there any problems', 'what should i be worried about']):
        return 'key_concerns_summary', 0.95

    # 10. Documented diagnosis
    if any(q in msg for q in ['what illness does he have', 'what is his diagnosis', 'what disease', 'what condition does he have']):
        return 'diagnosis_query', 0.95

    # 11. Full patient summary request
    if any(q in msg for q in ['tell me everything', 'give me everything', 'full summary', 'complete summary', 'give me the complete patient summary', 'give me a clinical overview']):
        return 'patient_summary', 0.95

    # 12. Fallback to full prioritized pattern detection
    return detect_intent(message)


# =============================================================================
# 6. ADVANCED CLINICAL REASONING SYNTHESIZERS
# =============================================================================

def format_conversational_greeting(p_name=None, p_code=None):
    """
    Conversational response to greetings ('How are you?', 'Hi', etc.).
    Guarantees zero database clinical summary dumps.
    """
    if p_name and p_code:
        return (
            f"I'm doing well, Doctor. I am ready to assist you with clinical rounds for patient **{p_name}** ({p_code}).\n\n"
            f"You can ask me about their current condition, vital trends, EWS risk score, transfer assessments, or specific parameters."
        )
    return (
        "Hello, Doctor. I am Dr. Setu, your clinical decision-support assistant for ICU–HDU patient management.\n\n"
        "Please enter or search for a patient's name or Patient ID to begin clinical rounds."
    )


def format_conversational_help(p_name=None, p_code=None):
    """
    Explains Dr. Setu's clinical assistant capabilities.
    """
    prefix = f"For patient **{p_name}** ({p_code}), I" if (p_name and p_code) else "I"
    return (
        f"{prefix} can help you review:\n"
        f"• **Current Condition & Vitals**: Current clinical status, telemetry values, and alert flags.\n"
        f"• **Clinical Reasoning**: Multi-parameter correlation and physiological causes.\n"
        f"• **Trends & Trajectory**: Longitudinal trends and stability index.\n"
        f"• **EWS & Risk Breakdown**: Early Warning Score point contributions.\n"
        f"• **Transfer Decisions**: ICU vs HDU transfer recommendations and clinician review history.\n"
        f"• **Documented Diagnosis**: Stored medical diagnosis from hospital records."
    )


def format_conversational_acknowledgment(p_name=None):
    """
    Conversational response to 'Thanks', 'Okay', 'That's helpful', etc.
    """
    if p_name:
        return f"You're welcome, Doctor. I'm ready if you'd like to review **{p_name}**'s vital trends, compare with yesterday, or check transfer recommendations."
    return "You're welcome, Doctor. Let me know if you'd like to review any patient's vitals, trends, or transfer assessments."


def reason_current_status_overview(context):
    """
    Broad, concise clinical overview for 'condition?', 'how is he?', 'status?', 'tell me about Sahil', etc.
    Provides unit, vitals, concern pattern, trend, EWS, decision support recommendation, and timestamp.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    r = context.get('recommendation')
    csi = context.get('composite_stability_index', {})
    trends = context.get('trends', {})

    p_name = p['name']
    unit = p.get('ward_type', 'ICU')
    bed = f" (Bed {p['bed_number']})" if p.get('bed_number') else ""
    rec_time = v.get('recorded_at', 'recent') if v else 'N/A'

    if not v:
        return (
            f"**{p_name}** is currently admitted in the **{unit}**{bed}.\n\n"
            f"There are currently no recorded vital signs in the database for this patient.\n"
            f"Documented Diagnosis: **{p.get('diagnosis') or 'None documented'}**."
        )

    findings = []
    if v.get('spo2') is not None:
        spo2_tag = " (Low / Hypoxemia)" if v.get('spo2') < 94 else " (Normal)"
        findings.append(f"SpO₂: **{_fmt_val(v.get('spo2'))}%**{spo2_tag}")
    if v.get('respiratory_rate') is not None:
        rr_tag = " (Tachypnea / Elevated)" if v.get('respiratory_rate') > 24 else (" (Bradypnea)" if v.get('respiratory_rate') < 12 else " (Normal)")
        findings.append(f"Respiratory Rate: **{_fmt_val(v.get('respiratory_rate'))}/min**{rr_tag}")
    if v.get('heart_rate') is not None:
        hr_tag = " (Tachycardia)" if v.get('heart_rate') > 100 else (" (Bradycardia)" if v.get('heart_rate') < 50 else " (Normal)")
        findings.append(f"Heart Rate: **{_fmt_val(v.get('heart_rate'))} bpm**{hr_tag}")
    if v.get('blood_pressure_sys') is not None:
        dia_str = f"/{_fmt_val(v.get('blood_pressure_dia'))}" if v.get('blood_pressure_dia') is not None else ""
        findings.append(f"Blood Pressure: **{_fmt_val(v.get('blood_pressure_sys'))}{dia_str} mmHg**")
    if v.get('temperature') is not None:
        temp_tag = " (Fever / Pyrexia)" if v.get('temperature') > 38.0 else ""
        findings.append(f"Temperature: **{_fmt_val(v.get('temperature'))} °C**{temp_tag}")

    findings_str = "\n• ".join(findings) if findings else "No specific telemetry parameters recorded."
    direction = trends.get('overall_direction', 'insufficient data').lower()
    score = e.get('score', 0)
    risk = e.get('risk_level', get_risk_level(score).upper())

    rec_text = r.get('recommendation_text', 'Keep in ICU') if r else 'Under Evaluation'
    rec_reason = r.get('reason') if (r and r.get('reason')) else "Physiological Early Warning Score criteria"
    diag_str = f" (Documented condition: *{p.get('diagnosis')}*)" if p.get('diagnosis') else ""

    condition_adjective = "critical" if score >= 5 else ("concerning / unstable" if score >= 3 else "stable")

    return (
        f"**{p_name}** is currently admitted in the **{unit}**{bed}{diag_str}.\n"
        f"Based on the latest available records, the patient's current condition is **{condition_adjective}**.\n\n"
        f"**Main Clinical Findings:**\n"
        f"• {findings_str}\n\n"
        f"• **Recent Trend**: {direction}\n"
        f"• **Early Warning Score (EWS)**: **{score}** ({risk} Risk)\n"
        f"• **Jeevan Setu Recommendation**: **{rec_text}** ({rec_reason})\n\n"
        f"*(Latest available telemetry recorded at {rec_time})*"
    )


def reason_historical_comparison(context, query_lower):
    """
    Compares latest vs previous/yesterday's readings with clear deltas and timestamp comparisons.
    """
    p = context['patient']
    history = context.get('vitals_history', [])
    latest = context.get('latest_vitals')

    if not history or len(history) < 2:
        if latest:
            return (
                f"For patient **{p['name']}**, only one telemetry reading is currently available in the database "
                f"(recorded at {latest.get('recorded_at', 'recent')}). There are not enough historical readings "
                f"from yesterday to calculate a multi-day comparison."
            )
        return f"No historical telemetry records exist in the database for patient {p['name']}."

    current = history[0]
    previous = history[1]

    curr_time = current.get('recorded_at', 'Today')
    prev_time = previous.get('recorded_at', 'Previous reading')

    lines = [
        f"**Clinical Comparison for {p['name']} ({curr_time} vs {prev_time}):**\n"
    ]

    c_spo2, p_spo2 = current.get('spo2'), previous.get('spo2')
    if c_spo2 is not None and p_spo2 is not None:
        change = "decreased" if c_spo2 < p_spo2 else ("increased" if c_spo2 > p_spo2 else "remained stable")
        lines.append(f"• **Oxygen Saturation (SpO₂)**: {_fmt_val(p_spo2)}% → **{_fmt_val(c_spo2)}%** ({change})")
    elif c_spo2 is not None:
        lines.append(f"• **Oxygen Saturation (SpO₂)**: Current {_fmt_val(c_spo2)}% (Previous unrecorded)")

    c_rr, p_rr = current.get('respiratory_rate'), previous.get('respiratory_rate')
    if c_rr is not None and p_rr is not None:
        change = "increased (worsened)" if c_rr > p_rr else ("decreased" if c_rr < p_rr else "remained stable")
        lines.append(f"• **Respiratory Rate**: {_fmt_val(p_rr)}/min → **{_fmt_val(c_rr)}/min** ({change})")
    elif c_rr is not None:
        lines.append(f"• **Respiratory Rate**: Current {_fmt_val(c_rr)}/min")

    c_hr, p_hr = current.get('heart_rate'), previous.get('heart_rate')
    if c_hr is not None and p_hr is not None:
        change = "increased" if c_hr > p_hr else ("decreased" if c_hr < p_hr else "stable")
        lines.append(f"• **Heart Rate**: {_fmt_val(p_hr)} bpm → **{_fmt_val(c_hr)} bpm** ({change})")

    c_bp, p_bp = current.get('blood_pressure_sys'), previous.get('blood_pressure_sys')
    if c_bp is not None and p_bp is not None:
        lines.append(f"• **Systolic BP**: {_fmt_val(p_bp)} mmHg → **{_fmt_val(c_bp)} mmHg**")

    c_ews, p_ews = current.get('ews_score', 0), previous.get('ews_score', 0)
    change_ews = "increased (higher risk)" if c_ews > p_ews else ("decreased (improving)" if c_ews < p_ews else "unchanged")
    lines.append(f"• **EWS Score**: {p_ews} → **{c_ews}** ({change_ews})")

    lines.append(
        f"\n**Summary**: Compared to the previous reading at {prev_time}, the patient's physiology demonstrates "
        f"{'elevated stress and higher early warning scores' if c_ews >= p_ews else 'stabilizing physiological parameters'}."
    )
    return "\n".join(lines)


def reason_key_concerns_summary(context, query_lower):
    """
    Summarizes key abnormal and concerning findings for 'Summarize the important things'.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    r = context.get('recommendation')

    if not v:
        return f"No telemetry readings are recorded in the database for patient {p['name']}."

    rec_time = v.get('recorded_at', 'recent')
    score = e.get('score', 0)
    risk = e.get('risk_level', get_risk_level(score).upper())

    lines = [
        f"**Key Clinical Concerns & Critical Findings for {p['name']} ({p['patient_code']}):**\n"
    ]

    concerns = []
    if v.get('spo2') is not None and v.get('spo2') < 94:
        concerns.append(f"**Low SpO₂**: {_fmt_val(v.get('spo2'))}% (Hypoxemia risk)")
    if v.get('respiratory_rate') is not None and v.get('respiratory_rate') > 24:
        concerns.append(f"**Elevated Respiratory Rate**: {_fmt_val(v.get('respiratory_rate'))}/min (Significant respiratory compromise)")
    if v.get('heart_rate') is not None and (v.get('heart_rate') > 100 or v.get('heart_rate') < 50):
        concerns.append(f"**Abnormal Heart Rate**: {_fmt_val(v.get('heart_rate'))} bpm")
    if v.get('blood_pressure_sys') is not None and v.get('blood_pressure_sys') < 90:
        concerns.append(f"**Hypotension**: {_fmt_val(v.get('blood_pressure_sys'))} mmHg systolic")

    if concerns:
        for c in concerns:
            lines.append(f"• {c}")
    else:
        lines.append("• No acute vital parameter threshold breaches in the latest reading.")

    lines.append(f"• **EWS Score**: **{score}** ({risk} Risk Category)")
    if r:
        lines.append(f"• **Current Decision Recommendation**: **{r.get('recommendation_text')}** ({r.get('reason')})")
    if p.get('diagnosis'):
        lines.append(f"• **Documented Condition**: {p.get('diagnosis')}")

    lines.append(f"\n*(Telemetry verified as of {rec_time})*")
    return "\n".join(lines)


def reason_clinical_synthesis(context, query_lower):
    """
    Provides decision support clinical synthesis for 'What do you think is going on?'
    Clearly separates system evidence from definitive doctor diagnosis.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    r = context.get('recommendation')
    trends = context.get('trends', {})

    if not v:
        return f"There is insufficient telemetry data in the database for patient {p['name']} to provide a clinical synthesis."

    direction = trends.get('overall_direction', 'Worsening').lower()
    score = e.get('score', 0)
    risk = e.get('risk_level', get_risk_level(score).upper())

    diag_note = f"in the context of documented *{p.get('diagnosis')}*" if p.get('diagnosis') else "without a documented primary diagnosis"

    return (
        f"Based on the available Jeevan Setu telemetry data, the main concern for **{p['name']}** is an overall **{direction}** physiological pattern {diag_note}.\n\n"
        f"• **Physiological Evidence**: EWS is currently **{score}** ({risk} Risk), driven by abnormal vital sign parameters.\n"
        f"• **Decision Support Assessment**: Jeevan Setu recommends **{r.get('recommendation_text', 'Continue ICU Care') if r else 'ICU Monitoring'}**.\n\n"
        f"*Clinical Note: This system assessment correlates recorded telemetry and early warning algorithms to support your clinical review. Definitive diagnostic decisions should be guided by bedside examination and comprehensive clinical workup.*"
    )


def reason_single_parameter(context, query_lower):
    """
    Answers single vital parameter questions (e.g., 'What is his SpO2?').
    Focuses specifically on the requested parameter with current value, timestamp, previous delta, and threshold band.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    trends = context.get('trends', {}).get('parameters', {})
    rec_time = v.get('recorded_at', 'Latest') if v else 'Not recorded'

    if not v:
        return f"No vital sign records are currently available in the database for patient {p['name']} ({p['patient_code']})."

    # 1. SpO2 / Oxygen
    if 'spo2' in query_lower or 'oxygen' in query_lower or 'o2' in query_lower or 'saturation' in query_lower:
        spo2 = v.get('spo2')
        if spo2 is None:
            return f"Oxygen Saturation (SpO2) is currently **not recorded (N/A)** in the database for patient {p['name']}."
        t_info = trends.get('spo2')
        prev_str = f"Previous readings: {', '.join(_fmt_val(x) + '%' for x in t_info['previous_values'])}, indicating a **{t_info['direction'].lower()}** trend." if t_info and t_info.get('previous_values') else "No previous baseline readings recorded."
        band = "Critical (<92%)" if spo2 < 92 else ("Caution (92-94%)" if spo2 < 95 else "Normal (≥95%)")
        return (
            f"The latest recorded Oxygen Saturation (SpO2) for {p['name']} is **{_fmt_val(spo2)}%**, recorded at {rec_time}.\n\n"
            f"• {prev_str}\n"
            f"• Jeevan Setu Parameter Band: **{band}**"
        )

    # 2. Heart Rate / Pulse
    if 'heart rate' in query_lower or 'pulse' in query_lower or 'hr' in query_lower:
        hr = v.get('heart_rate')
        if hr is None:
            return f"Heart Rate is currently **not recorded (N/A)** in the database for patient {p['name']}."
        t_info = trends.get('heart_rate')
        prev_str = f"Previous readings: {', '.join(_fmt_val(x) + ' bpm' for x in t_info['previous_values'])}, indicating a **{t_info['direction'].lower()}** trend." if t_info and t_info.get('previous_values') else "No previous baseline readings recorded."
        score = calculate_parameter_score('heart_rate', hr)
        band = "Critical" if score == 3 else ("Caution" if score in (1, 2) else "Normal")
        return (
            f"The latest recorded Heart Rate for {p['name']} is **{_fmt_val(hr)} bpm**, recorded at {rec_time}.\n\n"
            f"• {prev_str}\n"
            f"• Parameter Band: **{band}** (EWS Contribution: +{score})"
        )

    # 3. Respiratory Rate / Breathing
    if 'resp' in query_lower or 'breathing' in query_lower or 'rr' in query_lower:
        rr = v.get('respiratory_rate')
        if rr is None:
            return f"Respiratory Rate is currently **not recorded (N/A)** in the database for patient {p['name']}."
        t_info = trends.get('respiratory_rate')
        prev_str = f"Previous readings: {', '.join(_fmt_val(x) + '/min' for x in t_info['previous_values'])}, indicating a **{t_info['direction'].lower()}** trend." if t_info and t_info.get('previous_values') else "No previous baseline readings recorded."
        score = calculate_parameter_score('respiratory_rate', rr)
        band = "Critical" if score == 3 else ("Caution" if score in (1, 2) else "Normal")
        return (
            f"The latest recorded Respiratory Rate for {p['name']} is **{_fmt_val(rr)} breaths/min**, recorded at {rec_time}.\n\n"
            f"• {prev_str}\n"
            f"• Parameter Band: **{band}** (EWS Contribution: +{score})"
        )

    # 4. Blood Pressure
    if 'bp' in query_lower or 'blood pressure' in query_lower or 'systolic' in query_lower or 'diastolic' in query_lower:
        sys_bp = v.get('blood_pressure_sys')
        dia_bp = v.get('blood_pressure_dia')
        if sys_bp is None:
            return f"Blood Pressure measurements are currently **not recorded (N/A)** in the database for patient {p['name']}."
        dia_str = f"/{_fmt_val(dia_bp)}" if dia_bp is not None else ""
        score = calculate_parameter_score('blood_pressure_sys', sys_bp)
        band = "Critical" if score == 3 else ("Caution" if score in (1, 2) else "Normal")
        return (
            f"The latest recorded Blood Pressure for {p['name']} is **{_fmt_val(sys_bp)}{dia_str} mmHg**, recorded at {rec_time}.\n\n"
            f"• Parameter Band: **{band}** (EWS Contribution: +{score})"
        )

    # 5. Body Temperature
    if 'temp' in query_lower or 'temperature' in query_lower:
        temp = v.get('temperature')
        if temp is None:
            return f"Body Temperature is currently **not recorded (N/A)** in the database for patient {p['name']}."
        score = calculate_parameter_score('temperature', temp)
        band = "Critical" if score in (2, 3) else ("Caution" if score == 1 else "Normal")
        return (
            f"The latest recorded Body Temperature for {p['name']} is **{_fmt_val(temp)} °C**, recorded at {rec_time}.\n\n"
            f"• Parameter Band: **{band}** (EWS Contribution: +{score})"
        )

def format_vital_parameters_analysis(context, specific_param=None):
    """
    Format vital parameters analysis (Backwards-compatible wrapper around reason_single_parameter).
    """
    param_str = specific_param or "vitals"
    return reason_single_parameter(context, param_str)


def getClinicalContext(patient_id, intent="GENERAL"):
    """
    Intent-specific clinical context retrieval layer (Section 17).
    Returns intent-optimized context payload for performance and precision.
    """
    full_context = get_patient_clinical_context(patient_id)
    if not full_context:
        return None

    intent_upper = (intent or "").upper()

    if intent_upper in ["GREETING", "HELP"]:
        # No heavy telemetry required for greetings
        return {
            'patient_id': patient_id,
            'name': full_context['patient']['name'],
            'patient_code': full_context['patient']['patient_code']
        }

    if intent_upper in ["CURRENT_VITALS", "SINGLE_PARAMETER"]:
        return {
            'patient': full_context['patient'],
            'latest_vitals': full_context.get('latest_vitals'),
            'ews': full_context.get('ews')
        }

    if intent_upper in ["TREND_ANALYSIS", "DETERIORATION_IMPROVEMENT"]:
        return {
            'patient': full_context['patient'],
            'latest_vitals': full_context.get('latest_vitals'),
            'vitals_history': full_context.get('vitals_history'),
            'trends': full_context.get('trends'),
            'ews': full_context.get('ews')
        }

    if intent_upper in ["TRANSFER_DECISION", "RECOMMENDATION"]:
        return {
            'patient': full_context['patient'],
            'current_unit': full_context['patient']['ward_type'],
            'recommendation': full_context.get('recommendation'),
            'ews': full_context.get('ews'),
            'composite_stability_index': full_context.get('composite_stability_index'),
            'latest_vitals': full_context.get('latest_vitals'),
            'trends': full_context.get('trends')
        }

    if intent_upper in ["DOCUMENTED_CONDITION", "DIAGNOSIS"]:
        return {
            'patient_id': patient_id,
            'diagnosis': full_context['patient'].get('diagnosis')
        }

    return full_context


def reason_cause_and_multi_parameter(context, query_lower):
    """
    Physician-grade multi-parameter correlation explaining why a vital or condition is changing.
    Correlates SpO2 + RR + HR + BP + Temp + Diagnosis + EWS + Decision Engine rationale.
    Follows the Answer-First Rule.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    r = context.get('recommendation')
    csi = context.get('composite_stability_index', {})
    trends = context.get('trends', {})
    p_params = trends.get('parameters', {}) if trends.get('has_sufficient_data') else {}

    if not v:
        return f"No vital sign measurements are currently available in the database for patient {p['name']} ({p['patient_code']}) to perform clinical reasoning."

    # Identify primary focus
    focus = "general"
    if 'oxygen' in query_lower or 'spo2' in query_lower or 'o2' in query_lower:
        focus = "oxygen"
    elif 'heart rate' in query_lower or 'pulse' in query_lower or 'hr' in query_lower or 'tachycardia' in query_lower:
        focus = "heart_rate"
    elif 'resp' in query_lower or 'breathing' in query_lower or 'rr' in query_lower:
        focus = "respiratory"
    elif 'bp' in query_lower or 'blood pressure' in query_lower or 'hypotension' in query_lower:
        focus = "blood_pressure"

    lines = []
    spo2_val = _fmt_val(v.get('spo2'))
    rr_val = _fmt_val(v.get('respiratory_rate'))
    hr_val = _fmt_val(v.get('heart_rate'))
    sbp_val = _fmt_val(v.get('blood_pressure_sys'))
    rec_time = v.get('recorded_at', 'recent')

    if focus == "oxygen":
        spo2_info = p_params.get('spo2')
        prev_str = ""
        if spo2_info and spo2_info.get('previous_values'):
            prev_vals = ", ".join(f"{_fmt_val(x)}%" for x in spo2_info['previous_values'][:3])
            prev_str = f", which is lower than previous readings of {prev_vals}"
        lines.append(f"The latest recorded SpO2 for {p['name']} is **{spo2_val}%** (recorded at {rec_time}){prev_str}.")

        correlates = []
        if v.get('respiratory_rate') is not None:
            rr_info = p_params.get('respiratory_rate')
            if rr_info and rr_info.get('previous_values'):
                correlates.append(f"respiratory rate has changed from {_fmt_val(rr_info['oldest_in_window'])}/min to {rr_val}/min")
            else:
                correlates.append(f"respiratory rate is {rr_val}/min")
        if v.get('heart_rate') is not None:
            correlates.append(f"heart rate is {hr_val} bpm")

        if correlates:
            lines.append(f"Concurrently, the " + " and ".join(correlates) + ".")

        lines.append("\n**Clinical Interpretation:**")
        lines.append(
            "This combination suggests acute respiratory compromise and compensatory physiological response "
            "(tachypnea and tachycardia secondary to increased work of breathing and hypoxic drive)."
        )

    elif focus == "heart_rate":
        hr_info = p_params.get('heart_rate')
        prev_str = ""
        if hr_info and hr_info.get('previous_values'):
            prev_vals = ", ".join(f"{_fmt_val(x)} bpm" for x in hr_info['previous_values'][:3])
            prev_str = f" (previously {prev_vals})"
        lines.append(f"The latest recorded Heart Rate is **{hr_val} bpm**{prev_str}, recorded at {rec_time}.")

        lines.append("\n**Correlating Parameters:**")
        if v.get('blood_pressure_sys') is not None:
            lines.append(f"• Systolic Blood Pressure: {sbp_val} mmHg")
        if v.get('temperature') is not None:
            lines.append(f"• Body Temperature: {_fmt_val(v.get('temperature'))} °C")
        if v.get('spo2') is not None:
            lines.append(f"• Oxygen Saturation (SpO2): {spo2_val}%")

        lines.append("\n**Clinical Interpretation:**")
        lines.append(
            "Elevated heart rate may reflect physiological stress, systemic inflammatory response/fever, "
            "compensatory tachycardia for compromised oxygenation, or volume depletion."
        )

    else:
        overall_dir = trends.get('overall_direction', 'Worsening')
        lines.append(f"Based on the latest available records, the patient's condition demonstrates a **{overall_dir.lower()} physiological trend**.")
        lines.append("\n**Key Contributing Telemetry Findings:**")
        if v.get('spo2') is not None:
            lines.append(f"• SpO2: {spo2_val}% ({p_params.get('spo2', {}).get('direction', 'Stable') if p_params.get('spo2') else 'Recorded'})")
        if v.get('respiratory_rate') is not None:
            lines.append(f"• Respiratory Rate: {rr_val}/min ({p_params.get('respiratory_rate', {}).get('direction', 'Stable') if p_params.get('respiratory_rate') else 'Recorded'})")
        if v.get('heart_rate') is not None:
            lines.append(f"• Heart Rate: {hr_val} bpm ({p_params.get('heart_rate', {}).get('direction', 'Stable') if p_params.get('heart_rate') else 'Recorded'})")
        if v.get('blood_pressure_sys') is not None:
            lines.append(f"• Systolic BP: {sbp_val} mmHg")

    # Documented Diagnosis Context
    diag = p.get('diagnosis')
    if diag and diag.strip():
        lines.append(f"\n**Documented Clinical Context:**\nThe patient's records document **{diag.strip()}**, which provides essential clinical context for interpreting these physiological fluctuations.")
    else:
        lines.append("\n**Documented Clinical Context:**\nNo documented primary diagnosis is currently recorded in the Jeevan Setu database.")

    # Jeevan Setu Decision Support Integration
    rec_text = r.get('recommendation_text', 'CONTINUE_ICU') if r else 'Under Evaluation'
    rec_reason = r.get('reason') if (r and r.get('reason')) else "Physiological Early Warning Score criteria"
    lines.append("\n**Jeevan Setu Decision Support Assessment:**")
    lines.append(f"• Early Warning Score (EWS): **{e.get('score', 0)}** ({e.get('risk_level', 'LOW')} Risk)")
    lines.append(f"• Composite Stability Index: **{csi.get('index', 'N/A')}%** ({csi.get('classification', 'Stable')})")
    lines.append(f"• Current Recommendation: **{rec_text}** (Reason: {rec_reason})")

    lines.append(
        "\n*Clinical Note: The available database records indicate physiological concern, but database telemetry "
        "alone cannot establish a definitive single etiology without direct bedside clinical assessment by the treating team.*"
    )

    return "\n".join(lines)


def reason_historical_data(context, query_lower):
    """
    Answers historical questions specifically (e.g. 'What was his EWS yesterday?', 'Previous vitals').
    Guarantees clear distinction between current and historical data.
    """
    p = context['patient']
    history = context.get('vitals_history', [])
    latest = context.get('latest_vitals')

    if not history:
        return f"No historical vital records or previous EWS logs are found in the database for patient {p['name']} ({p['patient_code']})."

    lines = [f"**Historical Telemetry Records for {p['name']} ({p['patient_code']}):**\n"]

    if 'ews' in query_lower:
        lines.append("**Previous Recorded EWS Trajectory:**")
        for idx, h in enumerate(history[:6], 1):
            t_str = h.get('recorded_at') or f"Reading #{idx}"
            score = h.get('ews_score', 0)
            risk = get_risk_level(score).upper()
            status_tag = "(Current Reading)" if idx == 1 else "(Previous Reading)"
            lines.append(f"• {t_str}: EWS Score **{score}** ({risk} Risk) {status_tag}")
        return "\n".join(lines)

    lines.append("**Serial Historical Vitals:**")
    for idx, h in enumerate(history[:5], 1):
        t_str = h.get('recorded_at') or f"Reading #{idx}"
        dia_str = f"/{_fmt_val(h.get('blood_pressure_dia'))}" if h.get('blood_pressure_dia') is not None else ""
        bp_str = f"{_fmt_val(h.get('blood_pressure_sys'))}{dia_str} mmHg" if h.get('blood_pressure_sys') is not None else "N/A"
        status_tag = "(Current)" if idx == 1 else "(Historical)"
        lines.append(
            f"**{idx}. {t_str} {status_tag}**:\n"
            f"   SpO2: {_fmt_val(h.get('spo2'))}% | RR: {_fmt_val(h.get('respiratory_rate'))}/min | HR: {_fmt_val(h.get('heart_rate'))} bpm | BP: {bp_str} | EWS: {h.get('ews_score', 0)}"
        )

    return "\n".join(lines)


def reason_prognosis_and_mortality(context):
    """
    Prognosis and high-risk mortality inquiries.
    Communicates seriousness without false certainty and emphasizes prompt clinical review.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    r = context.get('recommendation')
    csi = context.get('composite_stability_index', {})
    trends = context.get('trends', {})

    if not v:
        return f"I cannot provide a clinical risk evaluation because no vital signs are recorded in the database for patient {p['name']}."

    p_params = trends.get('parameters', {}) if trends.get('has_sufficient_data') else {}

    lines = [
        f"I cannot determine from the available data whether the patient will die, and no clinical decision support system "
        f"should make definitive mortality predictions from database telemetry measurements alone.",
        f"\nHowever, the current records for **{p['name']}** ({p['patient_code']}) show important concerning physiological findings:\n"
    ]

    if v.get('spo2') is not None:
        spo2_info = p_params.get('spo2')
        delta_str = f" (trend: {spo2_info['direction']} from {_fmt_val(spo2_info['oldest_in_window'])}%)" if spo2_info else ""
        lines.append(f"• Oxygen Saturation (SpO2): **{_fmt_val(v.get('spo2'))}%**{delta_str}")

    if v.get('respiratory_rate') is not None:
        rr_info = p_params.get('respiratory_rate')
        delta_str = f" (trend: {rr_info['direction']} from {_fmt_val(rr_info['oldest_in_window'])}/min)" if rr_info else ""
        lines.append(f"• Respiratory Rate: **{_fmt_val(v.get('respiratory_rate'))}/min**{delta_str}")

    if v.get('heart_rate') is not None:
        lines.append(f"• Heart Rate: **{_fmt_val(v.get('heart_rate'))} bpm**")

    if v.get('blood_pressure_sys') is not None:
        dia_str = f"/{_fmt_val(v.get('blood_pressure_dia'))}" if v.get('blood_pressure_dia') is not None else ""
        lines.append(f"• Blood Pressure: **{_fmt_val(v.get('blood_pressure_sys'))}{dia_str} mmHg**")

    lines.append(f"• Level of Consciousness: **{v.get('consciousness', 'Alert')}**")
    lines.append(f"• Early Warning Score (EWS): **{e.get('score', 0)}** ({e.get('risk_level', 'LOW')} Risk)")
    lines.append(f"• Composite Stability Index: **{csi.get('index', 'N/A')}%** ({csi.get('classification', 'Stable')})")
    lines.append(f"• Telemetry Timestamp: {v.get('recorded_at', 'Latest')}")

    rec_text = r.get('recommendation_text', 'CONTINUE_ICU') if r else 'CONTINUE_ICU'
    rec_reason = r.get('reason') if (r and r.get('reason')) else "Physiological instability criteria"

    lines.append(
        f"\n**Jeevan Setu Clinical Assessment:**\n"
        f"The current recommendation is **{rec_text}** due to: {rec_reason}."
    )
    lines.append(
        f"\n**Action Required:**\n"
        f"These findings indicate active physiological compromise. This situation requires immediate bedside assessment "
        f"and continuous monitoring by the treating ICU / critical care clinical team."
    )

    return "\n".join(lines)


def reason_deterioration_or_improvement(context, query_lower):
    """
    Answers direct 'Is he improving/worsening?' with Answer-First Rule followed by structured trajectory evidence.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    trends = context.get('trends', {})

    if not v:
        return f"No vital sign records exist for patient {p['name']} ({p['patient_code']}) to determine condition trajectory."

    if not trends.get('has_sufficient_data'):
        return (
            f"Based on the single recorded reading for {p['name']}, current EWS is **{e.get('score', 0)}** ({e.get('risk_level', 'LOW')}). "
            f"There is not enough historical data to determine a reliable trend."
        )

    overall_dir = trends.get('overall_direction', 'Stable')
    p_params = trends.get('parameters', {})

    lines = []
    # Check if user specifically asked about SpO2 improving/worsening
    if 'spo2' in query_lower or 'oxygen' in query_lower:
        sp = p_params.get('spo2')
        if sp:
            is_better = sp['direction'] == 'Improving'
            is_worse = sp['direction'] == 'Worsening'
            ans = "No" if is_worse else ("Yes" if is_better else "Relatively stable")
            lines.append(f"**{ans}. Oxygen Saturation (SpO2) is currently {_fmt_val(sp['current'])}% and has {sp['direction'].lower()} from {_fmt_val(sp['oldest_in_window'])}% over recent recorded readings.**")
        else:
            lines.append(f"SpO2 is recorded at {_fmt_val(v.get('spo2'))}%.")
    else:
        if overall_dir == "WORSENING":
            lines.append(f"**Yes, the available recent readings show a worsening physiological trend for {p['name']}.**")
        elif overall_dir == "IMPROVING":
            lines.append(f"**Yes, the available recent readings show an improving physiological trend for {p['name']}.**")
        elif overall_dir == "MIXED":
            lines.append(f"**The recent readings show a mixed physiological pattern (some parameters improving while others are worsening) for {p['name']}.**")
        else:
            lines.append(f"**The recent readings indicate relative physiological stability across recorded parameters for {p['name']}.**")

    lines.append("\n**Trajectory Breakdown:**")
    if p_params.get('spo2'):
        sp = p_params['spo2']
        lines.append(f"• SpO2: {sp['direction']} {sp['symbol']} ({_fmt_val(sp['oldest_in_window'])}% → {_fmt_val(sp['current'])}%)")
    if p_params.get('respiratory_rate'):
        rr = p_params['respiratory_rate']
        lines.append(f"• Respiratory Rate: {rr['direction']} {rr['symbol']} ({_fmt_val(rr['oldest_in_window'])}/min → {_fmt_val(rr['current'])}/min)")
    if p_params.get('heart_rate'):
        hr = p_params['heart_rate']
        lines.append(f"• Heart Rate: {hr['direction']} {hr['symbol']} ({_fmt_val(hr['oldest_in_window'])} bpm → {_fmt_val(hr['current'])} bpm)")
    if p_params.get('blood_pressure_sys'):
        bp = p_params['blood_pressure_sys']
        lines.append(f"• Systolic BP: {bp['direction']} {bp['symbol']} ({_fmt_val(bp['oldest_in_window'])} mmHg → {_fmt_val(bp['current'])} mmHg)")
    if p_params.get('temperature'):
        tp = p_params['temperature']
        lines.append(f"• Temperature: {tp['direction']} {tp['symbol']} ({_fmt_val(tp['oldest_in_window'])} °C → {_fmt_val(tp['current'])} °C)")

    lines.append(f"\n• Current EWS Score: **{e.get('score', 0)}** ({e.get('risk_level', 'LOW')} Risk)")
    lines.append(f"• Latest Telemetry Recorded: {v.get('recorded_at')}")

    return "\n".join(lines)


def reason_emergency_critical(context, query):
    """
    Immediate escalation for critical symptoms or acute desaturation.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})

    lines = [
        "🚨 **CRITICAL EMERGENCY PROTOCOL ACTIVATED** 🚨\n",
        "**IMMEDIATE CLINICAL ACTION REQUIRED:**",
        "The reported presentation represents an acute, potentially life-threatening clinical situation.",
        "1. Immediately initiate emergency critical care assessment (Airway, Breathing, Circulation).",
        "2. Alert the attending ICU specialist and Medical Emergency Team (MET) / Code Blue team.",
        "3. Verify patent airway and deliver high-flow supplemental oxygen as clinically indicated.\n"
    ]

    if v:
        lines.append(f"**Latest Stored Telemetry for {p['name']} ({p['patient_code']}):**")
        lines.append(f"• SpO2: {_fmt_val(v.get('spo2'))}% | RR: {_fmt_val(v.get('respiratory_rate'))}/min | HR: {_fmt_val(v.get('heart_rate'))} bpm")
        dia_str = f"/{_fmt_val(v.get('blood_pressure_dia'))}" if v.get('blood_pressure_dia') is not None else ""
        lines.append(f"• Blood Pressure: {_fmt_val(v.get('blood_pressure_sys'))}{dia_str} mmHg | Consciousness: {v.get('consciousness', 'Alert')}")
        lines.append(f"• Current EWS Score: {e.get('score', 0)} ({e.get('risk_level', 'CRITICAL')} Risk)")

    lines.append("\n*Do not delay bedside intervention for software queries.*")
    return "\n".join(lines)


def reason_general_medical_query(query, context):
    """
    Provides general clinical medical concept explanation and immediately correlates with this patient's stored data.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    q_lower = query.lower()

    if 'spo2' in q_lower or 'oxygen' in q_lower:
        concept = (
            "**General Clinical Concept:**\n"
            "Oxygen saturation (SpO2) measures the percentage of hemoglobin binding sites occupied by oxygen. "
            "In adults, normal SpO2 is typically ≥95% on room air. Values below 92% indicate significant hypoxemia "
            "requiring oxygen supplementation and investigation of underlying pulmonary or cardiac etiologies."
        )
        patient_note = ""
        if v and v.get('spo2') is not None:
            patient_note = (
                f"\n\n**Patient-Specific Data for {p['name']}:**\n"
                f"The latest recorded SpO2 is **{_fmt_val(v.get('spo2'))}%** (recorded at {v.get('recorded_at')}). "
                f"Respiratory rate is recorded at {_fmt_val(v.get('respiratory_rate'))}/min."
            )
        return f"{concept}{patient_note}"

    if 'respiratory rate' in q_lower or 'rr' in q_lower:
        concept = (
            "**General Clinical Concept:**\n"
            "Normal adult resting respiratory rate is 12 to 20 breaths per minute. Tachypnea (>20/min) is often "
            "one of the earliest and most sensitive physiological indicators of metabolic acidosis, hypoxia, sepsis, "
            "or respiratory distress."
        )
        patient_note = ""
        if v and v.get('respiratory_rate') is not None:
            patient_note = (
                f"\n\n**Patient-Specific Data for {p['name']}:**\n"
                f"The latest recorded Respiratory Rate is **{_fmt_val(v.get('respiratory_rate'))}/min** (recorded at {v.get('recorded_at')})."
            )
        return f"{concept}{patient_note}"

    if 'tachycardia' in q_lower or 'bradycardia' in q_lower or 'heart rate' in q_lower or 'pulse' in q_lower:
        concept = (
            "**General Clinical Concept:**\n"
            "Tachycardia (resting Heart Rate >100 bpm) and Bradycardia (<50-60 bpm) indicate alterations in cardiac pacing. "
            "In ICU patients, tachycardia commonly reflects compensatory responses to hypovolemia, pain, fever, sepsis, or cardiac arrhythmias, "
            "while bradycardia may indicate conduction blocks, vagal stimulation, or medication effects."
        )
        patient_note = ""
        if v and v.get('heart_rate') is not None:
            patient_note = (
                f"\n\n**Patient-Specific Data for {p['name']}:**\n"
                f"The latest recorded Heart Rate is **{_fmt_val(v.get('heart_rate'))} bpm** (recorded at {v.get('recorded_at', 'recent')})."
            )
        return f"{concept}{patient_note}"

    if 'blood pressure' in q_lower or 'hypertension' in q_lower or 'hypotension' in q_lower or 'bp' in q_lower:
        concept = (
            "**General Clinical Concept:**\n"
            "Blood pressure reflects systemic vascular resistance and cardiac output. Systolic BP <90 mmHg (hypotension) "
            "may compromise vital organ perfusion and requires urgent evaluation for shock, while severe hypertension increases myocardial and cerebrovascular workload."
        )
        patient_note = ""
        if v and v.get('blood_pressure_sys') is not None:
            dia_str = f"/{_fmt_val(v.get('blood_pressure_dia'))}" if v.get('blood_pressure_dia') is not None else ""
            patient_note = (
                f"\n\n**Patient-Specific Data for {p['name']}:**\n"
                f"The latest recorded Blood Pressure is **{_fmt_val(v.get('blood_pressure_sys'))}{dia_str} mmHg** (recorded at {v.get('recorded_at', 'recent')})."
            )
        return f"{concept}{patient_note}"

    if 'ews' in q_lower or 'early warning' in q_lower:
        concept = (
            "**General Clinical Concept:**\n"
            "The Early Warning Score (EWS) is a standardized physiological scoring tool that evaluates Heart Rate, "
            "Systolic Blood Pressure, Respiratory Rate, SpO2, Body Temperature, and Level of Consciousness to "
            "quantify clinical risk and detect early signs of physiological decompensation."
        )
        patient_note = (
            f"\n\n**Patient-Specific Data for {p['name']}:**\n"
            f"Current EWS is **{context.get('ews', {}).get('score', 0)}** ({context.get('ews', {}).get('risk_level', 'LOW')} Risk)."
        )
        return f"{concept}{patient_note}"

    return (
        f"**Clinical Concept:** Telemetry parameters must be interpreted collectively in the context of the "
        f"patient's baseline history. For patient **{p['name']}**, current EWS is {context.get('ews', {}).get('score', 0)} ({context.get('ews', {}).get('risk_level', 'LOW')} Risk)."
    )


# =============================================================================
# 7. CLINICAL RESPONSE FORMATTERS (STANDARD & STRUCTURED)
# =============================================================================

def format_structured_patient_summary(context):
    """
    Generate the complete, structured patient summary according to the 6-part clinical standard.
    ONLY invoked when explicitly requested (PATIENT_SUMMARY).
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    csi = context.get('composite_stability_index', {})
    r = context.get('recommendation')
    trends = context.get('trends', {})

    p_name = p['name']
    p_code = p['patient_code']
    p_age = p['age']
    p_gender = p['gender']
    p_ward = p['ward_type']
    p_bed = p.get('bed_number') or "Not assigned"
    p_adm = p.get('admission_date') or "Recorded in database"
    p_diag = p.get('diagnosis') or "No documented diagnosis is available in the Jeevan Setu records."

    sec1 = (
        f"----------------------------------------\n"
        f"PATIENT SUMMARY\n"
        f"----------------------------------------\n"
        f"Name: {p_name}\n"
        f"Patient ID: {p_code}\n"
        f"Age / Gender: {p_age} yrs / {p_gender}\n"
        f"Current Unit: {p_ward} (Bed: {p_bed})\n"
        f"Admission: {p_adm}\n"
        f"Documented Diagnosis / Condition: {p_diag}\n"
        f"Current Status: {p['status'].capitalize()}"
    )

    if v:
        bp_str = f"{_fmt_val(v.get('blood_pressure_sys'))}/{_fmt_val(v.get('blood_pressure_dia'))} mmHg" if v.get('blood_pressure_sys') is not None else "Not recorded"
        sec2 = (
            f"----------------------------------------\n"
            f"CURRENT VITALS\n"
            f"----------------------------------------\n"
            f"Heart Rate: {_fmt_val(v.get('heart_rate'))} bpm\n"
            f"Systolic Blood Pressure: {_fmt_val(v.get('blood_pressure_sys'))} mmHg\n"
            f"Blood Pressure: {bp_str}\n"
            f"SpO2: {_fmt_val(v.get('spo2'))}%\n"
            f"Respiratory Rate: {_fmt_val(v.get('respiratory_rate'))} /min\n"
            f"Temperature: {_fmt_val(v.get('temperature'))} °C\n"
            f"Level of Consciousness: {v.get('consciousness', 'Alert')}\n"
            f"Timestamp: {v.get('recorded_at', 'Latest')}"
        )
    else:
        sec2 = (
            f"----------------------------------------\n"
            f"CURRENT VITALS\n"
            f"----------------------------------------\n"
            f"No vital sign measurements are currently recorded for this patient."
        )

    csi_str = f"{csi.get('index')}%" if csi.get('index') is not None else "No recorded value is available"
    csi_class = csi.get('classification', e.get('risk_level', 'Stable'))
    sec3 = (
        f"----------------------------------------\n"
        f"CURRENT EWS / SCORE\n"
        f"----------------------------------------\n"
        f"EWS: {e.get('score', 0)}\n"
        f"Composite Stability Index: {csi_str}\n"
        f"Overall Classification: {csi_class}"
    )

    if r and r.get('status') != 'none':
        rec_text = r.get('recommendation_text', 'No active recommendation')
        rec_reason = r.get('reason') or "Generated from EWS criteria and unit capacity rules."
        sec4 = (
            f"----------------------------------------\n"
            f"CURRENT TRANSFER RECOMMENDATION\n"
            f"----------------------------------------\n"
            f"Recommendation: {rec_text}\n"
            f"Reason: {rec_reason}"
        )
    else:
        sec4 = (
            f"----------------------------------------\n"
            f"CURRENT TRANSFER RECOMMENDATION\n"
            f"----------------------------------------\n"
            f"Recommendation: None\n"
            f"Reason: No active transfer recommendation is recorded in Jeevan Setu."
        )

    if trends.get('has_sufficient_data'):
        p_trends = trends.get('parameters', {})
        hr_t = p_trends.get('heart_rate', {}).get('direction', 'Stable') if p_trends.get('heart_rate') else "Stable"
        spo2_t = p_trends.get('spo2', {}).get('direction', 'Stable') if p_trends.get('spo2') else "Stable"
        rr_t = p_trends.get('respiratory_rate', {}).get('direction', 'Stable') if p_trends.get('respiratory_rate') else "Stable"

        sec5 = (
            f"----------------------------------------\n"
            f"RECENT TREND\n"
            f"----------------------------------------\n"
            f"Heart Rate: {hr_t}\n"
            f"SpO2: {spo2_t}\n"
            f"Respiratory Rate: {rr_t}\n"
            f"{trends.get('summary_text', '')}"
        )
    else:
        sec5 = (
            f"----------------------------------------\n"
            f"RECENT TREND\n"
            f"----------------------------------------\n"
            f"There is not enough historical data to determine a reliable trend."
        )

    sec6 = (
        f"----------------------------------------\n"
        f"CLINICAL NOTE\n"
        f"----------------------------------------\n"
        f"This summary is based on the information available in Jeevan Setu.\n"
        f"Final clinical assessment remains with the treating healthcare professional."
    )

    return f"{sec1}\n\n{sec2}\n\n{sec3}\n\n{sec4}\n\n{sec5}\n\n{sec6}"


def format_transfer_decision_explanation(context):
    """
    Explain why the current Jeevan Setu recommendation was generated using actual Decision Engine factors.
    """
    p = context['patient']
    r = context.get('recommendation')
    e = context.get('ews', {})
    v = context.get('latest_vitals')
    csi = context.get('composite_stability_index', {})

    if not r or r.get('status') == 'none':
        return f"There are currently no active transfer recommendations recorded for patient {p['name']} ({p['patient_code']})."

    rec_text = r.get('recommendation_text', 'No recommendation')
    reason = r.get('reason') or "Based on physiological EWS criteria"
    from_w = r.get('from_ward', p['ward_type'])
    to_w = r.get('to_ward', 'N/A')
    status = r.get('status', 'pending').upper()

    factors = []
    if v:
        if v.get('spo2') is not None:
            factors.append(f"SpO2 = {_fmt_val(v.get('spo2'))}%")
        if v.get('respiratory_rate') is not None:
            factors.append(f"Respiratory Rate = {_fmt_val(v.get('respiratory_rate'))}/min")
        if v.get('heart_rate') is not None:
            factors.append(f"Heart Rate = {_fmt_val(v.get('heart_rate'))} bpm")
        if v.get('blood_pressure_sys') is not None:
            factors.append(f"Systolic BP = {_fmt_val(v.get('blood_pressure_sys'))} mmHg")

    contrib_str = "\n• ".join(factors) if factors else "Telemetry data recorded in database."

    return (
        f"**Jeevan Setu Transfer Recommendation for {p['name']} ({p['patient_code']}):**\n\n"
        f"Jeevan Setu currently recommends keeping the patient in **{to_w if to_w != 'N/A' else from_w}** (Recommendation: **{rec_text}**).\n\n"
        f"**Primary Decision Engine Factors:**\n"
        f"• Current Unit: {from_w} (Bed {p.get('bed_number', 'N/A')})\n"
        f"• Early Warning Score (EWS): **{e.get('score', 0)}** ({e.get('risk_level', 'LOW')} Risk)\n"
        f"• Composite Stability Index: **{csi.get('index', 'N/A')}%** ({csi.get('classification', 'Stable')})\n"
        f"• Clinical Reason: {reason}\n\n"
        f"**Contributing Physiological Parameters:**\n"
        f"• {contrib_str}\n\n"
        f"*Note: This recommendation was generated by the Jeevan Setu Decision Engine. The final clinical transfer decision remains with the authorized clinician.*"
    )


def format_decision_history_and_overrides(context):
    """
    Show previous transfer decisions, clinician reviews, and distinguish system recommendations from clinician overrides.
    """
    p = context['patient']
    recs = context.get('recommendations_history', [])
    decs = context.get('decisions_history', [])
    trans = context.get('transfers_history', [])

    if not recs and not decs and not trans:
        return f"No previous transfer decisions or reviews are recorded in the database for patient {p['name']} ({p['patient_code']})."

    output_lines = [f"**Transfer Decision History for {p['name']} ({p['patient_code']}):**\n"]

    for idx, r in enumerate(recs, 1):
        r_text = r.get('recommendation_text', 'N/A')
        r_status = (r.get('status') or 'pending').capitalize()
        r_reviewer = r.get('decided_by_name') or "Pending Clinician Review"
        r_time = r.get('decided_at') or r.get('created_at', 'N/A')
        r_reason = r.get('reason') or "Physiological criteria"

        override_note = ""
        if r_status == "Rejected":
            override_note = f"\n   ⚠️ **Clinician Override:** System recommended '{r_text}' but was overridden by {r_reviewer}."
        elif r_status == "Approved":
            override_note = f"\n   ✅ **Clinician Approval:** Accepted by {r_reviewer}."

        output_lines.append(
            f"**{idx}. Date/Time:** {r_time}\n"
            f"   • System Recommendation: **{r_text}** ({r.get('from_ward')} → {r.get('to_ward')})\n"
            f"   • Reason: {r_reason}\n"
            f"   • Clinician Decision / Status: **{r_status}** ({r_reviewer}){override_note}\n"
        )

    return "\n".join(output_lines)


def format_documented_diagnosis(context):
    """
    Return strictly documented diagnosis or declare absence without inferring.
    """
    p = context['patient']
    diag = p.get('diagnosis')
    if diag and diag.strip():
        return f"According to the patient's records in Jeevan Setu, the documented condition is: **{diag.strip()}**."
    else:
        return "The Jeevan Setu database does not contain a documented diagnosis for this patient."


def format_abnormal_parameters(context):
    """
    Summarize all currently abnormal parameters and latest critical alerts.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    if not v:
        return f"No vital sign records are currently available for patient {p['name']}."

    abnormalities = []
    hr = v.get('heart_rate')
    if hr is not None and (hr < 50 or hr > 100):
        abnormalities.append(f"Heart Rate = {_fmt_val(hr)} bpm (Abnormal: normal range 60-100 bpm)")

    spo2 = v.get('spo2')
    if spo2 is not None and spo2 < 95:
        abnormalities.append(f"SpO2 = {_fmt_val(spo2)}% (Abnormal: normal range ≥ 95%)")

    rr = v.get('respiratory_rate')
    if rr is not None and (rr < 12 or rr > 20):
        abnormalities.append(f"Respiratory Rate = {_fmt_val(rr)}/min (Abnormal: normal range 12-20/min)")

    sys_bp = v.get('blood_pressure_sys')
    if sys_bp is not None and (sys_bp < 90 or sys_bp > 140):
        abnormalities.append(f"Systolic Blood Pressure = {_fmt_val(sys_bp)} mmHg (Abnormal: normal range 90-140 mmHg)")

    temp = v.get('temperature')
    if temp is not None and (temp < 36.0 or temp > 38.0):
        abnormalities.append(f"Temperature = {_fmt_val(temp)} °C (Abnormal: normal range 36.0-38.0 °C)")

    cons = v.get('consciousness')
    if cons and cons != "Alert":
        abnormalities.append(f"Level of Consciousness = {cons} (Abnormal)")

    if abnormalities:
        return (
            f"**Abnormal Findings for {p['name']} ({p['patient_code']}):**\n"
            + "\n".join(f"• {a}" for a in abnormalities)
            + "\n\n*These parameters should be reviewed immediately by the treating clinical team.*"
        )
    else:
        return f"All latest recorded vital parameters for patient {p['name']} ({p['patient_code']}) are within standard physiological ranges."


# =============================================================================
# 8. MAIN CLINICAL REASONING ORCHESTRATOR
# =============================================================================

# =============================================================================
# 8. MAIN CLINICAL REASONING ORCHESTRATOR
# =============================================================================

def _generate_factual_response(intent, message_lower, context, session_state=None):
    """
    Generate question-specific clinical response from retrieved context.
    Strictly answers the user's specific inquiry without dumping irrelevant patient summaries.
    """
    p = context['patient']
    v = context.get('latest_vitals')
    e = context.get('ews', {})
    r = context.get('recommendation')
    p_name = p['name']
    p_code = p['patient_code']

    # 1. Greeting / Pleasantries -> Clean conversational response
    if intent == 'greeting':
        return format_conversational_greeting(p_name, p_code)

    # 2. Conversational Acknowledgment ('Thanks', 'Okay', 'Got it')
    if intent == 'acknowledgment':
        return format_conversational_acknowledgment(p_name)

    # 3. Current Clinical Status Overview ('How is he doing?', 'How is Sahil?')
    if intent == 'current_status_overview':
        return reason_current_status_overview(context)

    # 4. Help
    if intent == 'help':
        return format_conversational_help(p_name, p_code)

    # 5. Emergency Critical
    if intent == 'emergency_critical':
        return reason_emergency_critical(context, message_lower)

    # 6. Prognosis / Mortality / 'Is it serious?'
    if intent == 'prognosis_mortality':
        return reason_prognosis_and_mortality(context)

    # 7. Historical Comparison ('Compare today with yesterday')
    if intent == 'historical_comparison':
        return reason_historical_comparison(context, message_lower)

    # 8. Key Concerns Summary ('Summarize the important things')
    if intent == 'key_concerns_summary':
        return reason_key_concerns_summary(context, message_lower)

    # 9. Clinical Decision Support Synthesis ('What do you think is going on?')
    if intent == 'clinical_synthesis':
        return reason_clinical_synthesis(context, message_lower)

    # 10. Cause / Reason Analysis ('Why?', 'What could be causing it?')
    if intent == 'cause_reason':
        return reason_cause_and_multi_parameter(context, message_lower)

    # 11. Historical Data / Previous Vitals & EWS
    if intent == 'historical_data':
        return reason_historical_data(context, message_lower)

    # 12. Deterioration / Trajectory / Improvement (Answer-First)
    if intent == 'deterioration_improvement':
        return reason_deterioration_or_improvement(context, message_lower)

    # 13. General Medical Query
    if intent == 'general_medical':
        return reason_general_medical_query(message_lower, context)

    # 14. Documented Diagnosis Query
    if intent == 'diagnosis_query':
        return format_documented_diagnosis(context)

    # 15. Abnormal Vitals
    if intent == 'abnormal_vitals':
        return format_abnormal_parameters(context)

    # 16. Explicit Patient Summary Request ONLY
    if intent == 'patient_summary':
        return format_structured_patient_summary(context)

    # 17. Trends Query
    if intent == 'trends_query':
        trends = context.get('trends', {})
        if not trends.get('has_sufficient_data'):
            return "There is not enough historical data to determine a reliable trend."
        return f"**Vital Parameter Trends for {p_name} ({p_code}):**\n\n{trends.get('summary_text')}"

    # 18. Decision History & Overrides
    if intent == 'decision_history':
        return format_decision_history_and_overrides(context)

    # 19. Transfer Recommendation Query
    if intent == 'recommendation_query':
        return format_transfer_decision_explanation(context)

    # 20. EWS Score Query
    if intent == 'ews_query':
        if not v and e.get('score', 0) == 0:
            return f"No EWS evaluation records exist for patient {p_name} ({p_code})."
        csi = context.get('composite_stability_index', {})
        score = e.get('score', 0)
        risk = e.get('risk_level', get_risk_level(score).upper())
        rec_time = v.get('recorded_at', 'Recent') if v else 'Recent'

        if 'why' in message_lower or 'high' in message_lower or 'increase' in message_lower:
            factors = []
            if v:
                if v.get('spo2') is not None and v.get('spo2') < 95:
                    factors.append(f"SpO2 is low at {_fmt_val(v.get('spo2'))}% (+2 points)")
                if v.get('respiratory_rate') is not None and (v.get('respiratory_rate') > 20 or v.get('respiratory_rate') < 12):
                    factors.append(f"Respiratory Rate is elevated at {_fmt_val(v.get('respiratory_rate'))}/min (+2 points)")
                if v.get('heart_rate') is not None and (v.get('heart_rate') > 100 or v.get('heart_rate') < 50):
                    factors.append(f"Heart Rate is abnormal at {_fmt_val(v.get('heart_rate'))} bpm (+1 point)")
                if v.get('temperature') is not None and (v.get('temperature') > 38.0 or v.get('temperature') < 36.0):
                    factors.append(f"Temperature is elevated at {_fmt_val(v.get('temperature'))} °C (+1 point)")

            factor_str = "\n• ".join(factors) if factors else "Multiple physiological parameter deviations recorded in telemetry."
            return (
                f"**Early Warning Score (EWS)** for {p_name} ({p_code}):\n"
                f"• EWS Score: **{score}**\n"
                f"• Risk Stratification: **{risk}**\n\n"
                f"**Main Contributing Factors:**\n"
                f"• {factor_str}\n\n"
                f"Composite Stability Index: **{csi.get('index', 'N/A')}%** ({csi.get('classification', 'Stable')})."
            )

        return (
            f"**Early Warning Score (EWS)** for {p_name} ({p_code}):\n"
            f"• EWS Score: **{score}**\n"
            f"• Risk Stratification: **{risk}**\n"
            f"• Composite Stability Index: **{csi.get('index', 'N/A')}%** ({csi.get('classification', 'Stable')})\n"
            f"• Telemetry Timestamp: {rec_time}"
        )

    # 21. Single Vital Query
    if intent == 'vitals_query':
        return reason_single_parameter(context, message_lower)

    # 22. Report Generation
    if intent == 'report_generation':
        return (
            f"You can export the official clinical report for patient **{p_name}** ({p_code}):\n"
            f"• [Download Clinical PDF Report](/reports/patients/pdf?patient_id={p['patient_id']})\n"
            f"• [View EWS Trend Report](/reports/ews/{p['patient_id']})"
        )

    # Fallback: Natural conversational clinical response synthesized from active context
    if context and context.get('patient'):
        if any(w in message_lower for w in ['short answer', 'brief', 'quick', 'numbers only']):
            unit = p.get('ward_type', 'ICU')
            score = e.get('score', 0)
            rec_text = r.get('recommendation_text', 'Keep in ICU') if r else 'Under Evaluation'
            v_brief = []
            if v:
                if v.get('spo2') is not None:
                    v_brief.append(f"SpO₂ {_fmt_val(v.get('spo2'))}%")
                if v.get('respiratory_rate') is not None:
                    v_brief.append(f"RR {_fmt_val(v.get('respiratory_rate'))}/min")
                if v.get('heart_rate') is not None:
                    v_brief.append(f"HR {_fmt_val(v.get('heart_rate'))} bpm")
                if v.get('blood_pressure_sys') is not None:
                    v_brief.append(f"BP {_fmt_val(v.get('blood_pressure_sys'))} mmHg")
            v_str = ", ".join(v_brief) if v_brief else "No vitals recorded"
            return (
                f"**{p_name}** is currently in **{unit}**. Current readings: {v_str}. "
                f"EWS score is **{score}**, and Jeevan Setu recommends **{rec_text}**."
            )
        return reason_current_status_overview(context)

    return (
        "Hello, Doctor. I am Dr. Setu, your clinical decision-support assistant. "
        "Please select or search for a patient to begin clinical rounds."
    )


# =============================================================================
# 9. CONVERSATIONAL PIPELINE WITH STRICT RBAC & MEMORY
# =============================================================================

def process_message(user_id, message, patient_id=None):
    """
    Main chatbot request processor with strict patient-specific context enforcement.
    """
    if not patient_id:
        return {
            'success': False,
            'error': 'Patient ID context is required. Please select a patient first.',
            'text': 'Please select a specific patient to start an authorized clinical inquiry.',
            'intent': 'missing_patient_id',
            'confidence': 1.0
        }

    context = get_patient_clinical_context(patient_id)
    if not context:
        return {
            'success': False,
            'error': f'Patient #{patient_id} not found in the database.',
            'text': f'Patient #{patient_id} was not found in the hospital records.',
            'intent': 'patient_not_found',
            'confidence': 1.0
        }

    state = ConversationMemory.get_state(user_id)
    intent, confidence = detect_contextual_intent(message, session_state=state)
    response_text = _generate_factual_response(intent, message.lower(), context, session_state=state)

    # Update state memory
    ConversationMemory.update_state(
        user_id=user_id,
        active_patient_id=patient_id,
        active_patient_name=context['patient']['name'],
        intent=intent,
        user_query=message,
        bot_response=response_text
    )

    try:
        ChatbotConversation.save(
            user_id=user_id,
            user_message=message,
            bot_response=response_text,
            patient_id=patient_id,
            intent=intent,
            confidence=confidence
        )
    except Exception as e:
        print(f"[CHATBOT] Note: Could not save conversation history: {e}")

    return {
        'success': True,
        'patient_id': patient_id,
        'intent': intent,
        'confidence': confidence,
        'text': response_text,
        'context': context
    }


PATIENT_ENTITY_STOPWORDS = {
    'he', 'she', 'it', 'his', 'her', 'him', 'the', 'a', 'an', 'this', 'that',
    'these', 'those', 'patient', 'patients', 'they', 'them', 'my', 'your', 'our', 'their',
    'dr', 'doctor', 'nurse', 'icu', 'hdu', 'ward', 'bed', 'spo2', 'bp', 'hr',
    'pulse', 'temp', 'temperature', 'vitals', 'vital', 'summary', 'status',
    'data', 'chart', 'notes', 'u', 'you', 'me', 'i', 'we', 'today', 'now', 'here', 'condition',
    'is', 'are', 'was', 'were', 'what', 'why', 'how', 'who', 'tell', 'show', 'give', 'get', 'please',
    'hi', 'hello', 'hey', 'good', 'morning', 'afternoon', 'evening', 'night', 'thanks', 'thank',
    'update', 'overview', 'serious', 'stable', 'better', 'worse', 'improving', 'deteriorating',
    'oxygen', 'breathing', 'tachycardia', 'bradycardia', 'hypertension', 'hypotension',
    'changed', 'overnight', 'yesterday', 'concerns', 'problems', 'findings', 'points', 'latest'
}


def clean_extracted_patient_name(name):
    """Clean leading/trailing auxiliary words, pronouns, and excess whitespace from extracted patient name candidate."""
    if not name:
        return ""
    cleaned = name.strip()
    prev = ""
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(r'^(?:the|patient|a|an|is|are|was|were|what|why|how|who|of|for|about|tell|show|give|check|find|search|his|her|their|my|your|now|switch|to|open|look|at|lets|let\'s|on|me)\s+', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[\?\.\!\:\;]+$', '', cleaned.strip())
    if cleaned.lower() in PATIENT_ENTITY_STOPWORDS:
        return ""
    if any(w in cleaned.lower().split() for w in ['oxygen', 'spo2', 'bp', 'hr', 'pulse', 'temp', 'temperature', 'breathing', 'respiratory', 'vitals', 'vital', 'condition', 'status', 'update', 'ews', 'icu', 'hdu', 'tachycardia', 'hypertension', 'hypotension']):
        return ""
    return cleaned.strip()


def extract_patient_entity(msg):
    """
    Extracts potential patient identifier/name and the remaining clinical question.
    Returns:
        tuple (candidate_name_or_id, cleaned_clinical_query, is_explicit_mention)
    """
    text = (msg or "").strip()
    if not text:
        return None, text, False

    # 0. Direct match check on the entire message
    mtype, pats = search_patients_for_chat(text)
    if mtype in ('single', 'multiple'):
        return text, '', True

    # 1. Explicit UHID / Patient Code pattern (e.g. UHID-2026-00011, JS-0066)
    m_code = re.search(r'\b(UHID-\d{4}-\d{5}|JS-\d{2,5})\b', text, re.IGNORECASE)
    if m_code:
        code = m_code.group(1).upper()
        cleaned = text.replace(m_code.group(1), '').strip()
        return code, cleaned, True

    # 2. Patient ID / Number pattern: e.g. 'patient 66', 'patient #66', '#66'
    m_pnum = re.search(r'\b(?:patient\s+|patient\s*#|#)(?P<id>\d+)\b', text, re.IGNORECASE)
    if m_pnum:
        pid = m_pnum.group('id')
        cleaned = text[:m_pnum.start()] + text[m_pnum.end():]
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return pid, cleaned, True

    # 3. Possessive pattern: <name>'s
    m_poss = re.search(r'\b([A-Za-z0-9_\-]+(?:\s+[A-Za-z0-9_\-]+)?)[\'’]s\b', text, re.IGNORECASE)
    if m_poss:
        raw_cand = m_poss.group(1).strip()
        cand = clean_extracted_patient_name(raw_cand)
        if cand and len(cand) > 1 and cand.lower() not in PATIENT_ENTITY_STOPWORDS:
            cleaned = text[:m_poss.start()] + text[m_poss.end():]
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cand, cleaned, True

    # 4. Explicit introductory phrases (tell me about, who is, search, find, switch to, status of, now check...)
    intro_pattern = r'^\s*(?:tell\s+me\s+about|information\s+(?:on|about)|info\s+(?:on|about)|details\s+(?:of|for|on)|status\s+(?:of|for)|summary\s+(?:of|for)|check\s+on|check|now\s+check|now\s+look\s+at|look\s+up|look\s+at|open|search\s+for|search|find|select|switch\s+to|change\s+to|who\s+is|show\s+me|how\s+about|what\s+about)\s+(?:the\s+)?(?:patient\s+)?(?P<name>[a-zA-Z0-9_\-\s]+?)(?:\s+summary|\s+status|\s+report|\s+overview|\s+profile|\?|\.|\!|$)'
    m_intro = re.search(intro_pattern, text, re.IGNORECASE)
    if m_intro:
        raw_cand = m_intro.group('name').strip()
        cand = clean_extracted_patient_name(raw_cand)
        if cand and len(cand) > 1 and cand.lower() not in PATIENT_ENTITY_STOPWORDS:
            return cand, 'tell me about', True

    # 5. 'why is / how is / is <name> <clinical verb/condition>'
    m_quest = re.search(r'^\s*(?:how\s+is|why\s+is|is|what\s+is)\s+(?:the\s+)?(?:patient\s+)?(?P<name>[A-Za-z0-9_\-]+(?:\s+[A-Za-z0-9_\-]+)?)\s+(?P<rest>(?:getting\s+worse|deteriorating|improving|stable|unstable|critical|doing|having|suffering|admitted).*?)\s*$', text, re.IGNORECASE)
    if m_quest:
        raw_cand = m_quest.group('name').strip()
        cand = clean_extracted_patient_name(raw_cand)
        if cand and len(cand) > 1 and cand.lower() not in PATIENT_ENTITY_STOPWORDS:
            cleaned = text[:m_quest.start('name')] + m_quest.group('rest')
            return cand, cleaned, True

    # 6. Prepositional: 'what is the spo2 for/of <name>'
    m_prep = re.search(r'(?P<query>.*?)\b(?:for|of|regarding|about)\s+(?:the\s+)?(?:patient\s+)?(?P<name>[A-Za-z0-9_\-]+(?:\s+[A-Za-z0-9_\-]+)?)\s*[\?\.\!]*$', text, re.IGNORECASE)
    if m_prep:
        raw_cand = m_prep.group('name').strip()
        cand = clean_extracted_patient_name(raw_cand)
        if cand and len(cand) > 1 and cand.lower() not in PATIENT_ENTITY_STOPWORDS:
            cleaned = m_prep.group('query').strip()
            return cand, cleaned, True

    # 7. Fallback: Check if user entered just a 1 to 4 word name/identifier or lookup
    words = [w for w in re.split(r'[^a-zA-Z0-9_\-]+', text) if w]
    if 1 <= len(words) <= 4:
        cand = clean_extracted_patient_name(' '.join(words))
        if cand and len(cand) > 1 and cand.lower() not in PATIENT_ENTITY_STOPWORDS:
            mtype, pats = search_patients_for_chat(cand)
            if mtype in ('single', 'multiple'):
                return cand, '', True
            base_intent, _ = detect_intent(text)
            if base_intent in ('general_query', 'greeting') and not re.search(r'\b(why|how|what|is|are|was|were|can|should|spo2|bp|hr|temp|vitals|help|hi|hello|hey)\b', text.lower()):
                return cand, '', True

    return None, text, False


def process_conversational_message(user_id, message, active_patient_id=None):
    """
    High-level conversational orchestrator that handles:
    1. Greeting / Acknowledgment / Help (Never dumps patient profile)
    2. Dynamic Patient Entity Extraction & Context Switching
    3. Multi-turn pronoun & elliptical follow-up resolution with ConversationMemory
    4. Patient Disambiguation
    5. Scaled clinical reasoning grounded in live verified telemetry
    6. Audit Logging
    """
    msg = (message or "").strip()
    if not msg:
        return {
            'success': False,
            'error': 'Empty message.',
            'text': 'Please enter a question, patient name, or Patient ID.',
            'intent': 'empty_query'
        }

    msg_lower = msg.lower()
    state = ConversationMemory.get_state(user_id)

    # Synchronize active patient ID with state
    if active_patient_id:
        state['active_patient_id'] = active_patient_id

    effective_patient_id = active_patient_id or state.get('active_patient_id')

    # Step 1: Extract explicit patient entity mention from message first
    cand_name, cleaned_query, is_explicit_mention = extract_patient_entity(msg)

    # Step 2: Handle explicit patient mention
    if is_explicit_mention and cand_name:
        match_type, patients = search_patients_for_chat(cand_name)

        if match_type == "none":
            return {
                'success': True,
                'text': f"I could not find any patient matching '{cand_name}' in the database.\n\nPlease check the spelling or enter a valid Patient ID (e.g. JS-1024 or UHID-2026-00001).",
                'intent': "patient_not_found",
                'requires_patient_selection': True
            }
        elif match_type == "multiple":
            patient_list_text = "\n".join(
                f"• **{p['name']}** — ID: `{p['patient_code']}` (Age: {p['age']}, Unit: {p['ward_type']}, Bed: {p['bed_number']})"
                for p in patients
            )
            return {
                'success': True,
                'text': f"I found multiple patients matching '{cand_name}'. Please select the patient using the Patient ID or another identifier:\n\n{patient_list_text}",
                'intent': "patient_disambiguation",
                'candidates': patients,
                'requires_patient_selection': True
            }
        elif match_type == "single":
            p = patients[0]
            found_id = p['patient_id']
            try:
                AuditLog.log(
                    user_id=user_id,
                    action="CHATBOT_PATIENT_SEARCH",
                    entity_type="patient",
                    entity_id=found_id,
                    description=f"Searched patient {p['name']} ({p['patient_code']})"
                )
            except Exception:
                pass

            context = get_patient_clinical_context(found_id)
            query_to_eval = cleaned_query if cleaned_query else 'show patient summary'
            intent, _ = detect_contextual_intent(query_to_eval, session_state=state)

            # Update session memory to switch active patient
            ConversationMemory.update_state(
                user_id=user_id,
                active_patient_id=found_id,
                active_patient_name=p['name'],
                intent=intent
            )

            # If user just inquired about the patient (e.g. 'Tell me about Sahil', 'Who is Sahil', 'Sahil Sharma')
            if intent in ['current_status_overview', 'patient_summary', 'help', 'greeting', 'prompt_patient_id', 'general_query'] or query_to_eval in ['show patient summary', 'the patient', '']:
                if any(k in msg_lower for k in ['how is', 'how\'s', 'tell me about', 'status of', 'condition of', 'how about', 'what about', 'how does', 'what is happening']):
                    status_text = reason_current_status_overview(context)
                    ConversationMemory.update_state(user_id=user_id, bot_response=status_text)
                    return {
                        'success': True,
                        'text': status_text,
                        'intent': "current_status_overview",
                        'patient_id': found_id,
                        'patient': p,
                        'context': context
                    }
                elif not cleaned_query or any(k in msg_lower for k in ['search', 'find', 'select', 'switch to', 'lookup']):
                    return {
                        'success': True,
                        'text': (
                            f"I found 1 patient matching **{p['name']}**.\n\n"
                            f"**Patient:** {p['name']}\n"
                            f"**Patient ID:** {p['patient_code']}\n"
                            f"**Current Unit:** {p['ward_type']} (Bed {p['bed_number']})\n\n"
                            f"Would you like me to show the complete patient summary?"
                        ),
                        'intent': "patient_found",
                        'patient_id': found_id,
                        'patient': p,
                        'context': context
                    }
                else:
                    status_text = reason_current_status_overview(context)
                    ConversationMemory.update_state(user_id=user_id, bot_response=status_text)
                    return {
                        'success': True,
                        'text': status_text,
                        'intent': "current_status_overview",
                        'patient_id': found_id,
                        'patient': p,
                        'context': context
                    }
            else:
                # Specific clinical question for this resolved patient
                resp = process_message(user_id=user_id, message=query_to_eval, patient_id=found_id)
                resp['patient_id'] = found_id
                return resp

    # Step 3: Check for Pure Acknowledgment / Greetings & Help when no explicit patient entity was extracted
    if _is_pure_acknowledgment(msg):
        p_name = state.get('active_patient_name')
        return {
            'success': True,
            'text': format_conversational_acknowledgment(p_name),
            'intent': "acknowledgment",
            'patient_id': effective_patient_id
        }

    is_greeting = _matches_pattern(INTENT_PATTERNS['greeting'], msg)
    is_help = _matches_pattern(INTENT_PATTERNS['help'], msg)
    if is_greeting:
        p_name = state.get('active_patient_name')
        p_code = None
        if effective_patient_id:
            c = get_patient_clinical_context(effective_patient_id)
            if c:
                p_name = c['patient']['name']
                p_code = c['patient']['patient_code']
        return {
            'success': True,
            'text': format_conversational_greeting(p_name, p_code),
            'intent': "greeting",
            'patient_id': effective_patient_id,
            'requires_patient_selection': (effective_patient_id is None)
        }
    if is_help:
        p_name = state.get('active_patient_name')
        p_code = None
        if effective_patient_id:
            c = get_patient_clinical_context(effective_patient_id)
            if c:
                p_name = c['patient']['name']
                p_code = c['patient']['patient_code']
        return {
            'success': True,
            'text': format_conversational_help(p_name, p_code),
            'intent': "help",
            'patient_id': effective_patient_id,
            'requires_patient_selection': (effective_patient_id is None)
        }

    # Step 4: User confirmed "Yes" / "Show summary" on active patient
    if effective_patient_id and msg_lower in ["yes", "y", "show summary", "view summary", "view patient summary", "yes please", "sure", "show complete summary", "show patient summary"]:
        context = get_patient_clinical_context(effective_patient_id)
        if not context:
            return {
                'success': False,
                'text': "Patient record could not be loaded.",
                'intent': "patient_not_found"
            }
        summary_text = format_structured_patient_summary(context)
        ConversationMemory.update_state(user_id=user_id, intent='patient_summary', bot_response=summary_text)
        return {
            'success': True,
            'text': summary_text,
            'intent': "patient_summary",
            'patient_id': effective_patient_id,
            'context': context
        }

    # Step 5: Active Patient Inquiries (when patient is active in session)
    if effective_patient_id:
        return process_message(user_id=user_id, message=msg, patient_id=effective_patient_id)

    # Step 6: No active patient and no explicit entity pattern matched — perform fallback search
    match_type, patients = search_patients_for_chat(msg)
    if match_type == "single":
        p = patients[0]
        found_id = p['patient_id']
        context = get_patient_clinical_context(found_id)
        ConversationMemory.update_state(
            user_id=user_id,
            active_patient_id=found_id,
            active_patient_name=p['name'],
            intent='patient_found'
        )
        return {
            'success': True,
            'text': (
                f"I found 1 patient matching **{p['name']}**.\n\n"
                f"**Patient:** {p['name']}\n"
                f"**Patient ID:** {p['patient_code']}\n"
                f"**Current Unit:** {p['ward_type']} (Bed {p['bed_number']})\n\n"
                f"Would you like me to show the complete patient summary?"
            ),
            'intent': "patient_found",
            'patient_id': found_id,
            'patient': p,
            'context': context
        }
    elif match_type == "multiple":
        patient_list_text = "\n".join(
            f"• **{p['name']}** — ID: `{p['patient_code']}` (Age: {p['age']}, Unit: {p['ward_type']}, Bed: {p['bed_number']})"
            for p in patients
        )
        return {
            'success': True,
            'text': f"I found multiple patients matching '{msg}'. Please select the patient using the Patient ID or another identifier:\n\n{patient_list_text}",
            'intent': "patient_disambiguation",
            'candidates': patients,
            'requires_patient_selection': True
        }
    elif match_type == "none":
        return {
            'success': True,
            'text': f"I could not find any patient matching '{msg}'.\n\nPlease check the spelling or enter a valid Patient ID (e.g. JS-1024 or UHID-2026-00001).",
            'intent': "patient_not_found",
            'requires_patient_selection': True
        }

    return {
        'success': True,
        'text': "Doctor, please enter a patient's name, UHID, or Patient ID (e.g. 'tell me about Sahil' or 'UHID-2026-00001') to begin clinical rounds.",
        'intent': "prompt_patient_id",
        'requires_patient_selection': True
    }


if __name__ == '__main__':
    import os
    import sys
    # Add workspace/app root to path if needed
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    print("=" * 70)
    print(" DR. SETU — CLINICAL DECISION SUPPORT CONVERSATIONAL ENGINE ")
    print("=" * 70)
    
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from models.user_model import User
            doc = User.get_by_username('dr_khajuria')
            user_id = doc['user_id'] if doc else 1
            ConversationMemory.reset_state(user_id)
            
            sample_queries = [
                "How are you?",
                "Tell me about Sahil",
                "How is he doing?",
                "Is he getting better?",
                "Why?",
                "What is his EWS?",
                "Why is it that high?",
                "Why is he still in ICU?",
                "Okay, summarize the important things",
                "Okay thanks"
            ]
            
            for idx, q in enumerate(sample_queries, 1):
                print(f"\n[Turn {idx}] User: \"{q}\"")
                result = process_conversational_message(user_id=user_id, message=q)
                print(f"-> Detected Intent: {result.get('intent')}")
                print(f"-> Dr. Setu:\n{result.get('text')}")
                print("-" * 70)
                
            print("\n[SUCCESS] Dr. Setu Conversational Clinical Engine executed successfully.")
    except Exception as e:
        print(f"\n[ERROR] Execution failed: {e}")
        import traceback
        traceback.print_exc()
