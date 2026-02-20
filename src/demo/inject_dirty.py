# src/demo/inject_dirty.py
# 발표 데모용 - 불량 데이터 주입

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

# 현재 상태 확인
cur.execute("SELECT COUNT(*) FROM orders_analytics")
before = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM orders_analytics WHERE phone_number IS NULL OR phone_number = ''")
null_before = cur.fetchone()[0]

print(f"\n--- 주입 전 상태 ---")
print(f"  총 건수: {before:,}건")
print(f"  phone_number NULL: {null_before:,}건 ({null_before/before*100:.1f}%)")

# 불량 데이터 500건 주입 (phone_number NULL 100%)
cur.execute("""
    INSERT INTO orders_analytics 
    (order_id, customer_id, customer_name, phone_number, email,
     order_date, total_amount, product_code, product_name,
     category, order_status, payment_method)
    SELECT 
        -- 현재 가장 큰 ID에 1부터 순차적으로 더함 (중복 절대 방지)
        (SELECT MAX(order_id) FROM orders_analytics t) + ROW_NUMBER() OVER (ORDER BY order_id),
        customer_id,
        customer_name,
        NULL, -- 의도적인 불량 데이터 (전화번호 누락)
        email,
        CURDATE(),
        total_amount,
        product_code,
        product_name,
        category,
        order_status,
        payment_method
    FROM orders_analytics
    WHERE order_id <= 5000
    ORDER BY RAND()
    LIMIT 50
""")
conn.commit()

# 주입 후 상태
cur.execute("SELECT COUNT(*) FROM orders_analytics")
after = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM orders_analytics WHERE phone_number IS NULL OR phone_number = ''")
null_after = cur.fetchone()[0]

print(f"\n--- 주입 후 상태 ---")
print(f"  총 건수: {after:,}건 (+{after-before}건)")
print(f"  phone_number NULL: {null_after:,}건 ({null_after/after*100:.1f}%)")
print(f"\n✅ 불량 데이터 주입 완료! 이제 analyzer.py를 실행하세요.")

cur.close()
conn.close()