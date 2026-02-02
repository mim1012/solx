"""
Grid Engine v4.0 - CRITICAL 이슈 해결 검증 테스트

검증 항목:
✅ C3. Race Condition 제거
✅ C4. 주문 수량 검증
✅ C5. Gap Trading 배치 제한
✅ H4. 부분 체결 처리
"""

import pytest
import threading
import time
from datetime import datetime
from unittest.mock import Mock

# 임시 경로 추가
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models import GridSettings
from src.grid_engine_v4_state_machine import GridEngineV4
from tier_state_machine import TierState


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def default_settings():
    """기본 그리드 설정"""
    return GridSettings(
        account_no="12345678-01",
        ticker="SOXL",
        tier1_price=50.0,
        buy_interval=0.005,  # 0.5%
        sell_target=0.03,    # 3%
        tier_amount=500.0,
        total_tiers=240,
        investment_usd=100000.0,
        tier1_auto_update=False,
        tier1_trading_enabled=True,
        tier1_buy_percent=0.0,
        buy_limit=False,   # 매수 허용
        sell_limit=False   # 매도 허용
    )


@pytest.fixture
def engine(default_settings):
    """Grid Engine v4 인스턴스"""
    return GridEngineV4(default_settings)


# ============================================
# C3. Race Condition 제거 테스트
# ============================================

def test_race_condition_prevented(engine):
    """
    [C3] Race Condition 방지 검증

    시나리오:
    - 2개 스레드가 동시에 Tier 5 매수 시도
    - 상태 머신의 Lock이 중복 주문 차단해야 함
    """
    results = {'buy_signals': []}
    lock = threading.Lock()

    def worker(price):
        """워커 스레드"""
        signals = engine.process_tick(price)
        with lock:
            results['buy_signals'].extend(signals)

    # Tier 5 매수 조건 ($47.50)
    tier5_price = engine.calculate_tier_price(5)
    buy_price = tier5_price  # 정확히 조건 충족

    # 2개 스레드 동시 실행
    thread1 = threading.Thread(target=worker, args=(buy_price,))
    thread2 = threading.Thread(target=worker, args=(buy_price,))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # 검증: Tier 중복이 없어야 함
    buy_signals = [s for s in results['buy_signals'] if s.action == "BUY"]

    print(f"\n[C3 테스트] 매수 신호 개수: {len(buy_signals)}")

    # 모든 신호의 Tier를 수집
    all_tiers = []
    for signal in buy_signals:
        all_tiers.extend(signal.tiers)
        print(f"  - Signal: tiers={signal.tiers}, qty={signal.quantity}")

    # 중복 Tier 확인
    unique_tiers = set(all_tiers)
    assert len(all_tiers) == len(unique_tiers), \
        f"Tier 중복 발생! (전체={all_tiers}, 고유={unique_tiers})"

    # 최소 1개 Tier는 포함되어야 함 (테스트가 실제로 동작했는지 확인)
    assert len(all_tiers) >= 1, "매수 신호가 생성되지 않음"

    print(f"[OK] C3 검증 통과: {len(all_tiers)}개 Tier, 중복 없음!")


# ============================================
# C4. 주문 수량 검증 테스트
# ============================================

def test_invalid_price_rejected(engine):
    """
    [C4] 유효하지 않은 가격 차단

    시나리오:
    - 가격 = 0 또는 음수
    - 주문 차단되어야 함
    """
    # 가격 = 0
    assert not engine._validate_order_quantity(1, 100, 0.0), "가격 0 차단 실패"

    # 가격 = 음수
    assert not engine._validate_order_quantity(1, 100, -10.0), "음수 가격 차단 실패"

    # 최소값 미만
    assert not engine._validate_order_quantity(1, 100, 0.001), "최소값 미만 차단 실패"

    print("[OK] C4-1 검증 통과: 유효하지 않은 가격 차단!")


def test_zero_quantity_rejected(engine):
    """
    [C4] 수량 = 0 차단

    시나리오:
    - 투자금이 현재가보다 작아서 수량 = 0
    - 주문 차단되어야 함
    """
    assert not engine._validate_order_quantity(1, 0, 45.0), "수량 0 차단 실패"
    assert not engine._validate_order_quantity(1, -5, 45.0), "음수 수량 차단 실패"

    print("[OK] C4-2 검증 통과: 수량 0 차단!")


def test_excessive_quantity_rejected(engine):
    """
    [C4] 비정상적으로 큰 수량 차단

    시나리오:
    - 가격 오류로 수량이 10,000주 초과
    - 안전 상한선으로 차단되어야 함
    """
    # 안전 상한 초과
    assert not engine._validate_order_quantity(1, 15000, 1.0), "상한 초과 차단 실패"

    # 정상 범위는 통과
    assert engine._validate_order_quantity(1, 100, 45.0), "정상 수량 거부됨!"

    print("[OK] C4-3 검증 통과: 비정상 수량 차단!")


# ============================================
# C5. Gap Trading 배치 제한 테스트
# ============================================

def test_gap_trading_batch_limit(engine):
    """
    [C5] Gap Trading 배치 제한

    시나리오:
    - 가격이 10개 Tier를 건너뜀 (플래시 크래시)
    - MAX_BATCH_ORDERS(3)개로 제한되어야 함
    """
    # 현재가 = Tier 10 조건 (10개 Tier 건너뜀)
    tier10_price = engine.calculate_tier_price(10)

    signals = engine.process_tick(tier10_price)

    buy_signals = [s for s in signals if s.action == "BUY"]
    assert len(buy_signals) == 1, "매수 신호가 없거나 여러 개"

    signal = buy_signals[0]
    batch_count = len(signal.tiers)

    print(f"\n[C5 테스트] 건너뛴 Tier: 10개, 실제 배치: {batch_count}개")

    assert batch_count <= engine.MAX_BATCH_ORDERS, \
        f"배치 제한 초과! ({batch_count}개 > {engine.MAX_BATCH_ORDERS}개)"

    print(f"[OK] C5 검증 통과: Gap 배치 {batch_count}개로 제한됨!")


# ============================================
# H4. 부분 체결 처리 테스트
# ============================================

def test_partial_fill_tracking(engine):
    """
    [H4] 부분 체결 정확한 추적

    시나리오:
    - 100주 주문, 50주만 체결
    - PARTIAL_FILLED 상태로 전이
    - 나중에 추가 50주 체결 → FILLED
    """
    # 1. Tier 5 매수 신호 생성 (실제로는 배치로 여러 Tier 포함될 수 있음)
    tier5_price = engine.calculate_tier_price(5)
    signals = engine.process_tick(tier5_price)

    buy_signal = next((s for s in signals if s.action == "BUY"), None)
    assert buy_signal is not None, "매수 신호 없음"

    # 신호에 실제 포함된 첫 번째 Tier 사용
    test_tier = buy_signal.tiers[0]
    total_ordered_qty = buy_signal.quantity
    qty_per_tier = total_ordered_qty // len(buy_signal.tiers)

    # 2. 부분 체결 (각 Tier당 절반만)
    partial_qty_per_tier = qty_per_tier // 2
    partial_total_qty = partial_qty_per_tier * len(buy_signal.tiers)

    engine.confirm_order(
        signal=buy_signal,
        order_id="ORDER123",
        filled_qty=partial_total_qty,  # 전체의 절반
        filled_price=tier5_price,
        success=True
    )

    # 3. 상태 확인
    test_tier_state = engine.state_machine.get_tier(test_tier)
    assert test_tier_state is not None, f"Tier {test_tier} 상태 없음"

    print(f"\n[H4 테스트] Tier {test_tier} 상태: {test_tier_state.state.value}")
    print(f"  주문 수량: {test_tier_state.ordered_qty}")
    print(f"  체결 수량: {test_tier_state.filled_qty}")

    # 부분 체결 확인
    assert test_tier_state.filled_qty > 0, "체결 수량이 0"
    assert test_tier_state.state == TierState.PARTIAL_FILLED, \
        f"부분 체결 상태가 아님: {test_tier_state.state.value}"

    print("[OK] H4 검증 통과: 부분 체결 추적됨!")


# ============================================
# 통합 시나리오 테스트
# ============================================

def test_full_scenario(engine):
    """
    통합 시나리오: 정상 매수 → 매도

    1. Tier 5 매수
    2. 상태 확인: FILLED
    3. 가격 상승
    4. Tier 5 매도
    5. 상태 확인: EMPTY (재사용 가능)
    """
    # 1. 매수
    buy_price = engine.calculate_tier_price(5)
    buy_signals = engine.process_tick(buy_price)

    buy_signal = next((s for s in buy_signals if s.action == "BUY"), None)
    assert buy_signal is not None, "매수 신호 없음"

    # 신호에 실제 포함된 첫 번째 Tier 사용
    test_tier = buy_signal.tiers[0]

    # 매수 확인 (전량 체결)
    qty = buy_signal.quantity
    engine.confirm_order(
        signal=buy_signal,
        order_id="BUY123",
        filled_qty=qty,
        filled_price=buy_price,
        success=True
    )

    # 2. 상태 확인
    test_tier_state = engine.state_machine.get_tier(test_tier)
    assert test_tier_state.state == TierState.FILLED, f"매수 후 상태 오류: {test_tier_state.state}"

    print(f"\n[통합] 매수 완료: Tier {test_tier}, {qty}주 @ ${buy_price:.2f}")

    # 3. 가격 상승 → 매도 조건 충족 (모든 Tier의 sell_price 이상으로 상승)
    #    Tier 1의 sell_price = tier1_price * 1.03 = $51.50이 가장 높으므로
    #    그 이상으로 설정해야 모든 Tier가 매도됨
    sell_price = engine.tier1_price * (1 + engine.settings.sell_target) + 1.0
    sell_signals = engine.process_tick(sell_price)

    sell_signal = next((s for s in sell_signals if s.action == "SELL"), None)
    assert sell_signal is not None, "매도 신호 없음"
    assert test_tier in sell_signal.tiers, f"Tier {test_tier}가 매도 대상에 미포함"

    # 매도 확인
    engine.confirm_order(
        signal=sell_signal,
        order_id="SELL123",
        filled_qty=sell_signal.quantity,
        filled_price=sell_price,
        success=True
    )

    # 4. 상태 확인 (재사용 가능해야 함)
    test_tier_state = engine.state_machine.get_tier(test_tier)
    assert test_tier_state.state == TierState.EMPTY, f"매도 후 상태 오류: {test_tier_state.state}"

    print(f"[통합] 매도 완료: Tier {test_tier}, {sell_signal.quantity}주 @ ${sell_price:.2f}")
    print("[OK] 통합 시나리오 통과!")


# ============================================
# 실행
# ============================================

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
