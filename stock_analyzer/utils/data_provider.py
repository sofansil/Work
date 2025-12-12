"""
데이터 제공자

주식 데이터를 가져오는 추상 인터페이스와 구현체
"""

from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Optional, Dict
import pandas as pd
from cachetools import TTLCache
import FinanceDataReader as fdr
from pykrx import stock

from stock_analyzer.config import get_settings
from stock_analyzer.utils.logger import LoggerMixin


class DataProvider(ABC):
    """데이터 제공자 인터페이스"""

    @abstractmethod
    def fetch_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """
        OHLCV 데이터를 가져옵니다.

        Args:
            ticker: 종목 코드
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            OHLCV 데이터프레임 (None if error)
        """
        pass

    @abstractmethod
    def get_stock_list(self, market: str = 'KRX') -> pd.DataFrame:
        """
        종목 리스트를 가져옵니다.

        Args:
            market: 시장 구분 (KRX, KOSPI, KOSDAQ, etc.)

        Returns:
            종목 리스트 데이터프레임
        """
        pass


class FDRDataProvider(DataProvider, LoggerMixin):
    """FinanceDataReader 기반 데이터 제공자"""

    def fetch_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """FDR을 사용하여 OHLCV 데이터를 가져옵니다"""
        try:
            df = fdr.DataReader(ticker, start_date, end_date)
            if df is None or df.empty:
                return None

            # 컬럼명 통일 (Close -> 종가)
            column_mapping = {
                'Close': '종가',
                'Open': '시가',
                'High': '고가',
                'Low': '저가',
                'Volume': '거래량'
            }
            df = df.rename(columns=column_mapping)

            return df.dropna()

        except Exception as e:
            self.logger.error(f"FDR 데이터 조회 오류: {ticker} - {e}")
            return None

    def get_stock_list(self, market: str = 'KRX') -> pd.DataFrame:
        """FDR을 사용하여 종목 리스트를 가져옵니다"""
        try:
            return fdr.StockListing(market)
        except Exception as e:
            self.logger.error(f"종목 리스트 조회 오류: {market} - {e}")
            return pd.DataFrame()


class PyKRXDataProvider(DataProvider, LoggerMixin):
    """pykrx 기반 데이터 제공자"""

    def fetch_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """pykrx를 사용하여 OHLCV 데이터를 가져옵니다"""
        try:
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")

            df = stock.get_market_ohlcv(start_str, end_str, ticker)
            if df is None or df.empty:
                return None

            df = df.dropna().copy()
            df.index = pd.to_datetime(df.index)
            return df

        except Exception as e:
            self.logger.error(f"pykrx 데이터 조회 오류: {ticker} - {e}")
            return None

    def get_stock_list(self, market: str = 'KRX') -> pd.DataFrame:
        """pykrx는 종목 리스트 제공하지 않음 - FDR 사용 권장"""
        raise NotImplementedError("pykrx는 종목 리스트를 제공하지 않습니다. FDRDataProvider를 사용하세요.")


class CachedDataProvider(DataProvider, LoggerMixin):
    """캐싱을 적용한 데이터 제공자 (데코레이터 패턴)"""

    def __init__(self, provider: DataProvider):
        """
        Args:
            provider: 실제 데이터를 가져올 제공자
        """
        self.provider = provider
        settings = get_settings()
        cache_config = settings.cache

        if cache_config.enabled:
            self.cache = TTLCache(
                maxsize=cache_config.max_size,
                ttl=cache_config.ttl_seconds
            )
            self.logger.info(
                f"캐시 활성화 (크기: {cache_config.max_size}, TTL: {cache_config.ttl_seconds}초)"
            )
        else:
            self.cache = None
            self.logger.info("캐시 비활성화")

    def _make_cache_key(self, ticker: str, start_date: date, end_date: date) -> str:
        """캐시 키 생성"""
        return f"{ticker}_{start_date}_{end_date}"

    def fetch_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """캐시를 먼저 확인하고, 없으면 실제 데이터 조회"""
        if self.cache is None:
            # 캐시 비활성화 - 직접 조회
            return self.provider.fetch_ohlcv(ticker, start_date, end_date)

        cache_key = self._make_cache_key(ticker, start_date, end_date)

        if cache_key in self.cache:
            self.logger.debug(f"캐시 히트: {ticker}")
            return self.cache[cache_key].copy()

        # 캐시 미스 - 실제 데이터 조회
        self.logger.debug(f"캐시 미스: {ticker} - API 호출")
        df = self.provider.fetch_ohlcv(ticker, start_date, end_date)

        if df is not None:
            self.cache[cache_key] = df.copy()

        return df

    def get_stock_list(self, market: str = 'KRX') -> pd.DataFrame:
        """종목 리스트는 캐싱하지 않음 (자주 변경되지 않으므로)"""
        return self.provider.get_stock_list(market)

    def clear_cache(self):
        """캐시를 비웁니다"""
        if self.cache:
            self.cache.clear()
            self.logger.info("캐시 초기화 완료")

    def get_cache_stats(self) -> Dict[str, int]:
        """캐시 통계를 반환합니다"""
        if self.cache:
            return {
                'size': len(self.cache),
                'maxsize': self.cache.maxsize,
                'ttl': self.cache.ttl
            }
        return {'size': 0, 'maxsize': 0, 'ttl': 0}


def create_data_provider(
    provider_type: str = 'fdr',
    use_cache: bool = True
) -> DataProvider:
    """
    데이터 제공자를 생성합니다 (팩토리 함수).

    Args:
        provider_type: 제공자 타입 ('fdr' 또는 'pykrx')
        use_cache: 캐싱 사용 여부

    Returns:
        데이터 제공자 인스턴스
    """
    if provider_type == 'fdr':
        provider = FDRDataProvider()
    elif provider_type == 'pykrx':
        provider = PyKRXDataProvider()
    else:
        raise ValueError(f"알 수 없는 제공자 타입: {provider_type}")

    if use_cache:
        return CachedDataProvider(provider)

    return provider


if __name__ == "__main__":
    # 데이터 제공자 테스트
    provider = create_data_provider('fdr', use_cache=True)

    # OHLCV 조회 테스트
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)

    print("첫 번째 조회 (캐시 미스)...")
    df1 = provider.fetch_ohlcv('005930', start_date, end_date)
    print(f"데이터 크기: {len(df1) if df1 is not None else 0}")

    print("\n두 번째 조회 (캐시 히트)...")
    df2 = provider.fetch_ohlcv('005930', start_date, end_date)
    print(f"데이터 크기: {len(df2) if df2 is not None else 0}")

    # 캐시 통계
    if isinstance(provider, CachedDataProvider):
        stats = provider.get_cache_stats()
        print(f"\n캐시 통계: {stats}")
