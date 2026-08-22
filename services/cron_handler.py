import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional
import pymysql
from core.logger import get_logger
from config.db_manager import db_mgr
from services.shop.runner import get_shop_rank_sync
from services.place.runner import get_place_rank_sync

logger = get_logger("rank.cron")

API_BASE_URL = "http://127.0.0.1:8888"


def get_pending_ranks(service_name: str, limit: int = 100, force: bool = False, interval_hours: int = 3) -> List[Dict[str, Any]]:
    """
    Fetches pending items to check today from nshop_daily_ranks or nplace_daily_ranks.
    - Prioritizes 0-rank (rank = 0 / NULL) items so they are deeply searched up to 500 ranks.
    - Default interval: 3 hours for ranked items, 30 minutes for 0-rank items.
    """
    prefix = "nshop" if service_name in ("shop", "nshop") else "nplace"
    table = f"{prefix}_daily_ranks"
    pid_col = "target_id" if prefix == "nshop" else "place_id"
    extra_cols = ", price_compare_mid, product_mid" if prefix == "nshop" else ""

    where_time = "" if force else f"""
        AND (
            checked_at IS NULL
            OR ((rank = 0 OR rank IS NULL) AND checked_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE))
            OR checked_at < DATE_SUB(NOW(), INTERVAL {interval_hours} HOUR)
        )
    """

    conn = db_mgr.get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(f"""
                SELECT id, rank_date, query, {pid_col} AS target_id, rank_data, rank{extra_cols}
                FROM {table}
                WHERE rank_date = CURDATE()
                  AND is_active = TRUE
                  {where_time}
                ORDER BY checked_at IS NULL DESC,
                         (rank = 0 OR rank IS NULL) DESC,
                         checked_at ASC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pending ranks for {service_name}: {e}")
        return []
    finally:
        conn.close()


def save_master_item_info(service_name: str, target_id: str, info: Dict[str, Any]):
    """
    Saves master metadata to nshop_list or nplace_list.
    """
    prefix = "nshop" if service_name in ("shop", "nshop") else "nplace"
    table = f"{prefix}_list"

    conn = db_mgr.get_connection()
    try:
        with conn.cursor() as cur:
            if prefix == "nshop":
                price = info.get("price")
                try:
                    price_val = int(str(price).replace(",", "").replace("원", "").strip()) if price else None
                except Exception:
                    price_val = None

                score_val = None
                try:
                    score_str = str(info.get("score") or "").strip()
                    score_val = float(score_str) if score_str else None
                except Exception:
                    score_val = None

                cur.execute(f"""
                    INSERT INTO {table} (
                        target_id, product_name, product_title, brand, mall_name,
                        price, low_price, review_count, score_info, mall_count,
                        image_url, product_url, mall_product_id, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        product_name = VALUES(product_name),
                        product_title = VALUES(product_title),
                        brand = VALUES(brand),
                        mall_name = VALUES(mall_name),
                        price = VALUES(price),
                        low_price = VALUES(low_price),
                        review_count = VALUES(review_count),
                        score_info = VALUES(score_info),
                        mall_count = VALUES(mall_count),
                        image_url = VALUES(image_url),
                        product_url = VALUES(product_url),
                        mall_product_id = VALUES(mall_product_id),
                        updated_at = NOW()
                """, (
                    target_id,
                    info.get("productTitle") or info.get("productName", ""),
                    info.get("productTitle", ""),
                    info.get("brand", ""),
                    info.get("mallName", ""),
                    price_val,
                    info.get("lowPrice") or price_val,
                    int(info.get("reviewCount") or 0),
                    score_val,
                    int(info.get("mallCount") or 0),
                    info.get("imageUrl", ""),
                    info.get("productUrl", ""),
                    info.get("originalMallProductId", "")
                ))
            else:
                cur.execute(f"""
                    INSERT INTO {table} (
                        place_id, name, category, updated_at
                    )
                    VALUES (%s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        category = VALUES(category),
                        updated_at = NOW()
                """, (
                    target_id,
                    info.get("name", ""),
                    info.get("category", "")
                ))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving master item info for {service_name}/{target_id}: {e}")
    finally:
        conn.close()


def update_daily_rank_record(service_name: str, item_id: int, rank_val: int, rank_data: dict):
    """
    Updates today's rank and history timestamp in nshop_daily_ranks or nplace_daily_ranks.
    """
    prefix = "nshop" if service_name in ("shop", "nshop") else "nplace"
    table = f"{prefix}_daily_ranks"

    conn = db_mgr.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE {table}
                SET rank = %s,
                    rank_data = %s,
                    checked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (rank_val, json.dumps(rank_data, ensure_ascii=False), item_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating daily rank for item {item_id}: {e}")
    finally:
        conn.close()


def save_cron_execution_log(service_name: str, total_count: int, success_count: int, error_count: int, duration_ms: int):
    """
    Saves cron execution metrics in nshop_cron_logs or nplace_cron_logs.
    """
    prefix = "nshop" if service_name in ("shop", "nshop") else "nplace"
    table = f"{prefix}_cron_logs"

    status = "success" if error_count == 0 else ("partial" if success_count > 0 else "failed")
    conn = db_mgr.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {table}
                (job_type, site_code, status, total_count, success_count, error_count,
                 started_at, finished_at, duration_ms)
                VALUES ('rank_check', 'cron', %s, %s, %s, %s, NOW(), NOW(), %s)
            """, (status, total_count, success_count, error_count, duration_ms))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving cron log: {e}")
    finally:
        conn.close()


def _call_http_api(endpoint: str, keyword: str, target: str) -> Optional[Dict[str, Any]]:
    """
    Calls the local PM2 HTTP REST API server on port 8888.
    """
    try:
        query = urllib.parse.urlencode({"keyword": keyword, "target": target})
        url = f"{API_BASE_URL}/api/rank/{endpoint}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "NodriverCronChecker/2.3"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        logger.warning(f"HTTP API call to {url} failed ({e}), falling back to direct runner...")
        return None


def run_cron_check(service_name: str = "shop", limit: int = 100, force: bool = False) -> Dict[str, Any]:
    """
    Unified Cron Checker Entrypoint for Shop and Place.
    - Continuously checks pending items (interval: 3 hours).
    - Routes requests through the PM2 HTTP API server (port 8888) for unified logging and caching.
    - Updates nshop_daily_ranks / nplace_daily_ranks and master tables.
    """
    t0 = time.time()
    srv_key = "shop" if service_name in ("shop", "nshop") else "place"
    logger.info(f"Starting [{srv_key.upper()}] Cron Rank Check (Limit: {limit}, Force: {force})...")

    pending_items = get_pending_ranks(srv_key, limit=limit, force=force, interval_hours=3)
    if not pending_items:
        logger.info(f"No pending items to check for [{srv_key.upper()}].")
        return {"status": "SUCCESS", "total": 0, "processed": 0}

    total_count = len(pending_items)
    success_count = 0
    error_count = 0

    for idx, item in enumerate(pending_items, 1):
        kw = item["query"]
        target_id = item["target_id"]

        if srv_key == "shop":
            search_ids = []
            for sid in [target_id, item.get("price_compare_mid"), item.get("product_mid")]:
                if sid:
                    s_clean = str(sid).strip()
                    if s_clean and s_clean != '0' and s_clean not in search_ids:
                        search_ids.append(s_clean)

            if not search_ids:
                search_ids = [str(target_id).strip()]

            target_str = ",".join(search_ids)

            # 1. Route through PM2 HTTP API
            api_res = _call_http_api("shop", kw, target_str)
            if api_res:
                rank_val = api_res.get("rank") or 0
                prod_info = api_res.get("product") or {}
                status_ok = api_res.get("success", False) or (api_res.get("status") == "SUCCESS")
            else:
                # In-process Fallback
                fb_res = get_shop_rank_sync(keyword=kw, target_id=target_str, max_pages=10)
                rank_val = fb_res.get("targetRank") or 0
                prod_info = fb_res.get("targetProduct") or {}
                status_ok = (fb_res.get("status") == "SUCCESS")

            if prod_info:
                save_master_item_info("shop", target_id, prod_info)

        else:
            api_res = _call_http_api("place", kw, target_id)
            if api_res:
                rank_val = api_res.get("rank") or 0
                place_info = api_res.get("place") or {}
                status_ok = api_res.get("success", False) or (api_res.get("status") == "SUCCESS")
            else:
                fb_res = get_place_rank_sync(keyword=kw, target_id=target_id, max_pages=10)
                rank_val = fb_res.get("targetRank") or 0
                place_info = fb_res.get("targetItem") or {}
                status_ok = (fb_res.get("status") == "SUCCESS")

            if place_info:
                save_master_item_info("place", target_id, place_info)

        # Build rank_data timeline
        time_key = time.strftime("%H:%M:%S.000")
        rank_data = {}
        if item.get("rank_data"):
            try:
                rank_data = json.loads(item["rank_data"])
            except Exception:
                pass
        rank_data[time_key] = rank_val

        # Update daily ranks
        update_daily_rank_record(srv_key, item["id"], rank_val, rank_data)

        if status_ok:
            success_count += 1
        else:
            error_count += 1

        rank_display = f"Rank #{rank_val}" if rank_val > 0 else "0위 (순위밖)"
        logger.info(f"[{idx:03d}/{total_count:03d}] [PM2_API_HTTP] | {kw:<12} | {target_id:<15} | {rank_display}")

    duration_ms = int((time.time() - t0) * 1000)
    save_cron_execution_log(srv_key, total_count, success_count, error_count, duration_ms)

    logger.info(f"[{srv_key.upper()}] Cron Completed: Total {total_count} (Success: {success_count}, Error: {error_count}) in {duration_ms/1000:.2f}s")
    return {
        "status": "SUCCESS",
        "service": srv_key,
        "total": total_count,
        "success": success_count,
        "error": error_count,
        "durationMs": duration_ms
    }
