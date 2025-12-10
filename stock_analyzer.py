import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from telegram import Bot
import asyncio
import schedule
import time
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
STOCK_SYMBOL = "005930.KS"  # 삼성전자 (KRX 종목은 .KS 붙임)
SCHEDULE_TIME = "09:00"  # 기본 실행 시간 (24시간 형식)

def send_telegram_message_sync(message):
    """텔레그램으로 메시지 전송 (동기 버전)"""
    try:
        async def _send():
            bot = Bot(token=TELEGRAM_TOKEN)
            async with bot:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

        asyncio.run(_send())
        return True
    except Exception as e:
        print(f"❌ 텔레그램 전송 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def send_telegram_message(message):
    """텔레그램으로 메시지 전송"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        async with bot:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        return True
    except Exception as e:
        print(f"❌ 텔레그램 전송 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def get_chat_id():
    """봇에게 메시지를 보낸 사용자의 채팅 ID 가져오기"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        async with bot:
            updates = await bot.get_updates()
            if updates:
                chat_id = updates[-1].message.chat.id
                print(f"\n✅ 채팅 ID를 찾았습니다: {chat_id}")
                print(f"📝 .env 파일의 TELEGRAM_CHAT_ID를 다음으로 업데이트하세요: {chat_id}\n")
                return chat_id
            else:
                print("\n⚠️  메시지가 없습니다.")
                print("📱 텔레그램에서 봇에게 아무 메시지나 보낸 후 다시 시도하세요.\n")
                return None
    except Exception as e:
        print(f"❌ 채팅 ID 가져오기 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def analyze_stock(symbol):
    """주식 데이터 분석"""
    try:
        # 과거 1개월 데이터 조회
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1mo")
        
        if hist.empty:
            return None
        
        # 분석 데이터 계산
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[0]
        change_rate = ((current_price - prev_price) / prev_price) * 100
        ma_20 = hist['Close'].tail(20).mean()
        
        # 메시지 구성
        message = f"""
📈 주식 분석 결과 ({symbol})
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

현재가: {current_price:,.0f}원
이전가: {prev_price:,.0f}원
변동율: {change_rate:+.2f}%

20일 이동평균: {ma_20:,.0f}원
현재가 vs 이동평균: {current_price - ma_20:+,.0f}원
"""
        return message
    
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

def job(symbol=None):
    """스케줄된 작업"""
    if symbol is None:
        symbol = STOCK_SYMBOL
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 주식 분석 시작...")
    message = analyze_stock(symbol)
    if message:
        send_telegram_message_sync(message)
        print("✅ 텔레그램으로 전송되었습니다.")
    else:
        print("❌ 분석 실패")

async def main(symbol=None):
    """메인 함수"""
    if symbol is None:
        symbol = STOCK_SYMBOL
    message = analyze_stock(symbol)
    if message:
        await send_telegram_message(message)
        print("✅ 텔레그램으로 전송되었습니다.")

def get_schedule_time():
    """사용자로부터 스케줄 시간 입력받기"""
    while True:
        time_input = input("⏰ 실행 시간을 입력하세요 (HH:MM 형식, 예: 09:00): ").strip()
        try:
            datetime.strptime(time_input, "%H:%M")
            return time_input
        except ValueError:
            print("❌ 올바른 형식이 아닙니다. HH:MM 형식으로 입력해주세요.")

def start_scheduler(schedule_time):
    """스케줄러 시작"""
    print(f"📅 스케줄러 시작: 매일 {schedule_time}에 실행")
    schedule.every().day.at(schedule_time).do(job)
    
    print("💤 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n\n⛔ 스케줄러가 종료되었습니다.")

def get_stock_symbol():
    """사용자로부터 종목코드 입력받기"""
    print("\n📈 종목코드 입력")
    print("=" * 50)
    print("예시:")
    print("  - 삼성전자: 005930.KS")
    print("  - 카카오: 035720.KS")
    print("  - NAVER: 035420.KS")
    print("  - 애플: AAPL")
    print("  - 테슬라: TSLA")
    print("=" * 50)
    symbol = input("종목코드를 입력하세요 (기본값: 005930.KS): ").strip()
    if not symbol:
        symbol = STOCK_SYMBOL
    return symbol

def show_menu():
    """메뉴 표시"""
    print("\n" + "="*50)
    print("📊 주식 분석 및 텔레그램 알림 시스템")
    print("="*50)
    print("0️⃣  채팅 ID 가져오기 (최초 설정)")
    print("1️⃣  지금 바로 분석 실행")
    print("2️⃣  스케줄러 시작 (시간 입력)")
    print("3️⃣  스케줄러 시작 (기본 시간: " + SCHEDULE_TIME + ")")
    print("4️⃣  종료")
    print("="*50 + "\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 명령행 인자로 실행
        if sys.argv[1] == "now":
            asyncio.run(main())
        elif sys.argv[1] == "schedule":
            schedule_time = sys.argv[2] if len(sys.argv) > 2 else SCHEDULE_TIME
            start_scheduler(schedule_time)
    else:
        # 인터랙티브 메뉴
        while True:
            show_menu()
            choice = input("선택: ").strip()

            if choice == "0":
                print("\n🔍 채팅 ID를 가져오는 중...\n")
                print("📱 먼저 텔레그램에서 봇(@YourBotName)에게 '/start' 또는 아무 메시지나 보내세요!\n")
                input("메시지를 보냈으면 Enter를 눌러주세요...")
                chat_id = asyncio.run(get_chat_id())
                if chat_id:
                    # .env 파일 업데이트
                    with open('.env', 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    with open('.env', 'w', encoding='utf-8') as f:
                        for line in lines:
                            if line.startswith('TELEGRAM_CHAT_ID='):
                                f.write(f'TELEGRAM_CHAT_ID={chat_id}\n')
                            else:
                                f.write(line)
                    print("✅ .env 파일이 업데이트되었습니다!")
                    print("⚠️  프로그램을 다시 시작해주세요.\n")
            elif choice == "1":
                symbol = get_stock_symbol()
                print(f"\n🚀 {symbol} 분석을 실행 중입니다...\n")
                asyncio.run(main(symbol))
            elif choice == "2":
                symbol = get_stock_symbol()
                schedule_time = get_schedule_time()
                print(f"\n📅 {symbol} 종목을 매일 {schedule_time}에 분석합니다.\n")
                # 스케줄러에 종목 전달을 위한 래퍼 함수
                schedule.every().day.at(schedule_time).do(job, symbol=symbol)
                print("💤 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")
                try:
                    while True:
                        schedule.run_pending()
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\n\n⛔ 스케줄러가 종료되었습니다.")
            elif choice == "3":
                symbol = get_stock_symbol()
                print(f"\n📅 {symbol} 종목을 매일 {SCHEDULE_TIME}에 분석합니다.\n")
                schedule.every().day.at(SCHEDULE_TIME).do(job, symbol=symbol)
                print("💤 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")
                try:
                    while True:
                        schedule.run_pending()
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\n\n⛔ 스케줄러가 종료되었습니다.")
            elif choice == "4":
                print("👋 프로그램을 종료합니다.")
                break
            else:
                print("❌ 잘못된 선택입니다. 다시 시도해주세요.\n")