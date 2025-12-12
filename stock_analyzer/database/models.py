"""
데이터베이스 모델

SQLAlchemy ORM을 사용한 데이터베이스 모델 정의
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class StockHistory(Base):
    """종목 이력 테이블"""

    __tablename__ = 'stock_history'

    종목코드 = Column(String(10), primary_key=True, comment='종목 코드')
    종목명 = Column(String(100), nullable=False, comment='종목명')
    테마명 = Column(String(200), default='', comment='테마명')
    최초발견일 = Column(String(10), nullable=False, comment='최초 발견일 (YYYY-MM-DD)')
    최종발견일 = Column(String(10), nullable=False, comment='최종 발견일 (YYYY-MM-DD)')
    발견횟수 = Column(Integer, default=1, comment='누적 발견 횟수')
    연속발견횟수 = Column(Integer, default=1, comment='연속 발견 횟수')
    최대상승률 = Column(Float, default=0.0, comment='최대 상승률 (%)')
    최대가격 = Column(Integer, default=0, comment='최대 가격')
    생성일시 = Column(DateTime, default=datetime.now, comment='생성 일시')
    수정일시 = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='수정 일시')

    # 관계 설정
    daily_records = relationship('DailyRecord', back_populates='stock', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<StockHistory(종목코드={self.종목코드}, 종목명={self.종목명}, 발견횟수={self.발견횟수})>"

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            '종목코드': self.종목코드,
            '종목명': self.종목명,
            '테마명': self.테마명,
            '최초발견일': self.최초발견일,
            '최종발견일': self.최종발견일,
            '발견횟수': self.발견횟수,
            '연속발견횟수': self.연속발견횟수,
            '최대상승률': self.최대상승률,
            '최대가격': self.최대가격,
            '생성일시': self.생성일시.isoformat() if self.생성일시 else None,
            '수정일시': self.수정일시.isoformat() if self.수정일시 else None,
        }


class DailyRecord(Base):
    """일별 발견 기록 테이블"""

    __tablename__ = 'daily_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    종목코드 = Column(String(10), ForeignKey('stock_history.종목코드'), nullable=False)
    종목명 = Column(String(100), nullable=False)
    테마명 = Column(String(200), default='')
    발견일 = Column(String(10), nullable=False, comment='발견일 (YYYY-MM-DD)')
    현재가 = Column(Integer, default=0)
    상승률 = Column(Float, default=0.0)
    거래량 = Column(Integer, default=0)
    기록일시 = Column(DateTime, default=datetime.now)

    # 관계 설정
    stock = relationship('StockHistory', back_populates='daily_records')

    def __repr__(self):
        return f"<DailyRecord(종목코드={self.종목코드}, 발견일={self.발견일}, 상승률={self.상승률})>"

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            '종목코드': self.종목코드,
            '종목명': self.종목명,
            '테마명': self.테마명,
            '발견일': self.발견일,
            '현재가': self.현재가,
            '상승률': self.상승률,
            '거래량': self.거래량,
            '기록일시': self.기록일시.isoformat() if self.기록일시 else None,
        }


class SurgeScreeningResult(Base):
    """급등주 스크리닝 결과 테이블"""

    __tablename__ = 'surge_screening_results'
    __table_args__ = (
        UniqueConstraint('종목코드', '스크리닝날짜', name='uix_code_date'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    종목코드 = Column(String(10), nullable=False)
    종목명 = Column(String(100), nullable=False)
    시장 = Column(String(20), comment='KOSPI/KOSDAQ/KONEX')
    grade = Column(String(1), comment='A/B/C 등급')
    score = Column(Integer, default=0, comment='평가 점수')
    현재가 = Column(Integer, default=0)
    today_return = Column(Float, default=0.0, comment='당일 수익률')
    이유 = Column(String(500), comment='선정 이유')
    mode = Column(String(20), comment='initial/monitoring')
    스크리닝날짜 = Column(String(10), nullable=False)
    스크리닝일시 = Column(String(20), nullable=False)
    생성일시 = Column(DateTime, default=datetime.now)
    status = Column(String(10), default='new', comment='new/old')

    def __repr__(self):
        return f"<SurgeScreeningResult(종목코드={self.종목코드}, grade={self.grade}, score={self.score})>"

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            '종목코드': self.종목코드,
            '종목명': self.종목명,
            '시장': self.시장,
            'grade': self.grade,
            'score': self.score,
            '현재가': self.현재가,
            'today_return': self.today_return,
            '이유': self.이유,
            'mode': self.mode,
            '스크리닝날짜': self.스크리닝날짜,
            '스크리닝일시': self.스크리닝일시,
            '생성일시': self.생성일시.isoformat() if self.생성일시 else None,
            'status': self.status,
        }
