import requests, os
from dotenv import load_dotenv
load_dotenv()

login_url = f"{os.getenv('IDMC_LOGIN_URL')}/ma/api/v2/user/login"
payload = {"@type": "login", "username": os.getenv('IDMC_USERNAME'), "password": os.getenv('IDMC_PASSWORD')}
resp = requests.post(login_url, json=payload)
data = resp.json()

sid = data['icSessionId']
server_url = data['serverUrl']

logs = requests.get(f"{server_url}/api/v2/activity/activityLog", headers={"icSessionId": sid}).json()

# ORDERS 포함된 것만 찾기
print("ORDERS 관련 로그:")
for log in logs:
    name = log.get('objectName', '')
    if 'ORDER' in name.upper() or 'SYNC' in name.upper():
        print(f"  name: {name} | state: {log.get('state')} | rows: {log.get('successTargetRows')} | time: {log.get('startTime')}")
