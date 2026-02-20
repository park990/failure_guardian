# src/demo/daily_loader.py
# 매일 Oracle에 더미 주문 데이터 INSERT (CAI 역할)

import oracledb
import random
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# 더미 데이터 풀
CUSTOMERS = [
    (1, '김철수', '010-1234-5678', 'kim@email.com'),
    (2, '이영희', '010-2345-6789', 'lee@email.com'),
    (3, '박민수', '010-3456-7890', 'park@email.com'),
    (4, '정수진', '010-4567-8901', 'jung@email.com'),
    (5, '최동현', '010-5678-9012', 'choi@email.com'),
    (6, '한지은', '010-6789-0123', 'han@email.com'),
    (7, '윤서준', '010-7890-1234', 'yoon@email.com'),
    (8, '강미래', '010-8901-2345', 'kang@email.com'),
    (9, '조현우', '010-9012-3456', 'cho@email.com'),
    (10, '송지아', '010-0123-4567', 'song@email.com'),
    (11, '임태호', '010-1111-2222', 'lim@email.com'),
    (12, '오수빈', '010-2222-3333', 'oh@email.com'),
    (13, '배준혁', '010-3333-4444', 'bae@email.com'),
    (14, '신예린', '010-4444-5555', 'shin@email.com'),
    (15, '홍성민', '010-5555-6666', 'hong@email.com'),
    (16, '류하은', '010-6666-7777', 'ryu@email.com'),
    (17, '권도윤', '010-7777-8888', 'kwon@email.com'),
    (18, '문서현', '010-8888-9999', 'moon@email.com'),
    (19, '장우진', '010-1010-2020', 'jang@email.com'),
    (20, '황지민', '010-3030-4040', 'hwang@email.com'),
    (21, '안재현', '010-5050-6060', 'ahn@email.com'),
    (22, '전소율', '010-7070-8080', 'jeon@email.com'),
    (23, '고민석', '010-9090-1010', 'go@email.com'),
    (24, '남하린', '010-1212-3434', 'nam@email.com'),
    (25, '서진우', '010-5656-7878', 'seo@email.com'),
    (26, '양은서', '010-9898-1212', 'yang@email.com'),
    (27, '손태양', '010-3434-5656', 'son@email.com'),
    (28, '노유진', '010-7878-9090', 'noh@email.com'),
    (29, '하승준', '010-2424-3636', 'ha@email.com'),
    (30, '우채원', '010-4848-6060', 'woo@email.com'),
]

PRODUCTS = [
    ('P001', '노트북', '전자기기', 890000),
    ('P002', '무선이어폰', '전자기기', 189000),
    ('P003', '프로틴바 세트', '식품', 32000),
    ('P004', '겨울 패딩', '의류', 259000),
    ('P005', '공기청정기', '생활가전', 450000),
    ('P006', '선크림 세트', '뷰티', 48000),
    ('P007', '기계식 키보드', '전자기기', 129000),
    ('P008', '비타민 세트', '식품', 55000),
    ('P009', '운동화', '의류', 98000),
    ('P010', '로봇청소기', '생활가전', 894000),
]

STATUSES = ['COMPLETED', 'COMPLETED', 'COMPLETED', 'SHIPPED', 'PENDING', 'CANCELLED']
PAYMENTS = ['CARD', 'CARD', 'BANK', 'KAKAO_PAY', 'NAVER_PAY']

# 요일별 평균 건수 (월=0 ~ 일=6)
DOW_VOLUME = {
    0: 4800, 1: 5100, 2: 5300,
    3: 4900, 4: 6100, 5: 7200, 6: 6800
}


def generate_daily_data(target_date=None):
    """하루치 더미 데이터 생성 및 Oracle INSERT"""
    if target_date is None:
        target_date = date.today()

    dow = target_date.weekday()
    base = DOW_VOLUME[dow]
    count = int(base * random.uniform(0.90, 1.10))

    conn = oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN")
    )
    cur = conn.cursor()

    # 오늘 이미 넣은 데이터 있으면 스킵
    cur.execute("SELECT COUNT(*) FROM ORDERS WHERE order_date = :d", {'d': target_date})
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"⏭️ {target_date} 데이터 이미 {existing:,}건 존재. 스킵합니다.")
        conn.close()
        return existing

    # 현재 최대 order_id
    cur.execute("SELECT NVL(MAX(order_id), 0) FROM ORDERS")
    max_id = cur.fetchone()[0]

    inserted = 0
    for i in range(count):
        cust = random.choice(CUSTOMERS)
        prod = random.choice(PRODUCTS)
        amount = int(prod[3] * random.uniform(0.8, 1.2))

        cur.execute("""
            INSERT INTO ORDERS 
            (order_id, customer_id, customer_name, phone_number, email,
             order_date, total_amount, product_code, product_name,
             category, order_status, payment_method)
            VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12)
        """, (
            max_id + i + 1,
            cust[0], cust[1], cust[2], cust[3],
            target_date, amount,
            prod[0], prod[1], prod[2],
            random.choice(STATUSES),
            random.choice(PAYMENTS)
        ))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"✅ {target_date} ({['월','화','수','목','금','토','일'][dow]}) → {inserted:,}건 INSERT 완료")
    return inserted


if __name__ == '__main__':
    generate_daily_data()