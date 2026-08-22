# 네이버 쇼핑 & 플레이스 순수 오가닉 순위 조회 API 연동 가이드

> **API Server Base URL**: `http://114.207.112.172:8888`  
> **API Version**: `v2.3`  
> **인코딩**: `UTF-8`  
> **데이터 형식**: `application/json`

---

## 1. API 개요

본 API는 네이버 모바일 쇼핑 및 플레이스(지도)의 **순수 자연 검색 순위(광고 제외 오가닉 순위)**를 실시간으로 탐색하여 제공하는 고성능 순위 조회 서비스입니다.

### 🌟 핵심 기능
- **최대 500위(쇼핑) / 1,000위(플레이스) 전수 순위 조회 지원**: 상위권(1~70위)뿐만 아니라 심층 순위까지 완벽 탐색.
- **판매처 구분 자동 제공**: `CATALOG`(가격비교 카탈로그) 및 `STORE`(단일상품/스마트스토어) 자동 분류.
- **초고속 응답 보장**: 1단계 초고속 패킷 탐색(0.5초) 및 60분 지능형 캐시(1ms) 탑재.

---

## 2. API 엔드포인트 목록

| 서비스 | 메서드 | 엔드포인트 URI | 설명 |
| :--- | :---: | :--- | :--- |
| **쇼핑 순위** | `GET` | `/api/rank/shop` | 네이버 쇼핑 타겟 상품 순위 또는 500위 전수 목록 조회 |
| **플레이스 순위** | `GET` | `/api/rank/place` | 네이버 플레이스 타겟 업체 순위 또는 1,000위 전수 목록 조회 |
| **서버 상태** | `GET` | `/api/health` | API 서버 정상 작동 여부 확인 |

---

## 3. 상세 API 명세

### ① 네이버 쇼핑 순위 조회 (`GET /api/rank/shop`)

#### 요청 파라미터 (Query Parameters)
| 파라미터명 | 타입 | 필수 여부 | 기본값 | 설명 |
| :--- | :---: | :---: | :---: | :--- |
| `keyword` | String | **필수** | - | 검색할 키워드 (예: `노트북`) |
| `target` | String | 선택 | `null` | 찾고자 하는 상품 고유 ID (`nvMid` 또는 스마트스토어 상품번호) |
| `maxpage` | Integer | 선택 | `13` | 최대 탐색 페이지 (13페이지 = 최대 ~500개 탐색) |

---

#### 🟢 [성공 케이스 1] 가격비교(카탈로그) 상품 발견 시
- **요청 예시**:
  ```http
  GET /api/rank/shop?keyword=노트북&target=52631236642 HTTP/1.1
  Host: 114.207.112.172:8888
  ```
- **응답 (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "status": "SUCCESS",
    "keyword": "노트북",
    "target": "52631236642",
    "rank": 5,
    "product": {
      "productType": "CATALOG",
      "productTypeName": "가격비교",
      "productTitle": "삼성전자 갤럭시북4 노트북 NT750XGR-A51A i5 16GB, 256GB",
      "mallName": "가격비교 (판매처 156개)",
      "mallCount": 156,
      "price": 1174970,
      "nvMid": "52631236642",
      "channelProductId": "",
      "reviewCount": 20734,
      "score": 4.91
    }
  }
  ```

---

#### 🟢 [성공 케이스 2] 단일상품(스마트스토어/단독몰) 상품 발견 시
- **요청 예시**:
  ```http
  GET /api/rank/shop?keyword=노트북&target=88807541662 HTTP/1.1
  Host: 114.207.112.172:8888
  ```
- **응답 (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "status": "SUCCESS",
    "keyword": "노트북",
    "target": "88807541662",
    "rank": 64,
    "product": {
      "productType": "STORE",
      "productTypeName": "단일상품",
      "productTitle": "삼성전자 갤럭시북6 프로 울트라7 Win11 32GB 1TB 가벼운 대학생 고성능 노트북",
      "mallName": "삼성공식파트너 코잇",
      "mallCount": 0,
      "price": 3699000,
      "nvMid": "88807541662",
      "channelProductId": "11263031331",
      "reviewCount": 1348,
      "score": 4.93
    }
  }
  ```

---

#### 🔴 [실패/미발견 케이스] 상품이 순위권(500위) 내에 없을 때
- **요청 예시**:
  ```http
  GET /api/rank/shop?keyword=노트북&target=99999999999 HTTP/1.1
  Host: 114.207.112.172:8888
  ```
- **응답 (HTTP 200 OK)**:
  ```json
  {
    "success": false,
    "status": "NOT_FOUND",
    "keyword": "노트북",
    "target": "99999999999",
    "rank": null,
    "product": null
  }
  ```

---

### ② 네이버 플레이스 순위 조회 (`GET /api/rank/place`)

#### 요청 파라미터 (Query Parameters)
| 파라미터명 | 타입 | 필수 여부 | 기본값 | 설명 |
| :--- | :---: | :---: | :---: | :--- |
| `keyword` | String | **필수** | - | 검색할 키워드 (예: `강남역 맛집`) |
| `target` | String | 선택 | `null` | 찾고자 하는 플레이스 고유 번호 (예: `1047144456`) |
| `maxpage` | Integer | 선택 | `12` | 최대 스크롤 깊이 (12회 = 최대 ~1,003개 탐색) |

---

#### 🟢 [성공 케이스] 플레이스 타겟 발견 시
- **요청 예시**:
  ```http
  GET /api/rank/place?keyword=강남맛집&target=2062973993 HTTP/1.1
  Host: 114.207.112.172:8888
  ```
- **응답 (HTTP 200 OK)**:
  ```json
  {
    "success": true,
    "status": "SUCCESS",
    "keyword": "강남맛집",
    "target": "2062973993",
    "rank": 1,
    "place": {
      "placeId": "2062973993",
      "name": "홍수회전훠궈",
      "category": "중식당",
      "visitorReviewCount": 931,
      "blogReviewCount": 68,
      "saveCount": "~100"
    }
  }
  ```

---

## 4. 응답 필드 상세 설명 (Data Dictionary)

| 필드명 | 데이터 타입 | 설명 |
| :--- | :---: | :--- |
| `success` | Boolean | 타겟 발견 여부 (`true`: 발견 / `false`: 미발견) |
| `status` | String | 상태 코드 (`SUCCESS`: 성공, `NOT_FOUND`: 순위권 밖 미발견) |
| `keyword` | String | 검색 키워드 |
| `target` | String | 요청한 타겟 상품/플레이스 코드 |
| `rank` | Integer | **최종 오가닉 순위** (미발견 시 `null`) |
| `product.productType` | String | 상품 분류 (`CATALOG`: 가격비교 카탈로그, `STORE`: 단일상품) |
| `product.productTypeName` | String | 상품 분류 한글명 (`가격비교` 또는 `단일상품`) |
| `product.productTitle` | String | 상품명 (HTML 태그가 정제된 깔끔한 텍스트) |
| `product.mallName` | String | 판매처/몰명 (가격비교 시 `가격비교 (판매처 N개)`, 단일상품 시 상호명) |
| `product.mallCount` | Integer | 입점 판매처 수 |
| `product.price` | Integer | 상품 판매가/최저가 (원 단위 정수) |
| `product.nvMid` | String | 네이버 모델 고유 ID |
| `product.channelProductId` | String | 스마트스토어 상품 등록 번호 |
| `product.reviewCount` | Integer | 총 리뷰 수 |
| `product.score` | Float | 평균 평점 (5.0 만점 기준) |

---

## 5. 프로그래밍 언어별 연동 예제 코드

### 🐍 Python
```python
import requests
import urllib.parse

API_BASE = "http://114.207.112.172:8888"

def check_shop_rank(keyword: str, target_id: str):
    url = f"{API_BASE}/api/rank/shop"
    params = {
        "keyword": keyword,
        "target": target_id
    }
    response = requests.get(url, params=params, timeout=20)
    data = response.json()
    
    if data.get("success"):
        print(f"[성공] '{keyword}' 키워드에서 {data['rank']}위로 노출 중!")
        print(f" - 상품명: {data['product']['productTitle']}")
        print(f" - 판매처: {data['product']['mallName']} ({data['product']['price']:,}원)")
    else:
        print(f"[미발견] '{keyword}' 500위 순위권 내에 상품이 존재하지 않습니다.")

# 실행 테스트
check_shop_rank("노트북", "52631236642")
```

---

### 🌐 JavaScript / Node.js (Axios)
```javascript
const axios = require('axios');

async function checkShopRank(keyword, targetId) {
  try {
    const res = await axios.get('http://114.207.112.172:8888/api/rank/shop', {
      params: { keyword: keyword, target: targetId },
      timeout: 20000
    });

    const data = res.data;
    if (data.success) {
      console.log(`[성공] 순위: ${data.rank}위 | 상품명: ${data.product.productTitle}`);
    } else {
      console.log(`[미발견] 500위 내 상품이 없습니다.`);
    }
  } catch (error) {
    console.error('API 호출 오류:', error.message);
  }
}

checkShopRank('노트북', '52631236642');
```

---

### 🐘 PHP (cURL)
```php
<?php
$keyword = urlencode("노트북");
$targetId = "52631236642";
$url = "http://114.207.112.172:8888/api/rank/shop?keyword={$keyword}&target={$targetId}";

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 20);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
if ($data['success']) {
    echo "[성공] 순위: " . $data['rank'] . "위\n";
    echo "상품명: " . $data['product']['productTitle'] . "\n";
    echo "가격: " . number_format($data['product']['price']) . "원\n";
} else {
    echo "[미발견] 500위 순위권 밖입니다.\n";
}
?>
```

---

### 💻 cURL CLI
```bash
curl -X GET "http://114.207.112.172:8888/api/rank/shop?keyword=%EB%85%B8%ED%8A%B8%EB%B6%81&target=52631236642"
```
