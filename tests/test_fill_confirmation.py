# -*- coding: utf-8 -*-
"""
체결 확인 기능 테스트

P0 버그 수정 검증:
1. get_order_fill_status() 메서드
2. 0수량 포지션 방지
3. 체결 확인 로직
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.kis_rest_adapter import KisRestAdapter
from src.grid_engine import GridEngine
from src.models import GridSettings, TradeSignal


class TestOrderFillStatus:
    """주문 체결 상태 조회 테스트"""

    @pytest.fixture
    def adapter(self):
        """KisRestAdapter 인스턴스 생성"""
        adapter = KisRestAdapter(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01"
        )
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)
        return adapter

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_order_fill_status_completed(self, mock_get, adapter):
        """체결 완료 상태 조회"""
        # Mock 응답
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": [{
                "odno": "1234567890",
                "ft_ccld_qty": "100",
                "ft_ccld_unpr3": "45.52",
                "nccs_qty": "0",
                "prcs_stat_name": "완료",
                "rjct_rson_name": ""
            }]
        }
        mock_get.return_value = mock_response

        # 실행
        result = adapter.get_order_fill_status("1234567890")

        # 검증
        assert result["status"] == "완료"
        assert result["filled_qty"] == 100
        assert result["filled_price"] == 45.52
        assert result["unfilled_qty"] == 0

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_order_fill_status_pending(self, mock_get, adapter):
        """체결 대기 상태 조회"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": [{
                "odno": "1234567890",
                "ft_ccld_qty": "0",
                "ft_ccld_unpr3": "0",
                "nccs_qty": "100",
                "prcs_stat_name": "접수",
                "rjct_rson_name": ""
            }]
        }
        mock_get.return_value = mock_response

        result = adapter.get_order_fill_status("1234567890")

        assert result["status"] == "접수"
        assert result["filled_qty"] == 0
        assert result["unfilled_qty"] == 100

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_order_fill_status_rejected(self, mock_get, adapter):
        """주문 거부 상태 조회"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": [{
                "odno": "1234567890",
                "ft_ccld_qty": "0",
                "ft_ccld_unpr3": "0",
                "nccs_qty": "100",
                "prcs_stat_name": "거부",
                "rjct_rson_name": "잔고 부족"
            }]
        }
        mock_get.return_value = mock_response

        result = adapter.get_order_fill_status("1234567890")

        assert result["status"] == "거부"
        assert result["reject_reason"] == "잔고 부족"
        assert result["filled_qty"] == 0

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_order_fill_status_partial_fill(self, mock_get, adapter):
        """부분 체결 상태 조회"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": [{
                "odno": "1234567890",
                "ft_ccld_qty": "50",
                "ft_ccld_unpr3": "45.50",
                "nccs_qty": "50",
                "prcs_stat_name": "접수",
                "rjct_rson_name": ""
            }]
        }
        mock_get.return_value = mock_response

        result = adapter.get_order_fill_status("1234567890")

        assert result["status"] == "접수"
        assert result["filled_qty"] == 50
        assert result["unfilled_qty"] == 50


class TestZeroQuantityPrevention:
    """0수량 포지션 방지 테스트"""

    @pytest.fixture
    def settings(self):
        """GridSettings 생성"""
        return GridSettings(
            account_no="12345678-01",
            ticker="SOXL",
            investment_usd=10000,
            total_tiers=240,
            tier_amount=500,
            tier1_auto_update=True,
            tier1_trading_enabled=False,
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=False,
            tier1_price=10.0
        )

    @pytest.fixture
    def engine(self, settings):
        """GridEngine 생성"""
        return GridEngine(settings)

    def test_execute_buy_with_zero_quantity(self, engine):
        """0수량 매수 시도 - 포지션 생성 안됨"""
        signal = TradeSignal(
            action="BUY",
            tier=2,
            price=9.95,
            quantity=50,
            reason="Tier 2 매수"
        )

        # 0수량으로 체결
        position = engine.execute_buy(
            signal=signal,
            actual_filled_price=9.95,
            actual_filled_qty=0  # 0수량
        )

        # 포지션이 생성되지 않아야 함
        assert position is None
        assert len(engine.positions) == 0
        # 잔고도 차감되지 않아야 함
        assert engine.account_balance == 10000.0

    def test_execute_sell_with_zero_quantity(self, engine):
        """0수량 매도 시도 - 포지션 유지"""
        # 먼저 포지션 생성
        buy_signal = TradeSignal(
            action="BUY",
            tier=2,
            price=9.95,
            quantity=50,
            reason="Tier 2 매수"
        )
        position = engine.execute_buy(buy_signal)
        assert position is not None

        # 0수량 매도 시도
        sell_signal = TradeSignal(
            action="SELL",
            tier=2,
            price=10.25,
            quantity=50,
            reason="Tier 2 매도"
        )

        profit = engine.execute_sell(
            signal=sell_signal,
            actual_filled_price=10.25,
            actual_filled_qty=0  # 0수량
        )

        # 수익은 0이어야 함
        assert profit == 0.0
        # 포지션은 그대로 유지되어야 함
        assert len(engine.positions) == 1
        assert engine.positions[0].tier == 2
        assert engine.positions[0].quantity == 50

    def test_execute_buy_with_negative_quantity(self, engine):
        """음수 수량 매수 시도 - 포지션 생성 안됨"""
        signal = TradeSignal(
            action="BUY",
            tier=2,
            price=9.95,
            quantity=50,
            reason="Tier 2 매수"
        )

        position = engine.execute_buy(
            signal=signal,
            actual_filled_price=9.95,
            actual_filled_qty=-10  # 음수
        )

        assert position is None
        assert len(engine.positions) == 0


class TestFillCheckIntegration:
    """체결 확인 통합 테스트"""

    def test_fill_check_settings_defaults(self):
        """체결 확인 설정 기본값"""
        settings = GridSettings(
            account_no="12345678-01",
            ticker="SOXL",
            investment_usd=10000,
            total_tiers=240,
            tier_amount=500,
            tier1_auto_update=True,
            tier1_trading_enabled=False,
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=False,
            tier1_price=10.0
        )

        assert settings.fill_check_enabled is True
        assert settings.fill_check_max_retries == 10
        assert settings.fill_check_interval == 2.0

    def test_fill_check_can_be_disabled(self):
        """체결 확인 비활성화 가능"""
        settings = GridSettings(
            account_no="12345678-01",
            ticker="SOXL",
            investment_usd=10000,
            total_tiers=240,
            tier_amount=500,
            tier1_auto_update=True,
            tier1_trading_enabled=False,
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=False,
            tier1_price=10.0,
            fill_check_enabled=False
        )

        assert settings.fill_check_enabled is False


class TestWaitForFillIntegration:
    """_wait_for_fill() 통합 테스트"""

    @pytest.fixture
    def mock_system(self):
        """PhoenixTradingSystem Mock"""
        from unittest.mock import MagicMock

        system = MagicMock()

        # Settings Mock
        system.settings.fill_check_max_retries = 3
        system.settings.fill_check_interval = 0.1  # 빠른 테스트

        # KIS Adapter Mock
        system.kis_adapter = MagicMock()

        return system

    def test_wait_for_fill_success(self, mock_system):
        """체결 성공 시나리오"""
        from phoenix_main import PhoenixTradingSystem

        # Mock 응답: 첫 시도에 체결 완료
        mock_system.kis_adapter.get_order_fill_status.return_value = {
            "status": "완료",
            "filled_qty": 100,
            "filled_price": 45.50,
            "unfilled_qty": 0
        }

        # _wait_for_fill 실행
        filled_price, filled_qty = PhoenixTradingSystem._wait_for_fill(
            mock_system, "1234567890", 100
        )

        assert filled_qty == 100
        assert filled_price == 45.50

    def test_wait_for_fill_partial(self, mock_system):
        """부분 체결 시나리오"""
        from phoenix_main import PhoenixTradingSystem

        # Mock 응답: 50주만 체결 (상태: "접수")
        mock_system.kis_adapter.get_order_fill_status.return_value = {
            "status": "접수",
            "filled_qty": 50,
            "filled_price": 45.50,
            "unfilled_qty": 50
        }

        filled_price, filled_qty = PhoenixTradingSystem._wait_for_fill(
            mock_system, "1234567890", 100
        )

        # 부분 체결도 반영되어야 함
        assert filled_qty == 50
        assert filled_price == 45.50

    def test_wait_for_fill_rejected(self, mock_system):
        """주문 거부 시나리오"""
        from phoenix_main import PhoenixTradingSystem

        mock_system.kis_adapter.get_order_fill_status.return_value = {
            "status": "거부",
            "filled_qty": 0,
            "filled_price": 0.0,
            "unfilled_qty": 100,
            "reject_reason": "잔고 부족"
        }

        filled_price, filled_qty = PhoenixTradingSystem._wait_for_fill(
            mock_system, "1234567890", 100
        )

        assert filled_qty == 0
        assert filled_price == 0.0

    def test_wait_for_fill_timeout(self, mock_system):
        """타임아웃 시나리오"""
        from phoenix_main import PhoenixTradingSystem

        # Mock 응답: 계속 체결 대기
        mock_system.kis_adapter.get_order_fill_status.return_value = {
            "status": "접수",
            "filled_qty": 0,
            "filled_price": 0.0,
            "unfilled_qty": 100
        }

        filled_price, filled_qty = PhoenixTradingSystem._wait_for_fill(
            mock_system, "1234567890", 100
        )

        # 타임아웃 시 0 반환
        assert filled_qty == 0
        assert filled_price == 0.0

        # 재시도 횟수 확인: max_retries(3) + 타임아웃 후 추가 조회(1) = 4
        assert mock_system.kis_adapter.get_order_fill_status.call_count == 4
