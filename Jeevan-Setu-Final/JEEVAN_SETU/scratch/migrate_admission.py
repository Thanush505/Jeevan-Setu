"""
migrate_admission.py — Add assigned_nurse column to patients and seed available beds.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.db import db

# 1. Add assigned_nurse column if not exists
cols = [c['Field'] for c in db.execute_query('DESCRIBE patients', fetch=True)]
if 'assigned_nurse' not in cols:
    db.execute_query('ALTER TABLE patients ADD COLUMN assigned_nurse INT NULL, ADD CONSTRAINT fk_patients_nurse FOREIGN KEY (assigned_nurse) REFERENCES users(user_id) ON DELETE SET NULL')
    print('Added assigned_nurse column to patients table.')
else:
    print('assigned_nurse column already exists.')

# 2. Update existing patients with nurse assignments
nurse_assignments = {
    1: 5, 2: 5, 3: 5,
    4: 6, 5: 6, 6: 6,
    7: 7, 8: 7, 9: 7, 10: 7
}
for pid, nid in nurse_assignments.items():
    db.execute_query('UPDATE patients SET assigned_nurse = %s WHERE patient_id = %s', (nid, pid))
print('Updated existing patients with nurse assignments.')

# 3. Add General Ward if not exists
gw = db.execute_query("SELECT * FROM wards WHERE name = 'General Ward - C'", fetch=True)
if not gw:
    wid = db.execute_query("INSERT INTO wards (name, ward_type, floor_number, total_beds, description) VALUES ('General Ward - C', 'General', 1, 6, 'General Inpatient Ward — Wing C, Floor 1')")
    print(f'Created General Ward - C with ID: {wid}')
else:
    wid = gw[0]['ward_id']

# 4. Add available beds across wards
sample_beds = [
    (1, 'ICU-A07', 'available'),
    (1, 'ICU-A08', 'available'),
    (2, 'HDU-B05', 'available'),
    (2, 'HDU-B06', 'available'),
    (wid, 'GEN-C01', 'available'),
    (wid, 'GEN-C02', 'available'),
    (wid, 'GEN-C03', 'available'),
    (wid, 'GEN-C04', 'available'),
]
for ward_id, bed_num, status in sample_beds:
    existing = db.execute_query('SELECT * FROM beds WHERE bed_number = %s', (bed_num,), fetch=True)
    if not existing:
        db.execute_query('INSERT INTO beds (ward_id, bed_number, status) VALUES (%s, %s, %s)', (ward_id, bed_num, status))
        print(f'Added bed {bed_num} ({status})')

# Update total_beds count for wards
for w in db.execute_query('SELECT ward_id FROM wards', fetch=True):
    cnt = db.execute_query('SELECT COUNT(*) as cnt FROM beds WHERE ward_id = %s', (w['ward_id'],), fetch=True)[0]['cnt']
    db.execute_query('UPDATE wards SET total_beds = %s WHERE ward_id = %s', (cnt, w['ward_id']))

print('Migration completed successfully!')
