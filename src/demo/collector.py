import requests
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def get_idmc_session():
    login_url = f"{os.getenv('IDMC_LOGIN_URL')}/ma/api/v2/user/login"
    payload = {"@type": "login", "username": os.getenv('IDMC_USERNAME'), "password": os.getenv('IDMC_PASSWORD')}
    response = requests.post(login_url, json=payload)
    data = response.json()
    return data['icSessionId'], data['serverUrl']

def fetch_and_save_logs():
    try:
        sid, server_url = get_idmc_session()
        log_url = f"{server_url}/api/v2/activity/activityLog" 
        headers = {"icSessionId": sid}
        logs = requests.get(log_url, headers=headers).json()

        conn = sqlite3.connect('guardian.db')
        cur = conn.cursor()
        
        # 1. 기존 테이블 삭제 (PK 구조를 바꾸기 위해 한 번 밀어줍니다)
        cur.execute('DROP TABLE IF EXISTS idmc_logs')
        
        # 2. 새로운 테이블 생성 (run_id와 start_time을 합쳐서 중복 방지)
        cur.execute('''
            CREATE TABLE idmc_logs (
                run_id TEXT,
                object_name TEXT,
                status TEXT,
                source_rows INTEGER,
                target_rows INTEGER,
                start_time TEXT,
                end_time TEXT,
                PRIMARY KEY (run_id, start_time)
            )
        ''')

        for log in logs:
            if 'm_ORDERS_SYNC' in log.get('objectName', ''):
                # 진짜 이름표(successTargetRows) 사용 [cite: 471-480]
                t_rows = log.get('successTargetRows', 0)
                
                cur.execute('''
                    INSERT OR IGNORE INTO idmc_logs VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    log.get('runId'), log.get('objectName'), str(log.get('state')),
                    log.get('successSourceRows', 0), t_rows,
                    log.get('startTime'), log.get('endTime')
                ))
        
        conn.commit()
        conn.close()
        print("\n✅ SQLite 수첩 정리 완료!.")

    except Exception as e:
        print(f"🚨 오류: {e}")

if __name__ == "__main__":
    fetch_and_save_logs()