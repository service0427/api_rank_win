# 🚀 Naver Organic Pure Rank Engine - Windows Server 배포 가이드

본 문서는 **새로운 윈도우 서버(Windows Server 2022/2025 또는 Windows 10/11 Pro)** 환경에서 네이버 쇼핑 및 플레이스 순수 오가닉 순위 수집 API 엔진을 5분 안에 즉시 배포하고 운영할 수 있는 가이드입니다.

---

## 📁 1. 디렉토리 구조 및 핵심 파일 안내

```text
nshop_rank/
├── api_server.py                 # FastAPI 프로덕션 API 엔트리포인트 (포트 8888)
├── main.py                       # CLI 순위 조회 및 테스트 도구
├── run_api_server.bat            # [1클릭] API 서버 무한 실행 배치 파일 (크래시 시 자동 재시작)
├── run_cron_scheduler.bat        # [1클릭] 매분 100건 타겟 자동 수집 스케줄러 배치 파일
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
│   └── stealth.py                # 봇 감지 무력화 JS 및 브라우저 아규먼트
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
    ├── browser_profiles/         # 워커별 네이버 세션 보존 디렉토리
    └── logs/                     # 일자별 실행 로그
```

---

## ⚙️ 2. 윈도우 서버 초기 세팅 (3단계)

### Step 1. Python 및 Google Chrome 설치
1. **Python 3.11 이상 설치** (설치 시 반드시 `Add Python to PATH` 체크)
2. **Google Chrome 최신 버전 설치** (일반 크롬 브라우저 설치)

### Step 2. 필수 라이브러리 설치
명령 프롬프트(CMD) 또는 PowerShell을 열고 프로젝트 폴더로 이동한 뒤 실행:
```cmd
cd D:\dev\nshop_rank
pip install -r requirements.txt
```

### Step 3. 환경 변수 설정 (`.env`)
`.env.example` 파일을 복사하여 `.env`로 저장하고 MySQL 접속 정보를 입력합니다:
```env
API_HOST=0.0.0.0
API_PORT=8888

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=rank
DB_PASS=Tech1324
DB_NAME=rank

MAX_CONCURRENT_BROWSERS=5
USE_PROXY_POOL=0
```

---

## 🏃 3. 서버 실행 및 운영 방법

### 1) [방법 A] 1클릭 배치 파일 실행 (가장 추천)
- **API 서버 가동**: `run_api_server.bat` 더블 클릭 ➔ `http://0.0.0.0:8888`에서 API 즉시 서비스 시작 (서버 종료 시 3초 후 자동 재기동)
- **타겟 자동 스케줄러 가동**: `run_cron_scheduler.bat` 더블 클릭 ➔ 매분 쇼핑 100건 / 플레이스 50건 순위 자동 수집 및 DB 갱신

### 2) [방법 B] Windows 백그라운드 서비스(NSSM) 등록
윈도우 재부팅 시 로그인 없이 백그라운드에서 자동 실행되도록 하려면:
```cmd
:: NSSM 다운로드 후 서비스 등록
nssm install NaverRankAPI "C:\Python313\python.exe" "D:\dev\nshop_rank\api_server.py"
nssm set NaverRankAPI AppDirectory "D:\dev\nshop_rank"
nssm start NaverRankAPI
```

---

## 📡 4. 제공 API 엔드포인트 규격

### 1) 쇼핑 순수 오가닉 순위 조회
- **요청**: `GET http://<서버IP>:8888/api/rank/shop?keyword=메모꽂이&target=87882183423`
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
- **요청**: `GET http://<서버IP>:8888/api/rank/place?keyword=강남맛집&target=2062973993`
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
