import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.agent import run_agent

st.header("💬 AI Agent — 데이터에게 물어보기")
st.caption("자연어로 질문하면 AI가 필요한 도구를 스스로 선택하여 답합니다. (MySQL, Oracle, IDMC 로그, Slack)")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_results" not in st.session_state:
    st.session_state.agent_results = []

# 이력 표시
for i, msg in enumerate(st.session_state.chat_history):
    if msg['role'] == 'user':
        st.chat_message("user").write(msg['content'])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg['content'])
            # 해당 결과의 사고과정 표시
            result_idx = i // 2
            if result_idx < len(st.session_state.agent_results):
                res = st.session_state.agent_results[result_idx]
                with st.expander(f"🧠 Agent 사고 과정 ({res['iterations']}단계)"):
                    for step in res['steps']:
                        if step['type'] == 'plan':
                            st.info(f"📋 **계획:** {step['content']}")
                        elif step['type'] == 'mysql':
                            st.success("🗄️ **MySQL 조회**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'idmc':
                            st.success("📡 **IDMC 로그**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'oracle':
                            st.success("🏛️ **Oracle 조회**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'quality_history':
                            st.success("📊 **품질 이력**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'self_correction':
                            st.warning(f"🔄 **SQL 자동 수정:** `{step['original'][:80]}` → `{step['fixed'][:80]}`")
                        elif step['type'] == 'analysis':
                            st.info(f"🔍 **판단:** {step['severity'].upper()}")
                        elif step['type'] == 'slack':
                            st.success(f"📱 **Slack:** {step['result']}")

user_question = st.chat_input("예: 오늘 데이터 정상인지 확인해줘")

if user_question:
    st.chat_message("user").write(user_question)
    st.session_state.chat_history.append({'role': 'user', 'content': user_question})

    with st.chat_message("assistant"):
        with st.spinner("🤖 Agent가 분석 중..."):
            try:
                result = run_agent(user_question, st.session_state.chat_history)

                st.markdown(result['answer'])

                with st.expander(f"🧠 Agent 사고 과정 ({result['iterations']}단계)"):
                    for step in result['steps']:
                        if step['type'] == 'plan':
                            st.info(f"📋 **계획:** {step['content']}")
                        elif step['type'] == 'mysql':
                            st.success("🗄️ **MySQL 조회**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'idmc':
                            st.success("📡 **IDMC 로그**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'oracle':
                            st.success("🏛️ **Oracle 조회**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'quality_history':
                            st.success("📊 **품질 이력**")
                            st.code(step['result'][:500], language="json")
                        elif step['type'] == 'self_correction':
                            st.warning(f"🔄 **SQL 자동 수정:** `{step['original'][:80]}` → `{step['fixed'][:80]}`")
                        elif step['type'] == 'analysis':
                            st.info(f"🔍 **판단:** {step['severity'].upper()}")
                        elif step['type'] == 'slack':
                            st.success(f"📱 **Slack:** {step['result']}")

                st.session_state.chat_history.append({'role': 'assistant', 'content': result['answer']})
                st.session_state.agent_results.append(result)

            except Exception as e:
                error_str = str(e)
                if '529' in error_str or 'overloaded' in error_str.lower():
                    error_msg = "⏳ AI 서버가 일시적으로 과부하 상태입니다. 30초 후에 다시 시도해주세요."
                else:
                    error_msg = f"오류: {e}"
                st.error(error_msg)
                st.session_state.chat_history.append({'role': 'assistant', 'content': error_msg})

st.divider()
st.caption("🛡️ LangGraph Agent — MySQL, Oracle, IDMC 로그를 자율적으로 조회하여 원인을 역추적합니다.")