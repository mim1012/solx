"""
src/telegram_notifier.py 단위 테스트

테스트 범위:
1. 텔레그램 봇 초기화
2. 메시지 전송
3. 거래 알림 포맷
4. 에러 핸들링

코드 리뷰에서 식별된 이슈:
- 메시지 전송 실패 시 retry 로직 부재
"""

import pytest
from unittest.mock import Mock, patch
from src.telegram_notifier import TelegramNotifier
from src.models import TradeSignal
from datetime import datetime


class TestTelegramInitialization:
    """텔레그램 초기화 테스트"""

    def test_create_notifier(self, mock_telegram_bot):
        """텔레그램 알리미 생성"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id"
        )

        assert notifier.bot_token == "test_token"
        assert notifier.chat_id == "test_chat_id"


class TestMessageSending:
    """메시지 전송 테스트"""

    def test_send_simple_message(self, mock_telegram_bot):
        """간단한 메시지 전송"""
        notifier = TelegramNotifier("token", "chat_id")
        notifier.bot = mock_telegram_bot

        result = notifier.send_message("테스트 메시지")

        assert result == True
        mock_telegram_bot.send_message.assert_called_once()

    @pytest.mark.xfail(reason="Retry logic not implemented")
    def test_send_message_with_retry(self, mock_telegram_bot):
        """메시지 전송 실패 시 재시도"""
        notifier = TelegramNotifier("token", "chat_id")
        notifier.bot = mock_telegram_bot

        # 첫 2번 실패, 3번째 성공
        mock_telegram_bot.send_message.side_effect = [
            Exception("네트워크 에러"),
            Exception("네트워크 에러"),
            True
        ]

        result = notifier.send_message_with_retry("테스트", max_retries=3)

        assert result == True
        assert mock_telegram_bot.send_message.call_count == 3


class TestTradeNotification:
    """거래 알림 테스트"""

    def test_notify_buy_signal(self, mock_telegram_bot):
        """매수 알림"""
        notifier = TelegramNotifier("token", "chat_id")
        notifier.bot = mock_telegram_bot

        signal = TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Tier 1 매수 조건",
            timestamp=datetime.now()
        )

        notifier.notify_trade_signal(signal)

        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args[0][0]
        assert "매수" in call_args
        assert "Tier 1" in call_args

    def test_notify_sell_signal(self, mock_telegram_bot):
        """매도 알림"""
        notifier = TelegramNotifier("token", "chat_id")
        notifier.bot = mock_telegram_bot

        signal = TradeSignal(
            action="SELL",
            tier=1,
            price=10.1,
            quantity=10,
            reason="Tier 1 목표가 도달",
            timestamp=datetime.now()
        )

        notifier.notify_trade_signal(signal)

        call_args = mock_telegram_bot.send_message.call_args[0][0]
        assert "매도" in call_args
