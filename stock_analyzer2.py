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
import requests
from bs4 import BeautifulSoup
import sqlite3

# 환경변수 로드
load_dotenv()

# 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
STOCK_SYMBOL = "005930"  # 삼성전자 (자동으로 KOSPI/KOSDAQ 판단)
SCHEDULE_TIME = "09:00"  # 기본 실행 시간 (24시간 형식)
DB_FILE = "stock_history.db"  # SQLite DB 파일명

# ==================== SQLite DB 관리 ====================
def init_db():
    """DB 초기화 및 테이블 생성"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 급등주 이력 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_history (
            종목코드 TEXT PRIMARY KEY,
            종목명 TEXT,
            테마명 TEXT,
            최초발견일 TEXT,
            최종발견일 TEXT,
            발견횟수 INTEGER DEFAULT 1,
            연속발견횟수 INTEGER DEFAULT 1,
            최대상승률 REAL,
            최대가격 INTEGER,
            생성일시 TEXT,
            수정일시 TEXT
        )
    ''')

    # 일별 발견 기록 테이블 (상세 이력)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            종목코드 TEXT,
            종목명 TEXT,
            테마명 TEXT,
            발견일 TEXT,
            현재가 INTEGER,
            상승률 REAL,
            거래량 INTEGER,
            기록일시 TEXT,
            FOREIGN KEY (종목코드) REFERENCES stock_history(종목코드)
        )
    ''')

    # 종목 처리 상태 테이블 (체크포인트)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_status (
            종목코드 TEXT PRIMARY KEY,
            종목명 TEXT,
            테마명 TEXT,
            상태 TEXT,
            배치번호 INTEGER,
            시도횟수 INTEGER DEFAULT 0,
            최종시도일시 TEXT,
            오류메시지 TEXT,
            생성일시 TEXT,
            수정일시 TEXT
        )
    ''')

    conn.commit()
    conn.close()


def update_stock_history(stock_data):
    """
    종목 이력 업데이트

    Args:
        stock_data: 종목 정보 딕셔너리

    Returns:
        dict: 업데이트된 이력 정보 (최초발견일, 발견횟수, 연속발견횟수, 신규여부)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    code = stock_data['종목코드']
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 기존 데이터 조회
    cursor.execute('SELECT * FROM stock_history WHERE 종목코드 = ?', (code,))
    existing = cursor.fetchone()

    is_new = False
    consecutive_count = 1
    total_count = 1
    first_found = today

    if existing:
        # 기존 종목 업데이트
        col_names = [desc[0] for desc in cursor.description]
        existing_dict = dict(zip(col_names, existing))

        total_count = existing_dict['발견횟수'] + 1
        last_found = existing_dict['최종발견일']
        first_found = existing_dict['최초발견일']

        # 연속 발견 체크 (마지막 발견일이 어제 또는 오늘인지)
        last_date = datetime.strptime(last_found, '%Y-%m-%d')
        today_date = datetime.strptime(today, '%Y-%m-%d')
        days_diff = (today_date - last_date).days

        if days_diff == 0:
            # 같은 날 재발견 (연속발견횟수 유지)
            consecutive_count = existing_dict['연속발견횟수']
        elif days_diff == 1:
            # 하루 연속 발견
            consecutive_count = existing_dict['연속발견횟수'] + 1
        else:
            # 며칠 만에 재발견 (연속 끊김)
            consecutive_count = 1

        # 최대값 업데이트
        max_rate = max(existing_dict['최대상승률'], stock_data['상승률'])
        max_price = max(existing_dict['최대가격'], stock_data['현재가'])

        cursor.execute('''
            UPDATE stock_history
            SET 종목명 = ?, 테마명 = ?, 최종발견일 = ?,
                발견횟수 = ?, 연속발견횟수 = ?,
                최대상승률 = ?, 최대가격 = ?, 수정일시 = ?
            WHERE 종목코드 = ?
        ''', (stock_data['종목명'], stock_data.get('테마명', ''), today,
              total_count, consecutive_count, max_rate, max_price, now, code))

    else:
        # 신규 종목 등록
        is_new = True
        cursor.execute('''
            INSERT INTO stock_history
            (종목코드, 종목명, 테마명, 최초발견일, 최종발견일,
             발견횟수, 연속발견횟수, 최대상승률, 최대가격, 생성일시, 수정일시)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, stock_data['종목명'], stock_data.get('테마명', ''),
              today, today, 1, 1, stock_data['상승률'],
              stock_data['현재가'], now, now))

    # 일별 기록 추가
    cursor.execute('''
        INSERT INTO daily_records
        (종목코드, 종목명, 테마명, 발견일, 현재가, 상승률, 거래량, 기록일시)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (code, stock_data['종목명'], stock_data.get('테마명', ''),
          today, stock_data['현재가'], stock_data['상승률'],
          stock_data['거래량'], now))

    conn.commit()
    conn.close()

    return {
        '신규여부': is_new,
        '최초발견일': first_found,
        '발견횟수': total_count,
        '연속발견횟수': consecutive_count
    }


def get_stock_history(code):
    """종목 이력 조회"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM stock_history WHERE 종목코드 = ?', (code,))
    result = cursor.fetchone()

    conn.close()

    if result:
        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, result))
    return None


def get_statistics():
    """전체 통계 조회"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    # 오늘 발견된 종목 수
    cursor.execute('SELECT COUNT(*) FROM stock_history WHERE 최종발견일 = ?', (today,))
    today_count = cursor.fetchone()[0]

    # 이번주 신규 발견 종목 수
    cursor.execute('SELECT COUNT(*) FROM stock_history WHERE 최초발견일 >= ?', (week_ago,))
    new_this_week = cursor.fetchone()[0]

    # 5회 이상 연속 발견 종목 수
    cursor.execute('SELECT COUNT(*) FROM stock_history WHERE 연속발견횟수 >= 5')
    hot_stocks = cursor.fetchone()[0]

    conn.close()

    return {
        '오늘발견': today_count,
        '이번주신규': new_this_week,
        '연속5회이상': hot_stocks
    }


# ==================== 체크포인트 관리 ====================
def update_processing_status(code, name, theme, status, batch_num, error_msg=None):
    """종목 처리 상태 업데이트"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('SELECT 시도횟수 FROM processing_status WHERE 종목코드 = ?', (code,))
    existing = cursor.fetchone()

    if existing:
        retry_count = existing[0] + 1 if status == 'failed' else existing[0]
        cursor.execute('''
            UPDATE processing_status
            SET 종목명 = ?, 테마명 = ?, 상태 = ?, 배치번호 = ?,
                시도횟수 = ?, 최종시도일시 = ?, 오류메시지 = ?, 수정일시 = ?
            WHERE 종목코드 = ?
        ''', (name, theme, status, batch_num, retry_count, now, error_msg, now, code))
    else:
        cursor.execute('''
            INSERT INTO processing_status
            (종목코드, 종목명, 테마명, 상태, 배치번호, 시도횟수, 최종시도일시, 오류메시지, 생성일시, 수정일시)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, theme, status, batch_num, 1 if status == 'failed' else 0, now, error_msg, now, now))

    conn.commit()
    conn.close()


def get_pending_stocks(csv_file):
    """미처리 또는 실패한 종목 가져오기"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # CSV에서 전체 종목 읽기
    df = pd.read_csv(csv_file, encoding='utf-8-sig')

    # 완료된 종목 조회
    cursor.execute('SELECT 종목코드 FROM processing_status WHERE 상태 = ?', ('completed',))
    completed_codes = set(row[0] for row in cursor.fetchall())

    # 실패한 종목 조회 (3회 미만 시도)
    cursor.execute('SELECT 종목코드 FROM processing_status WHERE 상태 = ? AND 시도횟수 < 3', ('failed',))
    retry_codes = set(row[0] for row in cursor.fetchall())

    conn.close()

    # 미처리 종목 필터링
    pending_df = df[~df['종목코드'].isin(completed_codes)]

    return pending_df, len(completed_codes), retry_codes


def clear_processing_status():
    """처리 상태 초기화 (새로운 스크리닝 시작 시)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM processing_status')
    conn.commit()
    conn.close()


def get_processing_statistics():
    """처리 통계 조회"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM processing_status WHERE 상태 = ?', ('completed',))
    completed = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM processing_status WHERE 상태 = ?', ('failed',))
    failed = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM processing_status WHERE 상태 = ?', ('processing',))
    processing = cursor.fetchone()[0]

    conn.close()

    return {
        'completed': completed,
        'failed': failed,
        'processing': processing
    }


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

def analyze_single_stock(code, name, market, start_date, end_date, threshold, volume_multiplier=1.0):
    """
    단일 종목 분석 (병렬 처리용)

    Args:
        code: 종목 코드
        name: 종목명
        market: 시장 (KOSPI/KOSDAQ/KONEX)
        start_date: 시작 날짜
        end_date: 종료 날짜
        threshold: 상승률 기준
        volume_multiplier: 거래량 배수 (기본값: 1.0, 예: 2.0이면 평균의 2배)

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

        # 상승률 조건 체크
        if diff_pct < threshold:
            return None

        # 거래량 체크 (Volume 컬럼이 있는 경우만)
        if 'Volume' in hist.columns:
            current_volume = hist['Volume'].iloc[-1]
            avg_volume_20 = hist['Volume'].tail(20).mean()

            # 거래량 배수 조건 체크
            if volume_multiplier > 1.0 and current_volume < (avg_volume_20 * volume_multiplier):
                return None

            volume_ratio = (current_volume / avg_volume_20) if avg_volume_20 > 0 else 0
        else:
            current_volume = 0
            avg_volume_20 = 0
            volume_ratio = 0

        return {
            '종목코드': code,
            '종목명': name,
            '시장': market,
            '현재가': int(current_price),
            '20일평균': int(ma_20),
            '상승률': round(diff_pct, 2),
            '거래량': int(current_volume),
            '평균거래량': int(avg_volume_20),
            '거래량비율': round(volume_ratio, 2)
        }
    except KeyboardInterrupt:
        raise  # KeyboardInterrupt는 상위로 전파
    except Exception as e:
        # 오류 로깅 (디버깅용)
        # print(f"[DEBUG] {code} 오류: {type(e).__name__}: {str(e)}")
        pass

    return None

def screen_stocks(threshold=5.0, max_workers=20, volume_multiplier=1.0):
    """
    20일 이동평균 대비 현재가가 threshold% 이상 상승한 종목 찾기 (병렬 처리)
    """
    init_db()

    print("[시작] KRX 종목 스크리닝 시작...")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
    # ✅ 추가: 거래량 조건 주석
    if volume_multiplier > 1.0:
        print(f"[조건] 20일 평균 거래량의 {volume_multiplier}배 이상")
    print(f"[설정] 병렬 처리 스레드: {max_workers}개")
    print("="*70)

    try:
        df_krx = fdr.StockListing('KRX')
        df_krx = df_krx[df_krx['Market'] != 'KONEX']
        print(f"[정보] 총 {len(df_krx)}개 종목 스캔 중...\n")
    except Exception as e:
        print(f"[오류] 종목 리스트 가져오기 실패: {e}")
        return []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=50)

    results = []
    completed_count = 0
    error_count = 0
    total_count = len(df_krx)
    lock = threading.Lock()
    
    executor = ThreadPoolExecutor(max_workers=max_workers)
    
    print(f"[DEBUG] executor 생성 완료 (workers={max_workers})")
    print(f"[DEBUG] future_to_stock 생성 시작...")
    
    try:
        # 모든 작업 제출
        future_to_stock = {
            executor.submit(
                analyze_single_stock,
                row['Code'], row['Name'], row['Market'],
                start_date, end_date, threshold, volume_multiplier
            ): (row['Code'], row['Name'], row['Market'])
            for _, row in df_krx.iterrows()
        }
        
        print(f"[DEBUG] future_to_stock 생성 완료: {len(future_to_stock)}개 종목")
        print(f"[DEBUG] as_completed() 루프 시작...")

        # ✅ 수정: timeout을 더 길게 설정하고, 타임아웃 처리 개선
        timeout_per_batch = 60  # 배치당 60초
        
        for future in as_completed(future_to_stock, timeout=timeout_per_batch):
            code, name, market = future_to_stock[future]
            completed_count += 1

            try:
                # ✅ 수정: timeout을 개별 future에서 제거 (이미 as_completed에서 처리)
                result = future.result()
                
                if result:
                    history = update_stock_history(result)
                    result.update(history)

                    with lock:
                        results.append(result)

                    status_icon = "🆕신규" if history['신규여부'] else f"({history['발견횟수']}회째)"
                    if history['연속발견횟수'] >= 5:
                        status_icon = f"🔥{history['연속발견횟수']}회 연속"

                    volume_info = f", 거래량: {result.get('거래량비율', 0)}배" if result.get('거래량비율', 0) > 0 else ""
                    print(f"[발견] {code} {name} ({market}) - {result['현재가']:,}원, {result['상승률']}% {status_icon}{volume_info}")
                    
            except TimeoutError:
                with lock:
                    error_count += 1
                print(f"[타임아웃] {code} {name}")
                
            except KeyboardInterrupt:
                print(f"[DEBUG] KeyboardInterrupt 발생!")
                raise
                
            except Exception as e:
                with lock:
                    error_count += 1
                print(f"[DEBUG] 예외 발생: {code} {name} - {type(e).__name__}: {str(e)[:100]}")

            # 진행상황 표시
            if completed_count % 100 == 0:
                remaining = total_count - completed_count
                print(f"[진행] {completed_count}/{total_count} 완료 (남은 것: {remaining}개)... (발견: {len(results)}개, 오류: {error_count}개)")

        print(f"[DEBUG] as_completed() 루프 종료, 완료: {completed_count}/{total_count}")

    except TimeoutError as te:
        print(f"\n[경고] 타임아웃 발생!")
        print(f"[진행] {completed_count}/{total_count} 종목까지 분석 완료")
        print(f"[결과] 지금까지 {len(results)}개 종목 발견")
        print(f"[DEBUG] TimeoutError: {str(te)}")
        
    except KeyboardInterrupt:
        print(f"\n[중단] {completed_count}/{total_count} 종목까지 분석 완료")
        print(f"[결과] 지금까지 {len(results)}개 종목 발견")
        print(f"[DEBUG] KeyboardInterrupt 캐치됨")
        
    except Exception as e:
        print(f"[DEBUG] 예상치 못한 예외: {type(e).__name__}: {str(e)}")
        
    finally:
        # ✅ 수정: executor 반드시 정리
        print(f"[DEBUG] executor.shutdown() 호출 시작...")
        print(f"[DEBUG] 남은 future 개수: {total_count - completed_count}")
        executor.shutdown(wait=False, cancel_futures=True)  # wait=False로 변경
        print(f"[DEBUG] executor.shutdown() 완료")

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.\n")
    print(f"[DEBUG] screen_stocks() 함수 종료")

    return results


def format_screening_results(results, threshold):
    """스크리닝 결과를 텔레그램 메시지 형식으로 포맷"""
    if not results:
        return f"20일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

    # 통계 조회
    stats = get_statistics()

    # 상승률 순으로 정렬
    results_sorted = sorted(results, key=lambda x: x['상승률'], reverse=True)

    # 상위 20개만 선택
    top_results = results_sorted[:20]

    # 신규 종목과 재발견 종목 분리
    new_stocks = [s for s in results if s.get('신규여부', False)]
    hot_stocks = [s for s in results if s.get('연속발견횟수', 0) >= 5]

    message = f"""
📈 주식 스크리닝 결과
조건: 20일 이동평균 대비 {threshold}% 이상 상승
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📊 통계
• 총 발견: {len(results)}개 종목
• 🆕 신규: {len(new_stocks)}개
• 🔥 연속5회 이상: {len(hot_stocks)}개
• 이번주 신규: {stats['이번주신규']}개

[상위 {len(top_results)}개 종목]
"""

    for i, stock in enumerate(top_results, 1):
        # 상태 아이콘
        status = ""
        if stock.get('신규여부', False):
            status = " 🆕신규"
        elif stock.get('연속발견횟수', 0) >= 5:
            status = f" 🔥{stock['연속발견횟수']}"
        elif stock.get('발견횟수', 1) > 1:
            status = f" ({stock['발견횟수']})"

        # 거래량 정보 구성
        volume_ratio = stock.get('거래량비율', 0)
        volume_text = f"   거래량: {stock['거래량']:,}주"
        if volume_ratio > 0:
            volume_text += f" (평균 대비 {volume_ratio}배)"

        message += f"""
{i}. {stock['종목명']} ({stock['종목코드']}){status}
   시장: {stock['시장']}
   현재가: {stock['현재가']:,}원
   20일평균: {stock['20일평균']:,}원
   상승률: +{stock['상승률']}%
{volume_text}
"""
        if stock.get('최초발견일'):
            message += f"   최초발견: {stock['최초발견일']}\n"

    if len(results) > 20:
        message += f"\n* 상위 20개만 표시 (전체 {len(results)}개)"

    return message

# ==================== 네이버 테마 크롤링 ====================
def crawl_theme_page(page=1):
    """
    네이버 금융 테마별 시세 페이지 크롤링

    Args:
        page (int): 페이지 번호

    Returns:
        list: 테마 정보 딕셔너리 리스트
    """
    url = f'https://finance.naver.com/sise/theme.naver?&page={page}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://finance.naver.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 테마 테이블 찾기 - 여러 방법 시도
        table = soup.find('table', class_='type_1')

        if not table:
            # class가 없는 경우도 시도
            tables = soup.find_all('table')
            for t in tables:
                if 'type_1' in str(t.get('class', [])) or 'theme' in str(t.get('class', [])):
                    table = t
                    break

        if not table:
            print(f"[오류] 페이지 {page}에서 테이블을 찾을 수 없습니다.")
            return []

        themes = []
        # tbody 태그가 없을 수도 있으므로 직접 tr 찾기
        rows = table.find_all('tr')

        for row in rows:
            # 빈 행이나 구분선 행 건너뛰기
            if 'blank' in row.get('class', []) or 'division_line' in row.get('class', []):
                continue

            cols = row.find_all('td')

            # 데이터가 있는 행만 처리
            if len(cols) >= 8:
                try:
                    # 테마명과 테마 번호 추출
                    theme_link = cols[0].find('a')
                    theme_name = theme_link.text.strip() if theme_link else ''
                    theme_url = theme_link.get('href', '') if theme_link else ''

                    # 테마 번호 추출
                    theme_no = ''
                    if 'no=' in theme_url:
                        theme_no = theme_url.split('no=')[1].split('&')[0]

                    # 전일대비 등락률
                    change_rate = cols[1].text.strip().replace('\n', '').replace('\t', '')

                    # 최근 3일 등락률
                    recent_3days = cols[2].text.strip().replace('\n', '').replace('\t', '')

                    # 등락현황
                    up_count = cols[3].text.strip()
                    same_count = cols[4].text.strip()
                    down_count = cols[5].text.strip()

                    # 주도주 1, 2
                    leader1_link = cols[6].find('a')
                    leader1_name = leader1_link.text.strip() if leader1_link else ''
                    leader1_code = ''
                    if leader1_link and 'code=' in leader1_link.get('href', ''):
                        leader1_code = leader1_link.get('href').split('code=')[1].split('&')[0]

                    leader2_link = cols[7].find('a')
                    leader2_name = leader2_link.text.strip() if leader2_link else ''
                    leader2_code = ''
                    if leader2_link and 'code=' in leader2_link.get('href', ''):
                        leader2_code = leader2_link.get('href').split('code=')[1].split('&')[0]

                    theme_data = {
                        '테마번호': theme_no,
                        '테마명': theme_name,
                        '전일대비': change_rate,
                        '최근3일등락률': recent_3days,
                        '상승': up_count,
                        '보합': same_count,
                        '하락': down_count,
                        '주도주1': leader1_name,
                        '주도주1코드': leader1_code,
                        '주도주2': leader2_name,
                        '주도주2코드': leader2_code,
                        '페이지': page
                    }

                    themes.append(theme_data)

                except Exception as e:
                    print(f"[오류] 행 파싱 중 오류: {e}")
                    continue

        return themes

    except Exception as e:
        print(f"[오류] 페이지 {page} 크롤링 중 오류: {e}")
        return []


def crawl_all_themes(max_pages=7):
    """
    모든 테마 페이지 크롤링

    Args:
        max_pages (int): 크롤링할 최대 페이지 수 (기본값: 7)

    Returns:
        DataFrame: 모든 테마 정보가 담긴 데이터프레임
    """
    all_themes = []

    for page in range(1, max_pages + 1):
        print(f"[진행] {page}/{max_pages} 페이지 크롤링 중...")
        themes = crawl_theme_page(page)
        all_themes.extend(themes)

        # 서버 부하 방지를 위한 대기
        if page < max_pages:
            time.sleep(1)

    df = pd.DataFrame(all_themes)
    print(f"\n[완료] 총 {len(df)}개의 테마 정보를 수집했습니다.")

    return df


def format_theme_results(df, top_n=10):
    """
    테마 크롤링 결과를 텔레그램 메시지 형식으로 포맷

    Args:
        df: 테마 데이터프레임
        top_n: 상위 N개 테마만 표시

    Returns:
        str: 포맷된 메시지
    """
    if df.empty:
        return "테마 데이터를 가져올 수 없습니다."

    # 전일대비를 숫자로 변환하여 정렬
    df_copy = df.copy()
    df_copy['등락률_숫자'] = df_copy['전일대비'].str.replace('%', '').str.replace('+', '').astype(float)
    df_sorted = df_copy.sort_values('등락률_숫자', ascending=False)

    # 상위 N개만 선택
    top_themes = df_sorted.head(top_n)

    message = f"""
📊 네이버 금융 테마별 시세
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}
총 테마 수: {len(df)}개

[상위 {len(top_themes)}개 급등 테마]
"""

    for i, (_, theme) in enumerate(top_themes.iterrows(), 1):
        message += f"""
{i}. {theme['테마명']}
   전일대비: {theme['전일대비']}
   최근3일: {theme['최근3일등락률']}
   상승: {theme['상승']}개 / 보합: {theme['보합']}개 / 하락: {theme['하락']}개
   주도주: {theme['주도주1']} ({theme['주도주1코드']})
"""

    if len(df) > top_n:
        message += f"\n* 상위 {top_n}개만 표시 (전체 {len(df)}개)"

    return message


def handle_theme_crawling():
    """네이버 테마 크롤링 실행 처리"""
    print("\n[실행] 네이버 금융 테마 크롤링을 시작합니다...\n")

    # 페이지 수 입력
    pages_input = input("[입력] 크롤링할 페이지 수 (기본값: 7, 전체 약 267개 테마): ").strip()
    try:
        max_pages = int(pages_input) if pages_input else 7
        max_pages = max(1, min(10, max_pages))  # 1-10 범위로 제한
    except ValueError:
        print("[오류] 잘못된 입력입니다. 기본값 7을 사용합니다.")
        max_pages = 7

    print(f"\n[설정] {max_pages}페이지 크롤링\n")

    # 크롤링 실행
    df_themes = crawl_all_themes(max_pages)

    if df_themes.empty:
        print("[오류] 크롤링된 데이터가 없습니다.")
        return

    # 결과 미리보기
    print("\n" + "="*70)
    print("[상위 10개 테마]")
    print("="*70)

    # 등락률 순으로 정렬하여 상위 10개 출력
    df_copy = df_themes.copy()
    df_copy['등락률_숫자'] = df_copy['전일대비'].str.replace('%', '').str.replace('+', '').astype(float)
    df_sorted = df_copy.sort_values('등락률_숫자', ascending=False)

    print(df_sorted[['테마명', '전일대비', '최근3일등락률', '상승', '하락', '주도주1']].head(10).to_string(index=False))

    # 텔레그램 메시지 포맷
    message = format_theme_results(df_themes, top_n=10)

    # 콘솔 출력
    print("\n" + "="*70)
    print("[텔레그램 전송 메시지 미리보기]")
    print("="*70)
    print(message)

    # 텔레그램 전송
    send_choice = input("\n텔레그램으로 전송하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if send_choice != 'n':
        print("\n[전송] 텔레그램으로 전송 중...")
        success = send_telegram_message_sync(message)
        if success:
            print("[OK] 텔레그램 전송 완료!")
        else:
            print("[오류] 텔레그램 전송 실패")

    # CSV 파일 저장
    save_choice = input("\nCSV 파일로 저장하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if save_choice != 'n':
        filename = f"naver_themes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_themes.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장] {filename} 파일로 저장되었습니다.")


def analyze_theme_stock(code, name, theme_name, start_date, end_date, threshold):
    """
    테마별 단일 종목 분석 (병렬 처리용)

    Args:
        code: 종목 코드
        name: 종목명
        theme_name: 테마명
        start_date: 시작 날짜
        end_date: 종료 날짜
        threshold: 상승률 기준

    Returns:
        dict or None: 조건을 만족하면 종목 정보 딕셔너리, 아니면 None
    """
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            # 데이터 가져오기 (타임아웃 포함)
            hist = fdr.DataReader(code, start_date, end_date)

            if hist is None or hist.empty or len(hist) < 20:
                return None

            # 현재가와 20일 이동평균 계산
            current_price = hist['Close'].iloc[-1]
            ma_20 = hist['Close'].tail(20).mean()

            # 상승률 계산
            diff_pct = ((current_price - ma_20) / ma_20) * 100

            if diff_pct >= threshold:
                return {
                    '테마명': theme_name,
                    '종목코드': code,
                    '종목명': name,
                    '현재가': int(current_price),
                    '20일평균': int(ma_20),
                    '상승률': round(diff_pct, 2),
                    '거래량': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
                }
            return None

        except KeyboardInterrupt:
            raise
        except Exception as e:
            # 마지막 시도가 아니면 재시도
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            # 마지막 시도에서도 실패하면 None 반환 (에러 로그는 옵션)
            # print(f"[오류] {code} {name}: {str(e)}")
            return None

    return None


def screen_theme_stocks_from_csv(csv_file, threshold=5.0, max_workers=20):
    """
    CSV 파일에서 테마별 종목을 읽어 급등주 스크리닝 (병렬 처리)

    Args:
        csv_file: 테마 종목 CSV 파일 경로
        threshold: 상승률 기준 (기본값: 5.0%)
        max_workers: 병렬 처리 스레드 수 (기본값: 20)

    Returns:
        list: 조건을 만족하는 종목 리스트
    """
    # DB 초기화
    init_db()

    print(f"[시작] CSV 파일에서 테마별 종목 스크리닝 시작...")
    print(f"[파일] {csv_file}")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
    print(f"[설정] 병렬 처리 스레드: {max_workers}개")
    print("="*70)

    # CSV 파일 읽기
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"[정보] CSV에서 총 {len(df)}개 종목 로드 완료\n")

        # 필요한 컬럼 확인
        required_cols = ['테마명', '종목코드', '종목명']
        for col in required_cols:
            if col not in df.columns:
                print(f"[오류] CSV 파일에 '{col}' 컬럼이 없습니다.")
                return []

    except FileNotFoundError:
        print(f"[오류] 파일을 찾을 수 없습니다: {csv_file}")
        return []
    except Exception as e:
        print(f"[오류] CSV 파일 읽기 실패: {e}")
        return []

    # 날짜 범위 설정 (최근 50일)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=50)

    results = []
    completed_count = 0
    error_count = 0
    total_count = len(df)
    lock = threading.Lock()

    # 병렬 처리로 종목 분석
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 종목에 대해 작업 제출
        future_to_stock = {
            executor.submit(
                analyze_theme_stock,
                row['종목코드'],
                row['종목명'],
                row['테마명'],
                start_date,
                end_date,
                threshold
            ): (row['종목코드'], row['종목명'], row['테마명'])
            for _, row in df.iterrows()
        }

        # 완료된 작업 처리 (타임아웃 추가)
        try:
            for future in as_completed(future_to_stock):
                code, name, theme = future_to_stock[future]
                completed_count += 1

                try:
                    result = future.result(timeout=15)
                    if result:
                        # DB에 이력 업데이트
                        history = update_stock_history(result)
                        result.update(history)

                        with lock:
                            results.append(result)

                        # 신규/재발견 표시
                        status_icon = "🆕신규" if history['신규여부'] else f"({history['발견횟수']}회째)"
                        if history['연속발견횟수'] >= 5:
                            status_icon = f"🔥{history['연속발견횟수']}회 연속"

                        print(f"[발견] {code} {name} ({theme}) - 현재가: {result['현재가']:,}원, 상승률: {result['상승률']}% {status_icon}")
                except TimeoutError:
                    with lock:
                        error_count += 1
                except KeyboardInterrupt:
                    print("\n[중단] 사용자에 의해 중단되었습니다.")
                    print(f"[정보] {completed_count}/{total_count} 종목까지 분석 완료")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                except Exception as e:
                    with lock:
                        error_count += 1
                    # 오류 내용을 간단히 표시 (너무 많으면 주석 처리)
                    if error_count <= 10:
                        print(f"[오류] {code} {name}: {str(e)[:50]}")

                # 진행상황 표시 (100개마다)
                if completed_count % 100 == 0:
                    print(f"[진행] {completed_count}/{total_count} 종목 분석 완료... (오류: {error_count}개, 발견: {len(results)}개)")

        except KeyboardInterrupt:
            print(f"\n[중단] 사용자에 의해 중단되었습니다.")
            print(f"[정보] {completed_count}/{total_count} 종목까지 분석 완료")
            executor.shutdown(wait=False, cancel_futures=True)

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.")
    print(f"[통계] 분석 완료: {completed_count}개 / 오류: {error_count}개\n")

    return results


def screen_theme_stocks_with_checkpoint(csv_file, threshold=5.0, max_workers=20, batch_size=500, resume=False, rate_limit_delay=0.1):
    """
    체크포인트 기반 배치 처리 스크리닝 (중단 후 재개 가능)

    Args:
        csv_file: 테마 종목 CSV 파일 경로
        threshold: 상승률 기준 (기본값: 5.0%)
        max_workers: 병렬 처리 스레드 수 (기본값: 20)
        batch_size: 배치 크기 (기본값: 500)
        resume: 이전 작업 이어서 하기 (기본값: False)
        rate_limit_delay: API 요청 간 지연 시간 초 (기본값: 0.1초)

    Returns:
        list: 조건을 만족하는 종목 리스트
    """
    # DB 초기화
    init_db()

    print(f"[시작] 체크포인트 기반 스크리닝 시작...")
    print(f"[파일] {csv_file}")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
    print(f"[설정] 병렬 처리: {max_workers}개 | 배치 크기: {batch_size}개 | 요청 지연: {rate_limit_delay}초")
    print("="*70)

    # 재개 여부에 따라 처리
    if not resume:
        # 새로 시작 - 기존 상태 초기화
        clear_processing_status()
        print("[새로운 작업] 처리 상태를 초기화했습니다.\n")
    else:
        # 재개 - 기존 통계 확인
        stats = get_processing_statistics()
        print(f"[재개 모드] 기존 진행 상황:")
        print(f"  - 완료: {stats['completed']}개")
        print(f"  - 실패: {stats['failed']}개")
        print(f"  - 처리 중: {stats['processing']}개\n")

    # 미처리 종목 가져오기
    try:
        pending_df, completed_count, retry_codes = get_pending_stocks(csv_file)
        total_stocks = len(pending_df)

        if total_stocks == 0:
            print("[완료] 모든 종목 처리가 완료되었습니다!")
            # 결과 조회
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT h.* FROM stock_history h
                INNER JOIN processing_status p ON h.종목코드 = p.종목코드
                WHERE p.상태 = 'completed'
            ''')
            results = []
            if cursor.description:
                col_names = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(col_names, row)))
            conn.close()
            return results

        print(f"[정보] 처리 대상: {total_stocks}개 종목 (이미 완료: {completed_count}개)")
        if len(retry_codes) > 0:
            print(f"[정보] 재시도 대상: {len(retry_codes)}개 종목\n")

    except Exception as e:
        print(f"[오류] 종목 로드 실패: {e}")
        return []

    # 날짜 범위 설정
    end_date = datetime.now()
    start_date = end_date - timedelta(days=50)

    # 배치로 나누기
    num_batches = (total_stocks + batch_size - 1) // batch_size
    results = []
    overall_completed = completed_count
    overall_errors = 0
    lock = threading.Lock()

    print(f"[배치 정보] 총 {num_batches}개 배치로 처리 ({batch_size}개씩)\n")

    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_stocks)
        batch_df = pending_df.iloc[start_idx:end_idx]
        batch_count = len(batch_df)

        print(f"\n{'='*70}")
        print(f"[배치 {batch_num + 1}/{num_batches}] {batch_count}개 종목 처리 중...")
        print(f"{'='*70}")

        batch_results = []
        batch_completed = 0
        batch_errors = 0

        # 배치 내 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_stock = {
                executor.submit(
                    analyze_theme_stock,
                    row['종목코드'],
                    row['종목명'],
                    row['테마명'],
                    start_date,
                    end_date,
                    threshold
                ): (row['종목코드'], row['종목명'], row['테마명'])
                for _, row in batch_df.iterrows()
            }

            try:
                for future in as_completed(future_to_stock):
                    code, name, theme = future_to_stock[future]
                    batch_completed += 1
                    overall_completed += 1

                    # Rate limiting
                    if rate_limit_delay > 0:
                        time.sleep(rate_limit_delay)

                    try:
                        result = future.result(timeout=15)

                        if result:
                            # 성공 - DB에 이력 및 상태 업데이트
                            history = update_stock_history(result)
                            result.update(history)

                            with lock:
                                batch_results.append(result)
                                results.append(result)

                            # 처리 상태 업데이트
                            update_processing_status(code, name, theme, 'completed', batch_num + 1)

                            # 상태 아이콘
                            status_icon = "🆕신규" if history['신규여부'] else f"({history['발견횟수']}회째)"
                            if history['연속발견횟수'] >= 5:
                                status_icon = f"🔥{history['연속발견횟수']}회 연속"

                            print(f"[발견] {code} {name} - 현재가: {result['현재가']:,}원, 상승률: {result['상승률']}% {status_icon}")
                        else:
                            # 조건 미충족 - 완료로 처리
                            update_processing_status(code, name, theme, 'completed', batch_num + 1)

                    except TimeoutError:
                        with lock:
                            batch_errors += 1
                            overall_errors += 1
                        update_processing_status(code, name, theme, 'failed', batch_num + 1, '15초 타임아웃')
                        print(f"[타임아웃] {code} {name}")

                    except KeyboardInterrupt:
                        print("\n[중단] 사용자에 의해 중단되었습니다.")
                        print(f"[체크포인트] 배치 {batch_num + 1}까지 처리 완료")
                        print(f"[결과] 지금까지 {len(results)}개 종목 발견")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    except Exception as e:
                        with lock:
                            batch_errors += 1
                            overall_errors += 1
                        error_msg = str(e)[:100]
                        update_processing_status(code, name, theme, 'failed', batch_num + 1, error_msg)
                        if batch_errors <= 5:
                            print(f"[오류] {code} {name}: {error_msg}")

                    # 진행 상황 표시
                    if batch_completed % 50 == 0:
                        print(f"[진행] 배치 {batch_num + 1}: {batch_completed}/{batch_count} 완료 (전체: {overall_completed} | 오류: {overall_errors} | 발견: {len(results)})")

            except KeyboardInterrupt:
                print("\n[중단] 사용자에 의해 중단되었습니다.")
                print(f"[체크포인트] 배치 {batch_num + 1}까지 처리 완료")
                executor.shutdown(wait=False, cancel_futures=True)

        # 배치 완료 - 중간 결과 저장
        print(f"\n[배치 완료] {batch_completed}개 처리 | 발견: {len(batch_results)}개 | 오류: {batch_errors}개")

        if batch_results:
            save_batch_results(batch_results, batch_num + 1)

        # 배치 간 휴식 (마지막 배치 제외)
        if batch_num < num_batches - 1:
            print(f"[휴식] 다음 배치까지 2초 대기...\n")
            time.sleep(2)

    print("\n" + "="*70)
    print(f"[완료] 모든 배치 처리 완료!")
    print(f"[통계] 총 처리: {overall_completed}개 | 발견: {len(results)}개 | 오류: {overall_errors}개\n")

    return results


def save_batch_results(batch_results, batch_num):
    """배치 결과를 CSV 파일로 저장"""
    if not batch_results:
        return

    try:
        df = pd.DataFrame(batch_results)
        filename = f"batch_{batch_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장] 배치 {batch_num} 결과 저장: {filename}")
    except Exception as e:
        print(f"[오류] 배치 결과 저장 실패: {e}")


def format_theme_screening_results(results, threshold):
    """테마별 스크리닝 결과를 텔레그램 메시지 형식으로 포맷"""
    if not results:
        return f"20일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

    # 통계 조회
    stats = get_statistics()

    # 상승률 순으로 정렬
    results_sorted = sorted(results, key=lambda x: x['상승률'], reverse=True)

    # 상위 30개만 선택
    top_results = results_sorted[:30]

    # 신규 종목과 재발견 종목 분리
    new_stocks = [s for s in results if s.get('신규여부', False)]
    hot_stocks = [s for s in results if s.get('연속발견횟수', 0) >= 5]

    # 테마별로 그룹화
    theme_groups = {}
    for stock in top_results:
        theme = stock['테마명']
        if theme not in theme_groups:
            theme_groups[theme] = []
        theme_groups[theme].append(stock)

    message = f"""
📈 테마별 급등주 스크리닝 결과
조건: 20일 이동평균 대비 {threshold}% 이상 상승
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📊 통계
• 총 발견: {len(results)}개 종목 ({len(theme_groups)}개 테마)
• 🆕 신규: {len(new_stocks)}개
• 🔥 연속5회 이상: {len(hot_stocks)}개
• 이번주 신규: {stats['이번주신규']}개

[상위 {len(top_results)}개 종목 - 테마별 그룹]
"""

    for theme, stocks in theme_groups.items():
        message += f"\n▶ {theme} ({len(stocks)}개)\n"
        for stock in stocks:
            # 상태 아이콘
            status = ""
            if stock.get('신규여부', False):
                status = " 🆕"
            elif stock.get('연속발견횟수', 0) >= 5:
                status = f" 🔥{stock['연속발견횟수']}"
            elif stock.get('발견횟수', 1) > 1:
                status = f" ({stock['발견횟수']})"

            message += f"  · {stock['종목명']}({stock['종목코드']}) "
            message += f"{stock['현재가']:,}원 +{stock['상승률']}%{status}\n"

    if len(results) > 30:
        message += f"\n* 상위 30개만 표시 (전체 {len(results)}개)"

    return message


def handle_theme_stock_screening():
    """테마별 종목 급등주 스크리닝 실행 처리"""
    print("\n[실행] 테마별 종목 급등주 스크리닝을 시작합니다...\n")

    # CSV 파일 선택
    import glob
    csv_files = glob.glob("naver_theme_stocks_*.csv")

    if not csv_files:
        print("[오류] 테마 종목 CSV 파일이 없습니다.")
        print("[안내] 먼저 '1. 네이버 테마 크롤링'을 실행하여 CSV 파일을 생성하세요.")
        return

    # 최신 파일 찾기
    csv_files.sort(reverse=True)
    latest_csv = csv_files[0]

    print(f"[파일] 최신 CSV 파일: {latest_csv}")

    # 다른 파일 선택 옵션
    if len(csv_files) > 1:
        print(f"\n[참고] 총 {len(csv_files)}개의 CSV 파일이 있습니다.")
        use_latest = input("최신 파일을 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()

        if use_latest == 'n':
            print("\n사용 가능한 파일 목록:")
            for i, f in enumerate(csv_files, 1):
                print(f"  {i}. {f}")

            file_choice = input("\n파일 번호를 선택하세요: ").strip()
            try:
                file_idx = int(file_choice) - 1
                if 0 <= file_idx < len(csv_files):
                    latest_csv = csv_files[file_idx]
                else:
                    print("[오류] 잘못된 번호입니다. 최신 파일을 사용합니다.")
            except ValueError:
                print("[오류] 잘못된 입력입니다. 최신 파일을 사용합니다.")

    print(f"\n[선택] {latest_csv}\n")

    # 스크리닝 조건 입력
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

    print(f"\n[설정] {max_pages}페이지 크롤링\n")

    # 크롤링 실행
    df_themes = crawl_all_themes(max_pages)

    if df_themes.empty:
        print("[오류] 크롤링된 데이터가 없습니다.")
        return

    # 결과 미리보기
    print("\n" + "="*70)
    print("[상위 10개 테마]")
    print("="*70)

    # 등락률 순으로 정렬하여 상위 10개 출력
    df_copy = df_themes.copy()
    df_copy['등락률_숫자'] = df_copy['전일대비'].str.replace('%', '').str.replace('+', '').astype(float)
    df_sorted = df_copy.sort_values('등락률_숫자', ascending=False)

    print(df_sorted[['테마명', '전일대비', '최근3일등락률', '상승', '하락', '주도주1']].head(10).to_string(index=False))

    # 텔레그램 메시지 포맷
    message = format_theme_results(df_themes, top_n=10)

    # 콘솔 출력
    print("\n" + "="*70)
    print("[텔레그램 전송 메시지 미리보기]")
    print("="*70)
    print(message)

    # 텔레그램 전송
    send_choice = input("\n텔레그램으로 전송하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if send_choice != 'n':
        print("\n[전송] 텔레그램으로 전송 중...")
        success = send_telegram_message_sync(message)
        if success:
            print("[OK] 텔레그램 전송 완료!")
        else:
            print("[오류] 텔레그램 전송 실패")

    # CSV 파일 저장
    save_choice = input("\nCSV 파일로 저장하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if save_choice != 'n':
        filename = f"naver_themes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_themes.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장] {filename} 파일로 저장되었습니다.")


def analyze_theme_stock(code, name, theme_name, start_date, end_date, threshold):
    """
    테마별 단일 종목 분석 (병렬 처리용)

    Args:
        code: 종목 코드
        name: 종목명
        theme_name: 테마명
        start_date: 시작 날짜
        end_date: 종료 날짜
        threshold: 상승률 기준

    Returns:
        dict or None: 조건을 만족하면 종목 정보 딕셔너리, 아니면 None
    """
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            # 데이터 가져오기 (타임아웃 포함)
            hist = fdr.DataReader(code, start_date, end_date)

            if hist is None or hist.empty or len(hist) < 20:
                return None

            # 현재가와 20일 이동평균 계산
            current_price = hist['Close'].iloc[-1]
            ma_20 = hist['Close'].tail(20).mean()

            # 상승률 계산
            diff_pct = ((current_price - ma_20) / ma_20) * 100

            if diff_pct >= threshold:
                return {
                    '테마명': theme_name,
                    '종목코드': code,
                    '종목명': name,
                    '현재가': int(current_price),
                    '20일평균': int(ma_20),
                    '상승률': round(diff_pct, 2),
                    '거래량': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
                }
            return None

        except KeyboardInterrupt:
            raise
        except Exception as e:
            # 마지막 시도가 아니면 재시도
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            # 마지막 시도에서도 실패하면 None 반환 (에러 로그는 옵션)
            # print(f"[오류] {code} {name}: {str(e)}")
            return None

    return None


def screen_theme_stocks_from_csv(csv_file, threshold=5.0, max_workers=20):
    """
    CSV 파일에서 테마별 종목을 읽어 급등주 스크리닝 (병렬 처리)

    Args:
        csv_file: 테마 종목 CSV 파일 경로
        threshold: 상승률 기준 (기본값: 5.0%)
        max_workers: 병렬 처리 스레드 수 (기본값: 20)

    Returns:
        list: 조건을 만족하는 종목 리스트
    """
    # DB 초기화
    init_db()

    print(f"[시작] CSV 파일에서 테마별 종목 스크리닝 시작...")
    print(f"[파일] {csv_file}")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
    print(f"[설정] 병렬 처리 스레드: {max_workers}개")
    print("="*70)

    # CSV 파일 읽기
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"[정보] CSV에서 총 {len(df)}개 종목 로드 완료\n")

        # 필요한 컬럼 확인
        required_cols = ['테마명', '종목코드', '종목명']
        for col in required_cols:
            if col not in df.columns:
                print(f"[오류] CSV 파일에 '{col}' 컬럼이 없습니다.")
                return []

    except FileNotFoundError:
        print(f"[오류] 파일을 찾을 수 없습니다: {csv_file}")
        return []
    except Exception as e:
        print(f"[오류] CSV 파일 읽기 실패: {e}")
        return []

    # 날짜 범위 설정 (최근 50일)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=50)

    results = []
    completed_count = 0
    error_count = 0
    total_count = len(df)
    lock = threading.Lock()

    # 병렬 처리로 종목 분석
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 종목에 대해 작업 제출
        future_to_stock = {
            executor.submit(
                analyze_theme_stock,
                row['종목코드'],
                row['종목명'],
                row['테마명'],
                start_date,
                end_date,
                threshold
            ): (row['종목코드'], row['종목명'], row['테마명'])
            for _, row in df.iterrows()
        }

        # 완료된 작업 처리 (타임아웃 추가)
        try:
            for future in as_completed(future_to_stock):
                code, name, theme = future_to_stock[future]
                completed_count += 1

                try:
                    result = future.result(timeout=15)
                    if result:
                        # DB에 이력 업데이트
                        history = update_stock_history(result)
                        result.update(history)

                        with lock:
                            results.append(result)

                        # 신규/재발견 표시
                        status_icon = "🆕신규" if history['신규여부'] else f"({history['발견횟수']}회째)"
                        if history['연속발견횟수'] >= 5:
                            status_icon = f"🔥{history['연속발견횟수']}회 연속"

                        print(f"[발견] {code} {name} ({theme}) - 현재가: {result['현재가']:,}원, 상승률: {result['상승률']}% {status_icon}")
                except TimeoutError:
                    with lock:
                        error_count += 1
                except KeyboardInterrupt:
                    print("\n[중단] 사용자에 의해 중단되었습니다.")
                    print(f"[체크포인트] 배치 {batch_num + 1}까지 처리 완료")
                    print(f"[결과] 지금까지 {len(results)}개 종목 발견")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                except Exception as e:
                    with lock:
                        error_count += 1
                    # 오류 내용을 간단히 표시 (너무 많으면 주석 처리)
                    if error_count <= 10:
                        print(f"[오류] {code} {name}: {str(e)[:50]}")

                # 진행상황 표시 (100개마다)
                if completed_count % 100 == 0:
                    print(f"[진행] {completed_count}/{total_count} 종목 분석 완료... (오류: {error_count}개, 발견: {len(results)}개)")

        except KeyboardInterrupt:
            print(f"\n[중단] 사용자에 의해 중단되었습니다.")
            print(f"[체크포인트] 배치 {batch_num + 1}까지 처리 완료")
            executor.shutdown(wait=False, cancel_futures=True)

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.")
    print(f"[통계] 분석 완료: {completed_count}개 / 오류: {error_count}개\n")

    return results


def screen_theme_stocks_with_checkpoint(csv_file, threshold=5.0, max_workers=20, batch_size=500, resume=False, rate_limit_delay=0.1):
    """
    체크포인트 기반 배치 처리 스크리닝 (중단 후 재개 가능)

    Args:
        csv_file: 테마 종목 CSV 파일 경로
        threshold: 상승률 기준 (기본값: 5.0%)
        max_workers: 병렬 처리 스레드 수 (기본값: 20)
        batch_size: 배치 크기 (기본값: 500)
        resume: 이전 작업 이어서 하기 (기본값: False)
        rate_limit_delay: API 요청 간 지연 시간 초 (기본값: 0.1초)

    Returns:
        list: 조건을 만족하는 종목 리스트
    """
    # DB 초기화
    init_db()

    print(f"[시작] 체크포인트 기반 스크리닝 시작...")
    print(f"[파일] {csv_file}")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
    print(f"[설정] 병렬 처리: {max_workers}개 | 배치 크기: {batch_size}개 | 요청 지연: {rate_limit_delay}초")
    print("="*70)

    # 재개 여부에 따라 처리
    if not resume:
        # 새로 시작 - 기존 상태 초기화
        clear_processing_status()
        print("[새로운 작업] 처리 상태를 초기화했습니다.\n")
    else:
        # 재개 - 기존 통계 확인
        stats = get_processing_statistics()
        print(f"[재개 모드] 기존 진행 상황:")
        print(f"  - 완료: {stats['completed']}개")
        print(f"  - 실패: {stats['failed']}개")
        print(f"  - 처리 중: {stats['processing']}개\n")

    # 미처리 종목 가져오기
    try:
        pending_df, completed_count, retry_codes = get_pending_stocks(csv_file)
        total_stocks = len(pending_df)

        if total_stocks == 0:
            print("[완료] 모든 종목 처리가 완료되었습니다!")
            # 결과 조회
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT h.* FROM stock_history h
                INNER JOIN processing_status p ON h.종목코드 = p.종목코드
                WHERE p.상태 = 'completed'
            ''')
            results = []
            if cursor.description:
                col_names = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(col_names, row)))
            conn.close()
            return results

        print(f"[정보] 처리 대상: {total_stocks}개 종목 (이미 완료: {completed_count}개)")
        if len(retry_codes) > 0:
            print(f"[정보] 재시도 대상: {len(retry_codes)}개 종목\n")

    except Exception as e:
        print(f"[오류] 종목 로드 실패: {e}")
        return []

    # 날짜 범위 설정
    end_date = datetime.now()
    start_date = end_date - timedelta(days=50)

    # 배치로 나누기
    num_batches = (total_stocks + batch_size - 1) // batch_size
    results = []
    overall_completed = completed_count
    overall_errors = 0
    lock = threading.Lock()

    print(f"[배치 정보] 총 {num_batches}개 배치로 처리 ({batch_size}개씩)\n")

    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_stocks)
        batch_df = pending_df.iloc[start_idx:end_idx]
        batch_count = len(batch_df)

        print(f"\n{'='*70}")
        print(f"[배치 {batch_num + 1}/{num_batches}] {batch_count}개 종목 처리 중...")
        print(f"{'='*70}")

        batch_results = []
        batch_completed = 0
        batch_errors = 0

        # 배치 내 병렬 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_stock = {
                executor.submit(
                    analyze_theme_stock,
                    row['종목코드'],
                    row['종목명'],
                    row['테마명'],
                    start_date,
                    end_date,
                    threshold
                ): (row['종목코드'], row['종목명'], row['테마명'])
                for _, row in batch_df.iterrows()
            }

            try:
                for future in as_completed(future_to_stock):
                    code, name, theme = future_to_stock[future]
                    batch_completed += 1
                    overall_completed += 1

                    # Rate limiting
                    if rate_limit_delay > 0:
                        time.sleep(rate_limit_delay)

                    try:
                        result = future.result(timeout=15)

                        if result:
                            # 성공 - DB에 이력 및 상태 업데이트
                            history = update_stock_history(result)
                            result.update(history)

                            with lock:
                                batch_results.append(result)
                                results.append(result)

                            # 처리 상태 업데이트
                            update_processing_status(code, name, theme, 'completed', batch_num + 1)

                            # 상태 아이콘
                            status_icon = "🆕신규" if history['신규여부'] else f"({history['발견횟수']}회째)"
                            if history['연속발견횟수'] >= 5:
                                status_icon = f"🔥{history['연속발견횟수']}회 연속"

                            print(f"[발견] {code} {name} - 현재가: {result['현재가']:,}원, 상승률: {result['상승률']}% {status_icon}")
                        else:
                            # 조건 미충족 - 완료로 처리
                            update_processing_status(code, name, theme, 'completed', batch_num + 1)

                    except TimeoutError:
                        with lock:
                            batch_errors += 1
                            overall_errors += 1
                        update_processing_status(code, name, theme, 'failed', batch_num + 1, '15초 타임아웃')
                        print(f"[타임아웃] {code} {name}")

                    except KeyboardInterrupt:
                        print("\n[중단] 사용자에 의해 중단되었습니다.")
                        print(f"[체크포인트] 배치 {batch_num + 1}까지 처리 완료")
                        print(f"[결과] 지금까지 {len(results)}개 종목 발견")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    except Exception as e:
                        with lock:
                            batch_errors += 1
                            overall_errors += 1
                        error_msg = str(e)[:100]
                        update_processing_status(code, name, theme, 'failed', batch_num + 1, error_msg)
                        if batch_errors <= 5:
                            print(f"[오류] {code} {name}: {error_msg}")

                    # 진행 상황 표시
                    if batch_completed % 50 == 0:
                        print(f"[진행] 배치 {batch_num + 1}: {batch_completed}/{batch_count} 완료 (전체: {overall_completed} | 오류: {overall_errors} | 발견: {len(results)})")

            except KeyboardInterrupt:
                print("\n[중단] 사용자에 의해 중단되었습니다.")
                print(f"[체크포인트] 배치 {batch_num + 1}까지 처리 완료")
                executor.shutdown(wait=False, cancel_futures=True)

        # 배치 완료 - 중간 결과 저장
        print(f"\n[배치 완료] {batch_completed}개 처리 | 발견: {len(batch_results)}개 | 오류: {batch_errors}개")

        if batch_results:
            save_batch_results(batch_results, batch_num + 1)

        # 배치 간 휴식 (마지막 배치 제외)
        if batch_num < num_batches - 1:
            print(f"[휴식] 다음 배치까지 2초 대기...\n")
            time.sleep(2)

    print("\n" + "="*70)
    print(f"[완료] 모든 배치 처리 완료!")
    print(f"[통계] 총 처리: {overall_completed}개 | 발견: {len(results)}개 | 오류: {overall_errors}개\n")

    return results


def save_batch_results(batch_results, batch_num):
    """배치 결과를 CSV 파일로 저장"""
    if not batch_results:
        return

    try:
        df = pd.DataFrame(batch_results)
        filename = f"batch_{batch_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장] 배치 {batch_num} 결과 저장: {filename}")
    except Exception as e:
        print(f"[오류] 배치 결과 저장 실패: {e}")


def format_theme_screening_results(results, threshold):
    """테마별 스크리닝 결과를 텔레그램 메시지 형식으로 포맷"""
    if not results:
        return f"20일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

    # 통계 조회
    stats = get_statistics()

    # 상승률 순으로 정렬
    results_sorted = sorted(results, key=lambda x: x['상승률'], reverse=True)

    # 상위 30개만 선택
    top_results = results_sorted[:30]

    # 신규 종목과 재발견 종목 분리
    new_stocks = [s for s in results if s.get('신규여부', False)]
    hot_stocks = [s for s in results if s.get('연속발견횟수', 0) >= 5]

    # 테마별로 그룹화
    theme_groups = {}
    for stock in top_results:
        theme = stock['테마명']
        if theme not in theme_groups:
            theme_groups[theme] = []
        theme_groups[theme].append(stock)

    message = f"""
📈 테마별 급등주 스크리닝 결과
조건: 20일 이동평균 대비 {threshold}% 이상 상승
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📊 통계
• 총 발견: {len(results)}개 종목 ({len(theme_groups)}개 테마)
• 🆕 신규: {len(new_stocks)}개
• 🔥 연속5회 이상: {len(hot_stocks)}개
• 이번주 신규: {stats['이번주신규']}개

[상위 {len(top_results)}개 종목 - 테마별 그룹]
"""

    for theme, stocks in theme_groups.items():
        message += f"\n▶ {theme} ({len(stocks)}개)\n"
        for stock in stocks:
            # 상태 아이콘
            status = ""
            if stock.get('신규여부', False):
                status = " 🆕"
            elif stock.get('연속발견횟수', 0) >= 5:
                status = f" 🔥{stock['연속발견횟수']}"
            elif stock.get('발견횟수', 1) > 1:
                status = f" ({stock['발견횟수']})"

            message += f"  · {stock['종목명']}({stock['종목코드']}) "
            message += f"{stock['현재가']:,}원 +{stock['상승률']}%{status}\n"

    if len(results) > 30:
        message += f"\n* 상위 30개만 표시 (전체 {len(results)}개)"

    return message


def handle_theme_stock_screening():
    """테마별 종목 급등주 스크리닝 실행 처리"""
    print("\n[실행] 테마별 종목 급등주 스크리닝을 시작합니다...\n")

    # CSV 파일 선택
    import glob
    csv_files = glob.glob("naver_theme_stocks_*.csv")

    if not csv_files:
        print("[오류] 테마 종목 CSV 파일이 없습니다.")
        print("[안내] 먼저 '1. 네이버 테마 크롤링'을 실행하여 CSV 파일을 생성하세요.")
        return

    # 최신 파일 찾기
    csv_files.sort(reverse=True)
    latest_csv = csv_files[0]

    print(f"[파일] 최신 CSV 파일: {latest_csv}")

    # 다른 파일 선택 옵션
    if len(csv_files) > 1:
        print(f"\n[참고] 총 {len(csv_files)}개의 CSV 파일이 있습니다.")
        use_latest = input("최신 파일을 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()

        if use_latest == 'n':
            print("\n사용 가능한 파일 목록:")
            for i, f in enumerate(csv_files, 1):
                print(f"  {i}. {f}")

            file_choice = input("\n파일 번호를 선택하세요: ").strip()
            try:
                file_idx = int(file_choice) - 1
                if 0 <= file_idx < len(csv_files):
                    latest_csv = csv_files[file_idx]
                else:
                    print("[오류] 잘못된 번호입니다. 최신 파일을 사용합니다.")
            except ValueError:
                print("[오류] 잘못된 입력입니다. 최신 파일을 사용합니다.")

    print(f"\n[선택] {latest_csv}\n")

    # 스크리닝 조건 입력
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
    results = screen_theme_stocks_from_csv(latest_csv, threshold, max_workers)

    if not results:
        print("\n[결과] 조건을 만족하는 종목이 없습니다.")
        return

    # 결과를 DataFrame으로 변환
    df_results = pd.DataFrame(results)

    # 결과 미리보기
    print("\n" + "="*70)
    print("[상위 20개 종목]")
    print("="*70)
    display_cols = ['테마명', '종목명', '종목코드', '현재가', '상승률']
    available_cols = [col for col in display_cols if col in df_results.columns]
    print(df_results[available_cols].head(20).to_string(index=False))

    # 텔레그램 메시지 포맷
    message = format_theme_screening_results(results, threshold)

    # 콘솔 출력
    print("\n" + "="*70)
    print("[텔레그램 전송 메시지 미리보기]")
    print("="*70)
    print(message)

    # 텔레그램 전송
    send_choice = input("\n텔레그램으로 전송하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if send_choice != 'n':
        print("\n[전송] 텔레그램으로 전송 중...")
        success = send_telegram_message_sync(message)
        if success:
            print("[OK] 텔레그램 전송 완료!")
        else:
            print("[오류] 텔레그램 전송 실패")

    # CSV 파일 저장
    save_choice = input("\nCSV 파일로 저장하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if save_choice != 'n':
        filename = f"theme_screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_results.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장] {filename} 파일로 저장되었습니다.")


def handle_checkpoint_screening():
    """체크포인트 기반 스크리닝 실행 처리 (개선된 버전)"""
    print("\n[실행] 체크포인트 기반 스크리닝을 시작합니다...")
    print("💡 이 모드는 중단 후 재개가 가능하며, 배치별로 안정적으로 처리합니다.\n")

    # CSV 파일 선택
    import glob
    csv_files = glob.glob("naver_theme_stocks_*.csv")

    if not csv_files:
        print("[오류] 테마 종목 CSV 파일이 없습니다.")
        print("[안내] 먼저 '1. 네이버 테마 크롤링'을 실행하여 CSV 파일을 생성하세요.")
        return

    # 최신 파일 찾기
    csv_files.sort(reverse=True)
    latest_csv = csv_files[0]

    print(f"[파일] 최신 CSV 파일: {latest_csv}")

    # 다른 파일 선택 옵션
    if len(csv_files) > 1:
        print(f"\n[참고] 총 {len(csv_files)}개의 CSV 파일이 있습니다.")
        use_latest = input("최신 파일을 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()

        if use_latest == 'n':
            print("\n사용 가능한 파일 목록:")
            for i, f in enumerate(csv_files, 1):
                print(f"  {i}. {f}")

            file_choice = input("\n파일 번호를 선택하세요: ").strip()
            try:
                file_idx = int(file_choice) - 1
                if 0 <= file_idx < len(csv_files):
                    latest_csv = csv_files[file_idx]
                else:
                    print("[오류] 잘못된 번호입니다. 최신 파일을 사용합니다.")
            except ValueError:
                print("[오류] 잘못된 입력입니다. 최신 파일을 사용합니다.")

    print(f"\n[선택] {latest_csv}\n")

    # 재개 모드 확인
    resume_choice = input("[질문] 이전 작업을 이어서 하시겠습니까? (y/n, 기본값: n): ").strip().lower()
    resume = resume_choice == 'y'

    # 스크리닝 조건 입력
    threshold_input = input("[입력] 상승률 기준을 입력하세요 (기본값: 5.0%): ").strip()
    try:
        threshold = float(threshold_input) if threshold_input else 5.0
    except ValueError:
        print("[오류] 잘못된 입력입니다. 기본값 5.0%를 사용합니다.")
        threshold = 5.0

    workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 20, 권장: 10-30): ").strip()
    try:
        max_workers = int(workers_input) if workers_input else 20
        max_workers = max(5, min(50, max_workers))
    except ValueError:
        print("[오류] 잘못된 입력입니다. 기본값 20을 사용합니다.")
        max_workers = 20

    batch_input = input("[입력] 배치 크기 (기본값: 500, 권장: 300-1000): ").strip()
    try:
        batch_size = int(batch_input) if batch_input else 500
        batch_size = max(100, min(2000, batch_size))
    except ValueError:
        print("[오류] 잘못된 입력입니다. 기본값 500을 사용합니다.")
        batch_size = 500

    delay_input = input("[입력] API 요청 지연 시간 초 (기본값: 0.1, 권장: 0.05-0.2): ").strip()
    try:
        rate_limit_delay = float(delay_input) if delay_input else 0.1
        rate_limit_delay = max(0.0, min(1.0, rate_limit_delay))
    except ValueError:
        print("[오류] 잘못된 입력입니다. 기본값 0.1초를 사용합니다.")
        rate_limit_delay = 0.1

    print(f"\n[설정] 상승률 기준: {threshold}%")
    print(f"[설정] 병렬 처리 스레드: {max_workers}개")
    print(f"[설정] 배치 크기: {batch_size}개")
    print(f"[설정] API 지연: {rate_limit_delay}초")
    print(f"[설정] 재개 모드: {'예' if resume else '아니오'}\n")

    # 스크리닝 실행
    results = screen_theme_stocks_with_checkpoint(
        latest_csv,
        threshold,
        max_workers,
        batch_size,
        resume,
        rate_limit_delay
    )

    if not results:
        print("\n[결과] 조건을 만족하는 종목이 없습니다.")
        return

    # 결과를 DataFrame으로 변환
    df_results = pd.DataFrame(results)

    # 결과 미리보기
    print("\n" + "="*70)
    print("[상위 20개 종목]")
    print("="*70)
    display_cols = ['테마명', '종목명', '종목코드', '현재가', '상승률']
    available_cols = [col for col in display_cols if col in df_results.columns]
    print(df_results[available_cols].head(20).to_string(index=False))

    # 텔레그램 메시지 포맷
    message = format_theme_screening_results(results, threshold)

    # 콘솔 출력
    print("\n" + "="*70)
    print("[텔레그램 전송 메시지 미리보기]")
    print("="*70)
    print(message)

    # 텔레그램 전송
    send_choice = input("\n텔레그램으로 전송하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if send_choice != 'n':
        print("\n[전송] 텔레그램으로 전송 중...")
        success = send_telegram_message_sync(message)
        if success:
            print("[OK] 텔레그램 전송 완료!")
        else:
            print("[오류] 텔레그램 전송 실패")

    # CSV 파일 저장
    save_choice = input("\nCSV 파일로 저장하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if save_choice != 'n':
        filename = f"checkpoint_screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_results.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장] {filename} 파일로 저장되었습니다.")


def show_menu():
    """메뉴 표시"""
    print("\n" + "="*50)
    print("[시스템] 주식 분석 및 텔레그램 알림")
    print("="*50)
    print("0. 채팅 ID 가져오기 (최초 설정)")
    print("1. 네이버 테마 크롤링 (급등 테마 분석)")
    print("2. 지금 바로 종목 분석 실행")
    print("3. 스케줄러 시작 (시간 입력)")
    print("4. 스케줄러 시작 (기본 시간: " + SCHEDULE_TIME + ")")
    print("5. 급등주 스크리닝 (20일 이평선 돌파)")
    print("6. 테마별 급등주 스크리닝 (기본 모드)")
    print("7. 테마별 급등주 스크리닝 (체크포인트 모드) ⭐NEW")
    print("8. 종료")
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
                handle_theme_crawling()
            elif choice == "2":
                symbol = get_stock_symbol()
                print(f"\n[실행] {symbol} 분석을 실행 중입니다...\n")

                asyncio.run(main(symbol))
            elif choice == "3":
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
            elif choice == "4":
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
            elif choice == "5":
                print("\n[실행] 급등주 스크리닝을 시작합니다...\n")
                threshold_input = input("[입력] 상승률 기준을 입력하세요 (기본값: 5.0%): ").strip() or "5.0"
                try:
                    threshold = float(threshold_input)
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 5.0%를 사용합니다.")
                    threshold = 5.0

                print("\n[거래량 필터 옵션]")
                print("  예시: 100 = 평균의 100% (필터 없음)")
                print("  예시: 150 = 평균의 150%")
                print("  예시: 200 = 평균의 200%")
                
                print("\n[DEBUG] volume_input 입력 대기 시작...")
                
                volume_input = input("[입력] 거래량 % (기본값: 100): ").strip()
                
                print(f"[DEBUG] volume_input 값: '{volume_input}'")
                print(f"[DEBUG] volume_input 타입: {type(volume_input)}")
                print(f"[DEBUG] volume_input 길이: {len(volume_input)}")
                
                volume_multiplier = 1.0
                if volume_input:
                    print(f"[DEBUG] 입력이 있음, 처리 시작...")
                    try:
                        volume_percent = float(volume_input)
                        print(f"[DEBUG] volume_percent: {volume_percent}")
                        
                        volume_multiplier = volume_percent / 100.0
                        print(f"[DEBUG] volume_multiplier: {volume_multiplier}")
                        
                        if volume_multiplier < 0.5:
                            print(f"[경고] {volume_percent}%는 50% 미만입니다. 50%로 설정합니다.")
                            volume_multiplier = 0.5
                        elif volume_multiplier > 10.0:
                            print(f"[경고] {volume_percent}%는 1000% 초과입니다. 1000%로 설정합니다.")
                            volume_multiplier = 10.0
                        
                        print(f"[설정] 거래량 필터: {volume_percent}% (평균의 {volume_multiplier}배)")
                    except ValueError as e:
                        print(f"[DEBUG] ValueError 발생: {e}")
                        print("[오류] 잘못된 입력입니다. 기본값 100%를 사용합니다.")
                        volume_multiplier = 1.0
                else:
                    print(f"[DEBUG] 입력이 없음, 기본값 사용")
                    print(f"[설정] 거래량 필터 없음 (100%)")

                print("\n[DEBUG] workers_input 입력 대기 시작...")
                
                workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 20): ").strip()
                
                print(f"[DEBUG] workers_input 값: '{workers_input}'")
                print(f"[DEBUG] workers_input 타입: {type(workers_input)}")
                
                try:
                    max_workers = int(workers_input) if workers_input else 20
                    max_workers = max(5, min(50, max_workers))
                    print(f"[DEBUG] max_workers: {max_workers}")
                except ValueError as e:
                    print(f"[DEBUG] ValueError 발생: {e}")
                    print("[오류] 잘못된 입력입니다. 기본값 20을 사용합니다.")
                    max_workers = 20

                # ✅ 수정: 거래량 조건 추가
                print(f"\n[설정] 상승률 기준: {threshold}%")
                if volume_multiplier > 1.0:
                    print(f"[설정] 거래량 필터: {volume_multiplier}배 이상 (평균 대비)")
                else:
                    print(f"[설정] 거래량 필터: 없음")
                print(f"[설정] 병렬 처리 스레드: {max_workers}개\n")

                print(f"[DEBUG] screen_stocks 호출 시작...")
                print(f"[DEBUG] threshold={threshold}, max_workers={max_workers}, volume_multiplier={volume_multiplier}")
                
                results = screen_stocks(threshold, max_workers, volume_multiplier)
                
                print(f"[DEBUG] screen_stocks 호출 완료, 결과 개수: {len(results)}")

                message = format_screening_results(results, threshold)

                print("\n" + "="*70)
                print("[결과 미리보기]")
                print("="*70)
                print(message)

                print("\n[전송] 텔레그램으로 전송 중...")
                success = send_telegram_message_sync(message)
                if success:
                    print("[OK] 텔레그램 전송 완료!")
                else:
                    print("[오류] 텔레그램 전송 실패")

                if results:
                    df_results = pd.DataFrame(results)
                    filename = f"stock_screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    df_results.to_csv(filename, index=False, encoding='utf-8-sig')
                    print(f"[저장] {filename} 파일로 저장되었습니다.")
            elif choice == "6":
                handle_theme_stock_screening()

            elif choice == "7":
                handle_checkpoint_screening()

            elif choice == "8":
                print("[종료] 프로그램을 종료합니다.")
                break
            else:
                print("[오류] 잘못된 선택입니다. 다시 시도해주세요.\n")