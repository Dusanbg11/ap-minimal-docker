from extensions import mysql
from datetime import datetime

def log_action(actor, action, target_type, target_name, details=""):
    cur = None
    try:
        cur = mysql.connection.cursor()
        query = """
            INSERT INTO audit_logs (timestamp, actor, action, target_type, target_name, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (datetime.now(), actor, action, target_type, target_name, details))
        mysql.connection.commit()
    except Exception as e:
        print(f"[LOGGING ERROR] {e}")
    finally:
        if cur:
            cur.close()

