"""
급등주 스크리너

주식 시장을 스캔하여 급등 가능성이 있는 종목을 찾습니다.
"""

from typing import List, Dict, Optional, Callable
from datetime import datetime
import pandas as pd

from stock_analyzer.utils.data_provider import DataProvider
from stock_analyzer.analyzers.technical import TechnicalAnalyzer
from stock_analyzer.analyzers.classifier import SignalClassifier
from stock_analyzer.database.operations import DatabaseManager
from stock_analyzer.utils.parallel import ParallelProcessor
from stock_analyzer.utils.logger import LoggerMixin
from stock_analyzer.config import get_settings


class StockScreener(LoggerMixin):
    """통합 주식 스크리너"""

    def __init__(
        self,
        data_provider: DataProvider,
        db_manager: DatabaseManager,
        analyzer: TechnicalAnalyzer,
        classifier: SignalClassifier
    ):
        """
        Args:
            data_provider: 데이터 제공자
            db_manager: 데이터베이스 관리자
            analyzer: 기술적 분석기
            classifier: 신호 분류기
        """
        self.data_provider = data_provider
        self.db = db_manager
        self.analyzer = analyzer
        self.classifier = classifier
        self.settings = get_settings()

    def screen_by_ma_threshold(
        self,
        threshold: float,
        market: str = 'KRX',
        volume_multiplier: float = 1.0,
        max_workers: int = 20
    ) -> List[Dict]:
        """
        20일 이동평균 대비 상승률 기준으로 스크리닝합니다.

        Args:
            threshold: 상승률 기준 (%)
            market: 시장 (KRX, KOSPI, KOSDAQ)
            volume_multiplier: 거래량 배수 조건
            max_workers: 병렬 처리 워커 수

        Returns:
            조건을 만족하는 종목 리스트
        """
        self.logger.info(f"스크리닝 시작: {threshold}% 임계값, 거래량 배수: {volume_multiplier}")

        # 종목 리스트 가져오기
        df_stocks = self.data_provider.get_stock_list(market)
        if market == 'KRX':
            df_stocks = df_stocks[df_stocks['Market'] != 'KONEX']

        self.logger.info(f"총 {len(df_stocks)}개 종목 스캔")

        # 병렬 처리
        processor = ParallelProcessor(
            max_workers=max_workers,
            timeout=self.settings.screening.total_timeout,
            item_timeout=self.settings.screening.request_timeout
        )

        def analyze_stock(row):
            return self._analyze_single_stock(
                row['Code'],
                row['Name'],
                row['Market'],
                threshold,
                volume_multiplier
            )

        result = processor.process(
            items=df_stocks.to_dict('records'),
            func=analyze_stock,
            desc="MA 기준 스크리닝"
        )

        # DB에 이력 저장
        for stock in result.successes:
            history = self.db.update_stock_history(stock)
            stock.update(history)

        self.logger.info(f"스크리닝 완료: {len(result.successes)}개 발견")
        return result.successes

    def _analyze_single_stock(
        self,
        code: str,
        name: str,
        market: str,
        threshold: float,
        volume_multiplier: float
    ) -> Optional[Dict]:
        """단일 종목 분석 (MA 기준)"""
        try:
            df = self.analyzer.fetch_and_analyze(code, days=50)
            if df is None or len(df) < 20:
                return None

            last = df.iloc[-1]

            # 상승률 계산
            current_price = last['종가']
            ma_20 = last['MA20']
            diff_pct = ((current_price - ma_20) / ma_20) * 100

            # 상승률 조건 체크
            if diff_pct < threshold:
                return None

            # 거래량 조건 체크
            if volume_multiplier > 1.0:
                current_volume = last['거래량']
                avg_volume_20 = last['vol_avg20']
                if current_volume < (avg_volume_20 * volume_multiplier):
                    return None

            volume_ratio = (last['거래량'] / last['vol_avg20']) if last['vol_avg20'] > 0 else 0

            return {
                '종목코드': code,
                '종목명': name,
                '시장': market,
                '현재가': int(current_price),
                '20일평균': int(ma_20),
                '상승률': round(diff_pct, 2),
                '거래량': int(last['거래량']),
                '평균거래량': int(last['vol_avg20']),
                '거래량비율': round(volume_ratio, 2)
            }

        except Exception as e:
            self.logger.debug(f"종목 분석 오류: {code} - {e}")
            return None

    def screen_surge_stocks(
        self,
        market: str = 'KRX',
        max_workers: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        급등주 초기 포착 (A/B/C 분류).

        Args:
            market: 시장 (KRX, KOSPI, KOSDAQ)
            max_workers: 병렬 처리 워커 수

        Returns:
            A/B/C 등급별 종목 딕셔너리
        """
        self.logger.info(f"급등주 초기 포착 시작 (A/B/C 분류)")

        # 종목 리스트
        df_stocks = self.data_provider.get_stock_list(market)
        if market == 'KRX':
            df_stocks = df_stocks[df_stocks['Market'].isin(['KOSPI', 'KOSDAQ'])]

        self.logger.info(f"총 {len(df_stocks)}개 종목 분석")

        # 병렬 처리
        processor = ParallelProcessor(
            max_workers=max_workers,
            timeout=self.settings.screening.total_timeout,
            item_timeout=self.settings.screening.request_timeout
        )

        def analyze_stock(row):
            return self._classify_single_stock(
                row['Code'],
                row['Name'],
                row['Market']
            )

        result = processor.process(
            items=df_stocks.to_dict('records'),
            func=analyze_stock,
            desc="급등주 분류"
        )

        # 등급별 분류
        results_by_grade = {'A': [], 'B': [], 'C': []}
        for stock in result.successes:
            grade = stock.get('class')
            if grade in results_by_grade:
                results_by_grade[grade].append(stock)

        # DB에 저장
        all_results = results_by_grade['A'] + results_by_grade['B'] + results_by_grade['C']
        if all_results:
            self.db.save_surge_results(all_results)

        self.logger.info(
            f"급등주 분류 완료: A={len(results_by_grade['A'])}, "
            f"B={len(results_by_grade['B'])}, C={len(results_by_grade['C'])}"
        )

        return results_by_grade

    def _classify_single_stock(
        self,
        code: str,
        name: str,
        market: str
    ) -> Optional[Dict]:
        """단일 종목 분류"""
        try:
            # 지표 계산
            indicators = self.analyzer.get_latest_indicators(code)
            if indicators is None:
                return None

            # 신호 분류
            signal = self.classifier.classify(indicators)
            if signal.grade == 'NONE':
                return None

            return {
                '종목코드': code,
                '종목명': name,
                '시장': market,
                'class': signal.grade,
                'score': signal.score,
                '현재가': int(indicators['close']),
                'today_return': round(indicators['today_return'], 2),
                '거래량': int(indicators.get('volume_today', 0)),  # 전체 이력 추적을 위해 추가
                '테마명': '',  # 급등주는 테마명 없음
                '이유': '; '.join(signal.reasons),
                'mode': 'initial'
            }

        except Exception as e:
            self.logger.debug(f"종목 분류 오류: {code} - {e}")
            return None


if __name__ == "__main__":
    from stock_analyzer.utils.data_provider import create_data_provider

    # 컴포넌트 초기화
    provider = create_data_provider('fdr', use_cache=True)
    db = DatabaseManager()
    analyzer = TechnicalAnalyzer(provider)
    classifier = SignalClassifier()

    # 스크리너 생성
    screener = StockScreener(provider, db, analyzer, classifier)

    # MA 기준 스크리닝 테스트 (작은 샘플만)
    print("MA 기준 스크리닝 테스트...")
    results = screener.screen_by_ma_threshold(
        threshold=5.0,
        market='KOSPI',
        max_workers=5
    )
    print(f"발견된 종목: {len(results)}개")

    if results:
        df = pd.DataFrame(results[:10])
        print(df[['종목명', '현재가', '상승률', '거래량비율']])
