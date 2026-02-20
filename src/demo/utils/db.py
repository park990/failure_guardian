# utils/db.py - DB 연결 담당

import sqlite3
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# guardian.db 경로 (프로젝트 루트 기준)
GUARDIAN_DB = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'guardian.db')


def get_sqlite():
    """SQLite 연결"""
    return sqlite3.connect(GUARDIAN_DB)


def get_mysql():
    """MySQL 연결"""
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        database=os.getenv('MYSQL_DB', 'analytics'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD')
    )