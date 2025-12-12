import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from telegram import Bot
import asyncio
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def send_telegram_message(message):
    """텔레그램으로 메시지 전송"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        async with bot:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        return True
    except Exception as e:
        print(f"[오류] 텔레그램 전송 오류: {str(e)}")
        return False

def screen_stocks(threshold=5.0):
    """
    20일 이동평균 대비 현재가가 threshold% 이상 상승한 종목 찾기

    Args:
        threshold: 상승률 기준 (기본값: 5.0%)
    """
    print("[시작] KRX 종목 스크리닝 시작...")
    print(f"[조건] 20일 이동평균 대비 {threshold}% 이상 상승 종목")
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

    # 각 종목 분석
    for idx, row in df_krx.iterrows():
        code = row['Code']
        name = row['Name']
        market = row['Market']

        try:
            # 데이터 가져오기
            hist = fdr.DataReader(code, start_date, end_date)

            if len(hist) < 20:
                continue

            # 현재가와 20일 이동평균 계산
            current_price = hist['Close'].iloc[-1]
            ma_20 = hist['Close'].tail(20).mean()

            # 상승률 계산
            diff_pct = ((current_price - ma_20) / ma_20) * 100

            if diff_pct >= threshold:
                results.append({
                    '종목코드': code,
                    '종목명': name,
                    '시장': market,
                    '현재가': int(current_price),
                    '20일평균': int(ma_20),
                    '상승률': round(diff_pct, 2),
                    '거래량': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
                })

                print(f"[발견] {code} {name} ({market}) - 현재가: {int(current_price):,}원, 상승률: {diff_pct:.2f}%")

        except Exception as e:
            # 데이터가 없거나 오류가 있는 종목은 조용히 넘어감
            pass

        # 진행상황 표시 (100개마다)
        if (idx + 1) % 100 == 0:
            print(f"[진행] {idx + 1}/{len(df_krx)} 종목 분석 완료...")

    print("\n" + "="*70)
    print(f"[완료] 총 {len(results)}개 종목이 조건을 만족합니다.\n")

    return results

def format_results(results, threshold):
    """결과를 텔레그램 메시지 형식으로 포맷"""
    if not results:
        return f"20일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

    # 상승률 순으로 정렬
    results_sorted = sorted(results, key=lambda x: x['상승률'], reverse=True)

    # 상위 20개만 선택
    top_results = results_sorted[:20]

    message = f"""
📊 주식 스크리닝 결과
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

async def main():
    """메인 함수"""
    import sys

    # 명령줄 인자로 threshold 받기
    if len(sys.argv) > 1:
        try:
            threshold = float(sys.argv[1])
        except ValueError:
            print("[오류] 잘못된 입력입니다. 기본값 5%를 사용합니다.")
            threshold = 5.0
    else:
        threshold = 5.0

    print(f"\n[설정] 상승률 기준: {threshold}%")

    # 스크리닝 실행
    results = screen_stocks(threshold)

    # 결과 포맷
    message = format_results(results, threshold)

    # 콘솔 출력
    print("\n" + "="*70)
    print("[결과 미리보기]")
    print("="*70)
    print(message)

    # 자동으로 텔레그램 전송
    print("\n[전송] 텔레그램으로 전송 중...")
    success = await send_telegram_message(message)
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

if __name__ == "__main__":
    asyncio.run(main())
