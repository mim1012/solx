"""
Tier State Machine - Phoenix Trading System
상태 머신 기반 Tier 관리 (Race Condition 해결)

핵심 개념:
1. 각 Tier는 명확한 상태(State)를 가짐
2. 상태 전이(Transition)는 검증된 경로만 허용
3. 모든 상태 변경은 Lock으로 보호
4. 부분 체결, 예외 등 중간 상태 명확히 추적
"""

import threading
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class TierState(Enum):
    """Tier 상태"""
    EMPTY = "비어있음"              # 초기 상태, 매수 가능
    ORDERING = "매수주문중"         # 매수 주문 전송됨 (체결 대기)
    PARTIAL_FILLED = "부분체결"     # 일부만 체결됨
    FILLED = "체결완료"             # 매수 완료, 매도 대기
    SELLING = "매도주문중"          # 매도 주문 전송됨
    SOLD = "매도완료"               # 매도 완료 (곧 EMPTY로)
    ERROR = "오류"                  # 주문 실패/예외 발생
    LOCKED = "잠김"                 # 동시 접근 방지용


@dataclass
class TierInfo:
    """Tier 정보"""
    tier_id: int                    # Tier 번호 (1~240)
    state: TierState                # 현재 상태

    # 가격 정보
    buy_price: float                # 매수 목표가
    sell_price: float               # 매도 목표가

    # 주문 정보
    order_id: Optional[str] = None  # 주문 번호
    ordered_qty: int = 0            # 주문 수량
    filled_qty: int = 0             # 체결 수량
    filled_price: float = 0.0       # 평균 체결가

    # 메타 정보
    last_updated: Optional[datetime] = None
    error_message: str = ""
    retry_count: int = 0


class TierStateMachine:
    """
    Tier 상태 머신 관리자

    모든 Tier의 상태를 메모리에서 관리하고,
    상태 전이 시 검증 및 동기화 수행
    """

    # 허용된 상태 전이 (from_state -> to_state)
    ALLOWED_TRANSITIONS = {
        TierState.EMPTY: [TierState.ORDERING, TierState.LOCKED, TierState.ERROR],  # [FIX] ERROR 추가
        TierState.ORDERING: [TierState.PARTIAL_FILLED, TierState.FILLED, TierState.ERROR, TierState.EMPTY],
        TierState.PARTIAL_FILLED: [TierState.FILLED, TierState.ERROR],
        TierState.FILLED: [TierState.SELLING, TierState.LOCKED],
        TierState.SELLING: [TierState.SOLD, TierState.ERROR, TierState.FILLED],
        TierState.SOLD: [TierState.EMPTY],
        TierState.ERROR: [TierState.EMPTY, TierState.ORDERING],  # 재시도 가능
        TierState.LOCKED: [TierState.EMPTY, TierState.FILLED, TierState.ORDERING, TierState.ERROR],  # [FIX] ORDERING, ERROR 추가
    }

    def __init__(self, total_tiers: int = 240):
        """
        초기화

        Args:
            total_tiers: 총 Tier 개수
        """
        self.total_tiers = total_tiers
        self._tiers: Dict[int, TierInfo] = {}
        self._lock = threading.RLock()  # 재진입 가능 Lock

        logger.info(f"TierStateMachine 초기화: {total_tiers}개 Tier")

    def initialize_tier(self, tier_id: int, buy_price: float, sell_price: float):
        """Tier 초기화"""
        with self._lock:
            self._tiers[tier_id] = TierInfo(
                tier_id=tier_id,
                state=TierState.EMPTY,
                buy_price=buy_price,
                sell_price=sell_price,
                last_updated=datetime.now()
            )
            logger.debug(f"Tier {tier_id} 초기화: 매수가=${buy_price:.2f}, 매도가=${sell_price:.2f}")

    def get_tier(self, tier_id: int) -> Optional[TierInfo]:
        """Tier 정보 조회 (읽기 전용)"""
        with self._lock:
            tier = self._tiers.get(tier_id)
            if tier:
                # 복사본 반환 (외부 수정 방지)
                import copy
                return copy.deepcopy(tier)
            return None

    def can_transition(self, tier_id: int, new_state: TierState) -> bool:
        """
        상태 전이 가능 여부 확인

        Args:
            tier_id: Tier 번호
            new_state: 전이하려는 상태

        Returns:
            bool: 전이 가능 여부
        """
        with self._lock:
            tier = self._tiers.get(tier_id)
            if not tier:
                logger.error(f"Tier {tier_id} 없음")
                return False

            current_state = tier.state
            allowed = self.ALLOWED_TRANSITIONS.get(current_state, [])

            if new_state in allowed:
                return True
            else:
                logger.warning(
                    f"Tier {tier_id}: 잘못된 상태 전이 시도 "
                    f"{current_state.value} → {new_state.value}"
                )
                return False

    def transition(
        self,
        tier_id: int,
        new_state: TierState,
        order_id: Optional[str] = None,
        filled_qty: int = 0,
        filled_price: float = 0.0,
        error_message: str = ""
    ) -> bool:
        """
        상태 전이 실행 (원자적)

        Args:
            tier_id: Tier 번호
            new_state: 새 상태
            order_id: 주문 번호 (옵션)
            filled_qty: 체결 수량 (옵션)
            filled_price: 체결 가격 (옵션)
            error_message: 오류 메시지 (옵션)

        Returns:
            bool: 성공 여부
        """
        with self._lock:
            if not self.can_transition(tier_id, new_state):
                return False

            tier = self._tiers[tier_id]
            old_state = tier.state

            # 상태 업데이트
            tier.state = new_state
            tier.last_updated = datetime.now()

            # 추가 정보 업데이트
            if order_id:
                tier.order_id = order_id
            if filled_qty > 0:
                tier.filled_qty = filled_qty
            if filled_price > 0:
                tier.filled_price = filled_price
            if error_message:
                tier.error_message = error_message

            logger.info(
                f"Tier {tier_id}: {old_state.value} → {new_state.value} "
                f"(주문={order_id}, 체결={filled_qty}주)"
            )

            return True

    def try_lock_for_buy(self, tier_id: int) -> bool:
        """
        매수 시도를 위한 Tier Lock

        Returns:
            bool: Lock 성공 여부 (EMPTY → LOCKED 전이 성공)
        """
        with self._lock:
            tier = self._tiers.get(tier_id)
            if not tier:
                return False

            # EMPTY 상태만 Lock 가능
            if tier.state == TierState.EMPTY:
                return self.transition(tier_id, TierState.LOCKED)
            else:
                logger.debug(f"Tier {tier_id}: 이미 사용 중 (상태={tier.state.value})")
                return False

    def unlock(self, tier_id: int, restore_state: TierState):
        """Tier Unlock (원래 상태로 복원)"""
        with self._lock:
            tier = self._tiers.get(tier_id)
            if tier and tier.state == TierState.LOCKED:
                self.transition(tier_id, restore_state)

    def mark_ordering(self, tier_id: int, order_id: str, ordered_qty: int) -> bool:
        """매수 주문 전송 완료 마킹"""
        with self._lock:
            tier = self._tiers.get(tier_id)
            if tier and tier.state == TierState.LOCKED:
                tier.order_id = order_id
                tier.ordered_qty = ordered_qty
                return self.transition(tier_id, TierState.ORDERING, order_id=order_id)
            return False

    def mark_filled(self, tier_id: int, filled_qty: int, filled_price: float) -> bool:
        """체결 완료 마킹"""
        with self._lock:
            tier = self._tiers.get(tier_id)
            if not tier:
                return False

            # 전량 체결
            if filled_qty == tier.ordered_qty:
                return self.transition(
                    tier_id,
                    TierState.FILLED,
                    filled_qty=filled_qty,
                    filled_price=filled_price
                )
            # 부분 체결
            elif filled_qty < tier.ordered_qty:
                return self.transition(
                    tier_id,
                    TierState.PARTIAL_FILLED,
                    filled_qty=filled_qty,
                    filled_price=filled_price
                )
            else:
                logger.error(f"Tier {tier_id}: 체결 수량 오류 (주문={tier.ordered_qty}, 체결={filled_qty})")
                return False

    def mark_error(self, tier_id: int, error_message: str) -> bool:
        """오류 상태 마킹"""
        with self._lock:
            return self.transition(tier_id, TierState.ERROR, error_message=error_message)

    def get_tiers_by_state(self, state: TierState) -> List[TierInfo]:
        """특정 상태의 모든 Tier 조회"""
        with self._lock:
            import copy
            return [
                copy.deepcopy(tier)
                for tier in self._tiers.values()
                if tier.state == state
            ]

    def export_to_excel_format(self) -> List[Dict]:
        """Excel 업데이트용 데이터 추출"""
        with self._lock:
            result = []
            for tier_id in sorted(self._tiers.keys()):
                tier = self._tiers[tier_id]
                result.append({
                    'tier_id': tier_id,
                    'state': tier.state.value,
                    'buy_price': tier.buy_price,
                    'sell_price': tier.sell_price,
                    'filled_qty': tier.filled_qty,
                    'filled_price': tier.filled_price,
                    'order_id': tier.order_id or ""
                })
            return result


# ============================================
# 사용 예시
# ============================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 1. 상태 머신 초기화
    sm = TierStateMachine(total_tiers=10)

    # 2. Tier 설정
    for i in range(1, 11):
        sm.initialize_tier(
            tier_id=i,
            buy_price=50.0 - (i * 0.5),  # $50.00, $49.50, $49.00 ...
            sell_price=51.5 - (i * 0.5)
        )

    # 3. 매수 시나리오 (Tier 5)
    print("\n=== 매수 시나리오 ===")

    # 3-1. Lock 시도
    if sm.try_lock_for_buy(5):
        print("✓ Tier 5 Lock 성공")

        # 3-2. 주문 전송
        order_id = "ORDER12345"
        sm.mark_ordering(5, order_id, ordered_qty=100)
        print(f"✓ Tier 5 주문 전송: {order_id}")

        # 3-3. 체결 확인 (부분 체결)
        sm.mark_filled(5, filled_qty=50, filled_price=47.25)
        print("✓ Tier 5 부분 체결: 50주 @ $47.25")

        # 3-4. 추가 체결
        sm.mark_filled(5, filled_qty=100, filled_price=47.30)
        print("✓ Tier 5 전량 체결: 100주 @ $47.30")

    # 4. 동시 접근 방지 테스트
    print("\n=== Race Condition 방지 테스트 ===")
    if sm.try_lock_for_buy(5):
        print("✗ Tier 5 Lock 실패 (이미 체결됨) - 정상!")
    else:
        print("✓ Tier 5 중복 매수 차단됨")

    # 5. 상태 조회
    print("\n=== 현재 상태 ===")
    filled_tiers = sm.get_tiers_by_state(TierState.FILLED)
    print(f"체결 완료 Tier: {[t.tier_id for t in filled_tiers]}")

    empty_tiers = sm.get_tiers_by_state(TierState.EMPTY)
    print(f"비어있는 Tier: {[t.tier_id for t in empty_tiers]}")
