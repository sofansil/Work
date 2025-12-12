"""
메인 애플리케이션

주식 분석 시스템의 진입점입니다.
"""

import sys
import asyncio
from datetime import datetime
import pandas as pd

from stock_analyzer.config import get_settings
from stock_analyzer.database.operations import DatabaseManager
from stock_analyzer.utils.data_provider import create_data_provider
from stock_analyzer.analyzers.technical import TechnicalAnalyzer
from stock_analyzer.analyzers.classifier import SignalClassifier
from stock_analyzer.screeners.surge_screener import StockScreener
from stock_analyzer.notifiers.telegram import TelegramNotifier
from stock_analyzer.utils.logger import setup_logger


class StockAnalyzerApp:
    """주식 분석 애플리케이션"""

    def __init__(self):
        """컴포넌트 초기화"""
        self.logger = setup_logger(__name__)
        self.settings = get_settings()

        # 컴포넌트 생성
        self.data_provider = create_data_provider('fdr', use_cache=True)
        self.db = DatabaseManager()
        self.analyzer = TechnicalAnalyzer(self.data_provider)
        self.classifier = SignalClassifier()
        self.screener = StockScreener(
            self.data_provider,
            self.db,
            self.analyzer,
            self.classifier
        )
        self.notifier = TelegramNotifier()

        self.logger.info("애플리케이션 초기화 완료")

    def show_menu(self):
        """메뉴 표시"""
        print("\n" + "="*60)
        print("[시스템] 주식 분석 및 텔레그램 알림")
        print("="*60)
        print("1. 급등주 스크리닝 (20일 이평선 기준)")
        print("2. 급등주 초기 포착 (A/B/C 등급 분류)")
        print("3. 통계 조회")
        print("4. 캐시 초기화")
        print("0. 종료")
        print("="*60 + "\n")

    def handle_ma_screening(self):
        """MA 기준 스크리닝 처리"""
        print("\n[실행] 급등주 스크리닝을 시작합니다...\n")

        # 사용자 입력
        threshold_input = input("[입력] 상승률 기준 (기본값: 5.0%): ").strip() or "5.0"
        try:
            threshold = float(threshold_input)
        except ValueError:
            print("[오류] 잘못된 입력입니다. 기본값 5.0%를 사용합니다.")
            threshold = 5.0

        volume_input = input("[입력] 거래량 필터 % (기본값: 100, 없음): ").strip() or "100"
        try:
            volume_multiplier = float(volume_input) / 100.0
        except ValueError:
            print("[오류] 잘못된 입력입니다. 기본값 100%를 사용합니다.")
            volume_multiplier = 1.0

        workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 20): ").strip() or "20"
        try:
            max_workers = int(workers_input)
        except ValueError:
            print("[오류] 잘못된 입력입니다. 기본값 20을 사용합니다.")
            max_workers = 20

        print(f"\n[설정] 상승률 기준: {threshold}%")
        print(f"[설정] 거래량 필터: {volume_multiplier}배")
        print(f"[설정] 병렬 처리: {max_workers}개\n")

        # 스크리닝 실행
        results = self.screener.screen_by_ma_threshold(
            threshold=threshold,
            volume_multiplier=volume_multiplier,
            max_workers=max_workers
        )

        if not results:
            print("\n[결과] 조건을 만족하는 종목이 없습니다.")
            return

        # 결과 표시
        df = pd.DataFrame(results)
        print("\n" + "="*70)
        print(f"[발견] 총 {len(results)}개 종목")
        print("="*70)
        print(df[['종목명', '종목코드', '현재가', '상승률', '거래량비율']].head(20).to_string(index=False))

        # 텔레그램 전송
        send_choice = input("\n텔레그램으로 전송하시겠습니까? (y/n): ").strip().lower()
        if send_choice == 'y':
            message = self.notifier.format_screening_results(results, threshold)
            success = self.notifier.send_message_sync(message)
            print(f"[텔레그램] {'전송 완료' if success else '전송 실패'}")

        # CSV 저장
        save_choice = input("CSV 파일로 저장하시겠습니까? (y/n): ").strip().lower()
        if save_choice == 'y':
            filename = f"screening_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"[저장] {filename}")

    def handle_surge_detection(self):
        """급등주 초기 포착 처리"""
        print("\n[실행] 급등주 초기 포착 (A/B/C 등급 분류)을 시작합니다...\n")

        workers_input = input("[입력] 병렬 처리 스레드 수 (기본값: 10): ").strip() or "10"
        try:
            max_workers = int(workers_input)
        except ValueError:
            print("[오류] 잘못된 입력입니다. 기본값 10을 사용합니다.")
            max_workers = 10

        print(f"\n[설정] 병렬 처리: {max_workers}개\n")

        # 스크리닝 실행
        results_by_grade = self.screener.screen_surge_stocks(max_workers=max_workers)

        results_a = results_by_grade['A']
        results_b = results_by_grade['B']
        results_c = results_by_grade['C']

        # 결과 표시
        print("\n" + "="*70)
        print(f"[결과] A급: {len(results_a)}, B급: {len(results_b)}, C급: {len(results_c)}")
        print("="*70)

        if results_a:
            print("\n[🔥 A급 급등 초기]")
            df_a = pd.DataFrame(results_a)
            print(df_a[['종목명', '종목코드', '현재가', 'score', '이유']].head(10).to_string(index=False))

        if results_b:
            print("\n[⚡ B급 강세]")
            df_b = pd.DataFrame(results_b)
            print(df_b[['종목명', '종목코드', '현재가', 'score']].head(10).to_string(index=False))

        # 텔레그램 전송
        send_choice = input("\n텔레그램으로 전송하시겠습니까? (y/n): ").strip().lower()
        if send_choice == 'y':
            messages = self.notifier.format_surge_results(results_by_grade)
            asyncio.run(self._send_multiple_messages(messages))

        # CSV 저장
        if results_a or results_b or results_c:
            all_results = results_a + results_b + results_c
            df = pd.DataFrame(all_results)
            filename = f"surge_A{len(results_a)}_B{len(results_b)}_C{len(results_c)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"[저장] {filename}")

    async def _send_multiple_messages(self, messages):
        """여러 메시지를 순차적으로 전송"""
        stats = await self.notifier.send_long_message('\n\n'.join(messages))
        print(f"[텔레그램] {stats['success']}/{stats['total']} 메시지 전송 완료")

    def handle_statistics(self):
        """통계 조회"""
        print("\n[통계 조회]")
        print("="*60)

        stats = self.db.get_statistics()
        print(f"오늘 발견: {stats['오늘발견']}개")
        print(f"이번주 신규: {stats['이번주신규']}개")
        print(f"연속 5회 이상: {stats['연속5회이상']}개")
        print(f"전체 종목 수: {stats['전체종목수']}개")
        print("="*60)

        # 캐시 통계
        from stock_analyzer.utils.data_provider import CachedDataProvider
        if isinstance(self.data_provider, CachedDataProvider):
            cache_stats = self.data_provider.get_cache_stats()
            print(f"\n[캐시] {cache_stats['size']}/{cache_stats['maxsize']} (TTL: {cache_stats['ttl']}초)")

    def handle_cache_clear(self):
        """캐시 초기화"""
        from stock_analyzer.utils.data_provider import CachedDataProvider
        if isinstance(self.data_provider, CachedDataProvider):
            self.data_provider.clear_cache()
            print("[캐시] 초기화 완료")
        else:
            print("[캐시] 캐시가 활성화되어 있지 않습니다")

    def run(self):
        """메인 루프"""
        print("\n[시작] 주식 분석 프로그램을 시작합니다.")

        while True:
            try:
                self.show_menu()
                choice = input("선택: ").strip()

                if choice == "1":
                    self.handle_ma_screening()
                elif choice == "2":
                    self.handle_surge_detection()
                elif choice == "3":
                    self.handle_statistics()
                elif choice == "4":
                    self.handle_cache_clear()
                elif choice == "0":
                    print("\n[종료] 프로그램을 종료합니다.\n")
                    break
                else:
                    print("[오류] 잘못된 선택입니다.")

            except KeyboardInterrupt:
                print("\n\n[중단] 사용자에 의해 중단되었습니다.")
                break
            except Exception as e:
                self.logger.exception(f"오류 발생: {e}")
                print(f"[오류] {e}")


def main():
    """프로그램 진입점"""
    try:
        app = StockAnalyzerApp()
        app.run()
    except Exception as e:
        print(f"[치명적 오류] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
