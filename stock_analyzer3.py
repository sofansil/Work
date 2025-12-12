import json
import os
import socket
from pykrx import stock
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from telegram import Bot
import asyncio
import time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import threading
import requests
from bs4 import BeautifulSoup
import sqlite3

# 환경변수 로드
load_dotenv()

# 네트워크 기본 타임아웃 (초) - 모든 소켓 요청에 적용
socket.setdefaulttimeout(10)

# 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
STOCK_SYMBOL = "005930"  # 삼성전자 (자동으로 KOSPI/KOSDAQ 판단)
DB_FILE = "stock_history.db"  # SQLite DB 파일명

# Watchlist 저장 경로
WATCHLIST_JSON = "watchlist.json"
WATCHLIST_CSV = "watchlist.csv"

# ==================== SQLite DB 관리 ====================
def init_db():
    """DB 초기화 및 테이블 생성"""
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()

    # WAL 모드 활성화 (멀티스레드 동시성 개선)
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA synchronous=NORMAL')  # WAL 모드에서 안전하게 성능 향상

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

    # 급등주 스크리닝 결과 테이블 (A/B/C 분류)
    # 테이블 존재 여부 및 컬럼 구조 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='surge_screening_results'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # 기존 테이블의 컬럼 구조 확인
        cursor.execute("PRAGMA table_info(surge_screening_results)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 스크리닝날짜 또는 status 컬럼이 없으면 테이블 재생성
        if '스크리닝날짜' not in columns or 'status' not in columns:
            print("[DB 업데이트] surge_screening_results 테이블 구조 변경 감지")
            print("[DB 업데이트] 기존 테이블 삭제 후 새로운 구조로 재생성합니다...")
            cursor.execute('DROP TABLE surge_screening_results')
            print("[DB 업데이트] 테이블 재생성 완료")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS surge_screening_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            종목코드 TEXT,
            종목명 TEXT,
            시장 TEXT,
            class TEXT,
            score INTEGER,
            현재가 INTEGER,
            today_return REAL,
            이유 TEXT,
            mode TEXT,
            스크리닝날짜 TEXT,
            스크리닝일시 TEXT,
            생성일시 TEXT,
            status TEXT,
            UNIQUE(종목코드, 스크리닝날짜)
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
    # 필수 데이터 검증
    required_keys = ['종목코드', '종목명', '현재가', '상승률', '거래량']
    for key in required_keys:
        if key not in stock_data:
            raise ValueError(f"필수 데이터 누락: {key}")

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30)
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

        # 반환값 추가 (치명적 버그 수정)
        return {
            '신규여부': is_new,
            '최초발견일': first_found,
            '발견횟수': total_count,
            '연속발견횟수': consecutive_count
        }

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[오류] DB 업데이트 실패 ({stock_data.get('종목코드', 'UNKNOWN')}): {e}")
        raise
    finally:
        if conn:
            conn.close()


# ==================== Watchlist 관리 ====================
def load_watchlist():
    if os.path.exists(WATCHLIST_JSON):
        try:
            with open(WATCHLIST_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_watchlist(watchlist):
    try:
        with open(WATCHLIST_JSON, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # CSV도 함께 저장 (간단 확인용)
    try:
        import csv

        with open(WATCHLIST_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["code", "name", "market", "first_detected", "last_detected"])
            for code, item in watchlist.items():
                writer.writerow([
                    code,
                    item.get("name", ""),
                    item.get("market", ""),
                    item.get("first_detected", ""),
                    item.get("last_detected", ""),
                ])
    except Exception:
        pass


def save_surge_results_to_db(results):
    """급등주 스크리닝 결과를 DB에 저장"""
    if not results:
        return
    
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30)
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        screening_date = datetime.now().strftime('%Y-%m-%d')
        
        success_count = 0
        new_count = 0
        update_count = 0
        
        for r in results:
            try:
                # 기존 데이터 확인
                cursor.execute('''
                    SELECT id FROM surge_screening_results 
                    WHERE 종목코드 = ? AND 스크리닝날짜 = ?
                ''', (r.get('종목코드', ''), screening_date))
                existing = cursor.fetchone()
                
                # 신규/기존 구분
                status = 'old' if existing else 'new'
                if status == 'new':
                    new_count += 1
                else:
                    update_count += 1
                
                cursor.execute('''
                    INSERT OR REPLACE INTO surge_screening_results 
                    (종목코드, 종목명, 시장, class, score, 현재가, today_return, 이유, mode, 스크리닝날짜, 스크리닝일시, 생성일시, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    r.get('종목코드', ''),
                    r.get('종목명', ''),
                    r.get('시장', ''),
                    r.get('class', ''),
                    r.get('score', 0),
                    r.get('현재가', 0),
                    r.get('today_return', 0.0),
                    r.get('이유', ''),
                    r.get('mode', ''),
                    screening_date,
                    screening_date + ' ' + now.split()[1],
                    now,
                    status
                ))
                success_count += 1
            except Exception as e:
                print(f"[DB 저장 오류] {r.get('종목코드', '')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        print(f"[DB 저장] {success_count}/{len(results)}개 종목 저장 (신규: {new_count}, 업데이트: {update_count})")
    except Exception as e:
        print(f"[DB 연결 오류] {e}")
        print(f"[안내] DB 초기화를 먼저 실행해주세요.")


# ==================== 분석 헬퍼 ====================
def fetch_data(ticker, days=120):
    """pykrx에서 OHLCV를 불러옵니다."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    try:
        df = stock.get_market_ohlcv(start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), ticker)
        if df is None or df.empty:
            return None
        df = df.dropna().copy()
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


def get_volatility(df, window):
    if len(df) < window + 1:
        return None
    return df["종가"].pct_change().tail(window).std()


def calculate_initial_signal(df):
    """초기 포착 조건 계산"""
    if len(df) < 25:
        return False, {}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    vol_5 = df["거래량"].tail(5)
    vol_20 = df["거래량"].tail(20)
    high_20 = df["고가"].tail(20).max()

    cond_volume = (last["거래량"] >= prev["거래량"] * 3) or (last["거래량"] >= vol_5.mean() * 5)
    cond_price = (last["종가"] >= high_20) or (last["종가"] >= high_20 * 0.99)
    body = last["종가"] - last["시가"]
    range_candle = max(last["고가"] - last["저가"], 1e-9)
    cond_candle = (last["종가"] > last["시가"]) and ((body / range_candle) >= 0.7) and ((last["종가"] / last["시가"] - 1) >= 0.04)

    vol_5_std = get_volatility(df, 5)
    vol_20_std = get_volatility(df, 20)
    cond_vcp = False
    if vol_5_std is not None and vol_20_std is not None:
        cond_vcp = (vol_5_std < vol_20_std) and (prev["거래량"] <= vol_5.mean())

    is_initial = cond_volume and cond_price and cond_candle and cond_vcp

    meta = {
        "volume_spike": cond_volume,
        "price_breakout": cond_price,
        "candle_strong": cond_candle,
        "vcp": cond_vcp,
        "close": int(last["종가"]),
        "volume": int(last["거래량"]),
    }
    return is_initial, meta


def calculate_monitoring_signal(df):
    """모니터링 조건 계산"""
    if len(df) < 25:
        return False, {}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    ma5 = df["종가"].tail(5).mean()
    ma20 = df["종가"].tail(20).mean()
    high_20 = df["고가"].tail(20).max()
    vol5_mean = df["거래량"].tail(5).mean()

    cond_trend = (last["종가"] >= ma5) or (last["종가"] >= ma20)
    cond_volume = (last["거래량"] >= prev["거래량"] * 0.8) or (last["거래량"] >= vol5_mean * 0.8)
    cond_price = (last["종가"] >= high_20 * 0.9) or (last["종가"] >= prev["종가"] * 1.03)
    cond_candle = last["종가"] >= last["시가"]

    is_monitor = cond_trend and cond_volume and cond_price and cond_candle
    meta = {
        "trend": cond_trend,
        "volume_hold": cond_volume,
        "price_hold": cond_price,
        "candle_bull": cond_candle,
        "close": int(last["종가"]),
        "volume": int(last["거래량"]),
    }
    return is_monitor, meta


# ==================== 급등주 분류 헬퍼 (A/B/C) ====================
def fetch_stock_data(ticker, days=120):
    """OHLCV + 보조지표 계산"""
    df = fetch_data(ticker, days)
    if df is None or df.empty:
        return None
    df = df.copy()
    df["MA5"] = df["종가"].rolling(5).mean()
    df["MA20"] = df["종가"].rolling(20).mean()
    df["vol_avg5"] = df["거래량"].rolling(5).mean()
    df["vol_avg20"] = df["거래량"].rolling(20).mean()
    df["high20"] = df["고가"].rolling(20).max()
    return df.dropna()


def get_indicators(df):
    if len(df) < 21:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    low5 = df["저가"].tail(5)
    low10_prev5 = df["저가"].tail(10).head(5)  # 최근 10일 중 이전 5일

    candle_range = max(last["고가"] - last["저가"], 1e-9)
    body = last["종가"] - last["시가"]

    indicators = {
        "close": last["종가"],
        "open": last["시가"],
        "high": last["고가"],
        "low": last["저가"],
        "volume_today": last["거래량"],
        "volume_prev": prev["거래량"],
        "high20": last["high20"],
        "MA5": last["MA5"],
        "MA20": last["MA20"],
        "vol_avg5": last["vol_avg5"],
        "vol_avg20": last["vol_avg20"],
        "volatility5": (df["고가"] - df["저가"]).tail(5).std(),
        "volatility20": (df["고가"] - df["저가"]).tail(20).std(),
        "today_return": (last["종가"] - last["시가"]) / max(last["시가"], 1e-9) * 100,
        "min_low5": low5.min(),
        "min_low_prev5": low10_prev5.min() if len(low10_prev5) > 0 else low5.min(),
        "body": body,
        "candle_range": candle_range,
    }
    return indicators


def is_C_signal(ind):
    cond_trend = ind["close"] >= ind["MA20"]
    cond_price = ind["today_return"] >= 2
    cond_volume = (ind["volume_today"] >= ind["volume_prev"] * 1.2) or (ind["volume_today"] >= ind["vol_avg5"] * 1.5)
    return cond_trend and cond_price and cond_volume


def is_B_signal(ind):
    if not is_C_signal(ind):
        return False
    cond_near_high = ind["close"] >= ind["high20"] * 0.95
    cond_volume = (ind["volume_today"] >= ind["volume_prev"] * 2) or (ind["volume_today"] >= ind["vol_avg5"] * 2)
    cond_higher_low = ind["min_low5"] > ind["min_low_prev5"]
    return cond_near_high and cond_volume and cond_higher_low


def is_A_signal(ind):
    cond_volume_explosion = (ind["volume_today"] >= ind["volume_prev"] * 3) or (ind["volume_today"] >= ind["vol_avg5"] * 5)
    cond_breakout = (ind["close"] >= ind["high20"]) or (ind["close"] >= ind["high20"] * 0.99)
    cond_big_candle = (ind["close"] >= ind["open"] * 1.04) and (ind["body"] >= ind["candle_range"] * 0.7)
    cond_vcp = (ind["volatility5"] < ind["volatility20"]) and (ind["volume_prev"] < ind["vol_avg5"])
    return cond_volume_explosion and cond_breakout and cond_big_candle and cond_vcp


def compute_score(ind):
    score = 0
    # 가격
    if ind["close"] >= ind["MA20"]: score += 1
    if ind["today_return"] >= 2: score += 1
    if ind["close"] >= ind["high20"] * 0.95: score += 1
    if ind["close"] >= ind["high20"]: score += 2
    # 거래량
    if ind["volume_today"] >= ind["volume_prev"] * 1.5: score += 1
    if ind["volume_today"] >= ind["volume_prev"] * 3: score += 2
    if ind["volume_today"] >= ind["vol_avg5"] * 2: score += 1
    if ind["volume_today"] >= ind["vol_avg5"] * 5: score += 2
    # 추세/캔들
    if ind["min_low5"] > ind["min_low_prev5"]: score += 1
    if ind["close"] > ind["open"]: score += 1
    if ind["body"] >= ind["candle_range"] * 0.7: score += 2
    return score


def classify_signal(ind):
    score = compute_score(ind)
    if score >= 6:
        return "A", score
    if score >= 4:
        return "B", score
    if score >= 2:
        return "C", score
    return "NONE", score


def summarize_reasons(ind, label):
    reasons = []

    if label == "A":
        if ind["volume_today"] >= ind["volume_prev"] * 3:
            reasons.append("거래량 전일 3배↑")
        elif ind["volume_today"] >= ind["vol_avg5"] * 5:
            reasons.append("거래량 5일평균 5배↑")
        if ind["close"] >= ind["high20"]:
            reasons.append("20일 고점 돌파")
        elif ind["close"] >= ind["high20"] * 0.99:
            reasons.append("20일 고점 근접")
        if (ind["close"] >= ind["open"] * 1.04) and (ind["body"] >= ind["candle_range"] * 0.7):
            reasons.append("장대양봉(몸통 70%+)" )
        if (ind["volatility5"] < ind["volatility20"]) and (ind["volume_prev"] < ind["vol_avg5"]):
            reasons.append("VCP(변동성 축소 후 거래량 회복)")
    elif label == "B":
        if ind["close"] >= ind["high20"] * 0.95:
            reasons.append("20일 고점 95% 근접")
        if (ind["volume_today"] >= ind["volume_prev"] * 2) or (ind["volume_today"] >= ind["vol_avg5"] * 2):
            reasons.append("거래량 2배↑")
        if ind["min_low5"] > ind["min_low_prev5"]:
            reasons.append("저점 상승 추세")
        if ind["today_return"] >= 2:
            reasons.append("당일 +2% 이상")
    elif label == "C":
        if ind["close"] >= ind["MA20"]:
            reasons.append("20일선 위")
        if ind["today_return"] >= 2:
            reasons.append("당일 +2% 이상")
        if (ind["volume_today"] >= ind["volume_prev"] * 1.2) or (ind["volume_today"] >= ind["vol_avg5"] * 1.5):
            reasons.append("거래량 증가")

    if not reasons:
        reasons.append("다중 조건 충족")

    return "; ".join(reasons)


def get_stock_history(code):
    """종목 이력 조회"""
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM stock_history WHERE 종목코드 = ?', (code,))
    result = cursor.fetchone()

    if result:
        col_names = [desc[0] for desc in cursor.description]
        result_dict = dict(zip(col_names, result))
        conn.close()
        return result_dict

    conn.close()
    return None


def get_statistics():
    """전체 통계 조회"""
    conn = sqlite3.connect(DB_FILE, timeout=30)
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

async def main(symbol=None):
    """메인 함수"""
    if symbol is None:
        symbol = STOCK_SYMBOL
    message = analyze_stock(symbol)
    if message:
        await send_telegram_message(message)
        print("[OK] 텔레그램으로 전송되었습니다.")

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

        # 상승률 조건 체크
        if diff_pct < threshold:
            return None

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

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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

            print(f"[정보] {len(future_to_stock)}개 종목 병렬 분석 중...\n")

            # ⭐ 전체 타임아웃 5분 추가
            for future in as_completed(future_to_stock, timeout=300):
                code, name, market = future_to_stock[future]
                completed_count += 1

                try:
                    # ⭐ 개별 타임아웃 30초 추가
                    result = future.result(timeout=30)

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
                    print(f"[타임아웃] {code} {name} - 30초 초과")

                except Exception as e:
                    with lock:
                        error_count += 1
                    if error_count <= 10:
                        print(f"[오류] {code} {name}: {str(e)[:50]}")

                # 진행상황 표시
                if completed_count % 100 == 0:
                    remaining = total_count - completed_count
                    print(f"[진행] {completed_count}/{total_count} 완료 (남은 것: {remaining}개)... (발견: {len(results)}개, 오류: {error_count}개)")

            # ⭐ 마지막 진행상황 출력
            if completed_count % 100 != 0:
                print(f"[진행] {completed_count}/{total_count} 완료 (100%) - 발견: {len(results)}개, 오류: {error_count}개")

        except TimeoutError:
            print(f"\n[경고] 전체 타임아웃 발생! {completed_count}/{total_count} 종목까지 완료")
            print(f"[결과] 지금까지 {len(results)}개 종목 발견")

        except KeyboardInterrupt:
            print(f"\n[중단] {completed_count}/{total_count} 종목까지 분석 완료")
            print(f"[결과] 지금까지 {len(results)}개 종목 발견")

        except Exception as e:
            print(f"[오류] 예상치 못한 예외: {type(e).__name__}: {str(e)}")

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.\n")

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
    df_copy['등락률_숫자'] = df_copy['전일대비'].str.replace('%', '', regex=False).str.replace('+', '', regex=False).astype(float)
    df_sorted = df_copy.sort_values('등락률_숫자', ascending=False)

    # 상위 N개만 선택
    top_themes = df_sorted.head(top_n)

    message = f"""
📊 네이버 금융 테마별 시세
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}
총 테마 수: {len(df)}개

[상위 {top_themes.shape[0]}개 급등 테마]
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
    df_copy['등락률_숫자'] = df_copy['전일대비'].str.replace('%', '', regex=False).str.replace('+', '', regex=False).astype(float)
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
            for future in as_completed(future_to_stock, timeout=300):
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

                        print(f"[발견] {code} {name} ({theme}) - {result['현재가']:,}원, {result['상승률']}% {status_icon}")
                except TimeoutError:
                    with lock:
                        error_count += 1
                except KeyboardInterrupt:
                    print("\n[중단] 사용자에 의해 중단되었습니다.")
                    print(f"[진행] {completed_count}/{total_count} 종목까지 처리 완료")
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

        except TimeoutError:
            print(f"\n[경고] 전체 타임아웃 발생! {completed_count}/{total_count} 종목까지 완료")
            print(f"[결과] 지금까지 {len(results)}개 종목 발견")

        except KeyboardInterrupt:
            print(f"\n[중단] 사용자에 의해 중단되었습니다.")
            print(f"[진행] {completed_count}/{total_count} 종목까지 처리 완료")
            executor.shutdown(wait=False, cancel_futures=True)

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.")
    print(f"[통계] 분석 완료: {completed_count}개 / 오류: {error_count}개\n")

    return results


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

            message += f"  · {stock['종목명']}({stock['종목코드']}) {stock['현재가']:,}원 +{stock['상승률']}%{status}\n"

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
    threshold_input = input("[입력] 상승률 기준을 입력하세요 (기본값: 5.0%): ").strip() or "5.0"
    try:
        threshold = float(threshold_input)
    except ValueError:
        print("[오류] 잘못된 입력입니다. 기본값 5.0%를 사용합니다.")
        threshold = 5.0

    workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 20, 권장: 10-30): ").strip() or "20"
    try:
        max_workers = int(workers_input)
        max_workers = max(5, min(50, max_workers))
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

def screen_surge_stocks(max_workers=10):
    """급등주 초기 포착 + 모니터링 (KOSPI+KOSDAQ, A/B/C 분류)"""
    # DB 초기화 (테이블 생성)
    init_db()
    
    print("\n[시작] 급등주 스크리닝 시작...")
    print("="*70)

    # KOSPI + KOSDAQ 종목 리스트
    try:
        df_krx = fdr.StockListing('KRX')
        df_krx = df_krx[df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])]
        print(f"[정보] 총 {len(df_krx)}개 KOSPI+KOSDAQ 종목 분석 중...")
        kospi_count = len(df_krx[df_krx['Market'] == 'KOSPI'])
        kosdaq_count = len(df_krx[df_krx['Market'] == 'KOSDAQ'])
        print(f"  - KOSPI: {kospi_count}개")
        print(f"  - KOSDAQ: {kosdaq_count}개\n")
    except Exception as e:
        print(f"[오류] 종목 리스트 가져오기 실패: {e}")
        return [], []

    watchlist = load_watchlist()
    today_str = datetime.now().strftime('%Y-%m-%d')

    results_A, results_B, results_C = [], [], []
    error_count = 0
    lock = threading.Lock()

    def analyze_stock(row):
        ticker = row['Code']
        name = row['Name']
        market = row['Market']

        df = fetch_stock_data(ticker, days=120)
        if df is None or len(df) < 25:
            return None

        ind = get_indicators(df)
        if ind is None:
            return None

        label, score = classify_signal(ind)
        if label == "NONE":
            return None

        in_watch = ticker in watchlist
        mode = "monitoring" if in_watch else "initial"

        reason = summarize_reasons(ind, label)

        return {
            '종목코드': ticker,
            '종목명': name,
            '시장': market,
            'class': label,
            'score': score,
            '현재가': int(ind['close']),
            'today_return': round(ind['today_return'], 2),
            'mode': mode,
            '이유': reason,
        }

    # 병렬 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(analyze_stock, row): row for _, row in df_krx.iterrows()}

        completed = 0
        total = len(futures)
        start_time = time.time()
        pending = set(futures)

        try:
            # 30초마다 완료 여부 점검, 완료 없는 경우 남은 작업 취소
            while pending:
                done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)

                if not done:
                    with lock:
                        error_count += len(pending)
                    print(f"\n[타임아웃] 30초 동안 완료 없음 - 미완료 {len(pending)}개 취소 후 종료")
                    for future in pending:
                        future.cancel()
                    break

                for future in done:
                    completed += 1

                    if completed % 50 == 0:
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = total - completed
                        remaining_time = (remaining / rate) if rate > 0 else 0
                        detected = len(results_A) + len(results_B) + len(results_C)
                        print(f"[진행] {completed}/{total} 완료 ({completed*100//total}%) - {rate:.1f}개/초 (남은 것: {remaining}개, 예상: {remaining_time:.0f}초, 발견: {detected}개)")

                    try:
                        result = future.result()
                        if result:
                            with lock:
                                label = result['class']
                                ticker = result['종목코드']
                                reason = result.get('이유', '')
                                if label == 'A':
                                    results_A.append(result)
                                    watchlist[ticker] = {
                                        'name': result['종목명'],
                                        'market': result['시장'],
                                        'first_detected': watchlist.get(ticker, {}).get('first_detected', today_str),
                                        'last_detected': today_str,
                                    }
                                    print(f"🆕 [A급] {result['종목명']}({ticker}) ({result['시장']}) - {result['현재가']:,}원 점수:{result['score']} | {reason}")
                                elif label == 'B':
                                    results_B.append(result)
                                    if ticker in watchlist:
                                        watchlist[ticker]['last_detected'] = today_str
                                    print(f"⚡ [B급] {result['종목명']}({ticker}) ({result['시장']}) - {result['현재가']:,}원 점수:{result['score']} | {reason}")
                                elif label == 'C':
                                    results_C.append(result)
                                    if ticker in watchlist:
                                        watchlist[ticker]['last_detected'] = today_str
                                    # C급은 로그 최소화
                    except Exception:
                        with lock:
                            error_count += 1
                        if error_count % 10 == 0:
                            print(f"[경고] 오류/타임아웃 누적 {error_count}건 - 문제 종목 스킵")

        except KeyboardInterrupt:
            print(f"\n[중단] 사용자 중단 - {completed}/{total} 완료")

            for future in pending:
                if not future.done():
                    future.cancel()

        finally:
            save_watchlist(watchlist)

    elapsed_total = time.time() - start_time
    print("\n" + "="*70)
    print(f"[완료] A:{len(results_A)} B:{len(results_B)} C:{len(results_C)}")
    print(f"[통계] 완료: {completed}/{total} ({completed*100//total if total > 0 else 0}%), 오류/타임아웃: {error_count}개")
    print(f"[속도] {elapsed_total:.1f}초 소요 ({completed/elapsed_total if elapsed_total > 0 else 0:.1f}개/초)")
    print("="*70)

    # 결과 출력 (이유 포함)
    cols_common = ['종목명', '종목코드', '시장', '현재가', 'score', '이유']
    if results_A:
        print("\n[🔥 A급 급등 초기]")
        print(pd.DataFrame(results_A)[cols_common].sort_values('score', ascending=False).to_string(index=False))
    if results_B:
        print("\n[⚡ B급 강세]")
        print(pd.DataFrame(results_B)[cols_common].sort_values('score', ascending=False).to_string(index=False))
    if results_C:
        print("\n[👀 C급 관심]")
        print(pd.DataFrame(results_C)[cols_common].sort_values('score', ascending=False).to_string(index=False))

    return results_A + results_B + results_C, []


def show_menu():
    """메뉴 표시"""
    print("\n" + "="*50)
    print("[시스템] 주식 분석 및 텔레그램 알림")
    print("="*50)
    print("0. 채팅 ID 가져오기 (최초 설정)")
    print("1. 지금 바로 종목 분석 실행")
    print("2. 급등주 스크리닝 (20일 이평선 돌파)")
    print("3. 급등주 초기 포착 + 모니터링 ⭐NEW")
    print("4. 종료")
    print("="*50 + "\n")


def graceful_exit():
    """프로그램을 확실히 종료"""
    print("\n" + "="*50)
    print("[종료] 프로그램을 종료합니다.")
    print("="*50 + "\n")
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 명령행 인자로 실행
        if sys.argv[1] == "now":
            # python stock_analyzer3.py now [종목코드]
            symbol = sys.argv[2] if len(sys.argv) > 2 else STOCK_SYMBOL
            asyncio.run(main(symbol))
    else:
        # 인터랙티브 메뉴
        print("\n[시작] 주식 분석 프로그램을 시작합니다.\n")
        
        while True:
            show_menu()
            choice = input("선택: ").strip()

            if choice == "0":
                # 채팅 ID 가져오기
                print("\n[실행] 텔레그램 채팅 ID를 가져옵니다...\n")
                print("[안내] 텔레그램에서 봇에게 아무 메시지나 보낸 후 엔터를 누르세요.\n")
                chat_id = asyncio.run(get_chat_id())
                if chat_id:
                    print(f"\n[OK] 채팅 ID: {chat_id}")
                    print("[안내] .env 파일을 업데이트하세요.\n")
            elif choice == "1":
                symbol = get_stock_symbol()
                print(f"\n[실행] {symbol} 분석을 실행 중입니다...\n")
                asyncio.run(main(symbol))
            elif choice == "2":
                print("\n[실행] 급등주 스크리닝을 시작합니다...\n")
                threshold_input = input("[입력] 상승률 기준을 입력하세요 (기본값: 5.0%): ").strip() or "5.0"
                try:
                    threshold = float(threshold_input)
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 5.0%를 사용합니다.")
                    threshold = 5.0

                print("\n[거래량 필터]")
                print("  100 = 평균의 100% (필터 없음)")
                print("  150 = 평균의 150%")
                print("  200 = 평균의 200%")
                
                volume_input = input("[입력] 거래량 % (기본값: 100): ").strip() or "100"
                
                volume_multiplier = 1.0
                try:
                    volume_percent = float(volume_input)
                    volume_multiplier = volume_percent / 100.0
                    
                    if volume_multiplier < 0.5:
                        print(f"[경고] {volume_percent}%는 50% 미만입니다. 50%로 설정합니다.")
                        volume_multiplier = 0.5
                    elif volume_multiplier > 10.0:
                        print(f"[경고] {volume_percent}%는 1000% 초과입니다. 1000%로 설정합니다.")
                        volume_multiplier = 10.0
                    
                    print(f"[설정] 거래량 필터: {volume_percent}% (평균의 {volume_multiplier}배)")
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 100%를 사용합니다.")
                    volume_multiplier = 1.0

                workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 20): ").strip() or "20"
                try:
                    max_workers = int(workers_input)
                    max_workers = max(5, min(50, max_workers))
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 20을 사용합니다.")
                    max_workers = 20

                print(f"\n[설정] 상승률 기준: {threshold}%")
                if volume_multiplier > 1.0:
                    print(f"[설정] 거래량 필터: {volume_multiplier}배 이상 (평균 대비)")
                else:
                    print(f"[설정] 거래량 필터: 없음")
                print(f"[설정] 병렬 처리 스레드: {max_workers}개\n")

                results = screen_stocks(threshold, max_workers, volume_multiplier)

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
            elif choice == "3":
                print("\n[실행] 급등주 초기 포착 + 모니터링을 시작합니다...\n")
                
                workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 5): ").strip() or "5"
                try:
                    max_workers = int(workers_input)
                    max_workers = max(1, min(10, max_workers))  # 1-10 범위로 제한
                except ValueError:
                    print("[오류] 잘못된 입력입니다. 기본값 5를 사용합니다.")
                    max_workers = 5
                
                results, _ = screen_surge_stocks(max_workers)

                results_A = [r for r in results if r.get('class') == 'A']
                results_B = [r for r in results if r.get('class') == 'B']
                results_C = [r for r in results if r.get('class') == 'C']

                def fmt_stock(r):
                    """가독성 높은 종목 정보 포맷"""
                    lines = []
                    lines.append(f"📌 {r['종목명']}({r['종목코드']})")
                    lines.append(f"💰 {r['현재가']:,}원 (점수: {r.get('score', '-')})")
                    reason = r.get('이유', '')
                    if reason:
                        lines.append(f"📊 {reason}")
                    return "\n".join(lines)

                # 텔레그램 전송 메시지 구성 (4096자 제한 고려)
                messages = []
                
                # 첫 번째 메시지: 요약 + A급
                msg1 = f"📊 급등주 스크리닝 결과\n"
                msg1 += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                msg1 += f"{'='*30}\n"
                msg1 += f"🔥 A급: {len(results_A)}개\n"
                msg1 += f"⚡ B급: {len(results_B)}개\n"
                msg1 += f"👀 C급: {len(results_C)}개\n"
                msg1 += f"{'='*30}\n\n"

                if results_A:
                    msg1 += "****  🔥 A급 급등 초기 🔥  ****\n\n"
                    for idx, r in enumerate(results_A[:5], 1):  # A급 5개로 제한
                        msg1 += fmt_stock(r) + "\n\n"
                    if len(results_A) > 5:
                        msg1 += f"... 외 {len(results_A) - 5}개\n\n"
                
                messages.append(msg1)
                
                # 두 번째 메시지: B급
                if results_B:
                    msg2 = "****  ⚡ B급 강세 ⚡  ****\n\n"
                    for idx, r in enumerate(results_B[:5], 1):  # B급 5개로 제한
                        msg2 += fmt_stock(r) + "\n\n"
                    if len(results_B) > 5:
                        msg2 += f"... 외 {len(results_B) - 5}개\n\n"
                    messages.append(msg2)
                
                # 세 번째 메시지: C급
                if results_C:
                    msg3 = "****  👀 C급 관심 👀  ****\n\n"
                    for idx, r in enumerate(results_C[:3], 1):  # C급 3개로 제한
                        msg3 += fmt_stock(r) + "\n\n"
                    if len(results_C) > 3:
                        msg3 += f"... 외 {len(results_C) - 3}개\n\n"
                    messages.append(msg3)
                
                # ✅ 결과 미리보기 표시
                print("\n" + "="*70)
                print("[텔레그램 전송 메시지 미리보기]")
                print("="*70)
                for i, msg in enumerate(messages, 1):
                    print(f"\n--- 메시지 {i}/{len(messages)} ---")
                    print(msg)
                    print(f"--- 길이: {len(msg)}자 ---")
                
                # ✅ 빈 결과 체크
                if not results:
                    print("\n[알림] 조건을 만족하는 종목이 없습니다.")
                    send_choice = input("그래도 텔레그램으로 전송하시겠습니까? (y/n, 기본값: n): ").strip().lower()
                    if send_choice != 'y':
                        continue
                
                # ✅ 사용자 확인 후 전송 (여러 메시지 순차 전송)
                print(f"\n[전송] 텔레그램으로 {len(messages)}개 메시지 전송 중...")
                success_count = 0
                for i, msg in enumerate(messages, 1):
                    print(f"  [{i}/{len(messages)}] 전송 중... (길이: {len(msg)}자)")
                    if send_telegram_message_sync(msg):
                        success_count += 1
                        print(f"  [{i}/{len(messages)}] 전송 완료!")
                        if i < len(messages):
                            time.sleep(1)  # 메시지 간 1초 간격
                    else:
                        print(f"  [{i}/{len(messages)}] 전송 실패!")
                
                if success_count == len(messages):
                    print(f"[OK] 모든 메시지 전송 완료! ({success_count}/{len(messages)})")
                else:
                    print(f"[경고] 일부 메시지 전송 실패 ({success_count}/{len(messages)})")
                
                # ✅ CSV 저장 옵션
                if results:
                    # CSV 파일에 전체 결과 저장 (A/B/C 모두 포함)
                    df_results = pd.DataFrame(results)
                    
                    # 컬럼 순서 정리
                    cols_order = ['class', 'score', '종목명', '종목코드', '시장', '현재가', 'today_return', '이유', 'mode']
                    available_cols = [c for c in cols_order if c in df_results.columns]
                    df_results = df_results[available_cols]
                    
                    # 점수 순으로 정렬
                    df_results = df_results.sort_values(['class', 'score'], ascending=[True, False])
                    
                    # 파일명에 통계 포함
                    filename = f"surge_A{len(results_A)}_B{len(results_B)}_C{len(results_C)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    df_results.to_csv(filename, index=False, encoding='utf-8-sig')
                    print(f"\n[CSV 저장] {filename}")
                    print(f"  - 총 {len(results)}개 종목 (A:{len(results_A)}, B:{len(results_B)}, C:{len(results_C)})")
                    
                    # DB에도 저장
                    save_surge_results_to_db(results)
                    print(f"[DB 저장] stock_history.db에 저장 완료")
            elif choice == "4":
                graceful_exit()
            else:
                print("[오류] 잘못된 선택입니다. 다시 시도해주세요.\n")

        # ✅ 루프 종료 후 실행 (정상 종료 시)
        print("[완료] 프로그램이 정상적으로 종료되었습니다.")
        graceful_exit()