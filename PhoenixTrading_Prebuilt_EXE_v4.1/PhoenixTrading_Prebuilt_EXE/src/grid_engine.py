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

        # [P0 FIX] Tier 230 도달 조기 경고 (Risk-03 완화)
        max_tier_held = max([pos.tier for pos in self.positions], default=0)
        if max_tier_held >= 230:
            logger.warning(f"⚠️ Tier {max_tier_held} 도달: 위험 수준 접근 (Tier 240까지 {240 - max_tier_held}개 티어 남음)")

        # [P0 FIX] Tier 240 도달 시 매수 중단 (Risk-03 완화)
        if any(pos.tier == 240 for pos in self.positions):
            logger.error("🛑 Tier 240 도달: 추가 매수 중단")
            return None

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
            # 티어 지정 가격 기준으로 매도가 계산 (실제 매수가 무관)
            tier_buy_price = self.calculate_tier_price(pos.tier)
            tier_sell_price = tier_buy_price * (1 + self.settings.sell_target)

            if current_price >= tier_sell_price:
                # 실제 수익률 계산 (로깅용)
                actual_profit_rate = (current_price - pos.avg_price) / pos.avg_price
                logger.info(
                    f"Tier {pos.tier} 매도 조건 충족: "
                    f"현재가 ${current_price:.2f} ≥ 티어매도가 ${tier_sell_price:.2f} "
                    f"(실제수익률: {actual_profit_rate:.2%})"
                )
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
        # 매수 수량 계산 (최소 1주 보장, 0으로 나누기 방지)
        if current_price <= 0:
            logger.warning(f"[SKIP] 현재가가 유효하지 않음 (${current_price:.2f}), 매수 수량 1로 설정")
            quantity = 1
        else:
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

    def execute_buy(
        self,
        signal: TradeSignal,
        actual_filled_price: Optional[float] = None,
        actual_filled_qty: Optional[int] = None
    ) -> Position:
        """
        매수 실행 (실제 체결가/수량 반영) - 배치 주문 지원

        Args:
            signal: 매수 신호 (signal.tiers가 있으면 배치 주문)
            actual_filled_price: 실제 체결가 (None이면 signal.price 사용)
            actual_filled_qty: 실제 체결 수량 (None이면 signal.quantity 사용)

        Returns:
            생성된 포지션 (배치 시 대표 티어 포지션 반환)
        """
        # 실제 체결가/수량 사용 (없으면 signal 값 사용)
        filled_price = actual_filled_price if actual_filled_price is not None else signal.price
        filled_qty = actual_filled_qty if actual_filled_qty is not None else signal.quantity

        # [P0 FIX] 0수량 포지션 방지
        if filled_qty <= 0:
            logger.warning(
                f"매수 실행 거부: Tier {signal.tier} - "
                f"체결 수량이 0 이하입니다 (filled_qty={filled_qty}). "
                f"포지션을 생성하지 않습니다."
            )
            return None

        # 실제 투자금 계산
        invested = filled_price * filled_qty

        # 잔고 차감
        if self.account_balance < invested:
            raise ValueError(f"잔고 부족: ${self.account_balance:.2f} < ${invested:.2f}")

        self.account_balance -= invested

        # [NEW] 배치 주문 처리
        if signal.tiers and len(signal.tiers) > 1:
            # [P0 FIX] 배치: 극단적 부분체결 검증
            if filled_qty < len(signal.tiers):
                logger.warning(
                    f"[PARTIAL FILL] 배치 매수 극단적 부분체결! "
                    f"체결: {filled_qty}주 < 티어 수: {len(signal.tiers)}"
                )
                # 첫 번째 티어에만 전량 할당
                position = Position(
                    tier=signal.tiers[0],
                    quantity=filled_qty,
                    avg_price=filled_price,
                    invested_amount=filled_price * filled_qty,
                    opened_at=datetime.now()
                )
                self.positions.append(position)

                logger.info(
                    f"배치 매수 부분체결 완료: Tier {signal.tiers[0]}에 {filled_qty}주 @ ${filled_price:.2f} 할당"
                )
                return position

            # 정상 배치: 각 티어에 동일 수량 분배
            qty_per_tier = filled_qty // len(signal.tiers)
            remainder = filled_qty % len(signal.tiers)

            created_positions = []
            for i, tier in enumerate(signal.tiers):
                # 나머지 수량은 첫 번째 티어에 추가
                tier_qty = qty_per_tier + (remainder if i == 0 else 0)

                # [P0 FIX] 0주 포지션 생성 방지
                if tier_qty <= 0:
                    logger.warning(f"Tier {tier} 수량 0주로 스킵 (배치 매수)")
                    continue

                tier_invested = filled_price * tier_qty

                position = Position(
                    tier=tier,
                    quantity=tier_qty,
                    avg_price=filled_price,
                    invested_amount=tier_invested,
                    opened_at=datetime.now()
                )
                self.positions.append(position)
                created_positions.append(position)

            # 로그
            logger.info(
                f"배치 매수 체결: Tiers {signal.tiers}, "
                f"총 {filled_qty}주 @ ${filled_price:.2f}, "
                f"티어당 {qty_per_tier}주 분배"
            )

            return created_positions[0] if created_positions else None

        else:
            # 단일 티어 처리 (기존 로직)
            position = Position(
                tier=signal.tier,
                quantity=filled_qty,
                avg_price=filled_price,
                invested_amount=invested,
                opened_at=datetime.now()
            )

            self.positions.append(position)

            # 로그에 실제 체결 정보 포함
            if actual_filled_price is not None or actual_filled_qty is not None:
                logger.info(
                    f"매수 체결: Tier {signal.tier} - "
                    f"주문 {signal.quantity}주 @ ${signal.price:.2f}, "
                    f"실제 체결 {filled_qty}주 @ ${filled_price:.2f}"
                )
            else:
                logger.info(f"매수 체결: Tier {signal.tier}, {filled_qty}주 @ ${filled_price:.2f}")

            return position

    def execute_sell(
        self,
        signal: TradeSignal,
        actual_filled_price: Optional[float] = None,
        actual_filled_qty: Optional[int] = None
    ) -> float:
        """
        매도 실행 (실제 체결가/수량 반영) - 배치 주문 지원

        Args:
            signal: 매도 신호 (signal.tiers가 있으면 배치 주문)
            actual_filled_price: 실제 체결가 (None이면 signal.price 사용)
            actual_filled_qty: 실제 체결 수량 (None이면 signal.quantity 사용)

        Returns:
            매도 수익금 (USD) - 실현 수익 (총 매도 금액 - 투자금)
        """
        # 실제 체결가/수량 사용 (없으면 signal 값 사용)
        filled_price = actual_filled_price if actual_filled_price is not None else signal.price
        filled_qty = actual_filled_qty if actual_filled_qty is not None else signal.quantity

        # [P0 FIX] 0수량 체결 방지
        if filled_qty <= 0:
            logger.warning(
                f"매도 실행 거부: Tier {signal.tier} - "
                f"체결 수량이 0 이하입니다 (filled_qty={filled_qty}). "
                f"포지션을 유지합니다."
            )
            return 0.0  # 수익 0

        # [NEW] 배치 주문 처리
        if signal.tiers and len(signal.tiers) > 1:
            # [P0 FIX] 부분체결 처리: 먼저 총 보유 수량 계산
            tier_positions = []
            total_quantity = 0
            for tier in signal.tiers:
                position = next((p for p in self.positions if p.tier == tier), None)
                if not position:
                    logger.warning(f"Tier {tier} 포지션을 찾을 수 없음 (배치 매도 중)")
                    continue
                tier_positions.append(position)
                total_quantity += position.quantity

            # 높은 티어부터 제거 (낮은 가격에 산 것부터 매도)
            tier_positions.sort(key=lambda p: p.tier, reverse=True)

            if total_quantity == 0:
                logger.error(f"배치 매도 실패: 보유 수량 0 (Tiers {signal.tiers})")
                return 0.0

            # 체결 수량 검증
            if filled_qty > total_quantity:
                logger.warning(
                    f"체결 수량({filled_qty})이 보유 수량({total_quantity})보다 많음. "
                    f"보유 수량으로 조정합니다."
                )
                filled_qty = total_quantity

            # 부분체결 vs 전량체결
            is_partial_fill = (filled_qty < total_quantity)

            if is_partial_fill:
                # 부분체결: 높은 티어부터 순차적으로 제거
                logger.warning(
                    f"[PARTIAL FILL] 배치 매도 부분체결 발생! "
                    f"체결: {filled_qty}주 / 보유: {total_quantity}주"
                )

                total_profit = 0.0
                total_invested = 0.0
                qty_remaining = filled_qty

                for position in tier_positions:
                    if qty_remaining <= 0:
                        break

                    # 이 티어에서 제거할 수량 (높은 티어부터 순차 제거)
                    qty_to_remove = min(position.quantity, qty_remaining)

                    # 투자금 비례 계산
                    invested_removed = position.invested_amount * (qty_to_remove / position.quantity)
                    total_invested += invested_removed

                    # 포지션 업데이트
                    if qty_to_remove >= position.quantity:
                        # 전량 제거
                        self.positions.remove(position)
                        logger.info(
                            f"  Tier {position.tier}: {position.quantity}주 전량 제거"
                        )
                    else:
                        # 일부만 제거: 새 포지션 생성
                        new_position = Position(
                            tier=position.tier,
                            quantity=position.quantity - qty_to_remove,
                            avg_price=position.avg_price,
                            invested_amount=position.invested_amount - invested_removed,
                            opened_at=position.opened_at
                        )
                        self.positions.remove(position)
                        self.positions.append(new_position)
                        logger.info(
                            f"  Tier {position.tier}: {qty_to_remove}주 제거 "
                            f"(잔여: {new_position.quantity}주)"
                        )

                    qty_remaining -= qty_to_remove

                # 수량 일치 검증
                if qty_remaining != 0:
                    logger.error(
                        f"[CRITICAL] 부분체결 수량 불일치! "
                        f"체결: {filled_qty}주, 실제 제거: {filled_qty - qty_remaining}주"
                    )

                # 매도 금액 및 수익 계산
                sell_amount = filled_price * filled_qty
                self.account_balance += sell_amount
                total_profit = sell_amount - total_invested

                logger.info(
                    f"배치 매도 부분체결 완료: Tiers {signal.tiers}, "
                    f"체결 {filled_qty}주 @ ${filled_price:.2f}, "
                    f"수익: ${total_profit:.2f}"
                )

            else:
                # 전량체결: 모든 포지션 제거
                total_invested = 0.0
                for position in tier_positions:
                    self.positions.remove(position)
                    total_invested += position.invested_amount

                # 매도 금액 및 수익 계산
                sell_amount = filled_price * filled_qty
                self.account_balance += sell_amount
                total_profit = sell_amount - total_invested

                logger.info(
                    f"배치 매도 체결: Tiers {signal.tiers}, "
                    f"총 {filled_qty}주 @ ${filled_price:.2f}, "
                    f"수익: ${total_profit:.2f}"
                )

            return total_profit

        else:
            # 단일 티어 처리 (기존 로직)
            # 해당 티어 포지션 찾기
            position = next((p for p in self.positions if p.tier == signal.tier), None)
            if not position:
                raise ValueError(f"Tier {signal.tier} 포지션을 찾을 수 없음")

            # 매도 금액 계산 (실제 체결가 사용)
            sell_amount = filled_price * filled_qty

            # 잔고 증가
            self.account_balance += sell_amount

            # 포지션 업데이트 또는 제거
            if filled_qty >= position.quantity:
                # 전체 매도 (또는 초과) - 포지션 제거
                self.positions.remove(position)
                profit = sell_amount - position.invested_amount

                # 로그에 실제 체결 정보 포함
                if actual_filled_price is not None or actual_filled_qty is not None:
                    logger.info(
                        f"매도 체결 (전체): Tier {signal.tier} - "
                        f"주문 {signal.quantity}주 @ ${signal.price:.2f}, "
                        f"실제 체결 {filled_qty}주 @ ${filled_price:.2f}, "
                        f"수익: ${profit:.2f}"
                    )
                else:
                    logger.info(f"매도 체결 (전체): Tier {signal.tier}, {filled_qty}주 @ ${filled_price:.2f}, 수익: ${profit:.2f}")
            else:
                # 부분 매도 - 포지션 업데이트
                invested_per_share = position.invested_amount / position.quantity
                sold_invested = invested_per_share * filled_qty

                remaining_quantity = position.quantity - filled_qty
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

                # 로그에 실제 체결 정보 포함
                if actual_filled_price is not None or actual_filled_qty is not None:
                    logger.info(
                        f"매도 체결 (부분): Tier {signal.tier} - "
                        f"주문 {signal.quantity}주 @ ${signal.price:.2f}, "
                        f"실제 체결 {filled_qty}주 @ ${filled_price:.2f}, "
                        f"수익: ${profit:.2f}, 남은 수량: {remaining_quantity}주"
                    )
                else:
                    logger.info(f"매도 체결 (부분): Tier {signal.tier}, {filled_qty}주 @ ${filled_price:.2f}, 수익: ${profit:.2f}, 남은 수량: {remaining_quantity}주")

        return profit  # 실현 수익 반환 (기존과 다름: sell_amount가 아닌 profit 반환)

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
        시세 틱 처리 (메인 루프) - 배치 주문 방식

        현재가 1개를 조회하여:
        1. 매도 가능한 모든 티어를 찾아 수량 합산 → 1번 주문
        2. 매수 가능한 모든 티어를 찾아 수량 합산 → 1번 주문

        Args:
            current_price: 현재가 (USD)

        Returns:
            생성된 거래 신호 리스트 (최대 2개: 매도 1개, 매수 1개)
        """
        signals = []

        # 1. Tier 1 갱신 확인
        self.update_tier1(current_price)

        # 2. 매도 조건 확인 (배치)
        if not self.settings.sell_limit:
            sell_batch = []  # (tier, quantity, avg_price) 튜플 리스트

            for pos in sorted(self.positions, key=lambda p: p.tier, reverse=True):
                # 티어 지정 가격 기준으로 매도가 계산
                tier_buy_price = self.calculate_tier_price(pos.tier)
                tier_sell_price = tier_buy_price * (1 + self.settings.sell_target)

                if current_price >= tier_sell_price:
                    sell_batch.append((pos.tier, pos.quantity, pos.avg_price))
                    actual_profit_rate = (current_price - pos.avg_price) / pos.avg_price
                    logger.debug(f"매도 배치 추가: Tier {pos.tier}, {pos.quantity}주 (실제수익률: {actual_profit_rate:.2%})")

            # 매도 배치 신호 생성
            if sell_batch:
                total_qty = sum(qty for _, qty, _ in sell_batch)
                tiers = tuple(tier for tier, _, _ in sell_batch)

                # 실제 평균 수익률 계산 (로깅용)
                weighted_avg_price = sum(qty * avg_price for _, qty, avg_price in sell_batch) / total_qty
                avg_profit_rate = (current_price - weighted_avg_price) / weighted_avg_price

                signal = TradeSignal(
                    action="SELL",
                    tier=tiers[0],  # 대표 티어 (가장 높은 티어)
                    tiers=tiers,
                    price=current_price,
                    quantity=total_qty,
                    reason=f"배치 매도 {len(tiers)}개 티어 (평균수익률: {avg_profit_rate:.2%})"
                )
                signals.append(signal)
                logger.info(f"[BATCH SELL] {len(tiers)}개 티어, 총 {total_qty}주 @ ${current_price:.2f}")

        # 3. 매수 조건 확인 (배치)
        if not self.settings.buy_limit:
            buy_batch = []  # (tier, quantity) 튜플 리스트
            start_tier = 1 if self.settings.tier1_trading_enabled else 2

            for tier in range(start_tier, self.settings.total_tiers + 1):
                # 이미 보유 중인 티어는 제외
                if any(pos.tier == tier for pos in self.positions):
                    continue

                # 티어 매수 조건 확인
                tier_price = self.calculate_tier_price(tier)
                if current_price <= tier_price:
                    # 매수 수량 계산 (0으로 나누기 방지)
                    if current_price <= 0:
                        logger.warning(f"[SKIP] 현재가가 유효하지 않음 (${current_price:.2f}), 매수 건너뜀")
                        continue

                    raw_qty = self.settings.tier_amount / current_price
                    quantity = max(1, floor(raw_qty))

                    buy_batch.append((tier, quantity))
                    logger.debug(f"매수 배치 추가: Tier {tier}, {quantity}주")

            # 매수 배치 신호 생성 (잔고 확인 포함)
            if buy_batch:
                total_qty = sum(qty for _, qty in buy_batch)
                total_cost = total_qty * current_price

                if self.account_balance >= total_cost:
                    tiers = tuple(tier for tier, _ in buy_batch)

                    signal = TradeSignal(
                        action="BUY",
                        tier=tiers[0],  # 대표 티어 (가장 낮은 티어)
                        tiers=tiers,
                        price=current_price,
                        quantity=total_qty,
                        reason=f"배치 매수 {len(tiers)}개 티어"
                    )
                    signals.append(signal)
                    logger.info(f"[BATCH BUY] {len(tiers)}개 티어, 총 {total_qty}주 @ ${current_price:.2f} (비용: ${total_cost:.2f})")
                else:
                    logger.warning(f"잔고 부족으로 배치 매수 중단: 필요=${total_cost:.2f}, 잔고=${self.account_balance:.2f}")

        return signals
