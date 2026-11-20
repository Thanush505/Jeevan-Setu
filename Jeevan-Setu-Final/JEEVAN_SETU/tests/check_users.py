import sys
sys.path.insert(0, 'Jeevan-Setu-Final/JEEVAN_SETU')
from database.db import db

cols = db.execute_query("DESCRIBE users", fetch=True)
for c in cols:
    print(c['Field'], c['Type'])

print("\n--- SAMPLE USERS ---")
users = db.execute_query("SELECT user_id, username, email, role FROM users LIMIT 10", fetch=True)
for u in users:
    print(u)
