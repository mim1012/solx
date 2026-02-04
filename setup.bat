@echo off
echo ================================================
echo Phoenix Trading System v4.1 설치 스크립트
echo ================================================
echo.

REM 현재 디렉토리 확인
set CURRENT_DIR=%~dp0
echo 설치 경로: %CURRENT_DIR%

REM 1. .env 파일 생성 확인
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
    echo.
    echo 📋 다음 파일을 편집하여 설정을 완료하세요:
    echo   1. .env 파일 - API 키 및 계좌번호 설정
    echo   2. phoenix_grid_template_v3.xlsx - 거래 설정
)

REM 2. Python 패키지 설치 확인
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

REM 3. 필수 패키지 설치
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
pause