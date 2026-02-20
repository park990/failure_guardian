# src/demo/cleanup.py
# 데모 후 불량 데이터 제거

import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv('MYSQL_HOST', 'localhost'),
    port=int(os.getenv('MYSQL_PORT', 3306)),
    database=os.getenv('MYSQL_DB', 'pjy_bitek'),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD')
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM orders_analytics WHERE phone_number IS NULL")
dirty = cur.fetchone()[0]

cur.execute("DELETE FROM orders_analytics WHERE phone_number IS NULL")
conn.commit()

cur.execute("SELECT COUNT(*) FROM orders_analytics")
remain = cur.fetchone()[0]

print(f"🧹 불량 데이터 {dirty:,}건 삭제 완료")
print(f"   남은 정상 데이터: {remain:,}건")

cur.close()
conn.close()

'''
**발표 데모 흐름:**

python src/demo/analyzer.py     → ✅ 정상
python src/demo/inject_dirty.py → 불량 500건 주입
python src/demo/analyzer.py     → 🔴 감지! AI 리포트!
python src/demo/cleanup.py      → 원상복구
'''