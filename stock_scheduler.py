import schedule
import time
import asyncio
from stock_analyzer import analyze_stock, send_telegram_message

def job():
    message = analyze_stock("005930.KS")
    if message:
        asyncio.run(send_telegram_message(message))

# 매일 오전 9시에 실행
schedule.every().day.at("09:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)