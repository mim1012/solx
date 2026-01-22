"""
배치 주문 로직 테스트
"""
import pytest
from datetime import datetime
from src.grid_engine import GridEngine
from src.models import GridSettings, Position


@pytest.fixture
def grid_engine():
    """테스트용 GridEngine 인스턴스"""
    settings = GridSettings(
        account_no="12345678-01",
        ticker="SOXL",
        investment_usd=1000.0,
        total_tiers=240,
        tier_amount=1000.0 / 240,  # ~$4.17 per tier
        tier1_auto_update=False,
        tier1_trading_enabled=True,
        tier1_buy_percent=0.0,
        buy_limit=False,
        sell_limit=False,
        kis_app_key="test_key",
        kis_app_secret="test_secret",
        kis_account_no="12345678-01",
        system_running=True,
        tier1_price=100.0,  # Tier 1 기준가
        tier_interval=0.5,   # $0.50 간격
        seed_ratio=0.05,
        buy_interval=0.005,  # 0.5%
        sell_target=0.03     # 3%
    )

    engine = GridEngine(settings)
    engine.account_balance = 5000.0  # 테스트용 잔고 설정
    return engine


def test_batch_buy_gap_down(grid_engine):
    """
    급락 시나리오: 여러 티어 매수가를 한번에 통과

    시나리오:
    - Tier 1 매수가: $100
    - Tier 2 매수가: $99.50
    - Tier 3 매수가: $99.00
    - 현재가: $98.50 (3개 티어 모두 통과!)

    기대 결과:
    - 1개의 매수 신호 생성
    - 수량: Tier 1+2+3 합산
    - 가격: $98.50 (현재가)
    """
    # 현재가: $98.50 (Tier 1,2,3 모두 통과)
    current_price = 98.50

    # 시그널 생성
    signals = grid_engine.process_tick(current_price)

    # 검증 1: 1개의 매수 신호만 생성되어야 함
    assert len(signals) == 1, f"Expected 1 signal, got {len(signals)}"

    buy_signal = signals[0]

    # 검증 2: 매수 신호여야 함
    assert buy_signal.action == "BUY"

    # 검증 3: 배치 신호여야 함 (tiers 필드가 있어야 함)
    assert buy_signal.tiers is not None, "tiers field should exist for batch order"
    assert len(buy_signal.tiers) >= 3, f"Expected at least 3 tiers, got {len(buy_signal.tiers)}"

    # 검증 4: 현재가로 주문되어야 함
    assert buy_signal.price == current_price

    # 검증 5: 수량이 양수여야 함 (합산된 값)
    assert buy_signal.quantity > 0, f"Expected positive quantity, got {buy_signal.quantity}"

    print(f"✅ 배치 매수 테스트 성공:")
    print(f"   - Tiers: {buy_signal.tiers}")
    print(f"   - 티어 수: {len(buy_signal.tiers)}개")
    print(f"   - 총 수량: {buy_signal.quantity}주")
    print(f"   - 가격: ${buy_signal.price:.2f}")


def test_batch_sell_gap_up(grid_engine):
    """
    급등 시나리오: 여러 티어 매도가를 한번에 돌파

    시나리오:
    1. 먼저 Tier 1,2,3에 포지션 생성 (매수 시뮬레이션)
    2. 현재가 급등: $105 (모든 티어 매도가 돌파)

    기대 결과:
    - 1개의 매도 신호 생성
    - 수량: Tier 1+2+3 보유 수량 합산
    - 가격: $105 (현재가)
    """
    # Step 1: 포지션 생성 (매수 시뮬레이션)
    tier1_qty = 100
    tier2_qty = 100
    tier3_qty = 100

    pos1 = Position(tier=1, quantity=tier1_qty, avg_price=100.0,
                    invested_amount=100.0*tier1_qty, opened_at=datetime.now())
    pos2 = Position(tier=2, quantity=tier2_qty, avg_price=99.5,
                    invested_amount=99.5*tier2_qty, opened_at=datetime.now())
    pos3 = Position(tier=3, quantity=tier3_qty, avg_price=99.0,
                    invested_amount=99.0*tier3_qty, opened_at=datetime.now())

    grid_engine.positions = [pos1, pos2, pos3]

    # Step 2: 현재가 급등 ($105 - 모든 티어 매도가 돌파)
    # Tier 1 매도가: $100 × 1.03 = $103.00
    # Tier 2 매도가: $99.5 × 1.03 = $102.49
    # Tier 3 매도가: $99.0 × 1.03 = $101.97
    current_price = 105.0

    # 시그널 생성
    signals = grid_engine.process_tick(current_price)

    # 검증 1: 1개의 매도 신호만 생성되어야 함
    assert len(signals) == 1, f"Expected 1 signal, got {len(signals)}"

    sell_signal = signals[0]

    # 검증 2: 매도 신호여야 함
    assert sell_signal.action == "SELL"

    # 검증 3: 배치 신호여야 함
    assert sell_signal.tiers is not None, "tiers field should exist for batch order"
    assert len(sell_signal.tiers) == 3, f"Expected 3 tiers, got {len(sell_signal.tiers)}"

    # 검증 4: 현재가로 주문되어야 함
    assert sell_signal.price == current_price

    # 검증 5: 수량이 합산되어야 함
    expected_qty = tier1_qty + tier2_qty + tier3_qty
    assert sell_signal.quantity == expected_qty, \
        f"Expected quantity {expected_qty}, got {sell_signal.quantity}"

    print(f"✅ 배치 매도 테스트 성공:")
    print(f"   - Tiers: {sell_signal.tiers}")
    print(f"   - 총 수량: {sell_signal.quantity}주")
    print(f"   - 가격: ${sell_signal.price:.2f}")


def test_execute_buy_batch(grid_engine):
    """
    execute_buy에서 배치 신호를 처리할 수 있는지 테스트

    검증:
    - 배치 신호로 execute_buy 호출 시 여러 포지션이 생성되는지 확인
    """
    from src.models import TradeSignal

    # 잔고 충분하게 설정
    grid_engine.account_balance = 50000.0

    # 배치 매수 신호 생성
    batch_signal = TradeSignal(
        action="BUY",
        tier=1,
        tiers=(1, 2, 3),
        price=98.50,
        quantity=300,  # 총 300주
        reason="배치 매수 테스트"
    )

    # 초기 포지션 수
    initial_position_count = len(grid_engine.positions)

    # 매수 실행
    grid_engine.execute_buy(batch_signal)

    # 검증 1: 3개의 포지션이 생성되어야 함
    assert len(grid_engine.positions) == initial_position_count + 3, \
        f"Expected 3 new positions, got {len(grid_engine.positions) - initial_position_count}"

    # 검증 2: 각 티어에 포지션이 있어야 함
    tier_positions = {p.tier: p for p in grid_engine.positions}
    assert 1 in tier_positions, "Tier 1 position missing"
    assert 2 in tier_positions, "Tier 2 position missing"
    assert 3 in tier_positions, "Tier 3 position missing"

    # 검증 3: 총 수량이 300주여야 함
    total_qty = sum(p.quantity for p in grid_engine.positions)
    assert total_qty == 300, f"Expected total quantity 300, got {total_qty}"

    print(f"✅ execute_buy 배치 처리 테스트 성공:")
    print(f"   - 생성된 포지션 수: {len(grid_engine.positions) - initial_position_count}")
    print(f"   - 총 수량: {total_qty}주")


def test_execute_sell_batch(grid_engine):
    """
    execute_sell에서 배치 신호를 처리할 수 있는지 테스트

    검증:
    - 배치 신호로 execute_sell 호출 시 여러 포지션이 제거되는지 확인
    """
    from src.models import TradeSignal

    # 포지션 생성
    pos1 = Position(tier=1, quantity=100, avg_price=100.0,
                    invested_amount=10000.0, opened_at=datetime.now())
    pos2 = Position(tier=2, quantity=100, avg_price=99.5,
                    invested_amount=9950.0, opened_at=datetime.now())
    pos3 = Position(tier=3, quantity=100, avg_price=99.0,
                    invested_amount=9900.0, opened_at=datetime.now())

    grid_engine.positions = [pos1, pos2, pos3]
    initial_position_count = 3

    # 배치 매도 신호 생성
    batch_signal = TradeSignal(
        action="SELL",
        tier=1,
        tiers=(1, 2, 3),
        price=105.0,
        quantity=300,  # 총 300주
        reason="배치 매도 테스트"
    )

    # 초기 잔고
    initial_balance = grid_engine.account_balance

    # 매도 실행
    profit = grid_engine.execute_sell(batch_signal)

    # 검증 1: 모든 포지션이 제거되어야 함
    assert len(grid_engine.positions) == 0, \
        f"Expected 0 positions, got {len(grid_engine.positions)}"

    # 검증 2: 잔고가 증가해야 함
    expected_balance = initial_balance + (105.0 * 300)
    assert grid_engine.account_balance == expected_balance, \
        f"Expected balance {expected_balance}, got {grid_engine.account_balance}"

    # 검증 3: 수익이 계산되어야 함
    expected_profit = (105.0 * 300) - (10000.0 + 9950.0 + 9900.0)
    assert profit == expected_profit, \
        f"Expected profit {expected_profit}, got {profit}"

    print(f"✅ execute_sell 배치 처리 테스트 성공:")
    print(f"   - 제거된 포지션 수: {initial_position_count}")
    print(f"   - 수익: ${profit:.2f}")


if __name__ == "__main__":
    # 수동 실행용
    print("="*60)
    print("배치 주문 로직 테스트 시작")
    print("="*60)

    engine = grid_engine()

    print("\n[Test 1] 배치 매수 (급락 시나리오)")
    print("-"*60)
    test_batch_buy_gap_down(engine)

    print("\n[Test 2] 배치 매도 (급등 시나리오)")
    print("-"*60)
    engine2 = grid_engine()
    test_batch_sell_gap_up(engine2)

    print("\n[Test 3] execute_buy 배치 처리")
    print("-"*60)
    engine3 = grid_engine()
    test_execute_buy_batch(engine3)

    print("\n[Test 4] execute_sell 배치 처리")
    print("-"*60)
    engine4 = grid_engine()
    test_execute_sell_batch(engine4)

    print("\n" + "="*60)
    print("모든 테스트 성공!")
    print("="*60)
