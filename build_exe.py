"""
Phoenix Trading System - EXE 빌드 스크립트 v2.0
Debug/Release 모드, Pre/Post Validation 지원

사용법:
    python build_exe.py --mode=debug              # 빠른 개발/테스트
    python build_exe.py --mode=release            # 배포용
    python build_exe.py --mode=release --full-validation  # 전체 검증
"""
import argparse
import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime


class BuildMode:
    """빌드 모드 상수"""
    DEBUG = "debug"
    RELEASE = "release"


def clean_build_artifacts():
    """이전 빌드 산출물 정리"""
    print("")
    print("=" * 60)
    print("이전 빌드 산출물 정리 중...")
    print("=" * 60)

    artifacts = ['build', 'dist', 'debug', '__pycache__']

    for artifact in artifacts:
        if Path(artifact).exists():
            print(f"삭제: {artifact}/")
            shutil.rmtree(artifact, ignore_errors=True)

    # .spec 파일 삭제
    for spec_file in Path('.').glob('*.spec'):
        print(f"삭제: {spec_file}")
        spec_file.unlink()

    print("[OK] 정리 완료")
    print("")


def run_pre_build_validation() -> bool:
    """
    Pre-Build Validation 실행

    Returns:
        bool: 검증 통과 시 True
    """
    print("=" * 60)
    print("Pre-Build Validation 실행 중...")
    print("=" * 60)
    print("")

    result = subprocess.run([sys.executable, "build_validation.py"])

    if result.returncode != 0:
        print("")
        print("[FAIL] Pre-Build Validation 실패!")
        print("빌드를 계속하려면 위 에러를 먼저 수정하세요.")
        return False

    print("")
    print("[OK] Pre-Build Validation 통과")
    print("")
    return True


def build_exe(mode: str = BuildMode.RELEASE) -> tuple[bool, Path]:
    """
    EXE 빌드

    Args:
        mode: BuildMode.DEBUG 또는 BuildMode.RELEASE

    Returns:
        tuple: (성공 여부, 출력 폴더 경로)
    """
    print("=" * 60)
    print(f"EXE 빌드 시작 (모드: {mode})")
    print("=" * 60)
    print("")

    # 기본 PyInstaller 명령
    base_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=PhoenixTrading",
        "--console",
        "--add-data=src;src",

        # Hidden imports
        "--hidden-import=openpyxl",
        "--hidden-import=openpyxl.cell._writer",
        "--hidden-import=requests",
        "--hidden-import=websockets",
        "--hidden-import=dataclasses",

        # 제외 모듈 (크기 최적화)
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=pandas",
        "--exclude-module=scipy",
        "--exclude-module=pytest",
        "--exclude-module=black",
        "--exclude-module=flake8",

        # 빌드 옵션
        "--clean",
        "--noconfirm"
    ]

    # Debug vs Release 모드
    if mode == BuildMode.DEBUG:
        mode_cmd = [
            "--onedir",      # 폴더 형태 (빠른 빌드)
            "--debug=all",   # 디버그 정보
            "--distpath=debug"  # debug/ 폴더에 출력
        ]
        output_base = Path("debug")
    else:
        mode_cmd = [
            "--onefile"      # 단일 EXE
        ]
        output_base = Path("dist")

    cmd = base_cmd + mode_cmd + ["phoenix_main.py"]

    print("빌드 명령:")
    print(" ".join(cmd))
    print("")

    # 빌드 실행
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("")
        print("[OK] 빌드 성공!")
        print("")
        return True, output_base
    else:
        print("")
        print("[FAIL] 빌드 실패!")
        print("")
        return False, None


def run_post_build_tests() -> bool:
    """
    Post-Build Testing 실행

    Returns:
        bool: 테스트 통과 시 True
    """
    print("=" * 60)
    print("Post-Build Testing 실행 중...")
    print("=" * 60)
    print("")

    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/test_build_validation.py",
        "-v",
        "--tb=short"
    ])

    if result.returncode != 0:
        print("")
        print("[FAIL] Post-Build Testing 실패!")
        print("")
        return False

    print("")
    print("[OK] Post-Build Testing 통과")
    print("")
    return True


def run_full_test_suite() -> bool:
    """
    전체 테스트 스위트 실행 (94개 pytest)

    Returns:
        bool: 전체 테스트 통과 시 True
    """
    print("=" * 60)
    print("전체 테스트 스위트 실행 중... (94 tests)")
    print("=" * 60)
    print("")

    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-x"  # 첫 실패 시 중단
    ])

    if result.returncode != 0:
        print("")
        print("[FAIL] 전체 테스트 실패!")
        print("")
        return False

    print("")
    print("[OK] 전체 테스트 통과 (94 passed)")
    print("")
    return True


def create_package(mode: str) -> Path:
    """
    배포 패키지 생성

    Args:
        mode: BuildMode.DEBUG 또는 BuildMode.RELEASE

    Returns:
        Path: 패키지 폴더 경로
    """
    print("=" * 60)
    print("배포 패키지 생성 중...")
    print("=" * 60)
    print("")

    if mode == BuildMode.DEBUG:
        source_dir = Path("debug") / "PhoenixTrading"
        package_dir = Path("debug_package")
    else:
        source_dir = Path("dist")
        package_dir = Path("release")

    # 패키지 폴더 생성
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()

    # EXE 복사
    if mode == BuildMode.DEBUG:
        # Debug 모드: 폴더 전체 복사
        exe_folder = source_dir
        shutil.copytree(exe_folder, package_dir / "PhoenixTrading")
        print("  [OK] Debug 폴더 전체 복사")
    else:
        # Release 모드: EXE 파일만 복사
        exe_file = source_dir / "PhoenixTrading.exe"
        shutil.copy(exe_file, package_dir / "PhoenixTrading.exe")
        print("  [OK] PhoenixTrading.exe")

    # Excel 템플릿 복사
    excel_template = Path("phoenix_grid_template_v3.xlsx")
    if excel_template.exists():
        shutil.copy(excel_template, package_dir / "phoenix_grid_template_v3.xlsx")
        print("  [OK] phoenix_grid_template_v3.xlsx")
    else:
        print("  [WARNING]  Excel 템플릿 없음 (create_excel_template.py 실행 권장)")

    # README 복사
    readme = Path("README_배포용.txt")
    if readme.exists():
        shutil.copy(readme, package_dir / "README_사용방법.txt")
        print("  [OK] README_사용방법.txt")

    # logs 폴더 생성
    (package_dir / "logs").mkdir(exist_ok=True)
    print("  [OK] logs/ (빈 폴더)")

    # 빌드 정보 파일 생성
    build_info = package_dir / f"BUILD_INFO_{mode}.txt"
    with open(build_info, 'w', encoding='utf-8') as f:
        f.write(f"Build Mode: {mode}\n")
        f.write(f"Build Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Python Version: {sys.version}\n")
        f.write(f"Platform: {sys.platform}\n")
    print(f"  [OK] BUILD_INFO_{mode}.txt")

    print("")
    print(f"[OK] 배포 패키지: {package_dir.absolute()}")
    print("")

    return package_dir


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Phoenix Trading System EXE 빌드 스크립트 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python build_exe.py --mode=debug
  python build_exe.py --mode=release
  python build_exe.py --mode=release --full-validation
  python build_exe.py --mode=debug --skip-validation --skip-post-tests
        """
    )

    parser.add_argument(
        "--mode",
        choices=[BuildMode.DEBUG, BuildMode.RELEASE],
        default=BuildMode.DEBUG,
        help="빌드 모드 (debug=빠른 테스트, release=배포용)"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Pre-Build Validation 건너뛰기"
    )
    parser.add_argument(
        "--skip-post-tests",
        action="store_true",
        help="Post-Build Testing 건너뛰기"
    )
    parser.add_argument(
        "--skip-full-tests",
        action="store_true",
        help="전체 테스트 스위트 건너뛰기 (94 tests)"
    )
    parser.add_argument(
        "--full-validation",
        action="store_true",
        help="모든 검증 수행 (Release 배포 전 권장)"
    )

    args = parser.parse_args()

    # 헤더
    print("")
    print("=" * 60)
    print("Phoenix Trading System - EXE 빌드 스크립트 v2.0")
    print("=" * 60)
    print("")

    # 1. 정리
    clean_build_artifacts()

    # 2. Pre-Build Validation
    if not args.skip_validation:
        if not run_pre_build_validation():
            print("[FAIL] 빌드 중단 (Pre-Build Validation 실패)")
            return 1

    # 3. 빌드
    success, output_dir = build_exe(args.mode)
    if not success:
        print("[FAIL] 빌드 실패")
        return 1

    # 4. Post-Build Testing
    if not args.skip_post_tests:
        if not run_post_build_tests():
            print("[WARNING]  Post-Build Testing 실패 (빌드는 완료됨)")
            if args.mode == BuildMode.RELEASE:
                print("[FAIL] Release 빌드는 테스트 통과 필수!")
                return 1

    # 5. 전체 테스트 스위트 (--full-validation 시)
    if args.full_validation and not args.skip_full_tests:
        if not run_full_test_suite():
            print("[FAIL] 전체 테스트 실패")
            return 1

    # 6. 배포 패키지 생성
    package_dir = create_package(args.mode)

    # 최종 결과
    print("=" * 60)
    print("[SUCCESS] 모든 작업 완료!")
    print("=" * 60)
    print("")

    if args.mode == BuildMode.DEBUG:
        print(f"[DIR] Debug 패키지: {package_dir}/")
        print("   → 개발/테스트용")
        print("")
        print("다음 단계:")
        print("  1. debug_package/PhoenixTrading/PhoenixTrading.exe 실행")
        print("  2. 테스트 후 --mode=release로 배포용 빌드")
    else:
        print(f"[DIR] Release 패키지: {package_dir}/")
        print("   → 사용자 배포 준비 완료")
        print("")
        print("다음 단계:")
        print("  1. release/ 폴더를 ZIP으로 압축")
        print("  2. 사용자에게 전달")

    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
