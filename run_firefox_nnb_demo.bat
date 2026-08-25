@echo off
chcp 65001 > nul
echo ================================================================================
echo   [모질라 파이어폭스(Firefox) NNB 쿠키 타임스탬프 조작 실시간 화면 검증]
echo ================================================================================
echo.
echo 1. 24시간 숙성 NNB 주입 모드 (로그인 없이 100%% 프리패스 검증)
echo 2. 일반 신규 세션 모드       (Aging 없이 로그인창 차단 유도 검증)
echo.
set /p MODE_CHOICE="실행할 모드를 선택하세요 (1 또는 2, 기본: 1): "
if "%MODE_CHOICE%"=="2" (
    set SELECTED_MODE=fresh
    echo.
    echo [2번: 일반 신규 세션으로 파이어폭스를 실행합니다 -> 로그인창 차단 유도...]
) else (
    set SELECTED_MODE=aged
    echo.
    echo [1번: 24시간 숙성 NNB를 주입하여 파이어폭스를 실행합니다 -> 100%% 프리패스...]
)
echo.
set /p KEYWORD="검색 키워드 입력 (엔터 시 기본: 스마트폰): "
if "%KEYWORD%"=="" set KEYWORD=스마트폰
echo.
python tools\demo_firefox_nnb_live.py "%KEYWORD%" "%SELECTED_MODE%"
pause
