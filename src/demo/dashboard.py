# src/demo/dashboard.py - 메인 홈

import streamlit as st

st.set_page_config(page_title="Silent Failure Guardian", page_icon="🛡️", layout="wide")

st.title("🛡️ Silent Failure Guardian")
st.caption("IDMC 데이터 품질 모니터링 — ETL 성공 뒤에 숨은 문제를 AI가 잡아냅니다")

st.divider()

st.markdown("""
### 📌 메뉴 안내

왼쪽 사이드바에서 원하는 기능을 선택하세요.

| 페이지 | 설명 |
|--------|------|
| 📊 볼륨검사 | 일별 처리 건수를 과거 이력과 비교 |
| 🔍 품질검사 | 컬럼별 NULL 비율 변화 추적 |
| 🤖 AI분석 | Claude AI 종합 분석 + Slack 알림 |
| 💬 데이터질의 | 자연어로 데이터 조회 |
""")

st.divider()
st.caption("Silent Failure Guardian v2 — IDMC는 성공/실패를 알려줍니다. Guardian은 성공 뒤에 숨은 문제를 잡습니다.")