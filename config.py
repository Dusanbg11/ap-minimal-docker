# config.py
from datetime import timedelta

class Config:
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'apadmin'
    MYSQL_PASSWORD = 'Simona15'  # koristi istu iz baze
    MYSQL_DB = 'apminimal'
    SECRET_KEY = 'Simona15'  # koristi neku jaku random šifru
    # Default session timeout — 30 minuta
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    MAINTENANCE_MODE = False
