"""
src/excel_bridge.py 단위 테스트

테스트 범위:
1. Excel 파일 로딩 및 저장
2. 설정 읽기/쓰기
3. Tier 데이터 읽기/쓰기
4. 운용로그 기록
5. 데이터 검증

코드 리뷰에서 식별된 CRITICAL 이슈 테스트:
- Issue #1: Excel 파일 동시 접근 시 PermissionError (retry logic 없음)
- Issue #2: save_workbook에 retry 메커니즘 부재
"""

import pytest
import openpyxl
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from src.excel_bridge import ExcelBridge
from src.models import Position, GridSettings


class TestExcelBridgeInitialization:
    """ExcelBridge 초기화 테스트"""

    def test_load_existing_file(self, temp_excel_file):
        """기존 Excel 파일 로딩"""
        bridge = ExcelBridge(temp_excel_file)

        assert bridge.file_path == temp_excel_file
        assert bridge.wb is not None
        assert "01_매매전략_기준설정" in bridge.wb.sheetnames
        assert "02_운용로그_히스토리" in bridge.wb.sheetnames

    def test_load_nonexistent_file(self):
        """존재하지 않는 파일 로딩 시 에러"""
        with pytest.raises(FileNotFoundError):
            ExcelBridge("nonexistent_file.xlsx")

    def test_worksheets_accessible(self, temp_excel_file):
        """워크시트 접근 가능"""
        bridge = ExcelBridge(temp_excel_file)

        ws1 = bridge.get_worksheet("01_매매전략_기준설정")
        ws2 = bridge.get_worksheet("02_운용로그_히스토리")

        assert ws1 is not None
        assert ws2 is not None


class TestReadSettings:
    """설정 읽기 테스트"""

    def test_read_basic_settings(self, temp_excel_file):
        """기본 설정 읽기"""
        bridge = ExcelBridge(temp_excel_file)
        settings = bridge.load_settings()

        assert isinstance(settings, GridSettings)
        assert settings.ticker == "SOXL"
        assert settings.account_no == "12345678"
        assert settings.investment_usd == 10000
        assert settings.tier1_price == 10.0

    def test_read_tier1_settings(self, temp_excel_file):
        """Tier 1 설정 읽기"""
        # Tier 1 활성화
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B10"] = True  # Tier 1 매수 활성화
        ws["B11"] = True  # Tier 1 매도 활성화
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        settings = bridge.load_settings()

        assert settings.tier1_trading_enabled == True

    def test_read_invalid_settings(self, temp_excel_file):
        """잘못된 설정 읽기 시 에러"""
        # 필수 값을 null로 설정
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B3"] = None  # 종목코드 null
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)

        with pytest.raises(ValueError):
            bridge.load_settings()


class TestReadTierData:
    """Tier 데이터 읽기 테스트"""

    def test_read_empty_tiers(self, temp_excel_file):
        """빈 Tier 데이터 읽기"""
        bridge = ExcelBridge(temp_excel_file)
        positions = bridge.read_tier_positions()

        assert len(positions) == 0

    def test_read_single_position(self, temp_excel_file):
        """단일 포지션 읽기"""
        # Tier 1 데이터 입력
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["H18"] = 10  # Tier 1 잔고량
        ws["I18"] = 100.0  # 투자금
        ws["J18"] = 10.0  # 평균단가
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        positions = bridge.read_tier_positions()

        assert len(positions) == 1
        assert positions[0].tier == 1
        assert positions[0].quantity == 10
        assert positions[0].invested_amount == 100.0
        assert positions[0].avg_price == 10.0

    def test_read_multiple_positions(self, temp_excel_file):
        """다중 포지션 읽기"""
        # Tier 1, 2, 3 데이터 입력
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]

        for tier in [1, 2, 3]:
            row_idx = 17 + tier
            ws[f"H{row_idx}"] = 10 * tier
            ws[f"I{row_idx}"] = 100.0 * tier
            ws[f"J{row_idx}"] = 10.0 - (tier * 0.05)

        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        positions = bridge.read_tier_positions()

        assert len(positions) == 3
        assert positions[0].tier == 1
        assert positions[1].tier == 2
        assert positions[2].tier == 3


class TestWriteTierData:
    """Tier 데이터 쓰기 테스트"""

    def test_write_single_position(self, temp_excel_file, sample_positions):
        """단일 포지션 쓰기"""
        bridge = ExcelBridge(temp_excel_file)

        position = sample_positions[0]  # Tier 1
        bridge.write_tier_position(position)

        # 저장 및 재로딩
        bridge.save_workbook()
        bridge = ExcelBridge(temp_excel_file)

        # 검증
        ws = bridge.get_worksheet("01_매매전략_기준설정")
        row_idx = 17 + position.tier

        assert ws[f"H{row_idx}"].value == position.quantity
        assert ws[f"I{row_idx}"].value == position.invested_amount
        assert ws[f"J{row_idx}"].value == position.avg_price

    def test_write_multiple_positions(self, temp_excel_file, sample_positions):
        """다중 포지션 쓰기"""
        bridge = ExcelBridge(temp_excel_file)

        for position in sample_positions:
            bridge.write_tier_position(position)

        bridge.save_workbook()

        # 검증
        bridge = ExcelBridge(temp_excel_file)
        loaded_positions = bridge.read_tier_positions()

        assert len(loaded_positions) == len(sample_positions)
        for i, pos in enumerate(loaded_positions):
            assert pos.tier == sample_positions[i].tier
            assert pos.quantity == sample_positions[i].quantity


class TestOperationLog:
    """운용로그 테스트"""

    def test_add_log_entry_buy(self, temp_excel_file):
        """매수 로그 추가"""
        bridge = ExcelBridge(temp_excel_file)

        log_data = {
            "업데이트": datetime.now(),
            "종목": "SOXL",
            "티어": 1,
            "매수": 10,
            "매도": None
        }

        bridge.add_operation_log(log_data)
        bridge.save_workbook()

        # 검증
        bridge = ExcelBridge(temp_excel_file)
        ws = bridge.get_worksheet("02_운용로그_히스토리")

        # 마지막 행 확인
        last_row = ws.max_row
        assert ws[f"E{last_row}"].value == 1  # 티어
        assert ws[f"P{last_row}"].value == 10  # 매수

    def test_add_log_entry_sell(self, temp_excel_file):
        """매도 로그 추가"""
        bridge = ExcelBridge(temp_excel_file)

        log_data = {
            "업데이트": datetime.now(),
            "종목": "SOXL",
            "티어": 1,
            "매수": None,
            "매도": 10
        }

        bridge.add_operation_log(log_data)
        bridge.save_workbook()

        # 검증
        bridge = ExcelBridge(temp_excel_file)
        ws = bridge.get_worksheet("02_운용로그_히스토리")

        last_row = ws.max_row
        assert ws[f"Q{last_row}"].value == 10  # 매도


class TestFileLocking:
    """파일 잠금 처리 테스트 (CRITICAL)"""

    @pytest.mark.xfail(reason="Excel file retry logic not implemented - Code Review Issue #1")
    def test_save_with_file_locked_should_retry(self, locked_excel_file):
        """
        파일 잠금 시 재시도 로직 테스트

        코드 리뷰 Issue #1:
        Excel 파일이 다른 프로세스에 의해 잠겨있을 때,
        PermissionError 발생하지만 retry 로직이 없음
        """
        file_path, locked_wb = locked_excel_file

        bridge = ExcelBridge(file_path)

        # 파일이 잠긴 상태에서 저장 시도
        # retry 로직이 있으면 성공해야 함
        with pytest.raises(PermissionError):
            bridge.save_workbook(max_retries=3, retry_delay=0.5)

        # 실제 구현 시: 재시도 후 성공
        # assert True

    @patch('openpyxl.Workbook.save')
    def test_save_with_permission_error_retries(self, mock_save, temp_excel_file):
        """
        PermissionError 발생 시 재시도 테스트 (Mock)
        """
        # 처음 2번 실패, 3번째 성공
        mock_save.side_effect = [
            PermissionError("파일 잠김"),
            PermissionError("파일 잠김"),
            None  # 성공
        ]

        bridge = ExcelBridge(temp_excel_file)

        # retry 로직이 구현되면 성공해야 함
        # 현재는 구현되지 않아서 실패
        with pytest.raises(PermissionError):
            bridge.save_workbook()

    def test_save_without_permission_error(self, temp_excel_file):
        """정상 저장 테스트"""
        bridge = ExcelBridge(temp_excel_file)

        # 데이터 변경
        ws = bridge.get_worksheet("01_매매전략_기준설정")
        ws["B2"] = "99999999"

        # 저장
        bridge.save_workbook()

        # 재로딩 검증
        bridge = ExcelBridge(temp_excel_file)
        ws = bridge.get_worksheet("01_매매전략_기준설정")
        assert ws["B2"].value == "99999999"


class TestDataValidation:
    """데이터 검증 테스트"""

    def test_validate_tier_range(self, temp_excel_file):
        """Tier 범위 검증 (1-240)"""
        bridge = ExcelBridge(temp_excel_file)

        # 유효한 Tier
        position = Position(
            tier=1,
            quantity=10,
            avg_price=10.0,
            invested_amount=100.0,
            opened_at=datetime.now()
        )
        bridge.write_tier_position(position)  # 성공

        # 유효하지 않은 Tier
        invalid_position = Position(
            tier=241,  # 범위 초과
            quantity=10,
            avg_price=10.0,
            invested_amount=100.0,
            opened_at=datetime.now()
        )

        with pytest.raises(ValueError):
            bridge.write_tier_position(invalid_position)

    def test_validate_quantity_non_negative(self, temp_excel_file):
        """수량은 음수 불가"""
        bridge = ExcelBridge(temp_excel_file)

        position = Position(
            tier=1,
            quantity=-10,  # 음수
            avg_price=10.0,
            invested_amount=-100.0,
            opened_at=datetime.now()
        )

        with pytest.raises(ValueError):
            bridge.write_tier_position(position)


class TestPerformance:
    """성능 테스트"""

    def test_read_all_tiers_performance(self, temp_excel_file):
        """전체 Tier 읽기 성능 (240개)"""
        # 240개 Tier 데이터 생성
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]

        for tier in range(1, 241):
            row_idx = 17 + tier
            ws[f"H{row_idx}"] = 10
            ws[f"I{row_idx}"] = 100.0
            ws[f"J{row_idx}"] = 10.0

        wb.save(temp_excel_file)
        wb.close()

        # 성능 측정
        bridge = ExcelBridge(temp_excel_file)

        start = time.time()
        positions = bridge.read_tier_positions()
        duration = time.time() - start

        # 240개 읽기가 1초 이내여야 함
        assert len(positions) == 240
        assert duration < 1.0

    def test_save_workbook_performance(self, temp_excel_file):
        """Excel 저장 성능"""
        bridge = ExcelBridge(temp_excel_file)

        # 데이터 변경
        for tier in range(1, 11):
            position = Position(
                tier=tier,
                quantity=10,
                avg_price=10.0,
                invested_amount=100.0,
                opened_at=datetime.now()
            )
            bridge.write_tier_position(position)

        # 저장 성능 측정
        start = time.time()
        bridge.save_workbook()
        duration = time.time() - start

        # 저장이 2초 이내여야 함
        assert duration < 2.0


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_log_sheet(self, temp_excel_file):
        """빈 로그 시트"""
        bridge = ExcelBridge(temp_excel_file)

        # 로그 읽기 (헤더만 있음)
        ws = bridge.get_worksheet("02_운용로그_히스토리")
        assert ws.max_row == 1  # 헤더만

    def test_corrupted_cell_value(self, temp_excel_file):
        """손상된 셀 값 처리"""
        # 잘못된 데이터 입력
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["H18"] = "invalid"  # 숫자여야 하는데 문자열
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)

        # 에러 핸들링
        with pytest.raises((ValueError, TypeError)):
            bridge.read_tier_positions()

    def test_file_closed_after_operation(self, temp_excel_file):
        """작업 후 파일이 닫혀야 함"""
        bridge = ExcelBridge(temp_excel_file)
        bridge.save_workbook()

        # 파일이 다시 열릴 수 있어야 함
        bridge2 = ExcelBridge(temp_excel_file)
        assert bridge2.wb is not None


class TestBooleanParsing:
    """Bug #4 수정 검증: Boolean 파싱 테스트"""

    def test_read_bool_string_zero_is_false(self, temp_excel_file):
        """
        CRITICAL: 문자열 "0"은 False여야 함

        이전 버그: bool("0") = True (Python bool은 비어있지 않은 문자열을 True로 처리)
        수정 후: _read_bool("0") = False
        """
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B7"] = "0"  # 문자열 "0"
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        bridge.load_workbook()
        result = bridge._read_bool(bridge.ws_master["B7"])

        assert result == False, "문자열 '0'은 False여야 함"

    def test_read_bool_numeric_zero_is_false(self, temp_excel_file):
        """숫자 0은 False"""
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B7"] = 0  # 숫자 0
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        bridge.load_workbook()
        result = bridge._read_bool(bridge.ws_master["B7"])

        assert result == False

    def test_read_bool_string_one_is_true(self, temp_excel_file):
        """문자열 "1"은 True"""
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B7"] = "1"  # 문자열 "1"
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        bridge.load_workbook()
        result = bridge._read_bool(bridge.ws_master["B7"])

        assert result == True

    def test_read_bool_numeric_one_is_true(self, temp_excel_file):
        """숫자 1은 True"""
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B7"] = 1  # 숫자 1
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        bridge.load_workbook()
        result = bridge._read_bool(bridge.ws_master["B7"])

        assert result == True

    def test_read_bool_true_string_variants(self, temp_excel_file):
        """다양한 True 문자열 ("true", "yes", "y", "on")"""
        test_cases = ["true", "True", "TRUE", "yes", "YES", "y", "Y", "on", "ON"]

        for test_value in test_cases:
            wb = openpyxl.load_workbook(temp_excel_file)
            ws = wb["01_매매전략_기준설정"]
            ws["B7"] = test_value
            wb.save(temp_excel_file)
            wb.close()

            bridge = ExcelBridge(temp_excel_file)
            bridge.load_workbook()
            result = bridge._read_bool(bridge.ws_master["B7"])

            assert result == True, f"'{test_value}'는 True여야 함"

    def test_read_bool_false_string_variants(self, temp_excel_file):
        """다양한 False 문자열 ("false", "no", "n", "off")"""
        test_cases = ["false", "False", "FALSE", "no", "NO", "n", "N", "off", "OFF", ""]

        for test_value in test_cases:
            wb = openpyxl.load_workbook(temp_excel_file)
            ws = wb["01_매매전략_기준설정"]
            ws["B7"] = test_value
            wb.save(temp_excel_file)
            wb.close()

            bridge = ExcelBridge(temp_excel_file)
            bridge.load_workbook()
            result = bridge._read_bool(bridge.ws_master["B7"])

            assert result == False, f"'{test_value}'는 False여야 함"

    def test_read_bool_none_is_false(self, temp_excel_file):
        """None 값은 False"""
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B7"] = None
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        bridge.load_workbook()
        result = bridge._read_bool(bridge.ws_master["B7"])

        assert result == False

    def test_read_bool_unknown_string_defaults_to_false(self, temp_excel_file):
        """알 수 없는 문자열은 False로 기본값 (경고 로그 발생)"""
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]
        ws["B7"] = "unknown_value"
        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        bridge.load_workbook()

        with pytest.warns(UserWarning):  # 경고 로그 발생 예상
            result = bridge._read_bool(bridge.ws_master["B7"])

        assert result == False, "알 수 없는 값은 False로 기본값"

    def test_load_settings_uses_read_bool(self, temp_excel_file):
        """
        load_settings()가 _read_bool()을 사용하는지 검증

        실제 설정 로드 시 Boolean 파싱이 올바르게 동작하는지 확인
        """
        wb = openpyxl.load_workbook(temp_excel_file)
        ws = wb["01_매매전략_기준설정"]

        # 모든 Boolean 설정을 문자열 "0"으로 설정
        ws["B7"] = "0"   # tier1_auto_update
        ws["B8"] = "0"   # tier1_trading_enabled
        ws["B9"] = "0"   # buy_limit
        ws["B10"] = "0"  # sell_limit
        ws["B15"] = "0"  # telegram_enabled

        wb.save(temp_excel_file)
        wb.close()

        bridge = ExcelBridge(temp_excel_file)
        settings = bridge.load_settings()

        # 모두 False여야 함
        assert settings.tier1_auto_update == False
        assert settings.tier1_trading_enabled == False
        assert settings.telegram_enabled == False
