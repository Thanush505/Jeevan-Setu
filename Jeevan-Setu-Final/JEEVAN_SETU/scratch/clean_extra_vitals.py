import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import execute_query

v = execute_query("SELECT vital_id, recorded_at, heart_rate, ews_score FROM vitals WHERE patient_id = 1", fetch=True)
print("Patient 1 vitals:", v)
if len(v) > 1:
    # Keep only the original seeded vital
    execute_query("DELETE FROM vitals WHERE patient_id = 1 AND heart_rate = 118")
    print("Cleaned up extra test vitals")
v_after = execute_query("SELECT vital_id, recorded_at, heart_rate, ews_score FROM vitals WHERE patient_id = 1", fetch=True)
print("Patient 1 vitals after cleanup:", v_after)
