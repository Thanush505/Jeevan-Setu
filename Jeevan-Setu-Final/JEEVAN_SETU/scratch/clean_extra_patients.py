import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import db

def main():
    rows = db.execute_query('SELECT patient_id, name FROM patients WHERE patient_id > 10')
    print('Extra:', rows)
    db.execute_query('DELETE FROM vitals WHERE patient_id > 10')
    db.execute_query('DELETE FROM patient_qr_tokens WHERE patient_id > 10')
    db.execute_query("DELETE FROM audit_logs WHERE entity_type='patient' AND entity_id > 10")
    db.execute_query('DELETE FROM patients WHERE patient_id > 10')
    c = db.execute_query("SELECT COUNT(*) as c FROM patients WHERE status='admitted'")[0]['c']
    print('Baseline count:', c)

if __name__ == '__main__':
    main()
