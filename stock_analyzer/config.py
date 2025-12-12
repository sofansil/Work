"""
설정 관리 모듈

애플리케이션의 모든 설정을 중앙에서 관리합니다.
환경 변수를 통해 설정을 주입받으며, Pydantic을 사용하여 유효성을 검증합니다.
"""

from typing import Optional
from pydantic import BaseSettings, Field, validator
from pathlib import Path


# ============================================================================
# 빠른 설정 (Quick Settings)
# ============================================================================
# 여기서 주요 설정값을 빠르게 수정할 수 있습니다.
# .env 파일이 우선 적용되며, .env가 없을 때 아래 값이 사용됩니다.
# ============================================================================

# 병렬 처리 설정
DEFAULT_MAX_WORKERS = 12  # 스레드 수 (권장: 10-15, SQLite 안정성 고려)

# 분류 기준
DEFAULT_A_SCORE_THRESHOLD = 6  # A급 점수 기준
DEFAULT_B_SCORE_THRESHOLD = 4  # B급 점수 기준
DEFAULT_C_SCORE_THRESHOLD = 2  # C급 점수 기준

# 거래량 배수
DEFAULT_A_VOLUME_PREV = 3.0    # A급: 전일 대비 거래량
DEFAULT_A_VOLUME_AVG5 = 5.0    # A급: 5일 평균 대비 거래량
DEFAULT_B_VOLUME_MULTIPLIER = 2.0  # B급: 거래량 배수

# 타임아웃 설정
DEFAULT_SOCKET_TIMEOUT = 10    # 소켓 타임아웃 (초)
DEFAULT_REQUEST_TIMEOUT = 30   # 요청 타임아웃 (초)
DEFAULT_TOTAL_TIMEOUT = 300    # 전체 타임아웃 (초)

# ============================================================================


class ClassificationCriteria(BaseSettings):
    """A/B/C 등급 분류 기준"""

    # A급 기준
    a_score_threshold: int = Field(default=DEFAULT_A_SCORE_THRESHOLD, description="A급 점수 기준")
    a_volume_multiplier_prev: float = Field(default=DEFAULT_A_VOLUME_PREV, description="전일 대비 거래량 배수")
    a_volume_multiplier_avg5: float = Field(default=DEFAULT_A_VOLUME_AVG5, description="5일 평균 대비 거래량 배수")
    a_price_breakout_ratio: float = Field(default=1.04, description="가격 돌파 비율 (4%)")
    a_candle_body_ratio: float = Field(default=0.7, description="캔들 몸통 비율 (70%)")
    a_high20_proximity: float = Field(default=0.99, description="20일 고점 근접도 (99%)")

    # B급 기준
    b_score_threshold: int = Field(default=DEFAULT_B_SCORE_THRESHOLD, description="B급 점수 기준")
    b_high20_proximity: float = Field(default=0.95, description="20일 고점 근접도 (95%)")
    b_volume_multiplier: float = Field(default=DEFAULT_B_VOLUME_MULTIPLIER, description="거래량 배수")

    # C급 기준
    c_score_threshold: int = Field(default=DEFAULT_C_SCORE_THRESHOLD, description="C급 점수 기준")
    c_return_threshold: float = Field(default=2.0, description="상승률 기준 (%)")

    class Config:
        env_prefix = "CLASSIFICATION_"


class TelegramSettings(BaseSettings):
    """텔레그램 설정"""

    token: str = Field(..., env='TELEGRAM_TOKEN', description="텔레그램 봇 토큰")
    chat_id: str = Field(..., env='TELEGRAM_CHAT_ID', description="텔레그램 채팅 ID")
    max_message_length: int = Field(default=4096, description="최대 메시지 길이")

    class Config:
        env_prefix = "TELEGRAM_"


class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""

    url: str = Field(default='sqlite:///stock_history.db', description="데이터베이스 URL")
    echo: bool = Field(default=False, description="SQL 쿼리 로깅 여부")
    pool_size: int = Field(default=5, description="커넥션 풀 크기")
    max_overflow: int = Field(default=10, description="최대 오버플로우")

    class Config:
        env_prefix = "DB_"


class ScreeningSettings(BaseSettings):
    """스크리닝 설정"""

    default_threshold: float = Field(default=5.0, ge=0, le=100, description="기본 상승률 기준 (%)")
    max_workers: int = Field(default=DEFAULT_MAX_WORKERS, ge=1, le=50, description="병렬 처리 스레드 수")
    batch_size: int = Field(default=500, ge=100, le=2000, description="배치 크기")
    socket_timeout: int = Field(default=DEFAULT_SOCKET_TIMEOUT, ge=1, le=60, description="소켓 타임아웃 (초)")
    request_timeout: int = Field(default=DEFAULT_REQUEST_TIMEOUT, ge=5, le=120, description="요청 타임아웃 (초)")
    total_timeout: int = Field(default=DEFAULT_TOTAL_TIMEOUT, ge=60, le=3600, description="전체 타임아웃 (초)")
    rate_limit_delay: float = Field(default=0.1, ge=0.0, le=1.0, description="API 요청 지연 (초)")

    class Config:
        env_prefix = "SCREENING_"


class AnalysisSettings(BaseSettings):
    """분석 설정"""

    lookback_days: int = Field(default=120, ge=30, le=365, description="데이터 조회 기간 (일)")
    ma_period_short: int = Field(default=5, ge=3, le=20, description="단기 이동평균 기간")
    ma_period_long: int = Field(default=20, ge=10, le=60, description="장기 이동평균 기간")
    volume_window: int = Field(default=20, ge=5, le=60, description="거래량 평균 계산 기간")
    volatility_window: int = Field(default=20, ge=5, le=60, description="변동성 계산 기간")

    class Config:
        env_prefix = "ANALYSIS_"


class CacheSettings(BaseSettings):
    """캐시 설정"""

    enabled: bool = Field(default=True, description="캐시 사용 여부")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="캐시 TTL (초)")
    max_size: int = Field(default=1000, ge=100, le=10000, description="최대 캐시 크기")

    class Config:
        env_prefix = "CACHE_"


class LoggingSettings(BaseSettings):
    """로깅 설정"""

    level: str = Field(default="INFO", description="로그 레벨")
    file_path: Optional[str] = Field(default="stock_analyzer.log", description="로그 파일 경로")
    max_bytes: int = Field(default=10485760, description="로그 파일 최대 크기 (10MB)")
    backup_count: int = Field(default=5, description="백업 파일 개수")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="로그 포맷"
    )

    @validator('level')
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"로그 레벨은 {valid_levels} 중 하나여야 합니다")
        return v.upper()

    class Config:
        env_prefix = "LOG_"


class FilePathSettings(BaseSettings):
    """파일 경로 설정"""

    watchlist_json: str = Field(default="watchlist.json", description="Watchlist JSON 파일")
    watchlist_csv: str = Field(default="watchlist.csv", description="Watchlist CSV 파일")
    output_dir: str = Field(default="outputs", description="출력 파일 디렉토리")

    class Config:
        env_prefix = "FILE_"


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""

    # 하위 설정 그룹
    classification: ClassificationCriteria = ClassificationCriteria()
    telegram: TelegramSettings
    database: DatabaseSettings = DatabaseSettings()
    screening: ScreeningSettings = ScreeningSettings()
    analysis: AnalysisSettings = AnalysisSettings()
    cache: CacheSettings = CacheSettings()
    logging: LoggingSettings = LoggingSettings()
    file_paths: FilePathSettings = FilePathSettings()

    # 기타 설정
    debug: bool = Field(default=False, env='DEBUG', description="디버그 모드")

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        env_nested_delimiter = '__'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 출력 디렉토리 생성
        Path(self.file_paths.output_dir).mkdir(parents=True, exist_ok=True)


# 전역 설정 인스턴스
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """설정 인스턴스를 반환합니다 (싱글톤 패턴)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings():
    """설정을 다시 로드합니다"""
    global _settings
    _settings = Settings()
    return _settings


if __name__ == "__main__":
    # 설정 테스트
    settings = get_settings()
    print(f"텔레그램 토큰: {settings.telegram.token[:10]}...")
    print(f"데이터베이스 URL: {settings.database.url}")
    print(f"스크리닝 기본 임계값: {settings.screening.default_threshold}%")
    print(f"A급 점수 기준: {settings.classification.a_score_threshold}")
    print(f"로그 레벨: {settings.logging.level}")
