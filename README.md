# Naver Shopping Pure Organic Rank Search Engine

네이버 쇼핑의 순수 비광고(Organic) 실시간 상품 순위를 초고속으로 탐색하고, 최대 500위(13개 페이지)까지 대량 수집할 수 있는 고성능 랭킹 크롤러 및 순위 탐색 서비스입니다.

네이버의 WTM 보안 게이트웨이(HTTP 418 차단, nCaptcha, 로그인 리다이렉트)를 완벽하게 우회하며, **패킷급 트래픽 최적화(CDP 미디어 차단)**를 통해 초저대역폭 및 1~2초대 초고속 순위 판별을 지원합니다.

---

## 🚀 하이브리드 연계 탐색 전략 (Cascade Architecture)

시스템은 요청 상황에 따라 가장 효율적이고 빠른 파이프라인을 자동 선택합니다.

```mermaid
flowchart TD
    Start([실행 시작]) --> CheckTarget{--target 입력 여부}
    
    CheckTarget -- "타겟 있음 (--target)" --> Stage1[1단계: curl_cffi 패킷 고속 탐색\n(1~72위, 0.5초 소요)]
    Stage1 --> TargetFound{1~72위 내 발견?}
    
    TargetFound -- "발견 (YES)" --> ReturnRank([즉시 순위 리턴 및 종료\n(0.8초 완료, 브라우저 미구동)])
    TargetFound -- "미발견 (NO)" --> Stage2[2단계: Nodriver 심층 탐색 전환\n(미디어 차단 + 500위까지 탐색)]
    Stage2 --> DeepFound{500위 내 발견?}
    DeepFound -- "발견" --> ReturnDeepRank([심층 순위 리턴 및 종료])
    DeepFound -- "미발견" --> ReturnNotFound([500위 밖 판정 및 종료])

    CheckTarget -- "타겟 없음 (생략)" --> FullNodriver[Nodriver 대량 수집\n(500위+ 전수 수집 및 JSON/CSV/TXT 리포트 저장)]
    FullNodriver --> SaveReports([3종 리포트 생성 및 완료])
```

1. **타겟 코드 입력 시 (`--target <ID>`)**:
   - **1단계 (0.5s Fast Probe)**: `curl_cffi` 기반 순수 패킷으로 1~72위를 **0.5~0.8초 만에 초고속 검증**.
   - **발견 시**: 브라우저를 띄우지 않고 즉시 순위(#5)를 리턴하며 **0.8초 만에 종료**.
   - **미발견 시**: 즉시 **2단계 Nodriver(미디어 차단)**로 자동 전환하여 73위부터 500위까지 심층 탐색 후 발견 즉시 종료.
2. **타겟 코드 생략 시 (Full Scrape Mode)**:
   - **Nodriver**로 1위부터 500위+까지 순차 수집(500개 도달 시 해당 페이지 완료 후 자동 중단)하고 JSON, CSV(Excel BOM), TXT 보고서를 생성합니다.

---

## 📁 디렉토리 구조 (Project Structure)

```text
D:\dev\nshop_rank\
├── main.py                        # [통합 진입점] CLI 및 파이썬 API (search_ranks)
├── requirements.txt               # 필수 라이브러리 의존성
├── README.md                      # 프로젝트 사용 가이드 및 아키텍처 문서
├── output\                        # 수집 리포트 (JSON, CSV, TXT) 자동 저장 디렉토리
└── lib\
    ├── browser.py                 # 스텔스 브라우저 매니저 (모바일 에뮬레이션, CDP 트래픽 차단)
    ├── mobile_nodriver_runner.py  # [핵심] 최적화된 모바일 Nodriver 순위 엔진 (타겟 즉시 반환)
    ├── mobile_packet_ranker.py    # [패킷] curl_cffi 기반 0.5초 초고속 모바일 패킷 엔진
    ├── pagination_service.py      # [심층] 1~13페이지 (520위) 연속 페이지네이션 및 418 모니터
    ├── shopping_service.py        # 쇼핑 탭 전환 및 target='_self' 정제 모듈
    ├── search_service.py          # 합성 ackey 기반 자연 검색 진입 모듈
    ├── ackey.py                   # 네이버 자연 유입 ackey Base36 알고리즘 생성기
    ├── nnb_generator.py           # LCS 초경량 비콘 기반 NNB/BUC 쿠키 발급기
    ├── rank_reporter.py           # 표준 JSON, CSV (Excel BOM), TXT 리포트 생성기
    └── logger.py                  # 표준 로깅 포맷터
```

---

## 🛠 설치 및 환경 설정 (Installation)

- **Python 버전**: Python 3.10 이상 권장
- **필수 패키지 설치**:

```bash
pip install -r requirements.txt
```

---

## 💻 사용법 (Usage)

### 1. CLI 명령어 실행

#### ① 타겟 상품 순위 즉시 탐색 (타겟 코드 입력 모드)
특정 상품의 ID(`nvMid` 또는 스마트스토어 상품 ID)를 지정하면, 해당 상품을 찾는 즉시 순위를 출력하고 종료합니다.

```bash
python main.py --keyword 노트북 --target 52631236642
```
```text
================================================================================
RANK SEARCH EXECUTION RESULT:
================================================================================
Status           : SUCCESS
Keyword          : '노트북'
Mode             : MOBILE
Total Extracted  : 5 organic products

★ Target Code      : 52631236642
★ Target Found     : True
★ Target Rank      : #5
★ Product Title    : 삼성전자 갤럭시북4 노트북 NT750XGR-A51A i5 16GB, 256GB
★ Price            : 1,174,990원
★ nvMid            : 52631236642
================================================================================
```

#### ② 500위 대량 순위 수집 (타겟 생략 모드)
타겟 코드를 생략하면 1페이지부터 13페이지(기본 500위+)까지 전수 수집하여 3종 보고서를 저장합니다.

```bash
# 기본 모바일 모드로 500위 수집
python main.py --keyword 노트북 --maxpage 13

# 백그라운드(Headless) 모드로 수집
python main.py --keyword 무선이어폰 --headless
```

#### ③ 0.5초 초고속 순수 패킷 모드 (`--mode packet`)
상위 70위 이내 상품 탐색 시 브라우저 없이 초고속으로 결과를 확인합니다.

```bash
python main.py --keyword 노트북 --target 52631236642 --mode packet
```

---

### 2. 파이썬 프로그램 및 API 연동 (Programmatic Usage)

향후 **FastAPI / Flask / Django** 등 웹 서비스 백엔드에 즉시 연동할 수 있는 표준 함수 인터페이스를 제공합니다.

```python
from main import search_ranks

# 1. 특정 상품 순위 탐색 (타겟 발견 시 즉시 반환)
result = search_ranks(
    keyword="노트북",
    target_code="52631236642",
    mode="mobile",      # 'mobile' 또는 'packet'
    headless=True
)

if result["targetFound"]:
    print(f"발견 순위: {result['targetRank']}위")
    print(f"상품명: {result['targetProduct']['productTitle']}")
    print(f"가격: {result['targetProduct']['price']}원")

# 2. 대량 순위 수집 (13개 페이지 / 500위)
result_full = search_ranks(
    keyword="노트북",
    max_pages=13,
    headless=True
)
print(f"수집된 총 순수 상품 수: {result_full['totalExtracted']}개")
print(f"보고서 경로: {result_full['reports']['json']}")
```

---

## 📊 반환 데이터 명세 (JSON Schema)

`search_ranks()` 함수 및 CLI 실행 결과는 다음과 같은 표준 구조를 반환합니다.

```json
{
  "status": "SUCCESS",
  "keyword": "노트북",
  "targetCode": "52631236642",
  "targetFound": true,
  "targetRank": 5,
  "targetProduct": {
    "rank": 5,
    "page": 1,
    "pageRank": 5,
    "id": "52631236642",
    "nvMid": "52631236642",
    "productTitle": "삼성전자 갤럭시북4 노트북 NT750XGR-A51A i5 16GB, 256GB",
    "mallName": "N/A",
    "price": 1174990,
    "reviewCount": 1842,
    "scoreInfo": 4.9,
    "imageUrl": "https://shopping-phinf.pstatic.net/...",
    "productUrl": "https://cr.shopping.naver.com/..."
  },
  "totalExtracted": 520,
  "totalPagesReached": 13,
  "elapsedSec": 2.05,
  "reports": {
    "json": "output/rank_report_노트북_mobile_nodriver.json",
    "csv": "output/rank_report_노트북_mobile_nodriver.csv",
    "txt": "output/rank_report_노트북_mobile_nodriver.txt"
  }
}
```

---

## ⚙️ 실행 옵션 정리 (CLI Options)

| 옵션 | 단축키 | 기본값 | 설명 |
| :--- | :---: | :---: | :--- |
| `--keyword` | `-k` | `노트북` | 검색할 네이버 쇼핑 키워드 |
| `--target` | `-t`, `--code` | `None` | 탐색할 타겟 상품 ID (생략 시 대량 수집 모드) |
| `--maxpage` | `-m` | `13` | 최대 수집 페이지 수 (13페이지 = ~520위) |
| `--mode` | | `mobile` | `mobile`(모바일 Nodriver), `packet`(초고속 패킷), `pc`(데스크톱) |
| `--headless` | | `False` | 브라우저 창을 띄우지 않고 백그라운드 실행 |
| `--no-block-media`| | `False` | 이미지/미디어 차단 비활성화 (기본값은 패킷급 트래픽을 위해 차단 활성화) |
| `--close` | | `0.0` | 작업 완료 후 브라우저 자동 종료 대기 시간(초) |
