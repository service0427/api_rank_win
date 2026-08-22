import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from core.logger import get_logger
from config.settings import API_HOST, API_PORT
from config.proxy_manager import proxy_mgr
from services.shop.runner import get_shop_rank
from services.place.runner import get_place_rank

logger = get_logger("rank.api")

app = FastAPI(
    title="Naver Organic Pure Rank Engine API",
    description="High-Speed Pure Ranking API for Naver Shopping & Place",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Naver Organic Rank Engine",
        "uptimeSec": round(time.time() - SERVER_START_TIME, 2),
        "availableServices": ["shop", "place"]
    }


@app.get("/api/rank/shop")
async def query_shop_rank(
    request: Request,
    keyword: str = Query(..., description="검색 키워드 (예: 노트북)"),
    target: Optional[str] = Query(None, description="찾고자 하는 상품 ID (nvMid 또는 스마트스토어 상품번호)"),
    maxpage: int = Query(13, description="최대 탐색 페이지 수 (13페이지 = ~500개)"),
    proxy: Optional[str] = Query(None, description="커스텀 프록시 (선택)")
):
    """
    네이버 쇼핑 순수 오가닉 순위 조회 API.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1").split(",")[0].strip()
    logger.info(f"[API: SHOP] Keyword='{keyword}', Target='{target}', ClientIP='{client_ip}'")

    res = await get_shop_rank(
        keyword=keyword,
        target_id=target,
        max_pages=maxpage,
        headless=True,
        block_media=True,
        proxy_url=proxy,
        client_ip=client_ip
    )

    # 1. Target Single Item Response
    if target:
        found = res.get("targetFound", False)
        tp = res.get("targetProduct")
        return {
            "success": found,
            "status": "SUCCESS" if found else "NOT_FOUND",
            "keyword": keyword,
            "target": target,
            "rank": res.get("targetRank") if found else None,
            "product": {
                "productType": tp.get("productType"),
                "productTypeName": tp.get("productTypeName"),
                "productTitle": tp.get("productTitle"),
                "mallName": tp.get("mallName"),
                "mallCount": tp.get("mallCount", 0),
                "price": tp.get("price"),
                "nvMid": tp.get("nvMid"),
                "channelProductId": tp.get("channelProductId"),
                "reviewCount": tp.get("reviewCount"),
                "score": tp.get("score")
            } if found and tp else None
        }

    # 2. Full Mode Response (When target is omitted)
    else:
        raw_prods = res.get("products", [])
        cleaned_prods = []
        for p in raw_prods:
            cleaned_prods.append({
                "rank": p.get("rank"),
                "productType": p.get("productType"),
                "productTypeName": p.get("productTypeName"),
                "productTitle": p.get("productTitle"),
                "mallName": p.get("mallName"),
                "mallCount": p.get("mallCount", 0),
                "price": p.get("price"),
                "nvMid": p.get("nvMid"),
                "channelProductId": p.get("channelProductId"),
                "reviewCount": p.get("reviewCount"),
                "score": p.get("score")
            })

        return {
            "success": True,
            "status": "SUCCESS",
            "keyword": keyword,
            "total": len(cleaned_prods),
            "products": cleaned_prods
        }


@app.get("/api/rank/place")
async def query_place_rank(
    request: Request,
    keyword: str = Query(..., description="검색 키워드 (예: 강남역 맛집)"),
    target: Optional[str] = Query(None, description="찾고자 하는 플레이스 고유 ID"),
    maxpage: int = Query(12, description="최대 스크롤 깊이"),
    proxy: Optional[str] = Query(None, description="커스텀 프록시 (선택)")
):
    """
    네이버 플레이스 순수 오가닉 순위 조회 API.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1").split(",")[0].strip()
    logger.info(f"[API: PLACE] Keyword='{keyword}', Target='{target}', ClientIP='{client_ip}'")

    res = await get_place_rank(
        keyword=keyword,
        target_id=target,
        max_pages=maxpage,
        headless=True,
        block_media=True,
        proxy_url=proxy,
        client_ip=client_ip
    )

    if target:
        found = res.get("targetFound", False)
        tp = res.get("targetItem")
        m_info = res.get("masterInfo") or {}
        return {
            "success": found,
            "status": "SUCCESS" if found else "NOT_FOUND",
            "keyword": keyword,
            "target": target,
            "rank": res.get("targetRank") if found else None,
            "place": {
                "placeId": tp.get("placeId") if tp else target,
                "name": tp.get("name") if tp else m_info.get("name"),
                "category": tp.get("category") if tp else m_info.get("category"),
                "visitorReviewCount": m_info.get("visitor_review_count"),
                "blogReviewCount": m_info.get("blog_cafe_review_count"),
                "saveCount": m_info.get("save_count")
            } if found else None
        }
    else:
        raw_places = res.get("places", [])
        cleaned_places = []
        for p in raw_places:
            cleaned_places.append({
                "rank": p.get("rank"),
                "placeId": p.get("placeId"),
                "name": p.get("name"),
                "category": p.get("category")
            })

        return {
            "success": True,
            "status": "SUCCESS",
            "keyword": keyword,
            "total": len(cleaned_places),
            "places": cleaned_places
        }


SERVER_START_TIME = time.time()

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Naver Rank API Server on {API_HOST}:{API_PORT}...")
    uvicorn.run("api_server:app", host=API_HOST, port=API_PORT, reload=False, workers=1)
