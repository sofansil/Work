"""
주식 분석 및 텔레그램 알림 시스템 (개선 버전)
- 단일 종목 분석
- 급등주 스크리닝 (병렬 처리)
- 텔레그램 알림
- 스케줄링 기능
"""

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
import logging
from typing import Optional, List, Dict, Tuple

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 환경변수 로드
load_dotenv()

# ==================== 상수 정의 ====================
# 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
STOCK_SYMBOL = "005930"  # 삼성전자
SCHEDULE_TIME = "09:00"  # 기본 실행 시간

# 기술적 지표 상수
MA_PERIOD = 20  # 이동평균 기간
MIN_DATA_DAYS = 20  # 최소 데이터 일수
ANALYSIS_DAYS = 30  # 분석 기간 (일)
DATA_FETCH_DAYS = 50  # 데이터 가져올 기간 (여유있게)

# 스크리닝 설정
DEFAULT_THRESHOLD = 5.0  # 기본 상승률 기준 (%)
DEFAULT_MAX_WORKERS = 20  # 기본 병렬 처리 스레드 수
MIN_WORKERS = 5  # 최소 스레드 수
MAX_WORKERS = 50  # 최대 스레드 수
TOP_RESULTS_LIMIT = 20  # 텔레그램 전송 시 상위 N개만
PROGRESS_REPORT_INTERVAL = 100  # N개마다 진행상황 표시

# API 호출 제한
API_RATE_LIMIT_DELAY = 0.05  # API 호출 간 대기 시간 (초)


# ==================== 텔레그램 통신 ====================
def send_telegram_message_sync(message: str) -> bool:
    """
    텔레그램으로 메시지 전송 (동기 버전)

    Args:
        message: 전송할 메시지

    Returns:
        bool: 성공 여부
    """
    try:
        async def _send():
            bot = Bot(token=TELEGRAM_TOKEN)
            async with bot:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

        asyncio.run(_send())
        logger.info("텔레그램 메시지 전송 완료")
        return True
    except Exception as e:
        logger.error(f"텔레그램 전송 오류: {str(e)}", exc_info=True)
        return False


async def send_telegram_message(message: str) -> bool:
    """
    텔레그램으로 메시지 전송 (비동기 버전)

    Args:
        message: 전송할 메시지

    Returns:
        bool: 성공 여부
    """
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        async with bot:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info("텔레그램 메시지 전송 완료")
        return True
    except Exception as e:
        logger.error(f"텔레그램 전송 오류: {str(e)}", exc_info=True)
        return False


async def get_chat_id() -> Optional[int]:
    """
    봇에게 메시지를 보낸 사용자의 채팅 ID 가져오기

    Returns:
        Optional[int]: 채팅 ID (실패 시 None)
    """
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        async with bot:
            updates = await bot.get_updates()
            if updates:
                chat_id = updates[-1].message.chat.id
                logger.info(f"채팅 ID를 찾았습니다: {chat_id}")
                print(f"\n[OK] 채팅 ID를 찾았습니다: {chat_id}")
                print(f"[안내] .env 파일의 TELEGRAM_CHAT_ID를 다음으로 업데이트하세요: {chat_id}\n")
                return chat_id
            else:
                logger.warning("메시지가 없습니다.")
                print("\n[주의] 메시지가 없습니다.")
                print("[안내] 텔레그램에서 봇에게 아무 메시지나 보낸 후 다시 시도하세요.\n")
                return None
    except Exception as e:
        logger.error(f"채팅 ID 가져오기 오류: {str(e)}", exc_info=True)
        return None


# ==================== 종목 코드 처리 ====================
def normalize_stock_symbol(symbol: str) -> Tuple[str, str]:
    """
    종목코드 정규화 - 한국 주식의 경우 KOSPI/KOSDAQ 자동 판단

    Args:
        symbol: 종목 코드

    Returns:
        Tuple[str, str]: (정규화된 종목코드, 시장 구분)
    """
    symbol = symbol.strip().upper()

    # 숫자로만 이루어진 경우 (한국 주식)
    if symbol.isdigit():
        try:
            # KRX 전체 종목 리스트에서 확인
            df_krx = fdr.StockListing('KRX')
            if symbol in df_krx['Code'].values:
                stock_info = df_krx[df_krx['Code'] == symbol].iloc[0]
                market = stock_info['Market']
                name = stock_info['Name']
                logger.info(f"{symbol} ({name}, {market}) 종목을 찾았습니다.")
                return symbol, 'KRX'
            else:
                logger.warning(f"{symbol} 종목을 KRX에서 찾을 수 없습니다.")
                return symbol, 'KRX'
        except Exception as e:
            logger.warning(f"종목 확인 중 오류: {e}")
            return symbol, 'KRX'

    # 알파벳인 경우 (미국 주식 등)
    return symbol, 'US'


# ==================== 단일 종목 분석 ====================
def analyze_stock(symbol: str) -> str:
    """
    주식 데이터 분석

    Args:
        symbol: 종목 코드

    Returns:
        str: 분석 결과 메시지
    """
    try:
        # 종목코드 정규화
        symbol_code, market = normalize_stock_symbol(symbol)

        # 날짜 범위 설정
        end_date = datetime.now()
        start_date = end_date - timedelta(days=ANALYSIS_DAYS)

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
            except Exception:
                stock_name = symbol_code
        else:
            # 미국 주식
            hist = fdr.DataReader(symbol_code, start_date, end_date)
            currency = 'USD'
            stock_name = symbol_code

        if hist.empty:
            error_msg = f"[오류] {symbol_code} 종목의 데이터를 찾을 수 없습니다. 종목코드를 확인해주세요."
            logger.error(error_msg)
            return error_msg

        # 분석 데이터 계산
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[0]
        change_rate = ((current_price - prev_price) / prev_price) * 100

        # 이동평균 (데이터가 부족하면 가능한 만큼만)
        ma_days = min(MA_PERIOD, len(hist))
        ma = hist['Close'].tail(ma_days).mean()

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
{ANALYSIS_DAYS}일 전 가격: {price_format(prev_price)}
변동율: {change_rate:+.2f}%

{ma_days}일 이동평균: {price_format(ma)}
현재가 vs 이동평균: {price_format(current_price - ma)} ({((current_price - ma) / ma * 100):+.2f}%)
"""
        logger.info(f"{symbol_code} 분석 완료")
        return message

    except Exception as e:
        error_msg = f"[오류] 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


# ==================== 스케줄 작업 ====================
def job(symbol: Optional[str] = None):
    """
    스케줄된 작업

    Args:
        symbol: 종목 코드 (None이면 기본값 사용)
    """
    if symbol is None:
        symbol = STOCK_SYMBOL
    logger.info(f"스케줄 작업 시작 - 종목: {symbol}")
    message = analyze_stock(symbol)
    if message:
        send_telegram_message_sync(message)
    else:
        logger.error("분석 실패")


async def main(symbol: Optional[str] = None):
    """
    메인 함수 (비동기)

    Args:
        symbol: 종목 코드 (None이면 기본값 사용)
    """
    if symbol is None:
        symbol = STOCK_SYMBOL
    message = analyze_stock(symbol)
    if message:
        await send_telegram_message(message)


# ==================== 급등주 스크리닝 ====================
def analyze_single_stock(
    code: str,
    name: str,
    market: str,
    start_date: datetime,
    end_date: datetime,
    threshold: float
) -> Optional[Dict]:
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
        Optional[Dict]: 조건을 만족하면 종목 정보 딕셔너리, 아니면 None
    """
    try:
        # API 호출 제한
        time.sleep(API_RATE_LIMIT_DELAY)

        # 데이터 가져오기
        hist = fdr.DataReader(code, start_date, end_date)

        if len(hist) < MIN_DATA_DAYS:
            return None

        # 현재가와 이동평균 계산
        current_price = hist['Close'].iloc[-1]
        ma = hist['Close'].tail(MA_PERIOD).mean()

        # 상승률 계산
        diff_pct = ((current_price - ma) / ma) * 100

        if diff_pct >= threshold:
            return {
                '종목코드': code,
                '종목명': name,
                '시장': market,
                '현재가': int(current_price),
                f'{MA_PERIOD}일평균': int(ma),
                '상승률': round(diff_pct, 2),
                '거래량': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
            }
    except Exception as e:
        # 개별 종목 오류는 로깅만 하고 조용히 넘어감
        logger.debug(f"종목 {code} 분석 오류: {e}")

    return None


def screen_stocks(threshold: float = DEFAULT_THRESHOLD, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Dict]:
    """
    20일 이동평균 대비 현재가가 threshold% 이상 상승한 종목 찾기 (병렬 처리)

    Args:
        threshold: 상승률 기준
        max_workers: 병렬 처리 스레드 수

    Returns:
        List[Dict]: 조건을 만족하는 종목 리스트
    """
    logger.info(f"KRX 종목 스크리닝 시작 - 기준: {threshold}%, 스레드: {max_workers}개")
    print(f"[시작] KRX 종목 스크리닝 시작...")
    print(f"[조건] {MA_PERIOD}일 이동평균 대비 {threshold}% 이상 상승 종목")
    print(f"[설정] 병렬 처리 스레드: {max_workers}개")
    print("="*70)

    # KRX 전체 종목 리스트 가져오기
    try:
        df_krx = fdr.StockListing('KRX')
        logger.info(f"총 {len(df_krx)}개 종목 로드")
        print(f"[정보] 총 {len(df_krx)}개 종목 스캔 중...\n")
    except Exception as e:
        logger.error(f"종목 리스트 가져오기 실패: {e}")
        print(f"[오류] 종목 리스트 가져오기 실패: {e}")
        return []

    # 날짜 범위 설정
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DATA_FETCH_DAYS)

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
                    logger.info(f"발견: {code} {name} - 상승률: {result['상승률']}%")
                    print(f"[발견] {code} {name} ({market}) - 현재가: {result['현재가']:,}원, 상승률: {result['상승률']}%")
            except Exception as e:
                logger.debug(f"종목 {code} 처리 오류: {e}")

            # 진행상황 표시
            if completed_count % PROGRESS_REPORT_INTERVAL == 0:
                progress = (completed_count / total_count) * 100
                logger.info(f"진행: {completed_count}/{total_count} ({progress:.1f}%)")
                print(f"[진행] {completed_count}/{total_count} 종목 분석 완료 ({progress:.1f}%)...")

    logger.info(f"스크리닝 완료 - 발견: {len(results)}개")
    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.\n")

    return results


def format_screening_results(results: List[Dict], threshold: float) -> str:
    """
    스크리닝 결과를 텔레그램 메시지 형식으로 포맷

    Args:
        results: 스크리닝 결과 리스트
        threshold: 사용된 상승률 기준

    Returns:
        str: 포맷된 메시지
    """
    if not results:
        return f"{MA_PERIOD}일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

    # 상승률 순으로 정렬
    results_sorted = sorted(results, key=lambda x: x['상승률'], reverse=True)

    # 상위 N개만 선택
    top_results = results_sorted[:TOP_RESULTS_LIMIT]

    message = f"""
📊 주식 스크리닝 결과
조건: {MA_PERIOD}일 이동평균 대비 {threshold}% 이상 상승
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}
총 발견: {len(results)}개 종목

[상위 {len(top_results)}개 종목]
"""

    for i, stock in enumerate(top_results, 1):
        message += f"""
{i}. {stock['종목명']} ({stock['종목코드']})
   시장: {stock['시장']}
   현재가: {stock['현재가']:,}원
   {MA_PERIOD}일평균: {stock[f'{MA_PERIOD}일평균']:,}원
   상승률: +{stock['상승률']}%
   거래량: {stock['거래량']:,}주
"""

    if len(results) > TOP_RESULTS_LIMIT:
        message += f"\n* 상위 {TOP_RESULTS_LIMIT}개만 표시 (전체 {len(results)}개)"

    return message


# ==================== 사용자 입력 함수 ====================
def get_schedule_time() -> str:
    """
    사용자로부터 스케줄 시간 입력받기

    Returns:
        str: HH:MM 형식의 시간
    """
    while True:
        time_input = input("[입력] 실행 시간을 입력하세요 (HH:MM 형식, 예: 09:00): ").strip()
        try:
            datetime.strptime(time_input, "%H:%M")
            return time_input
        except ValueError:
            print("[오류] 올바른 형식이 아닙니다. HH:MM 형식으로 입력해주세요.")


def get_stock_symbol() -> str:
    """
    사용자로부터 종목코드 입력받기

    Returns:
        str: 종목 코드
    """
    print("\n[입력] 종목코드 입력")
    print("=" * 50)
    print("예시:")
    print("  [한국 주식]")
    print("  - 삼성전자: 005930")
    print("  - 카카오: 035720")
    print("  - NAVER: 035420")
    print("  - 에코프로비엠: 247540")
    print("")
    print("  [미국 주식]")
    print("  - 애플: AAPL")
    print("  - 테슬라: TSLA")
    print("  - 엔비디아: NVDA")
    print("=" * 50)
    symbol = input(f"종목코드를 입력하세요 (기본값: {STOCK_SYMBOL}): ").strip()
    if not symbol:
        symbol = STOCK_SYMBOL
    return symbol


def get_threshold_input() -> float:
    """
    사용자로부터 상승률 기준 입력받기

    Returns:
        float: 상승률 기준 (%)
    """
    threshold_input = input(f"[입력] 상승률 기준을 입력하세요 (기본값: {DEFAULT_THRESHOLD}%): ").strip()
    try:
        threshold = float(threshold_input) if threshold_input else DEFAULT_THRESHOLD
        return threshold
    except ValueError:
        logger.warning(f"잘못된 입력. 기본값 {DEFAULT_THRESHOLD}% 사용")
        print(f"[오류] 잘못된 입력입니다. 기본값 {DEFAULT_THRESHOLD}%를 사용합니다.")
        return DEFAULT_THRESHOLD


def get_workers_input() -> int:
    """
    사용자로부터 병렬 처리 스레드 수 입력받기

    Returns:
        int: 스레드 수 (MIN_WORKERS ~ MAX_WORKERS 범위)
    """
    workers_input = input(f"[입력] 병렬 처리 스레드 수 (기본값: {DEFAULT_MAX_WORKERS}, 권장: 10-30): ").strip()
    try:
        max_workers = int(workers_input) if workers_input else DEFAULT_MAX_WORKERS
        max_workers = max(MIN_WORKERS, min(MAX_WORKERS, max_workers))
        return max_workers
    except ValueError:
        logger.warning(f"잘못된 입력. 기본값 {DEFAULT_MAX_WORKERS} 사용")
        print(f"[오류] 잘못된 입력입니다. 기본값 {DEFAULT_MAX_WORKERS}를 사용합니다.")
        return DEFAULT_MAX_WORKERS


# ==================== 스케줄러 ====================
def start_scheduler_with_job(schedule_time: str, symbol: str):
    """
    스케줄러 시작 (중복 코드 제거용 통합 함수)

    Args:
        schedule_time: 실행 시간 (HH:MM)
        symbol: 종목 코드
    """
    logger.info(f"스케줄러 시작 - 종목: {symbol}, 시간: {schedule_time}")
    print(f"\n[스케줄] {symbol} 종목을 매일 {schedule_time}에 분석합니다.\n")
    schedule.every().day.at(schedule_time).do(job, symbol=symbol)
    print("[대기중] 스케줄러가 대기 중입니다... (Ctrl+C로 종료)\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")
        print("\n\n[종료] 스케줄러가 종료되었습니다.")


# ==================== 메뉴 ====================
def show_menu():
    """메뉴 표시"""
    print("\n" + "="*50)
    print("[시스템] 주식 분석 및 텔레그램 알림")
    print("="*50)
    print("0. 채팅 ID 가져오기 (최초 설정)")
    print("1. 지금 바로 분석 실행")
    print("2. 스케줄러 시작 (시간 입력)")
    print(f"3. 스케줄러 시작 (기본 시간: {SCHEDULE_TIME})")
    print(f"4. 급등주 스크리닝 ({MA_PERIOD}일 이평선 돌파)")
    print("5. 종료")
    print("="*50 + "\n")


def handle_chat_id_setup():
    """채팅 ID 설정 처리"""
    print("\n[실행] 채팅 ID를 가져오는 중...\n")
    print("[안내] 먼저 텔레그램에서 봇(@crawlTickerL_bot)에게 '/start' 또는 아무 메시지나 보내세요!\n")
    input("메시지를 보냈으면 Enter를 눌러주세요...")
    chat_id = asyncio.run(get_chat_id())
    if chat_id:
        # .env 파일 업데이트
        try:
            with open('.env', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            with open('.env', 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.startswith('TELEGRAM_CHAT_ID='):
                        f.write(f'TELEGRAM_CHAT_ID={chat_id}\n')
                    else:
                        f.write(line)
            logger.info(".env 파일 업데이트 완료")
            print("[OK] .env 파일이 업데이트되었습니다!")
            print("[주의] 프로그램을 다시 시작해주세요.\n")
        except Exception as e:
            logger.error(f".env 파일 업데이트 실패: {e}")
            print(f"[오류] .env 파일 업데이트 실패: {e}")


def handle_immediate_analysis():
    """즉시 분석 실행 처리"""
    symbol = get_stock_symbol()
    logger.info(f"즉시 분석 실행 - 종목: {symbol}")
    print(f"\n[실행] {symbol} 분석을 실행 중입니다...\n")
    asyncio.run(main(symbol))


def handle_scheduler_custom_time():
    """커스텀 시간 스케줄러 처리"""
    symbol = get_stock_symbol()
    schedule_time = get_schedule_time()
    start_scheduler_with_job(schedule_time, symbol)


def handle_scheduler_default_time():
    """기본 시간 스케줄러 처리"""
    symbol = get_stock_symbol()
    start_scheduler_with_job(SCHEDULE_TIME, symbol)


def handle_stock_screening():
    """급등주 스크리닝 처리"""
    logger.info("급등주 스크리닝 시작")
    print("\n[실행] 급등주 스크리닝을 시작합니다...\n")

    # 사용자 입력
    threshold = get_threshold_input()
    max_workers = get_workers_input()

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
        logger.info(f"결과 저장: {filename}")
        print(f"[저장] {filename} 파일로 저장되었습니다.")


# ==================== 메인 실행 ====================
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 명령행 인자로 실행
        if sys.argv[1] == "now":
            # python stock_analyzer2_improved.py now [종목코드]
            symbol = sys.argv[2] if len(sys.argv) > 2 else STOCK_SYMBOL
            logger.info(f"명령행 실행 (now) - 종목: {symbol}")
            asyncio.run(main(symbol))
        elif sys.argv[1] == "schedule":
            # python stock_analyzer2_improved.py schedule [시간] [종목코드]
            schedule_time = sys.argv[2] if len(sys.argv) > 2 else SCHEDULE_TIME
            symbol = sys.argv[3] if len(sys.argv) > 3 else STOCK_SYMBOL
            logger.info(f"명령행 실행 (schedule) - 종목: {symbol}, 시간: {schedule_time}")
            start_scheduler_with_job(schedule_time, symbol)
    else:
        # 인터랙티브 메뉴
        logger.info("인터랙티브 모드 시작")
        while True:
            show_menu()
            choice = input("선택: ").strip()

            if choice == "0":
                handle_chat_id_setup()
            elif choice == "1":
                handle_immediate_analysis()
            elif choice == "2":
                handle_scheduler_custom_time()
            elif choice == "3":
                handle_scheduler_default_time()
            elif choice == "4":
                handle_stock_screening()
            elif choice == "5":
                logger.info("프로그램 종료")
                print("[종료] 프로그램을 종료합니다.")
                break
            else:
                print("[오류] 잘못된 선택입니다. 다시 시도해주세요.\n")
