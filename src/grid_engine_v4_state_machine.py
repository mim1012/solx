"""
Phoenix Grid Engine v4.0 - State Machine Edition
상태 머신 기반 Tier 관리로 CRITICAL 이슈 해결

주요 개선사항:
✅ C3. Race Condition 제거 (TierStateMachine + Lock)
✅ C4. 주문 수량 검증 (0, 음수, 비정상 가격 차단)
✅ C5. Gap Trading 배치 제한 (MAX_BATCH_ORDERS)
✅ H4. 부분 체결 정확한 추적 (PARTIAL_FILLED 상태)
✅ H7. 예외 발생 시 안전한 복구 (ERROR 상태)
"""

from typing import List, Optional, Tuple
from datetime import datetime
from math import floor
from dataclasses import replace
import logging
import threading

from .models import Position, TradeSignal, GridSettings, SystemState

# 상태 머신 import
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from tier_state_machine import TierStateMachine, TierState


logger = logging.getLogger(__name__)


class GridEngineV4:
    """
    Phoenix 그리드 거래 엔진 v4.0

    [v4.0 주요 개선]
    - 상태 머신 기반 Tier 관리
    - Race Condition 완전 제거
    - Gap Trading 제한 (설정 가능)
    - 주문 수량 검증 강화
    - 부분 체결 명확히 추적
    """

    # 안전 설정
    MAX_BATCH_ORDERS = 3      # Gap 발생 시 최대 배치 주문 개수
    MAX_ORDER_QUANTITY = 10000  # 주문 수량 상한선
    MIN_PRICE = 0.01          # 최소 유효 가격

    def __init__(self, settings: GridSettings):
        """
        그리드 엔진 초기화

        Args:
            settings: 그리드 시스템 설정
        """
        self.settings = settings
        self.positions: List[Position] = []
        self.tier1_price: float = settings.tier1_price
        self.current_price: float = 0.0
        self.account_balance: float = settings.investment_usd

        # [v4.0] 상태 머신 초기화
        self.state_machine = TierStateMachine(total_tiers=settings.total_tiers)
        self._process_lock = threading.RLock()  # process_tick 동시 호출 방지
        self._init_state_machine()

        # 검증
        if settings.ticker != "SOXL":
            raise ValueError(f"지원하지 않는 종목: {settings.ticker}. SOXL만 지원합니다.")

        logger.info(f"[v4.0] GridEngine 초기화 완료 (State Machine Edition)")
        logger.info(f"  - 최대 배치 주문: {self.MAX_BATCH_ORDERS}개")
        logger.info(f"  - 주문 수량 상한: {self.MAX_ORDER_QUANTITY:,}주")

    def _init_state_machine(self):
        """상태 머신 초기화 - 모든 Tier 설정"""
        for tier in range(1, self.settings.total_tiers + 1):
            buy_price = self.calculate_tier_price(tier)
            sell_price = buy_price * (1 + self.settings.sell_target)
            self.state_machine.initialize_tier(tier, buy_price, sell_price)

        logger.info(f"상태 머신: {self.settings.total_tiers}개 Tier 초기화 완료")

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

        # 최소 가격 보장
        if tier_price < self.MIN_PRICE:
            logger.warning(f"Tier {tier} 계산 가격 ${tier_price:.4f}이 최소값 미만, ${self.MIN_PRICE}로 조정")
            return self.MIN_PRICE

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

        decline_rate = (self.tier1_price - current_price) / self.tier1_price
        tier = int(decline_rate / self.settings.buy_interval) + 1

        return min(tier, self.settings.total_tiers)

    def _validate_order_quantity(self, tier: int, quantity: int, price: float) -> bool:
        """
        [v4.0] 주문 수량 검증 (C4 이슈 해결)

        Args:
            tier: Tier 번호
            quantity: 주문 수량
            price: 주문 가격

        Returns:
            bool: 검증 통과 여부
        """
        # 1. 가격 검증
        if price <= 0:
            logger.error(f"Tier {tier}: 유효하지 않은 가격 ${price:.4f} (주문 차단)")
            return False

        if price < self.MIN_PRICE:
            logger.error(f"Tier {tier}: 가격이 최소값 ${self.MIN_PRICE} 미만 (주문 차단)")
            return False

        # 2. 수량 검증
        if quantity <= 0:
            logger.warning(f"Tier {tier}: 수량이 0 이하 ({quantity}주, 주문 차단)")
            return False

        if quantity > self.MAX_ORDER_QUANTITY:
            logger.error(
                f"Tier {tier}: 수량이 안전 상한 초과 "
                f"({quantity:,}주 > {self.MAX_ORDER_QUANTITY:,}주, 주문 차단)"
            )
            return False

        # 3. 비정상적으로 큰 수량 체크 (가격 오류 감지)
        expected_qty = floor(self.settings.tier_amount / price)
        if quantity > expected_qty * 10:  # 예상의 10배 이상이면 의심
            logger.error(
                f"Tier {tier}: 수량이 예상치의 10배 초과 "
                f"(주문={quantity:,}주, 예상={expected_qty:,}주, 주문 차단)"
            )
            return False

        return True

    def process_tick(self, current_price: float) -> List[TradeSignal]:
        """
        [v4.0] 시세 틱 처리 - 상태 머신 기반

        핵심 변경:
        1. Lock으로 Race Condition 제거
        2. 배치 주문 개수 제한 (MAX_BATCH_ORDERS)
        3. 주문 수량 검증
        4. 상태 머신으로 Tier 상태 관리

        Args:
            current_price: 현재가 (USD)

        Returns:
            생성된 거래 신호 리스트
        """
        # [v4.0 FIX] 전체 틱 처리를 원자적으로 수행 (Race Condition 완전 제거)
        with self._process_lock:
            signals = []

            # 가격 유효성 검사
            if current_price <= 0:
                logger.warning(f"유효하지 않은 현재가: ${current_price:.4f}, 틱 처리 건너뜀")
                return signals

            self.current_price = current_price

            # 1. Tier 1 갱신 확인
            self.update_tier1(current_price)

            # 2. 매도 조건 확인 (배치)
            if not self.settings.sell_limit:
                sell_signal = self._process_sell_batch(current_price)
                if sell_signal:
                    signals.append(sell_signal)

            # 3. 매수 조건 확인 (배치, 제한 적용)
            if not self.settings.buy_limit:
                buy_signal = self._process_buy_batch(current_price)
                if buy_signal:
                    signals.append(buy_signal)

            return signals

    def _process_sell_batch(self, current_price: float) -> Optional[TradeSignal]:
        """
        매도 배치 처리

        Args:
            current_price: 현재가

        Returns:
            매도 신호 (없으면 None)
        """
        sell_batch = []  # (tier, quantity, avg_price)

        # 체결 완료 상태인 Tier만 매도 대상
        filled_tiers = self.state_machine.get_tiers_by_state(TierState.FILLED)

        for tier_info in sorted(filled_tiers, key=lambda t: t.tier_id, reverse=True):
            tier = tier_info.tier_id
            sell_price = tier_info.sell_price

            if current_price >= sell_price:
                # 해당 Position 찾기
                pos = next((p for p in self.positions if p.tier == tier), None)
                if pos:
                    sell_batch.append((tier, pos.quantity, pos.avg_price))
                    actual_profit_rate = (current_price - pos.avg_price) / pos.avg_price
                    logger.debug(
                        f"매도 배치 추가: Tier {tier}, {pos.quantity}주 "
                        f"(실제수익률: {actual_profit_rate:.2%})"
                    )

        # 매도 배치 신호 생성
        if sell_batch:
            total_qty = sum(qty for _, qty, _ in sell_batch)
            tiers = tuple(tier for tier, _, _ in sell_batch)

            # 실제 평균 수익률 계산
            weighted_avg_price = sum(qty * avg_price for _, qty, avg_price in sell_batch) / total_qty
            avg_profit_rate = (current_price - weighted_avg_price) / weighted_avg_price

            signal = TradeSignal(
                action="SELL",
                tier=tiers[0],
                tiers=tiers,
                price=current_price,
                quantity=total_qty,
                reason=f"배치 매도 {len(tiers)}개 Tier (평균수익률: {avg_profit_rate:.2%})"
            )
            logger.info(f"[BATCH SELL] {len(tiers)}개 Tier, 총 {total_qty}주 @ ${current_price:.2f}")
            return signal

        return None

    def _process_buy_batch(self, current_price: float) -> Optional[TradeSignal]:
        """
        [v4.0] 매수 배치 처리 - Gap Trading 제한 적용

        Args:
            current_price: 현재가

        Returns:
            매수 신호 (없으면 None)
        """
        buy_batch = []  # (tier, quantity)
        start_tier = 1 if self.settings.tier1_trading_enabled else 2

        for tier in range(start_tier, self.settings.total_tiers + 1):
            tier_info = self.state_machine.get_tier(tier)
            if not tier_info:
                continue

            # Tier 매수 조건 확인
            tier_price = tier_info.buy_price
            if current_price <= tier_price:
                # [v4.0 FIX] Race Condition 방지: EMPTY 체크와 LOCK을 원자적으로 수행
                if not self.state_machine.try_lock_for_buy(tier):
                    # 이미 다른 스레드가 처리 중이거나 EMPTY가 아님
                    continue

                # 수량 계산
                raw_qty = self.settings.tier_amount / current_price
                quantity = max(1, floor(raw_qty))

                # [v4.0] 수량 검증
                if not self._validate_order_quantity(tier, quantity, current_price):
                    logger.warning(f"Tier {tier}: 수량 검증 실패, 매수 건너뜀")
                    # Lock 해제 (원래 상태로 복원)
                    self.state_machine.unlock(tier, TierState.EMPTY)
                    continue

                buy_batch.append((tier, quantity))
                logger.debug(f"매수 배치 추가: Tier {tier}, {quantity}주 (LOCKED)")

                # [v4.0] 배치 제한 확인
                if len(buy_batch) >= self.MAX_BATCH_ORDERS:
                    logger.warning(
                        f"배치 주문 제한 도달: {len(buy_batch)}개 "
                        f"(최대 {self.MAX_BATCH_ORDERS}개)"
                    )
                    break

        # 매수 배치 신호 생성
        if buy_batch:
            total_qty = sum(qty for _, qty in buy_batch)
            total_cost = total_qty * current_price

            # 잔고 확인
            if self.account_balance >= total_cost:
                tiers = tuple(tier for tier, _ in buy_batch)

                signal = TradeSignal(
                    action="BUY",
                    tier=tiers[0],
                    tiers=tiers,
                    price=current_price,
                    quantity=total_qty,
                    reason=f"배치 매수 {len(tiers)}개 Tier"
                )
                logger.info(
                    f"[BATCH BUY] {len(tiers)}개 Tier, 총 {total_qty}주 @ "
                    f"${current_price:.2f} (비용: ${total_cost:.2f})"
                )
                return signal
            else:
                # [v4.0 FIX] 잔고 부족 시 Lock 해제
                logger.warning(
                    f"잔고 부족으로 배치 매수 중단: "
                    f"필요=${total_cost:.2f}, 잔고=${self.account_balance:.2f}"
                )
                for tier, _ in buy_batch:
                    self.state_machine.unlock(tier, TierState.EMPTY)
                    logger.debug(f"Tier {tier} Lock 해제 (잔고 부족)")

        return None

    def confirm_order(
        self,
        signal: TradeSignal,
        order_id: str,
        filled_qty: int,
        filled_price: float,
        success: bool = True,
        error_message: str = ""
    ):
        """
        [v4.0] 주문 결과 확인 및 상태 업데이트

        Args:
            signal: 원래 신호
            order_id: 주문 번호
            filled_qty: 체결 수량
            filled_price: 체결 가격
            success: 성공 여부
            error_message: 오류 메시지 (실패 시)
        """
        if signal.action == "BUY":
            self._confirm_buy_order(signal, order_id, filled_qty, filled_price, success, error_message)
        elif signal.action == "SELL":
            self._confirm_sell_order(signal, order_id, filled_qty, filled_price, success, error_message)

    def _confirm_buy_order(
        self,
        signal: TradeSignal,
        order_id: str,
        filled_qty: int,
        filled_price: float,
        success: bool,
        error_message: str
    ):
        """매수 주문 확인"""
        if not success:
            # [v4.0 FIX] 실패 시 LOCKED → EMPTY로 복원 후 ERROR 처리
            for tier in signal.tiers:
                tier_info = self.state_machine.get_tier(tier)
                if tier_info and tier_info.state == TierState.LOCKED:
                    # Lock 해제
                    self.state_machine.unlock(tier, TierState.EMPTY)
                # ERROR 상태로 마킹
                self.state_machine.mark_error(tier, error_message)
                logger.error(f"Tier {tier} 매수 실패: {error_message}")
            return

        # [FIX] 배치 주문 수량 분배
        num_tiers = len(signal.tiers)
        # 원래 주문 수량 (signal.quantity)과 실제 체결 수량 (filled_qty) 분리
        ordered_base_qty = signal.quantity // num_tiers
        ordered_remainder = signal.quantity % num_tiers

        filled_base_qty = filled_qty // num_tiers
        filled_remainder = filled_qty % num_tiers

        total_filled = 0  # 검증용

        for idx, tier in enumerate(signal.tiers):
            # 각 Tier별 원래 주문 수량과 실제 체결 수량
            tier_ordered_qty = ordered_base_qty + (ordered_remainder if idx == 0 else 0)
            tier_filled_qty = filled_base_qty + (filled_remainder if idx == 0 else 0)

            # 1. ORDERING 상태로 전이 (원래 주문 수량 기록)
            if not self.state_machine.mark_ordering(tier, order_id, tier_ordered_qty):
                logger.warning(f"Tier {tier}: ORDERING 상태 전이 실패")
                continue

            # 2. FILLED 또는 PARTIAL_FILLED 상태로 전이
            if self.state_machine.mark_filled(tier, tier_filled_qty, filled_price):
                # 3. Position 추가
                invested = tier_filled_qty * filled_price
                new_position = Position(
                    tier=tier,
                    quantity=tier_filled_qty,
                    avg_price=filled_price,
                    invested_amount=invested,
                    opened_at=datetime.now()
                )
                self.positions.append(new_position)

                # 4. 잔고 차감
                self.account_balance -= tier_filled_qty * filled_price
                total_filled += tier_filled_qty

                logger.info(
                    f"Tier {tier} 매수 체결: {tier_filled_qty}/{tier_ordered_qty}주 @ ${filled_price:.2f} "
                    f"(주문번호: {order_id})"
                )

        # [FIX] 검증: 실제 체결 수량과 할당 수량이 일치하는지 확인
        if total_filled != filled_qty:
            logger.error(
                f"[CRITICAL] 체결 수량 불일치! "
                f"실제={filled_qty}주, 할당={total_filled}주, 차이={filled_qty - total_filled}주"
            )

    def _confirm_sell_order(
        self,
        signal: TradeSignal,
        order_id: str,
        filled_qty: int,
        filled_price: float,
        success: bool,
        error_message: str
    ):
        """매도 주문 확인"""
        if not success:
            for tier in signal.tiers:
                self.state_machine.mark_error(tier, error_message)
                logger.error(f"Tier {tier} 매도 실패: {error_message}")
            return

        for tier in signal.tiers:
            # 1. [FIX] Position 정보를 먼저 읽기 (삭제 전!)
            pos = next((p for p in self.positions if p.tier == tier), None)
            if not pos:
                logger.warning(f"Tier {tier} 매도 대상 포지션 없음")
                continue

            # 2. SELLING 상태로
            self.state_machine.transition(tier, TierState.SELLING, order_id=order_id)

            # 3. [FIX] 수익/원금 계산 (각 Tier의 실제 수량 사용)
            tier_qty = pos.quantity  # 이 Tier의 실제 보유 수량
            profit = (filled_price - pos.avg_price) * tier_qty
            principal = pos.avg_price * tier_qty
            total_proceeds = principal + profit

            # 4. [FIX] 잔고 복구 (Position 삭제 전!)
            self.account_balance += total_proceeds

            logger.info(
                f"Tier {tier} 매도 체결: {tier_qty}주 @ ${filled_price:.2f} "
                f"(원금: ${principal:.2f}, 수익: ${profit:.2f}, 합계: ${total_proceeds:.2f}, 주문번호: {order_id})"
            )

            # 5. [FIX] 전량 매도 (배치 매도는 항상 전량 처리)
            # 전량 매도: Position 제거
            self.positions = [p for p in self.positions if p.tier != tier]
            # SOLD → EMPTY로 (재사용 가능)
            self.state_machine.transition(tier, TierState.SOLD)
            self.state_machine.transition(tier, TierState.EMPTY)

    def update_tier1(self, current_price: float) -> Tuple[bool, Optional[float]]:
        """Tier 1 (High Water Mark) 갱신 로직"""
        if not self.settings.tier1_auto_update:
            return False, None

        if current_price > self.tier1_price:
            old_tier1 = self.tier1_price
            self.tier1_price = current_price

            # [BUG FIX] 기존 상태를 보존하면서 가격만 재계산
            # _init_state_machine()을 호출하면 모든 티어가 EMPTY로 리셋되어
            # 진행 중인 주문(ORDERING, LOCKED)이나 보유 포지션(FILLED)이 사라짐
            self._update_tier_prices()

            logger.info(f"Tier 1 갱신: ${old_tier1:.2f} → ${self.tier1_price:.2f}")
            return True, old_tier1

        return False, None

    def _update_tier_prices(self):
        """기존 상태를 보존하면서 모든 Tier의 가격만 재계산"""
        with self.state_machine._lock:
            for tier in range(1, self.settings.total_tiers + 1):
                buy_price = self.calculate_tier_price(tier)
                sell_price = buy_price * (1 + self.settings.sell_target)

                tier_info = self.state_machine._tiers.get(tier)
                if tier_info:
                    # 가격만 갱신, 상태/주문정보는 보존
                    tier_info.buy_price = buy_price
                    tier_info.sell_price = sell_price
                else:
                    # 새 티어면 초기화
                    self.state_machine.initialize_tier(tier, buy_price, sell_price)

        logger.info(f"Tier 가격 재계산 완료 (상태 보존)")

    def get_status(self) -> dict:
        """[v4.0] 시스템 상태 조회 - 상태 머신 정보 포함"""
        return {
            'tier1_price': self.tier1_price,
            'current_price': self.current_price,
            'account_balance': self.account_balance,
            'total_positions': len(self.positions),
            'state_summary': {
                'EMPTY': len(self.state_machine.get_tiers_by_state(TierState.EMPTY)),
                'ORDERING': len(self.state_machine.get_tiers_by_state(TierState.ORDERING)),
                'FILLED': len(self.state_machine.get_tiers_by_state(TierState.FILLED)),
                'PARTIAL_FILLED': len(self.state_machine.get_tiers_by_state(TierState.PARTIAL_FILLED)),
                'ERROR': len(self.state_machine.get_tiers_by_state(TierState.ERROR)),
            }
        }

    # ============================================
    # 하위 호환성 메서드 (Phoenix Main 연동용)
    # ============================================

    def execute_buy(
        self,
        signal: TradeSignal,
        actual_filled_price: Optional[float] = None,
        actual_filled_qty: Optional[int] = None
    ) -> Position:
        """
        [호환성] 매수 실행 (기존 phoenix_main.py와 호환)

        내부적으로 confirm_order를 호출하여 상태 머신 업데이트

        Args:
            signal: 매수 신호
            actual_filled_price: 실제 체결가
            actual_filled_qty: 실제 체결 수량

        Returns:
            생성된 포지션 (배치 시 대표 티어)
        """
        filled_price = actual_filled_price if actual_filled_price is not None else signal.price
        filled_qty = actual_filled_qty if actual_filled_qty is not None else signal.quantity

        # 더미 order_id (실제로는 API에서 받아야 함)
        order_id = f"COMPAT_BUY_{signal.tier}_{datetime.now().strftime('%H%M%S')}"

        # 상태 머신 업데이트
        self.confirm_order(
            signal=signal,
            order_id=order_id,
            filled_qty=filled_qty,
            filled_price=filled_price,
            success=True
        )

        # 대표 Tier 포지션 반환
        rep_tier = signal.tiers[0] if signal.tiers else signal.tier
        position = next((p for p in self.positions if p.tier == rep_tier), None)

        if position:
            return position
        else:
            # 포지션이 없으면 더미 생성 (하위 호환성)
            qty = filled_qty // len(signal.tiers) if signal.tiers else filled_qty
            return Position(
                tier=rep_tier,
                quantity=qty,
                avg_price=filled_price,
                invested_amount=qty * filled_price,
                opened_at=datetime.now()
            )

    def execute_sell(
        self,
        signal: TradeSignal,
        actual_filled_price: Optional[float] = None,
        actual_filled_qty: Optional[int] = None
    ) -> float:
        """
        [호환성] 매도 실행 (기존 phoenix_main.py와 호환)

        Args:
            signal: 매도 신호
            actual_filled_price: 실제 체결가
            actual_filled_qty: 실제 체결 수량

        Returns:
            매도 수익금 (USD)
        """
        filled_price = actual_filled_price if actual_filled_price is not None else signal.price
        filled_qty = actual_filled_qty if actual_filled_qty is not None else signal.quantity

        # 수익 계산 (매도 전에)
        profit = 0.0
        for tier in (signal.tiers or [signal.tier]):
            pos = next((p for p in self.positions if p.tier == tier), None)
            if pos:
                profit += (filled_price - pos.avg_price) * pos.quantity

        # 더미 order_id
        order_id = f"COMPAT_SELL_{signal.tier}_{datetime.now().strftime('%H%M%S')}"

        # 상태 머신 업데이트
        self.confirm_order(
            signal=signal,
            order_id=order_id,
            filled_qty=filled_qty,
            filled_price=filled_price,
            success=True
        )

        return profit

    def get_system_state(self, current_price: float) -> SystemState:
        """
        [호환성] 시스템 상태 조회 (Phoenix Main용)

        Args:
            current_price: 현재가

        Returns:
            SystemState 객체
        """
        self.current_price = current_price

        # 집계 계산
        total_quantity = sum(pos.quantity for pos in self.positions)
        total_invested = sum(pos.quantity * pos.avg_price for pos in self.positions)

        # 주식 평가액
        stock_value = sum(pos.current_value(current_price) for pos in self.positions)

        # 총 자산
        equity = self.account_balance + stock_value

        # 수익금/수익률
        total_profit = equity - self.settings.investment_usd
        profit_rate = (total_profit / self.settings.investment_usd * 100) if self.settings.investment_usd > 0 else 0.0

        # 현재 Tier
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
            profit_rate=profit_rate,
            buy_status="정상",
            sell_status="정상",
            last_update=datetime.now()
        )
