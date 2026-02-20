# src/demo/seed_history.py
import sqlite3
import random
from datetime import date, timedelta

DOW_VOLUME = {
    0: 4800, 1: 5100, 2: 5300,
    3: 4900, 4: 6100, 5: 7200, 6: 6800
}

conn = sqlite3.connect('guardian.db')
cur = conn.cursor()

cur.execute('''
    CREATE TABLE IF NOT EXISTS task_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        run_date TEXT NOT NULL,
        day_of_week INTEGER NOT NULL,
        rows_processed INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )
''')

cur.execute("DELETE FROM task_history WHERE task_name = 'm_ORDERS_SYNC'")
 
for i in range(30, 0, -1):
    d = date.today() - timedelta(days=i)
    dow = d.weekday()
    base = DOW_VOLUME[dow]
    rows = int(base * random.uniform(0.90, 1.18))
    
    cur.execute(
        'INSERT INTO task_history (task_name, run_date, day_of_week, rows_processed) VALUES (?,?,?,?)',
        ('m_ORDERS_SYNC', d.strftime('%Y-%m-%d'), dow, rows)
    )
    dow_name = ['월','화','수','목','금','토','일'][dow]
    print(f'  {d} ({dow_name}) → {rows:,}건')

conn.commit()
conn.close()
print('\n✅ 30일치 이력 생성 완료!')

'''

이러면 그래프가 **주중 낮고 주말 높은 물결 패턴**으로 나와서 현실적으로 보입니다. 다시 실행해보세요:
```
python src/demo/seed_history.py
streamlit run src/demo/dashboard.py
'''