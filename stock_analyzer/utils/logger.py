"""
로깅 유틸리티

애플리케이션 전체에서 사용할 로거를 설정하고 관리합니다.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from stock_analyzer.config import get_settings


def setup_logger(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    로거를 설정하고 반환합니다.

    Args:
        name: 로거 이름 (일반적으로 __name__)
        level: 로그 레벨 (None이면 설정 파일에서 가져옴)
        log_file: 로그 파일 경로 (None이면 설정 파일에서 가져옴)

    Returns:
        설정된 로거 인스턴스
    """
    settings = get_settings()
    log_config = settings.logging

    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(level or log_config.level)

    # 기존 핸들러 제거 (중복 방지)
    logger.handlers.clear()

    # 포맷터 생성
    formatter = logging.Formatter(log_config.format)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (설정된 경우)
    if log_file or log_config.file_path:
        file_path = log_file or log_config.file_path
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=log_config.max_bytes,
            backupCount=log_config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    로거를 가져옵니다. 없으면 새로 생성합니다.

    Args:
        name: 로거 이름

    Returns:
        로거 인스턴스
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


class LoggerMixin:
    """로거를 자동으로 추가하는 믹스인 클래스"""

    @property
    def logger(self) -> logging.Logger:
        """클래스별 로거를 반환합니다"""
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return get_logger(name)


if __name__ == "__main__":
    # 로거 테스트
    logger = setup_logger(__name__)
    logger.debug("디버그 메시지")
    logger.info("정보 메시지")
    logger.warning("경고 메시지")
    logger.error("오류 메시지")
    logger.critical("심각한 오류 메시지")
