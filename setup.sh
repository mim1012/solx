#!/bin/bash

echo "================================================"
echo "Phoenix Trading System v4.1 설치 스크립트"
echo "================================================"
echo

# 현재 디렉토리 확인
CURRENT_DIR=$(pwd)
echo "설치 경로: $CURRENT_DIR"

# 1. .env 파일 생성 확인
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
    echo
    echo "📋 다음 파일을 편집하여 설정을 완료하세요:"
    echo "  1. .env 파일 - API 키 및 계좌번호 설정"
    echo "  2. phoenix_grid_template_v3.xlsx - 거래 설정"
fi

# 2. Python 패키지 설치 확인
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

# 3. 가상 환경 생성 (선택사항)
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

# 4. 필수 패키지 설치
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
echo "문제 발생 시 README_배포용.txt 참조"