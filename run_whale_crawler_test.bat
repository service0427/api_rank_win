@echo off
chcp 65001 > nul
echo ================================================================================
echo   [네이버 공식 웨일 브라우저 기반 쇼핑 1+2페이지 랭킹 수집 테스트]
echo ================================================================================
echo.
set /p KEYWORD="검색할 키워드를 입력하세요 (기본값: 노트북): "
if "%KEYWORD%"=="" set KEYWORD=노트북
echo.
echo [%KEYWORD%] 키워드로 웨일 브라우저를 기동합니다...
echo.
python tools\test_whale_production_crawler.py "%KEYWORD%"
pause
