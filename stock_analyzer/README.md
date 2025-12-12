# 주식 분석 시스템 (Stock Analyzer)

한국 주식 시장에서 급등 가능성이 있는 종목을 자동으로 스크리닝하고 텔레그램으로 알림을 보내는 시스템입니다.

## ✨ 주요 기능

### 1. 급등주 스크리닝
- **20일 이동평균 기준**: 설정한 상승률 이상의 종목 필터링
- **거래량 필터**: 평균 거래량 대비 특정 배수 이상 조건
- **이력 추적**: 발견 횟수, 연속 발견 횟수 자동 기록

### 2. A/B/C 등급 분류
- **A급 (급등 초기)**: VCP 패턴 + 거래량 폭발 + 고점 돌파
- **B급 (강세 유지)**: 고점 근접 + 거래량 증가 + 저점 상승
- **C급 (관심 종목)**: 20일선 위 + 상승 추세 + 거래량 증가

### 3. 데이터베이스 관리
- SQLAlchemy ORM 사용
- 종목 이력, 일별 기록, 스크리닝 결과 저장
- 통계 조회 기능

### 4. 텔레그램 알림
- 스크리닝 결과 자동 전송
- 긴 메시지 자동 분할
- 포맷팅된 보고서

## 🏗️ 아키텍처

```
stock_analyzer/
├── analyzers/          # 기술적 분석 및 신호 분류
│   ├── technical.py
│   └── classifier.py
├── database/           # 데이터베이스 모델 및 작업
│   ├── models.py
│   └── operations.py
├── screeners/          # 주식 스크리너
│   └── surge_screener.py
├── notifiers/          # 알림 (텔레그램)
│   └── telegram.py
├── utils/              # 유틸리티
│   ├── logger.py
│   ├── parallel.py
│   └── data_provider.py
├── config.py           # 설정 관리
└── main.py             # 메인 애플리케이션
```

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 입력합니다:

```env
# 텔레그램 설정
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# 데이터베이스 (선택사항, 기본값 사용 가능)
DB_URL=sqlite:///stock_history.db

# 스크리닝 설정 (선택사항)
SCREENING_DEFAULT_THRESHOLD=5.0
SCREENING_MAX_WORKERS=12  # 권장: 10-15

# 로깅 설정 (선택사항)
LOG_LEVEL=INFO
LOG_FILE_PATH=stock_analyzer.log

# 캐시 설정 (선택사항)
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
```

### 3. 실행

```bash
# 메인 디렉토리에서 실행
cd stock_analyzer
python main.py
```

또는

```bash
# 모듈로 실행
python -m stock_analyzer.main
```

## 📊 사용 예시

### 1. MA 기준 스크리닝

```python
from stock_analyzer.main import StockAnalyzerApp

app = StockAnalyzerApp()

# 5% 이상 상승, 거래량 2배 이상
results = app.screener.screen_by_ma_threshold(
    threshold=5.0,
    volume_multiplier=2.0,
    max_workers=12  # 권장: 10-15
)

print(f"발견: {len(results)}개 종목")
```

### 2. A/B/C 등급 분류

```python
from stock_analyzer.main import StockAnalyzerApp

app = StockAnalyzerApp()

# 급등주 초기 포착
results_by_grade = app.screener.screen_surge_stocks(max_workers=10)

print(f"A급: {len(results_by_grade['A'])}개")
print(f"B급: {len(results_by_grade['B'])}개")
print(f"C급: {len(results_by_grade['C'])}개")
```

### 3. 텔레그램 알림

```python
from stock_analyzer.notifiers.telegram import TelegramNotifier

notifier = TelegramNotifier()

# 간단한 메시지
notifier.send_message_sync("테스트 메시지")

# 스크리닝 결과 전송
message = notifier.format_screening_results(results, threshold=5.0)
notifier.send_message_sync(message)
```

## ⚙️ 설정 커스터마이징

### 병렬 처리 최적화

스레드 수는 SQLite 안정성과 성능의 균형을 고려하여 설정하세요:

```env
# 안정성 우선 (추천 - 프로덕션 환경)
SCREENING_MAX_WORKERS=10

# 균형 설정 (기본값)
SCREENING_MAX_WORKERS=12

# 성능 우선 (리스크 증가)
SCREENING_MAX_WORKERS=15
```

**참고:**
- 10-15개: SQLite database lock 최소화, 안정적
- 20개 이상: 과도한 경합, 에러율 증가
- 코드 상단 수정: [`stock_analyzer/config.py`](stock_analyzer/config.py) 파일의 `DEFAULT_MAX_WORKERS` 변수

### A/B/C 등급 기준 변경

```env
# A급 기준
CLASSIFICATION_A_SCORE_THRESHOLD=6
CLASSIFICATION_A_VOLUME_MULTIPLIER_PREV=3.0
CLASSIFICATION_A_VOLUME_MULTIPLIER_AVG5=5.0

# B급 기준
CLASSIFICATION_B_SCORE_THRESHOLD=4
CLASSIFICATION_B_VOLUME_MULTIPLIER=2.0

# C급 기준
CLASSIFICATION_C_SCORE_THRESHOLD=2
CLASSIFICATION_C_RETURN_THRESHOLD=2.0
```

### 캐시 설정

```env
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600  # 1시간
CACHE_MAX_SIZE=1000      # 최대 1000개 항목
```

## 🗄️ 데이터베이스 스키마

### stock_history
- 종목코드 (PK)
- 종목명, 테마명
- 최초발견일, 최종발견일
- 발견횟수, 연속발견횟수
- 최대상승률, 최대가격

### daily_records
- 종목코드 (FK)
- 발견일, 현재가, 상승률, 거래량

### surge_screening_results
- 종목코드, 종목명, 시장
- grade (A/B/C), score
- 스크리닝날짜, status (new/old)

## 🔧 개선 사항 (stock_analyzer3.py 대비)

### 1. 아키텍처
- ✅ 모듈화된 구조 (단일 파일 → 패키지)
- ✅ 관심사 분리 (DB, 분석, 알림 분리)
- ✅ 의존성 주입

### 2. 설정 관리
- ✅ Pydantic 기반 설정 (타입 안정성)
- ✅ 환경 변수 검증
- ✅ 하드코딩 제거

### 3. 로깅
- ✅ 체계적인 로깅 (print → logging)
- ✅ 파일 로깅 + 콘솔 출력
- ✅ 로그 레벨 제어

### 4. 오류 처리
- ✅ 구체적인 예외 처리
- ✅ 오류 추적 및 통계
- ✅ 재시도 로직

### 5. 데이터베이스
- ✅ SQLAlchemy ORM
- ✅ 컨텍스트 매니저
- ✅ 트랜잭션 관리

### 6. 병렬 처리
- ✅ 재사용 가능한 ParallelProcessor
- ✅ 진행 상황 추적
- ✅ 타임아웃 관리

### 7. 데이터 제공자
- ✅ 추상 인터페이스
- ✅ 캐싱 (TTL)
- ✅ 교체 가능한 구현체

### 8. 타입 안정성
- ✅ 타입 힌트
- ✅ 데이터클래스
- ✅ Pydantic 모델

## 🧪 테스트

```bash
# 전체 테스트 실행
pytest

# 커버리지 포함
pytest --cov=stock_analyzer

# 특정 모듈 테스트
pytest tests/test_classifier.py
```

## 📝 라이선스

MIT License

## 🤝 기여

이슈 리포트 및 PR 환영합니다!

## 📧 문의

문제가 발생하면 GitHub Issues에 등록해주세요.
