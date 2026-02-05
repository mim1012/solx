"""
Phoenix Trading System - 메시지 개선 검증 테스트
Phase 1 구현 후 InitStatus Enum 및 종료 코드 검증
"""
import pytest
import sys
from pathlib import Path

# phoenix_main 모듈 import를 위한 경로 설정
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestInitStatusEnum:
    """InitStatus Enum 정의 검증"""

    def test_init_status_enum_exists(self):
        """InitStatus Enum이 정의되어 있는지 확인"""
        try:
            from phoenix_main import InitStatus
            assert InitStatus is not None
        except ImportError:
            pytest.fail("InitStatus Enum을 import할 수 없습니다")

    def test_init_status_values(self):
        """InitStatus Enum 값 확인"""
        from phoenix_main import InitStatus

        # 필수 상태들
        assert hasattr(InitStatus, 'SUCCESS'), "SUCCESS 상태 없음"
        assert hasattr(InitStatus, 'STOPPED'), "STOPPED 상태 없음"
        assert hasattr(InitStatus, 'ERROR_EXCEL'), "ERROR_EXCEL 상태 없음"
        assert hasattr(InitStatus, 'ERROR_API_KEY'), "ERROR_API_KEY 상태 없음"
        assert hasattr(InitStatus, 'ERROR_LOGIN'), "ERROR_LOGIN 상태 없음"

    def test_stopped_status_value(self):
        """STOPPED 종료 코드 = 10"""
        from phoenix_main import InitStatus

        assert InitStatus.STOPPED.value == 10, "STOPPED 종료 코드는 10이어야 함"

    def test_success_status_value(self):
        """SUCCESS 종료 코드 = 0"""
        from phoenix_main import InitStatus

        assert InitStatus.SUCCESS.value == 0, "SUCCESS 종료 코드는 0이어야 함"

    def test_error_status_values(self):
        """에러 종료 코드들 (20-29)"""
        from phoenix_main import InitStatus

        assert InitStatus.ERROR_EXCEL.value == 20
        assert InitStatus.ERROR_API_KEY.value == 21
        assert InitStatus.ERROR_LOGIN.value == 22


class TestPhoenixMainInitialize:
    """phoenix_main.initialize() 메서드 검증"""

    def test_initialize_returns_init_status(self):
        """initialize() 메서드가 InitStatus를 반환하는지 확인"""
        from phoenix_main import PhoenixTradingSystem, InitStatus

        # 임시 Excel 파일 없이 테스트 (ERROR_EXCEL 예상)
        system = PhoenixTradingSystem("non_existent.xlsx")

        # 타입 힌트 확인
        import inspect
        sig = inspect.signature(system.initialize)
        assert sig.return_annotation == InitStatus, "initialize()는 InitStatus를 반환해야 함"


class TestPhoenixMainRun:
    """phoenix_main.run() 메서드 검증"""

    def test_run_returns_int(self):
        """run() 메서드가 int (종료 코드)를 반환하는지 확인"""
        from phoenix_main import PhoenixTradingSystem

        system = PhoenixTradingSystem("non_existent.xlsx")

        # 타입 힌트 확인
        import inspect
        sig = inspect.signature(system.run)
        assert sig.return_annotation == int, "run()은 int (종료 코드)를 반환해야 함"


class TestExitCodeBehavior:
    """종료 코드 동작 검증"""

    def test_b15_false_returns_10(self, test_excel_b15_false):
        """B15=FALSE → 종료 코드 10"""
        from phoenix_main import PhoenixTradingSystem

        system = PhoenixTradingSystem(str(test_excel_b15_false))
        exit_code = system.run()

        assert exit_code == 10, f"B15=FALSE 시 종료 코드 10 예상, 실제: {exit_code}"

    def test_excel_not_found_returns_20(self):
        """Excel 파일 없음 → 종료 코드 20"""
        from phoenix_main import PhoenixTradingSystem

        system = PhoenixTradingSystem("non_existent.xlsx")
        exit_code = system.run()

        assert exit_code == 20, f"Excel 없음 시 종료 코드 20 예상, 실제: {exit_code}"


class TestLogMessages:
    """로그 메시지 개선 검증"""

    def test_b15_false_log_message(self, test_excel_b15_false, caplog):
        """B15=FALSE 시 개선된 로그 메시지 확인"""
        from phoenix_main import PhoenixTradingSystem

        system = PhoenixTradingSystem(str(test_excel_b15_false))
        system.run()

        # 로그 메시지 확인
        log_messages = " ".join([record.message for record in caplog.records])

        assert "시스템이 중지 상태입니다" in log_messages
        assert "에러가 아닙니다" in log_messages
        assert "초기화 실패" not in log_messages  # 혼란스러운 메시지 제거 확인


# 테스트 헬퍼 Fixtures (재사용)
@pytest.fixture
def test_excel_b15_false(tmp_path):
    """B15=FALSE 테스트용 Excel 파일"""
    import shutil
    import openpyxl

    template = Path(__file__).parent.parent / "phoenix_grid_template_v3.xlsx"
    if not template.exists():
        pytest.skip("Excel 템플릿 없음")

    test_file = tmp_path / "test_stopped.xlsx"
    shutil.copy(template, test_file)

    wb = openpyxl.load_workbook(test_file)
    ws = wb["01_매매전략_기준설정"]
    ws["B15"] = False
    wb.save(test_file)
    wb.close()

    return test_file
