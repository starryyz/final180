# config.py
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key"
    MYSQL_HOST = "localhost"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "Smarties034!"
    MYSQL_DB = "blooming_seeds"
    MYSQL_PORT = 3306
    MYSQL_UNIX_SOCKET = "/tmp/mysql.sock"

