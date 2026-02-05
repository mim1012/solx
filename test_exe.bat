@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo EXE 파일 실행 테스트 중...
echo.

"USD잔고조회.exe"

echo.
echo 종료 코드: %ERRORLEVEL%
pause
