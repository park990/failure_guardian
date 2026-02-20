# utils/detector.py - 볼륨/품질 검사 로직

import numpy as np
import pandas as pd
import json
import decimal
from datetime import date
from utils.db import get_sqlite, get_mysql
from datetime import date, timedelta

TASK_NAME = 'm_ORDERS_SYNC'


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


def load_volume_history():
    """볼륨 이력 로드"""
    conn = get_sqlite()
    df = pd.read_sql("""
        SELECT run_date, day_of_week, rows_processed 
        FROM task_history WHERE task_name = ? ORDER BY run_date
    """, conn, params=(TASK_NAME,))
    conn.close()
    return df


def get_today_rows():
    """오늘 동기화된 데이터 건수"""
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders_analytics WHERE order_date = CURDATE()")
    total = cur.fetchone()[0]
    conn.close()
    return total if total > 0 else None


def check_volume(today_rows, df):
    """볼륨 이상 판단"""
    if today_rows is None:
        return {'severity': 'no_data', 'is_anomaly': False, 'today_rows': 0,
                'mean': 0, 'std': 0, 'z_score': 0, 'change_pct': 0,
                'compare': '', 'day_name': '', 'no_data': True}
    if df.empty:
        return {'severity': 'normal', 'is_anomaly': False, 'today_rows': today_rows,
                'mean': 0, 'std': 0, 'z_score': 0, 'change_pct': 0,
                'compare': '', 'day_name': ''}

    dow = date.today().weekday()
    dow_name = ['월','화','수','목','금','토','일'][dow]
    same_dow = df[df['day_of_week'] == dow]['rows_processed'].values
    history = same_dow if len(same_dow) >= 3 else df['rows_processed'].values
    compare = f'{dow_name}요일' if len(same_dow) >= 3 else '전체'

    mean = float(np.mean(history))
    std = float(np.std(history))
    if std < 1: std = max(mean * 0.1, 1)
    z = (today_rows - mean) / std
    pct = (today_rows - mean) / mean * 100
    severity = 'critical' if abs(z) >= 3 else 'warning' if abs(z) >= 2 else 'normal'

    return {
        'today_rows': today_rows, 'compare': compare, 'day_name': dow_name,
        'mean': round(mean, 1), 'std': round(std, 1), 'z_score': round(z, 2),
        'change_pct': round(pct, 1), 'severity': severity, 'is_anomaly': abs(z) >= 2,
    }


def load_quality_history():
    """품질 이력 로드"""
    conn = get_sqlite()
    df = pd.read_sql("""
        SELECT run_date, column_name, null_pct 
        FROM quality_history ORDER BY run_date
    """, conn)
    conn.close()
    return df


def check_quality():
    """컬럼 품질 검사 + 이력 비교"""
    conn = get_mysql()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT COUNT(*) as cnt FROM orders_analytics")
    total = cur.fetchone()['cnt']

    null_checks = {}
    for col in ['phone_number', 'email', 'customer_name', 'total_amount', 'product_code', 'category']:
        cur.execute(f"SELECT SUM(CASE WHEN {col} IS NULL OR {col} = '' THEN 1 ELSE 0 END) as n FROM orders_analytics")
        n = int(cur.fetchone()['n'] or 0)
        null_checks[col] = {'null_count': n, 'null_pct': round(n / total * 100, 1) if total > 0 else 0}

    cur.execute("""
        SELECT SUM(CASE WHEN total_amount=0 THEN 1 ELSE 0 END) as z,
               AVG(total_amount) as a, MIN(total_amount) as mi, MAX(total_amount) as ma
        FROM orders_analytics
    """)
    amt = cur.fetchone()

    cur.execute("SELECT category, COUNT(*) as cnt FROM orders_analytics GROUP BY category ORDER BY cnt DESC")
    cats = {str(r['category']): int(r['cnt']) for r in cur.fetchall()}
    conn.close()

    zero_pct = round(float(amt['z'] or 0) / total * 100, 1) if total > 0 else 0

    # 과거 7일 평균과 비교
    conn_sq = get_sqlite()
    cur_sq = conn_sq.cursor()
    changes = {}
    anomalies = []
    for col, info in null_checks.items():
        cur_sq.execute("SELECT AVG(null_pct) FROM quality_history WHERE column_name=? ORDER BY run_date DESC LIMIT 7", (col,))
        row = cur_sq.fetchone()
        prev = round(row[0], 2) if row and row[0] else 0.0
        diff = round(info['null_pct'] - prev, 1)
        growth_rate = (info['null_pct'] - prev) / prev if prev > 0 else info['null_pct']
        changes[col] = {'current_pct': info['null_pct'], 'prev_7d_avg': prev, 'diff': diff}

        if (prev == 0 and info['null_pct'] > 0.1) or (prev > 0 and growth_rate >= 1.0) or (diff >= 5.0):
            anomalies.append({
                'column': col, 'current_pct': info['null_pct'],
                'prev_avg': prev, 'diff': diff,
                'message': f"🚨 {col} 이상 감지: 이전 대비 {growth_rate*100:.0f}% 급증! ({prev}% → {info['null_pct']}%)"
            })
    conn_sq.close()

    if zero_pct > 5:
        anomalies.append({'column': 'total_amount', 'zero_pct': zero_pct,
                          'message': f"total_amount 0원 비율 {zero_pct}%"})

    return {
        'total_rows': total, 'null_checks': null_checks, 'changes': changes,
        'amount_stats': {'avg': float(amt['a'] or 0), 'min': float(amt['mi'] or 0),
                         'max': float(amt['ma'] or 0), 'zero_pct': zero_pct},
        'categories': cats, 'anomalies': anomalies, 'is_anomaly': len(anomalies) > 0,
    }