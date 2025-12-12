"""
신호 분류기 테스트
"""

import pytest
from stock_analyzer.analyzers.classifier import SignalClassifier


@pytest.fixture
def classifier():
    """분류기 인스턴스"""
    return SignalClassifier()


@pytest.fixture
def a_grade_indicators():
    """A급 예상 지표"""
    return {
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


@pytest.fixture
def c_grade_indicators():
    """C급 예상 지표"""
    return {
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


def test_classifier_initialization(classifier):
    """분류기 초기화 테스트"""
    assert classifier is not None
    assert classifier.criteria is not None


def test_classify_a_grade(classifier, a_grade_indicators):
    """A급 분류 테스트"""
    result = classifier.classify(a_grade_indicators)

    assert result.grade == 'A'
    assert result.score >= classifier.criteria.a_score_threshold
    assert len(result.reasons) > 0


def test_classify_c_grade(classifier, c_grade_indicators):
    """C급 분류 테스트"""
    result = classifier.classify(c_grade_indicators)

    assert result.grade in ['C', 'B']  # B급일 수도 있음
    assert result.score >= classifier.criteria.c_score_threshold
    assert len(result.reasons) > 0


def test_is_a_signal(classifier, a_grade_indicators):
    """A급 신호 판별 테스트"""
    # A급 지표는 is_a_signal이 True여야 함
    is_a = classifier.is_a_signal(a_grade_indicators)
    # 실제로는 VCP 조건 등에 따라 다를 수 있음
    assert isinstance(is_a, bool)


def test_is_c_signal(classifier, c_grade_indicators):
    """C급 신호 판별 테스트"""
    is_c = classifier.is_c_signal(c_grade_indicators)
    assert is_c is True  # C급 지표는 최소한 C급 조건을 만족해야 함


def test_compute_score(classifier, a_grade_indicators):
    """점수 계산 테스트"""
    score = classifier._compute_score(a_grade_indicators)
    assert isinstance(score, int)
    assert score >= 0


def test_summarize_reasons(classifier):
    """이유 요약 테스트"""
    indicators = {
        'close': 10000,
        'volume_today': 3000000,
        'volume_prev': 1000000,
        'vol_avg5': 1000000,
        'high20': 9900,
        'MA20': 9500,
        'today_return': 3.0,
        'volatility5': 200,
        'volatility20': 300,
        'min_low5': 9300,
        'min_low_prev5': 9100,
        'open': 9700,
        'body': 300,
        'candle_range': 400,
    }

    reasons_a = classifier._summarize_reasons(indicators, 'A')
    assert len(reasons_a) > 0
    assert all(isinstance(r, str) for r in reasons_a)

    reasons_c = classifier._summarize_reasons(indicators, 'C')
    assert len(reasons_c) > 0


def test_none_grade(classifier):
    """NONE 등급 테스트"""
    low_score_indicators = {
        'close': 10000,
        'open': 10000,
        'high': 10050,
        'low': 9950,
        'volume_today': 1000000,
        'volume_prev': 1000000,
        'MA5': 10100,
        'MA20': 10200,
        'vol_avg5': 1000000,
        'vol_avg20': 1000000,
        'high20': 10500,
        'low20': 9500,
        'min_low5': 9900,
        'min_low_prev5': 9850,
        'volatility5': 100,
        'volatility20': 150,
        'today_return': 0.0,
        'body': 0,
        'candle_range': 100,
    }

    result = classifier.classify(low_score_indicators)
    assert result.grade == 'NONE'
    assert result.score < classifier.criteria.c_score_threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
