import sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import execute_query, db
from modules.scoring_engine import calculate_ews, calculate_parameter_score, get_risk_level

# Reference base timestamp (same as the existing seeded vital)
BASE_TIME = datetime(2026, 9, 25, 13, 29, 37)

# Historical telemetry definitions for all 10 patients
HISTORICAL_TELEMETRY = {
    1: [
        {"hours_ago": 48, "hr": 88.0, "sbp": 125.0, "dbp": 80.0, "rr": 18.0, "temp": 37.2, "spo2": 98.0},
        {"hours_ago": 36, "hr": 94.0, "sbp": 115.0, "dbp": 78.0, "rr": 20.0, "temp": 37.8, "spo2": 97.0},
        {"hours_ago": 24, "hr": 102.0, "sbp": 105.0, "dbp": 72.0, "rr": 22.0, "temp": 38.2, "spo2": 95.0},
        {"hours_ago": 16, "hr": 108.0, "sbp": 95.0, "dbp": 68.0, "rr": 23.0, "temp": 38.4, "spo2": 94.0},
        {"hours_ago": 8,  "hr": 112.0, "sbp": 88.0, "dbp": 64.0, "rr": 25.0, "temp": 38.4, "spo2": 93.0},
    ],
    2: [
        {"hours_ago": 40, "hr": 105.0, "sbp": 95.0, "dbp": 65.0, "rr": 22.0, "temp": 37.6, "spo2": 95.0},
        {"hours_ago": 28, "hr": 94.0, "sbp": 110.0, "dbp": 72.0, "rr": 20.0, "temp": 37.2, "spo2": 97.0},
        {"hours_ago": 16, "hr": 86.0, "sbp": 118.0, "dbp": 76.0, "rr": 18.0, "temp": 36.9, "spo2": 98.0},
        {"hours_ago": 8,  "hr": 80.0, "sbp": 120.0, "dbp": 78.0, "rr": 17.0, "temp": 36.8, "spo2": 99.0},
    ],
    3: [
        {"hours_ago": 30, "hr": 96.0, "sbp": 120.0, "dbp": 80.0, "rr": 19.0, "temp": 37.4, "spo2": 97.0},
        {"hours_ago": 20, "hr": 100.0, "sbp": 105.0, "dbp": 70.0, "rr": 21.0, "temp": 37.9, "spo2": 96.0},
        {"hours_ago": 12, "hr": 108.0, "sbp": 98.0, "dbp": 66.0, "rr": 22.0, "temp": 38.2, "spo2": 95.0},
        {"hours_ago": 4,  "hr": 104.0, "sbp": 96.0, "dbp": 65.0, "rr": 22.0, "temp": 38.3, "spo2": 95.0},
    ],
    4: [
        {"hours_ago": 48, "hr": 108.0, "sbp": 100.0, "dbp": 68.0, "rr": 23.0, "temp": 37.5, "spo2": 96.0},
        {"hours_ago": 32, "hr": 104.0, "sbp": 115.0, "dbp": 75.0, "rr": 22.0, "temp": 37.3, "spo2": 97.0},
        {"hours_ago": 18, "hr": 98.0, "sbp": 125.0, "dbp": 80.0, "rr": 22.0, "temp": 37.1, "spo2": 97.0},
    ],
    5: [
        {"hours_ago": 20, "hr": 112.0, "sbp": 100.0, "dbp": 68.0, "rr": 23.0, "temp": 38.5, "spo2": 95.0},
        {"hours_ago": 12, "hr": 106.0, "sbp": 105.0, "dbp": 70.0, "rr": 23.0, "temp": 38.3, "spo2": 96.0},
        {"hours_ago": 6,  "hr": 104.0, "sbp": 108.0, "dbp": 72.0, "rr": 22.0, "temp": 38.2, "spo2": 96.0},
    ],
    6: [
        {"hours_ago": 16, "hr": 135.0, "sbp": 68.0, "dbp": 45.0, "rr": 28.0, "temp": 35.5, "spo2": 91.0},
        {"hours_ago": 10, "hr": 128.0, "sbp": 72.0, "dbp": 48.0, "rr": 27.0, "temp": 35.7, "spo2": 93.0},
        {"hours_ago": 4,  "hr": 126.0, "sbp": 74.0, "dbp": 50.0, "rr": 26.0, "temp": 35.8, "spo2": 93.0},
    ],
    7: [
        {"hours_ago": 72, "hr": 104.0, "sbp": 145.0, "dbp": 92.0, "rr": 23.0, "temp": 37.0, "spo2": 95.0},
        {"hours_ago": 48, "hr": 92.0, "sbp": 138.0, "dbp": 88.0, "rr": 20.0, "temp": 36.8, "spo2": 97.0},
        {"hours_ago": 24, "hr": 82.0, "sbp": 132.0, "dbp": 85.0, "rr": 18.0, "temp": 36.7, "spo2": 98.0},
    ],
    8: [
        {"hours_ago": 36, "hr": 110.0, "sbp": 105.0, "dbp": 70.0, "rr": 24.0, "temp": 37.4, "spo2": 96.0},
        {"hours_ago": 24, "hr": 98.0, "sbp": 110.0, "dbp": 74.0, "rr": 20.0, "temp": 37.1, "spo2": 98.0},
        {"hours_ago": 12, "hr": 86.0, "sbp": 112.0, "dbp": 75.0, "rr": 18.0, "temp": 37.0, "spo2": 99.0},
    ],
    9: [
        {"hours_ago": 24, "hr": 98.0, "sbp": 125.0, "dbp": 80.0, "rr": 23.0, "temp": 38.2, "spo2": 95.0},
        {"hours_ago": 14, "hr": 94.0, "sbp": 128.0, "dbp": 82.0, "rr": 22.0, "temp": 37.8, "spo2": 96.0},
        {"hours_ago": 6,  "hr": 90.0, "sbp": 130.0, "dbp": 84.0, "rr": 21.0, "temp": 37.6, "spo2": 97.0},
    ],
    10: [
        {"hours_ago": 10, "hr": 84.0, "sbp": 145.0, "dbp": 90.0, "rr": 18.0, "temp": 36.8, "spo2": 98.0},
        {"hours_ago": 6,  "hr": 76.0, "sbp": 140.0, "dbp": 88.0, "rr": 16.0, "temp": 36.7, "spo2": 99.0},
    ]
}

def seed_history():
    print("Seeding rich historical clinical observations for all 10 canonical patients...")
    total_inserted = 0

    for pid, records in HISTORICAL_TELEMETRY.items():
        # Get patient's assigned nurse / doctor
        p_row = execute_query("SELECT patient_id, name, assigned_doctor, assigned_nurse FROM patients WHERE patient_id = %s", (pid,), fetch=True)
        if not p_row:
            continue
        p = p_row[0]
        recorded_by = p.get('assigned_nurse') or 5

        for r in records:
            rec_time = BASE_TIME - timedelta(hours=r["hours_ago"])
            time_str = rec_time.strftime("%Y-%m-%d %H:%M:%S")

            # Check if vital already exists at this exact timestamp
            existing = execute_query("SELECT vital_id FROM vitals WHERE patient_id = %s AND recorded_at = %s", (pid, time_str), fetch=True)
            if existing:
                continue

            # Calculate EWS
            v_dict = {
                'heart_rate': r['hr'],
                'blood_pressure_sys': r['sbp'],
                'respiratory_rate': r['rr'],
                'temperature': r['temp']
            }
            ews_calc = calculate_ews(v_dict)
            tot_score = ews_calc['total_score']
            risk = ews_calc['risk_level'].upper()
            if risk == 'NORMAL':
                risk = 'LOW'

            hr_s = ews_calc['breakdown']['heart_rate']['score']
            bp_s = ews_calc['breakdown']['blood_pressure_sys']['score']
            rr_s = ews_calc['breakdown']['respiratory_rate']['score']
            temp_s = ews_calc['breakdown']['temperature']['score']

            # Insert vital
            v_id = execute_query(
                """INSERT INTO vitals (patient_id, heart_rate, blood_pressure_sys, blood_pressure_dia,
                                      respiratory_rate, temperature, spo2, consciousness, ews_score,
                                      recorded_by, recorded_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'Alert', %s, %s, %s)""",
                (pid, r['hr'], r['sbp'], r['dbp'], r['rr'], r['temp'], r['spo2'], tot_score, recorded_by, time_str)
            )

            # Insert EWS score
            execute_query(
                """INSERT INTO ews_scores (patient_id, vital_id, total_score, risk_level,
                                          hr_score, bp_score, rr_score, temp_score, calculated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (pid, v_id, tot_score, risk, hr_s, bp_s, rr_s, temp_s, time_str)
            )
            total_inserted += 1

    print(f"Successfully seeded {total_inserted} historical observation records across all 10 patients!")

if __name__ == '__main__':
    seed_history()
