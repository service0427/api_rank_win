@echo off
chcp 65001 > nul
title Naver Organic Rank API Server (FastAPI Engine)
cd /d "%~dp0"

echo ======================================================================
echo   [Naver Organic Rank Engine] Production API Server
echo   Port: 8888 | Platform: Windows | Engine: Hybrid Packet + Nodriver
echo ======================================================================
echo.

:: Check python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH! Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

:: Create data directories
if not exist "data\browser_profiles" mkdir "data\browser_profiles"
if not exist "data\logs" mkdir "data\logs"
if not exist "output" mkdir "output"

:loop
echo [%date% %time%] Starting FastAPI Server on http://0.0.0.0:8888...
python api_server.py
echo.
echo [WARNING] API Server exited unexpectedly. Restarting in 3 seconds...
timeout /t 3 /nobreak > nul
goto loop
