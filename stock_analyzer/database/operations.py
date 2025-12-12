"""
데이터베이스 작업

데이터베이스 CRUD 작업을 처리하는 클래스
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from stock_analyzer.database.models import Base, StockHistory, DailyRecord, SurgeScreeningResult
from stock_analyzer.config import get_settings
from stock_analyzer.utils.logger import LoggerMixin


class DatabaseManager(LoggerMixin):
    """데이터베이스 관리 클래스"""

    def __init__(self, db_url: Optional[str] = None):
        """
        Args:
            db_url: 데이터베이스 URL (None이면 설정에서 가져옴)
        """
        settings = get_settings()
        self.db_url = db_url or settings.database.url

        # 엔진 생성
        self.engine = create_engine(
            self.db_url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow
        )

        # 세션 팩토리 생성
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        # 테이블 생성
        self.create_tables()
        self.logger.info(f"데이터베이스 초기화 완료: {self.db_url}")

    def create_tables(self):
        """모든 테이블을 생성합니다"""
        Base.metadata.create_all(bind=self.engine)
        self.logger.info("테이블 생성 완료")

    def drop_tables(self):
        """모든 테이블을 삭제합니다 (주의!)"""
        Base.metadata.drop_all(bind=self.engine)
        self.logger.warning("모든 테이블 삭제됨")

    @contextmanager
    def session_scope(self):
        """세션 컨텍스트 매니저"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"데이터베이스 오류: {e}")
            raise
        finally:
            session.close()

    # ==================== StockHistory 작업 ====================

    def update_stock_history(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        종목 이력을 업데이트합니다.

        Args:
            stock_data: 종목 정보 딕셔너리

        Returns:
            업데이트된 이력 정보 (최초발견일, 발견횟수, 연속발견횟수, 신규여부)
        """
        code = stock_data['종목코드']
        today = datetime.now().strftime('%Y-%m-%d')
        is_new = False
        consecutive_count = 1
        total_count = 1
        first_found = today

        with self.session_scope() as session:
            # 기존 데이터 조회
            stock = session.query(StockHistory).filter_by(종목코드=code).first()

            if stock:
                # 기존 종목 업데이트
                total_count = stock.발견횟수 + 1
                first_found = stock.최초발견일

                # 연속 발견 체크
                last_date = datetime.strptime(stock.최종발견일, '%Y-%m-%d')
                today_date = datetime.strptime(today, '%Y-%m-%d')
                days_diff = (today_date - last_date).days

                if days_diff == 0:
                    # 같은 날 재발견
                    consecutive_count = stock.연속발견횟수
                elif days_diff == 1:
                    # 하루 연속 발견
                    consecutive_count = stock.연속발견횟수 + 1
                else:
                    # 며칠 만에 재발견
                    consecutive_count = 1

                # 최대값 업데이트
                stock.종목명 = stock_data['종목명']
                stock.테마명 = stock_data.get('테마명', '')
                stock.최종발견일 = today
                stock.발견횟수 = total_count
                stock.연속발견횟수 = consecutive_count
                stock.최대상승률 = max(stock.최대상승률, stock_data.get('상승률', 0))
                stock.최대가격 = max(stock.최대가격, stock_data.get('현재가', 0))
                stock.수정일시 = datetime.now()

            else:
                # 신규 종목 등록
                is_new = True
                stock = StockHistory(
                    종목코드=code,
                    종목명=stock_data['종목명'],
                    테마명=stock_data.get('테마명', ''),
                    최초발견일=today,
                    최종발견일=today,
                    발견횟수=1,
                    연속발견횟수=1,
                    최대상승률=stock_data.get('상승률', 0),
                    최대가격=stock_data.get('현재가', 0),
                    생성일시=datetime.now(),
                    수정일시=datetime.now()
                )
                session.add(stock)

            # 일별 기록 추가
            daily_record = DailyRecord(
                종목코드=code,
                종목명=stock_data['종목명'],
                테마명=stock_data.get('테마명', ''),
                발견일=today,
                현재가=stock_data.get('현재가', 0),
                상승률=stock_data.get('상승률', 0),
                거래량=stock_data.get('거래량', 0),
                기록일시=datetime.now()
            )
            session.add(daily_record)

        return {
            '신규여부': is_new,
            '최초발견일': first_found,
            '발견횟수': total_count,
            '연속발견횟수': consecutive_count
        }

    def get_stock_history(self, code: str) -> Optional[Dict[str, Any]]:
        """종목 이력을 조회합니다"""
        with self.session_scope() as session:
            stock = session.query(StockHistory).filter_by(종목코드=code).first()
            return stock.to_dict() if stock else None

    def get_all_stock_histories(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """모든 종목 이력을 조회합니다"""
        with self.session_scope() as session:
            query = session.query(StockHistory).order_by(StockHistory.발견횟수.desc())
            if limit:
                query = query.limit(limit)
            return [stock.to_dict() for stock in query.all()]

    # ==================== DailyRecord 작업 ====================

    def get_daily_records(
        self,
        code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """일별 기록을 조회합니다"""
        with self.session_scope() as session:
            query = session.query(DailyRecord)

            if code:
                query = query.filter(DailyRecord.종목코드 == code)
            if start_date:
                query = query.filter(DailyRecord.발견일 >= start_date)
            if end_date:
                query = query.filter(DailyRecord.발견일 <= end_date)

            query = query.order_by(DailyRecord.발견일.desc())
            return [record.to_dict() for record in query.all()]

    # ==================== SurgeScreeningResult 작업 ====================

    def save_surge_results(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        급등주 스크리닝 결과를 저장합니다.

        Returns:
            저장 통계 (success_count, new_count, update_count)
        """
        if not results:
            return {'success_count': 0, 'new_count': 0, 'update_count': 0}

        screening_date = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now()

        success_count = 0
        new_count = 0
        update_count = 0

        with self.session_scope() as session:
            for r in results:
                try:
                    # 기존 데이터 확인
                    existing = session.query(SurgeScreeningResult).filter_by(
                        종목코드=r.get('종목코드', ''),
                        스크리닝날짜=screening_date
                    ).first()

                    if existing:
                        # 업데이트
                        existing.종목명 = r.get('종목명', '')
                        existing.시장 = r.get('시장', '')
                        existing.grade = r.get('class', '')
                        existing.score = r.get('score', 0)
                        existing.현재가 = r.get('현재가', 0)
                        existing.today_return = r.get('today_return', 0.0)
                        existing.이유 = r.get('이유', '')
                        existing.mode = r.get('mode', '')
                        existing.스크리닝일시 = now.strftime('%Y-%m-%d %H:%M:%S')
                        existing.status = 'old'
                        update_count += 1
                    else:
                        # 신규 생성
                        new_result = SurgeScreeningResult(
                            종목코드=r.get('종목코드', ''),
                            종목명=r.get('종목명', ''),
                            시장=r.get('시장', ''),
                            grade=r.get('class', ''),
                            score=r.get('score', 0),
                            현재가=r.get('현재가', 0),
                            today_return=r.get('today_return', 0.0),
                            이유=r.get('이유', ''),
                            mode=r.get('mode', ''),
                            스크리닝날짜=screening_date,
                            스크리닝일시=now.strftime('%Y-%m-%d %H:%M:%S'),
                            생성일시=now,
                            status='new'
                        )
                        session.add(new_result)
                        new_count += 1

                    success_count += 1

                except IntegrityError as e:
                    self.logger.warning(f"중복 데이터: {r.get('종목코드', '')} - {e}")
                    session.rollback()
                except Exception as e:
                    self.logger.error(f"저장 오류: {r.get('종목코드', '')} - {e}")
                    session.rollback()

        self.logger.info(
            f"급등주 결과 저장 완료: 총 {success_count}개 "
            f"(신규: {new_count}, 업데이트: {update_count})"
        )

        return {
            'success_count': success_count,
            'new_count': new_count,
            'update_count': update_count
        }

    def get_surge_results(
        self,
        date: Optional[str] = None,
        grade: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """급등주 스크리닝 결과를 조회합니다"""
        with self.session_scope() as session:
            query = session.query(SurgeScreeningResult)

            if date:
                query = query.filter(SurgeScreeningResult.스크리닝날짜 == date)
            if grade:
                query = query.filter(SurgeScreeningResult.grade == grade)

            query = query.order_by(SurgeScreeningResult.score.desc())
            return [result.to_dict() for result in query.all()]

    # ==================== 통계 ====================

    def get_statistics(self) -> Dict[str, int]:
        """통계 정보를 조회합니다"""
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        with self.session_scope() as session:
            # 오늘 발견된 종목 수
            today_count = session.query(func.count(StockHistory.종목코드)).filter(
                StockHistory.최종발견일 == today
            ).scalar()

            # 이번주 신규 발견 종목 수
            new_this_week = session.query(func.count(StockHistory.종목코드)).filter(
                StockHistory.최초발견일 >= week_ago
            ).scalar()

            # 5회 이상 연속 발견 종목 수
            hot_stocks = session.query(func.count(StockHistory.종목코드)).filter(
                StockHistory.연속발견횟수 >= 5
            ).scalar()

            # 전체 종목 수
            total_stocks = session.query(func.count(StockHistory.종목코드)).scalar()

        return {
            '오늘발견': today_count or 0,
            '이번주신규': new_this_week or 0,
            '연속5회이상': hot_stocks or 0,
            '전체종목수': total_stocks or 0
        }


if __name__ == "__main__":
    # 데이터베이스 테스트
    db = DatabaseManager()

    # 테스트 데이터
    test_stock = {
        '종목코드': '005930',
        '종목명': '삼성전자',
        '테마명': '반도체',
        '현재가': 70000,
        '상승률': 5.5,
        '거래량': 10000000
    }

    # 업데이트 테스트
    history = db.update_stock_history(test_stock)
    print(f"업데이트 결과: {history}")

    # 조회 테스트
    stock_info = db.get_stock_history('005930')
    print(f"종목 정보: {stock_info}")

    # 통계 테스트
    stats = db.get_statistics()
    print(f"통계: {stats}")
