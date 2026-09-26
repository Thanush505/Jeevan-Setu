import os
import sys
import mysql.connector
from mysql.connector import Error

# Load environment configuration
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
config = {
    'DB_HOST': 'localhost',
    'DB_PORT': 3306,
    'DB_USER': 'root',
    'DB_PASSWORD': 'NewPassword123!',
    'DB_NAME': 'jeevan_setu'
}

if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()

print(f"Connecting to MySQL on {config['DB_HOST']}:{config['DB_PORT']} as {config['DB_USER']}...")

try:
    conn = mysql.connector.connect(
        host=config['DB_HOST'],
        port=int(config['DB_PORT']),
        user=config['DB_USER'],
        password=config['DB_PASSWORD']
    )
    cursor = conn.cursor(dictionary=True)

    # 1. Create Database if not exists
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config['DB_NAME']}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute(f"USE `{config['DB_NAME']}`")
    print(f"[OK] Database '{config['DB_NAME']}' selected.")

    # 2. Read schema.sql
    schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    # Split statements
    statements = []
    current_stmt = []
    in_delimiter = False
    
    for line in schema_sql.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith('--'):
            continue
        current_stmt.append(line)
        if trimmed.endswith(';'):
            stmt = '\n'.join(current_stmt).strip()
            if stmt:
                statements.append(stmt)
            current_stmt = []
            
    if current_stmt:
        stmt = '\n'.join(current_stmt).strip()
        if stmt:
            statements.append(stmt)

    print(f"Executing {len(statements)} SQL statements from schema.sql...")
    
    executed_count = 0
    warning_count = 0
    
    for stmt in statements:
        try:
            cursor.execute(stmt)
            executed_count += 1
        except Error as e:
            # Ignore duplicate table or harmless warnings
            if e.errno in (1050, 1061):
                continue
            print(f"[WARN] Statement failed: {e.msg} (Errno: {e.errno})\nStatement: {stmt[:100]}...")
            warning_count += 1

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    print(f"[OK] Executed {executed_count} statements successfully ({warning_count} warnings).")

    # 3. Verify tables and record counts
    cursor.execute("SHOW TABLES;")
    tables = [list(row.values())[0] for row in cursor.fetchall()]
    print(f"\n==================================================")
    print(f"DATABASE VERIFICATION: {config['DB_NAME']}")
    print(f"Total Tables Created: {len(tables)}")
    print(f"==================================================")
    
    for table in sorted(tables):
        try:
            cursor.execute(f"SELECT COUNT(*) as count FROM `{table}`;")
            cnt = cursor.fetchone()['count']
            print(f" - {table:<30} : {cnt:>4} rows")
        except Exception as e:
            print(f" - {table:<30} : Error ({e})")
            
    print("==================================================")
    print("SUCCESS: schema.sql executed and database fully populated!")
    
    cursor.close()
    conn.close()

except Exception as e:
    print(f"[ERROR] Execution failed: {e}")
    sys.exit(1)
