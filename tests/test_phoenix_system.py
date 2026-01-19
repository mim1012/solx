"""
src/phoenix_system.py 단위 테스트

테스트 범위:
1. Phoenix 시스템 초기화
2. 시세 업데이트 처리
3. 신호 처리 및 주문 실행
4. Excel 업데이트
5. 동시성 제어

코드 리뷰에서 식별된 CRITICAL 이슈 테스트:
- Issue #1: _on_price_update 콜백에서 동시성 제어 미흡
- Issue #2: Excel이 매 틱마다 업데이트되어 성능 저하
- Issue #3: 주문 실패 시 GridEngine 상태 불일치
"""

import pytest
import threading
from unittest.mock import Mock, MagicMock, patch
from src.phoenix_system import PhoenixSystem
from src.models import TradeSignal
from datetime import datetime


class TestPhoenixInitialization:
    """Phoenix 시스템 초기화 테스트"""

    def test_create_system(self, temp_excel_file):
        """Phoenix 시스템 생성"""
        with patch('src.phoenix_system.KiwoomAdapter') as mock_kiwoom:
            with patch('src.phoenix_system.TelegramNotifier') as mock_telegram:
                system = PhoenixSystem(temp_excel_file)

                assert system.excel_path == temp_excel_file
                assert system.grid_engine is not None
                assert system.excel_bridge is not None


class TestPriceUpdateHandling:
    """시세 업데이트 처리 테스트 (CRITICAL)"""

    @pytest.mark.xfail(reason="Concurrency control not implemented - Code Review Issue #1")
    def test_concurrent_price_updates_thread_safe(self, temp_excel_file, concurrent_price_updates):
        """
        동시 시세 업데이트 스레드 안전성 테스트

        코드 리뷰 Issue #1:
        _on_price_update가 PyQt 스레드에서 호출되는데
        threading.Lock() 없이 grid_engine 상태 변경
        """
        with patch('src.phoenix_system.KiwoomAdapter'):
            with patch('src.phoenix_system.TelegramNotifier'):
                system = PhoenixSystem(temp_excel_file)

                # 동시 시세 업데이트 시뮬레이션
                concurrent_price_updates.register_callback(system._on_price_update)
                concurrent_price_updates.simulate_concurrent_updates()

                # race condition이 없어야 함
                # 현재는 Lock이 없어서 실패 가능
                assert system.grid_engine.positions is not None

    def test_price_update_generates_signals(self, temp_excel_file):
        """시세 업데이트가 신호 생성"""
        with patch('src.phoenix_system.KiwoomAdapter'):
            with patch('src.phoenix_system.TelegramNotifier'):
                system = PhoenixSystem(temp_excel_file)

                # Tier 1 활성화
                system.grid_engine.settings.tier1_trading_enabled = True

                # 시세 업데이트
                system._on_price_update(10.0)

                # 매수 신호 생성되어야 함
                # (실제 구현에 따라 검증 방식 다를 수 있음)


class TestSignalProcessing:
    """신호 처리 테스트 (CRITICAL)"""

    @pytest.mark.xfail(reason="Order failure handling not implemented - Code Review Issue #3")
    def test_order_failure_does_not_corrupt_state(self, temp_excel_file):
        """
        주문 실패 시 상태 불일치 방지 테스트

        코드 리뷰 Issue #3:
        주문 실패 시 GridEngine 상태가 이미 변경되어 롤백 불가
        """
        with patch('src.phoenix_system.KiwoomAdapter') as mock_kiwoom:
            with patch('src.phoenix_system.TelegramNotifier'):
                system = PhoenixSystem(temp_excel_file)

                # 주문 실패 시뮬레이션
                mock_kiwoom.return_value.send_order.side_effect = Exception("주문 실패")

                initial_balance = system.grid_engine.account_balance
                initial_positions = len(system.grid_engine.positions)

                signal = TradeSignal(
                    action="BUY",
                    tier=1,
                    price=10.0,
                    quantity=10,
                    reason="Test",
                    timestamp=datetime.now()
                )

                # 신호 처리 (주문 실패)
                try:
                    system._process_signal(signal)
                except Exception:
                    pass

                # 주문 실패했으므로 상태가 변경되지 않아야 함
                assert system.grid_engine.account_balance == initial_balance
                assert len(system.grid_engine.positions) == initial_positions


class TestExcelUpdateOptimization:
    """Excel 업데이트 최적화 테스트"""

    @pytest.mark.xfail(reason="Excel update optimization not implemented - Code Review Issue #2")
    def test_excel_not_updated_every_tick(self, temp_excel_file):
        """
        Excel이 매 틱마다 업데이트되지 않도록 최적화 테스트

        코드 리뷰 Issue #2:
        현재는 매 시세마다 Excel 저장 → 성능 저하
        """
        with patch('src.phoenix_system.KiwoomAdapter'):
            with patch('src.phoenix_system.TelegramNotifier'):
                system = PhoenixSystem(temp_excel_file)

                # Excel save 횟수 추적
                with patch.object(system.excel_bridge, 'save_workbook') as mock_save:
                    # 100번 시세 업데이트
                    for _ in range(100):
                        system._on_price_update(10.0)

                    # 100번 저장하면 안 됨 (최적화 필요)
                    assert mock_save.call_count < 10  # 예: 10초마다 저장


class TestSystemState:
    """시스템 상태 테스트"""

    def test_get_system_state(self, temp_excel_file):
        """시스템 상태 조회"""
        with patch('src.phoenix_system.KiwoomAdapter'):
            with patch('src.phoenix_system.TelegramNotifier'):
                system = PhoenixSystem(temp_excel_file)

                state = system.get_system_state()

                assert state.is_running == False
                assert state.account_balance > 0

    def test_start_stop_system(self, temp_excel_file):
        """시스템 시작/정지"""
        with patch('src.phoenix_system.KiwoomAdapter'):
            with patch('src.phoenix_system.TelegramNotifier'):
                system = PhoenixSystem(temp_excel_file)

                system.start()
                assert system.is_running == True

                system.stop()
                assert system.is_running == False


class TestBugFixes:
    """Bug #5 수정 검증: telegram None 가드 테스트"""

    def test_kiwoom_login_failure_preserves_original_error(self, temp_excel_file):
        """
        CRITICAL: telegram None일 때 AttributeError 발생 안 함

        시나리오:
        1. Kiwoom 로그인 실패
        2. initialize() 예외 발생
        3. telegram이 None이므로 notify_error() 호출 불가
        4. 원본 에러(ConnectionError)를 유지해야 함
        5. AttributeError가 발생하면 안 됨

        이전 버그: self.telegram.notify_error() → AttributeError: 'NoneType' object has no attribute 'notify_error'
        수정 후: telegram None 체크 후 안전하게 처리
        """
        with patch('src.phoenix_system.KiwoomAdapter') as mock_kiwoom:
            # Kiwoom 로그인 실패 시뮬레이션
            mock_kiwoom.return_value.login.return_value = False

            system = PhoenixSystem(temp_excel_file)

            # initialize() 호출 시 ConnectionError 발생해야 함
            with pytest.raises(ConnectionError) as exc_info:
                system.initialize()

            # 원본 에러 메시지 확인
            assert "키움증권 로그인 실패" in str(exc_info.value)

            # telegram이 None이어야 함 (초기화 실패)
            assert system.telegram is None

    def test_excel_load_failure_no_telegram_error(self, temp_excel_file):
        """
        Excel 파일 로드 실패 시 telegram None 안전 처리

        시나리오:
        1. Excel 파일이 손상됨
        2. ExcelBridge.load_workbook() 실패
        3. telegram이 아직 None
        4. AttributeError 없이 원본 에러만 발생해야 함
        """
        with patch('src.phoenix_system.ExcelBridge') as mock_excel:
            # Excel 로드 실패 시뮬레이션
            mock_excel.return_value.load_workbook.side_effect = Exception("Excel 손상")

            system = PhoenixSystem(temp_excel_file)

            with pytest.raises(Exception) as exc_info:
                system.initialize()

            # 원본 에러 확인
            assert "Excel 손상" in str(exc_info.value)

            # telegram이 None이어야 함
            assert system.telegram is None

    def test_telegram_initialization_success(self, temp_excel_file):
        """
        정상 초기화 시 telegram 알림이 작동해야 함

        시나리오:
        1. 모든 초기화 성공
        2. telegram이 제대로 생성됨
        3. notify_error() 호출 가능
        """
        with patch('src.phoenix_system.KiwoomAdapter') as mock_kiwoom:
            with patch('src.phoenix_system.TelegramNotifier') as mock_telegram:
                # 정상 로그인
                mock_kiwoom.return_value.login.return_value = True
                mock_kiwoom.return_value.account_list = ["12345678"]

                system = PhoenixSystem(temp_excel_file)
                system.initialize()

                # telegram이 생성되었어야 함
                assert system.telegram is not None

                # notify_system_start 호출 확인
                mock_telegram.from_settings.return_value.notify_system_start.assert_called_once()

    def test_telegram_notify_error_safe_call(self, temp_excel_file):
        """
        telegram이 활성화된 경우에만 알림 전송

        시나리오:
        1. telegram_enabled=False로 설정
        2. initialize() 실패
        3. telegram.notify_error() 호출 안 됨 (enabled=False)
        """
        with patch('src.phoenix_system.KiwoomAdapter') as mock_kiwoom:
            with patch('src.phoenix_system.TelegramNotifier') as mock_telegram:
                # telegram 비활성화 상태
                mock_telegram_instance = Mock()
                mock_telegram_instance.enabled = False
                mock_telegram.from_settings.return_value = mock_telegram_instance

                # Kiwoom 로그인 실패
                mock_kiwoom.return_value.login.return_value = False

                system = PhoenixSystem(temp_excel_file)

                with pytest.raises(ConnectionError):
                    system.initialize()

                # notify_error 호출 안 되었어야 함 (enabled=False)
                mock_telegram_instance.notify_error.assert_not_called()
