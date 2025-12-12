"""
텔레그램 알림

분석 결과를 텔레그램으로 전송합니다.
"""

import asyncio
from typing import List, Dict
from telegram import Bot

from stock_analyzer.config import get_settings
from stock_analyzer.utils.logger import LoggerMixin


class TelegramNotifier(LoggerMixin):
    """텔레그램 알림 클래스"""

    def __init__(self):
        """설정을 로드합니다"""
        telegram_config = get_settings().telegram
        self.token = telegram_config.token
        self.chat_id = telegram_config.chat_id
        self.max_length = telegram_config.max_message_length

    async def send_message(self, message: str) -> bool:
        """
        메시지를 전송합니다.

        Args:
            message: 전송할 메시지

        Returns:
            성공 여부
        """
        try:
            bot = Bot(token=self.token)
            async with bot:
                await bot.send_message(chat_id=self.chat_id, text=message)
            self.logger.info(f"텔레그램 메시지 전송 성공 ({len(message)}자)")
            return True
        except Exception as e:
            self.logger.error(f"텔레그램 전송 오류: {e}")
            return False

    def send_message_sync(self, message: str) -> bool:
        """동기 방식으로 메시지를 전송합니다"""
        return asyncio.run(self.send_message(message))

    async def send_long_message(self, message: str, delay: float = 1.0) -> Dict[str, int]:
        """
        긴 메시지를 여러 개로 나누어 전송합니다.

        Args:
            message: 전송할 메시지
            delay: 메시지 간 대기 시간 (초)

        Returns:
            전송 통계 (total, success, failed)
        """
        chunks = self._split_message(message)
        self.logger.info(f"메시지 분할: {len(chunks)}개")

        success_count = 0
        for i, chunk in enumerate(chunks, 1):
            self.logger.info(f"메시지 {i}/{len(chunks)} 전송 중... ({len(chunk)}자)")
            if await self.send_message(chunk):
                success_count += 1
                if i < len(chunks):
                    await asyncio.sleep(delay)
            else:
                self.logger.error(f"메시지 {i}/{len(chunks)} 전송 실패")

        return {
            'total': len(chunks),
            'success': success_count,
            'failed': len(chunks) - success_count
        }

    def _split_message(self, message: str) -> List[str]:
        """메시지를 최대 길이로 분할합니다"""
        if len(message) <= self.max_length:
            return [message]

        chunks = []
        lines = message.split('\n')
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline

            if current_length + line_length > self.max_length:
                # 현재 청크 저장
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        # 마지막 청크 저장
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def format_screening_results(
        self,
        results: List[Dict],
        threshold: float,
        top_n: int = 20
    ) -> str:
        """스크리닝 결과를 포맷팅합니다"""
        from datetime import datetime

        if not results:
            return f"20일 이동평균 대비 {threshold}% 이상 상승한 종목이 없습니다."

        # 상승률 순 정렬
        results_sorted = sorted(results, key=lambda x: x.get('상승률', 0), reverse=True)
        top_results = results_sorted[:top_n]

        # 신규/연속 종목 통계
        new_stocks = [s for s in results if s.get('신규여부', False)]
        hot_stocks = [s for s in results if s.get('연속발견횟수', 0) >= 5]

        message = f"""
📈 주식 스크리닝 결과
조건: 20일 이동평균 대비 {threshold}% 이상 상승
날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📊 통계
• 총 발견: {len(results)}개 종목
• 🆕 신규: {len(new_stocks)}개
• 🔥 연속5회 이상: {len(hot_stocks)}개

[상위 {len(top_results)}개 종목]
"""

        for i, stock in enumerate(top_results, 1):
            status = ""
            if stock.get('신규여부'):
                status = " 🆕신규"
            elif stock.get('연속발견횟수', 0) >= 5:
                status = f" 🔥{stock['연속발견횟수']}"

            message += f"""
{i}. {stock['종목명']} ({stock['종목코드']}){status}
   현재가: {stock['현재가']:,}원
   상승률: +{stock['상승률']}%
"""

        if len(results) > top_n:
            message += f"\n* 상위 {top_n}개만 표시 (전체 {len(results)}개)"

        return message

    def format_surge_results(
        self,
        results_by_grade: Dict[str, List[Dict]]
    ) -> List[str]:
        """급등주 결과를 포맷팅합니다 (여러 메시지로 분할)"""
        from datetime import datetime

        messages = []
        results_a = results_by_grade.get('A', [])
        results_b = results_by_grade.get('B', [])
        results_c = results_by_grade.get('C', [])

        # 첫 번째 메시지: 요약 + A급
        msg1 = f"""📊 급등주 스크리닝 결과
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

{'='*30}
🔥 A급: {len(results_a)}개
⚡ B급: {len(results_b)}개
👀 C급: {len(results_c)}개
{'='*30}
"""

        if results_a:
            msg1 += "\n🔥 A급 급등 초기 🔥\n\n"
            for stock in results_a[:5]:
                msg1 += self._format_stock(stock) + "\n\n"
            if len(results_a) > 5:
                msg1 += f"... 외 {len(results_a) - 5}개\n"

        messages.append(msg1)

        # B급, C급 메시지
        if results_b:
            msg2 = "⚡ B급 강세 ⚡\n\n"
            for stock in results_b[:5]:
                msg2 += self._format_stock(stock) + "\n\n"
            if len(results_b) > 5:
                msg2 += f"... 외 {len(results_b) - 5}개\n"
            messages.append(msg2)

        if results_c:
            msg3 = "👀 C급 관심 👀\n\n"
            for stock in results_c[:3]:
                msg3 += self._format_stock(stock) + "\n\n"
            if len(results_c) > 3:
                msg3 += f"... 외 {len(results_c) - 3}개\n"
            messages.append(msg3)

        return messages

    def _format_stock(self, stock: Dict) -> str:
        """개별 종목 포맷팅"""
        return f"""📌 {stock['종목명']}({stock['종목코드']})
💰 {stock['현재가']:,}원 (점수: {stock.get('score', '-')})
📊 {stock.get('이유', '')}"""


if __name__ == "__main__":
    # 텔레그램 테스트
    notifier = TelegramNotifier()

    # 테스트 메시지
    test_message = "🤖 주식 분석 시스템 테스트 메시지"
    success = notifier.send_message_sync(test_message)
    print(f"전송 {'성공' if success else '실패'}")
