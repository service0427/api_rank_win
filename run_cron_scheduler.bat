@echo off
chcp 65001 > nul
title Naver Organic Rank Cron Scheduler (Automated Batch Target Worker)
cd /d "%~dp0"

echo ======================================================================
echo   [Naver Organic Rank Engine] Automated Target Scheduler
echo   Target Rank Cron Worker | Platform: Windows
echo ======================================================================
echo.

:: Check python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    pause
    exit /b 1
)

:loop
echo [%date% %time%] Running Shop & Place Cron Checks...
python -m services.cron_handler --type shop --limit 100
python -m services.cron_handler --type place --limit 50
echo [%date% %time%] Batch complete. Waiting 60 seconds for next cycle...
timeout /t 60 /nobreak > nul
goto loop
