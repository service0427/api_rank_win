# 🚀 Naver Organic Pure Rank Engine - Windows Server 종합 배포 및 운영 가이드

본 문서는 **새로운 윈도우 서버(Windows Server 2022/2025 또는 Windows 10/11 Pro)** 환경에서 네이버 쇼핑 및 플레이스 순수 오가닉 순위 수집 API 엔진을 즉시 배포하고 운영할 수 있는 종합 가이드입니다.

---

## ⚠️ [필독] 네이버 쇼핑 WAF 방어벽 특성 및 핵심 주의사항

실측 및 패킷 분석을 통해 규명된 **네이버의 3대 안티봇 방어벽과 폐기된 우회 방식**입니다:

1. **모바일 에뮬레이션 (`msearch.shopping.naver.com`) 폐기**:
   - PC 환경에서 가짜 안드로이드 UA나 모바일 뷰로 모바일 전문관에 접근하면 비로그인 게스트는 **100% `nidlogin.login`으로 리다이렉트**됩니다.
2. **헤드리스 모드 (`headless=True`) 폐기**:
   - 윈도우 창 프레임 델타(`outerWidth === innerWidth`)와 D3D11 가속 부재로 네이버 FDS에 100% 걸립니다. (10회 연속 테스트 시 0회 성공 / 10회 차단)
3. **쇼핑 전문관 생(Raw) URL 직행 폐기**:
   - 통합검색 게이트웨이를 거치지 않으면 네이버 백엔드가 **`HTTP 418 (I'm a teapot)`**을 던지며 빈 껍데기 HTML만 내려줍니다.
4. **★ 확정된 정공법 (전용 윈도우 서버 데스크톱 파이프라인)**:
   - **`headless=False` (실제 화면 출력)**으로 띄워 윈도우 DWM과 D3D11 가속을 100% 가동하고,
   - **[통합검색 직행 ➔ 가격비교 더보기 클릭]**을 거치면 합법적인 `nl-ts-pid` 서명을 받아 **키워드당 4~5초 만에 1~500위 순위를 100% 무통과로 회수**합니다.

---

## 📁 1. 디렉토리 구조 및 핵심 파일 안내

```text
nshop_rank/
├── api_server.py                 # FastAPI 프로덕션 API 엔트리포인트 (포트 8888)
├── main.py                       # CLI 순위 조회 및 디버깅 도구
├── run_api_server.bat            # [1클릭] API 서버 무한 실행 배치 파일 (크래시 시 자동 재시작)
├── run_cron_scheduler.bat        # [1클릭] 매분 100건 타겟 자동 수집 스케줄러 배치 파일
├── setup_windows_firewall.bat    # [1클릭] 윈도우 방화벽 포트(8888, 22) 자동 인바운드 개방
├── requirements.txt              # 윈도우 프로덕션 필수 라이브러리 목록
│
├── core/
│   ├── browser.py                # 오프스크린 데스크톱 크롬 브라우저 매니저
│   ├── logger.py                 # 일자별 롤링 로거
│   └── stealth.py                # 브라우저 최적화 아규먼트
│
├── services/
│   ├── cron_handler.py           # 큐 기반 다중 타겟 병렬 크론 핸들러
│   ├── sync_handler.py           # DB 타겟 목록 동기화
│   ├── shop/
│   │   ├── runner.py             # 쇼핑 랭킹 서비스 오케스트레이터
│   │   └── deep_crawler.py       # 1~500위 심층 오프스크린 크롤러 (통합검색 게이트웨이)
│   └── place/
│       ├── runner.py             # 플레이스 오케스트레이터
│       ├── packet_crawler.py     # 플레이스 초고속 모바일 패킷 (0.3초)
│       └── parser.py             # 플레이스 HTML 및 State 파서
│
├── tools/                        # 실전 테스트 및 검증 도구 모음
│   ├── test_whale_production_crawler.py  # 웨일 브라우저 쇼핑 수집 실측 도구
│   └── run_offscreen_search_test.py      # 오프스크린 가상 좌표 연속 부하 테스트 도구
│
└── data/
    ├── browser_profiles/         # 영구 사용자 프로필 (Local State 기기 분리)
    └── logs/                     # 일자별 실행 로그
```

---

## ⚙️ 2. 윈도우 서버 초기 세팅 (3단계)

### Step 1. Python 및 Google Chrome 설치
1. **Python 3.11 이상 설치** (설치 시 반드시 `Add Python to PATH` 체크)
2. **Google Chrome 최신 버전 설치**

### Step 2. 필수 라이브러리 설치
명령 프롬프트(CMD) 또는 PowerShell에서 실행:
```cmd
cd nshop_rank
pip install -r requirements.txt
```

### Step 3. 방화벽 포트 1클릭 개방
- `setup_windows_firewall.bat` 파일을 **마우스 우클릭 ➔ '관리자 권한으로 실행'**
  - **TCP 8888**: 외부 API 호출 인바운드 자동 허용
  - **TCP 22**: 원격 SSH 접속 인바운드 자동 허용

---

## 💻 3. 윈도우를 우분투처럼 터미널(SSH)로 관리하기

윈도우 서버에 내장된 **OpenSSH Server**를 활성화하면 우분투와 똑같이 원격 터미널에서 SSH로 관리할 수 있습니다:

1. **PowerShell을 관리자 권한으로 실행**하고 아래 3줄 명령어 입력:
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
```
2. 이제 개발 PC나 어디서든 SSH 접속 가능:
```bash
ssh tech@<윈도우서버IP>
```

---

## 🏃 4. 서버 실행 및 무인 운영 방법

### 1) [방법 A] 1클릭 배치 파일 실행 (가장 간편)
- **API 서버 가동**: `run_api_server.bat` 더블 클릭 ➔ `http://0.0.0.0:8888`에서 즉시 서비스 시작 (크래시 시 3초 후 자동 복구)
- **자동 스케줄러 가동**: `run_cron_scheduler.bat` 더블 클릭 ➔ 매분 쇼핑 100건 / 플레이스 50건 순위 자동 수집 및 DB 갱신

### 2) [방법 B] Windows 백그라운드 서비스(NSSM) 등록
윈도우 재부팅 시 사용자 로그인 없이 백그라운드 데몬으로 상시 기동:
```cmd
nssm install NaverRankAPI "python" "api_server.py"
nssm set NaverRankAPI AppDirectory "D:\dev\nshop_rank"
nssm start NaverRankAPI
```

---

## 📡 5. 제공 API 엔드포인트 규격

### 1) 쇼핑 순수 오가닉 순위 조회
- **URL**: `GET http://<서버IP>:8888/api/rank/shop?keyword=노트북&target=58488180590`
- **응답 예시**:
```json
{
  "success": true,
  "status": "SUCCESS",
  "keyword": "노트북",
  "target": "58488180590",
  "rank": 1,
  "product": {
    "productType": "STORE",
    "productTypeName": "가격비교",
    "productTitle": "LG전자 LG그램 노트북 그램 14 AI AMD 14ZD95U-",
    "mallName": "N/A",
    "price": 1486750,
    "nvMid": "58488180590"
  },
  "stage": "STAGE_2_NODRIVER",
  "elapsedSec": 4.85
}
```

### 2) 플레이스 순수 오가닉 순위 조회
- **URL**: `GET http://<서버IP>:8888/api/rank/place?keyword=강남맛집&target=2062973993`
- **응답 예시**:
```json
{
  "success": true,
  "status": "SUCCESS",
  "keyword": "강남맛집",
  "target": "2062973993",
  "rank": 1,
  "place": {
    "placeId": "2062973993",
    "name": "마포갈매기 신논현역점",
    "category": "돼지고기구이"
  }
}
```
