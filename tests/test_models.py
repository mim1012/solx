"""
src/models.py 단위 테스트

테스트 범위:
1. Position 데이터 모델 검증
2. TradeSignal 데이터 모델 검증
3. GridSettings 데이터 모델 검증 및 validation
4. SystemState 데이터 모델 검증

코드 리뷰에서 식별된 이슈 테스트:
- Position.current_value 속성 미구현 (TODO)
- GridSettings.__post_init__ 검증 로직 부재
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError
from src.models import Position, TradeSignal, GridSettings, SystemState


class TestPosition:
    """Position 데이터 모델 테스트"""

    def test_create_position_basic(self):
        """기본 포지션 생성 테스트"""
        position = Position(
            tier=1,
            quantity=10,
            avg_price=10.0,
            invested_amount=100.0,
            opened_at=datetime.now()
        )

        assert position.tier == 1
        assert position.quantity == 10
        assert position.avg_price == 10.0
        assert position.invested_amount == 100.0
        assert isinstance(position.opened_at, datetime)

    def test_position_with_zero_quantity(self):
        """수량 0인 포지션 (청산된 포지션)"""
        position = Position(
            tier=1,
            quantity=0,
            avg_price=10.0,
            invested_amount=0.0,
            opened_at=datetime.now()
        )

        assert position.quantity == 0
        assert position.invested_amount == 0.0

    def test_position_with_negative_tier_should_fail(self):
        """음수 Tier는 불가능 (논리적 검증)"""
        # Note: 현재 코드에는 검증 없음 - 개선 필요
        with pytest.raises(Exception):
            # 실제로는 검증 로직이 없어서 예외가 발생하지 않음
            # 이 테스트는 FAIL하고, 개선이 필요함을 보여줌
            position = Position(
                tier=-1,
                quantity=10,
                avg_price=10.0,
                invested_amount=100.0,
                opened_at=datetime.now()
            )
            # 검증 로직 추가 시: raise ValueError("Tier must be positive")

    @pytest.mark.xfail(reason="current_value property not implemented yet")
    def test_position_current_value_property(self):
        """Position.current_value 속성 테스트 (코드 리뷰 issue #1)"""
        position = Position(
            tier=1,
            quantity=10,
            avg_price=10.0,
            invested_amount=100.0,
            opened_at=datetime.now()
        )

        # 현재가 11.0일 때
        current_price = 11.0
        expected_value = 10 * 11.0  # 110.0

        # 이 테스트는 실패함 (current_value가 구현되지 않음)
        assert position.current_value(current_price) == expected_value

    def test_position_immutable(self):
        """Position은 frozen=True로 불변이어야 함"""
        position = Position(
            tier=1,
            quantity=10,
            avg_price=10.0,
            invested_amount=100.0,
            opened_at=datetime.now()
        )

        # 속성 변경 시도 시 에러
        with pytest.raises(FrozenInstanceError):
            position.quantity = 20


class TestTradeSignal:
    """TradeSignal 데이터 모델 테스트"""

    def test_create_buy_signal(self):
        """매수 신호 생성"""
        signal = TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Tier 1 매수 조건 충족",
            timestamp=datetime.now()
        )

        assert signal.action == "BUY"
        assert signal.tier == 1
        assert signal.price == 10.0
        assert signal.quantity == 10
        assert "매수" in signal.reason

    def test_create_sell_signal(self):
        """매도 신호 생성"""
        signal = TradeSignal(
            action="SELL",
            tier=1,
            price=10.1,
            quantity=10,
            reason="Tier 1 매도 조건 충족",
            timestamp=datetime.now()
        )

        assert signal.action == "SELL"
        assert signal.tier == 1
        assert signal.price == 10.1

    def test_signal_immutable(self):
        """TradeSignal도 불변이어야 함"""
        signal = TradeSignal(
            action="BUY",
            tier=1,
            price=10.0,
            quantity=10,
            reason="Test",
            timestamp=datetime.now()
        )

        with pytest.raises(FrozenInstanceError):
            signal.action = "SELL"


class TestGridSettings:
    """GridSettings 데이터 모델 테스트"""

    def test_create_basic_settings(self, grid_settings_basic):
        """기본 Grid 설정 생성"""
        settings = grid_settings_basic

        assert settings.ticker == "SOXL"
        assert settings.total_tiers == 240
        assert settings.tier1_price == 10.0
        assert settings.investment_usd == 10000

    def test_tier1_disabled_by_default(self, grid_settings_basic):
        """Tier 1 매매는 기본적으로 비활성화"""
        settings = grid_settings_basic

        assert settings.tier1_trading_enabled == False

    def test_tier1_enabled_settings(self, grid_settings_tier1_enabled):
        """Tier 1 활성화된 설정"""
        settings = grid_settings_tier1_enabled

        assert settings.tier1_trading_enabled == True

    @pytest.mark.xfail(reason="GridSettings validation not implemented")
    def test_invalid_tier_count_should_fail(self):
        """잘못된 Tier 개수는 에러 (코드 리뷰 issue #2)"""
        # 현재는 검증 로직이 없어서 통과됨
        with pytest.raises(ValueError, match="total_tiers must be between 1 and 240"):
            GridSettings(
                ticker="SOXL",
                total_tiers=0,  # 0은 불가능
                tier1_price=10.0,
                investment_usd=10000,
                account_no="12345678"
            )

    @pytest.mark.xfail(reason="GridSettings validation not implemented")
    def test_negative_investment_should_fail(self):
        """음수 투자금은 에러"""
        with pytest.raises(ValueError, match="investment_usd must be positive"):
            GridSettings(
                ticker="SOXL",
                total_tiers=240,
                tier1_price=10.0,
                investment_usd=-1000,  # 음수 불가
                account_no="12345678"
            )

    @pytest.mark.xfail(reason="GridSettings validation not implemented")
    def test_zero_tier1_price_should_fail(self):
        """Tier 1 가격 0은 에러"""
        with pytest.raises(ValueError, match="tier1_price must be positive"):
            GridSettings(
                ticker="SOXL",
                total_tiers=240,
                tier1_price=0.0,  # 0 불가
                investment_usd=10000,
                account_no="12345678"
            )

    def test_calculate_tier_price(self, grid_settings_basic):
        """Tier 가격 계산 테스트"""
        settings = grid_settings_basic

        # Tier 1: 10.0
        # Tier 2: 9.95 (10.0 - 0.05)
        # Tier 3: 9.90 (10.0 - 0.10)

        tier1_price = 10.0
        tier2_price = tier1_price - (settings.tier_interval * 1)
        tier3_price = tier1_price - (settings.tier_interval * 2)

        assert tier2_price == 9.95
        assert tier3_price == 9.90

    def test_settings_immutable(self, grid_settings_basic):
        """GridSettings는 불변"""
        with pytest.raises(FrozenInstanceError):
            grid_settings_basic.tier1_price = 20.0


class TestSystemState:
    """SystemState 데이터 모델 테스트"""

    def test_create_system_state(self):
        """시스템 상태 생성 (v4.0 telemetry 모델)"""
        state = SystemState(
            current_price=10.0,
            tier1_price=10.0,
            current_tier=0,
            account_balance=10000.0,
            total_quantity=0,
            total_invested=0.0,
            stock_value=0.0,
            total_profit=0.0,
            profit_rate=0.0
        )

        assert state.current_price == 10.0
        assert state.account_balance == 10000.0
        assert state.total_quantity == 0

    def test_state_with_positions(self, sample_positions):
        """포지션이 있는 시스템 상태 (v4.0 모델)"""
        total_invested = sum(p.invested_amount for p in sample_positions)
        total_quantity = sum(p.quantity for p in sample_positions)

        state = SystemState(
            current_price=10.0,
            tier1_price=10.0,
            current_tier=3,  # 3개 tier 활성
            account_balance=9404.0,  # 10000 - 596 (invested)
            total_quantity=total_quantity,
            total_invested=total_invested,
            stock_value=600.0,  # 60 * 10.0
            total_profit=4.0,  # 600 - 596
            profit_rate=0.67  # 4 / 596
        )

        assert state.total_invested == 596.0
        assert state.total_quantity == 60  # 10 + 20 + 30
        assert state.current_tier == 3

    def test_state_not_frozen(self):
        """SystemState는 frozen=False (변경 가능, v4.0 모델)"""
        state = SystemState(
            current_price=10.0,
            tier1_price=10.0,
            current_tier=0,
            account_balance=10000.0,
            total_quantity=0,
            total_invested=0.0,
            stock_value=0.0,
            total_profit=0.0,
            profit_rate=0.0
        )

        # 속성 변경 가능 (mutable)
        state.current_price = 11.0
        state.account_balance = 9000.0

        assert state.current_price == 11.0
        assert state.account_balance == 9000.0


class TestDataModelIntegration:
    """데이터 모델 간 통합 테스트"""

    def test_position_to_signal_workflow(self):
        """포지션 생성 -> 매도 신호 생성 워크플로우"""
        # 1. 매수로 포지션 생성
        position = Position(
            tier=1,
            quantity=10,
            avg_price=10.0,
            invested_amount=100.0,
            opened_at=datetime.now()
        )

        # 2. 가격 상승 후 매도 신호
        sell_price = 10.1
        sell_signal = TradeSignal(
            action="SELL",
            tier=position.tier,
            price=sell_price,
            quantity=position.quantity,
            reason=f"Tier {position.tier} 목표가 도달",
            timestamp=datetime.now()
        )

        assert sell_signal.tier == position.tier
        assert sell_signal.quantity == position.quantity
        assert sell_signal.price > position.avg_price

    def test_system_state_reflects_positions(self, sample_positions):
        """시스템 상태가 포지션 리스트를 반영 (v4.0 모델)"""
        total_invested = sum(p.invested_amount for p in sample_positions)
        total_quantity = sum(p.quantity for p in sample_positions)

        state = SystemState(
            current_price=10.0,
            tier1_price=10.0,
            current_tier=len(sample_positions),
            account_balance=10000 - total_invested,
            total_quantity=total_quantity,
            total_invested=total_invested,
            stock_value=total_quantity * 10.0,
            total_profit=(total_quantity * 10.0) - total_invested,
            profit_rate=((total_quantity * 10.0) - total_invested) / total_invested
        )

        # 잔고 = 초기자본 - 투자금
        assert state.account_balance == 10000 - 596
        assert state.total_invested == 596
        assert state.total_quantity == 60
        assert state.current_tier == 3


# 성능 테스트
class TestPerformance:
    """데이터 모델 성능 테스트"""

    def test_create_many_positions_performance(self, benchmark):
        """대량 포지션 생성 성능 (240개 tier)"""
        def create_positions():
            positions = []
            for tier in range(1, 241):
                pos = Position(
                    tier=tier,
                    quantity=10,
                    avg_price=10.0 - (tier * 0.05),
                    invested_amount=100.0,
                    opened_at=datetime.now()
                )
                positions.append(pos)
            return positions

        # pytest-benchmark 필요
        # positions = benchmark(create_positions)
        # assert len(positions) == 240

        # 간단 버전 (benchmark 없이)
        positions = create_positions()
        assert len(positions) == 240
