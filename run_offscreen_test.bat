@echo off
chcp 65001 > nul
echo ================================================================================
echo   [오프스크린(Off-Screen) 가상 좌표 무간섭 쇼핑 순위 수집 테스트]
echo ================================================================================
echo.
echo 브라우저 창이 모니터 화면을 가리지 않고 가상 좌표(3000,3000)에서 조용히 작동합니다.
echo.
set /p KEYWORD="검색할 특정 키워드 입력 (엔터 시 기본 5개 연속 키워드 실행): "
echo.
if "%KEYWORD%"=="" (
    echo [기본 5개 키워드 연속 부하 테스트를 실행합니다...]
    python tools\run_offscreen_search_test.py
) else (
    echo [%KEYWORD%] 키워드를 오프스크린으로 조회합니다...
    python tools\run_offscreen_search_test.py "%KEYWORD%"
)
pause
