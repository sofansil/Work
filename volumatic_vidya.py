import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from matplotlib import font_manager, rc

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def calculate_cmo(data, period=14):
    """Chande Momentum Oscillator 계산"""
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
    """VIDYA (Variable Index Dynamic Average) 계산"""
    alpha = 2 / (period + 1)

    # CMO 계산
    cmo = calculate_cmo(data, cmo_period)
    cmo_ratio = abs(cmo) / 100

    # VIDYA 계산
    vidya = pd.Series(index=data.index, dtype=float)
    vidya.iloc[0] = data.iloc[0]

    for i in range(1, len(data)):
        if pd.notna(cmo_ratio.iloc[i]):
            adaptive_alpha = alpha * cmo_ratio.iloc[i]
            vidya.iloc[i] = adaptive_alpha * data.iloc[i] + (1 - adaptive_alpha) * vidya.iloc[i-1]
        else:
            vidya.iloc[i] = vidya.iloc[i-1]

    return vidya

def calculate_volumatic_vidya(data, volume, period=14, cmo_period=14):
    """Volumatic VIDYA - 거래량을 고려한 VIDYA"""
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
        if pd.notna(cmo_ratio.iloc[i]) and pd.notna(volume_ratio.iloc[i]):
            # 거래량 비율을 추가로 곱함
            adaptive_alpha = alpha * cmo_ratio.iloc[i] * volume_ratio.iloc[i]
            adaptive_alpha = min(adaptive_alpha, 1.0)  # 1.0을 넘지 않도록
            vidya.iloc[i] = adaptive_alpha * data.iloc[i] + (1 - adaptive_alpha) * vidya.iloc[i-1]
        else:
            vidya.iloc[i] = vidya.iloc[i-1]

    return vidya

# 데이터 다운로드 (애플 주식 최근 6개월)
print("데이터 다운로드 중...")
ticker = "AAPL"
data = yf.download(ticker, period="6mo", progress=False)

# 지표 계산
print("지표 계산 중...")
data['SMA_20'] = data['Close'].rolling(window=20).mean()
data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
data['VIDYA'] = calculate_vidya(data['Close'], period=20, cmo_period=14)
data['Volumatic_VIDYA'] = calculate_volumatic_vidya(data['Close'], data['Volume'], period=20, cmo_period=14)

# 그래프 그리기
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# 상단 차트: 가격과 이동평균선들
ax1.plot(data.index, data['Close'], label='종가', linewidth=2, color='black')
ax1.plot(data.index, data['SMA_20'], label='SMA(20)', linewidth=1.5, alpha=0.7, linestyle='--')
ax1.plot(data.index, data['EMA_20'], label='EMA(20)', linewidth=1.5, alpha=0.7, linestyle='--')
ax1.plot(data.index, data['VIDYA'], label='VIDYA(20)', linewidth=2, alpha=0.8)
ax1.plot(data.index, data['Volumatic_VIDYA'], label='Volumatic VIDYA(20)', linewidth=2, alpha=0.8)

ax1.set_title(f'{ticker} 주가와 이동평균선 비교', fontsize=16, fontweight='bold')
ax1.set_ylabel('가격 ($)', fontsize=12)
ax1.legend(loc='best', fontsize=10)
ax1.grid(True, alpha=0.3)

# 하단 차트: 거래량
ax2.bar(data.index, data['Volume'], label='거래량', alpha=0.5, color='blue')
ax2.set_title('거래량', fontsize=14, fontweight='bold')
ax2.set_xlabel('날짜', fontsize=12)
ax2.set_ylabel('거래량', fontsize=12)
ax2.legend(loc='best', fontsize=10)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('volumatic_vidya_analysis.png', dpi=150, bbox_inches='tight')
print("\n그래프가 'volumatic_vidya_analysis.png'로 저장되었습니다.")
plt.show()

# 최근 데이터 출력
print("\n" + "="*80)
print("최근 5일 데이터:")
print("="*80)
print(data[['Close', 'SMA_20', 'EMA_20', 'VIDYA', 'Volumatic_VIDYA']].tail().round(2))
