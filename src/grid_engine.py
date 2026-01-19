"""
Phoenix Grid Engine - 핵심 그리드 거래 로직 v3.1 (CUSTOM)
Tier 1 거래 기능 포함
"""
from typing import List, Optional, Tuple
from datetime import datetime
from math import floor
from dataclasses import replace
import logging

from .models import Position, TradeSignal, GridSettings, SystemState


logger = logging.getLogger(__name__)


class GridEngine:
    """
    Phoenix 그리드 거래 엔진

    [CUSTOM v3.1] Tier 1 거래 기능 포함:
    - tier1_trading_enabled: Tier 1 매수/매도 활성화 플래그
    - tier1_buy_percent: Tier 1 매수 조건 (사용자 설정값)
    """

    def __init__(self, settings: GridSettings):
        """
        그리드 엔진 초기화

        Args:
            settings: 그리드 시스템 설정
        """
        self.settings = settings
        self.positions: List[Position] = []
        self.tier1_price: float = settings.tier1_price  # High Water Mark (초기값: settings에서 가져옴)
        self.current_price: float = 0.0
        self.account_balance: float = settings.investment_usd

        # 검증
        if settings.ticker != "SOXL":
            raise ValueError(f"지원하지 않는 종목: {settings.ticker}. SOXL만 지원합니다.")

        # [CUSTOM v3.1] Tier 1 거래 모드 로깅
        if settings.tier1_trading_enabled:
            logger.info(f"[CUSTOM v3.1] Tier 1 거래 활성화 (매수%: {settings.tier1_buy_percent:.2%})")
        else:
            logger.info(f"[기본 모드] Tier 1은 추적 전용, Tier 2부터 매수 시작")

    def calculate_tier_price(self, tier: int) -> float:
        """
        특정 티어의 매수 기준가 계산

        Args:
            tier: 티어 번호 (1~240)

        Returns:
            해당 티어의 매수 기준가 (USD)
        """
        if tier == 1:
            return self.tier1_price

        # Tier 2 이상: Tier 1 - (티어-1) × 0.5%
        decline_rate = (tier - 1) * self.settings.buy_interval
        tier_price = self.tier1_price * (1 - decline_rate)

        # 최소 가격 보장 (0원 또는 음수 방지)
        min_price = 0.01
        if tier_price < min_price:
            logger.warning(f"Tier {tier} 계산 가격 ${tier_price:.4f}이 최소값 미만, ${min_price}로 조정")
            return min_price

        return tier_price

    def calculate_current_tier(self, current_price: float) -> int:
        """
        현재가 기준으로 현재 티어 계산

        Args:
            current_price: 현재가 (USD)

        Returns:
            현재 티어 (1~240)
        """
        if self.tier1_price == 0 or current_price >= self.tier1_price:
            return 1

        # 하락률 계산
        decline_rate = (self.tier1_price - current_price) / self.tier1_price

        # 티어 계산: 하락률 / 0.5% + 1
        tier = int(decline_rate / self.settings.buy_interval) + 1

        return min(tier, self.settings.total_tiers)

    def update_tier1(self, current_price: float) -> Tuple[bool, Optional[float]]:
        """
        Tier 1 (High Water Mark) 갱신 로직

        조건:
        - tier1_auto_update = TRUE 이어야 함
        - 총 보유 수량 = 0 이어야 함
        - 현재가 > 현재 Tier 1 가격

        Args:
            current_price: 현재가 (USD)

        Returns:
            (갱신 여부, 새로운 Tier 1 가격)
        """
        # 자동 갱신 OFF
        if not self.settings.tier1_auto_update:
            return False, None

        # 보유 중일 때는 갱신 안함
        total_quantity = sum(pos.quantity for pos in self.positions)
        if total_quantity > 0:
            return False, None

        # 초기 설정 또는 상승 시 갱신
        if self.tier1_price == 0 or current_price > self.tier1_price:
            old_tier1 = self.tier1_price
            self.tier1_price = current_price
            logger.info(f"Tier 1 갱신: ${old_tier1:.2f} → ${current_price:.2f}")
            return True, current_price

        return False, None

    def check_buy_condition(self, current_price: float) -> Optional[int]:
        """
        현재가 기준으로 매수 가능한 티어 확인

        [CUSTOM v3.1] tier1_trading_enabled 플래그에 따라 Tier 1 포함 여부 결정

        Args:
            current_price: 현재가 (USD)

        Returns:
            매수 가능한 티어 번호 (없으면 None)
        """
        # 매수 제한 스위치 확인
        if self.settings.buy_limit:
            logger.debug("매수 제한 활성화됨")
            return None

        # 계좌 잔고 확인
        if self.account_balance < self.settings.tier_amount:
            logger.debug(f"잔고 부족: ${self.account_balance:.2f} < ${self.settings.tier_amount:.2f}")
            return None

        # Tier 1 가격 미설정
        if self.tier1_price == 0:
            logger.warning("Tier 1 가격이 설정되지 않음")
            return None

        # [CUSTOM v3.1] 시작 티어 결정
        start_tier = 1 if self.settings.tier1_trading_enabled else 2

        # 티어 순회 (낮은 티어부터)
        for tier in range(start_tier, self.settings.total_tiers + 1):
            # 이미 보유 중인 티어는 제외
            if any(pos.tier == tier for pos in self.positions):
                continue

            # [CUSTOM v3.1] Tier 1 매수 조건
            if tier == 1:
                # tier1_buy_percent 값에 따라 조건 계산
                # 예: 0.0 → 현재가 ≤ Tier 1 가격
                # 예: -0.005 → 현재가 ≤ Tier 1 × 0.995
                # 예: +0.005 → 현재가 ≤ Tier 1 × 1.005
                tier1_buy_price = self.tier1_price * (1 + self.settings.tier1_buy_percent)
                if current_price <= tier1_buy_price:
                    logger.info(f"[CUSTOM] Tier 1 매수 조건 충족: ${current_price:.2f} ≤ ${tier1_buy_price:.2f}")
                    return 1
            else:
                # Tier 2 이상: 기존 로직
                tier_price = self.calculate_tier_price(tier)
                if current_price <= tier_price:
                    logger.info(f"Tier {tier} 매수 조건 충족: ${current_price:.2f} ≤ ${tier_price:.2f}")
                    return tier

        return None

    def check_sell_condition(self, current_price: float) -> Optional[int]:
        """
        현재가 기준으로 매도 가능한 티어 확인

        Args:
            current_price: 현재가 (USD)

        Returns:
            매도 가능한 티어 번호 (없으면 None)
        """
        # 매도 제한 스위치 확인
        if self.settings.sell_limit:
            logger.debug("매도 제한 활성화됨")
            return None

        # 보유 포지션 확인 (높은 티어부터)
        sorted_positions = sorted(self.positions, key=lambda p: p.tier, reverse=True)

        for pos in sorted_positions:
            # 목표 수익률 달성 여부 확인
            profit_rate = (current_price - pos.avg_price) / pos.avg_price

            if profit_rate >= self.settings.sell_target:
                logger.info(f"Tier {pos.tier} 매도 조건 충족: 수익률 {profit_rate:.2%} ≥ {self.settings.sell_target:.2%}")
                return pos.tier

        return None

    def generate_buy_signal(self, current_price: float, tier: int) -> TradeSignal:
        """
        매수 신호 생성

        Args:
            current_price: 현재가 (USD)
            tier: 매수 대상 티어

        Returns:
            매수 신호
        """
        # 매수 수량 계산 (최소 1주 보장)
        raw_qty = self.settings.tier_amount / current_price
        quantity = max(1, floor(raw_qty))

        reason = f"Tier {tier} 진입 (기준가: ${self.calculate_tier_price(tier):.2f})"
        if tier == 1 and self.settings.tier1_trading_enabled:
            reason = f"[CUSTOM] Tier 1 진입 (매수%: {self.settings.tier1_buy_percent:.2%})"

        return TradeSignal(
            action="BUY",
            tier=tier,
            price=current_price,
            quantity=quantity,
            reason=reason
        )

    def generate_sell_signal(self, current_price: float, tier: int) -> TradeSignal:
        """
        매도 신호 생성

        Args:
            current_price: 현재가 (USD)
            tier: 매도 대상 티어

        Returns:
            매도 신호
        """
        # 해당 티어 포지션 찾기
        position = next((p for p in self.positions if p.tier == tier), None)
        if not position:
            raise ValueError(f"Tier {tier} 포지션을 찾을 수 없음")

        profit_rate = (current_price - position.avg_price) / position.avg_price
        reason = f"Tier {tier} 익절 (수익률: {profit_rate:.2%})"

        return TradeSignal(
            action="SELL",
            tier=tier,
            price=current_price,
            quantity=position.quantity,
            reason=reason
        )

    def execute_buy(self, signal: TradeSignal) -> Position:
        """
        매수 실행 (시뮬레이션)

        Args:
            signal: 매수 신호

        Returns:
            생성된 포지션
        """
        # 실제 투자금 계산
        invested = signal.price * signal.quantity

        # 잔고 차감
        if self.account_balance < invested:
            raise ValueError(f"잔고 부족: ${self.account_balance:.2f} < ${invested:.2f}")

        self.account_balance -= invested

        # 포지션 생성
        position = Position(
            tier=signal.tier,
            quantity=signal.quantity,
            avg_price=signal.price,
            invested_amount=invested,
            opened_at=datetime.now()
        )

        self.positions.append(position)
        logger.info(f"매수 체결: Tier {signal.tier}, {signal.quantity}주 @ ${signal.price:.2f}")

        return position

    def execute_sell(self, signal: TradeSignal) -> float:
        """
        매도 실행 (시뮬레이션)

        Args:
            signal: 매도 신호

        Returns:
            매도 수익금 (USD) - 총 매도 금액
        """
        # 해당 티어 포지션 찾기
        position = next((p for p in self.positions if p.tier == signal.tier), None)
        if not position:
            raise ValueError(f"Tier {signal.tier} 포지션을 찾을 수 없음")

        # 매도 금액 계산
        sell_amount = signal.price * signal.quantity

        # 잔고 증가
        self.account_balance += sell_amount

        # 포지션 업데이트 또는 제거
        if signal.quantity == position.quantity:
            # 전체 매도 - 포지션 제거
            self.positions.remove(position)
            profit = sell_amount - position.invested_amount
            logger.info(f"매도 체결 (전체): Tier {signal.tier}, {signal.quantity}주 @ ${signal.price:.2f}, 수익: ${profit:.2f}")
        else:
            # 부분 매도 - 포지션 업데이트
            invested_per_share = position.invested_amount / position.quantity
            sold_invested = invested_per_share * signal.quantity

            remaining_quantity = position.quantity - signal.quantity
            remaining_invested = position.invested_amount - sold_invested

            # frozen dataclass이므로 replace 사용
            updated_position = replace(
                position,
                quantity=remaining_quantity,
                invested_amount=remaining_invested
            )

            idx = self.positions.index(position)
            self.positions[idx] = updated_position

            profit = sell_amount - sold_invested
            logger.info(f"매도 체결 (부분): Tier {signal.tier}, {signal.quantity}주 @ ${signal.price:.2f}, 수익: ${profit:.2f}, 남은 수량: {remaining_quantity}주")

        return sell_amount  # 매도 수익금 (총 매도 금액) 반환

    def get_system_state(self, current_price: float) -> SystemState:
        """
        시스템 현재 상태 조회

        Args:
            current_price: 현재가 (USD)

        Returns:
            시스템 상태
        """
        self.current_price = current_price

        # 집계 계산
        total_quantity = sum(pos.quantity for pos in self.positions)
        total_invested = sum(pos.invested_amount for pos in self.positions)

        # 주식 평가액 (수정: Position.current_value 메서드 사용)
        stock_value = sum(pos.current_value(current_price) for pos in self.positions)

        # 총 자산 = 현금 + 주식 (실현 손익 반영)
        equity = self.account_balance + stock_value

        # 총 손익 = 총 자산 - 초기 투자금
        total_profit = equity - self.settings.investment_usd

        # 수익률
        profit_rate = (total_profit / self.settings.investment_usd) if self.settings.investment_usd > 0 else 0.0

        # 현재 티어
        current_tier = self.calculate_current_tier(current_price)

        return SystemState(
            current_price=current_price,
            tier1_price=self.tier1_price,
            current_tier=current_tier,
            account_balance=self.account_balance,
            total_quantity=total_quantity,
            total_invested=total_invested,
            stock_value=stock_value,
            total_profit=total_profit,
            profit_rate=profit_rate
        )

    def process_tick(self, current_price: float) -> List[TradeSignal]:
        """
        시세 틱 처리 (메인 루프)

        Args:
            current_price: 현재가 (USD)

        Returns:
            생성된 거래 신호 리스트
        """
        signals = []
        MAX_SELL_PER_TICK = 5  # 한 틱당 최대 5개 매도 (플래시 크래시 대응)
        MAX_BUY_PER_TICK = 5   # 한 틱당 최대 5개 매수 (급락 대응)

        # 1. Tier 1 갱신 확인
        self.update_tier1(current_price)

        # 2. 매도 조건 확인 (우선순위 높음, 최대 5개)
        # [FIX #2] Limit 스위치 체크
        if self.settings.sell_limit:
            logger.debug("매도 제한 활성화됨 - 매도 신호 생성 중단")
        else:
            sell_count = 0
            for pos in sorted(self.positions, key=lambda p: p.tier, reverse=True):
                if sell_count >= MAX_SELL_PER_TICK:
                    break

                profit_rate = (current_price - pos.avg_price) / pos.avg_price
                if profit_rate >= self.settings.sell_target:
                    signal = self.generate_sell_signal(current_price, pos.tier)
                    signals.append(signal)
                    sell_count += 1
                    logger.info(f"매도 신호 생성: Tier {pos.tier}, 수익률 {profit_rate:.2%}")

        # 3. 매수 조건 확인 (최대 5개)
        # [FIX #2] Limit 스위치 체크
        if self.settings.buy_limit:
            logger.debug("매수 제한 활성화됨 - 매수 신호 생성 중단")
        else:
            start_tier = 1 if self.settings.tier1_trading_enabled else 2
            buy_count = 0

            for tier in range(start_tier, self.settings.total_tiers + 1):
                if buy_count >= MAX_BUY_PER_TICK:
                    break

                # 이미 보유 중인 티어는 제외
                if any(pos.tier == tier for pos in self.positions):
                    continue

                # [FIX #9] 잔고 확인 추가
                # 이미 생성된 매수 신호들의 누적 비용 계산
                accumulated_cost = sum(s.quantity * s.price for s in signals if s.action == "BUY")
                remaining_balance = self.account_balance - accumulated_cost

                # 현재 매수 신호 비용 계산
                tier_price = self.calculate_tier_price(tier)
                if current_price <= tier_price:
                    signal = self.generate_buy_signal(current_price, tier)
                    if signal:  # None이 아닌 경우만
                        # 신호 비용
                        signal_cost = signal.quantity * signal.price

                        # 잔고 확인
                        if remaining_balance < signal_cost:
                            logger.warning(
                                f"잔고 부족으로 매수 중단: "
                                f"필요=${signal_cost:.2f}, 잔고=${remaining_balance:.2f}"
                            )
                            break  # 잔고 부족 시 추가 매수 중단

                        signals.append(signal)
                        buy_count += 1
                        logger.info(f"매수 신호 생성: Tier {tier}, 기준가 ${tier_price:.2f}")

        return signals
