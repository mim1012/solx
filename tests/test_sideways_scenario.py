"""
횡보 시나리오 테스트: Tier 구간에서 반복 매매

시나리오:
1. Tier 1 ($10.00)에서 시작
2. 가격 하락하여 특정 Tier 진입
3. 이 구간에서 횡보 (반복 매수/매도)
4. 각 Tier의 독립적인 거래 검증

Tier 가격 계산 (buy_interval=0.5%):
- Tier 1: $10.00
- Tier 2: $9.95 (10.00 * 0.995)
- Tier 3: $9.90 (10.00 * 0.990)
- Tier 4: $9.85 (10.00 * 0.985)
- Tier 5: $9.80 (10.00 * 0.980)
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

    def test_tier2_rebuy_after_sell(self, engine):
        """
        Tier 2 재매수 시나리오

        1. Tier 2 ($9.95) 매수
        2. 목표가 도달 → 매도
        3. 다시 Tier 2로 하락 → 재매수 가능 확인
        """
        # Step 1: Tier 2 매수 (가격 $9.95 이하)
        buy_price = 9.94  # Tier 2 가격 ($9.95) 이하
        buy_tier = engine.check_buy_condition(buy_price)
        assert buy_tier == 2, f"Tier 2 매수 조건 충족해야 함, got {buy_tier}"

        signal = engine.generate_buy_signal(buy_price, buy_tier)
        engine.execute_buy(signal)

        # Tier 2 포지션 1개
        assert len(engine.positions) == 1
        assert engine.positions[0].tier == 2

        # Step 2: Tier 2 목표가 도달 (3% 수익)
        # Tier 2 매도가 = $9.95 * 1.03 = $10.2485
        target_price = 10.25
        sell_tier = engine.check_sell_condition(target_price)
        assert sell_tier == 2, f"Tier 2 매도 조건 충족해야 함, got {sell_tier}"

        sell_signal = engine.generate_sell_signal(target_price, sell_tier)
        profit = engine.execute_sell(sell_signal)

        # 매도 후 포지션 0개
        assert len(engine.positions) == 0, "매도 후 포지션 제거되어야 함"
        assert profit > 0, "수익 발생해야 함"

        # Step 3: 재매수 가능 확인
        rebuy_tier = engine.check_buy_condition(9.94)
        assert rebuy_tier == 2, f"Tier 2 재매수 가능해야 함, got {rebuy_tier}"

    def test_multiple_tiers_sequential_buy(self, engine):
        """
        여러 Tier 순차 매수 시나리오

        check_buy_condition은 낮은 Tier부터 순회하므로
        가격이 하락하면 이미 보유하지 않은 가장 낮은 Tier를 반환
        """
        # Tier 2 매수 ($9.94)
        buy_tier = engine.check_buy_condition(9.94)
        assert buy_tier == 2
        signal = engine.generate_buy_signal(9.94, buy_tier)
        engine.execute_buy(signal)
        assert len(engine.positions) == 1

        # 가격 더 하락 → Tier 3 매수 ($9.89)
        # Tier 2 이미 보유 중이므로 Tier 3 반환
        buy_tier = engine.check_buy_condition(9.89)
        assert buy_tier == 3, f"Tier 3 매수 조건 충족해야 함, got {buy_tier}"
        signal = engine.generate_buy_signal(9.89, buy_tier)
        engine.execute_buy(signal)
        assert len(engine.positions) == 2

        # 가격 더 하락 → Tier 4 매수 ($9.84)
        buy_tier = engine.check_buy_condition(9.84)
        assert buy_tier == 4, f"Tier 4 매수 조건 충족해야 함, got {buy_tier}"
        signal = engine.generate_buy_signal(9.84, buy_tier)
        engine.execute_buy(signal)
        assert len(engine.positions) == 3

        # 가격 더 하락 → Tier 5 매수 ($9.79)
        buy_tier = engine.check_buy_condition(9.79)
        assert buy_tier == 5, f"Tier 5 매수 조건 충족해야 함, got {buy_tier}"
        signal = engine.generate_buy_signal(9.79, buy_tier)
        engine.execute_buy(signal)
        assert len(engine.positions) == 4

        # 보유 Tier 확인
        held_tiers = {p.tier for p in engine.positions}
        assert held_tiers == {2, 3, 4, 5}

    def test_sell_highest_tier_first(self, engine):
        """
        매도 시 높은 Tier부터 매도

        여러 Tier 보유 시 가장 높은 Tier부터 매도 조건 확인
        """
        # Tier 2, 3, 4 순차 매수
        for price in [9.94, 9.89, 9.84]:
            tier = engine.check_buy_condition(price)
            signal = engine.generate_buy_signal(price, tier)
            engine.execute_buy(signal)

        assert len(engine.positions) == 3
        held_tiers = sorted([p.tier for p in engine.positions])
        assert held_tiers == [2, 3, 4]

        # 가격 상승 → Tier 4 목표가 도달
        # Tier 4 매도가 = $9.85 * 1.03 = $10.1455
        sell_tier = engine.check_sell_condition(10.15)
        assert sell_tier == 4, "가장 높은 Tier 4가 먼저 매도"

        sell_signal = engine.generate_sell_signal(10.15, sell_tier)
        engine.execute_sell(sell_signal)

        assert len(engine.positions) == 2
        remaining_tiers = sorted([p.tier for p in engine.positions])
        assert remaining_tiers == [2, 3], "Tier 4 매도 후 2, 3만 남음"

    def test_sideways_profit_accumulation(self, engine):
        """
        횡보 구간 수익 누적 시나리오

        Tier 2에서 3회 반복 매매 → 수익 누적 확인
        """
        initial_balance = engine.account_balance
        total_profit = 0.0

        # 3회 반복
        for i in range(3):
            # 매수 ($9.94 - Tier 2)
            buy_tier = engine.check_buy_condition(9.94)
            assert buy_tier == 2, f"반복 {i+1}: Tier 2 매수 가능"

            signal = engine.generate_buy_signal(9.94, buy_tier)
            engine.execute_buy(signal)

            # 매도 (Tier 2 목표가 $10.2485)
            target_price = 10.25
            sell_tier = engine.check_sell_condition(target_price)
            assert sell_tier == 2

            sell_signal = engine.generate_sell_signal(target_price, sell_tier)
            profit = engine.execute_sell(sell_signal)

            total_profit += profit

        # 잔고 증가 확인
        final_balance = engine.account_balance
        assert final_balance > initial_balance, "잔고가 증가해야 함"
        assert abs((final_balance - initial_balance) - total_profit) < 0.01, "수익이 잔고에 반영됨"

    def test_process_tick_generates_signals(self, engine):
        """
        process_tick()이 올바른 신호 생성
        """
        # 매수 조건 충족 가격
        signals = engine.process_tick(9.94)

        # 매수 신호 발생
        assert len(signals) >= 1, "신호가 발생해야 함"
        assert signals[0].action == "BUY"
        assert signals[0].tier == 2

    def test_no_rebuy_while_holding(self, engine):
        """
        포지션 보유 중에는 같은 Tier 재매수 불가

        Tier 2 보유 중 → Tier 2 재매수 시도 → 불가 (Tier 3으로 넘어감)
        """
        # Tier 2 매수
        signal = engine.generate_buy_signal(9.94, 2)
        engine.execute_buy(signal)

        assert len(engine.positions) == 1

        # 가격을 Tier 3 조건까지 하락시켜서 재매수 시도
        # Tier 3 가격 = $9.90, 이 이하에서 Tier 3 매수 가능
        rebuy_tier = engine.check_buy_condition(9.89)

        # Tier 2는 이미 보유 중이므로 Tier 3 반환
        assert rebuy_tier == 3, "이미 보유 중인 Tier 2 대신 Tier 3 반환"


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
        """
        # 잔고를 거의 소진
        engine.account_balance = 40.0  # Tier amount ($50) 미만

        buy_tier = engine.check_buy_condition(9.94)
        assert buy_tier is None, "잔고 부족으로 매수 불가"

    def test_buy_limit_prevents_rebuy(self):
        """
        매수 제한 스위치 활성화 시 재매수 불가
        """
        from src.models import GridSettings
        from src.grid_engine import GridEngine

        # buy_limit=True인 새 설정으로 엔진 생성
        settings = GridSettings(
            account_no="12345678",
            ticker="SOXL",
            investment_usd=10000.0,
            total_tiers=240,
            tier_amount=50.0,
            tier1_auto_update=False,
            tier1_trading_enabled=True,
            tier1_buy_percent=0.0,
            buy_limit=True,  # 매수 제한 활성화
            sell_limit=False,
            telegram_enabled=False,
            seed_ratio=0.05,
            buy_interval=0.005,
            sell_target=0.03
        )
        engine = GridEngine(settings)
        engine.tier1_price = 10.00

        buy_tier = engine.check_buy_condition(9.80)
        assert buy_tier is None, "매수 제한으로 매수 불가"

    def test_sell_limit_prevents_sell(self):
        """
        매도 제한 스위치 활성화 시 매도 불가
        """
        from src.models import GridSettings
        from src.grid_engine import GridEngine

        # sell_limit=False인 설정으로 먼저 매수
        settings_buy = GridSettings(
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
        engine = GridEngine(settings_buy)
        engine.tier1_price = 10.00

        # Tier 2 매수
        signal = engine.generate_buy_signal(9.94, 2)
        engine.execute_buy(signal)

        # sell_limit=True인 새 설정으로 엔진 재생성 (포지션 유지)
        settings_sell = GridSettings(
            account_no="12345678",
            ticker="SOXL",
            investment_usd=10000.0,
            total_tiers=240,
            tier_amount=50.0,
            tier1_auto_update=False,
            tier1_trading_enabled=True,
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=True,  # 매도 제한 활성화
            telegram_enabled=False,
            seed_ratio=0.05,
            buy_interval=0.005,
            sell_target=0.03
        )
        # 기존 포지션 복사
        old_positions = engine.positions.copy()
        old_balance = engine.account_balance

        engine2 = GridEngine(settings_sell)
        engine2.tier1_price = 10.00
        engine2.positions = old_positions
        engine2.account_balance = old_balance

        # 목표가 도달해도 매도 불가
        sell_tier = engine2.check_sell_condition(10.25)
        assert sell_tier is None, "매도 제한으로 매도 불가"

    def test_tier1_trading_enabled(self):
        """
        Tier 1 거래 활성화 시 Tier 1 매수 가능
        """
        from src.models import GridSettings
        from src.grid_engine import GridEngine

        settings = GridSettings(
            account_no="12345678",
            ticker="SOXL",
            investment_usd=10000.0,
            total_tiers=240,
            tier_amount=50.0,
            tier1_auto_update=False,
            tier1_trading_enabled=True,  # Tier 1 활성화
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

        # Tier 1 가격에서 매수
        buy_tier = engine.check_buy_condition(10.00)
        assert buy_tier == 1, "Tier 1 매수 가능"

    def test_tier1_trading_disabled(self):
        """
        Tier 1 거래 비활성화 시 Tier 2부터 매수
        """
        from src.models import GridSettings
        from src.grid_engine import GridEngine

        settings = GridSettings(
            account_no="12345678",
            ticker="SOXL",
            investment_usd=10000.0,
            total_tiers=240,
            tier_amount=50.0,
            tier1_auto_update=False,
            tier1_trading_enabled=False,  # Tier 1 비활성화
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

        # Tier 2 가격 ($9.95) 이하에서 매수 시도 → Tier 2 반환
        buy_tier = engine.check_buy_condition(9.94)
        assert buy_tier == 2, "Tier 1 비활성화 시 Tier 2부터 매수"
