@echo off
chcp 65001 >nul
title Phoenix Trading System v4.1 - 사전 빌드된 EXE
echo ================================================
echo  Phoenix Trading System v4.1 (사전 빌드 버전)
echo ================================================
echo.
echo 이 파일은 Phoenix Trading System의 사전 빌드된 버전입니다.
echo.
echo 주요 기능:
echo - 잔고 부족 오류 해결 (SOXL -> AMS 거래소)
echo - 잔고 자동 동기화
echo - config.py 메모장 수정 가능
echo - Python 설치 불필요
echo.
echo ================================================
echo.

REM 설정 파일 확인
if not exist .env (
    echo [설정 필요] .env 파일이 없습니다.
    echo.
    if exist .env.example (
        echo .env.example 파일을 .env로 복사합니다...
        copy .env.example .env
        echo.
        echo .env 파일이 생성되었습니다.
        echo 메모장으로 .env 파일을 열어 다음을 설정해주세요:
        echo.
        echo KIS_APP_KEY=여기에_당신의_KIS_앱_키
        echo KIS_APP_SECRET=여기에_당신의_KIS_앱_시크릿
        echo KIS_ACCOUNT_NO=여기에_당신의_계좌번호
        echo US_MARKET_EXCHANGE=AMS
        echo.
        timeout /t 10 /nobreak >nul
        echo 계속하려면 아무 키나 누르세요...
        pause >nul
    ) else (
        echo [오류] .env.example 파일도 없습니다.
        pause
        exit /b 1
    )
)

if not exist config.py (
    echo [오류] config.py 파일이 없습니다.
    pause
    exit /b 1
)

echo [정보] 설정 파일 확인 완료
echo.

REM Python 확인
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [주의] Python이 설치되지 않았습니다.
    echo 이 버전은 Python이 필요합니다.
    echo.
    echo Python 설치 방법:
    echo 1. https://www.python.org/downloads/
    echo 2. Python 3.8 이상 (64비트) 다운로드
    echo 3. 설치 시 "Add Python to PATH" 반드시 체크
    echo 4. 설치 후 이 프로그램 재실행
    echo.
    pause
    exit /b 1
)

echo [정보] Python 설치 확인: 
python --version
echo.

REM 가상 환경 확인/생성
if not exist venv (
    echo [준비] 가상 환경 생성 중...
    python -m venv venv
    if %errorLevel% neq 0 (
        echo [오류] 가상 환경 생성 실패
        pause
        exit /b 1
    )
    echo [성공] 가상 환경 생성 완료
)

echo [준비] 가상 환경 활성화...
call venv\Scripts\activate.bat
if %errorLevel% neq 0 (
    echo [오류] 가상 환경 활성화 실패
    pause
    exit /b 1
)

REM 패키지 설치 확인
echo [준비] 필수 패키지 확인 중...
pip install --upgrade pip >nul 2>&1

REM requirements.txt 확인
if exist requirements.txt (
    echo [준비] 패키지 설치 중... (잠시 기다려주세요)
    pip install -r requirements.txt >nul 2>&1
    if %errorLevel% neq 0 (
        echo [경고] 일부 패키지 설치 실패, 계속 진행...
    )
)

echo.
echo ================================================
echo  Phoenix Trading System 시작
echo ================================================
echo.
echo [시스템] 프로그램 실행 중...
echo [로그] 아래에 실시간 로그가 표시됩니다:
echo ================================================
echo.

REM 메인 프로그램 실행
python phoenix_main.py

echo.
echo ================================================
echo  프로그램 종료
echo ================================================
echo.
echo 종료 코드: %errorlevel%
echo.
if %errorlevel% equ 0 (
    echo [성공] 정상 종료
) else (
    echo [오류] 비정상 종료 (코드: %errorlevel%)
)

echo.
echo 로그 파일은 logs\ 폴더에서 확인할 수 있습니다.
echo.
pause