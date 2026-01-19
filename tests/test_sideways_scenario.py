"""
횡보 시나리오 테스트: Tier 4~10 구간에서 반복 매매

시나리오:
1. Tier 1 ($10.00)에서 시작
2. 가격 하락하여 Tier 4~10 진입
3. 이 구간에서 횡보 (반복 매수/매도)
4. 각 Tier의 독립적인 거래 검증
"""

import pytest
from datetime import datetime
from src.models import GridSettings
from src.grid_engine import GridEngine


class TestSidewaysScenario:
    """횡보 구간 시나리오 테스트"""

    @pytest.fixture
    def engine(self):
        """테스트용 GridEngine 생성 (Tier 1 비활성화)"""
        settings = GridSettings(
            account_no="12345678",
            ticker="SOXL",
            investment_usd=10000.0,
            total_tiers=240,
            tier_amount=50.0,
            tier1_auto_update=False,
            tier1_trading_enabled=False,  # Tier 1 비활성화 (Tier 2부터 거래)
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=False,
            telegram_enabled=False,
            seed_ratio=0.05,
            buy_interval=0.005,
            sell_target=0.03
        )
        engine = GridEngine(settings)
        engine.tier1_price = 10.00  # Tier 1 고정
        return engine

    def test_tier4_rebuy_after_sell(self, engine):
        """
        Tier 4 재매수 시나리오

        1. Tier 4 ($9.85) 매수
        2. 목표가 도달 → 매도
        3. 다시 Tier 4로 하락 → 재매수 가능 확인
        """
        # Step 1: Tier 4 매수
        buy_tier = engine.check_buy_condition(9.85)
        assert buy_tier == 4, f"Tier 4 매수 조건 충족해야 함, got {buy_tier}"

        signal = engine.generate_buy_signal(9.85, buy_tier)
        engine.execute_buy(signal)

        # Tier 4 포지션 1개
        assert len(engine.positions) == 1
        assert engine.positions[0].tier == 4

        # Step 2: Tier 4 목표가 도달 (3% 수익)
        target_price = 9.85 * 1.03  # $10.1455
        sell_tier = engine.check_sell_condition(target_price)
        assert sell_tier == 4, f"Tier 4 매도 조건 충족해야 함, got {sell_tier}"

        sell_signal = engine.generate_sell_signal(target_price, sell_tier)
        profit = engine.execute_sell(sell_signal)

        # 매도 후 포지션 0개
        assert len(engine.positions) == 0, "매도 후 포지션 제거되어야 함"
        assert profit > 0, "수익 발생해야 함"

        # Step 3: 재매수 가능 확인
        rebuy_tier = engine.check_buy_condition(9.85)
        assert rebuy_tier == 4, f"Tier 4 재매수 가능해야 함, got {rebuy_tier}"

    def test_multiple_tiers_independent_trading(self, engine):
        """
        여러 Tier 독립 거래 시나리오

        1. Tier 4, 5, 6, 7 순차 매수
        2. Tier 7 목표가 도달 → Tier 7만 매도
        3. Tier 4, 5, 6은 유지
        4. Tier 6 목표가 도달 → Tier 6만 매도
        """
        # Step 1: Tier 4~7 순차 매수
        for tier_price in [9.85, 9.80, 9.75, 9.70]:  # Tier 4, 5, 6, 7
            buy_tier = engine.check_buy_condition(tier_price)
            assert buy_tier is not None

            signal = engine.generate_buy_signal(tier_price, buy_tier)
            engine.execute_buy(signal)

        assert len(engine.positions) == 4, "4개 포지션 보유해야 함"

        # Step 2: Tier 7 목표가 도달 ($9.70 × 1.03 = $9.991)
        sell_tier = engine.check_sell_condition(10.00)
        assert sell_tier == 7, "Tier 7이 가장 높은 Tier이므로 먼저 매도"

        sell_signal = engine.generate_sell_signal(10.00, sell_tier)
        engine.execute_sell(sell_signal)

        assert len(engine.positions) == 3, "Tier 7 매도 후 3개 포지션"
        assert all(p.tier != 7 for p in engine.positions), "Tier 7 포지션 제거됨"

        # Step 3: Tier 6 목표가 도달 ($9.75 × 1.03 = $10.0425)
        sell_tier = engine.check_sell_condition(10.05)
        assert sell_tier == 6, "Tier 6이 현재 가장 높은 Tier"

        sell_signal = engine.generate_sell_signal(10.05, sell_tier)
        engine.execute_sell(sell_signal)

        assert len(engine.positions) == 2, "Tier 6 매도 후 2개 포지션"

    def test_sideways_profit_accumulation(self, engine):
        """
        횡보 구간 수익 누적 시나리오

        Tier 5에서 3회 반복 매매 → 수익 누적 확인
        """
        initial_balance = engine.account_balance
        total_profit = 0.0

        # 3회 반복
        for i in range(3):
            # 매수
            buy_tier = engine.check_buy_condition(9.80)  # Tier 5
            assert buy_tier == 5, f"반복 {i+1}: Tier 5 매수 가능"

            signal = engine.generate_buy_signal(9.80, buy_tier)
            engine.execute_buy(signal)

            # 매도
            target_price = 9.80 * 1.03
            sell_tier = engine.check_sell_condition(target_price)
            assert sell_tier == 5

            sell_signal = engine.generate_sell_signal(target_price, sell_tier)
            profit = engine.execute_sell(sell_signal)

            total_profit += profit

        # 잔고 증가 확인
        final_balance = engine.account_balance
        assert final_balance > initial_balance, "잔고가 증가해야 함"
        assert abs((final_balance - initial_balance) - total_profit) < 0.01, "수익이 잔고에 반영됨"

    def test_process_tick_sell_priority(self, engine):
        """
        process_tick()에서 매도 우선순위 확인

        매수와 매도 조건이 동시에 충족되면 매도가 우선
        """
        # Tier 5 매수
        signal = engine.generate_buy_signal(9.80, 5)
        engine.execute_buy(signal)

        # 목표가 도달 + Tier 6 매수 조건 동시 충족
        signals = engine.process_tick(9.75 * 1.03)  # Tier 5 목표가이면서 Tier 6 가격보다 높음

        # 매도 신호가 먼저 나와야 함
        assert len(signals) >= 1, "최소 1개 신호 발생"
        assert signals[0].action == "SELL", "매도가 우선순위"
        assert signals[0].tier == 5, "Tier 5 매도"

    def test_no_rebuy_while_holding(self, engine):
        """
        포지션 보유 중에는 같은 Tier 재매수 불가

        Tier 5 보유 중 → Tier 5 재매수 시도 → 불가
        """
        # Tier 5 매수
        signal = engine.generate_buy_signal(9.80, 5)
        engine.execute_buy(signal)

        assert len(engine.positions) == 1

        # Tier 5 재매수 시도
        rebuy_tier = engine.check_buy_condition(9.80)

        # Tier 5는 이미 보유 중이므로 다른 Tier로 넘어감
        if rebuy_tier is not None:
            assert rebuy_tier != 5, "이미 보유 중인 Tier는 재매수 불가"


class TestSidewaysEdgeCases:
    """횡보 구간 엣지 케이스"""

    @pytest.fixture
    def engine(self):
        settings = GridSettings(
            account_no="12345678",
            ticker="SOXL",
            investment_usd=10000.0,
            total_tiers=240,
            tier_amount=50.0,
            tier1_auto_update=False,
            tier1_trading_enabled=True,
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=False,
            telegram_enabled=False,
            seed_ratio=0.05,
            buy_interval=0.005,
            sell_target=0.03
        )
        engine = GridEngine(settings)
        engine.tier1_price = 10.00
        return engine

    def test_insufficient_balance_prevents_rebuy(self, engine):
        """
        잔고 부족 시 재매수 불가

        Tier 5 반복 매매 → 잔고 소진 → 재매수 불가
        """
        # 잔고를 거의 소진
        engine.account_balance = 40.0  # Tier amount ($50) 미만

        buy_tier = engine.check_buy_condition(9.80)
        assert buy_tier is None, "잔고 부족으로 매수 불가"

    def test_buy_limit_prevents_rebuy(self, engine):
        """
        매수 제한 스위치 활성화 시 재매수 불가
        """
        engine.settings.buy_limit = True

        buy_tier = engine.check_buy_condition(9.80)
        assert buy_tier is None, "매수 제한으로 매수 불가"

    def test_sell_limit_prevents_sell(self, engine):
        """
        매도 제한 스위치 활성화 시 매도 불가
        """
        # Tier 5 매수
        signal = engine.generate_buy_signal(9.80, 5)
        engine.execute_buy(signal)

        # 매도 제한 활성화
        engine.settings.sell_limit = True

        # 목표가 도달해도 매도 불가
        sell_tier = engine.check_sell_condition(9.80 * 1.03)
        assert sell_tier is None, "매도 제한으로 매도 불가"
