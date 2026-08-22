import asyncio
import time
from typing import Dict, Any, Optional
import nodriver as uc
from core.logger import get_logger
from config.settings import ENABLE_DEEP_NODRIVER
from config.db_manager import db_mgr
from services.shop.packet_crawler import crawl_shop_packet
from services.shop.deep_crawler import crawl_shop_deep_nodriver

logger = get_logger("rank.shop.runner")


async def get_shop_rank(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 13,
    headless: bool = True,
    block_media: bool = True,
    proxy_url: Optional[str] = None,
    client_ip: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified Shopping Rank Service with 60-Minute DB Cache & Master List (nshop_list) Auto-Sync.
    """
    t0 = time.time()

    # -------------------------------------------------------------
    # 0. STEP 0: 60-Minute DB Cache Check
    # -------------------------------------------------------------
    cached = db_mgr.get_cached_search(service_type="shop", keyword=keyword, target_code=target_id)
    if cached.get("hit"):
        elapsed_sec = time.time() - t0
        elapsed_ms = int(elapsed_sec * 1000)

        master_info = None
        if target_id and cached.get("targetProduct"):
            tp = cached["targetProduct"]
            # Smart Sync to nshop_list (24h or change based)
            master_info = db_mgr.sync_master_item_info("shop", target_id, tp)

            db_mgr.update_target_daily_history(
                service_type="shop",
                keyword=keyword,
                target_code=target_id,
                rank_num=cached.get("targetRank"),
                product_title=tp.get("productTitle"),
                mall_name=tp.get("mallName"),
                price=tp.get("price", 0)
            )

        db_mgr.log_api_request(
            service_type="shop",
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
            "targetProduct": cached.get("targetProduct"),
            "masterInfo": master_info,
            "totalExtracted": cached.get("totalExtracted", 0),
            "cachedMaxRank": cached.get("cachedMaxRank", 0),
            "remainTTLSec": cached.get("remainTTLSec", 3600),
            "products": cached.get("products"),
            "elapsedSec": elapsed_sec,
            "stage": "CACHE_HIT"
        }

    # -------------------------------------------------------------
    # 1. STEP 1: Fast Packet Probe (1~72위, 0.5초 소요)
    # -------------------------------------------------------------
    logger.info(f"[STAGE 1: FAST PROBE] Probing Ranks for '{keyword}' (Target: {target_id})...")
    pkt_res = await asyncio.to_thread(
        crawl_shop_packet,
        keyword=keyword,
        target_id=target_id,
        max_pages=max_pages,
        proxy_url=proxy_url
    )

    if pkt_res.get("products"):
        db_mgr.save_or_update_cache(
            service_type="shop",
            keyword=keyword,
            new_items=pkt_res["products"],
            engine_source="PACKET"
        )

    if target_id:
        if pkt_res.get("targetFound"):
            elapsed_sec = time.time() - t0
            elapsed_ms = int(elapsed_sec * 1000)

            tp = pkt_res.get("targetProduct", {})
            master_info = db_mgr.sync_master_item_info("shop", target_id, tp)
            pkt_res["masterInfo"] = master_info

            db_mgr.update_target_daily_history(
                service_type="shop",
                keyword=keyword,
                target_code=target_id,
                rank_num=pkt_res.get("targetRank"),
                product_title=tp.get("productTitle"),
                mall_name=tp.get("mallName"),
                price=tp.get("price", 0)
            )

            db_mgr.log_api_request(
                service_type="shop",
                keyword=keyword,
                target_code=target_id,
                result_rank=pkt_res.get("targetRank"),
                target_found=True,
                is_cache_hit=False,
                cache_coverage_rank=pkt_res.get("totalExtracted", 70),
                engine_used="PACKET_CURL_CFFI",
                elapsed_ms=elapsed_ms,
                client_ip=client_ip,
                proxy_used=pkt_res.get("proxyUsed")
            )

            pkt_res["stage"] = "STAGE_1_PACKET"
            pkt_res["isCacheHit"] = False
            pkt_res["totalTime"] = elapsed_sec
            logger.info(f"★ Target '{target_id}' found in Stage 1 at Rank #{pkt_res.get('targetRank')} ({elapsed_sec:.2f}s)")
            return pkt_res

        # If target not found in Stage 1 packet and running in packet-only mode:
        if not ENABLE_DEEP_NODRIVER:
            elapsed_sec = time.time() - t0
            db_mgr.log_api_request(
                service_type="shop",
                keyword=keyword,
                target_code=target_id,
                result_rank=None,
                target_found=False,
                is_cache_hit=False,
                cache_coverage_rank=pkt_res.get("totalExtracted", 70),
                engine_used="PACKET",
                elapsed_ms=int(elapsed_sec * 1000),
                client_ip=client_ip,
                proxy_used=pkt_res.get("proxyUsed")
            )
            pkt_res["stage"] = "STAGE_1_PACKET"
            pkt_res["isCacheHit"] = False
            pkt_res["totalTime"] = elapsed_sec
            logger.info(f"Target '{target_id}' not found in top organic listings. Returning NOT_FOUND (0위) directly.")
            return pkt_res

        logger.info(f"[STAGE 2: DEEP EXPANSION] Target not in top 72. Launching Nodriver for deep search...")
    else:
        # Full mode (when target_id is None): return all packet items if deep nodriver is disabled
        if not ENABLE_DEEP_NODRIVER:
            elapsed_sec = time.time() - t0
            pkt_res["stage"] = "STAGE_1_PACKET"
            pkt_res["isCacheHit"] = False
            pkt_res["totalTime"] = elapsed_sec
            return pkt_res

    # -------------------------------------------------------------
    # 2. STEP 2: Deep Nodriver Search (73~500위 심층 탐색)
    # -------------------------------------------------------------
    try:
        deep_res = await crawl_shop_deep_nodriver(
            keyword=keyword,
            target_id=target_id,
            max_pages=max_pages,
            headless=headless,
            block_media=block_media,
            proxy_url=proxy_url
        )

        if deep_res.get("products"):
            db_mgr.save_or_update_cache(
                service_type="shop",
                keyword=keyword,
                new_items=deep_res["products"],
                engine_source="BROWSER"
            )

        elapsed_sec = time.time() - t0
        elapsed_ms = int(elapsed_sec * 1000)

        master_info = None
        if target_id and deep_res.get("targetFound"):
            tp = deep_res.get("targetProduct", {})
            master_info = db_mgr.sync_master_item_info("shop", target_id, tp)
            deep_res["masterInfo"] = master_info

            db_mgr.update_target_daily_history(
                service_type="shop",
                keyword=keyword,
                target_code=target_id,
                rank_num=deep_res.get("targetRank"),
                product_title=tp.get("productTitle"),
                mall_name=tp.get("mallName"),
                price=tp.get("price", 0)
            )

        db_mgr.log_api_request(
            service_type="shop",
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
        logger.error(f"Stage 2 Nodriver execution error: {e}")
        elapsed_sec = time.time() - t0
        db_mgr.log_api_request(
            service_type="shop",
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


def get_shop_rank_sync(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 13,
    headless: bool = True,
    block_media: bool = True,
    proxy_url: Optional[str] = None,
    client_ip: Optional[str] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for get_shop_rank."""
    return uc.loop().run_until_complete(
        get_shop_rank(
            keyword=keyword,
            target_id=target_id,
            max_pages=max_pages,
            headless=headless,
            block_media=block_media,
            proxy_url=proxy_url,
            client_ip=client_ip
        )
    )
