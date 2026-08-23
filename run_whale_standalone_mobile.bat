@echo off
chcp 65001 > nul
echo ================================================================================
echo   [웨일 메인 브라우저 없이 '단독 모바일창(Standalone App Mode)' 즉시 실행기]
echo ================================================================================
echo.
set /p KEYWORD="검색할 키워드를 입력하세요 (기본값: 스마트폰): "
if "%KEYWORD%"=="" set KEYWORD=스마트폰
echo.
echo [%KEYWORD%] 키워드로 단독 모바일 창을 기동합니다...
echo.
python tools\run_whale_standalone_mobile.py "%KEYWORD%"
pause
