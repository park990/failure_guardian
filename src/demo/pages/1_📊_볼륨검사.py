import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.detector import load_volume_history, get_today_rows, check_volume
from datetime import date

st.header("📊 볼륨 검사")

df = load_volume_history()
today_rows = get_today_rows()
vol = check_volume(today_rows, df)

# session에 저장 (AI분석 페이지에서 사용)
st.session_state['vol'] = vol

if vol.get('no_data'):
    st.warning("⚠️ 오늘 IDMC 실행 기록이 없습니다. 스케줄러를 확인하세요.")

elif today_rows and not df.empty:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("금일 처리", f"{vol['today_rows']:,}건", f"{vol['change_pct']:+.1f}%",
              delta_color="inverse" if vol['change_pct'] < 0 else "normal")
    c2.metric(f"{vol['compare']} 평균", f"{vol['mean']:,.0f}건")
    c3.metric("Z-Score", f"{vol['z_score']:.2f}")
    if vol['severity'] == 'critical': c4.error("🔴 CRITICAL")
    elif vol['severity'] == 'warning': c4.warning("🟡 WARNING")
    else: c4.success("🟢 NORMAL")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['run_date'], y=df['rows_processed'],
                              mode='lines+markers', name='처리건수',
                              line=dict(color='#2674B8', width=2)))
    fig.add_hline(y=vol['mean'], line_dash="dash", line_color="green", annotation_text=f"평균: {vol['mean']:,.0f}")
    fig.add_hline(y=vol['mean'] - 2 * vol['std'], line_dash="dot", line_color="red", annotation_text="하한(2σ)")
    fig.add_hline(y=vol['mean'] + 2 * vol['std'], line_dash="dot", line_color="red", annotation_text="상한(2σ)")
    fig.add_trace(go.Scatter(x=[str(date.today())], y=[today_rows], mode='markers', name='오늘',
                              marker=dict(size=14, color='red' if vol['severity'] != 'normal' else 'green', symbol='star')))
    fig.update_layout(title="일별 처리 건수 추이", height=400, xaxis_title="날짜", yaxis_title="건수")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터 없음. collector를 먼저 실행하세요.")