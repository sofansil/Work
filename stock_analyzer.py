import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from telegram import Bot
import asyncio
import schedule
import time
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 환경변수 로드
load_dotenv()

# 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
STOCK_SYMBOL = "005930"  # 삼성전자 (자동으로 KOSPI/KOSDAQ 판단)
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
        print(f"[오류] 텔레그램 전송 오류: {str(e)}")
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
        print(f"[오류] 텔레그램 전송 오류: {str(e)}")
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
                print(f"\n[OK] 채팅 ID를 찾았습니다: {chat_id}")
                print(f"[안내] .env 파일의 TELEGRAM_CHAT_ID를 다음으로 업데이트하세요: {chat_id}\n")
                return chat_id
            else:
                print("\n[주의] 메시지가 없습니다.")
                print("[안내] 텔레그램에서 봇에게 아무 메시지나 보낸 후 다시 시도하세요.\n")
                return None
    except Exception as e:
        print(f"[오류] 채팅 ID 가져오기 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def normalize_stock_symbol(symbol):
    """종목코드 정규화 - 한국 주식의 경우 KOSPI/KOSDAQ 자동 판단"""
    symbol = symbol.strip().upper()

    # 숫자로만 이루어진 경우 (한국 주식) - FinanceDataReader는 접미사 없이 사용
    if symbol.isdigit():
        # FinanceDataReader로 종목 존재 여부 확인
        try:
            # KRX 전체 종목 리스트에서 확인
            df_krx = fdr.StockListing('KRX')
            if symbol in df_krx['Code'].values:
                stock_info = df_krx[df_krx['Code'] == symbol].iloc[0]
                market = stock_info['Market']
                name = stock_info['Name']
                print(f"[OK] {symbol} ({name}, {market}) 종목을 찾았습니다.")
                return symbol, 'KRX'
            else:
                print(f"[주의] {symbol} 종목을 KRX에서 찾을 수 없습니다.")
                return symbol, 'KRX'
        except Exception as e:
            print(f"[주의] 종목 확인 중 오류: {e}")
            return symbol, 'KRX'

    # 알파벳인 경우 (미국 주식 등)
    return symbol, 'US'

def analyze_stock(symbol):
    """주식 데이터 분석"""
    try:
        # 종목코드 정규화
        symbol_code, market = normalize_stock_symbol(symbol)

        # 날짜 범위 설정 (최근 1개월)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # 데이터 조회
        if market == 'KRX':
            # 한국 주식
            hist = fdr.DataReader(symbol_code, start_date, end_date)
            currency = 'KRW'

            # 종목 이름 가져오기
            try:
                df_krx = fdr.StockListing('KRX')
                stock_info = df_krx[df_krx['Code'] == symbol_code]
                if not stock_info.empty:
                    stock_name = stock_info.iloc[0]['Name']
                else:
                    stock_name = symbol_code
            except:
                stock_name = symbol_code
        else:
            # 미국 주식
            hist = fdr.DataReader(symbol_code, start_date, end_date)
            currency = 'USD'
            stock_name = symbol_code

        if hist.empty:
            return f"[오류] {symbol_code} 종목의 데이터를 찾을 수 없습니다. 종목코드를 확인해주세요."

        # 분석 데이터 계산
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[0]
        change_rate = ((current_price - prev_price) / prev_price) * 100

        # 20일 이동평균 (데이터가 20일 미만이면 가능한 만큼만)
        ma_days = min(20, len(hist))
        ma_20 = hist['Close'].tail(ma_days).mean()

        # 통화에 따른 포맷 결정
        if currency == 'KRW':
            price_format = lambda x: f"{x:,.0f}원"
        else:
            price_format = lambda x: f"${x:,.2f}"

        # 메시지 구성
        message = f"""
📈 주식 분석 결과
종목: {stock_name} ({symbol_code})
시장: {market}
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

현재가: {price_format(current_price)}
1개월 전 가격: {price_format(prev_price)}
변동율: {change_rate:+.2f}%

{ma_days}일 이동평균: {price_format(ma_20)}
현재가 vs 이동평균: {price_format(current_price - ma_20)} ({((current_price - ma_20) / ma_20 * 100):+.2f}%)
"""
        return message

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[오류] 오류 발생: {str(e)}"

def job(symbol=None):
    """스케줄된 작업"""
    if symbol is None:
        symbol = STOCK_SYMBOL
    print(f"[스케줄] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 주식 분석 시작...")
    message = analyze_stock(symbol)
    if message:
        send_telegram_message_sync(message)
        print("[OK] 텔레그램으로 전송되었습니다.")
    else:
        print("[오류] 분석 실패")

async def main(symbol=None):
    """메인 함수"""
    if symbol is None:
        symbol = STOCK_SYMBOL
    message = analyze_stock(symbol)
    if message:
        await send_telegram_message(message)
        print("[OK] 텔레그램으로 전송되었습니다.")

def get_schedule_time():
    """사용자로부터 스케줄 시간 입력받기"""
    while True:
        time_input = input("[입력] 실행 시간을 입력하세요 (HH:MM 형식, 예: 09:00): ").strip()
        try:
            datetime.strptime(time_input, "%H:%M")
            return time_input
        except ValueError:
            print("[오류] 올바른 형식이 아닙니다. HH:MM 형식으로 입력해주세요.")

def start_scheduler(schedule_time, symbol=None):
    """스케줄러 시작"""
    if symbol is None:
        symbol = STOCK_SYMBOL
    print(f"[스케줄러] {symbol} 종목을 매일 {schedule_time}에 실행합니다")
    schedule.every().day.at(schedule_time).do(job, symbol=symbol)

    print("[대기중] 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n\n[종료] 스케줄러가 종료되었습니다.")

def get_stock_symbol():
    """사용자로부터 종목코드 입력받기"""
    print("\n[입력] 종목코드 입력")
    print("=" * 50)
    print("예시:")
    print("  [한국 주식]")
    print("  - 삼성전자: 005930 (자동으로 KOSPI/KOSDAQ 판단)")
    print("  - 카카오: 035720")
    print("  - NAVER: 035420")
    print("  - 에코프로비엠: 247540")
    print("")
    print("  [미국 주식]")
    print("  - 애플: AAPL")
    print("  - 테슬라: TSLA")
    print("  - 엔비디아: NVDA")
    print("=" * 50)
    symbol = input("종목코드를 입력하세요 (기본값: 005930): ").strip()
    if not symbol:
        symbol = "005930"
    return symbol

def analyze_single_stock(code, name, market, start_date, end_date, threshold):
    """
    단일 종목 분석 (병렬 처리용)

    Args:
        code: 종목 코드
        name: 종목명
        market: 시장 (KOSPI/KOSDAQ/KONEX)
        start_date: 시작 날짜
        end_date: 종료 날짜
        threshold: 상승률 기준

    Returns:
        dict or None: 조건을 만족하면 종목 정보 딕셔너리, 아니면 None
    """
    try:
        # 데이터 가져오기
        hist = fdr.DataReader(code, start_date, end_date)

        if len(hist) < 20:
            return None

        # 현재가와 20일 이동평균 계산
        current_price = hist['Close'].iloc[-1]
        ma_20 = hist['Close'].tail(20).mean()

        # 상승률 계산
        diff_pct = ((current_price - ma_20) / ma_20) * 100

        if diff_pct >= threshold:
            return {
                '종목코드': code,
                '종목명': name,
                '시장': market,
                '현재가': int(current_price),
                '20일평균': int(ma_20),
                '상승률': round(diff_pct, 2),
                '거래량': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
            }
    except Exception as e:
        # 데이터가 없거나 오류가 있는 종목은 조용히 넘어감
        pass

    return None

def screen_stocks(threshold=5.0, max_workers=20):
    """
    20일 이동평균 대비 현재가가 threshold% 이상 상승한 종목 찾기 (병렬 처리)

    Args:
        threshold: 상승률 기준 (기본값: 5.0%)
        max_workers: 병렬 처리 스레드 수 (기본값: 20)
    """
    print("[시작] KRX 종목 스크리닝 시작...")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
    print(f"[설정] 병렬 처리 스레드: {max_workers}개")
    print("="*70)

    # KRX 전체 종목 리스트 가져오기
    try:
        df_krx = fdr.StockListing('KRX')
        print(f"[정보] 총 {len(df_krx)}개 종목 스캔 중...\n")
    except Exception as e:
        print(f"[오류] 종목 리스트 가져오기 실패: {e}")
        return []

    # 날짜 범위 설정 (최근 30일)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=50)  # 여유있게 50일

    results = []
    completed_count = 0
    total_count = len(df_krx)
    lock = threading.Lock()

    # 병렬 처리로 종목 분석
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 종목에 대해 작업 제출
        future_to_stock = {
            executor.submit(
                analyze_single_stock,
                row['Code'],
                row['Name'],
                row['Market'],
                start_date,
                end_date,
                threshold
            ): (row['Code'], row['Name'], row['Market'])
            for _, row in df_krx.iterrows()
        }

        # 완료된 작업 처리
        for future in as_completed(future_to_stock):
            code, name, market = future_to_stock[future]
            completed_count += 1

            try:
                result = future.result()
                if result:
                    with lock:
                        results.append(result)
                    print(f"[발견] {code} {name} ({market}) - 현재가: {result['현재가']:,}원, 상승률: {result['상승률']}%")
            except Exception as e:
                # 오류 무시
                pass

            # 진행상황 표시 (100개마다)
            if completed_count % 100 == 0:
                print(f"[진행] {completed_count}/{total_count} 종목 분석 완료...")

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.\n")

    return results
5

def format_screening_results(results, threshold):
    """스크리닝 결과를 텔레그램 메시지 형식으로 포맷"""
    if not results:
        return f"20일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

    # 상승률 순으로 정렬
    results_sorted = sorted(results, key=lambda x: x['상승률'], reverse=True)

    # 상위 20개만 선택
    top_results = results_sorted[:20]

    message = f"""
[주식 스크리닝 결과]
조건: 20일 이동평균 대비 {threshold}% 이상 상승
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}
총 발견: {len(results)}개 종목

[상위 {len(top_results)}개 종목]
"""

    for i, stock in enumerate(top_results, 1):
        message += f"""
{i}. {stock['종목명']} ({stock['종목코드']})
   시장: {stock['시장']}
   현재가: {stock['현재가']:,}원
   20일평균: {stock['20일평균']:,}원
   상승률: +{stock['상승률']}%
   거래량: {stock['거래량']:,}주
"""

    if len(results) > 20:
        message += f"\n* 상위 20개만 표시 (전체 {len(results)}개)"

    return message

def show_menu():
    """메뉴 표시"""
    print("\n" + "="*50)
    print("[시스템] 주식 분석 및 텔레그램 알림")
    print("="*50)
    print("0. 채팅 ID 가져오기 (최초 설정)")
    print("1. 지금 바로 분석 실행")
    print("2. 스케줄러 시작 (시간 입력)")
    print("3. 스케줄러 시작 (기본 시간: " + SCHEDULE_TIME + ")")
    print("4. 급등주 스크리닝 (20일 이평선 돌파)")
    print("5. 종료")
    print("="*50 + "\n")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 명령행 인자로 실행
        if sys.argv[1] == "now":
            # python stock_analyzer.py now [종목코드]
            symbol = sys.argv[2] if len(sys.argv) > 2 else STOCK_SYMBOL
            asyncio.run(main(symbol))
        elif sys.argv[1] == "schedule":
            # python stock_analyzer.py schedule [시간] [종목코드]
            schedule_time = sys.argv[2] if len(sys.argv) > 2 else SCHEDULE_TIME
            symbol = sys.argv[3] if len(sys.argv) > 3 else STOCK_SYMBOL
            start_scheduler(schedule_time, symbol)
    else:
        # 인터랙티브 메뉴
        while True:
            show_menu()
            choice = input("선택: ").strip()

            if choice == "0":
                print("\n[실행] 채팅 ID를 가져오는 중...\n")
                print("[안내] 먼저 텔레그램에서 봇(@crawlTickerL_bot)에게 '/start' 또는 아무 메시지나 보내세요!\n")
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
                    print("[OK] .env 파일이 업데이트되었습니다!")
                    print("[주의] 프로그램을 다시 시작해주세요.\n")
            elif choice == "1":
                symbol = get_stock_symbol()
                print(f"\n[실행] {symbol} 분석을 실행 중입니다...\n")
                asyncio.run(main(symbol))
            elif choice == "2":
                symbol = get_stock_symbol()
                schedule_time = get_schedule_time()
                print(f"\n[스케줄] {symbol} 종목을 매일 {schedule_time}에 분석합니다.\n")
                # 스케줄러에 종목 전달을 위한 래퍼 함수
                schedule.every().day.at(schedule_time).do(job, symbol=symbol)
                print("[대기중] 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")
                try:
                    while True:
                        schedule.run_pending()
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\n\n[종료] 스케줄러가 종료되었습니다.")
            elif choice == "3":
                symbol = get_stock_symbol()
                print(f"\n[스케줄] {symbol} 종목을 매일 {SCHEDULE_TIME}에 분석합니다.\n")
                schedule.every().day.at(SCHEDULE_TIME).do(job, symbol=symbol)
                print("[대기중] 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")
                try:
                    while True:
                        schedule.run_pending()
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\n\n[종료] 스케줄러가 종료되었습니다.")
            elif choice == "4":
                print("\n[실행] 급등주 스크리닝을 시작합니다...\n")
                threshold_input = input("[입력] 상승률 기준을 입력하세요 (기본값: 5.0%): ").strip()
                try:
                    threshold = float(threshold_input) if threshold_input else 5.0
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 5.0%를 사용합니다.")
                    threshold = 5.0

                workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 20, 권장: 10-30): ").strip()
                try:
                    max_workers = int(workers_input) if workers_input else 20
                    max_workers = max(5, min(50, max_workers))  # 5-50 범위로 제한
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 20을 사용합니다.")
                    max_workers = 20

                print(f"\n[설정] 상승률 기준: {threshold}%")
                print(f"[설정] 병렬 처리 스레드: {max_workers}개\n")

                # 스크리닝 실행
                results = screen_stocks(threshold, max_workers)

                # 결과 포맷
                message = format_screening_results(results, threshold)

                # 콘솔 출력
                print("\n" + "="*70)
                print("[결과 미리보기]")
                print("="*70)
                print(message)

                # 텔레그램 전송
                print("\n[전송] 텔레그램으로 전송 중...")
                success = send_telegram_message_sync(message)
                if success:
                    print("[OK] 텔레그램 전송 완료!")
                else:
                    print("[오류] 텔레그램 전송 실패")

                # 결과를 CSV로 저장
                if results:
                    df_results = pd.DataFrame(results)
                    filename = f"stock_screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    df_results.to_csv(filename, index=False, encoding='utf-8-sig')
                    print(f"[저장] {filename} 파일로 저장되었습니다.")

            elif choice == "5":
                print("[종료] 프로그램을 종료합니다.")
                break
            else:
                print("[오류] 잘못된 선택입니다. 다시 시도해주세요.\n")