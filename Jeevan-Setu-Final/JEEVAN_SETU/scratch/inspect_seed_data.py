import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import db

def inspect():
    users = db.execute_query('SELECT user_id, username, full_name, role FROM users ORDER BY user_id ASC LIMIT 15', fetch=True)
    print("Users:")
    for u in users:
        print(f"  {u['user_id']}: {u['username']} ({u['role']}) - {u['full_name']}")

    wards = db.execute_query('SELECT ward_id, name, ward_type, capacity FROM wards ORDER BY ward_id ASC', fetch=True)
    print("\nWards:")
    for w in wards:
        print(f"  {w['ward_id']}: {w['name']} ({w['ward_type']}) - cap: {w['capacity']}")

    beds = db.execute_query('SELECT bed_id, ward_id, bed_number, is_occupied FROM beds ORDER BY bed_id ASC LIMIT 20', fetch=True)
    print("\nBeds sample:")
    for b in beds:
        print(f"  Bed {b['bed_id']}: Ward {b['ward_id']}, Bed {b['bed_number']}, Occupied: {b['is_occupied']}")

if __name__ == '__main__':
    inspect()
