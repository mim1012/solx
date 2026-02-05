"""
Phoenix Telegram Notifier v3.1
텔레그램 봇을 통한 실시간 거래 알림
"""
import requests
from typing import Optional
from datetime import datetime
import logging

from .models import TradeSignal, SystemState, GridSettings


logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    텔레그램 봇 알림 서비스

    기능:
    - 매수/매도 체결 알림
    - 시스템 상태 업데이트
    - 에러 알림
    - Tier 1 갱신 알림
    """

    def __init__(self, token: str, chat_id: str, enabled: bool = True):
        """
        텔레그램 알림 초기화

        Args:
            token: 텔레그램 봇 토큰
            chat_id: 채팅방 ID
            enabled: 알림 활성화 여부
        """
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{token}"

        if self.enabled:
            logger.info(f"텔레그램 알림 활성화: 채팅ID={chat_id}")
        else:
            logger.info("텔레그램 알림 비활성화")

    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        텔레그램 메시지 전송

        Args:
            message: 메시지 내용
            parse_mode: 파싱 모드 ("Markdown" 또는 "HTML")

        Returns:
            전송 성공 여부
        """
        if not self.enabled:
            logger.debug(f"[SKIP] 알림 비활성화: {message}")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"텔레그램 메시지 전송 성공: {message[:50]}...")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"텔레그램 메시지 전송 실패: {e}")
            return False

    def notify_buy_executed(self, signal: TradeSignal, is_tier1: bool = False):
        """
        매수 체결 알림

        Args:
            signal: 매수 신호
            is_tier1: Tier 1 거래 여부
        """
        tier_label = f"[CUSTOM] Tier {signal.tier}" if is_tier1 else f"Tier {signal.tier}"
        message = f"""
🔵 *매수 체결* {tier_label}

📊 종목: `SOXL`
💰 체결가: `${signal.price:.2f}`
📈 수량: `{signal.quantity}주`
💵 투자금: `${signal.price * signal.quantity:.2f}`

🕐 시각: `{signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")}`
📝 사유: {signal.reason}
"""
        self.send_message(message.strip())

    def notify_sell_executed(self, signal: TradeSignal, profit: float, profit_rate: float):
        """
        매도 체결 알림

        Args:
            signal: 매도 신호
            profit: 수익금 (USD)
            profit_rate: 수익률
        """
        profit_emoji = "🟢" if profit > 0 else "🔴"
        message = f"""
{profit_emoji} *매도 체결* Tier {signal.tier}

📊 종목: `SOXL`
💰 체결가: `${signal.price:.2f}`
📉 수량: `{signal.quantity}주`
💵 매도금: `${signal.price * signal.quantity:.2f}`

💸 수익: `${profit:.2f}` ({profit_rate:+.2%})

🕐 시각: `{signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")}`
📝 사유: {signal.reason}
"""
        self.send_message(message.strip())

    def notify_tier1_updated(self, old_price: float, new_price: float):
        """
        Tier 1 갱신 알림

        Args:
            old_price: 이전 Tier 1 가격
            new_price: 새로운 Tier 1 가격
        """
        change_rate = ((new_price - old_price) / old_price) if old_price > 0 else 0.0
        message = f"""
⬆️ *Tier 1 갱신 (High Water Mark)*

📊 종목: `SOXL`
🔼 변경: `${old_price:.2f}` → `${new_price:.2f}` ({change_rate:+.2%})

🕐 시각: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`
"""
        self.send_message(message.strip())

    def notify_system_status(self, state: SystemState, settings: GridSettings):
        """
        시스템 상태 요약 알림

        Args:
            state: 시스템 상태
            settings: 그리드 설정
        """
        tier1_mode = "거래 활성화" if settings.tier1_trading_enabled else "추적 전용"
        message = f"""
📊 *Phoenix 시스템 상태*

🏷️ 종목: `SOXL`
📍 현재가: `${state.current_price:.2f}`
🎯 Tier 1: `${state.tier1_price:.2f}` ({tier1_mode})
📊 현재 티어: `{state.current_tier} / {settings.total_tiers}`

💼 포트폴리오:
• 예수금: `${state.account_balance:.2f}`
• 보유량: `{state.total_quantity}주`
• 평가금: `${state.stock_value:.2f}`
• 투자금: `${state.total_invested:.2f}`

💹 손익:
• 수익금: `${state.total_profit:+.2f}`
• 수익률: `{state.profit_rate:+.2%}`

🕐 업데이트: `{state.last_update.strftime("%Y-%m-%d %H:%M:%S")}`
"""
        self.send_message(message.strip())

    def notify_error(self, error_message: str, details: Optional[str] = None):
        """
        에러 알림

        Args:
            error_message: 에러 메시지
            details: 상세 정보 (선택)
        """
        message = f"""
⚠️ *시스템 에러*

🔴 에러: `{error_message}`
"""
        if details:
            message += f"\n📝 상세: {details}"

        message += f"\n\n🕐 시각: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"

        self.send_message(message.strip())

    def notify_system_start(self, settings: GridSettings):
        """
        시스템 시작 알림

        Args:
            settings: 그리드 설정
        """
        tier1_mode = "거래 활성화" if settings.tier1_trading_enabled else "추적 전용"
        tier1_detail = ""
        if settings.tier1_trading_enabled:
            tier1_detail = f"\n• Tier 1 매수%: `{settings.tier1_buy_percent:+.2%}`"

        message = f"""
🚀 *Phoenix 시스템 시작*

📊 종목: `{settings.ticker}`
💰 투자금: `${settings.investment_usd:.2f}`
🎯 티어 분할: `{settings.total_tiers}개`
💵 1티어 금액: `${settings.tier_amount:.2f}`

⚙️ 설정:
• Tier 1 모드: `{tier1_mode}`{tier1_detail}
• Tier 1 갱신: `{'자동' if settings.tier1_auto_update else '수동'}`
• 매수 간격: `{settings.buy_interval:.2%}`
• 매도 목표: `{settings.sell_target:.2%}`

🔔 텔레그램 알림: `활성화`

🕐 시작: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`

---
⚠️ 실거래 전용 시스템입니다.
"""
        self.send_message(message.strip())

    def notify_system_stop(self, final_state: SystemState):
        """
        시스템 종료 알림

        Args:
            final_state: 최종 시스템 상태
        """
        message = f"""
🛑 *Phoenix 시스템 종료*

📊 최종 상태:
• 현재가: `${final_state.current_price:.2f}`
• 보유량: `{final_state.total_quantity}주`
• 예수금: `${final_state.account_balance:.2f}`

💹 최종 손익:
• 수익금: `${final_state.total_profit:+.2f}`
• 수익률: `{final_state.profit_rate:+.2%}`

🕐 종료: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`
"""
        self.send_message(message.strip())

    def notify_daily_summary(self, state: SystemState, buy_count: int, sell_count: int):
        """
        일일 요약 알림

        Args:
            state: 현재 시스템 상태
            buy_count: 당일 매수 횟수
            sell_count: 당일 매도 횟수
        """
        message = f"""
📅 *일일 거래 요약*

📊 종목: `SOXL`
📅 날짜: `{datetime.now().strftime("%Y-%m-%d")}`

📈 거래 내역:
• 매수: `{buy_count}회`
• 매도: `{sell_count}회`
• 순거래: `{buy_count - sell_count}회`

💼 현재 포지션:
• 보유량: `{state.total_quantity}주`
• 평가금: `${state.stock_value:.2f}`
• 예수금: `${state.account_balance:.2f}`

💹 손익:
• 수익금: `${state.total_profit:+.2f}`
• 수익률: `{state.profit_rate:+.2%}`

🕐 업데이트: `{state.last_update.strftime("%H:%M:%S")}`
"""
        self.send_message(message.strip())

    @staticmethod
    def from_settings(settings: GridSettings) -> 'TelegramNotifier':
        """
        GridSettings에서 TelegramNotifier 생성

        Args:
            settings: 그리드 설정

        Returns:
            TelegramNotifier 인스턴스
        """
        if not settings.telegram_enabled:
            logger.info("텔레그램 알림 비활성화 (설정)")
            return TelegramNotifier("", "", enabled=False)

        if not settings.telegram_token or not settings.telegram_id:
            logger.warning("텔레그램 토큰 또는 ID 미설정, 알림 비활성화")
            return TelegramNotifier("", "", enabled=False)

        return TelegramNotifier(
            token=settings.telegram_token,
            chat_id=settings.telegram_id,
            enabled=True
        )
