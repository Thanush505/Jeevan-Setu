import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import execute_query

def check_db_vitals():
    print("Checking vitals count per patient in MySQL:")
    desc_ews = execute_query("DESCRIBE ews_scores", fetch=True)
    print("EWS cols:", [c['Field'] for c in desc_ews])
    desc_v = execute_query("DESCRIBE vitals", fetch=True)
    print("Vitals cols:", [c['Field'] for c in desc_v])
    patients = execute_query("SELECT * FROM patients ORDER BY patient_id", fetch=True)
    for p in patients:
        pid = p['patient_id']
        vitals = execute_query("SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at ASC", (pid,), fetch=True)
        ews_records = execute_query("SELECT * FROM ews_scores WHERE patient_id = %s ORDER BY calculated_at ASC" if 'calculated_at' in [c['Field'] for c in desc_ews] else "SELECT * FROM ews_scores WHERE patient_id = %s", (pid,), fetch=True)
        print(f"Patient {p['name']} (ID {pid}, Dr: {p.get('assigned_doctor')}): {len(vitals)} vitals, {len(ews_records)} ews_scores")
        for v in vitals:
            print(f"   V: {v.get('recorded_at')} | HR: {v.get('heart_rate')} | RR: {v.get('respiratory_rate')} | SBP: {v.get('blood_pressure_sys')} | Temp: {v.get('temperature')} | EWS: {v.get('ews_score')}")
        for v in vitals:
            print(f"   V: {v['recorded_at']} | HR: {v['heart_rate']} | RR: {v['respiratory_rate']} | SBP: {v['blood_pressure_sys']} | Temp: {v['temperature']} | EWS: {v['ews_score']}")

if __name__ == '__main__':
    check_db_vitals()
