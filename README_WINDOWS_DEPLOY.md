# 🚀 Naver Organic Pure Rank Engine - Windows Server 종합 배포 및 운영 가이드

본 문서는 **새로운 윈도우 서버(Windows Server 2022/2025 또는 Windows 10/11 Pro)** 환경에서 네이버 쇼핑 및 플레이스 순수 오가닉 순위 수집 API 엔진을 3분 안에 즉시 배포하고 운영할 수 있는 종합 가이드입니다.

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
├── .env.example                  # 환경 변수 템플릿 (DB 접속 정보 등)
│
├── config/
│   ├── settings.py               # 서버 포트, DB, 타임아웃, 동시성 설정
│   ├── db_manager.py             # MySQL 커넥션 풀, 캐시, 타겟 마스터 동기화
│   └── proxy_manager.py          # 프록시 풀 관리 및 헬스 체크
│
├── core/
│   ├── ackey.py                  # 모바일 ackey 세션 토큰 실시간 생성기
│   ├── browser.py                # 고정 프로필(user_data_dir) 기반 스텔스 크롬 브라우저
│   ├── logger.py                 # 일자별 롤링 로거
│   └── stealth.py                # 브라우저 아규먼트 및 스텔스 설정
│
├── services/
│   ├── cron_handler.py           # 큐 기반 다중 타겟 병렬 크론 핸들러
│   ├── sync_handler.py           # DB 타겟 목록 동기화
│   ├── shop/
│   │   ├── runner.py             # 쇼핑 2단계 하이브리드 오케스트레이터
│   │   ├── packet_crawler.py     # 1단계: curl_cffi 초고속 모바일 패킷 (0.3초)
│   │   ├── deep_crawler.py       # 2단계: 500위 심층 스크롤 & 동적 DOM 파서
│   │   └── parser.py             # INITIAL_STATE JSON 파서
│   └── place/
│       ├── runner.py             # 플레이스 100% 패킷 전용 오케스트레이터
│       ├── packet_crawler.py     # 1단계: 플레이스 초고속 모바일 패킷 (0.3초)
│       └── parser.py             # 플레이스 HTML 및 State 파서
│
└── data/
    ├── browser_profiles/         # 영구 사용자 프로필 (WAF 무통과 세션 보존)
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
- **URL**: `GET http://<서버IP>:8888/api/rank/shop?keyword=메모꽂이&target=87882183423`
- **응답 예시**:
```json
{
  "success": true,
  "status": "SUCCESS",
  "keyword": "메모꽂이",
  "target": "87882183423",
  "rank": 25,
  "product": {
    "productType": "STORE",
    "productTypeName": "단일상품",
    "productTitle": "아델 메탈 메모홀더 골드 메모꽂이",
    "mallName": "아델스토어",
    "price": 3500,
    "nvMid": "87882183423",
    "score": 4.8,
    "reviewCount": 142
  }
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

### 3) 대화형 Swagger API 문서
- 브라우저에서 `http://<서버IP>:8888/docs` 접속 시 실시간 테스트 가능
