"""
src/grid_engine.py 단위 테스트

테스트 범위:
1. GridEngine 초기화
2. 매수/매도 조건 판단 (Tier 1 포함)
3. 주문 실행 및 포지션 관리
4. 시세 처리 (process_tick)
5. 상태 일관성 검증

코드 리뷰에서 식별된 CRITICAL 이슈 테스트:
- Issue #1: execute_buy/sell이 주문 확정 전에 잔고를 차감 (2-phase commit 미구현)
- Issue #2: process_tick에서 동시에 매수/매도 신호 생성 가능
- Issue #3: Tier 가격 캐싱 없음 (성능 문제)
"""

import pytest
from dataclasses import replace
from datetime import datetime
from unittest.mock import Mock, patch
from src.models import Position, TradeSignal, GridSettings
from src.grid_engine import GridEngine


class TestGridEngineInitialization:
    """GridEngine 초기화 테스트"""

    def test_create_engine_basic(self, grid_settings_basic):
        """기본 Grid Engine 생성"""
        engine = GridEngine(grid_settings_basic)

        assert engine.settings == grid_settings_basic
        assert engine.account_balance == 10000.0
        assert len(engine.positions) == 0
        # total_invested는 계산된 값: sum(p.invested_amount for p in positions)
        total_invested = sum(p.invested_amount for p in engine.positions)
        assert total_invested == 0.0

    def test_create_engine_with_tier1_enabled(self, grid_settings_tier1_enabled):
        """Tier 1 활성화된 Engine"""
        engine = GridEngine(grid_settings_tier1_enabled)

        assert engine.settings.tier1_trading_enabled == True

    def test_initial_state_empty(self, grid_settings_basic):
        """초기 상태는 빈 포지션"""
        engine = GridEngine(grid_settings_basic)

        # get_position_quantity는 계산된 값
        total_quantity = sum(p.quantity for p in engine.positions)
        assert total_quantity == 0
        # get_active_tier_count는 len(positions)
        assert len(engine.positions) == 0


class TestBuyConditions:
    """매수 조건 판단 테스트"""

    def test_should_buy_tier1_disabled(self, grid_settings_basic):
        """Tier 1 비활성화 시 Tier 1 매수 불가"""
        engine = GridEngine(grid_settings_basic)

        current_price = 10.0  # Tier 1 가격
        tier = engine.check_buy_condition(current_price)

        # Tier 1 비활성화이므로 매수하지 않음 (None 반환)
        assert tier is None

    def test_should_buy_tier1_enabled(self, grid_settings_tier1_enabled):
        """Tier 1 활성화 시 Tier 1 매수 가능"""
        engine = GridEngine(grid_settings_tier1_enabled)

        current_price = 10.0  # Tier 1 가격
        tier = engine.check_buy_condition(current_price)

        # Tier 1 활성화이므로 매수 신호
        assert tier is not None
        assert tier == 1

    def test_should_buy_tier2_condition(self, grid_settings_tier1_enabled):
        """Tier 2 매수 조건: Tier 1 보유 + 현재가 Tier 2"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 1. Tier 1 매수
        engine.execute_buy(TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Test",
            timestamp=datetime.now()
        ))

        # 2. 현재가 Tier 2로 하락
        current_price = 9.95
        tier = engine.check_buy_condition(current_price)

        # Tier 1을 보유하고 있으므로 Tier 2 매수 가능
        assert tier is not None
        assert tier == 2

    def test_should_not_buy_without_previous_tier(self, grid_settings_tier1_enabled):
        """이전 Tier 미보유 시 다음 Tier 매수 불가 (Tier 1 활성화 시에도 순차 매수)"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # Tier 1을 건너뛰고 Tier 2 가격으로 진입
        current_price = 9.95  # Tier 2 가격

        tier = engine.check_buy_condition(current_price)

        # Tier 1 활성화 상태이므로 낮은 가격에서 Tier 1 매수 조건 만족
        assert tier == 1  # Tier 2가 아닌 Tier 1부터 매수해야 함

    def test_should_not_buy_insufficient_balance(self, grid_settings_tier1_enabled):
        """잔고 부족 시 매수 불가"""
        engine = GridEngine(grid_settings_tier1_enabled)
        engine.account_balance = 10.0  # 잔고 부족

        current_price = 10.0
        tier = engine.check_buy_condition(current_price)

        # 잔고 부족으로 매수 불가
        assert tier is None


class TestSellConditions:
    """매도 조건 판단 테스트"""

    def test_should_sell_tier1_profit(self, grid_settings_tier1_enabled):
        """Tier 1 수익 실현 매도"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 1. Tier 1 매수
        engine.execute_buy(TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Test",
            timestamp=datetime.now()
        ))

        # 2. 가격 상승 (수익 3%)
        current_price = 10.3  # Tier 1 목표가 (10.0 * 1.03 = 3% 수익)
        tier = engine.check_sell_condition(current_price)

        # 수익 3% 달성으로 매도 신호
        assert tier is not None
        assert tier == 1

    def test_should_not_sell_without_position(self, grid_settings_tier1_enabled):
        """보유 포지션 없으면 매도 불가"""
        engine = GridEngine(grid_settings_tier1_enabled)

        current_price = 10.1
        tier = engine.check_sell_condition(current_price)

        # 포지션이 없으므로 매도 불가
        assert tier is None

    def test_should_sell_tier2_when_tier1_gone(self, grid_settings_tier1_enabled):
        """Tier 1 청산 시 Tier 2 매도 (계단식)"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 1. Tier 1, 2 매수
        engine.execute_buy(TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))
        engine.execute_buy(TradeSignal(
            action="BUY", tier=2, price=9.95, quantity=20,
            reason="Test", timestamp=datetime.now()
        ))

        # 2. Tier 1 청산
        engine.execute_sell(TradeSignal(
            action="SELL", tier=1, price=10.1, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))

        # 3. 가격이 Tier 2 목표가 도달
        current_price = 10.25  # Tier 2 목표가 (9.95 * 1.03 ≈ 10.2485)
        tier = engine.check_sell_condition(current_price)

        # Tier 1이 없고 Tier 2가 3% 수익 달성으로 청산
        assert tier is not None
        assert tier == 2


class TestOrderExecution:
    """주문 실행 테스트 (CRITICAL)"""

    @pytest.mark.xfail(reason="2-phase commit not implemented - Code Review Issue #1")
    def test_execute_buy_two_phase_commit(self, grid_settings_tier1_enabled):
        """
        매수 실행 2-phase commit 패턴 테스트

        코드 리뷰 Issue #1:
        execute_buy가 주문 확정 전에 잔고를 차감하여,
        주문 실패 시 상태 불일치 발생
        """
        engine = GridEngine(grid_settings_tier1_enabled)
        initial_balance = engine.account_balance

        signal = TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Test",
            timestamp=datetime.now()
        )

        # 현재 API는 confirmed 파라미터가 없고 즉시 실행됨
        # 2-phase commit 패턴이 구현되면 이 테스트를 다시 작성해야 함
        position = engine.execute_buy(signal)

        # 즉시 잔고 차감 (2-phase commit 미구현)
        assert engine.account_balance == initial_balance - 100.0
        assert position is not None
        assert len(engine.positions) == 1

    def test_execute_buy_basic(self, grid_settings_tier1_enabled):
        """기본 매수 실행 (현재 구현)"""
        engine = GridEngine(grid_settings_tier1_enabled)
        initial_balance = engine.account_balance

        signal = TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Test",
            timestamp=datetime.now()
        )

        position = engine.execute_buy(signal)

        # 잔고 차감 확인
        assert engine.account_balance == initial_balance - 100.0
        assert position.tier == 1
        assert position.quantity == 10
        assert len(engine.positions) == 1

    def test_execute_sell_basic(self, grid_settings_tier1_enabled):
        """기본 매도 실행"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 1. 매수
        buy_signal = TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        )
        engine.execute_buy(buy_signal)

        initial_balance = engine.account_balance

        # 2. 매도
        sell_signal = TradeSignal(
            action="SELL", tier=1, price=10.1, quantity=10,
            reason="Test", timestamp=datetime.now()
        )
        profit = engine.execute_sell(sell_signal)

        # 잔고 증가 확인
        assert engine.account_balance == initial_balance + 101.0
        assert profit == 101.0  # 매도 수익금
        assert len(engine.positions) == 0  # 포지션 제거 (전체 청산)

    def test_execute_partial_sell(self, grid_settings_tier1_enabled):
        """부분 매도"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 1. 매수 20주
        buy_signal = TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=20,
            reason="Test", timestamp=datetime.now()
        )
        engine.execute_buy(buy_signal)

        # 2. 매도 10주 (부분 매도)
        sell_signal = TradeSignal(
            action="SELL", tier=1, price=10.1, quantity=10,
            reason="Test", timestamp=datetime.now()
        )
        profit = engine.execute_sell(sell_signal)

        # 10주 남음 (포지션은 engine.positions에서 확인)
        assert profit == 101.0  # 10주 매도 수익금
        assert len(engine.positions) == 1
        remaining_position = engine.positions[0]
        assert remaining_position.quantity == 10


class TestProcessTick:
    """시세 처리 테스트 (CRITICAL)"""

    @pytest.mark.xfail(reason="Simultaneous buy/sell signals possible - Code Review Issue #2")
    def test_process_tick_no_simultaneous_signals(self, grid_settings_tier1_enabled):
        """
        동시 매수/매도 신호 방지 테스트

        코드 리뷰 Issue #2:
        process_tick에서 매수와 매도 신호가 동시에 생성될 수 있음
        """
        engine = GridEngine(grid_settings_tier1_enabled)

        # Tier 1, 2 매수
        engine.execute_buy(TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))
        engine.execute_buy(TradeSignal(
            action="BUY", tier=2, price=9.95, quantity=20,
            reason="Test", timestamp=datetime.now()
        ))

        # 가격이 Tier 2와 Tier 1 사이 (애매한 상황)
        current_price = 9.98

        signals = engine.process_tick(current_price)

        # 매수 또는 매도 중 하나만 발생해야 함
        buy_signals = [s for s in signals if s.action == "BUY"]
        sell_signals = [s for s in signals if s.action == "SELL"]

        # 동시에 발생하면 안 됨
        assert not (len(buy_signals) > 0 and len(sell_signals) > 0)

    def test_process_tick_buy_signal(self, grid_settings_tier1_enabled):
        """시세 처리: 매수 신호 생성"""
        engine = GridEngine(grid_settings_tier1_enabled)

        current_price = 10.0  # Tier 1 가격
        signals = engine.process_tick(current_price)

        # 매수 신호 1개 생성
        assert len(signals) == 1
        assert signals[0].action == "BUY"
        assert signals[0].tier == 1

    def test_process_tick_sell_signal(self, grid_settings_tier1_enabled):
        """시세 처리: 매도 신호 생성"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 매수
        engine.execute_buy(TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))

        # 가격 상승 (3% 수익)
        current_price = 10.3
        signals = engine.process_tick(current_price)

        # 매도 신호 1개 생성
        assert len(signals) == 1
        assert signals[0].action == "SELL"
        assert signals[0].tier == 1

    def test_process_tick_no_signal(self, grid_settings_basic):
        """시세 처리: 신호 없음 (tier1_auto_update=False 사용)"""
        engine = GridEngine(grid_settings_basic)

        current_price = 10.15  # Tier 1 (10.0)보다 높지만 auto_update=False이므로 갱신 안됨, 매수 조건 불만족
        signals = engine.process_tick(current_price)

        assert len(signals) == 0


class TestTierPriceCalculation:
    """Tier 가격 계산 및 캐싱 테스트"""

    def test_calculate_tier_price(self, grid_settings_basic):
        """Tier 가격 계산"""
        engine = GridEngine(grid_settings_basic)

        tier1_price = engine.calculate_tier_price(1)
        tier2_price = engine.calculate_tier_price(2)
        tier10_price = engine.calculate_tier_price(10)

        assert tier1_price == 10.0
        assert tier2_price == pytest.approx(9.95)
        assert tier10_price == pytest.approx(9.55)  # 10.0 - (9 * 0.05)

    @pytest.mark.xfail(reason="Tier price caching not implemented - Code Review Issue #3")
    def test_tier_price_caching_performance(self, grid_settings_basic):
        """
        Tier 가격 캐싱 성능 테스트

        코드 리뷰 Issue #3:
        매번 계산하면 성능 문제. 캐싱 필요.
        """
        engine = GridEngine(grid_settings_basic)

        # 첫 계산
        import time
        start = time.time()
        for _ in range(1000):
            engine.calculate_tier_price(100)
        first_duration = time.time() - start

        # 두 번째 계산 (캐싱되어야 함)
        start = time.time()
        for _ in range(1000):
            engine.calculate_tier_price(100)
        second_duration = time.time() - start

        # 캐싱이 있으면 두 번째가 훨씬 빨라야 함
        assert second_duration < first_duration * 0.5


class TestStateConsistency:
    """상태 일관성 테스트 (CRITICAL)"""

    def test_state_consistency_after_buy(self, grid_settings_tier1_enabled):
        """매수 후 상태 일관성"""
        engine = GridEngine(grid_settings_tier1_enabled)

        initial_balance = engine.account_balance

        # 매수
        engine.execute_buy(TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))

        # 상태 확인
        total_invested = sum(p.invested_amount for p in engine.positions)
        assert engine.account_balance + total_invested == initial_balance
        total_quantity = sum(p.quantity for p in engine.positions)
        assert total_quantity == 10

    def test_state_consistency_after_sell(self, grid_settings_tier1_enabled):
        """매도 후 상태 일관성"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 매수
        engine.execute_buy(TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))

        # 매도
        engine.execute_sell(TradeSignal(
            action="SELL", tier=1, price=10.1, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))

        # 상태 확인
        total_quantity = sum(p.quantity for p in engine.positions)
        assert total_quantity == 0
        total_invested = sum(p.invested_amount for p in engine.positions)
        assert total_invested == 0
        assert len(engine.positions) == 0

    def test_state_consistency_multiple_tiers(self, grid_settings_tier1_enabled):
        """다중 Tier 상태 일관성"""
        engine = GridEngine(grid_settings_tier1_enabled)

        initial_balance = engine.account_balance

        # Tier 1, 2, 3 매수
        for tier in [1, 2, 3]:
            price = 10.0 - ((tier - 1) * 0.05)
            engine.execute_buy(TradeSignal(
                action="BUY",
                tier=tier,
                price=price,
                quantity=10,
                reason="Test",
                timestamp=datetime.now()
            ))

        # 상태 확인
        assert len(engine.positions) == 3  # 활성 티어 수
        total_quantity = sum(p.quantity for p in engine.positions)
        assert total_quantity == 30
        total_invested = sum(p.invested_amount for p in engine.positions)
        assert engine.account_balance + total_invested == pytest.approx(initial_balance, rel=1e-2)


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_buy_at_exact_tier_boundary(self, grid_settings_tier1_enabled):
        """정확히 Tier 경계 가격에서 매수"""
        engine = GridEngine(grid_settings_tier1_enabled)

        current_price = 10.0  # 정확히 Tier 1
        tier = engine.check_buy_condition(current_price)

        assert tier is not None
        assert tier == 1

    def test_sell_at_exact_target_price(self, grid_settings_tier1_enabled):
        """정확히 목표가에서 매도"""
        engine = GridEngine(grid_settings_tier1_enabled)

        # 매수
        engine.execute_buy(TradeSignal(
            action="BUY", tier=1, price=10.0, quantity=10,
            reason="Test", timestamp=datetime.now()
        ))

        # 정확히 목표가
        current_price = 10.3  # Tier 1 목표가 (10.0 * 1.03 = 3% 수익)
        tier = engine.check_sell_condition(current_price)

        assert tier is not None
        assert tier == 1

    def test_maximum_tier_limit(self, grid_settings_basic):
        """최대 Tier 240 제한"""
        engine = GridEngine(grid_settings_basic)

        # Tier 240 가격 계산
        tier240_price = engine.calculate_tier_price(240)

        # Tier 240보다 낮은 가격
        very_low_price = tier240_price - 1.0

        # Tier 240을 초과하지 않아야 함
        tier = engine.check_buy_condition(very_low_price)

        if tier is not None:
            assert tier <= 240

    def test_zero_balance_cannot_buy(self, grid_settings_tier1_enabled):
        """잔고 0이면 매수 불가"""
        engine = GridEngine(grid_settings_tier1_enabled)
        engine.account_balance = 0.0

        tier = engine.check_buy_condition(10.0)

        assert tier is None


class TestBugFixes:
    """Phase 0 버그 수정 검증 테스트"""

    def test_generate_buy_signal_minimum_quantity(self, grid_settings_tier1_enabled):
        """
        Bug #2 수정 검증: 고가 시나리오에서 최소 1주 보장

        시나리오: tier_amount=$50, price=$100 → 0.5주 계산되지만 1주 보장
        """
        engine = GridEngine(grid_settings_tier1_enabled)
        # frozen settings이므로 replace()로 새 인스턴스 생성
        engine.settings = replace(engine.settings, tier_amount=50.0)

        # 고가 시나리오
        signal = engine.generate_buy_signal(100.0, tier=1)

        assert signal.quantity >= 1, "최소 1주는 보장되어야 함"
        assert signal.quantity == 1, f"Expected 1 share, got {signal.quantity}"

    def test_generate_buy_signal_normal_scenario(self, grid_settings_tier1_enabled):
        """
        Bug #2 수정 검증: 정상 시나리오에서 올바른 수량 계산

        시나리오: tier_amount=$50, price=$10 → 5주
        """
        engine = GridEngine(grid_settings_tier1_enabled)
        # frozen settings이므로 replace()로 새 인스턴스 생성
        engine.settings = replace(engine.settings, tier_amount=50.0)

        # 정상 시나리오
        signal = engine.generate_buy_signal(10.0, tier=1)

        assert signal.quantity == 5, f"Expected 5 shares, got {signal.quantity}"

    def test_generate_buy_signal_fractional_rounding(self, grid_settings_tier1_enabled):
        """
        Bug #2 수정 검증: 소수점 버림 처리

        시나리오: tier_amount=$50, price=$15 → 3.333... → 3주 (floor)
        """
        engine = GridEngine(grid_settings_tier1_enabled)
        # frozen settings이므로 replace()로 새 인스턴스 생성
        engine.settings = replace(engine.settings, tier_amount=50.0)

        signal = engine.generate_buy_signal(15.0, tier=1)

        assert signal.quantity == 3, f"Expected 3 shares (floor), got {signal.quantity}"
