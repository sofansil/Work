import requests
import pandas as pd
from bs4 import BeautifulSoup
from telegram import Bot
from tqdm import tqdm
from datetime import datetime
import time
import asyncio

# 텔레그램 정보
BOT_TOKEN = '7710559919:AAFe5PGm7q_52T4OHGFbLn-CvLRhKyr1z_Q'  # 실제 토큰
CHAT_ID = '7659478692'  # 실제 chat_id
bot = Bot(token=BOT_TOKEN)

# ✅ 텔레그램 메시지 비동기 전송 함수
def send_telegram_message(text):
    try:
        asyncio.run(bot.send_message(chat_id=CHAT_ID, text=text))
    except Exception as e:
        print(f"⚠️ 텔레그램 전송 실패: {e}")

# ✅ 전 종목 코드 가져오기 (KOSPI + KOSDAQ)
def get_stock_codes():
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
    response = requests.get(url)
    df = pd.read_html(response.content, encoding='euc-kr')[0]
    df = df[['종목코드', '회사명', '업종']]
    df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
    return df

# ✅ 네이버 시세 가져오기
def get_price_history(code, count=30):
    url = f"https://finance.naver.com/item/sise_day.nhn?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    dfs = []

    for page in range(1, 5):
        pg_url = f"{url}&page={page}"
        res = requests.get(pg_url, headers=headers)
        try:
            df = pd.read_html(res.content, encoding='euc-kr')[0]
            dfs.append(df)
            time.sleep(0.3)
        except:
            continue

    if not dfs:
        return pd.DataFrame()

    price_df = pd.concat(dfs).dropna()
    price_df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
    price_df = price_df.reset_index(drop=True)
    price_df[['종가', '고가', '거래량']] = price_df[['종가', '고가', '거래량']].astype(int)
    return price_df.head(count)

# ✅ 조건 확인 함수
def check_conditions(code, name):
    try:
        df = get_price_history(code)
        if df.empty or len(df) < 20:
            return False

        prev_close = df.iloc[1]["종가"]
        max_high = df.iloc[0:20]["고가"].max()

        if max_high >= prev_close * 1.15:
            avg_volume = (df["거래량"] * df["종가"]).rolling(5).mean().iloc[0]
            return avg_volume
        else:
            return False
    except:
        return False

# ✅ 메인 실행 함수
def run_filter():
    codes_df = get_stock_codes()
    result = []

    print("📊 조건 확인 중...")
    for _, row in tqdm(codes_df.iterrows(), total=len(codes_df)):
        code = row['종목코드']
        name = row['회사명']
        result_value = check_conditions(code, name)

        if result_value and not pd.isna(result_value):
            result.append((code, name, result_value))

    top200 = sorted(result, key=lambda x: x[2], reverse=True)[:200]

    if top200:
        msg = "📈 조건 만족 종목 (20봉 내 15% 상승 + 거래대금 상위 200)\n\n"
        for code, name, value in top200:
            msg += f"{name} ({code}) - 5일 평균 거래대금: {int(value):,}원\n"
        send_telegram_message(msg)
    else:
        send_telegram_message("조건을 만족하는 종목이 없습니다.")

# ✅ 시작점
if __name__ == "__main__":
    run_filter()
