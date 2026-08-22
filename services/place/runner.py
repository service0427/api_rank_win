import asyncio
import time
from typing import Dict, Any, Optional
import nodriver as uc
from core.logger import get_logger
from config.db_manager import db_mgr
from services.place.packet_crawler import crawl_place_packet
from services.place.deep_crawler import crawl_place_deep_nodriver

logger = get_logger("rank.place.runner")


async def get_place_rank(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 12,
    headless: bool = True,
    block_media: bool = True,
    proxy_url: Optional[str] = None,
    client_ip: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified Naver Place Rank Service with 60-Minute DB Cache & Master List (nplace_list) Auto-Sync.
    """
    t0 = time.time()

    # -------------------------------------------------------------
    # 0. STEP 0: 60-Minute DB Cache Check
    # -------------------------------------------------------------
    cached = db_mgr.get_cached_search(service_type="place", keyword=keyword, target_code=target_id)
    if cached.get("hit"):
        elapsed_sec = time.time() - t0
        elapsed_ms = int(elapsed_sec * 1000)

        master_info = None
        if target_id and cached.get("targetItem"):
            tp = cached["targetItem"]
            # Smart Sync to nplace_list (24h or change based)
            master_info = db_mgr.sync_master_item_info("place", target_id, tp)

            db_mgr.update_target_daily_history(
                service_type="place",
                keyword=keyword,
                target_code=target_id,
                rank_num=cached.get("targetRank"),
                product_title=tp.get("name"),
                mall_name=tp.get("category"),
                price=0
            )

        db_mgr.log_api_request(
            service_type="place",
            keyword=keyword,
            target_code=target_id,
            result_rank=cached.get("targetRank"),
            target_found=cached.get("targetFound", False),
            is_cache_hit=True,
            cache_coverage_rank=cached.get("cachedMaxRank", 0),
            engine_used="DB_CACHE_60MIN",
            elapsed_ms=elapsed_ms,
            client_ip=client_ip,
            proxy_used=None
        )

        return {
            "status": "SUCCESS",
            "isCacheHit": True,
            "engine": "DB_CACHE_60MIN",
            "keyword": keyword,
            "targetCode": target_id,
            "targetFound": cached.get("targetFound", False),
            "targetRank": cached.get("targetRank"),
            "targetItem": cached.get("targetItem"),
            "masterInfo": master_info,
            "totalExtracted": cached.get("totalExtracted", 0),
            "cachedMaxRank": cached.get("cachedMaxRank", 0),
            "remainTTLSec": cached.get("remainTTLSec", 3600),
            "places": cached.get("places"),
            "elapsedSec": elapsed_sec,
            "stage": "CACHE_HIT"
        }

    # -------------------------------------------------------------
    # 1. STEP 1: Fast Packet Probe
    # -------------------------------------------------------------
    if target_id:
        logger.info(f"[PLACE STAGE 1: FAST PROBE] Probing Ranks for place target '{target_id}'...")
        pkt_res = await asyncio.to_thread(
            crawl_place_packet,
            keyword=keyword,
            target_id=target_id,
            proxy_url=proxy_url
        )

        if pkt_res.get("places"):
            db_mgr.save_or_update_cache(
                service_type="place",
                keyword=keyword,
                new_items=pkt_res["places"],
                engine_source="PACKET"
            )

        if pkt_res.get("targetFound"):
            elapsed_sec = time.time() - t0
            elapsed_ms = int(elapsed_sec * 1000)

            tp = pkt_res.get("targetItem", {})
            master_info = db_mgr.sync_master_item_info("place", target_id, tp)
            pkt_res["masterInfo"] = master_info

            db_mgr.update_target_daily_history(
                service_type="place",
                keyword=keyword,
                target_code=target_id,
                rank_num=pkt_res.get("targetRank"),
                product_title=tp.get("name"),
                mall_name=tp.get("category"),
                price=0
            )

            db_mgr.log_api_request(
                service_type="place",
                keyword=keyword,
                target_code=target_id,
                result_rank=pkt_res.get("targetRank"),
                target_found=True,
                is_cache_hit=False,
                cache_coverage_rank=pkt_res.get("totalExtracted", 0),
                engine_used="PACKET_CURL_CFFI",
                elapsed_ms=elapsed_ms,
                client_ip=client_ip,
                proxy_used=pkt_res.get("proxyUsed")
            )

            pkt_res["stage"] = "STAGE_1_PACKET"
            pkt_res["isCacheHit"] = False
            pkt_res["totalTime"] = elapsed_sec
            logger.info(f"★ Target Place '{target_id}' found in Stage 1 at Rank #{pkt_res.get('targetRank')}")
        # If not found in Stage 1 packet, return NOT_FOUND directly (Nodriver excluded for Place)
        db_mgr.log_api_request(
            service_type="place",
            keyword=keyword,
            target_code=target_id,
            result_rank=None,
            target_found=False,
            is_cache_hit=False,
            cache_coverage_rank=pkt_res.get("totalExtracted", 0),
            engine_used="PACKET",
            elapsed_ms=elapsed_ms,
            client_ip=client_ip,
            proxy_used=pkt_res.get("proxyUsed")
        )
        pkt_res["stage"] = "STAGE_1_PACKET"
        pkt_res["isCacheHit"] = False
        pkt_res["totalTime"] = elapsed_sec
        logger.info(f"Target Place '{target_id}' not found in top organic listings (0위)")
        return pkt_res

    # -------------------------------------------------------------
    # 2. STEP 2: Deep Nodriver Scroll
    # -------------------------------------------------------------
    try:
        deep_res = await crawl_place_deep_nodriver(
            keyword=keyword,
            target_id=target_id,
            max_scrolls=max_pages if max_pages > 5 else 12,
            headless=headless,
            block_media=block_media,
            proxy_url=proxy_url
        )

        if deep_res.get("places"):
            db_mgr.save_or_update_cache(
                service_type="place",
                keyword=keyword,
                new_items=deep_res["places"],
                engine_source="BROWSER"
            )

        elapsed_sec = time.time() - t0
        elapsed_ms = int(elapsed_sec * 1000)

        master_info = None
        if target_id and deep_res.get("targetFound"):
            tp = deep_res.get("targetItem", {})
            master_info = db_mgr.sync_master_item_info("place", target_id, tp)
            deep_res["masterInfo"] = master_info

            db_mgr.update_target_daily_history(
                service_type="place",
                keyword=keyword,
                target_code=target_id,
                rank_num=deep_res.get("targetRank"),
                product_title=tp.get("name"),
                mall_name=tp.get("category"),
                price=0
            )

        db_mgr.log_api_request(
            service_type="place",
            keyword=keyword,
            target_code=target_id,
            result_rank=deep_res.get("targetRank"),
            target_found=deep_res.get("targetFound", False),
            is_cache_hit=False,
            cache_coverage_rank=deep_res.get("totalExtracted", 0),
            engine_used="DEEP_NODRIVER",
            elapsed_ms=elapsed_ms,
            client_ip=client_ip,
            proxy_used=deep_res.get("proxyUsed")
        )

        deep_res["stage"] = "STAGE_2_NODRIVER"
        deep_res["isCacheHit"] = False
        deep_res["totalTime"] = elapsed_sec
        return deep_res

    except Exception as e:
        logger.error(f"Place Nodriver execution error: {e}")
        elapsed_sec = time.time() - t0
        db_mgr.log_api_request(
            service_type="place",
            keyword=keyword,
            target_code=target_id,
            result_rank=None,
            target_found=False,
            is_cache_hit=False,
            engine_used="DEEP_NODRIVER_ERROR",
            elapsed_ms=int(elapsed_sec * 1000),
            client_ip=client_ip,
            proxy_used=None
        )
        return {
            "status": "NOT_FOUND" if target_id else "FAILED",
            "stage": "STAGE_2_NODRIVER",
            "keyword": keyword,
            "targetCode": target_id,
            "targetFound": False,
            "totalExtracted": 0,
            "isCacheHit": False,
            "error": str(e),
            "totalTime": elapsed_sec
        }


def get_place_rank_sync(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 12,
    headless: bool = True,
    block_media: bool = True,
    proxy_url: Optional[str] = None,
    client_ip: Optional[str] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for get_place_rank."""
    return uc.loop().run_until_complete(
        get_place_rank(
            keyword=keyword,
            target_id=target_id,
            max_pages=max_pages,
            headless=headless,
            block_media=block_media,
            proxy_url=proxy_url,
            client_ip=client_ip
        )
    )
