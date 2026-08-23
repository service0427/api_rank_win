@echo off
chcp 65001 > nul
echo ================================================================================
echo   [100%% 순수 네이버 웨일 브라우저 네이티브 모바일 뷰 실행기]
echo ================================================================================
echo.
set /p KEYWORD="검색할 키워드를 입력하세요 (기본값: 노트북): "
if "%KEYWORD%"=="" set KEYWORD=노트북
echo.
echo [%KEYWORD%] 키워드로 순수 웨일 브라우저를 기동합니다...
echo.
python tools\run_pure_whale_search.py "%KEYWORD%"
pause
