import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def calculate_cmo(data, period=14):
    """
    Chande Momentum Oscillator 계산
    """
    delta = data.diff()

    up = delta.copy()
    down = delta.copy()

    up[up < 0] = 0
    down[down > 0] = 0
    down = abs(down)

    up_sum = up.rolling(window=period).sum()
    down_sum = down.rolling(window=period).sum()

    cmo = 100 * (up_sum - down_sum) / (up_sum + down_sum)

    return cmo

def calculate_vidya(data, period=14, cmo_period=14):
    """
    VIDYA (Variable Index Dynamic Average) 계산
    변동성에 따라 적응하는 이동평균선
    """
    alpha = 2 / (period + 1)

    # CMO 계산
    cmo = calculate_cmo(data, cmo_period)
    cmo_ratio = abs(cmo) / 100

    # VIDYA 계산
    vidya = pd.Series(index=data.index, dtype=float)
    vidya.iloc[0] = data.iloc[0]

    for i in range(1, len(data)):
        cmo_val = cmo_ratio.iloc[i]
        # Series인 경우 스칼라로 변환
        if isinstance(cmo_val, pd.Series):
            cmo_val = cmo_val.values[0] if len(cmo_val) > 0 else np.nan

        if not pd.isna(cmo_val):
            adaptive_alpha = alpha * cmo_val
            vidya.iloc[i] = adaptive_alpha * data.iloc[i] + (1 - adaptive_alpha) * vidya.iloc[i-1]
        else:
            vidya.iloc[i] = vidya.iloc[i-1]

    return vidya

def calculate_volumatic_vidya(data, volume, period=14, cmo_period=14):
    """
    Volumatic VIDYA - 거래량을 고려한 VIDYA
    변동성과 거래량을 모두 고려하여 적응
    """
    alpha = 2 / (period + 1)

    # CMO 계산
    cmo = calculate_cmo(data, cmo_period)
    cmo_ratio = abs(cmo) / 100

    # 거래량 비율 계산 (현재 거래량 / 평균 거래량)
    avg_volume = volume.rolling(window=period).mean()
    volume_ratio = volume / avg_volume
    volume_ratio = volume_ratio.clip(upper=2.0)  # 최대값 제한

    # Volumatic VIDYA 계산
    vidya = pd.Series(index=data.index, dtype=float)
    vidya.iloc[0] = data.iloc[0]

    for i in range(1, len(data)):
        cmo_val = cmo_ratio.iloc[i]
        vol_val = volume_ratio.iloc[i]

        # Series인 경우 스칼라로 변환
        if isinstance(cmo_val, pd.Series):
            cmo_val = cmo_val.values[0] if len(cmo_val) > 0 else np.nan
        if isinstance(vol_val, pd.Series):
            vol_val = vol_val.values[0] if len(vol_val) > 0 else np.nan

        if not pd.isna(cmo_val) and not pd.isna(vol_val):
            # 거래량 비율을 추가로 곱함
            adaptive_alpha = alpha * cmo_val * vol_val
            adaptive_alpha = min(adaptive_alpha, 1.0)  # 1.0을 넘지 않도록
            vidya.iloc[i] = adaptive_alpha * data.iloc[i] + (1 - adaptive_alpha) * vidya.iloc[i-1]
        else:
            vidya.iloc[i] = vidya.iloc[i-1]

    return vidya

def main():
    # 사용자 설정
    # KOSPI: ^KS11, KOSDAQ: ^KQ11
    # 개별 종목: 005930.KS (삼성전자), 035720.KS (카카오), 000660.KS (SK하이닉스)
    # ticker = "^KS11"  # KOSPI 지수
    # ticker = "^KQ11"  # KOSDAQ 지수 (선택)
    ticker = "060280.KS"  # 삼성전자 (선택)
    period = "6mo"   # 기간 (1mo, 3mo, 6mo, 1y 등)

    print(f"{'='*80}")
    print(f"Volumatic VIDYA 지표 분석 (한국 시장)")
    print(f"{'='*80}")

    # 종목명 표시
    if ticker == "^KS11":
        ticker_name = "KOSPI"
    elif ticker == "^KQ11":
        ticker_name = "KOSDAQ"
    else:
        ticker_name = ticker

    print(f"종목: {ticker_name} ({ticker})")
    print(f"기간: {period}")
    print(f"{'='*80}\n")

    # 데이터 다운로드
    print("데이터 다운로드 중...")
    data = yf.download(ticker, period=period, progress=False)

    if data.empty:
        print("데이터를 다운로드할 수 없습니다.")
        print("참고: 한국 종목 코드 형식")
        print("  - KOSPI 지수: ^KS11")
        print("  - KOSDAQ 지수: ^KQ11")
        print("  - 개별 종목: 종목코드.KS (예: 005930.KS)")
        return

    # MultiIndex 컬럼을 평탄화 (yfinance v2 대응)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    # Series를 DataFrame으로 처리
    if isinstance(data, pd.Series):
        data = data.to_frame()

    # 지표 계산
    print("지표 계산 중...")
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
    data['VIDYA'] = calculate_vidya(data['Close'], period=20, cmo_period=14)
    data['Volumatic_VIDYA'] = calculate_volumatic_vidya(data['Close'], data['Volume'], period=20, cmo_period=14)
    data['CMO'] = calculate_cmo(data['Close'], period=14)

    # 그래프 그리기
    print("그래프 생성 중...")
    fig = plt.figure(figsize=(16, 12))

    # 1. 가격 차트
    ax1 = plt.subplot(3, 1, 1)
    ax1.plot(data.index, data['Close'], label='종가', linewidth=2, color='black', alpha=0.7)
    ax1.plot(data.index, data['SMA_20'], label='SMA(20)', linewidth=1.5, alpha=0.7, linestyle='--', color='blue')
    ax1.plot(data.index, data['EMA_20'], label='EMA(20)', linewidth=1.5, alpha=0.7, linestyle='--', color='green')
    ax1.plot(data.index, data['VIDYA'], label='VIDYA(20)', linewidth=2, alpha=0.8, color='orange')
    ax1.plot(data.index, data['Volumatic_VIDYA'], label='Volumatic VIDYA(20)', linewidth=2.5, alpha=0.9, color='red')

    ax1.set_title(f'{ticker_name} - 가격과 이동평균선 비교', fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('지수' if ticker.startswith('^') else '가격 (원)', fontsize=12)
    ax1.legend(loc='best', fontsize=11)
    ax1.grid(True, alpha=0.3, linestyle='--')

    # 2. CMO (Chande Momentum Oscillator)
    ax2 = plt.subplot(3, 1, 2)
    ax2.plot(data.index, data['CMO'], label='CMO(14)', linewidth=2, color='purple')
    ax2.axhline(y=50, color='r', linestyle='--', alpha=0.5, label='과매수(+50)')
    ax2.axhline(y=-50, color='g', linestyle='--', alpha=0.5, label='과매도(-50)')
    ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax2.fill_between(data.index, 0, data['CMO'], where=(data['CMO'] > 0), alpha=0.3, color='green')
    ax2.fill_between(data.index, 0, data['CMO'], where=(data['CMO'] < 0), alpha=0.3, color='red')

    ax2.set_title('Chande Momentum Oscillator (CMO)', fontsize=14, fontweight='bold', pad=15)
    ax2.set_ylabel('CMO 값', fontsize=12)
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')

    # 3. 거래량
    ax3 = plt.subplot(3, 1, 3)

    # 거래량 막대 그래프 (단색)
    ax3.bar(data.index, data['Volume'], label='거래량', alpha=0.6, color='steelblue')
    ax3.plot(data.index, data['Volume'].rolling(window=20).mean(),
             label='평균 거래량(20)', linewidth=2, color='blue', alpha=0.8)

    ax3.set_title('거래량', fontsize=14, fontweight='bold', pad=15)
    ax3.set_xlabel('날짜', fontsize=12)
    ax3.set_ylabel('거래량', fontsize=12)
    ax3.legend(loc='best', fontsize=10)
    ax3.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()

    # 그래프 저장
    filename = f'{ticker_name}_volumatic_vidya_analysis.png'
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\n그래프가 '{filename}'로 저장되었습니다.")

    # 통계 정보 출력
    print(f"\n{'='*80}")
    print("최근 5일 데이터:")
    print(f"{'='*80}")
    recent_data = data[['Close', 'SMA_20', 'EMA_20', 'VIDYA', 'Volumatic_VIDYA', 'CMO']].tail()
    print(recent_data.round(2))

    print(f"\n{'='*80}")
    print("지표 분석:")
    print(f"{'='*80}")
    last_close = data['Close'].iloc[-1]
    last_vidya = data['VIDYA'].iloc[-1]
    last_vol_vidya = data['Volumatic_VIDYA'].iloc[-1]
    last_cmo = data['CMO'].iloc[-1]

    price_unit = "" if ticker.startswith('^') else "원"
    print(f"현재 종가: {last_close:,.2f}{price_unit}")
    print(f"VIDYA: {last_vidya:,.2f}{price_unit} ({'+' if last_close > last_vidya else ''}{((last_close/last_vidya - 1) * 100):.2f}%)")
    print(f"Volumatic VIDYA: {last_vol_vidya:,.2f}{price_unit} ({'+' if last_close > last_vol_vidya else ''}{((last_close/last_vol_vidya - 1) * 100):.2f}%)")
    print(f"CMO: {last_cmo:.2f}")

    if last_cmo > 50:
        print("→ CMO가 +50 이상: 강한 상승 모멘텀 (과매수 주의)")
    elif last_cmo < -50:
        print("→ CMO가 -50 이하: 강한 하락 모멘텀 (과매도 주의)")
    elif last_cmo > 0:
        print("→ CMO가 양수: 상승 모멘텀")
    else:
        print("→ CMO가 음수: 하락 모멘텀")

    print(f"{'='*80}\n")

    # 그래프 표시
    plt.show()

if __name__ == "__main__":
    main()
