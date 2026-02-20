# utils/agent.py - LangGraph 기반 멀티 도구 Agent

import os
import json
import re
import oracledb
import requests
import mysql.connector
import sqlite3
from datetime import date, timedelta
from typing import TypedDict, Annotated, Literal
from dotenv import load_dotenv
from anthropic import Anthropic
from langgraph.graph import StateGraph, END

load_dotenv()

client = Anthropic()

# ============================================================
# 상태(State) 정의
# ============================================================
class AgentState(TypedDict):
    user_message: str
    chat_history: list
    plan: str
    mysql_result: str
    idmc_result: str
    oracle_result: str
    quality_history_result: str
    analysis: str
    need_slack: bool
    slack_result: str
    final_answer: str
    steps: list
    error_count: int


# ============================================================
# 도구 함수들
# ============================================================
def query_mysql(sql: str) -> str:
    try:
        conn = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', 3306)),
            database=os.getenv('MYSQL_DB', 'analytics'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD')
        )
        cur = conn.cursor(dictionary=True)
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        return json.dumps(rows[:20], ensure_ascii=False, default=str)
    except Exception as e:
        return f"MYSQL_ERROR: {e}"


def query_oracle(sql: str) -> str:
    try:
        conn = oracledb.connect(
            user=os.getenv("ORACLE_USER"),
            password=os.getenv("ORACLE_PASSWORD"),
            dsn=os.getenv("ORACLE_DSN")
        )
        cur = conn.cursor()
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()[:20]]
        conn.close()
        return json.dumps(rows, ensure_ascii=False, default=str)
    except Exception as e:
        return f"ORACLE_ERROR: {e}"


def fetch_idmc_logs() -> str:
    """IDMC 로그 조회 (guardian.db에 저장된 것 + API 최신)"""
    try:
        # 1. guardian.db에서 먼저 조회
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'guardian.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT run_id, object_name, status, source_rows, target_rows, start_time, end_time
            FROM idmc_logs ORDER BY start_time DESC LIMIT 10
        """)
        rows = [{'runId': r[0], 'objectName': r[1], 'status': r[2], 'sourceRows': r[3],
                 'targetRows': r[4], 'startTime': r[5], 'endTime': r[6]} for r in cur.fetchall()]
        conn.close()

        if rows:
            return json.dumps(rows, ensure_ascii=False, default=str)

        # 2. 없으면 API 시도
        login_url = f"{os.getenv('IDMC_LOGIN_URL')}/ma/api/v2/user/login"
        payload = {
            "@type": "login",
            "username": os.getenv('IDMC_USERNAME'),
            "password": os.getenv('IDMC_PASSWORD')
        }
        resp = requests.post(login_url, json=payload)
        data = resp.json()
        sid = data['icSessionId']
        server_url = data['serverUrl']

        logs = requests.get(
            f"{server_url}/api/v2/activity/activityLog",
            headers={"icSessionId": sid}
        ).json()

        filtered = []
        for log in logs:
            if 'ORDERS' in log.get('objectName', '').upper():
                filtered.append({
                    'objectName': log.get('objectName'),
                    'state': log.get('state'),
                    'startTime': log.get('startTime'),
                    'endTime': log.get('endTime'),
                    'sourceRows': log.get('successSourceRows', 0),
                    'targetRows': log.get('successTargetRows', 0),
                    'errorMsg': log.get('errorMsg', ''),
                })
        return json.dumps(filtered[:5], ensure_ascii=False, default=str)
    except Exception as e:
        return f"IDMC_ERROR: {e}"


def fetch_quality_history() -> str:
    try:
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'guardian.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT run_date, column_name, null_pct FROM quality_history
            ORDER BY run_date DESC LIMIT 42
        """)
        rows = [{'date': r[0], 'column': r[1], 'null_pct': r[2]} for r in cur.fetchall()]
        conn.close()
        return json.dumps(rows, ensure_ascii=False)
    except Exception as e:
        return f"QUALITY_ERROR: {e}"


def send_slack(message: str) -> str:
    try:
        webhook = os.getenv('SLACK_WEBHOOK_URL')
        if not webhook:
            return "SLACK_WEBHOOK_URL 없음"
        r = requests.post(webhook, json={"text": message})
        return "Slack 발송 성공" if r.text == 'ok' else f"Slack 실패: {r.text}"
    except Exception as e:
        return f"SLACK_ERROR: {e}"


# ============================================================
# 노드(Node) 정의
# ============================================================
def plan_node(state: AgentState) -> AgentState:
    """사용자 질문을 분석하고 계획 수립"""
    messages = []
    if state.get('chat_history'):
        for msg in state['chat_history'][-6:]:
            messages.append({'role': msg['role'], 'content': msg['content']})
    messages.append({'role': 'user', 'content': state['user_message']})

    resp = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=1024,
       system=f"""사용자의 질문을 분석하고 어떤 도구를 사용할지 계획하세요.
오늘: {date.today()}

사용 가능한 도구:
- mysql: MySQL 분석 DB 조회 (orders_analytics 테이블)
- oracle: Oracle 소스 DB 조회 (ORDERS 테이블)
- idmc: IDMC ETL 로그 조회
- quality_history: 품질 이력 조회 (최근 7일 NULL 비율)
- slack: 알림 발송

## SQL 작성 원칙
- 반드시 완결된 SQL을 작성할 것. "추가 분석 필요" 같은 미완성 답변 금지.
- 비교가 필요하면 서브쿼리, JOIN, NOT IN 등 활용하여 하나의 SQL로 해결할 것

## 대화 맥락
- 이전 대화 내용을 반드시 참고할 것
- "그거", "아까", "위에서 말한" 같은 표현은 이전 대화를 참조하는 것
- 이전 답변에서 나온 수치나 결과를 기반으로 더 깊이 파고드는 SQL을 작성할 것


## MySQL 테이블: orders_analytics
컬럼: order_id(INT), customer_id(INT), customer_name, phone_number, email, order_date(DATE), total_amount(DECIMAL), product_code, product_name, category, order_status, payment_method, sync_timestamp

## Oracle 테이블: ORDERS
컬럼: ORDER_ID(NUMBER), CUSTOMER_ID(NUMBER), CUSTOMER_NAME, PHONE_NUMBER, EMAIL, ORDER_DATE(DATE), TOTAL_AMOUNT(NUMBER), PRODUCT_CODE, PRODUCT_NAME, CATEGORY, ORDER_STATUS, PAYMENT_METHOD
주의: Oracle은 컬럼명 대문자. 날짜 비교는 TRUNC(ORDER_DATE) = DATE '{date.today()}' 형식.
주의: Oracle에서 CURDATE() 사용 금지. SYSDATE 또는 DATE 리터럴 사용.

## 중요: 비교 규칙
- MySQL과 Oracle 건수를 비교할 때는 반드시 같은 조건으로 조회할 것
- MySQL에서 WHERE 없이 전체 조회하면 Oracle도 WHERE 없이 전체 조회
- MySQL에서 오늘만 조회하면 Oracle도 오늘만 조회
- 날짜 조건이 다르면 건수 비교가 무의미함

반드시 아래 JSON 형식으로만 응답:
{{"plan": "계획 설명", "tools": ["사용할 도구들"], "mysql_sqls": ["SQL1", "SQL2"], "oracle_sqls": ["SQL1", "SQL2"]}}

- mysql_sqls, oracle_sqls는 배열로 여러 개 가능
- 복합 분석이 필요하면 SQL을 여러 개 나눠서 작성
- 단순 질문이면 SQL 1개만 넣어도 됨""",
        messages=messages
    )

    text = resp.content[0].text
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            plan_data = json.loads(json_match.group())
        else:
            plan_data = {"plan": text, "tools": ["mysql"], "mysql_sql": "SELECT COUNT(*) as cnt FROM orders_analytics"}
    except:
        plan_data = {"plan": text, "tools": ["mysql"], "mysql_sql": "SELECT COUNT(*) as cnt FROM orders_analytics"}

    state['plan'] = json.dumps(plan_data, ensure_ascii=False)
    state['steps'] = state.get('steps', [])
    state['steps'].append({'type': 'plan', 'content': plan_data.get('plan', '')})
    state['error_count'] = 0
    return state


def mysql_node(state: AgentState) -> AgentState:
    """MySQL 조회 (복수 SQL 지원)"""
    plan_data = json.loads(state['plan'])
    
    # 단일 sql도 호환
    sqls = plan_data.get('mysql_sqls', [])
    if not sqls and plan_data.get('mysql_sql'):
        sqls = [plan_data['mysql_sql']]
    if not sqls:
        sqls = ['SELECT COUNT(*) as cnt FROM orders_analytics']

    all_results = []
    for i, sql in enumerate(sqls):
        if any(word in sql.upper() for word in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE']):
            all_results.append(f"[SQL {i+1}] 보안: SELECT만 허용됩니다")
            continue

        result = query_mysql(sql)

        if 'MYSQL_ERROR' in result and state['error_count'] < 3:
            state['error_count'] += 1
            fix_resp = client.messages.create(
                model='claude-sonnet-4-20250514',
                max_tokens=512,
                system="MySQL 쿼리에서 에러가 발생했습니다. 수정된 SQL만 출력하세요. 다른 텍스트 없이 SQL만.",
                messages=[{'role': 'user', 'content': f"원래 SQL: {sql}\n에러: {result}\n수정된 SQL:"}]
            )
            fixed_sql = fix_resp.content[0].text.strip()
            state['steps'].append({'type': 'self_correction', 'original': sql, 'fixed': fixed_sql, 'error': result})
            result = query_mysql(fixed_sql)

        all_results.append(f"[SQL {i+1}] {sql}\n결과: {result}")

    state['mysql_result'] = "\n\n".join(all_results)
    state['steps'].append({'type': 'mysql', 'result': state['mysql_result'][:1000]})
    return state

def idmc_node(state: AgentState) -> AgentState:
    """IDMC 로그 조회"""
    result = fetch_idmc_logs()
    state['idmc_result'] = result
    state['steps'].append({'type': 'idmc', 'result': result[:500]})
    return state


def oracle_node(state: AgentState) -> AgentState:
    """Oracle 소스 조회"""
    plan_data = json.loads(state['plan'])
    sql = plan_data.get('oracle_sql', 'SELECT COUNT(*) as cnt FROM ORDERS')

    if any(word in sql.upper() for word in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE']):
        state['oracle_result'] = "보안: SELECT만 허용됩니다"
    else:
        result = query_oracle(sql)

        if 'ORACLE_ERROR' in result and state['error_count'] < 3:
            state['error_count'] += 1
            fix_resp = client.messages.create(
                model='claude-sonnet-4-20250514',
                max_tokens=512,
                system="Oracle 쿼리에서 에러가 발생했습니다. 수정된 SQL만 출력하세요.",
                messages=[{'role': 'user', 'content': f"원래 SQL: {sql}\n에러: {result}\n수정된 SQL:"}]
            )
            fixed_sql = fix_resp.content[0].text.strip()
            state['steps'].append({'type': 'self_correction', 'original': sql, 'fixed': fixed_sql, 'error': result})
            result = query_oracle(fixed_sql)

        state['oracle_result'] = result

    state['steps'].append({'type': 'oracle', 'result': state['oracle_result'][:500]})
    return state


def quality_node(state: AgentState) -> AgentState:
    """품질 이력 조회"""
    result = fetch_quality_history()
    state['quality_history_result'] = result
    state['steps'].append({'type': 'quality_history', 'result': result[:500]})
    return state


def analyze_node(state: AgentState) -> AgentState:
    """수집한 데이터를 종합 분석"""
    context = f"""사용자 질문: {state['user_message']}
계획: {state['plan']}
MySQL 결과: {state.get('mysql_result', '조회 안 함')}
IDMC 로그: {state.get('idmc_result', '조회 안 함')}
Oracle 결과: {state.get('oracle_result', '조회 안 함')}
품질 이력: {state.get('quality_history_result', '조회 안 함')}"""

    resp = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=2048,
        system=f"""수집된 데이터를 바탕으로 종합 분석하세요. 오늘: {date.today()}

## 원인 추론 규칙
- IDMC 로그에서 최종 실행이 성공(status:1)이고 sourceRows == targetRows면 → ETL 전송 자체는 정상
- Oracle에도 NULL이 있고 MySQL에도 NULL이 있으면 → 소스 데이터 문제 (ETL은 정상적으로 전달한 것)
- Oracle에는 NULL이 없는데 MySQL에만 NULL이 있으면 → 두 가지 가능성 모두 언급:
  1) ETL 변환 과정에서 매핑/변환 오류로 NULL 발생
  2) ETL 외부에서 직접 INSERT된 데이터 (MySQL 건수가 Oracle보다 많으면 이 가능성이 높음)
- MySQL 건수 > Oracle 건수면 → 차이만큼 외부 주입 가능성 높음
- MySQL 건수 == Oracle 건수인데 NULL 차이가 있으면 → ETL 변환 오류 가능성 높음
- status:2(실패)는 최종 성공 전의 재시도이므로, 마지막 실행이 성공이면 ETL 전송은 정상으로 판단

반드시 아래 JSON으로 응답:
{{"answer": "사용자에게 보여줄 답변 (한국어, 간결하게)", "severity": "normal/warning/critical", "need_slack": true/false, "slack_message": "Slack에 보낼 메시지 (need_slack이 true일 때만)"}}""",
        messages=[{'role': 'user', 'content': context}]
    )

    text = resp.content[0].text
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        analysis = json.loads(json_match.group())
    except:
        analysis = {"answer": text, "severity": "normal", "need_slack": False}

    state['analysis'] = json.dumps(analysis, ensure_ascii=False)
    state['final_answer'] = analysis.get('answer', text)
    state['need_slack'] = analysis.get('need_slack', False)
    state['steps'].append({'type': 'analysis', 'severity': analysis.get('severity', 'normal')})
    return state


def slack_node(state: AgentState) -> AgentState:
    """Slack 알림 발송"""
    analysis = json.loads(state['analysis'])
    msg = analysis.get('slack_message', state['final_answer'])
    result = send_slack(f"🛡️ *[Guardian Agent]*\n\n{msg}")
    state['slack_result'] = result
    state['steps'].append({'type': 'slack', 'result': result})
    return state


# ============================================================
# 라우터 (분기 결정)
# ============================================================
def route_tools(state: AgentState) -> str:
    """계획에 따라 첫 번째 도구 노드 결정"""
    plan_data = json.loads(state['plan'])
    tools = plan_data.get('tools', ['mysql'])
    
    if 'quality_history' in tools:
        return 'quality_history'
    if 'mysql' in tools:
        return 'mysql'
    if 'idmc' in tools:
        return 'idmc'
    if 'oracle' in tools:
        return 'oracle'
    return 'mysql'


def route_after_quality(state: AgentState) -> str:
    plan_data = json.loads(state['plan'])
    tools = plan_data.get('tools', [])
    if 'mysql' in tools:
        return 'mysql'
    if 'idmc' in tools:
        return 'idmc'
    if 'oracle' in tools:
        return 'oracle'
    return 'analyze'


def route_after_mysql(state: AgentState) -> str:
    plan_data = json.loads(state['plan'])
    tools = plan_data.get('tools', [])
    if 'idmc' in tools:
        return 'idmc'
    if 'oracle' in tools:
        return 'oracle'
    return 'analyze'


def route_after_idmc(state: AgentState) -> str:
    plan_data = json.loads(state['plan'])
    tools = plan_data.get('tools', [])
    if 'oracle' in tools:
        return 'oracle'
    return 'analyze'


def route_slack(state: AgentState) -> str:
    if state.get('need_slack'):
        return 'slack'
    return 'end'


# ============================================================
# 그래프 구성
# ============================================================
def build_graph():
    graph = StateGraph(AgentState)

    # 노드 추가
    graph.add_node("plan", plan_node)
    graph.add_node("mysql", mysql_node)
    graph.add_node("idmc", idmc_node)
    graph.add_node("oracle", oracle_node)
    graph.add_node("quality_history", quality_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("slack", slack_node)

    # 시작 → 계획
    graph.set_entry_point("plan")

    # 계획 → 첫 번째 도구
    graph.add_conditional_edges("plan", route_tools, {
        "quality_history": "quality_history",
        "mysql": "mysql",
        "idmc": "idmc",
        "oracle": "oracle",
    })

    # 도구 → 다음 도구 또는 분석 (순차 실행)
    graph.add_conditional_edges("quality_history", route_after_quality, {
        "mysql": "mysql", "idmc": "idmc", "oracle": "oracle", "analyze": "analyze"
    })
    graph.add_conditional_edges("mysql", route_after_mysql, {
        "idmc": "idmc", "oracle": "oracle", "analyze": "analyze"
    })
    graph.add_conditional_edges("idmc", route_after_idmc, {
        "oracle": "oracle", "analyze": "analyze"
    })
    graph.add_edge("oracle", "analyze")

    # 분석 → Slack 또는 종료
    graph.add_conditional_edges("analyze", route_slack, {"slack": "slack", "end": END})
    graph.add_edge("slack", END)

    return graph.compile()

# 그래프 빌드
agent_graph = build_graph()


# ============================================================
# 실행 함수
# ============================================================
def run_agent(user_message: str, chat_history: list = None):
    """LangGraph Agent 실행"""
    initial_state = {
        'user_message': user_message,
        'chat_history': chat_history or [],
        'plan': '{}',
        'mysql_result': '',
        'idmc_result': '',
        'oracle_result': '',
        'quality_history_result': '',
        'analysis': '{}',
        'need_slack': False,
        'slack_result': '',
        'final_answer': '',
        'steps': [],
        'error_count': 0,
    }

    result = agent_graph.invoke(initial_state)

    return {
        'answer': result['final_answer'],
        'steps': result['steps'],
        'iterations': len(result['steps']),
    }