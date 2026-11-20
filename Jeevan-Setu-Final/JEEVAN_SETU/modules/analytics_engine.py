"""
modules/analytics_engine.py — Comprehensive Analytics Engine for Jeevan Setu.

Calculates:
1. Occupancy Analytics (Hospital-wide, ICU occupancy, HDU occupancy, General Ward, Available beds)
2. Transfer Analytics (Volume, status distribution, ward transitions, turnaround time, reasons)
3. Resource Utilization (Utilization index, maintenance impact, high-occupancy ward alerts)
4. Patient Statistics (Active vs discharged, ward distribution, gender, age cohorts, diagnoses)
5. EWS Statistics (Longitudinal risk distribution, average EWS by ward, critical alert patients)
"""

from datetime import datetime
from database.db import db
from models.ward_model import Ward
from models.bed_model import Bed


class AnalyticsEngine:
    """Core analytics calculation engine for clinical and operational hospital intelligence."""

    @staticmethod
    def get_occupancy_analytics():
        """
        Calculate hospital-wide, ICU, HDU, and ward-level bed occupancy metrics.
        """
        wards = Ward.get_all() or []
        all_beds = Bed.get_all() or []

        total_beds = len(all_beds)
        occupied_beds = sum(1 for b in all_beds if b.get('status') == 'occupied')
        available_beds = sum(1 for b in all_beds if b.get('status') == 'available')
        maintenance_beds = sum(1 for b in all_beds if b.get('status') == 'maintenance')
        overall_occupancy_pct = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

        # Helper for ward_type metrics
        def _calc_ward_type_metrics(ward_type_name):
            type_ward_ids = {w['ward_id'] for w in wards if str(w.get('ward_type', '')).upper() == ward_type_name.upper()}
            type_beds = [b for b in all_beds if b.get('ward_id') in type_ward_ids]
            t_total = len(type_beds)
            t_occ = sum(1 for b in type_beds if b.get('status') == 'occupied')
            t_avail = sum(1 for b in type_beds if b.get('status') == 'available')
            t_maint = sum(1 for b in type_beds if b.get('status') == 'maintenance')
            t_rate = round((t_occ / t_total * 100), 1) if t_total > 0 else 0.0
            return {
                'total_beds': t_total,
                'occupied_beds': t_occ,
                'available_beds': t_avail,
                'maintenance_beds': t_maint,
                'occupancy_rate_pct': t_rate
            }

        icu_metrics = _calc_ward_type_metrics('ICU')
        hdu_metrics = _calc_ward_type_metrics('HDU')
        general_metrics = _calc_ward_type_metrics('General')

        ward_breakdown = []
        for w in wards:
            w_id = w['ward_id']
            w_beds = [b for b in all_beds if b.get('ward_id') == w_id]
            w_total = len(w_beds)
            w_occ = sum(1 for b in w_beds if b.get('status') == 'occupied')
            w_avail = sum(1 for b in w_beds if b.get('status') == 'available')
            w_maint = sum(1 for b in w_beds if b.get('status') == 'maintenance')
            w_rate = round((w_occ / w_total * 100), 1) if w_total > 0 else 0.0

            ward_breakdown.append({
                'ward_id': w_id,
                'ward_name': w['name'],
                'ward_type': w['ward_type'],
                'floor_number': w.get('floor_number', 1),
                'total_beds': w_total,
                'occupied_beds': w_occ,
                'available_beds': w_avail,
                'maintenance_beds': w_maint,
                'occupancy_rate_pct': w_rate
            })

        return {
            'timestamp': datetime.now().isoformat(),
            'hospital_summary': {
                'total_wards': len(wards),
                'total_beds': total_beds,
                'occupied_beds': occupied_beds,
                'available_beds': available_beds,
                'maintenance_beds': maintenance_beds,
                'overall_occupancy_rate_pct': overall_occupancy_pct
            },
            'icu_occupancy': icu_metrics,
            'hdu_occupancy': hdu_metrics,
            'general_occupancy': general_metrics,
            'ward_breakdown': ward_breakdown
        }

    @staticmethod
    def get_transfer_analytics():
        """
        Calculate patient transfer metrics, flow transitions, approval statuses, and turnaround time.
        """
        query = """
            SELECT t.*, p.name AS patient_name, p.patient_code
            FROM transfers t
            JOIN patients p ON t.patient_id = p.patient_id
            ORDER BY t.created_at DESC
        """
        transfers = db.execute_query(query, fetch=True) or []

        total_transfers = len(transfers)
        status_counts = {
            'completed': sum(1 for t in transfers if t.get('status') == 'completed'),
            'approved': sum(1 for t in transfers if t.get('status') == 'approved'),
            'pending': sum(1 for t in transfers if t.get('status') == 'pending'),
            'rejected': sum(1 for t in transfers if t.get('status') == 'rejected'),
            'cancelled': sum(1 for t in transfers if t.get('status') == 'cancelled')
        }

        # Transitions flow matrix (e.g. ICU -> HDU, HDU -> ICU)
        flows = {}
        for t in transfers:
            fw = t.get('from_ward', 'Unknown')
            tw = t.get('to_ward', 'Unknown')
            route = f"{fw} -> {tw}"
            flows[route] = flows.get(route, 0) + 1

        # Reasons breakdown
        reasons_map = {}
        for t in transfers:
            reason = (t.get('transfer_reason') or 'Clinical recommendation').strip()
            reasons_map[reason] = reasons_map.get(reason, 0) + 1

        top_reasons = sorted([{'reason': k, 'count': v} for k, v in reasons_map.items()], key=lambda x: x['count'], reverse=True)[:5]

        # Calculate average turnaround time for completed transfers
        completion_durations = []
        for t in transfers:
            if t.get('status') == 'completed' and t.get('completed_at') and t.get('requested_at'):
                try:
                    c_time = t['completed_at']
                    r_time = t['requested_at']
                    if isinstance(c_time, str):
                        c_time = datetime.fromisoformat(c_time)
                    if isinstance(r_time, str):
                        r_time = datetime.fromisoformat(r_time)
                    delta_hours = (c_time - r_time).total_seconds() / 3600.0
                    if delta_hours >= 0:
                        completion_durations.append(delta_hours)
                except Exception:
                    pass

        avg_turnaround_hours = round(sum(completion_durations) / len(completion_durations), 1) if completion_durations else 1.5

        return {
            'timestamp': datetime.now().isoformat(),
            'total_transfers': total_transfers,
            'status_distribution': status_counts,
            'transition_flows': flows,
            'top_transfer_reasons': top_reasons,
            'average_turnaround_hours': avg_turnaround_hours,
            'completion_rate_pct': round((status_counts['completed'] / total_transfers * 100), 1) if total_transfers > 0 else 0.0
        }

    @staticmethod
    def get_resource_utilization_analytics():
        """
        Calculate hospital resource utilization indexes, maintenance impact, and capacity flags.
        """
        occ = AnalyticsEngine.get_occupancy_analytics()
        hs = occ['hospital_summary']
        icu = occ['icu_occupancy']
        hdu = occ['hdu_occupancy']

        total_critical_beds = icu['total_beds'] + hdu['total_beds']
        occupied_critical_beds = icu['occupied_beds'] + hdu['occupied_beds']
        available_critical_beds = icu['available_beds'] + hdu['available_beds']
        critical_utilization_pct = round((occupied_critical_beds / total_critical_beds * 100), 1) if total_critical_beds > 0 else 0.0

        maintenance_impact_pct = round((hs['maintenance_beds'] / hs['total_beds'] * 100), 1) if hs['total_beds'] > 0 else 0.0

        # Wards requiring immediate attention (>85% occupancy)
        high_occupancy_wards = [
            w for w in occ['ward_breakdown'] if w['occupancy_rate_pct'] >= 85.0
        ]
        available_wards = [
            w for w in occ['ward_breakdown'] if w['available_beds'] > 0
        ]

        return {
            'timestamp': datetime.now().isoformat(),
            'overall_utilization_rate_pct': hs['overall_occupancy_rate_pct'],
            'critical_care_utilization_pct': critical_utilization_pct,
            'total_beds': hs['total_beds'],
            'occupied_beds': hs['occupied_beds'],
            'available_beds': hs['available_beds'],
            'available_critical_beds': available_critical_beds,
            'maintenance_beds': hs['maintenance_beds'],
            'maintenance_impact_pct': maintenance_impact_pct,
            'high_occupancy_alerts_count': len(high_occupancy_wards),
            'high_occupancy_wards': high_occupancy_wards,
            'available_wards_count': len(available_wards)
        }

    @staticmethod
    def get_patient_statistics_analytics():
        """
        Calculate patient demographics, ward distributions, status distribution, and diagnoses.
        """
        patients = db.execute_query("SELECT * FROM patients", fetch=True) or []
        total_patients = len(patients)

        status_dist = {
            'admitted': sum(1 for p in patients if p.get('status') == 'admitted'),
            'discharged': sum(1 for p in patients if p.get('status') == 'discharged'),
            'transferred': sum(1 for p in patients if p.get('status') == 'transferred'),
            'deceased': sum(1 for p in patients if p.get('status') == 'deceased')
        }

        # Active admitted patients ward distribution
        active_patients = [p for p in patients if p.get('status') == 'admitted']
        ward_dist = {
            'ICU': sum(1 for p in active_patients if str(p.get('ward_type', '')).upper() == 'ICU'),
            'HDU': sum(1 for p in active_patients if str(p.get('ward_type', '')).upper() == 'HDU'),
            'General': sum(1 for p in active_patients if str(p.get('ward_type', '')).upper() == 'GENERAL')
        }

        # Gender distribution
        gender_dist = {
            'male': sum(1 for p in patients if str(p.get('gender', '')).lower() == 'male'),
            'female': sum(1 for p in patients if str(p.get('gender', '')).lower() == 'female'),
            'other': sum(1 for p in patients if str(p.get('gender', '')).lower() not in ('male', 'female'))
        }

        # Age distribution
        ages = [p['age'] for p in patients if p.get('age') is not None]
        avg_age = round(sum(ages) / len(ages), 1) if ages else 0.0
        age_cohorts = {
            'pediatric_under_18': sum(1 for a in ages if a < 18),
            'young_adult_18_40': sum(1 for a in ages if 18 <= a <= 40),
            'middle_aged_41_65': sum(1 for a in ages if 41 <= a <= 65),
            'senior_above_65': sum(1 for a in ages if a > 65)
        }

        # Diagnoses breakdown
        diag_counts = {}
        for p in patients:
            diag = (p.get('diagnosis') or 'Unspecified').strip()
            diag_counts[diag] = diag_counts.get(diag, 0) + 1

        top_diagnoses = sorted([{'diagnosis': k, 'count': v} for k, v in diag_counts.items()], key=lambda x: x['count'], reverse=True)[:5]

        return {
            'timestamp': datetime.now().isoformat(),
            'total_registered_patients': total_patients,
            'active_admitted_patients': len(active_patients),
            'status_distribution': status_dist,
            'active_ward_distribution': ward_dist,
            'gender_distribution': gender_dist,
            'average_age': avg_age,
            'age_cohorts': age_cohorts,
            'top_admission_diagnoses': top_diagnoses
        }

    @staticmethod
    def get_ews_statistics_analytics(time_range='7d', start_date=None, end_date=None, ward_filter=None):
        """
        Calculate Early Warning Score risk distributions, ward score averages,
        trends, clinical escalations, response times, and high-risk patient table.
        Uses only real database records and existing EWS thresholds.
        """
        from datetime import timedelta
        import statistics

        now = datetime.now()
        tr = (time_range or '7d').strip().lower()
        start_dt = None
        end_dt = now

        if tr == '24h':
            start_dt = now - timedelta(hours=24)
        elif tr == '30d':
            start_dt = now - timedelta(days=30)
        elif tr == 'custom' and start_date and end_date:
            try:
                start_dt = datetime.fromisoformat(str(start_date).strip()[:10] + ' 00:00:00')
                end_dt = datetime.fromisoformat(str(end_date).strip()[:10] + ' 23:59:59')
            except ValueError:
                start_dt = now - timedelta(days=7)
        else:
            tr = '7d'
            start_dt = now - timedelta(days=7)

        # Fetch active wards dynamically
        wards_rows = db.execute_query(
            "SELECT ward_id, name, ward_type, floor_number FROM wards WHERE is_active = TRUE ORDER BY ward_type, name",
            fetch=True
        ) or []

        ward_clause = ""
        ward_params = []
        wf = (ward_filter or '').strip()
        if wf and wf.lower() != 'all':
            if wf.isdigit():
                ward_clause = " AND p.ward_id = %s "
                ward_params.append(int(wf))
            elif wf.upper() in ('ICU', 'HDU', 'GENERAL'):
                ward_clause = " AND UPPER(p.ward_type) = %s "
                ward_params.append(wf.upper())
            else:
                ward_clause = " AND (w.name = %s OR p.ward_type = %s) "
                ward_params.extend([wf, wf])

        # 1. Latest EWS score per admitted patient (filtered by ward)
        query = f"""
            SELECT p.patient_id, p.patient_code, p.name AS patient_name, p.ward_id, p.ward_type,
                   COALESCE(w.name, p.ward_type) AS ward_name, p.bed_number,
                   e.total_score, e.risk_level, e.hr_score, e.bp_score, e.rr_score, e.temp_score,
                   e.calculated_at
            FROM patients p
            LEFT JOIN wards w ON p.ward_id = w.ward_id
            LEFT JOIN (
                SELECT e1.*
                FROM ews_scores e1
                INNER JOIN (
                    SELECT patient_id, MAX(ews_id) AS max_id
                    FROM ews_scores GROUP BY patient_id
                ) latest ON e1.ews_id = latest.max_id
            ) e ON p.patient_id = e.patient_id
            WHERE p.status = 'admitted' {ward_clause}
        """
        records = db.execute_query(query, tuple(ward_params) if ward_params else None, fetch=True) or []

        risk_counts = {
            'NORMAL': 0,   # Score 0
            'LOW': 0,      # Score 1-2
            'MEDIUM': 0,   # Score 3-4
            'HIGH': 0,     # Score 5-6
            'CRITICAL': 0  # Score >= 7
        }

        all_scores = []
        icu_scores = []
        hdu_scores = []
        general_scores = []
        critical_alert_patients = []
        acuity_map = {}

        param_contributors = {
            'heart_rate': 0,
            'blood_pressure': 0,
            'respiratory_rate': 0,
            'temperature': 0
        }

        # Unacknowledged alerts per patient
        unacked_rows = db.execute_query(
            "SELECT patient_id, COUNT(*) AS cnt FROM alerts WHERE is_acknowledged = FALSE AND is_dismissed = FALSE GROUP BY patient_id",
            fetch=True
        ) or []
        unacked_by_patient = {r['patient_id']: int(r['cnt']) for r in unacked_rows}

        high_risk_table = []

        for r in records:
            score = r.get('total_score') if r.get('total_score') is not None else 0
            all_scores.append(score)

            # Classify risk using existing authoritative thresholds
            if score == 0:
                risk_cat = 'NORMAL'
            elif score <= 2:
                risk_cat = 'LOW'
            elif score <= 4:
                risk_cat = 'MEDIUM'
            elif score <= 6:
                risk_cat = 'HIGH'
            else:
                risk_cat = 'CRITICAL'

            risk_counts[risk_cat] += 1

            w_type = str(r.get('ward_type') or 'General').upper()
            w_name = r.get('ward_name') or w_type
            if w_name not in acuity_map:
                acuity_map[w_name] = {'ward_name': w_name, 'ward_type': w_type, 'low': 0, 'moderate': 0, 'high': 0, 'total': 0}
            acuity_map[w_name]['total'] += 1
            if score <= 2:
                acuity_map[w_name]['low'] += 1
            elif score <= 4:
                acuity_map[w_name]['moderate'] += 1
            else:
                acuity_map[w_name]['high'] += 1

            if risk_cat == 'CRITICAL':
                critical_alert_patients.append({
                    'patient_id': r['patient_id'],
                    'patient_name': r['patient_name'],
                    'ward_type': r['ward_type'],
                    'bed_number': r.get('bed_number', 'N/A'),
                    'ews_score': score,
                    'risk_level': 'CRITICAL'
                })

            unacked_cnt = unacked_by_patient.get(r['patient_id'], 0)
            if score >= 5 or unacked_cnt > 0:
                calc_at = r.get('calculated_at')
                high_risk_table.append({
                    'patient_id': r['patient_id'],
                    'patient_code': r.get('patient_code') or f"PT-{r['patient_id']}",
                    'patient_name': r.get('patient_name') or 'Unknown',
                    'ward_name': w_name,
                    'ward_type': w_type,
                    'bed_number': r.get('bed_number') or 'N/A',
                    'ews_score': score,
                    'risk_category': risk_cat,
                    'calculated_at': calc_at.isoformat() if hasattr(calc_at, 'isoformat') else (str(calc_at) if calc_at else None),
                    'unacked_alerts': unacked_cnt,
                })

            if w_type == 'ICU':
                icu_scores.append(score)
            elif w_type == 'HDU':
                hdu_scores.append(score)
            else:
                general_scores.append(score)

            if (r.get('hr_score') or 0) > 0:
                param_contributors['heart_rate'] += r.get('hr_score', 0)
            if (r.get('bp_score') or 0) > 0:
                param_contributors['blood_pressure'] += r.get('bp_score', 0)
            if (r.get('rr_score') or 0) > 0:
                param_contributors['respiratory_rate'] += r.get('rr_score', 0)
            if (r.get('temp_score') or 0) > 0:
                param_contributors['temperature'] += r.get('temp_score', 0)

        hospital_avg_ews = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
        icu_avg_ews = round(sum(icu_scores) / len(icu_scores), 1) if icu_scores else 0.0
        hdu_avg_ews = round(sum(hdu_scores) / len(hdu_scores), 1) if hdu_scores else 0.0
        general_avg_ews = round(sum(general_scores) / len(general_scores), 1) if general_scores else 0.0

        # 2. Historical EWS Trends in selected range
        bucket_fmt = '%Y-%m-%d %H:00' if tr == '24h' else '%Y-%m-%d'
        trend_sql = f"""
            SELECT DATE_FORMAT(e.calculated_at, %s) AS bucket,
                   UPPER(COALESCE(p.ward_type, 'GENERAL')) AS ward_type,
                   ROUND(AVG(e.total_score), 2) AS avg_score,
                   COUNT(*) AS sample_count
            FROM ews_scores e
            JOIN patients p ON e.patient_id = p.patient_id
            LEFT JOIN wards w ON p.ward_id = w.ward_id
            WHERE e.calculated_at BETWEEN %s AND %s {ward_clause}
            GROUP BY bucket, UPPER(COALESCE(p.ward_type, 'GENERAL'))
            ORDER BY bucket ASC
        """
        trend_params = [bucket_fmt, start_dt.strftime('%Y-%m-%d %H:%M:%S'), end_dt.strftime('%Y-%m-%d %H:%M:%S')] + ward_params
        trend_rows = db.execute_query(trend_sql, tuple(trend_params), fetch=True) or []

        buckets = sorted({r['bucket'] for r in trend_rows if r.get('bucket')})
        series_map = {'ICU': {}, 'HDU': {}, 'GENERAL': {}}
        for r in trend_rows:
            wt = r.get('ward_type', 'GENERAL')
            if wt not in series_map:
                wt = 'GENERAL'
            series_map[wt][r['bucket']] = float(r['avg_score']) if r.get('avg_score') is not None else None

        ews_trends = {
            'labels': buckets,
            'series': {
                'ICU': [series_map['ICU'].get(b) for b in buckets],
                'HDU': [series_map['HDU'].get(b) for b in buckets],
                'General': [series_map['GENERAL'].get(b) for b in buckets],
            }
        }

        # 3. Clinical Escalations & Response Times (from alerts + decisions in range)
        alert_sql = f"""
            SELECT a.alert_id, a.alert_type, a.created_at, a.acknowledged_at, a.is_acknowledged,
                   UPPER(COALESCE(p.ward_type, 'GENERAL')) AS ward_type,
                   TIMESTAMPDIFF(SECOND, a.created_at, a.acknowledged_at) AS ack_seconds
            FROM alerts a
            JOIN patients p ON a.patient_id = p.patient_id
            LEFT JOIN wards w ON p.ward_id = w.ward_id
            WHERE a.created_at BETWEEN %s AND %s {ward_clause}
        """
        alert_params = [start_dt.strftime('%Y-%m-%d %H:%M:%S'), end_dt.strftime('%Y-%m-%d %H:%M:%S')] + ward_params
        alert_rows = db.execute_query(alert_sql, tuple(alert_params), fetch=True) or []

        dec_sql = f"""
            SELECT d.decision_id, d.recommendation, d.status, d.to_ward, d.created_at, d.decided_at,
                   UPPER(COALESCE(p.ward_type, 'GENERAL')) AS ward_type,
                   TIMESTAMPDIFF(SECOND, d.created_at, d.decided_at) AS dec_seconds
            FROM decisions d
            JOIN patients p ON d.patient_id = p.patient_id
            LEFT JOIN wards w ON p.ward_id = w.ward_id
            WHERE d.created_at BETWEEN %s AND %s {ward_clause}
        """
        dec_rows = db.execute_query(dec_sql, tuple(alert_params), fetch=True) or []

        ack_minutes = [
            round(r['ack_seconds'] / 60.0, 1)
            for r in alert_rows
            if r.get('acknowledged_at') is not None and r.get('ack_seconds') is not None and r['ack_seconds'] >= 0
        ]
        dec_minutes = [
            round(r['dec_seconds'] / 60.0, 1)
            for r in dec_rows
            if r.get('decided_at') is not None and r.get('dec_seconds') is not None and r['dec_seconds'] >= 0
        ]

        ward_ack = {'ICU': [], 'HDU': [], 'GENERAL': []}
        alert_by_type = {}
        alert_by_ward = {'ICU': 0, 'HDU': 0, 'GENERAL': 0}
        for r in alert_rows:
            at = r.get('alert_type') or 'clinical_alert'
            alert_by_type[at] = alert_by_type.get(at, 0) + 1
            wt = r.get('ward_type') or 'GENERAL'
            if wt not in alert_by_ward:
                wt = 'GENERAL'
            alert_by_ward[wt] += 1
            if r.get('acknowledged_at') is not None and r.get('ack_seconds') is not None and r['ack_seconds'] >= 0:
                ward_ack[wt].append(r['ack_seconds'] / 60.0)

        icu_transfer_escalations = sum(
            1 for d in dec_rows
            if 'icu' in str(d.get('to_ward') or '').lower() or 'icu' in str(d.get('recommendation') or '').lower()
        )
        physician_reviews = sum(1 for d in dec_rows if d.get('decided_at') is not None)

        high_risk_count = risk_counts['HIGH'] + risk_counts['CRITICAL']
        total_escalations = len(alert_rows) + len(dec_rows)
        avg_ack_min = round(sum(ack_minutes) / len(ack_minutes), 1) if ack_minutes else None
        med_ack_min = round(statistics.median(ack_minutes), 1) if ack_minutes else None
        avg_dec_min = round(sum(dec_minutes) / len(dec_minutes), 1) if dec_minutes else None
        med_dec_min = round(statistics.median(dec_minutes), 1) if dec_minutes else None

        return {
            'timestamp': now.isoformat(),
            'filters': {
                'range': tr,
                'start_date': start_dt.strftime('%Y-%m-%d'),
                'end_date': end_dt.strftime('%Y-%m-%d'),
                'ward': wf or 'all',
            },
            'wards': wards_rows,
            'total_evaluated_patients': len(records),
            'risk_distribution': risk_counts,
            'hospital_average_ews': hospital_avg_ews,
            'ward_average_ews': {
                'ICU': icu_avg_ews,
                'HDU': hdu_avg_ews,
                'General': general_avg_ews
            },
            'critical_patients_count': len(critical_alert_patients),
            'critical_patients': critical_alert_patients,
            'parameter_impact_breakdown': param_contributors,
            'kpis': {
                'high_risk_patients': high_risk_count,
                'critical_only_count': risk_counts['CRITICAL'],
                'high_only_count': risk_counts['HIGH'],
                'average_ews': hospital_avg_ews,
                'clinical_escalations': total_escalations,
                'alerts_count': len(alert_rows),
                'decisions_count': len(dec_rows),
                'icu_transfer_escalations': icu_transfer_escalations,
                'physician_reviews': physician_reviews,
                'avg_response_time_minutes': avg_ack_min,
                'patients_requiring_review': len(high_risk_table),
            },
            'ews_trends': ews_trends,
            'acuity_by_ward': list(acuity_map.values()),
            'escalation_analytics': {
                'total_escalations': total_escalations,
                'alerts_count': len(alert_rows),
                'decisions_count': len(dec_rows),
                'icu_transfer_escalations': icu_transfer_escalations,
                'physician_reviews': physician_reviews,
                'alerts_by_type': alert_by_type,
                'alerts_by_ward': alert_by_ward,
            },
            'response_analytics': {
                'alert_to_ack_avg_minutes': avg_ack_min,
                'alert_to_ack_median_minutes': med_ack_min,
                'alert_ack_samples': len(ack_minutes),
                'decision_avg_minutes': avg_dec_min,
                'decision_median_minutes': med_dec_min,
                'decision_samples': len(dec_minutes),
                'ward_ack_avg_minutes': {
                    'ICU': round(sum(ward_ack['ICU']) / len(ward_ack['ICU']), 1) if ward_ack['ICU'] else None,
                    'HDU': round(sum(ward_ack['HDU']) / len(ward_ack['HDU']), 1) if ward_ack['HDU'] else None,
                    'General': round(sum(ward_ack['GENERAL']) / len(ward_ack['GENERAL']), 1) if ward_ack['GENERAL'] else None,
                }
            },
            'high_risk_patients_table': sorted(high_risk_table, key=lambda x: (-x['ews_score'], x['patient_name'])),
        }
