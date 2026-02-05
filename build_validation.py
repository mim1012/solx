"""
Phoenix Trading System - 빌드 전 검증 스크립트
Pre-Build Validation: 빌드 시작 전 환경 및 소스 코드 검증
"""
import sys
import importlib
from pathlib import Path
import ast


class PreBuildValidator:
    """빌드 전 검증 수행"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_all(self) -> bool:
        """
        모든 검증 실행

        Returns:
            bool: 모든 검증 통과 시 True
        """
        checks = [
            ("Python 버전", self.validate_python_version),
            ("필수 패키지", self.validate_dependencies),
            ("소스 코드 문법", self.validate_source_syntax),
            ("Excel 템플릿", self.validate_excel_template),
            ("Import 트리", self.validate_imports)
        ]

        all_passed = True

        for name, check in checks:
            print(f"[검증] {name}...", end=" ")
            if not check():
                print("[FAIL]")
                all_passed = False
            else:
                print("[PASS]")

        return all_passed

    def validate_python_version(self) -> bool:
        """
        Python 버전 확인 (3.8+ 64bit 권장)

        Returns:
            bool: 검증 통과 시 True
        """
        # Python 3.8+ 확인
        if sys.version_info < (3, 8):
            self.errors.append(f"Python 3.8+ 필요 (현재: {sys.version_info.major}.{sys.version_info.minor})")
            return False

        # 64비트 확인 (권장)
        import platform
        if platform.architecture()[0] != '64bit':
            self.warnings.append("64비트 Python 권장 (KIS REST API 최적화)")

        return True

    def validate_dependencies(self) -> bool:
        """
        필수 패키지 설치 확인

        Returns:
            bool: 모든 패키지 설치 시 True
        """
        # 패키지명 → import 이름 매핑 (대소문자 구분)
        required_packages = {
            'openpyxl': 'openpyxl',
            'requests': 'requests',
            'websockets': 'websockets',
            'PyInstaller': 'PyInstaller'  # 대문자 P 유지
        }

        missing = []
        for package_name, import_name in required_packages.items():
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing.append(package_name)

        if missing:
            self.errors.append(f"누락된 패키지: {', '.join(missing)}")
            self.errors.append("실행: pip install -r requirements.txt")
            return False

        return True

    def validate_source_syntax(self) -> bool:
        """
        소스 코드 문법 검사 (AST 파싱)

        Returns:
            bool: 모든 파일 문법 정상 시 True
        """
        source_files = [
            Path("phoenix_main.py"),
            Path("config.py"),
            *list(Path("src").glob("*.py"))
        ]

        for file_path in source_files:
            if not file_path.exists():
                # 파일이 없으면 건너뛰기
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                    ast.parse(source_code)
            except SyntaxError as e:
                self.errors.append(f"{file_path.name}:{e.lineno} - {e.msg}")
                return False
            except Exception as e:
                self.errors.append(f"{file_path.name} 읽기 실패: {e}")
                return False

        return True

    def validate_excel_template(self) -> bool:
        """
        Excel 템플릿 유효성 검사

        Returns:
            bool: Excel 템플릿 정상 시 True (없으면 경고만)
        """
        template_path = Path("phoenix_grid_template_v3.xlsx")

        if not template_path.exists():
            self.warnings.append("Excel 템플릿이 없습니다 (create_excel_template.py 실행 권장)")
            return True  # 경고만, 검증은 통과

        try:
            import openpyxl
            wb = openpyxl.load_workbook(template_path, read_only=True, data_only=True)

            # 필수 시트 확인
            required_sheets = ["01_매매전략_기준설정", "02_운용로그_히스토리"]
            for sheet_name in required_sheets:
                if sheet_name not in wb.sheetnames:
                    self.errors.append(f"필수 시트 없음: {sheet_name}")
                    wb.close()
                    return False

            wb.close()
            return True

        except Exception as e:
            self.errors.append(f"Excel 템플릿 검증 실패: {e}")
            return False

    def validate_imports(self) -> bool:
        """
        Import 순환 참조 및 모듈 로드 확인

        Returns:
            bool: 모든 모듈 import 가능 시 True
        """
        try:
            # 메인 모듈
            import phoenix_main
            import config

            # src 모듈
            from src import excel_bridge
            from src import grid_engine
            from src import kis_rest_adapter
            from src import models
            from src import telegram_notifier

            return True

        except ImportError as e:
            self.errors.append(f"Import 실패: {e}")
            self.errors.append("Python 경로가 올바른지 확인하세요")
            return False
        except Exception as e:
            self.errors.append(f"모듈 로드 에러: {e}")
            return False

    def print_summary(self):
        """검증 결과 요약 출력"""
        print("")
        print("=" * 60)

        if self.warnings:
            print("[WARNING]:")
            for warning in self.warnings:
                print(f"  - {warning}")
            print("")

        if self.errors:
            print("[ERROR]:")
            for error in self.errors:
                print(f"  - {error}")
            print("")


def main():
    """메인 함수"""
    print("")
    print("=" * 60)
    print("Phoenix Trading System - Pre-Build Validation")
    print("=" * 60)
    print("")

    validator = PreBuildValidator()

    # 검증 실행
    success = validator.validate_all()

    # 결과 요약
    validator.print_summary()

    if success:
        print("[PASS] Pre-Build Validation 통과!")
        print("=" * 60)
        print("")
        return 0
    else:
        print("[FAIL] Pre-Build Validation 실패!")
        print("=" * 60)
        print("")
        print("빌드를 계속하려면 위 에러를 먼저 수정하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
