import sys
sys.path.insert(0, '.')
from database.db import db

users = db.execute_query("SELECT user_id, username, full_name, role, department FROM users", fetch=True)
for u in users:
    print(u)
