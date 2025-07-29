import os
from datetime import timedelta

class Config:
    # MySQL connection parameters
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "db")  # 'db' is the Docker Compose service name
    MYSQL_USER = os.environ.get("MYSQL_USER", "admin")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "admin")
    MYSQL_DB = os.environ.get("MYSQL_DATABASE", "apminimal")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

    # Secret key for session encryption
    SECRET_KEY = os.environ.get("SECRET_KEY", "default-secret-key")  # Replace in .env for production

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # Maintenance mode flag (not used directly here, but available if needed)
    MAINTENANCE_MODE = os.environ.get("MAINTENANCE_MODE", "False") == "True"
