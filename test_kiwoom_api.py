"""
키움 OpenAPI 설치 확인 테스트 스크립트
Phoenix Trading System v3.1 (CUSTOM)

이 스크립트는 키움 OpenAPI가 올바르게 설치되었는지 확인합니다.
"""
import sys
import struct

def check_python_architecture():
    """Python 비트 확인"""
    bits = struct.calcsize("P") * 8
    return bits

def test_pyqt5():
    """PyQt5 설치 확인"""
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QAxContainer import QAxWidget
        return True
    except ImportError as e:
        print(f"[ERROR] PyQt5 설치 안 됨: {e}")
        print("[FIX] pip install PyQt5")
        return False

def test_kiwoom_api():
    """키움 OpenAPI 설치 확인"""
    print("=" * 70)
    print("키움 OpenAPI 설치 확인 테스트")
    print("Phoenix Trading System v3.1 (CUSTOM)")
    print("=" * 70)
    print()

    # 1. Python 비트 확인
    print("[1/4] Python 아키텍처 확인 중...")
    bits = check_python_architecture()
    print(f"      현재 Python: {bits}비트")

    if bits != 32:
        print(f"      ❌ 경고: {bits}비트 Python은 키움 OpenAPI와 호환되지 않습니다!")
        print(f"      ⚠️  키움 OpenAPI는 32비트 Python이 필수입니다.")
        print(f"      ⚠️  Phoenix EXE 빌드 시 문제가 발생할 수 있습니다.")
        print()
        print(f"      해결: 32비트 Python 재설치")
        print(f"      다운로드: https://www.python.org/downloads/")
        print()
    else:
        print(f"      ✅ 32비트 Python 확인 완료")
    print()

    # 2. PyQt5 설치 확인
    print("[2/4] PyQt5 설치 확인 중...")
    if not test_pyqt5():
        print("      ❌ PyQt5 설치 필요")
        print()
        return False
    print("      ✅ PyQt5 설치 확인 완료")
    print()

    # 3. QApplication 생성
    print("[3/4] QApplication 생성 중...")
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        print("      ✅ QApplication 생성 완료")
    except Exception as e:
        print(f"      ❌ QApplication 생성 실패: {e}")
        return False
    print()

    # 4. OpenAPI 컨트롤 생성
    print("[4/4] 키움 OpenAPI 컨트롤 생성 중...")
    try:
        from PyQt5.QAxContainer import QAxWidget
        ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        print("      ✅ OpenAPI 컨트롤 생성 완료")
        print()

        # API 경로 확인
        try:
            api_path = ocx.dynamicCall("GetAPIModulePath()")
            print(f"      OpenAPI 설치 경로: {api_path}")
        except:
            print("      OpenAPI 설치 경로: 확인 불가 (정상)")

        print()
        print("=" * 70)
        print("✅ 키움 OpenAPI 설치 확인 완료!")
        print("=" * 70)
        print()
        print("다음 단계:")
        print("  1. Excel 템플릿 설정 (phoenix_grid_template_v3.xlsx)")
        print("  2. Phoenix Trading System 실행 (python main.py)")
        print()
        return True

    except Exception as e:
        print(f"      ❌ OpenAPI 컨트롤 생성 실패")
        print()
        print("=" * 70)
        print("❌ 키움 OpenAPI 설치 필요 또는 오류")
        print("=" * 70)
        print()
        print(f"오류 상세: {e}")
        print()
        print("해결 방법:")
        print()
        print("1. 키움 OpenAPI+ 설치 확인")
        print("   - 제어판 → 프로그램 및 기능")
        print("   - 'Kiwoom Open API+' 항목 확인")
        print()
        print("2. 키움 OpenAPI+ 설치 (미설치 시)")
        print("   - 다운로드: https://www.kiwoom.com/h/customer/download/VOpenApiInfoView")
        print("   - 관리자 권한으로 설치")
        print("   - 컴퓨터 재시작")
        print()
        print("3. 32비트 Python 사용 확인")
        print(f"   - 현재: {bits}비트")
        print("   - 필요: 32비트")
        print()
        print("4. COM 등록 확인 (고급)")
        print("   - 명령 프롬프트(관리자)")
        print("   - cd C:\\OpenAPI")
        print("   - regsvr32 KHOpenAPI.ocx")
        print()
        print("상세 가이드: docs/키움OpenAPI설치가이드.md")
        print()
        return False


def main():
    """메인 함수"""
    try:
        success = test_kiwoom_api()

        if not success:
            print("=" * 70)
            print("테스트 실패. 위 해결 방법을 따라 문제를 해결하세요.")
            print("=" * 70)
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n테스트 중단됨 (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
