# src/demo/seed_quality_history.py
# 과거 30일치 품질 이력 생성 (최초 1회)

import sqlite3
import random
from datetime import date, timedelta

conn = sqlite3.connect('guardian.db')
cur = conn.cursor()

cur.execute('''
    CREATE TABLE IF NOT EXISTS quality_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date TEXT NOT NULL,
        column_name TEXT NOT NULL,
        total_rows INTEGER,
        null_count INTEGER,
        null_pct REAL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )
''')

cur.execute("DELETE FROM quality_history")

# 컬럼별 "평소" NULL 비율
NORMAL_RATES = {
    'phone_number': 0.2,
    'email': 0.1,
    'customer_name': 0.0,
    'total_amount': 0.0,
    'product_code': 0.0,
    'category': 0.0,
}

for i in range(30, 0, -1):
    d = date.today() - timedelta(days=i)
    total = random.randint(4500, 7500)
    
    for col, base_pct in NORMAL_RATES.items():
        # 자연스러운 변동: ±0.1%p
        pct = max(0, base_pct + random.uniform(-0.1, 0.1))
        null_cnt = int(total * pct / 100)
        
        cur.execute(
            'INSERT INTO quality_history (run_date, column_name, total_rows, null_count, null_pct) VALUES (?,?,?,?,?)',
            (d.strftime('%Y-%m-%d'), col, total, null_cnt, round(pct, 2))
        )
    
    dow = ['월','화','수','목','금','토','일'][d.weekday()]
    print(f'  {d} ({dow}) phone_null={NORMAL_RATES["phone_number"]:.1f}%')

conn.commit()
conn.close()
print('\n✅ 30일치 품질 이력 생성 완료!')
'''
실행:
```

python src/demo/seed_quality_history.py

'''