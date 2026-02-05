#!/usr/bin/env python3
"""
Phoenix Trading System v4.1 패키지 재구성 스크립트
이 스크립트를 실행하면 모든 파일이 재구성됩니다.
"""
import os
import sys
import zipfile
from pathlib import Path
import base64

def create_file_structure():
    """파일 구조 생성"""
    print("=" * 60)
    print("Phoenix Trading System v4.1 패키지 재구성")
    print("=" * 60)
    
    # 현재 디렉토리
    current_dir = Path.cwd()
    print(f"작업 디렉토리: {current_dir}")
    
    # 파일 목록과 내용
    files = {
        # 설치 스크립트
        "setup.bat": """@echo off
echo ================================================
echo Phoenix Trading System v4.1 설치 스크립트
echo ================================================
echo.

set CURRENT_DIR=%~dp0
echo 설치 경로: %CURRENT_DIR%

echo.
echo [1/3] 환경 설정 파일 확인...
if exist ".env" (
    echo ✅ .env 파일이 이미 존재합니다.
) else (
    echo 📝 .env.example 파일을 .env로 복사합니다...
    copy ".env.example" ".env" > nul
    if errorlevel 1 (
        echo ❌ .env 파일 생성 실패
        pause
        exit /b 1
    )
    echo ✅ .env 파일 생성 완료
)

echo.
echo [2/3] Python 패키지 확인...
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았습니다.
    echo 다음 링크에서 Python 3.8+ 설치: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python 설치 확인: 
python --version

echo.
echo [3/3] 필수 패키지 설치...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 패키지 설치 실패
    echo 수동 설치 명령: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo ================================================
echo ✅ 설치 완료!
echo ================================================
echo.
echo 다음 단계:
echo 1. .env 파일 편집 - API 키 및 계좌번호 설정
echo 2. phoenix_grid_template_v3.xlsx 편집 - 거래 설정
echo 3. 테스트 실행: python test_config.py
echo 4. 테스트 실행: python test_kis_fix.py
echo 5. 메인 실행: python phoenix_main.py
echo.
echo 문제 발생 시 README_배포용.txt 참조
pause""",
        
        "setup.sh": """#!/bin/bash

echo "================================================"
echo "Phoenix Trading System v4.1 설치 스크립트"
echo "================================================"
echo

CURRENT_DIR=$(pwd)
echo "설치 경로: $CURRENT_DIR"

echo
echo "[1/3] 환경 설정 파일 확인..."
if [ -f ".env" ]; then
    echo "✅ .env 파일이 이미 존재합니다."
else
    echo "📝 .env.example 파일을 .env로 복사합니다..."
    cp ".env.example" ".env"
    if [ $? -ne 0 ]; then
        echo "❌ .env 파일 생성 실패"
        exit 1
    fi
    echo "✅ .env 파일 생성 완료"
fi

echo
echo "[2/3] Python 패키지 확인..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3이 설치되지 않았습니다."
    echo "다음 명령으로 설치:"
    echo "  macOS: brew install python"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    exit 1
fi

echo "✅ Python 설치 확인:"
python3 --version

echo
read -p "가상 환경을 생성하시겠습니까? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 가상 환경 생성 중..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ 가상 환경 생성 실패"
        exit 1
    fi
    echo "✅ 가상 환경 생성 완료"
    echo "가상 환경 활성화: source venv/bin/activate"
    source venv/bin/activate
fi

echo
echo "[3/3] 필수 패키지 설치..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ 패키지 설치 실패"
    echo "수동 설치 명령: pip3 install -r requirements.txt"
    exit 1
fi

echo
echo "================================================"
echo "✅ 설치 완료!"
echo "================================================"
echo
echo "다음 단계:"
echo "1. .env 파일 편집 - API 키 및 계좌번호 설정"
echo "   nano .env  또는  vim .env"
echo "2. phoenix_grid_template_v3.xlsx 편집 - 거래 설정"
echo "3. 테스트 실행: python3 test_config.py"
echo "4. 테스트 실행: python3 test_kis_fix.py"
echo "5. 메인 실행: python3 phoenix_main.py"
echo
echo "문제 발생 시 README_배포용.txt 참조" """,
        
        # 계속해서 다른 파일들 추가...
    }
    
    # 파일 생성
    print("\n📁 파일 생성 중...")
    created_count = 0
    
    for filename, content in files.items():
        filepath = current_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 실행 권한 부여 (sh 파일)
        if filename.endswith('.sh'):
            os.chmod(filepath, 0o755)
        
        created_count += 1
        print(f"  ✅ {filename}")
    
    print(f"\n✅ {created_count}개 파일 생성 완료")
    
    # requirements.txt 생성
    requirements_content = """requests>=2.28.0
python-dotenv>=1.0.0
openpyxl>=3.1.0
websockets>=11.0.0
"""
    
    req_file = current_dir / "requirements.txt"
    with open(req_file, 'w') as f:
        f.write(requirements_content)
    print("✅ requirements.txt 생성 완료")
    
    print("\n" + "=" * 60)
    print("🎉 패키지 재구성 완료!")
    print("=" * 60)
    print("\n다음 명령 실행:")
    print("1. Windows: setup.bat")
    print("2. macOS/Linux: chmod +x setup.sh && ./setup.sh")
    print("3. .env.example을 .env로 복사 후 설정")
    print("4. 테스트: python test_config.py")
    
    return True

if __name__ == "__main__":
    create_file_structure()