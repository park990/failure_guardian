import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.detector import load_volume_history, get_today_rows, check_volume, check_quality
from utils.ai import run_ai, send_slack

st.header("🤖 AI 종합 분석")

# 이전 페이지에서 데이터 가져오거나 새로 계산
if 'vol' not in st.session_state:
    df = load_volume_history()
    today_rows = get_today_rows()
    st.session_state['vol'] = check_volume(today_rows, df)
if 'qual' not in st.session_state:
    st.session_state['qual'] = check_quality()

vol = st.session_state['vol']
qual = st.session_state['qual']

# 현재 상태 요약
c1, c2 = st.columns(2)
with c1:
    if vol.get('no_data'): st.warning("📊 볼륨: ⚠️ 오늘 기록 없음")
    elif vol['severity'] == 'critical': st.error(f"📊 볼륨: 🔴 CRITICAL (Z={vol['z_score']})")
    elif vol['severity'] == 'warning': st.warning(f"📊 볼륨: 🟡 WARNING (Z={vol['z_score']})")
    else: st.success(f"📊 볼륨: 🟢 NORMAL (Z={vol['z_score']})")
with c2:
    if vol.get('no_data'): st.warning("🔍 품질: ⚠️ 볼륨 데이터 없어 판단 불가")
    elif qual['is_anomaly']: st.error(f"🔍 품질: 🔴 이상 {len(qual['anomalies'])}건")
    else: st.success("🔍 품질: 🟢 정상")

st.divider()

if vol.get('no_data'):
    st.warning("⚠️ 오늘 IDMC 실행 기록이 없습니다. 볼륨 검사를 할 수 없습니다.")
    st.info("IDMC 스케줄을 확인하거나, 수동으로 태스크를 실행해주세요.")
    st.stop()

if "ai_done" not in st.session_state:
    st.session_state.ai_done = False
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None
    
vol = st.session_state['vol']
qual = st.session_state['qual']

if vol.get('no_data'):
    st.warning("⚠️ 오늘 IDMC 실행 기록이 없습니다. 볼륨 검사를 할 수 없습니다.")
    st.info("IDMC 스케줄을 확인하거나, 수동으로 태스크를 실행해주세요.")
    st.stop()

if st.button("🤖 AI 분석 실행", type="primary"):
    with st.spinner("Claude AI 분석 중..."):
        try:
            ai = run_ai(vol, qual)
            st.session_state.ai_done = True
            st.session_state.ai_result = ai
            st.rerun()
        except Exception as e:
            st.error(f"AI 분석 실패: {e}")

if st.session_state.ai_done and st.session_state.ai_result:
    ai = st.session_state.ai_result

    if ai['overall_status'] == 'critical': st.error(f"🔴 CRITICAL — 확신도 {ai['confidence']*100:.0f}%")
    elif ai['overall_status'] == 'warning': st.warning(f"🟡 WARNING — 확신도 {ai['confidence']*100:.0f}%")
    else: st.success(f"🟢 NORMAL — 확신도 {ai['confidence']*100:.0f}%")

    st.subheader(f"📋 {ai['summary']}")

    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**🔎 원인 분석**")
        st.info(ai['cause_analysis'])
    with r2:
        st.markdown("**💼 비즈니스 영향**")
        st.warning(ai['business_impact'])

    st.markdown("**🔧 권장 조치**")
    for i, action in enumerate(ai['recommended_actions'], 1):
        st.markdown(f"{i}. {action}")

    if ai['overall_status'] != 'normal':
        slack_result = send_slack(vol, qual, ai)
        if slack_result == 'ok':
            st.success("📱 이상 감지! Slack 알림을 관리자에게 전송했습니다.")
        else:
            st.warning(f"Slack 발송 실패: {slack_result}")
    else:
        st.info("✅ 정상 상태이므로 Slack 알림을 전송하지 않습니다.")