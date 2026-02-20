# utils/ai.py - AI 분석 + Slack

import json
import os
import requests
from datetime import date
from anthropic import Anthropic
from dotenv import load_dotenv
from utils.detector import DecimalEncoder, TASK_NAME

load_dotenv()


def run_ai(vol, qual):
    """Claude AI 종합 분석"""
    client = Anthropic()
    system = """데이터 파이프라인 품질 전문가. 볼륨+품질 종합 분석.

## 판단 기준 (반드시 따르세요)
- 볼륨판정이 "normal"이고 품질이상이 0건이면 → 반드시 "normal"
- 볼륨판정이 "warning" 또는 품질이상 1건 이상 → "warning"  
- 볼륨판정이 "critical"이면서 품질이상도 있으면 → "critical"

정상일 때는 "현재 상태 양호"라고 보고하세요. 정상인데 WARNING을 주지 마세요.

JSON만: {"overall_status":"critical/warning/normal","confidence":0.0~1.0,"summary":"한줄","cause_analysis":"현재상태분석","business_impact":"영향","recommended_actions":["1","2","3"]}"""

    user_msg = f"""볼륨: {vol['today_rows']:,}건 (평균{vol['mean']:,.0f}, Z={vol['z_score']}, {vol['change_pct']}%)
볼륨판정: {vol['severity']} (Z-Score ±2 미만이면 정상)
NULL변화: {json.dumps(qual['changes'], ensure_ascii=False, cls=DecimalEncoder)}
품질이상건수: {len(qual['anomalies'])}건
품질이상: {json.dumps(qual['anomalies'], ensure_ascii=False, cls=DecimalEncoder)}
금액: {json.dumps(qual['amount_stats'], ensure_ascii=False, cls=DecimalEncoder)}
오늘: {date.today()} ({vol['day_name']}요일). JSON만."""

    resp = client.messages.create(model='claude-sonnet-4-20250514', max_tokens=1024,
                                   system=system, messages=[{'role': 'user', 'content': user_msg}])
    text = resp.content[0].text
    return json.loads(text.replace('```json', '').replace('```', '').strip())


def send_slack(vol, qual, ai):
    """Slack 알림 발송"""
    webhook = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook:
        return "SLACK_WEBHOOK_URL 없음"

    issues = []
    if vol.get('severity') != 'normal':
        issues.append(f"볼륨 {vol['change_pct']:+.1f}% (Z={vol['z_score']})")
    for a in qual.get('anomalies', []):
        issues.append(a['message'])

    issue_text = "\n".join(f"  • {i}" for i in issues) if issues else "  없음"
    actions = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(ai.get('recommended_actions', [])))
    icon = "🔴" if ai['overall_status'] == 'critical' else "🟡" if ai['overall_status'] == 'warning' else "🟢"

    msg = f"""{icon} *[Silent Failure Guardian]*

*태스크:* {TASK_NAME}
*일시:* {date.today()}

*📊 볼륨:* {vol['today_rows']:,}건 ({vol['compare']} 평균: {vol['mean']:,.0f}건)
*🔍 감지된 이상:*
{issue_text}

*🤖 AI 분석:*
{ai['summary']}

*원인:* {ai['cause_analysis']}

*🔧 권장 조치:*
{actions}

📊 <http://localhost:8501|대시보드 열기>"""

    r = requests.post(webhook, json={"text": msg})
    return r.text