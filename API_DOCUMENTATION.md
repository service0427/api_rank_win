# Naver Organic Pure Rank Engine REST API Specification

> **Base URL**: `http://114.207.112.172:8888`  
> **Framework**: FastAPI (Python 3.14 on Ubuntu)  
> **Process Manager**: PM2 (`nodriver-rank-api`)

---

## 1. Endpoints Overview

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/rank/shop` | `GET` | 네이버 쇼핑 순수 오가닉 순위 조회 (단일 타겟 or 1~500위 전수) |
| `/api/rank/place` | `GET` | 네이버 플레이스/지도 순수 오가닉 순위 조회 (단일 타겟 or 1~1,000위 전수) |
| `/api/health` | `GET` | 서버 상태 헬스 체크 |

---

## 2. API Endpoints

### ① 쇼핑 순위 조회 (`GET /api/rank/shop`)

#### Request Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `keyword` | String | **Yes** | - | 검색 키워드 (예: `노트북`) |
| `target` | String | No | `null` | 찾고자 하는 상품 고유 ID (`nvMid` 또는 스마트스토어 상품번호) |
| `maxpage` | Integer | No | `13` | 최대 크롤링 페이지 수 (13페이지 = ~500개) |

#### Example 1: 단일 타겟 상품 조회 (가격비교 카탈로그)
```http
GET /api/rank/shop?keyword=노트북&target=52631236642 HTTP/1.1
Host: 114.207.112.172:8888
```

#### Response (200 OK)
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

#### Example 2: 단일 타겟 상품 조회 (스마트스토어 단일상품)
```http
GET /api/rank/shop?keyword=노트북&target=88807541662 HTTP/1.1
Host: 114.207.112.172:8888
```

#### Response (200 OK)
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

#### Example 3: 타겟 미발견 시 (500위 밖)
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

### ② 플레이스 순위 조회 (`GET /api/rank/place`)

#### Request Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `keyword` | String | **Yes** | - | 검색 키워드 (예: `강남역 맛집`) |
| `target` | String | No | `null` | 찾고자 하는 플레이스 고유 ID (예: `1047144456`) |

#### Example: 단일 타겟 플레이스 조회
```http
GET /api/rank/place?keyword=강남역%20맛집&target=1047144456 HTTP/1.1
Host: 114.207.112.172:8888
```

#### Response (200 OK)
```json
{
  "success": true,
  "status": "SUCCESS",
  "keyword": "강남역 맛집",
  "target": "1047144456",
  "rank": 112,
  "place": {
    "placeId": "1047144456",
    "name": "금별맥주 강남역점",
    "category": "요리주점",
    "visitorReviewCount": 931,
    "blogReviewCount": 68,
    "saveCount": "~100"
  }
}
```
