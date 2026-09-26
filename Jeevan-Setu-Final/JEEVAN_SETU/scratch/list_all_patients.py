import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import db

def list_all_patients():
    patients = db.execute_query('SELECT patient_id, name, patient_code, status, ward_type, bed_number, assigned_doctor, assigned_nurse FROM patients ORDER BY patient_id ASC', fetch=True)
    print(f"Total count = {len(patients)}")
    for p in patients:
        print(f"ID: {p['patient_id']} | Code: {p['patient_code']} | Name: {p['name']} | Status: {p['status']} | Ward: {p['ward_type']} | Bed: {p['bed_number']} | Doc: {p['assigned_doctor']} | Nurse: {p['assigned_nurse']}")

if __name__ == '__main__':
    list_all_patients()
