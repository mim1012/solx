@echo off
chcp 65001 >nul
title USD 예수금 조회 (수동 입력)

cd /d "%~dp0"

echo.
echo ================================================
echo      한국투자증권 USD 예수금 조회
echo      (API 정보 직접 입력)
echo ================================================
echo.

python check_usd_balance_manual.py
