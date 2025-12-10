import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 1. 데이터 읽기
print("=" * 50)
print("1. 데이터 읽기")
print("=" * 50)
df = pd.read_excel('출생아수_합계출산율.xlsx')
print("\n원본 데이터:")
print(df.head(10))
print(f"\n데이터 shape: {df.shape}")
print(f"\n데이터 타입:\n{df.dtypes}")
print(f"\n결측치 확인:\n{df.isnull().sum()}")

# 2. 데이터 클렌징
print("\n" + "=" * 50)
print("2. 데이터 클렌징")
print("=" * 50)

# 결측치 제거
df_clean = df.dropna()
print(f"\n결측치 제거 후 shape: {df_clean.shape}")

# 데이터 타입 확인 및 변환
for col in df_clean.columns:
    print(f"\n{col} 컬럼:")
    print(f"  - 타입: {df_clean[col].dtype}")
    print(f"  - 샘플 값: {df_clean[col].iloc[0]}")

# 숫자형 변환이 필요한 경우 처리
for col in df_clean.columns:
    if col != df_clean.columns[0]:  # 첫 번째 컬럼(연도) 제외
        try:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        except:
            pass

# 중복 제거
df_clean = df_clean.drop_duplicates()
print(f"\n중복 제거 후 shape: {df_clean.shape}")

# 정렬 (연도별)
df_clean = df_clean.sort_values(by=df_clean.columns[0])
df_clean = df_clean.reset_index(drop=True)

print("\n클렌징된 데이터:")
print(df_clean.head(10))

# 3. 다각도 데이터 분석
print("\n" + "=" * 50)
print("3. 다각도 데이터 분석")
print("=" * 50)

# 기본 통계
print("\n[기본 통계량]")
print(df_clean.describe())

# 출생아수 분석 (두 번째 컬럼으로 가정)
birth_col = df_clean.columns[1]
year_col = df_clean.columns[0]

print(f"\n[{birth_col} 분석]")
print(f"  - 평균: {df_clean[birth_col].mean():,.0f}명")
print(f"  - 중앙값: {df_clean[birth_col].median():,.0f}명")
print(f"  - 최댓값: {df_clean[birth_col].max():,.0f}명 ({df_clean.loc[df_clean[birth_col].idxmax(), year_col]}년)")
print(f"  - 최솟값: {df_clean[birth_col].min():,.0f}명 ({df_clean.loc[df_clean[birth_col].idxmin(), year_col]}년)")
print(f"  - 표준편차: {df_clean[birth_col].std():,.0f}명")

# 변화율 분석
df_clean['전년대비_변화율'] = df_clean[birth_col].pct_change() * 100
print(f"\n[전년 대비 변화율]")
print(f"  - 평균 변화율: {df_clean['전년대비_변화율'].mean():.2f}%")
print(f"  - 최대 증가율: {df_clean['전년대비_변화율'].max():.2f}% ({df_clean.loc[df_clean['전년대비_변화율'].idxmax(), year_col]}년)")
print(f"  - 최대 감소율: {df_clean['전년대비_변화율'].min():.2f}% ({df_clean.loc[df_clean['전년대비_변화율'].idxmin(), year_col]}년)")

# 합계출산율 분석 (세 번째 컬럼이 있는 경우)
if len(df_clean.columns) >= 3:
    fertility_col = df_clean.columns[2]
    print(f"\n[{fertility_col} 분석]")
    print(f"  - 평균: {df_clean[fertility_col].mean():.3f}")
    print(f"  - 중앙값: {df_clean[fertility_col].median():.3f}")
    print(f"  - 최댓값: {df_clean[fertility_col].max():.3f} ({df_clean.loc[df_clean[fertility_col].idxmax(), year_col]}년)")
    print(f"  - 최솟값: {df_clean[fertility_col].min():.3f} ({df_clean.loc[df_clean[fertility_col].idxmin(), year_col]}년)")

# 기간별 분석
total_years = len(df_clean)
if total_years >= 10:
    print(f"\n[기간별 평균 {birth_col}]")
    split_idx = total_years // 2
    first_half = df_clean.iloc[:split_idx]
    second_half = df_clean.iloc[split_idx:]

    print(f"  - 전반기 ({first_half[year_col].min()}~{first_half[year_col].max()}): {first_half[birth_col].mean():,.0f}명")
    print(f"  - 후반기 ({second_half[year_col].min()}~{second_half[year_col].max()}): {second_half[birth_col].mean():,.0f}명")
    print(f"  - 변화: {((second_half[birth_col].mean() / first_half[birth_col].mean() - 1) * 100):.2f}%")

# 상관관계 분석
if len(df_clean.columns) >= 3:
    print(f"\n[상관관계 분석]")
    corr = df_clean[[birth_col, fertility_col]].corr()
    print(corr)

# 4. 출생아수 연도별 라인그래프
print("\n" + "=" * 50)
print("4. 출생아수 연도별 라인그래프 생성")
print("=" * 50)

plt.figure(figsize=(14, 8))

# 라인그래프
plt.subplot(2, 1, 1)
plt.plot(df_clean[year_col], df_clean[birth_col], marker='o', linewidth=2, markersize=6, color='#2E86AB')
plt.title(f'대한민국 연도별 {birth_col} 추이', fontsize=16, fontweight='bold', pad=20)
plt.xlabel('연도', fontsize=12, fontweight='bold')
plt.ylabel(birth_col, fontsize=12, fontweight='bold')
plt.grid(True, alpha=0.3, linestyle='--')
plt.xticks(rotation=45)

# 최대/최소값 표시
max_idx = df_clean[birth_col].idxmax()
min_idx = df_clean[birth_col].idxmin()
plt.scatter(df_clean.loc[max_idx, year_col], df_clean.loc[max_idx, birth_col],
           color='red', s=200, zorder=5, label=f'최댓값: {df_clean.loc[max_idx, birth_col]:,.0f}명')
plt.scatter(df_clean.loc[min_idx, year_col], df_clean.loc[min_idx, birth_col],
           color='orange', s=200, zorder=5, label=f'최솟값: {df_clean.loc[min_idx, birth_col]:,.0f}명')
plt.legend(fontsize=10)

# 합계출산율이 있는 경우 추가
if len(df_clean.columns) >= 3:
    plt.subplot(2, 1, 2)
    plt.plot(df_clean[year_col], df_clean[fertility_col], marker='s', linewidth=2, markersize=6, color='#A23B72')
    plt.title(f'대한민국 연도별 {fertility_col} 추이', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('연도', fontsize=12, fontweight='bold')
    plt.ylabel(fertility_col, fontsize=12, fontweight='bold')
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.xticks(rotation=45)
    plt.axhline(y=2.1, color='r', linestyle='--', alpha=0.5, label='인구 대체 수준 (2.1)')
    plt.legend(fontsize=10)

plt.tight_layout()
plt.savefig('출생아수_분석_그래프.png', dpi=300, bbox_inches='tight')
print("\n그래프 저장 완료: 출생아수_분석_그래프.png")
plt.show()

print("\n" + "=" * 50)
print("분석 완료!")
print("=" * 50)
