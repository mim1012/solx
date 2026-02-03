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
from unittest.mock import Mock, patch, MagicMock
from src.telegram_notifier import TelegramNotifier
from src.models import TradeSignal
from datetime import datetime


class TestTelegramInitialization:
    """텔레그램 초기화 테스트"""

    def test_create_notifier(self, mock_telegram_bot):
        """텔레그램 알리미 생성"""
        notifier = TelegramNotifier(
            token="test_token",
            chat_id="test_chat_id"
        )

        assert notifier.token == "test_token"
        assert notifier.chat_id == "test_chat_id"


class TestMessageSending:
    """메시지 전송 테스트"""

    @patch('src.telegram_notifier.requests.post')
    def test_send_simple_message(self, mock_post, mock_telegram_bot):
        """간단한 메시지 전송"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        notifier = TelegramNotifier("token", "chat_id", enabled=True)

        result = notifier.send_message("테스트 메시지")

        assert result == True
        mock_post.assert_called_once()

    @pytest.mark.xfail(reason="Retry logic not implemented")
    def test_send_message_with_retry(self, mock_telegram_bot):
        """메시지 전송 실패 시 재시도"""
        notifier = TelegramNotifier("token", "chat_id", enabled=True)

        result = notifier.send_message_with_retry("테스트", max_retries=3)

        assert result == True


class TestTradeNotification:
    """거래 알림 테스트"""

    @patch('src.telegram_notifier.requests.post')
    def test_notify_buy_signal(self, mock_post, mock_telegram_bot):
        """매수 알림"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        notifier = TelegramNotifier("token", "chat_id", enabled=True)

        signal = TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Tier 1 매수 조건",
            timestamp=datetime.now()
        )

        notifier.notify_buy_executed(signal)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert "매수" in payload["text"]
        assert "Tier 1" in payload["text"]

    @patch('src.telegram_notifier.requests.post')
    def test_notify_sell_signal(self, mock_post, mock_telegram_bot):
        """매도 알림"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        notifier = TelegramNotifier("token", "chat_id", enabled=True)

        signal = TradeSignal(
            action="SELL",
            tier=1,
            price=10.1,
            quantity=10,
            reason="Tier 1 목표가 도달",
            timestamp=datetime.now()
        )

        notifier.notify_sell_executed(signal, profit=1.0, profit_rate=0.01)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert "매도" in payload["text"]
