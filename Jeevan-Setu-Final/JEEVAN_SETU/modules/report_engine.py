"""
modules/report_engine.py — Comprehensive Backend Report Generation Engine for Jeevan Setu.

Generates:
1. Multi-Patient & Single-Patient Clinical PDF Reports (Demographics, vitals, EWS, Decision Support, Transfers, History)
2. Patient Clinical Summary
3. Transfer Report
4. EWS History & Longitudinal Trend Report
5. Resource Utilization Report

Features:
- ReportLab-powered PDF Generation with Two-Pass `HospitalReportCanvas`
- Permanent repeating Hospital Header on EVERY single page with logo emblem & branding
- Repeating Footer with confidentiality notice and dynamic 'Page X of Y' on every page
- Clean patient isolation with page breaks for multi-patient batches
- CSV and JSON export formats
- Metadata recording in MySQL `reports` table and `audit_logs` for compliance
"""

import io
import csv
import json
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas

from database.db import db
from models.report_model import Report
from models.patient_model import Patient
from models.vitals_model import Vitals
from models.ward_model import Ward
from models.bed_model import Bed
from models.transfer_model import Transfer
from modules.scoring_engine import calculate_ews, get_risk_level, calculate_parameter_score
from services.decision_service import evaluate
from config import get_config


# ─────────────────────────────────────────────────────────────
# 1. Custom Two-Pass Numbered Canvas for Permanent Hospital Header
# ─────────────────────────────────────────────────────────────

class HospitalReportCanvas(canvas.Canvas):
    """
    Two-pass ReportLab Canvas that paints a permanent hospital header and
    'Page X of Y' footer on every single page of the generated PDF document.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_hospital_header_and_footer(num_pages)
            super().showPage()
        super().save()

    def draw_hospital_header_and_footer(self, total_pages):
        cfg = get_config()
        h_name = getattr(cfg, 'HOSPITAL_NAME', 'JEEVAN SETU MULTISPECIALTY HOSPITAL')
        h_tag = getattr(cfg, 'HOSPITAL_TAGLINE', 'Intelligent Clinical Decision & Critical Care Transfer System')
        h_addr = getattr(cfg, 'HOSPITAL_ADDRESS', 'Jeevan Setu Medical Enclave, Health City, Sector 12')
        h_loc = getattr(cfg, 'HOSPITAL_LOCATION', 'New Delhi, Delhi - 110029, India')
        h_phone = getattr(cfg, 'HOSPITAL_PHONE', '+91 11 2658 8500 / +91 1800 123 4567')
        h_email = getattr(cfg, 'HOSPITAL_EMAIL', 'clinical.reports@jeevansetu.org')
        h_web = getattr(cfg, 'HOSPITAL_WEBSITE', 'www.jeevansetu.org')

        self.saveState()
        page_w, page_h = letter  # 612 x 792 pt

        # ─── 1. TOP PERMANENT HOSPITAL HEADER (Appears on EVERY page) ───
        # Header Top Accent Bar
        self.setFillColor(colors.HexColor('#0a1e4d'))
        self.rect(0, page_h - 10, page_w, 10, fill=1, stroke=0)

        # Medical Cross Emblem Badge
        badge_x, badge_y = 36, page_h - 78
        self.setFillColor(colors.HexColor('#004ac6'))
        self.roundRect(badge_x, badge_y, 44, 44, 6, fill=1, stroke=0)

        # Medical Cross inside Badge
        self.setFillColor(colors.white)
        # Vertical Bar
        self.rect(badge_x + 18, badge_y + 8, 8, 28, fill=1, stroke=0)
        # Horizontal Bar
        self.rect(badge_x + 8, badge_y + 18, 28, 8, fill=1, stroke=0)
        # Central Accent dot
        self.setFillColor(colors.HexColor('#ef4444'))
        self.circle(badge_x + 22, badge_y + 22, 2.5, fill=1, stroke=0)

        # Hospital Text Branding
        self.setFillColor(colors.HexColor('#0a1e4d'))
        self.setFont('Helvetica-Bold', 12)
        self.drawString(88, page_h - 44, h_name)

        self.setFillColor(colors.HexColor('#2563eb'))
        self.setFont('Helvetica-Bold', 7.5)
        self.drawString(88, page_h - 55, h_tag.upper())

        self.setFillColor(colors.HexColor('#475569'))
        self.setFont('Helvetica', 7)
        self.drawString(88, page_h - 66, f"{h_addr}, {h_loc}")

        self.drawString(88, page_h - 76, f"Tel: {h_phone}  •  Email: {h_email}  •  Web: {h_web}")

        # Top Header Divider Rules
        self.setStrokeColor(colors.HexColor('#1e40af'))
        self.setLineWidth(1.5)
        self.line(36, page_h - 86, page_w - 36, page_h - 86)

        self.setStrokeColor(colors.HexColor('#bfdbfe'))
        self.setLineWidth(0.5)
        self.line(36, page_h - 88.5, page_w - 36, page_h - 88.5)

        # ─── 2. BOTTOM PERMANENT FOOTER (Appears on EVERY page) ───
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.75)
        self.line(36, 42, page_w - 36, 42)

        self.setFont('Helvetica-Bold', 7)
        self.setFillColor(colors.HexColor('#64748b'))
        self.drawString(36, 28, "CONFIDENTIAL & PROPRIETARY — JEEVAN SETU CLINICAL INTELLIGENCE PLATFORM")

        self.setFont('Helvetica', 7)
        self.drawString(36, 18, "For authorized hospital clinical and administrative staff use only. Not for public distribution.")

        self.setFont('Helvetica-Bold', 8)
        self.setFillColor(colors.HexColor('#0a1e4d'))
        page_text = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(page_w - 36, 25, page_text)

        self.restoreState()


# ─────────────────────────────────────────────────────────────
# 2. Section Normalization & Multi-Patient Report Data Generator
# ─────────────────────────────────────────────────────────────

def _normalize_sections(sections):
    """
    Normalizes a list or comma-separated string of section identifiers
    into a canonical set: {'vitals', 'ews', 'cds', 'transfers', 'timeline'}.
    """
    if sections is None:
        return {'vitals', 'ews', 'cds', 'transfers', 'timeline'}
    
    if isinstance(sections, str):
        parts = [s.strip().lower() for s in sections.split(',') if s.strip()]
    elif isinstance(sections, (list, tuple, set)):
        parts = [str(s).strip().lower() for s in sections if str(s).strip()]
    else:
        return {'vitals', 'ews', 'cds', 'transfers', 'timeline'}

    normalized = set()
    for p in parts:
        if p in ('vitals', 'vital', 'vital_signs', 'opt-vitals'):
            normalized.add('vitals')
        elif p in ('ews', 'ews_score', 'ews_breakdown', 'opt-ews'):
            normalized.add('ews')
        elif p in ('cds', 'decision_support', 'clinical_decision_support', 'opt-cds'):
            normalized.add('cds')
        elif p in ('transfers', 'transfer', 'transfer_history', 'opt-transfers'):
            normalized.add('transfers')
        elif p in ('timeline', 'events', 'audit_logs', 'clinical_timeline', 'opt-timeline'):
            normalized.add('timeline')
    return normalized


def generate_multi_patient_report_data(patient_ids, sections=None, generated_by=None, generated_by_name=None):
    """
    Fetch complete clinical, admission, vitals, EWS, CDS, and transfer records
    from MySQL for a list of patient IDs, configured for the selected report sections.
    """
    if not patient_ids:
        return {'error': 'Please select at least one patient to generate the report.'}

    active_sections = _normalize_sections(sections)
    if sections is not None and len(active_sections) == 0:
        return {'error': 'Please select at least one report section.'}

    # Ensure unique integer IDs
    clean_ids = []
    for pid in patient_ids:
        try:
            val = int(pid)
            if val not in clean_ids:
                clean_ids.append(val)
        except (ValueError, TypeError):
            continue

    if not clean_ids:
        return {'error': 'Invalid patient IDs provided.'}

    patients_data = []
    for pid in clean_ids:
        patient = Patient.get_by_id(pid)
        if not patient:
            continue

        # 1. Demographics & Admission Info
        uhid = patient.get('patient_code') or f"UHID-{patient['patient_id']:05d}"
        doctor_name = patient.get('doctor_name') or 'Not Assigned'
        nurse_name = patient.get('nurse_name') or 'Not Assigned'
        ward_name = patient.get('ward_name') or patient.get('ward_type') or 'General'
        bed_number = patient.get('bed_number') or patient.get('linked_bed_number') or 'N/A'
        
        # 2. Vitals History
        vitals_history = Vitals.get_history(pid, limit=20) or []
        latest_vital = vitals_history[0] if vitals_history else None

        # 3. EWS Breakdown
        ews_score = 0
        risk_level = 'normal'
        param_breakdown = {
            'heart_rate': {'value': None, 'score': 0, 'unit': 'bpm'},
            'blood_pressure_sys': {'value': None, 'score': 0, 'unit': 'mmHg'},
            'respiratory_rate': {'value': None, 'score': 0, 'unit': '/min'},
            'temperature': {'value': None, 'score': 0, 'unit': '°C'}
        }

        if latest_vital:
            hr = latest_vital.get('heart_rate')
            sbp = latest_vital.get('blood_pressure_sys')
            rr = latest_vital.get('respiratory_rate')
            temp = latest_vital.get('temperature')

            vitals_dict = {
                'heart_rate': hr,
                'blood_pressure_sys': sbp,
                'respiratory_rate': rr,
                'temperature': temp
            }
            ews_calc = calculate_ews(vitals_dict)
            ews_score = latest_vital.get('ews_score', ews_calc['total_score'])
            risk_level = ews_calc['risk_level']
            
            param_breakdown['heart_rate']['value'] = hr
            param_breakdown['heart_rate']['score'] = calculate_parameter_score('heart_rate', hr)
            param_breakdown['blood_pressure_sys']['value'] = sbp
            param_breakdown['blood_pressure_sys']['score'] = calculate_parameter_score('blood_pressure_sys', sbp)
            param_breakdown['respiratory_rate']['value'] = rr
            param_breakdown['respiratory_rate']['score'] = calculate_parameter_score('respiratory_rate', rr)
            param_breakdown['temperature']['value'] = temp
            param_breakdown['temperature']['score'] = calculate_parameter_score('temperature', temp)

        # 4. Clinical Decision Support
        decision = evaluate(ews_score)
        cds_info = {
            'condition': decision.get('condition', 'Stable'),
            'recommendation': decision.get('recommendation', 'Fit for HDU Transfer'),
            'ews_score': ews_score,
            'risk_level': risk_level,
            'explanation': (
                f"Automated 3-tier rule evaluation for Total EWS {ews_score}: "
                f"Condition is evaluated as {decision.get('condition')} with recommendation '{decision.get('recommendation')}'. "
                f"Assists clinical transfer triage."
            )
        }

        # 5. Transfers History
        transfers = Transfer.get_by_patient(pid) or []
        formatted_transfers = []
        for t in transfers:
            formatted_transfers.append({
                'transfer_id': t.get('transfer_id'),
                'from_ward': t.get('from_ward', 'N/A'),
                'to_ward': t.get('to_ward', 'N/A'),
                'from_bed': t.get('from_bed_number') or 'N/A',
                'to_bed': t.get('to_bed_number') or 'N/A',
                'reason': t.get('transfer_reason') or 'Clinical triage',
                'status': t.get('status', 'pending'),
                'requester': t.get('requester_name') or 'Clinical System',
                'approver': t.get('approver_name') or ('Approved' if t.get('status') == 'approved' else 'Pending'),
                'created_at': str(t.get('created_at', ''))[:19]
            })

        # 6. Patient Timeline / Audit History
        timeline_events = []
        try:
            events = db.execute_query(
                """SELECT action, description, created_at 
                   FROM audit_logs 
                   WHERE (entity_type = 'patient' AND entity_id = %s) 
                      OR (description LIKE %s)
                   ORDER BY created_at DESC LIMIT 8""",
                (pid, f"%{patient.get('name', '')}%"),
                fetch=True
            ) or []
            for ev in events:
                timeline_events.append({
                    'action': ev.get('action', 'ACTIVITY'),
                    'description': ev.get('description', ''),
                    'timestamp': str(ev.get('created_at', ''))[:19]
                })
        except Exception:
            pass

        patients_data.append({
            'patient_id': pid,
            'patient_code': uhid,
            'name': patient.get('name', 'N/A'),
            'age': patient.get('age', 'N/A'),
            'gender': patient.get('gender', 'N/A'),
            'blood_group': patient.get('blood_group', 'N/A'),
            'contact_number': patient.get('contact_number', 'N/A'),
            'emergency_contact': patient.get('emergency_contact', 'N/A'),
            'ward_type': patient.get('ward_type', 'N/A'),
            'ward_name': ward_name,
            'bed_number': bed_number,
            'diagnosis': patient.get('diagnosis', 'N/A'),
            'doctor_name': doctor_name,
            'nurse_name': nurse_name,
            'status': patient.get('status', 'admitted'),
            'admission_date': str(patient.get('admission_date', ''))[:19],
            'vitals_history': [
                {
                    'recorded_at': str(v.get('recorded_at', ''))[:19],
                    'heart_rate': v.get('heart_rate', '-'),
                    'blood_pressure_sys': v.get('blood_pressure_sys', '-'),
                    'respiratory_rate': v.get('respiratory_rate', '-'),
                    'temperature': v.get('temperature', '-'),
                    'ews_score': v.get('ews_score', 0)
                } for v in vitals_history[:10]
            ],
            'ews_breakdown': param_breakdown,
            'total_ews': ews_score,
            'risk_level': risk_level,
            'decision_support': cds_info,
            'transfers': formatted_transfers,
            'timeline': timeline_events
        })

    if not patients_data:
        return {'error': 'One or more selected patients could not be found in the database.'}

    now_dt = datetime.now()
    generated_at_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    gen_by_display = generated_by_name or (f"Admin #{generated_by}" if generated_by else "Authorized Administrator")

    num_pts = len(patients_data)
    title = f"Patient Management Report ({num_pts} {'Patient' if num_pts == 1 else 'Patients'})"
    if num_pts == 1:
        p0 = patients_data[0]
        title = f"Patient Clinical Report — {p0['name']} ({p0['patient_code']})"

    report_result = {
        'report_type': 'patient_management',
        'title': title,
        'generated_at': generated_at_str,
        'generated_date': now_dt.strftime('%Y-%m-%d'),
        'generated_time': now_dt.strftime('%H:%M:%S'),
        'generated_by': gen_by_display,
        'patient_count': num_pts,
        'patient_ids': [p['patient_id'] for p in patients_data],
        'sections': list(active_sections),
        'patients': patients_data
    }

    # Store metadata record in MySQL reports table
    try:
        report_id = Report.create(
            report_type='patient' if num_pts == 1 else 'daily',
            title=title,
            content=json.dumps(report_result, default=str),
            patient_id=patients_data[0]['patient_id'] if num_pts == 1 else None,
            generated_by=generated_by
        )
        report_result['report_id'] = report_id
    except Exception as e:
        print(f"[REPORT ENGINE] Warning saving report metadata: {e}")
        report_result['report_id'] = None

    return report_result


# ─────────────────────────────────────────────────────────────
# 3. Single-Patient Wrapper (Backwards Compatibility)
# ─────────────────────────────────────────────────────────────

def generate_patient_report_data(patient_id, sections=None, generated_by=None):
    """Backwards-compatible wrapper generating report data for a single patient."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return {'error': f'Patient #{patient_id} not found'}

    vitals_history = Vitals.get_history(patient_id, limit=50) or []
    vitals_summary = _summarize_vitals(vitals_history)
    latest_vitals = vitals_history[0] if vitals_history else None

    res = generate_multi_patient_report_data([patient_id], sections=sections, generated_by=generated_by)
    if 'error' in res:
        return res
    p0 = res['patients'][0]

    return {
        'report_id': res.get('report_id'),
        'report_type': 'patient',
        'title': res['title'],
        'generated_at': res['generated_at'],
        'sections': res.get('sections', ['vitals', 'ews', 'cds', 'transfers', 'timeline']),
        'data': {
            'patient': {
                'patient_id': p0['patient_id'],
                'patient_code': p0['patient_code'],
                'name': p0['name'],
                'age': p0['age'],
                'gender': p0['gender'],
                'blood_group': p0['blood_group'],
                'ward_type': p0['ward_type'],
                'ward_name': p0['ward_name'],
                'bed_number': p0['bed_number'],
                'diagnosis': p0['diagnosis'],
                'doctor_name': p0['doctor_name'],
                'status': p0['status'],
                'admission_date': p0['admission_date']
            },
            'latest_vitals': {
                'heart_rate': latest_vitals.get('heart_rate') if latest_vitals else None,
                'blood_pressure_sys': latest_vitals.get('blood_pressure_sys') if latest_vitals else None,
                'blood_pressure_dia': latest_vitals.get('blood_pressure_dia') if latest_vitals else None,
                'respiratory_rate': latest_vitals.get('respiratory_rate') if latest_vitals else None,
                'temperature': latest_vitals.get('temperature') if latest_vitals else None,
                'spo2': latest_vitals.get('spo2') if latest_vitals else None,
                'ews_score': latest_vitals.get('ews_score') if latest_vitals else 0,
                'recorded_at': str(latest_vitals.get('recorded_at', '')) if latest_vitals else None
            } if latest_vitals else None,
            'vitals_summary': vitals_summary,
            'total_readings': len(vitals_history),
            'readings': [
                {
                    'heart_rate': v.get('heart_rate'),
                    'blood_pressure': f"{v.get('blood_pressure_sys', '-')}/-",
                    'respiratory_rate': v.get('respiratory_rate'),
                    'temperature': v.get('temperature'),
                    'spo2': v.get('spo2'),
                    'ews_score': v.get('ews_score', 0),
                    'recorded_at': str(v.get('recorded_at', ''))
                } for v in vitals_history[:10]
            ],
            'generated_at': res['generated_at']
        },
        'patients_data': res
    }


# ─────────────────────────────────────────────────────────────
# 4. Multi-Patient Professional PDF Renderer (ReportLab)
# ─────────────────────────────────────────────────────────────

def render_multi_patient_pdf(report_result, sections=None):
    """
    Renders a comprehensive, multi-page clinical report PDF for selected patients
    featuring a permanent repeating hospital header, dynamic Page X of Y footer,
    and strictly including only the selected report sections.
    """
    active_sections = _normalize_sections(sections or report_result.get('sections'))
    if len(active_sections) == 0:
        raise ValueError('Please select at least one report section.')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=104,   # Clearance for permanent top header (height=88pt)
        bottomMargin=48  # Clearance for permanent bottom footer (height=42pt)
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0a1e4d'),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'RepSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569')
    )
    section_heading_style = ParagraphStyle(
        'SecHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#0a1e4d'),
        spaceBefore=8,
        spaceAfter=4
    )
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#334155')
    )
    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1e293b')
    )
    cell_bold_style = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    )
    cell_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.white
    )
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#64748b')
    )

    story = []

    # ── Document Header Summary Banner ──
    story.append(Paragraph("PATIENT MANAGEMENT REPORT", title_style))
    story.append(Paragraph("Confidential Clinical Summary, Vital Signs Monitoring, EWS Analysis & Transfer History", subtitle_style))
    story.append(Spacer(1, 6))

    # Meta Info Card
    meta_data = [
        [
            Paragraph("<b>Generated Date:</b>", meta_label_style),
            Paragraph(report_result.get('generated_date', str(datetime.now().date())), meta_val_style),
            Paragraph("<b>Generated Time:</b>", meta_label_style),
            Paragraph(report_result.get('generated_time', datetime.now().strftime('%H:%M:%S')), meta_val_style),
        ],
        [
            Paragraph("<b>Generated By:</b>", meta_label_style),
            Paragraph(str(report_result.get('generated_by', 'Administrator')), meta_val_style),
            Paragraph("<b>Selected Patients:</b>", meta_label_style),
            Paragraph(f"<b>{report_result.get('patient_count', 1)}</b> Patient(s)", meta_val_style),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[95, 175, 100, 170])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    patients = report_result.get('patients', [])

    # Iterate over each selected patient
    for idx, p in enumerate(patients):
        if idx > 0:
            # Start each subsequent patient on a brand new page
            story.append(PageBreak())

        # Patient Banner Bar
        patient_title_text = f"PATIENT #{idx + 1} — {p.get('name', 'N/A').upper()}  |  UHID: {p.get('patient_code', 'N/A')}"
        banner_data = [[Paragraph(f"<font color='white'><b>{patient_title_text}</b></font>", ParagraphStyle('PTitle', parent=cell_header_style, fontSize=9, leading=12))]]
        banner_table = Table(banner_data, colWidths=[540])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0a1e4d')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 6))

        # ── Always Included: Demographics & Admission Information ──
        demographics_data = [
            [
                Paragraph("<b>UHID:</b>", meta_label_style), Paragraph(str(p.get('patient_code', 'N/A')), meta_val_style),
                Paragraph("<b>Ward / Unit:</b>", meta_label_style), Paragraph(str(p.get('ward_name', 'N/A')), meta_val_style)
            ],
            [
                Paragraph("<b>Patient Name:</b>", meta_label_style), Paragraph(str(p.get('name', 'N/A')), meta_val_style),
                Paragraph("<b>Bed Number:</b>", meta_label_style), Paragraph(str(p.get('bed_number', 'N/A')), meta_val_style)
            ],
            [
                Paragraph("<b>Age / Gender:</b>", meta_label_style), Paragraph(f"{p.get('age', 'N/A')} yrs / {p.get('gender', 'N/A')}", meta_val_style),
                Paragraph("<b>Admission Date:</b>", meta_label_style), Paragraph(str(p.get('admission_date', 'N/A')), meta_val_style)
            ],
            [
                Paragraph("<b>Blood Group:</b>", meta_label_style), Paragraph(str(p.get('blood_group', 'N/A')), meta_val_style),
                Paragraph("<b>Current Status:</b>", meta_label_style), Paragraph(str(p.get('status', 'Admitted')).upper(), meta_val_style)
            ],
            [
                Paragraph("<b>Primary Diagnosis:</b>", meta_label_style), Paragraph(str(p.get('diagnosis', 'N/A')), meta_val_style),
                Paragraph("<b>Attending Doctor:</b>", meta_label_style), Paragraph(str(p.get('doctor_name', 'N/A')), meta_val_style)
            ],
            [
                Paragraph("<b>Emergency Contact:</b>", meta_label_style), Paragraph(str(p.get('emergency_contact') or p.get('contact_number') or 'N/A'), meta_val_style),
                Paragraph("<b>Assigned Nurse:</b>", meta_label_style), Paragraph(str(p.get('nurse_name', 'N/A')), meta_val_style)
            ]
        ]
        demo_table = Table(demographics_data, colWidths=[95, 175, 100, 170])
        demo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 3.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(demo_table)
        story.append(Spacer(1, 8))

        # ── 1. Vital Signs Table (Conditional) ──
        if 'vitals' in active_sections:
            story.append(Paragraph("Vital Signs Monitoring Records", section_heading_style))
            vitals = p.get('vitals_history', [])
            if vitals:
                vt_headers = [
                    Paragraph("Recorded At", cell_header_style),
                    Paragraph("Heart Rate", cell_header_style),
                    Paragraph("Systolic BP", cell_header_style),
                    Paragraph("Resp Rate", cell_header_style),
                    Paragraph("Temp (°C)", cell_header_style),
                    Paragraph("EWS Score", cell_header_style)
                ]
                vt_rows = [vt_headers]
                for v in vitals[:8]:
                    vt_rows.append([
                        Paragraph(str(v.get('recorded_at', ''))[:16], cell_style),
                        Paragraph(f"{v.get('heart_rate', '-')} bpm" if v.get('heart_rate') is not None else "-", cell_style),
                        Paragraph(f"{v.get('blood_pressure_sys', '-')} mmHg" if v.get('blood_pressure_sys') is not None else "-", cell_style),
                        Paragraph(f"{v.get('respiratory_rate', '-')} /min" if v.get('respiratory_rate') is not None else "-", cell_style),
                        Paragraph(f"{v.get('temperature', '-')} °C" if v.get('temperature') is not None else "-", cell_style),
                        Paragraph(f"<b>{v.get('ews_score', 0)}</b>", cell_bold_style)
                    ])
                vt_table = Table(vt_rows, colWidths=[120, 85, 90, 85, 80, 80])
                vt_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004ac6')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                    ('PADDING', (0, 0), (-1, -1), 3.5),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(vt_table)
            else:
                no_vitals_p = Paragraph("<i>No vital records recorded in the system for this patient.</i>", disclaimer_style)
                story.append(no_vitals_p)
            story.append(Spacer(1, 8))

        # ── 2. Early Warning Score (EWS) Breakdown (Conditional) ──
        if 'ews' in active_sections:
            story.append(Paragraph("Early Warning Score (EWS) Clinical Evaluation", section_heading_style))
            ews_bd = p.get('ews_breakdown', {})
            tot_ews = p.get('total_ews', 0)
            risk_lvl = p.get('risk_level', 'normal').upper()

            risk_bg_map = {
                'CRITICAL': colors.HexColor('#fee2e2'),
                'HIGH': colors.HexColor('#ffedd5'),
                'MEDIUM': colors.HexColor('#fef9c3'),
                'LOW': colors.HexColor('#dcfce7'),
                'NORMAL': colors.HexColor('#f1f5f9')
            }
            risk_txt_map = {
                'CRITICAL': '#b91c1c',
                'HIGH': '#c2410c',
                'MEDIUM': '#a16207',
                'LOW': '#15803d',
                'NORMAL': '#334155'
            }

            ews_table_data = [
                [
                    Paragraph("Parameter", cell_header_style),
                    Paragraph("Recorded Value", cell_header_style),
                    Paragraph("Assigned EWS Points (0–3)", cell_header_style),
                    Paragraph("Scoring Threshold Reference", cell_header_style)
                ],
                [
                    Paragraph("<b>Heart Rate</b>", cell_style),
                    Paragraph(f"{ews_bd.get('heart_rate', {}).get('value') or '-'} bpm", cell_style),
                    Paragraph(f"<b>+{ews_bd.get('heart_rate', {}).get('score', 0)}</b>", cell_bold_style),
                    Paragraph("0: 51–90 | 1: 41–50, 91–110 | 2: 111–130 | 3: ≤40, ≥131", disclaimer_style)
                ],
                [
                    Paragraph("<b>Systolic Blood Pressure</b>", cell_style),
                    Paragraph(f"{ews_bd.get('blood_pressure_sys', {}).get('value') or '-'} mmHg", cell_style),
                    Paragraph(f"<b>+{ews_bd.get('blood_pressure_sys', {}).get('score', 0)}</b>", cell_bold_style),
                    Paragraph("0: 101–199 | 1: 81–100 | 2: 71–80 | 3: ≤70, ≥200", disclaimer_style)
                ],
                [
                    Paragraph("<b>Respiratory Rate</b>", cell_style),
                    Paragraph(f"{ews_bd.get('respiratory_rate', {}).get('value') or '-'} /min", cell_style),
                    Paragraph(f"<b>+{ews_bd.get('respiratory_rate', {}).get('score', 0)}</b>", cell_bold_style),
                    Paragraph("0: 12–20 | 1: 9–11 | 2: 21–24 | 3: ≤8, ≥25", disclaimer_style)
                ],
                [
                    Paragraph("<b>Body Temperature</b>", cell_style),
                    Paragraph(f"{ews_bd.get('temperature', {}).get('value') or '-'} °C", cell_style),
                    Paragraph(f"<b>+{ews_bd.get('temperature', {}).get('score', 0)}</b>", cell_bold_style),
                    Paragraph("0: 36.1–38.0 | 1: 35.1–36.0, 38.1–39.0 | 2: ≥39.1 | 3: ≤35.0", disclaimer_style)
                ],
            ]
            ews_tbl = Table(ews_table_data, colWidths=[120, 100, 110, 210])
            ews_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#006591')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('PADDING', (0, 0), (-1, -1), 3),
                ('ALIGN', (1, 0), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(ews_tbl)
            story.append(Spacer(1, 4))

            # EWS Summary Badge Box
            risk_color_hex = risk_txt_map.get(risk_lvl, '#334155')
            ews_summary_data = [[
                Paragraph(f"<b>TOTAL EWS SCORE: {tot_ews}</b>", ParagraphStyle('EWSTot', parent=meta_label_style, fontSize=8.5, textColor=colors.HexColor('#0a1e4d'))),
                Paragraph(f"Risk Stratification: <font color='{risk_color_hex}'><b>{risk_lvl} RISK</b></font>", ParagraphStyle('EWSRisk', parent=meta_label_style, fontSize=8.5))
            ]]
            ews_sum_tbl = Table(ews_summary_data, colWidths=[270, 270])
            ews_sum_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), risk_bg_map.get(risk_lvl, colors.HexColor('#f1f5f9'))),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(risk_color_hex)),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(ews_sum_tbl)
            story.append(Spacer(1, 8))

        # ── 3. Clinical Decision Support (CDS) (Conditional) ──
        if 'cds' in active_sections:
            story.append(Paragraph("Clinical Decision Support & Transfer Guidance", section_heading_style))
            cds = p.get('decision_support', {})
            cds_data = [
                [
                    Paragraph("<b>Evaluated Condition:</b>", meta_label_style),
                    Paragraph(f"<b>{cds.get('condition', 'Stable')}</b>", meta_val_style),
                    Paragraph("<b>Triage Recommendation:</b>", meta_label_style),
                    Paragraph(f"<font color='#004ac6'><b>{cds.get('recommendation', 'Fit for HDU Transfer')}</b></font>", meta_val_style)
                ],
                [
                    Paragraph("<b>Decision Rationale:</b>", meta_label_style),
                    Paragraph(cds.get('explanation', 'Standard clinical protocol applied based on vital signs parameters.'), meta_val_style),
                    Paragraph("<b>Clinical Disclaimer:</b>", meta_label_style),
                    Paragraph("Clinical Decision Support assists staff; final triage requires attending clinician approval.", disclaimer_style)
                ]
            ]
            cds_table = Table(cds_data, colWidths=[105, 165, 110, 160])
            cds_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
                ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#bfdbfe')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dbeafe')),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(cds_table)
            story.append(Spacer(1, 8))

        # ── 4. Ward & Bed Transfer History (Conditional) ──
        if 'transfers' in active_sections:
            story.append(Paragraph("Ward & Bed Transfer History", section_heading_style))
            transfers = p.get('transfers', [])
            if transfers:
                tr_headers = [
                    Paragraph("Transfer ID", cell_header_style),
                    Paragraph("From Ward (Bed)", cell_header_style),
                    Paragraph("To Ward (Bed)", cell_header_style),
                    Paragraph("Reason", cell_header_style),
                    Paragraph("Status", cell_header_style),
                    Paragraph("Approver", cell_header_style),
                    Paragraph("Requested At", cell_header_style)
                ]
                tr_rows = [tr_headers]
                for t in transfers[:5]:
                    status_color = '#15803d' if t.get('status') in ('approved', 'completed') else ('#b91c1c' if t.get('status') == 'rejected' else '#b45309')
                    tr_rows.append([
                        Paragraph(f"#{t.get('transfer_id')}", cell_style),
                        Paragraph(f"{t.get('from_ward')} ({t.get('from_bed')})", cell_style),
                        Paragraph(f"{t.get('to_ward')} ({t.get('to_bed')})", cell_style),
                        Paragraph(str(t.get('reason', ''))[:22], cell_style),
                        Paragraph(f"<font color='{status_color}'><b>{t.get('status', '').upper()}</b></font>", cell_style),
                        Paragraph(str(t.get('approver', ''))[:16], cell_style),
                        Paragraph(str(t.get('created_at', ''))[:16], cell_style)
                    ])
                tr_table = Table(tr_rows, colWidths=[55, 90, 90, 105, 60, 70, 70])
                tr_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                    ('PADDING', (0, 0), (-1, -1), 3.5),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(tr_table)
            else:
                no_tr_p = Paragraph("<i>No transfer records found for this patient.</i>", disclaimer_style)
                story.append(no_tr_p)
            story.append(Spacer(1, 8))

        # ── 5. Patient Clinical Timeline & Event Log (Conditional) ──
        if 'timeline' in active_sections:
            story.append(Paragraph("Patient Clinical Timeline & Event Log", section_heading_style))
            timeline = p.get('timeline', [])
            if timeline:
                tl_headers = [
                    Paragraph("Timestamp", cell_header_style),
                    Paragraph("Action / Event", cell_header_style),
                    Paragraph("Details", cell_header_style)
                ]
                tl_rows = [tl_headers]
                for ev in timeline[:5]:
                    tl_rows.append([
                        Paragraph(str(ev.get('timestamp', ''))[:16], cell_style),
                        Paragraph(f"<b>{ev.get('action', 'EVENT')}</b>", cell_style),
                        Paragraph(str(ev.get('description', ''))[:60], cell_style)
                    ])
                tl_table = Table(tl_rows, colWidths=[110, 130, 300])
                tl_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                    ('PADDING', (0, 0), (-1, -1), 3.5),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(tl_table)
            else:
                no_tl_p = Paragraph("<i>No audit log records recorded for this patient.</i>", disclaimer_style)
                story.append(no_tl_p)
            story.append(Spacer(1, 8))

    # Build the document using our custom HospitalReportCanvas
    doc.build(story, canvasmaker=HospitalReportCanvas)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────
# 5. Additional Report Data Generators (Transfers, EWS, Utilization)
# ─────────────────────────────────────────────────────────────

def generate_transfer_report_data(patient_id=None, generated_by=None):
    """Generate transfer report data across the hospital or for a specific patient."""
    query = """
        SELECT t.*, p.name AS patient_name, p.patient_code,
               u1.full_name AS requested_by_name, u2.full_name AS approved_by_name
        FROM transfers t
        JOIN patients p ON t.patient_id = p.patient_id
        LEFT JOIN users u1 ON t.requested_by = u1.user_id
        LEFT JOIN users u2 ON t.approved_by = u2.user_id
    """
    params = []
    if patient_id:
        query += " WHERE t.patient_id = %s"
        params.append(patient_id)

    query += " ORDER BY t.created_at DESC LIMIT 100"

    transfers = db.execute_query(query, tuple(params), fetch=True) or []

    total_transfers = len(transfers)
    completed_count = sum(1 for t in transfers if t.get('status') == 'completed')
    approved_count = sum(1 for t in transfers if t.get('status') == 'approved')
    pending_count = sum(1 for t in transfers if t.get('status') == 'pending')
    rejected_count = sum(1 for t in transfers if t.get('status') == 'rejected')

    transfer_items = []
    for t in transfers:
        transfer_items.append({
            'transfer_id': t['transfer_id'],
            'patient_id': t['patient_id'],
            'patient_name': t.get('patient_name', f"Patient #{t['patient_id']}"),
            'patient_code': t.get('patient_code', 'N/A'),
            'from_ward': t['from_ward'],
            'to_ward': t['to_ward'],
            'from_bed': t.get('from_bed_number') or 'N/A',
            'to_bed': t.get('to_bed_number') or 'N/A',
            'transfer_reason': t.get('transfer_reason') or 'Clinical recommendation',
            'status': t['status'],
            'requested_by': t.get('requested_by_name') or 'Clinical Engine',
            'approved_by': t.get('approved_by_name') or 'Pending',
            'requested_at': str(t.get('requested_at', '')),
            'completed_at': str(t.get('completed_at', '')) if t.get('completed_at') else None
        })

    report_content = {
        'summary': {
            'total_transfers': total_transfers,
            'completed': completed_count,
            'approved': approved_count,
            'pending': pending_count,
            'rejected': rejected_count
        },
        'patient_filter': patient_id,
        'transfers': transfer_items,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    title = f"Patient Transfer Report — {datetime.now().strftime('%Y-%m-%d')}"
    if patient_id and transfers:
        title = f"Transfer History — {transfers[0]['patient_name']} ({datetime.now().strftime('%Y-%m-%d')})"

    report_id = Report.create(
        report_type='transfer',
        title=title,
        content=json.dumps(report_content),
        patient_id=patient_id,
        generated_by=generated_by
    )

    return {
        'report_id': report_id,
        'report_type': 'transfers',
        'title': title,
        'generated_at': report_content['generated_at'],
        'data': report_content
    }


def generate_ews_history_data(patient_id, generated_by=None):
    """Generate serial EWS history and risk trend report for a patient."""
    patient = Patient.get_by_id(patient_id)
    if not patient:
        return {'error': f'Patient #{patient_id} not found'}

    vitals = Vitals.get_history(patient_id, limit=100)
    scores = [v['ews_score'] for v in vitals if v.get('ews_score') is not None]

    peak_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    latest_score = scores[0] if scores else 0

    history_items = []
    for v in vitals:
        score = v.get('ews_score', 0)
        risk = "CRITICAL" if score >= 7 else ("HIGH" if score >= 5 else ("MEDIUM" if score >= 3 else "LOW"))
        history_items.append({
            'vital_id': v.get('vital_id'),
            'ews_score': score,
            'risk_level': risk,
            'heart_rate': v.get('heart_rate'),
            'blood_pressure': f"{v.get('blood_pressure_sys', '-')}/{v.get('blood_pressure_dia', '-')}",
            'respiratory_rate': v.get('respiratory_rate'),
            'temperature': v.get('temperature'),
            'spo2': v.get('spo2'),
            'recorded_at': str(v.get('recorded_at', ''))
        })

    report_content = {
        'patient': {
            'patient_id': patient['patient_id'],
            'patient_code': patient.get('patient_code', f"UHID-{patient['patient_id']:05d}"),
            'name': patient['name'],
            'ward_type': patient.get('ward_type', 'N/A'),
            'bed_number': patient.get('bed_number', 'N/A'),
            'diagnosis': patient.get('diagnosis', 'N/A')
        },
        'ews_stats': {
            'latest_score': latest_score,
            'peak_score': peak_score,
            'lowest_score': lowest_score,
            'avg_score': avg_score,
            'total_evaluations': len(scores)
        },
        'history': history_items,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    title = f"EWS History & Longitudinal Trend — {patient['name']}"
    report_id = Report.create(
        report_type='ews',
        title=title,
        content=json.dumps(report_content),
        patient_id=patient_id,
        generated_by=generated_by
    )

    return {
        'report_id': report_id,
        'report_type': 'ews',
        'title': title,
        'generated_at': report_content['generated_at'],
        'data': report_content
    }


def generate_resource_utilization_data(generated_by=None):
    """Generate hospital resource utilization metrics (wards, beds, occupancy rates)."""
    wards = Ward.get_all() or []
    all_beds = Bed.get_all() or []

    total_beds = len(all_beds)
    occupied_beds = sum(1 for b in all_beds if b.get('status') == 'occupied')
    available_beds = sum(1 for b in all_beds if b.get('status') == 'available')
    maintenance_beds = sum(1 for b in all_beds if b.get('status') == 'maintenance')
    overall_occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

    ward_breakdown = []
    for w in wards:
        w_id = w['ward_id']
        w_beds = [b for b in all_beds if b.get('ward_id') == w_id]
        w_total = len(w_beds)
        w_occupied = sum(1 for b in w_beds if b.get('status') == 'occupied')
        w_available = sum(1 for b in w_beds if b.get('status') == 'available')
        w_maintenance = sum(1 for b in w_beds if b.get('status') == 'maintenance')
        w_rate = round((w_occupied / w_total * 100), 1) if w_total > 0 else 0.0

        ward_breakdown.append({
            'ward_id': w_id,
            'name': w['name'],
            'ward_type': w['ward_type'],
            'floor_number': w.get('floor_number', 1),
            'capacity': w.get('capacity', w_total),
            'total_beds': w_total,
            'occupied_beds': w_occupied,
            'available_beds': w_available,
            'maintenance_beds': w_maintenance,
            'occupancy_rate_pct': w_rate
        })

    report_content = {
        'hospital_summary': {
            'total_wards': len(wards),
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'available_beds': available_beds,
            'maintenance_beds': maintenance_beds,
            'overall_occupancy_rate_pct': overall_occupancy_rate
        },
        'ward_breakdown': ward_breakdown,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    title = f"Hospital Resource Utilization Report — {datetime.now().strftime('%Y-%m-%d')}"
    report_id = Report.create(
        report_type='utilization',
        title=title,
        content=json.dumps(report_content),
        patient_id=None,
        generated_by=generated_by
    )

    return {
        'report_id': report_id,
        'report_type': 'resource_utilization',
        'title': title,
        'generated_at': report_content['generated_at'],
        'data': report_content
    }


def _summarize_vitals(vitals_list):
    """Calculate min, max, and average for each vital parameter."""
    if not vitals_list:
        return {}

    params = ['heart_rate', 'blood_pressure_sys', 'blood_pressure_dia',
              'respiratory_rate', 'temperature', 'spo2', 'ews_score']
    summary = {}

    for param in params:
        values = [v[param] for v in vitals_list if v.get(param) is not None]
        if values:
            summary[param] = {
                'min': round(min(values), 1),
                'max': round(max(values), 1),
                'avg': round(sum(values) / len(values), 1),
                'readings': len(values)
            }

    return summary


# ─────────────────────────────────────────────────────────────
# 6. CSV Export Renderer
# ─────────────────────────────────────────────────────────────

def render_report_csv(report_type, report_result):
    """Convert report data into clean, standard CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)
    data = report_result.get('data', {})

    if report_type in ('patient', 'daily', 'discharge', 'patient_management'):
        patients = report_result.get('patients') or ([data.get('patient')] if data.get('patient') else [])
        writer.writerow(["=== JEEVAN SETU PATIENT CLINICAL REPORT ==="])
        writer.writerow(["Generated At", report_result.get('generated_at', '')])
        writer.writerow(["Total Patients", len(patients)])
        writer.writerow([])

        for p in patients:
            writer.writerow(["--- PATIENT DEMOGRAPHICS ---"])
            writer.writerow(["UHID", p.get('patient_code', '')])
            writer.writerow(["Patient Name", p.get('name', '')])
            writer.writerow(["Age / Gender", f"{p.get('age', '')} / {p.get('gender', '')}"])
            writer.writerow(["Ward / Bed", f"{p.get('ward_name', '')} / {p.get('bed_number', '')}"])
            writer.writerow(["Diagnosis", p.get('diagnosis', '')])
            writer.writerow(["Attending Doctor", p.get('doctor_name', '')])
            writer.writerow(["Assigned Nurse", p.get('nurse_name', '')])
            writer.writerow(["Total EWS", p.get('total_ews', 0)])
            writer.writerow(["Risk Level", p.get('risk_level', 'NORMAL')])
            writer.writerow([])

            writer.writerow(["--- Recent Vitals ---"])
            writer.writerow(["Recorded At", "Heart Rate (bpm)", "Systolic BP (mmHg)", "Resp Rate (/min)", "Temp (°C)", "EWS Score"])
            for r in p.get('vitals_history', []):
                writer.writerow([
                    r.get('recorded_at', ''),
                    r.get('heart_rate', ''),
                    r.get('blood_pressure_sys', ''),
                    r.get('respiratory_rate', ''),
                    r.get('temperature', ''),
                    r.get('ews_score', '')
                ])
            writer.writerow([])
            writer.writerow(["=" * 50])
            writer.writerow([])

    elif report_type == 'transfers':
        s = data.get('summary', {})
        writer.writerow(["=== JEEVAN SETU PATIENT TRANSFER REPORT ==="])
        writer.writerow(["Generated At", data.get('generated_at', '')])
        writer.writerow(["Total Transfers", s.get('total_transfers', 0)])
        writer.writerow(["Completed", s.get('completed', 0)])
        writer.writerow(["Approved", s.get('approved', 0)])
        writer.writerow(["Pending", s.get('pending', 0)])
        writer.writerow(["Rejected", s.get('rejected', 0)])
        writer.writerow([])

        writer.writerow(["Transfer ID", "UHID", "Patient Name", "From Ward", "To Ward", "From Bed", "To Bed", "Status", "Reason", "Approved By", "Completed At"])
        for t in data.get('transfers', []):
            writer.writerow([
                t.get('transfer_id'),
                t.get('patient_code'),
                t.get('patient_name'),
                t.get('from_ward'),
                t.get('to_ward'),
                t.get('from_bed'),
                t.get('to_bed'),
                t.get('status'),
                t.get('transfer_reason'),
                t.get('approved_by'),
                t.get('completed_at') or 'N/A'
            ])

    elif report_type == 'ews':
        p = data.get('patient', {})
        st = data.get('ews_stats', {})
        writer.writerow(["=== JEEVAN SETU EWS LONGITUDINAL REPORT ==="])
        writer.writerow(["Generated At", data.get('generated_at', '')])
        writer.writerow(["Patient Name", p.get('name', '')])
        writer.writerow(["UHID", p.get('patient_code', '')])
        writer.writerow(["Latest EWS", st.get('latest_score', 0)])
        writer.writerow(["Peak EWS", st.get('peak_score', 0)])
        writer.writerow(["Average EWS", st.get('avg_score', 0)])
        writer.writerow([])

        writer.writerow(["Recorded At", "EWS Score", "Risk Level", "Heart Rate", "Blood Pressure", "Resp Rate", "Temp (°C)", "SpO2 (%)"])
        for h in data.get('history', []):
            writer.writerow([
                h.get('recorded_at', ''),
                h.get('ews_score', ''),
                h.get('risk_level', ''),
                h.get('heart_rate', ''),
                h.get('blood_pressure', ''),
                h.get('respiratory_rate', ''),
                h.get('temperature', ''),
                h.get('spo2', '')
            ])

    elif report_type in ('resource_utilization', 'utilization'):
        hs = data.get('hospital_summary', {})
        writer.writerow(["=== JEEVAN SETU RESOURCE UTILIZATION REPORT ==="])
        writer.writerow(["Generated At", data.get('generated_at', '')])
        writer.writerow(["Total Wards", hs.get('total_wards', 0)])
        writer.writerow(["Total Beds", hs.get('total_beds', 0)])
        writer.writerow(["Occupied Beds", hs.get('occupied_beds', 0)])
        writer.writerow(["Available Beds", hs.get('available_beds', 0)])
        writer.writerow(["Maintenance Beds", hs.get('maintenance_beds', 0)])
        writer.writerow(["Overall Occupancy Rate (%)", hs.get('overall_occupancy_rate_pct', 0)])
        writer.writerow([])

        writer.writerow(["Ward ID", "Ward Name", "Ward Type", "Floor", "Total Beds", "Occupied", "Available", "Maintenance", "Occupancy Rate (%)"])
        for w in data.get('ward_breakdown', []):
            writer.writerow([
                w.get('ward_id'),
                w.get('name'),
                w.get('ward_type'),
                w.get('floor_number'),
                w.get('total_beds'),
                w.get('occupied_beds'),
                w.get('available_beds'),
                w.get('maintenance_beds'),
                f"{w.get('occupancy_rate_pct')}%"
            ])

    return output.getvalue()


# ─────────────────────────────────────────────────────────────
# 7. Generic Legacy PDF Renderer
# ─────────────────────────────────────────────────────────────

def render_report_pdf(report_type, report_result):
    """Generic PDF renderer routing to the multi-patient PDF generator or specialized layout."""
    if report_type in ('patient', 'daily', 'discharge', 'patient_management') or 'patients' in report_result:
        # If report_result came from legacy single patient, ensure patients list exists
        if 'patients' not in report_result and 'patients_data' in report_result:
            return render_multi_patient_pdf(report_result['patients_data'])
        elif 'patients' in report_result:
            return render_multi_patient_pdf(report_result)
        else:
            # Fallback
            p_id = report_result.get('data', {}).get('patient', {}).get('patient_id')
            if p_id:
                data = generate_multi_patient_report_data([p_id])
                return render_multi_patient_pdf(data)

    # For other report types, use HospitalReportCanvas as well
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=104,
        bottomMargin=48
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor('#0a1e4d')
    )
    normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11)
    
    story = []
    title = report_result.get('title', 'Jeevan Setu Clinical Report')
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(f"Generated on: {report_result.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}", normal_style))
    story.append(Spacer(1, 10))

    data = report_result.get('data', {})

    if report_type == 'transfers':
        s = data.get('summary', {})
        story.append(Paragraph(f"<b>Summary:</b> Total Transfers: {s.get('total_transfers', 0)} | Completed: {s.get('completed', 0)} | Pending: {s.get('pending', 0)} | Rejected: {s.get('rejected', 0)}", normal_style))
        story.append(Spacer(1, 8))
        transfers = data.get('transfers', [])
        if transfers:
            table_data = [["ID", "Patient Name", "From", "To", "Reason", "Status", "Approved By"]]
            for t in transfers[:25]:
                table_data.append([
                    f"#{t.get('transfer_id')}",
                    t.get('patient_name', '')[:16],
                    f"{t.get('from_ward')} ({t.get('from_bed')})",
                    f"{t.get('to_ward')} ({t.get('to_bed')})",
                    t.get('transfer_reason', '')[:20],
                    t.get('status', '').upper(),
                    t.get('approved_by', '')[:14]
                ])
            t_table = Table(table_data, colWidths=[35, 110, 85, 85, 100, 55, 70])
            t_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a1e4d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('FONTSIZE', (0, 0), (-1, -1), 7.5),
                ('PADDING', (0, 0), (-1, -1), 3.5),
            ]))
            story.append(t_table)

    elif report_type in ('resource_utilization', 'utilization'):
        hs = data.get('hospital_summary', {})
        story.append(Paragraph(f"<b>Hospital Capacity:</b> Total Beds: {hs.get('total_beds', 0)} | Occupied: {hs.get('occupied_beds', 0)} | Available: {hs.get('available_beds', 0)} | Maintenance: {hs.get('maintenance_beds', 0)}", normal_style))
        story.append(Paragraph(f"<b>Overall Hospital Occupancy Rate:</b> {hs.get('overall_occupancy_rate_pct', 0)}%", normal_style))
        story.append(Spacer(1, 8))
        wards = data.get('ward_breakdown', [])
        if wards:
            table_data = [["Ward Name", "Type", "Floor", "Total Beds", "Occupied", "Available", "Maint.", "Occupancy %"]]
            for w in wards:
                table_data.append([
                    w.get('name', ''),
                    w.get('ward_type', ''),
                    str(w.get('floor_number', 1)),
                    str(w.get('total_beds', 0)),
                    str(w.get('occupied_beds', 0)),
                    str(w.get('available_beds', 0)),
                    str(w.get('maintenance_beds', 0)),
                    f"{w.get('occupancy_rate_pct', 0)}%"
                ])
            w_table = Table(table_data, colWidths=[110, 65, 45, 65, 60, 60, 50, 75])
            w_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a1e4d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('FONTSIZE', (0, 0), (-1, -1), 7.5),
                ('PADDING', (0, 0), (-1, -1), 3.5),
            ]))
            story.append(w_table)

    doc.build(story, canvasmaker=HospitalReportCanvas)
    return buffer.getvalue()
