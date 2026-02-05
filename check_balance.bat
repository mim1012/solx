@echo off
chcp 65001 >nul 2>&1
title USD Balance Check

cd /d "%~dp0"

check_balance.exe

pause
