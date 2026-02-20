import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.detector import check_quality, load_quality_history
from datetime import date

st.header("🔍 컬럼 품질 검사")

# 오늘 IDMC 실행 기록 확인
from utils.detector import get_today_rows
today_rows = get_today_rows()

if today_rows is None:
    st.warning("⚠️ 오늘 IDMC 실행 기록이 없습니다. 품질 검사를 할 수 없습니다.")
    st.info("IDMC 스케줄을 확인하거나, 수동으로 태스크를 실행해주세요.")
    st.stop()

qual = check_quality()
qh = load_quality_history()

# session에 저장
st.session_state['qual'] = qual

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("NULL 비율 변화 (최근7일 평균 → 현재)")
    table_rows = []
    for col_name, chg in qual['changes'].items():
        if chg['diff'] >= 5: icon = '🔴'
        elif chg['diff'] >= 2: icon = '🟡'
        else: icon = '🟢'
        table_rows.append({
            '상태': icon, '컬럼': col_name,
            '7일 평균': f"{chg['prev_7d_avg']}%",
            '현재': f"{chg['current_pct']}%",
            '변화': f"{chg['diff']:+.1f}%p",
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

with col_right:
    st.subheader("카테고리 분포")
    if qual['categories']:
        fig2 = go.Figure(data=[go.Pie(labels=list(qual['categories'].keys()),
                                       values=list(qual['categories'].values()), hole=0.4)])
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)

    amt = qual['amount_stats']
    ac1, ac2 = st.columns(2)
    ac1.metric("평균 주문금액", f"{amt['avg']:,.0f}원")
    ac2.metric("0원 비율", f"{amt['zero_pct']}%")

# phone_number NULL 추이
if not qh.empty:
    phone_hist = qh[qh['column_name'] == 'phone_number'].copy()
    if not phone_hist.empty:
        today_row = pd.DataFrame([{
            'run_date': str(date.today()), 'column_name': 'phone_number',
            'null_pct': qual['changes'].get('phone_number', {}).get('current_pct', 0)
        }])
        phone_hist = pd.concat([phone_hist, today_row], ignore_index=True)
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=phone_hist['run_date'], y=phone_hist['null_pct'],
                                   mode='lines+markers', name='phone_number NULL%',
                                   line=dict(color='#E74C3C', width=2)))
        fig3.update_layout(title="📱 phone_number NULL 비율 추이", height=300,
                           xaxis_title="날짜", yaxis_title="NULL %")
        st.plotly_chart(fig3, use_container_width=True)

if qual['anomalies']:
    for a in qual['anomalies']:
        st.error(f"🚨 {a['message']}")