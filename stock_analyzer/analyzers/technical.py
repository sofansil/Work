"""
기술적 분석

주식의 기술적 지표를 계산하고 분석합니다.
"""

from typing import Optional, Dict
from datetime import datetime, timedelta
import pandas as pd

from stock_analyzer.utils.data_provider import DataProvider
from stock_analyzer.config import get_settings
from stock_analyzer.utils.logger import LoggerMixin


class TechnicalAnalyzer(LoggerMixin):
    """기술적 분석기"""

    def __init__(self, data_provider: DataProvider):
        """
        Args:
            data_provider: 데이터 제공자
        """
        self.data_provider = data_provider
        self.settings = get_settings().analysis

    def fetch_and_analyze(
        self,
        ticker: str,
        days: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        데이터를 가져와서 기술적 지표를 계산합니다.

        Args:
            ticker: 종목 코드
            days: 조회 기간 (일)

        Returns:
            지표가 추가된 데이터프레임
        """
        days = days or self.settings.lookback_days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # 데이터 조회
        df = self.data_provider.fetch_ohlcv(ticker, start_date, end_date)
        if df is None or df.empty:
            return None

        # 지표 계산
        df = self._calculate_indicators(df)
        return df.dropna()

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표를 계산합니다"""
        df = df.copy()

        # 이동평균
        df['MA5'] = df['종가'].rolling(self.settings.ma_period_short).mean()
        df['MA20'] = df['종가'].rolling(self.settings.ma_period_long).mean()

        # 거래량 평균
        df['vol_avg5'] = df['거래량'].rolling(self.settings.ma_period_short).mean()
        df['vol_avg20'] = df['거래량'].rolling(self.settings.volume_window).mean()

        # 20일 고가
        df['high20'] = df['고가'].rolling(self.settings.ma_period_long).max()
        df['low20'] = df['저가'].rolling(self.settings.ma_period_long).min()

        # 변동성
        df['volatility5'] = (df['고가'] - df['저가']).rolling(self.settings.ma_period_short).std()
        df['volatility20'] = (df['고가'] - df['저가']).rolling(self.settings.volatility_window).std()

        # 가격 변동률
        df['price_change'] = df['종가'].pct_change()

        return df

    def get_latest_indicators(self, ticker: str) -> Optional[Dict]:
        """
        최신 지표를 딕셔너리로 반환합니다.

        Args:
            ticker: 종목 코드

        Returns:
            지표 딕셔너리
        """
        df = self.fetch_and_analyze(ticker)
        if df is None or len(df) < self.settings.ma_period_long + 1:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # 최근 5일, 10일 저가
        low5 = df['저가'].tail(5)
        low10_prev5 = df['저가'].tail(10).head(5)

        # 캔들 정보
        candle_range = max(last['고가'] - last['저가'], 1e-9)
        body = last['종가'] - last['시가']

        indicators = {
            # 가격
            'close': float(last['종가']),
            'open': float(last['시가']),
            'high': float(last['고가']),
            'low': float(last['저가']),

            # 거래량
            'volume_today': float(last['거래량']),
            'volume_prev': float(prev['거래량']),

            # 이동평균
            'MA5': float(last['MA5']),
            'MA20': float(last['MA20']),

            # 거래량 평균
            'vol_avg5': float(last['vol_avg5']),
            'vol_avg20': float(last['vol_avg20']),

            # 고저가
            'high20': float(last['high20']),
            'low20': float(last['low20']),
            'min_low5': float(low5.min()),
            'min_low_prev5': float(low10_prev5.min() if len(low10_prev5) > 0 else low5.min()),

            # 변동성
            'volatility5': float(last['volatility5']),
            'volatility20': float(last['volatility20']),

            # 수익률
            'today_return': float((last['종가'] - last['시가']) / max(last['시가'], 1e-9) * 100),

            # 캔들
            'body': float(body),
            'candle_range': float(candle_range),
        }

        return indicators

    @staticmethod
    def calculate_volatility(df: pd.DataFrame, window: int) -> Optional[float]:
        """변동성을 계산합니다"""
        if len(df) < window + 1:
            return None
        return df['종가'].pct_change().tail(window).std()


if __name__ == "__main__":
    from stock_analyzer.utils.data_provider import create_data_provider

    # 테스트
    provider = create_data_provider('fdr', use_cache=True)
    analyzer = TechnicalAnalyzer(provider)

    # 삼성전자 분석
    indicators = analyzer.get_latest_indicators('005930')
    if indicators:
        print("삼성전자 최신 지표:")
        for key, value in indicators.items():
            print(f"  {key}: {value:,.2f}" if isinstance(value, float) else f"  {key}: {value}")
    else:
        print("지표 계산 실패")
