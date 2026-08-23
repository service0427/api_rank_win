@echo off
chcp 65001 > nul
echo ================================================================================
echo   [Windows 방화벽 포트 자동 개방 도구 - Naver Rank API]
echo ================================================================================
echo.

:: 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [오류] 관리자 권한이 필요합니다.
    echo 이 배치 파일을 마우스 우클릭 후 '관리자 권한으로 실행'을 선택해 주세요.
    echo.
    pause
    exit /b 1
)

echo [1/2] API 서버 포트 (TCP 8888) 방화벽 인바운드 허용 추가 중...
netsh advfirewall firewall add rule name="Naver Rank API (Port 8888)" dir=in action=allow protocol=TCP localport=8888 > nul 2>&1
echo   -> TCP 8888 포트 인바운드 허용 완료!

echo.
echo [2/2] 윈도우 원격 SSH 관리 포트 (TCP 22) 방화벽 인바운드 허용 추가 중...
netsh advfirewall firewall add rule name="OpenSSH Server (Port 22)" dir=in action=allow protocol=TCP localport=22 > nul 2>&1
echo   -> TCP 22 포트 인바운드 허용 완료!

echo.
echo ================================================================================
echo   ★ 방화벽 포트 설정이 완벽하게 완료되었습니다!
echo   - API 서버: http://[서버IP]:8888
echo   - Swagger API 문서: http://[서버IP]:8888/docs
echo ================================================================================
echo.
pause
