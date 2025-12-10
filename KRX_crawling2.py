import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime
import time
from io import StringIO
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# 환경변수 로드
load_dotenv()

# 설정 상수
RATE_LIMIT_DELAY = 0.3  # 요청 간 대기 시간 (초) - 병렬 처리로 단축 가능
MAX_WORKERS = 10  # 동시 실행 워커 수 (15 → 10으로 낮춤, 서버 부하 감소)
MAX_RETRIES = 3  # 실패 시 재시도 횟수
TIMEOUT = 15  # 요청 타임아웃 (초) - 10초에서 15초로 증가

# HTTP 요청 헤더 (크롤링용)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# 🔐 텔레그램 정보 (본인 정보로 변경)
BOT_TOKEN = '7710559919:AAFe5PGm7q_52T4OHGFbLn-CvLRhKyr1z_Q'  # 실제 토큰
CHAT_ID = '7659478692'  # 실제 chat_id

# 텔레그램 봇 초기화
bot = None
telegram_enabled = False

if BOT_TOKEN and CHAT_ID:
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        telegram_enabled = True
        print("[OK] 텔레그램 봇 초기화 성공")
    except Exception as e:
        print(f"[WARNING] 텔레그램 봇 초기화 실패: {e}")
        print("텔레그램 메시지 전송이 비활성화됩니다.")
else:
    print("[WARNING] 텔레그램 정보가 설정되지 않았습니다.")
    print("텔레그램 메시지 전송이 비활성화됩니다.")

# ✅ 동기 메시지 전송 함수
def send_telegram_message(text):
    if not telegram_enabled or bot is None:
        print(f"[텔레그램 비활성화] {text[:100]}...")
        return

    try:
        import asyncio
        # 동기 환경에서 비동기 함수 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.send_message(chat_id=CHAT_ID, text=text))
        loop.close()
        time.sleep(RATE_LIMIT_DELAY)
    except Exception as e:
        print(f"[WARNING] 텔레그램 전송 실패: {e}")

# KOSDAQ 종목코드 가져오기 (FinanceDataReader 사용)
def get_kosdaq_stock_codes():
    try:
        import FinanceDataReader as fdr

        # KOSDAQ 전체 종목 리스트 가져오기
        df = fdr.StockListing('KOSDAQ')

        # 필요한 컬럼만 선택 및 이름 변경
        df = df[['Code', 'Name']]
        df.columns = ['종목코드', '회사명']

        # 종목코드 6자리로 포맷팅
        df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)

        print(f"[OK] FinanceDataReader로 {len(df)}개 종목 데이터 로드 완료")
        return df

    except ImportError:
        print("[ERROR] FinanceDataReader가 설치되지 않았습니다.")
        print("        설치 명령: pip install finance-datareader")
        send_telegram_message("[ERROR] FinanceDataReader 라이브러리가 필요합니다.")
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERROR] 종목 데이터 로드 실패: {e}")
        send_telegram_message(f"[ERROR] 종목 데이터 로드 실패: {e}")
        return pd.DataFrame()

# 네이버 시세 가져오기 (조기 종료 최적화 + 재시도 로직)
def get_price_history(code, count=30):
    url = f"https://finance.naver.com/item/sise_day.nhn?code={code}"
    dfs = []
    total_rows = 0

    for page in range(1, 10):  # 최대 10페이지까지 (필요 시 조기 종료)
        pg_url = f"{url}&page={page}"

        # 재시도 로직 추가
        for retry in range(MAX_RETRIES):
            try:
                res = requests.get(pg_url, headers=HEADERS, timeout=TIMEOUT)
                res.raise_for_status()

                # pandas는 자동으로 사용 가능한 파서를 선택합니다 (lxml -> html5lib -> html.parser)
                df = pd.read_html(StringIO(res.text))[0]
                df = df.dropna()  # 빈 행 제거

                dfs.append(df)
                total_rows += len(df)

                # 필요한 데이터 수집 완료 시 조기 종료
                if total_rows >= count:
                    break

                time.sleep(RATE_LIMIT_DELAY)
                break  # 성공하면 재시도 루프 탈출

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if retry < MAX_RETRIES - 1:
                    wait_time = (retry + 1) * 2  # 재시도 시 대기 시간 증가 (2, 4, 6초)
                    time.sleep(wait_time)
                    continue
                else:
                    # 최종 실패
                    break
            except Exception as e:
                # 다른 에러는 재시도 없이 중단
                break

        # 필요한 데이터 수집 완료 시 페이지 루프 탈출
        if total_rows >= count:
            break

    if not dfs:
        return pd.DataFrame()

    try:
        price_df = pd.concat(dfs, ignore_index=True)
        price_df = price_df.dropna()
        
        # 🔧 컬럼명 자동 감지 (첫 번째 행 확인)
        expected_cols = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
        
        # 만약 컬럼명이 다르면 위치 기반 재할당
        if len(price_df.columns) >= 7:
            price_df.columns = expected_cols[:len(price_df.columns)]
        else:
            print(f"[WARNING] {code} 예상보다 적은 컬럼: {list(price_df.columns)}")
            return pd.DataFrame()

        # 필요한 컬럼만 선택
        for col in ['종가', '고가', '저가', '거래량']:
            if col in price_df.columns:
                price_df[col] = pd.to_numeric(
                    price_df[col].astype(str).str.replace(',', ''),
                    errors='coerce'
                )

        price_df = price_df.dropna(subset=['종가', '거래량'])
        price_df = price_df.reset_index(drop=True)
        return price_df.head(count)
    except Exception as e:
        print(f"[WARNING] {code} 데이터 처리 오류: {e}")
        return pd.DataFrame()

# 조건 확인 (길이 체크 개선)
def check_conditions(code, name):
    try:
        df = get_price_history(code)

        # 데이터 길이 확인 (20일 이상 필요)
        if df.empty or len(df) < 20:
            return (0, 0)

        # 🔧 인덱싱 범위 확인
        if len(df) < 2:
            return (0, 0)

        prev_close = df.iloc[1]["종가"]
        max_high = df.iloc[0:20]["고가"].max()

        if pd.notna(prev_close) and pd.notna(max_high) and max_high >= prev_close * 1.15:
            df["거래대금"] = df["거래량"] * df["종가"]
            avg_trading_value = df.head(5)["거래대금"].mean()
            avg_volume = df.head(5)["거래량"].mean()

            if pd.notna(avg_trading_value) and avg_trading_value > 0:
                return (avg_trading_value, avg_volume)
            else:
                return (0, 0)
        else:
            return (0, 0)
    except Exception as e:
        print(f"[WARNING] {code}({name}) 조건 확인 오류: {e}")
        return (0, 0)

# 메인 필터 실행 (병렬 처리 적용)
def run_filter():
    print("[INFO] KOSDAQ 종목 데이터 로드 중...")
    codes_df = get_kosdaq_stock_codes()

    if codes_df.empty:
        send_telegram_message("[ERROR] 종목 데이터를 불러올 수 없습니다.")
        return

    result = []
    print(f"[INFO] {len(codes_df)}개 종목 조건 확인 중 (병렬 처리: {MAX_WORKERS}개 워커)...")

    # 병렬 처리로 속도 대폭 개선
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 작업 제출
        futures = {
            executor.submit(check_conditions, row['종목코드'], row['회사명']): (row['종목코드'], row['회사명'])
            for _, row in codes_df.iterrows()
        }

        # 진행률 표시와 함께 결과 수집
        for future in tqdm(as_completed(futures), total=len(futures), desc="크롤링 진행"):
            code, name = futures[future]
            try:
                avg_trading_value, avg_volume = future.result()
                if avg_trading_value > 0:  # 0보다 큰 경우만 추가
                    result.append((code, name, avg_trading_value, avg_volume))
            except Exception as e:
                print(f"\n[WARNING] {code}({name}) 처리 실패: {e}")

    top200 = sorted(result, key=lambda x: x[2], reverse=True)[:200]

    if top200:
        msg = "[결과] 조건 만족 종목 (20봉 내 15% 상승 + 거래대금 상위 200)\n"
        msg += f"[날짜] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        for i, (code, name, avg_value, avg_vol) in enumerate(top200, 1):
            # 백만 단위로 변환
            value_million = avg_value / 1_000_000

            # 거래량 단위 자동 조정
            if avg_vol >= 10_000_000:  # 1천만 이상
                volume_str = f"{avg_vol / 10_000_000:.1f}천만"
            elif avg_vol >= 1_000_000:  # 100만 이상
                volume_str = f"{avg_vol / 1_000_000:.1f}백만"
            elif avg_vol >= 100_000:  # 10만 이상
                volume_str = f"{avg_vol / 1_000:.0f}천"
            else:  # 10만 미만
                volume_str = f"{avg_vol / 1_000:.1f}천"

            if value_million >= 100:
                value_str = f"{value_million:.0f}백만원"
            else:
                value_str = f"{value_million:.1f}백만원"

            msg += f"{i}. {name} ({code}) - 거래대금: {value_str}, 거래량: {volume_str}\n"

            # 메시지 길이 제한 (텔레그램 최대 4096자)
            if len(msg) > 3500:
                send_telegram_message(msg)
                msg = "[결과 계속]\n\n"

        if msg.strip():
            send_telegram_message(msg)
    else:
        send_telegram_message("조건을 만족하는 종목이 없습니다.")

# 프로그램 시작점
if __name__ == "__main__":
    try:
        run_filter()
        print("[OK] 필터링 완료")
    except KeyboardInterrupt:
        print("\n[INFO] 프로그램 중단됨")
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류: {e}")
        send_telegram_message(f"[ERROR] 프로그램 오류 발생: {e}")
