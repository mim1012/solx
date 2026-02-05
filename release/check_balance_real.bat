@echo off
chcp 65001 >nul 2>&1
title USD Balance Check (Real - Phoenix Method)

cd /d "%~dp0"

"%~dp0check_balance_real.exe"

pause
