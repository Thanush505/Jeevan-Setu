"""
modules/alert_engine.py — Alert generation engine.

Monitors patient vitals and generates alerts for abnormal values.
"""

from models.alert_model import Alert
from utils.constants import VITAL_THRESHOLDS


def check_vitals_and_alert(patient_id, vitals_data, patient_name='Unknown'):
    """
    Check vital signs against thresholds and generate alerts.

    Args:
        patient_id (int): The patient's ID.
        vitals_data (dict): Current vital sign values.
        patient_name (str): Patient name for alert messages.

    Returns:
        list: List of generated alerts.
    """
    generated_alerts = []

    checks = [
        ('heart_rate', 'Heart Rate', 'bpm'),
        ('blood_pressure_sys', 'Systolic BP', 'mmHg'),
        ('respiratory_rate', 'Respiratory Rate', 'breaths/min'),
        ('temperature', 'Temperature', '°C'),
    ]

    for param, display_name, unit in checks:
        value = vitals_data.get(param)
        if value is None:
            continue

        threshold = VITAL_THRESHOLDS.get(param, {})
        alert_info = _evaluate_threshold(value, threshold, display_name, unit)

        if alert_info:
            alert_id = Alert.create(
                patient_id=patient_id,
                alert_type=alert_info['type'],
                title=f"{alert_info['type'].upper()}: {display_name} Alert — {patient_name}",
                message=alert_info['message'],
                parameter=param,
                value=value,
                threshold=alert_info['threshold_value']
            )
            alert_info['alert_id'] = alert_id
            generated_alerts.append(alert_info)

    return generated_alerts


def _evaluate_threshold(value, threshold, display_name, unit):
    """Evaluate a vital value against its threshold ranges."""
    critical_low = threshold.get('critical_low')
    critical_high = threshold.get('critical_high')
    warning_low = threshold.get('warning_low')
    warning_high = threshold.get('warning_high')

    if critical_low is not None and value < critical_low:
        return {
            'type': 'critical',
            'message': f"{display_name} critically low: {value} {unit} (threshold: {critical_low})",
            'threshold_value': critical_low
        }
    elif critical_high is not None and value > critical_high:
        return {
            'type': 'critical',
            'message': f"{display_name} critically high: {value} {unit} (threshold: {critical_high})",
            'threshold_value': critical_high
        }
    elif warning_low is not None and value < warning_low:
        return {
            'type': 'high',
            'message': f"{display_name} below normal: {value} {unit} (threshold: {warning_low})",
            'threshold_value': warning_low
        }
    elif warning_high is not None and value > warning_high:
        return {
            'type': 'high',
            'message': f"{display_name} above normal: {value} {unit} (threshold: {warning_high})",
            'threshold_value': warning_high
        }

    return None


def create_emergency_critical_alert(patient_id, total_score, condition, recommendation,
                                    patient_name='Unknown', abnormal_parameters=None, cursor=None):
    """
    Generate and persist a CRITICAL Emergency Alert for a patient when EWS indicates Critical state.
    Includes duplicate suppression: if an active unacknowledged critical alert already exists for the
    patient, duplicate alerts are not created.

    Args:
        patient_id (int): Patient identifier
        total_score (int): Computed total EWS score
        condition (str): Patient condition ("Critical")
        recommendation (str): Decision recommendation ("Keep in ICU")
        patient_name (str): Full patient name
        abnormal_parameters (list, optional): List of abnormal parameter dicts
        cursor (MySQLCursor, optional): Active transaction cursor if within a transaction

    Returns:
        int or None: Created alert_id, or None if skipped (already active)
    """
    from database.db import db
    from models.notification_model import Notification

    # 1. Check for existing active critical alert to prevent duplicate flood
    has_active = False
    if cursor:
        cursor.execute(
            """SELECT alert_id FROM alerts
               WHERE patient_id = %s AND alert_type = 'critical' AND parameter = 'ews_total' AND is_acknowledged = FALSE
               LIMIT 1""",
            (patient_id,)
        )
        has_active = bool(cursor.fetchone())
    else:
        res = db.execute_query(
            """SELECT alert_id FROM alerts
               WHERE patient_id = %s AND alert_type = 'critical' AND parameter = 'ews_total' AND is_acknowledged = FALSE
               LIMIT 1""",
            (patient_id,), fetch=True
        )
        has_active = bool(res)

    if has_active:
        return None

    # 2. Format clinical alert details
    abnormal_str = ''
    if abnormal_parameters:
        abnormal_names = [p.get('name', '') for p in abnormal_parameters if isinstance(p, dict)]
        if abnormal_names:
            abnormal_str = f" Abnormal parameters: {', '.join(abnormal_names)}."

    title = f"CRITICAL PATIENT ALERT — {patient_name}"
    message = (
        f"Critical condition detected for {patient_name}. Immediate clinical review required. "
        f"EWS Score: {total_score}. Condition: {condition}. Recommendation: {recommendation}.{abnormal_str}"
    )

    alert_id = None
    if cursor:
        cursor.execute(
            """INSERT INTO alerts (patient_id, alert_type, title, message, parameter, value, threshold)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (patient_id, 'critical', title, message, 'ews_total', total_score, 5.0)
        )
        alert_id = cursor.lastrowid
    else:
        alert_id = Alert.create(
            patient_id=patient_id,
            alert_type='critical',
            title=title,
            message=message,
            parameter='ews_total',
            value=float(total_score),
            threshold=5.0
        )

    # 3. Broadcast in-app notification to Doctors and Nurses
    try:
        Notification.broadcast_to_all_staff(
            title=f"[CRITICAL] {patient_name} Emergency Alert",
            message=message,
            notif_type='CRITICAL_VITAL',
            patient_id=patient_id,
            severity='CRITICAL'
        )
    except Exception as e:
        print(f"[ALERT ENGINE] Warning broadcasting notification: {e}")

    return alert_id


def auto_resolve_patient_critical_alerts(patient_id, cursor=None):
    """
    Auto-resolve active critical alerts when patient's vital signs improve to Stable or Moderate.
    """
    from database.db import db
    query = """UPDATE alerts SET is_acknowledged = TRUE, acknowledged_at = NOW()
               WHERE patient_id = %s AND alert_type = 'critical' AND is_acknowledged = FALSE"""
    if cursor:
        cursor.execute(query, (patient_id,))
    else:
        db.execute_query(query, (patient_id,))


def check_and_generate_prolonged_transfer_alerts(patient_id=None, waiting_period_minutes=None):
    """
    Detect patients who have been in 'READY-TO-TRANSFER' (Fit for HDU Transfer) state
    for longer than the configured transfer waiting period.
    Generates a Doctor Approval Required alert and dispatches notifications.

    Args:
        patient_id (int, optional): Specific patient ID to check, or None for all active patients.
        waiting_period_minutes (int, optional): Configured waiting period in minutes.

    Returns:
        list: List of generated prolonged transfer alerts.
    """
    from database.db import db
    from config import get_config
    from models.notification_model import Notification

    config = get_config()
    if waiting_period_minutes is None:
        waiting_period_minutes = getattr(config, 'TRANSFER_WAITING_PERIOD_MINUTES', 120)

    where_clauses = [
        "r.status IN ('pending', 'auto')",
        "(r.recommendation_text LIKE '%HDU%' OR r.to_ward = 'HDU')",
        "TIMESTAMPDIFF(MINUTE, r.created_at, NOW()) >= %s"
    ]
    params = [waiting_period_minutes]

    if patient_id:
        where_clauses.append("r.patient_id = %s")
        params.append(patient_id)

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT r.recommendation_id, r.patient_id, r.from_ward, r.to_ward, r.score,
               r.recommendation_text, r.created_at as ready_since,
               TIMESTAMPDIFF(MINUTE, r.created_at, NOW()) as minutes_waiting,
               p.name as patient_name, p.patient_code, p.ward_type, p.bed_number,
               p.assigned_doctor, p.assigned_nurse
        FROM recommendations r
        JOIN patients p ON r.patient_id = p.patient_id
        WHERE {where_sql}
        ORDER BY r.created_at ASC
    """
    prolonged_recs = db.execute_query(query, tuple(params), fetch=True) or []
    generated = []

    for rec in prolonged_recs:
        p_id = rec['patient_id']
        p_name = rec['patient_name']
        mins = rec['minutes_waiting']
        rec_id = rec['recommendation_id']

        # Check if active unacknowledged alert already exists for this prolonged transfer
        existing = db.execute_query(
            """SELECT alert_id FROM alerts
               WHERE patient_id = %s AND parameter = 'transfer_pending' AND is_acknowledged = FALSE
               LIMIT 1""",
            (p_id,), fetch=True
        )
        if existing:
            continue

        hours = mins // 60
        rem_mins = mins % 60
        time_str = f"{hours}h {rem_mins}m" if hours > 0 else f"{mins} mins"

        title = f"TRANSFER PENDING: Doctor Approval Required — {p_name}"
        message = (
            f"Patient {p_name} has remained Ready for Transfer ({rec.get('from_ward', 'ICU')} → {rec.get('to_ward', 'HDU')}) "
            f"for {time_str} (exceeding the configured {waiting_period_minutes} min threshold). "
            f"Attending Doctor review and transfer approval is required."
        )

        alert_id = Alert.create(
            patient_id=p_id,
            alert_type='high',
            title=title,
            message=message,
            parameter='transfer_pending',
            value=float(mins),
            threshold=float(waiting_period_minutes)
        )

        # Broadcast notification: Doctor (with approval action), Nurse (view-only notification)
        try:
            Notification.broadcast_to_role(
                role='doctor',
                title=f"[TRANSFER APPROVAL REQUIRED] {p_name}",
                message=message,
                notif_type='TRANSFER_READY',
                patient_id=p_id,
                severity='TRANSFER'
            )
            Notification.broadcast_to_role(
                role='nurse',
                title=f"[TRANSFER PENDING DOCTOR APPROVAL] {p_name}",
                message=f"Patient {p_name} is Ready to Transfer ({time_str}). Waiting for attending doctor approval.",
                notif_type='TRANSFER_READY',
                patient_id=p_id,
                severity='TRANSFER'
            )
        except Exception as e:
            print(f"[ALERT ENGINE] Warning broadcasting transfer notification: {e}")

        generated.append({
            'alert_id': alert_id,
            'patient_id': p_id,
            'recommendation_id': rec_id,
            'patient_name': p_name,
            'minutes_waiting': mins
        })

    return generated


def get_active_transfer_alerts_for_user(user=None, limit=20):
    """
    Fetch active ready-to-transfer recommendations and alerts scoped for user.
    Enforces role-based capabilities: can_approve is True ONLY for Doctor and Admin roles.
    """
    from database.db import db
    from config import get_config

    config = get_config()
    waiting_period_minutes = getattr(config, 'TRANSFER_WAITING_PERIOD_MINUTES', 120)

    if isinstance(user, dict):
        user_role = (user.get('role') or '').lower()
        user_id = user.get('user_id') or user.get('id')
    elif user:
        user_role = (getattr(user, 'role', '') or '').lower()
        user_id = getattr(user, 'id', None) or getattr(user, 'user_id', None)
    else:
        user_role = 'doctor'
        user_id = None

    can_approve = user_role in ('doctor', 'admin')

    where_clauses = [
        "r.status IN ('pending', 'auto')",
        "(r.recommendation_text LIKE '%HDU%' OR r.to_ward = 'HDU')"
    ]
    params = []

    if user:
        if user_role == 'attendant':
            return []
        # Doctors and Nurses see transfers for their assigned patients, unassigned patients, or hospital ward transfers
        if user_role == 'doctor' and user_id:
            where_clauses.append("(p.assigned_doctor = %s OR p.assigned_doctor IS NULL OR 1=1)")
            params.append(user_id)
        elif user_role == 'nurse' and user_id:
            where_clauses.append("(p.assigned_nurse = %s OR p.assigned_nurse IS NULL OR 1=1)")
            params.append(user_id)

    where_sql = " AND ".join(where_clauses)
    params.append(limit)

    query = f"""
        SELECT r.recommendation_id, r.patient_id, r.vital_id, r.from_ward, r.to_ward,
               r.score, r.confidence, r.recommendation_text, r.reason, r.status,
               r.created_at as ready_since,
               TIMESTAMPDIFF(MINUTE, r.created_at, NOW()) as minutes_waiting,
               p.name as patient_name, p.patient_code, p.ward_type, p.bed_number,
               p.diagnosis, p.assigned_doctor, p.assigned_nurse,
               t.transfer_id, t.status as transfer_status,
               a.alert_id, a.is_acknowledged as alert_acknowledged
        FROM recommendations r
        JOIN patients p ON r.patient_id = p.patient_id
        LEFT JOIN transfers t ON (r.recommendation_id = t.recommendation_id OR (r.patient_id = t.patient_id AND t.status = 'pending'))
        LEFT JOIN alerts a ON (r.patient_id = a.patient_id AND a.parameter = 'transfer_pending' AND a.is_acknowledged = FALSE)
        WHERE {where_sql}
        ORDER BY r.created_at DESC LIMIT %s
    """
    records = db.execute_query(query, tuple(params), fetch=True) or []

    results = []
    for r in records:
        mins = r.get('minutes_waiting', 0) or 0
        is_prolonged = mins >= waiting_period_minutes
        hours = mins // 60
        rem_mins = mins % 60
        time_str = f"{hours}h {rem_mins}m" if hours > 0 else f"{mins} mins"

        results.append({
            'recommendation_id': r['recommendation_id'],
            'transfer_id': r.get('transfer_id'),
            'alert_id': r.get('alert_id'),
            'patient_id': r['patient_id'],
            'patient_name': r['patient_name'],
            'patient_code': r.get('patient_code', f"P{r['patient_id']:03d}"),
            'from_ward': r.get('from_ward', 'ICU'),
            'to_ward': r.get('to_ward', 'HDU'),
            'score': r.get('score', 0),
            'recommendation_text': r.get('recommendation_text'),
            'ready_since': str(r.get('ready_since', '')),
            'minutes_waiting': mins,
            'waiting_formatted': time_str,
            'is_prolonged': is_prolonged,
            'severity': 'TRANSFER',
            'alert_type': 'transfer',
            'title': 'TRANSFER APPROVAL REQUIRED' if can_approve else 'READY TO TRANSFER (DOCTOR APPROVAL PENDING)',
            'message': f"Patient {r['patient_name']} is Ready to Transfer ({time_str} waiting). Doctor approval is required to proceed.",
            'can_approve': can_approve,  # Only Doctor/Admin can approve!
            'approval_status': 'pending'
        })

    return results

