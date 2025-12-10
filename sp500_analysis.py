import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 한글 폰트 설정 (Windows)
plt.rcParams['font.family'] = 'malgun gothic'
plt.rcParams['axes.unicode_minus'] = False

# 1. 데이터 로드
df = pd.read_csv('S&P 500_fr2000.csv')

# 2. 데이터 구조 확인
print("데이터 shape:", df.shape)
print("\n첫 5행:")
print(df.head())
print("\n컬럼명:", df.columns.tolist())

# 3. 데이터 클렌징
# 날짜 컬럼 파싱 (공백 제거 후 변환)
df['날짜'] = df['날짜'].str.replace(' ', '')
df['날짜'] = pd.to_datetime(df['날짜'], format='%Y-%m-%d')

# 종가(Close) 컬럼 수치형으로 변환 (쉼표 제거)
df['종가'] = df['종가'].astype(str).str.replace(',', '')
df['종가'] = pd.to_numeric(df['종가'], errors='coerce')

# 결측치 제거
df = df.dropna(subset=['종가', '날짜'])

# 날짜순으로 정렬
df = df.sort_values('날짜').reset_index(drop=True)

# 2000년~2019년 데이터 필터링
df = df[(df['날짜'].dt.year >= 2000) & (df['날짜'].dt.year <= 2019)]

print("\n클렌징 후 데이터:")
print(f"행 개수: {len(df)}")
print(f"날짜 범위: {df['날짜'].min()} ~ {df['날짜'].max()}")
print("\n첫 5행:")
print(df.head())

# 4. 라인 그래프 그리기
plt.figure(figsize=(15, 7))
plt.plot(df['날짜'], df['종가'], linewidth=1.5, color='#1f77b4')
plt.title('S&P 500 종가 추이 (2000-2019)', fontsize=16, fontweight='bold')
plt.xlabel('날짜', fontsize=12)
plt.ylabel('종가 (달러)', fontsize=12)
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# 5. 기본 통계
print("\n기본 통계:")
print(df['종가'].describe())