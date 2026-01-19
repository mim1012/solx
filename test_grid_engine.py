"""
Phoenix Grid Engine 테스트 스크립트
GridEngine 클래스의 기본 동작 검증
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models import GridSettings
from src.grid_engine import GridEngine


def test_basic_grid_logic():
    """기본 그리드 로직 테스트"""
    print("=" * 70)
    print("Phoenix Grid Engine 테스트 - 기본 모드")
    print("=" * 70)
    print()

    # 설정 생성
    settings = GridSettings(
        account_no="1234567890",
        ticker="SOXL",
        investment_usd=10000.0,
        total_tiers=240,
        tier_amount=500.0,
        tier1_auto_update=True,
        tier1_trading_enabled=False,  # Tier 1 거래 OFF
        tier1_buy_percent=0.0,
        buy_limit=False,
        sell_limit=False
    )

    # GridEngine 초기화
    engine = GridEngine(settings)
    print(f"[OK] GridEngine 초기화 완료")
    print(f"  - 종목: {settings.ticker}")
    print(f"  - 투자금: ${settings.investment_usd:.2f}")
    print(f"  - Tier 1 거래: {'활성화' if settings.tier1_trading_enabled else '비활성화'}")
    print()

    # Tier 1 가격 설정
    initial_price = 50.0
    engine.tier1_price = initial_price
    print(f"[설정] Tier 1 가격: ${initial_price:.2f}")
    print()

    # 시나리오 1: 가격 하락 → Tier 2 매수
    print("--- 시나리오 1: 가격 하락 (Tier 1 거래 OFF) ---")
    current_price = 49.75  # Tier 1 - 0.5%
    print(f"현재가: ${current_price:.2f}")

    buy_tier = engine.check_buy_condition(current_price)
    if buy_tier:
        print(f"✅ 매수 조건 충족: Tier {buy_tier}")
        signal = engine.generate_buy_signal(current_price, buy_tier)
        print(f"  - 매수가: ${signal.price:.2f}")
        print(f"  - 수량: {signal.quantity}주")
        print(f"  - 투자금: ${signal.price * signal.quantity:.2f}")

        # 매수 실행
        position = engine.execute_buy(signal)
        print(f"  - 포지션 생성: Tier {position.tier}")
    else:
        print("❌ 매수 조건 미충족")
    print()

    # 시나리오 2: 가격 상승 → 매도
    print("--- 시나리오 2: 가격 상승 (3% 익절) ---")
    current_price = 51.24  # 3% 상승
    print(f"현재가: ${current_price:.2f}")

    sell_tier = engine.check_sell_condition(current_price)
    if sell_tier:
        print(f"✅ 매도 조건 충족: Tier {sell_tier}")
        signal = engine.generate_sell_signal(current_price, sell_tier)
        print(f"  - 매도가: ${signal.price:.2f}")
        print(f"  - 수량: {signal.quantity}주")
        print(f"  - 매도금: ${signal.price * signal.quantity:.2f}")

        # 매도 실행
        profit = engine.execute_sell(signal)
        print(f"  - 수익금: ${profit:.2f}")
    else:
        print("❌ 매도 조건 미충족")
    print()

    # 상태 조회
    print("--- 최종 상태 ---")
    state = engine.get_system_state(current_price)
    print(f"현재 티어: {state.current_tier}")
    print(f"보유 포지션: {len(engine.positions)}개")
    print(f"계좌 잔고: ${state.account_balance:.2f}")
    print(f"총 수익: ${state.total_profit:.2f} ({state.profit_rate:+.2%})")
    print()


def test_tier1_trading():
    """Tier 1 거래 기능 테스트"""
    print("=" * 70)
    print("Phoenix Grid Engine 테스트 - Tier 1 거래 모드")
    print("=" * 70)
    print()

    # 설정 생성 (Tier 1 거래 활성화)
    settings = GridSettings(
        account_no="1234567890",
        ticker="SOXL",
        investment_usd=10000.0,
        total_tiers=240,
        tier_amount=500.0,
        tier1_auto_update=True,
        tier1_trading_enabled=True,   # Tier 1 거래 ON
        tier1_buy_percent=0.0,         # 정확히 일치
        buy_limit=False,
        sell_limit=False
    )

    # GridEngine 초기화
    engine = GridEngine(settings)
    print(f"[OK] GridEngine 초기화 완료")
    print(f"  - Tier 1 거래: 활성화")
    print(f"  - Tier 1 매수%: {settings.tier1_buy_percent:+.2%}")
    print()

    # Tier 1 가격 설정
    initial_price = 50.0
    engine.tier1_price = initial_price
    print(f"[설정] Tier 1 가격: ${initial_price:.2f}")
    print()

    # 시나리오: Tier 1 정확히 일치 → 매수
    print("--- 시나리오: Tier 1 가격에서 매수 (거래 모드 ON) ---")
    current_price = 50.0
    print(f"현재가: ${current_price:.2f}")

    buy_tier = engine.check_buy_condition(current_price)
    if buy_tier:
        print(f"✅ 매수 조건 충족: Tier {buy_tier}")
        if buy_tier == 1:
            print("  - [CUSTOM] Tier 1 매수 실행!")

        signal = engine.generate_buy_signal(current_price, buy_tier)
        print(f"  - 매수가: ${signal.price:.2f}")
        print(f"  - 수량: {signal.quantity}주")

        # 매수 실행
        position = engine.execute_buy(signal)
        print(f"  - 포지션 생성: Tier {position.tier}")
    else:
        print("❌ 매수 조건 미충족")
    print()

    # 상태 조회
    print("--- 최종 상태 ---")
    state = engine.get_system_state(current_price)
    print(f"보유 포지션: {len(engine.positions)}개")
    if engine.positions:
        for pos in engine.positions:
            print(f"  - Tier {pos.tier}: {pos.quantity}주 @ ${pos.avg_price:.2f}")
    print()


def main():
    """메인 테스트 함수"""
    try:
        # 테스트 1: 기본 그리드 로직
        test_basic_grid_logic()

        # 테스트 2: Tier 1 거래 기능
        test_tier1_trading()

        print("=" * 70)
        print("✅ 모든 테스트 완료")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
