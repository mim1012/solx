@echo off
chcp 65001 >nul 2>&1
title USD 예수금 조회

cd /d "%~dp0"

echo.
echo ================================================
echo   한국투자증권 USD 예수금 조회
echo   (파이썬 설치 불필요)
echo ================================================
echo.

check_usd_balance.exe

if errorlevel 1 (
    echo.
    echo [오류] 프로그램 실행 중 문제가 발생했습니다.
    echo.
)

pause
