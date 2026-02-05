#!/usr/bin/env python3
"""
릴리즈 패키지 생성 스크립트
"""
import os
import sys
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_release_package():
    """릴리즈 패키지 생성"""
    print("=" * 60)
    print("Phoenix Trading System v4.1 - 릴리즈 패키지 생성")
    print("=" * 60)
    
    # 기본 경로 설정
    project_root = Path(__file__).parent
    release_dir = project_root / "release"
    package_name = f"PhoenixTrading_v4.1_{datetime.now().strftime('%Y%m%d')}"
    zip_path = release_dir / f"{package_name}.zip"
    
    # 릴리즈 디렉토리 생성
    release_dir.mkdir(exist_ok=True)
    
    # 포함할 파일 목록
    include_files = [
        # 핵심 파일
        "phoenix_main.py",
        "config.py",
        "requirements.txt",
        "requirements_build.txt",
        
        # 템플릿 및 설정
        "phoenix_grid_template_v3.xlsx",
        ".env.example",
        
        # 문서
        "README_배포용.txt",
        "QUICK_START_GUIDE.md",
        "24시간_테스트_빠른시작.md",
        "GRID_ENGINE_V4_QUICK_START.md",
        
        # 설치 스크립트
        "setup.bat",
        "setup.sh",
        
        # 테스트 스크립트
        "test_config.py",
        "test_kis_fix.py",
        "test_paper_trading_v4.py",
        
        # 소스 코드
        "src/",
        "tier_state_machine.py",
        
        # 기타 문서
        "CODE_REVIEW_SUMMARY.md",
        "EXCEL_KIS_TESTING_GUIDE.md",
    ]
    
    # 제외할 파일/디렉토리
    exclude_patterns = [
        "__pycache__",
        ".git",
        ".gitignore",
        ".claude",
        "*.log",
        "logs/",
        "release/",
        "venv/",
        ".env",  # 사용자 설정 파일은 제외
    ]
    
    print("\n[1/4] 파일 검사 중...")
    
    # 필수 파일 확인
    missing_files = []
    for file_pattern in include_files:
        if file_pattern.endswith("/"):
            # 디렉토리
            dir_path = project_root / file_pattern.rstrip("/")
            if not dir_path.exists():
                missing_files.append(str(file_pattern))
        else:
            # 파일
            file_path = project_root / file_pattern
            if not file_path.exists():
                missing_files.append(file_pattern)
    
    if missing_files:
        print("❌ 다음 파일/디렉토리가 없습니다:")
        for missing in missing_files:
            print(f"  - {missing}")
        return False
    
    print("✅ 모든 필수 파일 확인 완료")
    
    # 임시 패키지 디렉토리 생성
    print("\n[2/4] 임시 패키지 디렉토리 생성 중...")
    temp_dir = release_dir / package_name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    # 파일 복사
    print("\n[3/4] 파일 복사 중...")
    copied_count = 0
    
    for file_pattern in include_files:
        if file_pattern.endswith("/"):
            # 디렉토리 복사
            src_dir = project_root / file_pattern.rstrip("/")
            dst_dir = temp_dir / file_pattern.rstrip("/")
            
            if src_dir.exists():
                # 디렉토리 내부 파일 필터링
                for root, dirs, files in os.walk(src_dir):
                    # 제외 패턴 필터링
                    dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
                    files[:] = [f for f in files if not any(pattern in f for pattern in exclude_patterns)]
                    
                    for file in files:
                        src_file = Path(root) / file
                        rel_path = src_file.relative_to(src_dir)
                        dst_file = dst_dir / rel_path
                        
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
        else:
            # 파일 복사
            src_file = project_root / file_pattern
            dst_file = temp_dir / file_pattern
            
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied_count += 1
    
    print(f"✅ {copied_count}개 파일 복사 완료")
    
    # ZIP 파일 생성
    print("\n[4/4] ZIP 파일 생성 중...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            # 제외 패턴 필터링
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
            files[:] = [f for f in files if not any(pattern in f for pattern in exclude_patterns)]
            
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(temp_dir)
                zipf.write(file_path, arcname)
    
    # 임시 디렉토리 정리
    shutil.rmtree(temp_dir)
    
    # 파일 크기 확인
    file_size = zip_path.stat().st_size / (1024 * 1024)  # MB 단위
    
    print(f"\n✅ 릴리즈 패키지 생성 완료!")
    print(f"   파일: {zip_path.name}")
    print(f"   크기: {file_size:.2f} MB")
    print(f"   경로: {zip_path}")
    
    # 포함된 파일 목록 출력
    print("\n📦 패키지 내용:")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        file_list = zipf.namelist()
        for file in sorted(file_list):
            if not file.endswith('/'):  # 디렉토리 제외
                print(f"  - {file}")
    
    print("\n" + "=" * 60)
    print("📋 배포 준비 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print(f"1. {zip_path.name} 파일 배포")
    print("2. 사용자는 setup.bat/setup.sh 실행")
    print("3. .env 파일과 Excel 템플릿 설정")
    print("4. test_config.py, test_kis_fix.py 실행 테스트")
    print("5. phoenix_main.py 실행")
    
    return True

if __name__ == "__main__":
    success = create_release_package()
    sys.exit(0 if success else 1)