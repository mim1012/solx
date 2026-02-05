@echo off
chcp 65001 >nul
title USD Balance Check

cd /d "%~dp0"

echo.
echo ================================================
echo   Korea Investment USD Balance Check
echo   (No Python Required)
echo ================================================
echo.

check_usd_balance.exe

if errorlevel 1 (
    echo.
    echo [ERROR] Program execution failed.
    echo.
)

pause
