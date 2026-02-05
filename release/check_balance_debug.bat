@echo off
chcp 65001 >nul 2>&1
title USD Balance Check (Debug)

cd /d "%~dp0"

"%~dp0check_balance_debug.exe"

pause
