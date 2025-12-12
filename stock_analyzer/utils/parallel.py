"""
병렬 처리 유틸리티

ThreadPoolExecutor를 래핑하여 편리한 병렬 처리 기능을 제공합니다.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, List, TypeVar, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import threading

from stock_analyzer.utils.logger import LoggerMixin

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class ProcessingError:
    """처리 오류 정보"""
    item: Any
    error_type: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessingResult:
    """처리 결과"""
    successes: List[R] = field(default_factory=list)
    errors: List[ProcessingError] = field(default_factory=list)
    total: int = 0
    completed: int = 0


class ParallelProcessor(LoggerMixin):
    """병렬 처리 유틸리티 클래스"""

    def __init__(
        self,
        max_workers: int = 20,
        timeout: int = 300,
        item_timeout: int = 30
    ):
        """
        Args:
            max_workers: 최대 워커 스레드 수
            timeout: 전체 처리 타임아웃 (초)
            item_timeout: 개별 아이템 처리 타임아웃 (초)
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self.item_timeout = item_timeout
        self._lock = threading.Lock()

    def process(
        self,
        items: List[T],
        func: Callable[[T], R],
        desc: str = "처리 중",
        progress_callback: Optional[Callable[[int, int, int], None]] = None
    ) -> ProcessingResult[R]:
        """
        아이템 리스트를 병렬로 처리합니다.

        Args:
            items: 처리할 아이템 리스트
            func: 각 아이템에 적용할 함수
            desc: 진행 상황 설명
            progress_callback: 진행 상황 콜백 함수 (completed, total, success_count)

        Returns:
            ProcessingResult 객체
        """
        result = ProcessingResult(total=len(items))
        self.logger.info(f"{desc} - 총 {len(items)}개 아이템 병렬 처리 시작 (워커: {self.max_workers}개)")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 모든 작업 제출
            futures = {executor.submit(func, item): item for item in items}

            try:
                # 완료된 작업 처리
                for future in as_completed(futures, timeout=self.timeout):
                    item = futures[future]
                    result.completed += 1

                    try:
                        # 개별 아이템 처리 결과 가져오기
                        data = future.result(timeout=self.item_timeout)
                        if data is not None:
                            with self._lock:
                                result.successes.append(data)

                    except TimeoutError:
                        error = ProcessingError(
                            item=item,
                            error_type='timeout',
                            message=f'{self.item_timeout}초 타임아웃'
                        )
                        with self._lock:
                            result.errors.append(error)
                        self.logger.warning(f"타임아웃: {item}")

                    except Exception as e:
                        error = ProcessingError(
                            item=item,
                            error_type=type(e).__name__,
                            message=str(e)
                        )
                        with self._lock:
                            result.errors.append(error)
                        self.logger.error(f"처리 오류: {item} - {e}")

                    # 진행 상황 콜백 호출
                    if progress_callback and result.completed % 50 == 0:
                        progress_callback(result.completed, result.total, len(result.successes))

            except TimeoutError:
                self.logger.error(f"전체 타임아웃 발생: {result.completed}/{result.total} 완료")
                executor.shutdown(wait=False, cancel_futures=True)

            except KeyboardInterrupt:
                self.logger.warning("사용자 중단")
                executor.shutdown(wait=False, cancel_futures=True)
                raise

        self.logger.info(
            f"{desc} 완료 - 성공: {len(result.successes)}, "
            f"실패: {len(result.errors)}, "
            f"처리율: {result.completed}/{result.total}"
        )

        return result

    def process_batches(
        self,
        items: List[T],
        func: Callable[[T], R],
        batch_size: int = 500,
        desc: str = "배치 처리 중"
    ) -> ProcessingResult[R]:
        """
        아이템을 배치로 나누어 처리합니다.

        Args:
            items: 처리할 아이템 리스트
            func: 각 아이템에 적용할 함수
            batch_size: 배치 크기
            desc: 진행 상황 설명

        Returns:
            ProcessingResult 객체
        """
        total_result = ProcessingResult(total=len(items))
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

        self.logger.info(f"{desc} - {len(batches)}개 배치로 분할 (배치 크기: {batch_size})")

        for batch_num, batch in enumerate(batches, 1):
            self.logger.info(f"배치 {batch_num}/{len(batches)} 처리 중...")

            batch_result = self.process(
                batch,
                func,
                desc=f"배치 {batch_num}/{len(batches)}"
            )

            # 결과 통합
            total_result.successes.extend(batch_result.successes)
            total_result.errors.extend(batch_result.errors)
            total_result.completed += batch_result.completed

        return total_result


def progress_printer(completed: int, total: int, success_count: int):
    """기본 진행 상황 출력 함수"""
    percentage = (completed / total * 100) if total > 0 else 0
    print(f"[진행] {completed}/{total} 완료 ({percentage:.1f}%) - 발견: {success_count}개")


if __name__ == "__main__":
    import time

    # 테스트 함수
    def test_func(x):
        time.sleep(0.1)
        if x % 10 == 0:
            raise ValueError(f"{x}는 처리할 수 없습니다")
        return x * 2

    # 병렬 처리 테스트
    processor = ParallelProcessor(max_workers=5, item_timeout=1)
    items = list(range(100))

    result = processor.process(
        items,
        test_func,
        desc="테스트 처리",
        progress_callback=progress_printer
    )

    print(f"\n총 처리: {result.completed}/{result.total}")
    print(f"성공: {len(result.successes)}")
    print(f"실패: {len(result.errors)}")
    print(f"오류 유형별 통계:")
    error_types = {}
    for error in result.errors:
        error_types[error.error_type] = error_types.get(error.error_type, 0) + 1
    for error_type, count in error_types.items():
        print(f"  {error_type}: {count}개")
