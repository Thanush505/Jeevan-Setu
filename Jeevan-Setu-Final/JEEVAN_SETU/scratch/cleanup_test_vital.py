import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import execute_query

execute_query("DELETE FROM vitals WHERE vital_id = 147")
print("Deleted test vital 147")
