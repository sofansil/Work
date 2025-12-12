"""
신호 분류기

주식의 급등 신호를 A/B/C 등급으로 분류합니다.
"""

from typing import Dict, Tuple, List
from dataclasses import dataclass

from stock_analyzer.config import get_settings
from stock_analyzer.utils.logger import LoggerMixin


@dataclass
class SignalGrade:
    """신호 등급"""
    grade: str  # A/B/C/NONE
    score: int
    reasons: List[str]


class SignalClassifier(LoggerMixin):
    """급등 신호 분류기"""

    def __init__(self):
        """설정을 로드합니다"""
        self.criteria = get_settings().classification

    def classify(self, indicators: Dict) -> SignalGrade:
        """
        지표를 기반으로 신호를 분류합니다.

        Args:
            indicators: 기술적 지표 딕셔너리

        Returns:
            SignalGrade 객체
        """
        score = self._compute_score(indicators)

        # 등급 결정
        if score >= self.criteria.a_score_threshold:
            grade = 'A'
        elif score >= self.criteria.b_score_threshold:
            grade = 'B'
        elif score >= self.criteria.c_score_threshold:
            grade = 'C'
        else:
            grade = 'NONE'

        # 이유 생성
        reasons = self._summarize_reasons(indicators, grade)

        return SignalGrade(grade=grade, score=score, reasons=reasons)

    def is_a_signal(self, ind: Dict) -> bool:
        """A급 신호 여부"""
        cond_volume_explosion = (
            ind["volume_today"] >= ind["volume_prev"] * self.criteria.a_volume_multiplier_prev
        ) or (
            ind["volume_today"] >= ind["vol_avg5"] * self.criteria.a_volume_multiplier_avg5
        )

        cond_breakout = (
            ind["close"] >= ind["high20"]
        ) or (
            ind["close"] >= ind["high20"] * self.criteria.a_high20_proximity
        )

        cond_big_candle = (
            ind["close"] >= ind["open"] * self.criteria.a_price_breakout_ratio
        ) and (
            ind["body"] >= ind["candle_range"] * self.criteria.a_candle_body_ratio
        )

        cond_vcp = (
            ind["volatility5"] < ind["volatility20"]
        ) and (
            ind["volume_prev"] < ind["vol_avg5"]
        )

        return cond_volume_explosion and cond_breakout and cond_big_candle and cond_vcp

    def is_b_signal(self, ind: Dict) -> bool:
        """B급 신호 여부"""
        if not self.is_c_signal(ind):
            return False

        cond_near_high = ind["close"] >= ind["high20"] * self.criteria.b_high20_proximity

        cond_volume = (
            ind["volume_today"] >= ind["volume_prev"] * self.criteria.b_volume_multiplier
        ) or (
            ind["volume_today"] >= ind["vol_avg5"] * self.criteria.b_volume_multiplier
        )

        cond_higher_low = ind["min_low5"] > ind["min_low_prev5"]

        return cond_near_high and cond_volume and cond_higher_low

    def is_c_signal(self, ind: Dict) -> bool:
        """C급 신호 여부"""
        cond_trend = ind["close"] >= ind["MA20"]

        cond_price = ind["today_return"] >= self.criteria.c_return_threshold

        cond_volume = (
            ind["volume_today"] >= ind["volume_prev"] * 1.2
        ) or (
            ind["volume_today"] >= ind["vol_avg5"] * 1.5
        )

        return cond_trend and cond_price and cond_volume

    def _compute_score(self, ind: Dict) -> int:
        """종합 점수를 계산합니다"""
        score = 0

        # 가격 조건
        if ind["close"] >= ind["MA20"]:
            score += 1
        if ind["today_return"] >= 2:
            score += 1
        if ind["close"] >= ind["high20"] * 0.95:
            score += 1
        if ind["close"] >= ind["high20"]:
            score += 2

        # 거래량 조건
        if ind["volume_today"] >= ind["volume_prev"] * 1.5:
            score += 1
        if ind["volume_today"] >= ind["volume_prev"] * 3:
            score += 2
        if ind["volume_today"] >= ind["vol_avg5"] * 2:
            score += 1
        if ind["volume_today"] >= ind["vol_avg5"] * 5:
            score += 2

        # 추세/캔들 조건
        if ind["min_low5"] > ind["min_low_prev5"]:
            score += 1
        if ind["close"] > ind["open"]:
            score += 1
        if ind["body"] >= ind["candle_range"] * 0.7:
            score += 2

        return score

    def _summarize_reasons(self, ind: Dict, grade: str) -> List[str]:
        """등급별 이유를 요약합니다"""
        reasons = []

        if grade == 'A':
            if ind["volume_today"] >= ind["volume_prev"] * self.criteria.a_volume_multiplier_prev:
                reasons.append(f"거래량 전일 {self.criteria.a_volume_multiplier_prev}배↑")
            elif ind["volume_today"] >= ind["vol_avg5"] * self.criteria.a_volume_multiplier_avg5:
                reasons.append(f"거래량 5일평균 {self.criteria.a_volume_multiplier_avg5}배↑")

            if ind["close"] >= ind["high20"]:
                reasons.append("20일 고점 돌파")
            elif ind["close"] >= ind["high20"] * self.criteria.a_high20_proximity:
                reasons.append("20일 고점 근접")

            if (ind["close"] >= ind["open"] * self.criteria.a_price_breakout_ratio) and \
               (ind["body"] >= ind["candle_range"] * self.criteria.a_candle_body_ratio):
                reasons.append(f"장대양봉(몸통 {self.criteria.a_candle_body_ratio*100:.0f}%+)")

            if (ind["volatility5"] < ind["volatility20"]) and \
               (ind["volume_prev"] < ind["vol_avg5"]):
                reasons.append("VCP(변동성 축소 후 거래량 회복)")

        elif grade == 'B':
            if ind["close"] >= ind["high20"] * self.criteria.b_high20_proximity:
                reasons.append(f"20일 고점 {self.criteria.b_high20_proximity*100:.0f}% 근접")

            if (ind["volume_today"] >= ind["volume_prev"] * self.criteria.b_volume_multiplier) or \
               (ind["volume_today"] >= ind["vol_avg5"] * self.criteria.b_volume_multiplier):
                reasons.append(f"거래량 {self.criteria.b_volume_multiplier}배↑")

            if ind["min_low5"] > ind["min_low_prev5"]:
                reasons.append("저점 상승 추세")

            if ind["today_return"] >= self.criteria.c_return_threshold:
                reasons.append(f"당일 +{self.criteria.c_return_threshold}% 이상")

        elif grade == 'C':
            if ind["close"] >= ind["MA20"]:
                reasons.append("20일선 위")

            if ind["today_return"] >= self.criteria.c_return_threshold:
                reasons.append(f"당일 +{self.criteria.c_return_threshold}% 이상")

            if (ind["volume_today"] >= ind["volume_prev"] * 1.2) or \
               (ind["volume_today"] >= ind["vol_avg5"] * 1.5):
                reasons.append("거래량 증가")

        if not reasons:
            reasons.append("다중 조건 충족")

        return reasons


if __name__ == "__main__":
    # 테스트
    classifier = SignalClassifier()

    # 테스트 지표 (A급 예상)
    test_indicators_a = {
        'close': 10000,
        'open': 9500,
        'high': 10100,
        'low': 9400,
        'volume_today': 5000000,
        'volume_prev': 1000000,
        'MA5': 9800,
        'MA20': 9500,
        'vol_avg5': 1000000,
        'vol_avg20': 900000,
        'high20': 9900,
        'low20': 8500,
        'min_low5': 9300,
        'min_low_prev5': 9100,
        'volatility5': 200,
        'volatility20': 300,
        'today_return': 5.26,
        'body': 500,
        'candle_range': 700,
    }

    result_a = classifier.classify(test_indicators_a)
    print(f"등급: {result_a.grade}, 점수: {result_a.score}")
    print(f"이유: {', '.join(result_a.reasons)}")

    # 테스트 지표 (C급 예상)
    test_indicators_c = {
        'close': 10000,
        'open': 9800,
        'high': 10050,
        'low': 9750,
        'volume_today': 1200000,
        'volume_prev': 1000000,
        'MA5': 9900,
        'MA20': 9800,
        'vol_avg5': 1000000,
        'vol_avg20': 900000,
        'high20': 10500,
        'low20': 9000,
        'min_low5': 9700,
        'min_low_prev5': 9650,
        'volatility5': 250,
        'volatility20': 300,
        'today_return': 2.04,
        'body': 200,
        'candle_range': 300,
    }

    result_c = classifier.classify(test_indicators_c)
    print(f"\n등급: {result_c.grade}, 점수: {result_c.score}")
    print(f"이유: {', '.join(result_c.reasons)}")
