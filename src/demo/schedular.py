# src/demo/scheduler.py
# 매일 08:00 Oracle에 더미데이터 적재

from apscheduler.schedulers.blocking import BlockingScheduler
from daily_data_loader import generate_daily_data

scheduler = BlockingScheduler()


@scheduler.scheduled_job('cron', hour=8, minute=0)
def job_load_data():
    print("\n⏰ [08:00] Oracle 데이터 적재 시작...")
    generate_daily_data()


if __name__ == '__main__':
    print("🛡️ 데이터 적재 스케줄러 시작!")
    print("  📦 매일 08:00 - Oracle에 더미데이터 INSERT")
    print("  그 다음은 IDMC 스케줄이 09:00에 동기화")
    print("  Ctrl+C로 종료\n")

    # 시작할 때 오늘치 1회 실행
    print("🔧 오늘치 즉시 실행...")
    generate_daily_data()

    scheduler.start()
'''
cd D:\JaeYoonP
python src/demo/scheduler.py
'''