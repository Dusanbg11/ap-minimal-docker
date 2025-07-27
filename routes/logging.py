from extensions import mysql
from datetime import datetime

def log_action(actor_id, target_id, target_type, action):
    """
    Logs user actions into the logs table.
    
    Params:
    - actor_id (int): ID of the logged-in user making the change
    - target_id (int or None): ID of the user/server/application being changed
    - target_type (str): One of 'user', 'application', or 'server'
    - action (str): One of 'add' or 'remove'
    """
    try:
        cur = mysql.connection.cursor()

        # Insert the new log entry
        cur.execute("""
            INSERT INTO logs (actor_id, target_id, target_type, action, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (actor_id, target_id, target_type, action, datetime.now()))

        # Delete log entries older than 30 days
        cur.execute("""
            DELETE FROM logs WHERE timestamp < NOW() - INTERVAL 30 DAY
        """)

        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"[ERROR] Failed to log action: {e}")

