import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import pymysql
from core.logger import get_logger

logger = get_logger("rank.db")

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "rank",
    "password": "Tech1324",
    "database": "rank",
    "charset": "utf8mb4",
    "autocommit": True
}


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("원", "").strip()
        return int(val)
    except Exception:
        return default


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace(",", "").strip()
        return float(val)
    except Exception:
        return default


class DBManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
        return cls._instance

    def get_connection(self):
        return pymysql.connect(**DB_CONFIG)

    def get_cached_search(
        self,
        service_type: str,
        keyword: str,
        target_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Queries 60-minute active cache from api_search_cache.
        """
        targets = {str(x).strip() for x in target_code.split(",")} if target_code else set()

        try:
            conn = self.get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute("""
                    SELECT max_rank, total_items, data_json, 
                           TIMESTAMPDIFF(SECOND, NOW(), expires_at) as remain_sec,
                           created_at, updated_at
                    FROM api_search_cache
                    WHERE service_type = %s 
                      AND keyword = %s 
                      AND expires_at > NOW()
                    LIMIT 1;
                """, (service_type, keyword))
                row = cur.fetchone()

            conn.close()

            if not row or not row.get("data_json"):
                return {"hit": False, "reason": "NO_CACHE_FOUND", "cachedMaxRank": 0}

            data = json.loads(row["data_json"])
            max_rank = row["max_rank"]
            remain_sec = row["remain_sec"]

            # Scenario A: Target specified -> check if present in cached items
            if targets:
                for item in data:
                    item_ids = [
                        str(item.get("id") or ""),
                        str(item.get("nvMid") or ""),
                        str(item.get("channelProductId") or ""),
                        str(item.get("originalMallProductId") or ""),
                        str(item.get("placeId") or "")
                    ]
                    if any(t in item_ids for t in targets):
                        logger.info(f"[CACHE HIT] Target '{target_code}' found in 60-min cache at Rank #{item['rank']}! (TTL: {remain_sec}s remain)")
                        return {
                            "hit": True,
                            "targetFound": True,
                            "targetRank": item["rank"],
                            "targetProduct": item if service_type == "shop" else None,
                            "targetItem": item if service_type == "place" else None,
                            "totalExtracted": len(data),
                            "products": data if service_type == "shop" else None,
                            "places": data if service_type == "place" else None,
                            "cachedMaxRank": max_rank,
                            "remainTTLSec": remain_sec,
                            "engine": "DB_CACHE_60MIN"
                        }

                logger.info(f"[CACHE MISS] Keyword '{keyword}' is cached up to Rank #{max_rank}, but target '{target_code}' is deeper.")
                return {
                    "hit": False,
                    "reason": "TARGET_NOT_IN_CACHED_RANGE",
                    "cachedMaxRank": max_rank,
                    "remainTTLSec": remain_sec
                }

            # Scenario B: Target omitted (Full Mode)
            else:
                if max_rank >= 500 or service_type == "place":
                    logger.info(f"[CACHE HIT: FULL] Keyword '{keyword}' cached with {len(data)} items up to Rank #{max_rank}.")
                    return {
                        "hit": True,
                        "targetFound": False,
                        "totalExtracted": len(data),
                        "products": data if service_type == "shop" else None,
                        "places": data if service_type == "place" else None,
                        "cachedMaxRank": max_rank,
                        "remainTTLSec": remain_sec,
                        "engine": "DB_CACHE_60MIN"
                    }
                else:
                    return {
                        "hit": False,
                        "reason": "INSUFFICIENT_COVERAGE",
                        "cachedMaxRank": max_rank,
                        "remainTTLSec": remain_sec
                    }

        except Exception as e:
            logger.error(f"Error querying search cache: {e}")
            return {"hit": False, "reason": str(e), "cachedMaxRank": 0}

    def save_or_update_cache(
        self,
        service_type: str,
        keyword: str,
        new_items: List[Dict[str, Any]],
        engine_source: str = "PACKET"
    ):
        """
        Saves or merges items into api_search_cache with 60-minute TTL.
        Records engine_source (PACKET / NODRIVER) and automatically purges expired cache (>2 hours old).
        """
        if not new_items:
            return

        try:
            conn = self.get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # 0. Lightweight cleanup of expired cache (> 2 hours old)
                cur.execute("DELETE FROM api_search_cache WHERE expires_at < DATE_SUB(NOW(), INTERVAL 2 HOUR);")

                # 1. Check existing items
                cur.execute("""
                    SELECT data_json, max_rank FROM api_search_cache
                    WHERE service_type = %s AND keyword = %s
                """, (service_type, keyword))
                row = cur.fetchone()

                combined_items = []
                seen_ids = set()

                for item in new_items:
                    item_id = str(item.get("id") or item.get("nvMid") or item.get("placeId") or "")
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        combined_items.append(item)

                if row and row.get("data_json"):
                    try:
                        prev_items = json.loads(row["data_json"])
                        for item in prev_items:
                            item_id = str(item.get("id") or item.get("nvMid") or item.get("placeId") or "")
                            if item_id and item_id not in seen_ids:
                                seen_ids.add(item_id)
                                combined_items.append(item)
                    except Exception:
                        pass

                combined_items.sort(key=lambda x: x.get("rank", 99999))
                for idx, itm in enumerate(combined_items):
                    itm["rank"] = idx + 1

                max_rank = len(combined_items)
                total_items = len(combined_items)
                json_data = json.dumps(combined_items, ensure_ascii=False)

                cur.execute("""
                    INSERT INTO api_search_cache 
                        (service_type, keyword, max_rank, total_items, engine_source, data_json, created_at, updated_at, expires_at)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, NOW(), NOW(), DATE_ADD(NOW(), INTERVAL 60 MINUTE))
                    ON DUPLICATE KEY UPDATE
                        max_rank = VALUES(max_rank),
                        total_items = VALUES(total_items),
                        engine_source = VALUES(engine_source),
                        data_json = VALUES(data_json),
                        updated_at = NOW(),
                        expires_at = DATE_ADD(NOW(), INTERVAL 60 MINUTE);
                """, (service_type, keyword, max_rank, total_items, engine_source, json_data))

            conn.commit()
            conn.close()
            logger.info(f"Saved {total_items} items to 60-min search cache for '{keyword}' [Source: {engine_source}] (Max Rank: #{max_rank}).")

        except Exception as e:
            logger.error(f"Error updating search cache for '{keyword}': {e}")

    def get_master_item_info(self, service_type: str, target_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves master company/product metadata from nshop_list or nplace_list.
        """
        prefix = "nshop" if service_type in ("shop", "nshop") else "nplace"
        table = f"{prefix}_list"
        pid_col = "target_id" if prefix == "nshop" else "place_id"

        try:
            conn = self.get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(f"SELECT * FROM {table} WHERE {pid_col} = %s LIMIT 1;", (target_id,))
                row = cur.fetchone()
            conn.close()
            return row
        except Exception as e:
            logger.error(f"Error fetching master item info from {table} for {target_id}: {e}")
            return None

    def sync_master_item_info(
        self,
        service_type: str,
        target_id: str,
        info: Dict[str, Any],
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Smart sync to nshop_list / nplace_list.
        Updates if:
        1. Record does not exist.
        2. updated_at is older than 24 hours.
        3. Information (price, title, review count, etc.) has changed.
        """
        if not target_id or not info:
            return None

        prefix = "nshop" if service_type in ("shop", "nshop") else "nplace"
        table = f"{prefix}_list"
        pid_col = "target_id" if prefix == "nshop" else "place_id"

        try:
            conn = self.get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # 1. Check existing record
                cur.execute(f"""
                    SELECT *, TIMESTAMPDIFF(HOUR, updated_at, NOW()) as age_hours 
                    FROM {table} 
                    WHERE {pid_col} = %s LIMIT 1;
                """, (target_id,))
                existing = cur.fetchone()

                should_update = False
                if not existing:
                    should_update = True
                elif force or existing.get("age_hours", 999) >= 24:
                    should_update = True
                else:
                    # Check if changed
                    if prefix == "nshop":
                        new_price = _safe_int(info.get("price"))
                        old_price = _safe_int(existing.get("price"))
                        new_title = (info.get("productTitle") or info.get("productName") or "").strip()
                        old_title = (existing.get("product_title") or existing.get("product_name") or "").strip()
                        if new_price != old_price or (new_title and new_title != old_title):
                            should_update = True
                    else:
                        new_name = (info.get("name") or "").strip()
                        old_name = (existing.get("name") or "").strip()
                        if new_name and new_name != old_name:
                            should_update = True

                if should_update:
                    if prefix == "nshop":
                        p_name = info.get("productTitle") or info.get("productName", "")
                        p_title = info.get("productTitle", "")
                        brand = info.get("brand", "")
                        mall = info.get("mallName", "")
                        price = _safe_int(info.get("price"))
                        low_p = _safe_int(info.get("lowPrice") or price)
                        rev_cnt = _safe_int(info.get("reviewCount"))
                        score = _safe_float(info.get("score"))
                        mall_cnt = _safe_int(info.get("mallCount"))
                        img = info.get("imageUrl", "")
                        p_url = info.get("productUrl", "")
                        orig_id = info.get("originalMallProductId", "")

                        cur.execute(f"""
                            INSERT INTO {table} (
                                target_id, product_name, product_title, brand, mall_name,
                                price, low_price, review_count, score_info, mall_count,
                                image_url, product_url, mall_product_id, created_at, updated_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            ON DUPLICATE KEY UPDATE
                                product_name = VALUES(product_name),
                                product_title = VALUES(product_title),
                                brand = IF(VALUES(brand) != '', VALUES(brand), brand),
                                mall_name = IF(VALUES(mall_name) != '', VALUES(mall_name), mall_name),
                                price = VALUES(price),
                                low_price = VALUES(low_price),
                                review_count = VALUES(review_count),
                                score_info = VALUES(score_info),
                                mall_count = VALUES(mall_count),
                                image_url = IF(VALUES(image_url) != '', VALUES(image_url), image_url),
                                product_url = IF(VALUES(product_url) != '', VALUES(product_url), product_url),
                                mall_product_id = IF(VALUES(mall_product_id) != '', VALUES(mall_product_id), mall_product_id),
                                updated_at = NOW();
                        """, (
                            target_id, p_name, p_title, brand, mall, price, low_p, rev_cnt, score, mall_cnt, img, p_url, orig_id
                        ))
                    else:
                        name = info.get("name", "")
                        cat = info.get("category", "")
                        vis_cnt = _safe_int(info.get("visitorReviewCount"))
                        blog_cnt = _safe_int(info.get("blogCafeReviewCount"))
                        save_cnt = str(info.get("saveCount") or "0")
                        img = info.get("imageUrl", "")

                        cur.execute(f"""
                            INSERT INTO {table} (
                                place_id, name, category, visitor_review_count, first_visitor_review_count,
                                blog_cafe_review_count, first_blog_cafe_review_count, save_count, first_save_count,
                                image_url, created_at, updated_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            ON DUPLICATE KEY UPDATE
                                name = VALUES(name),
                                category = VALUES(category),
                                visitor_review_count = VALUES(visitor_review_count),
                                first_visitor_review_count = CASE WHEN first_visitor_review_count = 0 THEN VALUES(visitor_review_count) ELSE first_visitor_review_count END,
                                blog_cafe_review_count = VALUES(blog_cafe_review_count),
                                first_blog_cafe_review_count = CASE WHEN first_blog_cafe_review_count = 0 THEN VALUES(blog_cafe_review_count) ELSE first_blog_cafe_review_count END,
                                save_count = VALUES(save_count),
                                first_save_count = CASE WHEN first_save_count = '0' THEN VALUES(save_count) ELSE first_save_count END,
                                image_url = IF(VALUES(image_url) != '', VALUES(image_url), image_url),
                                updated_at = NOW();
                        """, (
                            target_id, name, cat, vis_cnt, vis_cnt, blog_cnt, blog_cnt, save_cnt, save_cnt, img
                        ))

                    conn.commit()
                    logger.info(f"Master metadata updated in {table} for target [{target_id}].")

                # Fetch and return the latest master metadata
                cur.execute(f"SELECT * FROM {table} WHERE {pid_col} = %s LIMIT 1;", (target_id,))
                latest = cur.fetchone()

            conn.close()
            return latest

        except Exception as e:
            logger.error(f"Error syncing master item info for {service_type}/{target_id}: {e}")
            return None

    def log_api_request(
        self,
        service_type: str,
        keyword: str,
        target_code: Optional[str] = None,
        result_rank: Optional[int] = None,
        target_found: bool = False,
        is_cache_hit: bool = False,
        cache_coverage_rank: int = 0,
        engine_used: Optional[str] = None,
        elapsed_ms: int = 0,
        client_ip: Optional[str] = None,
        proxy_used: Optional[str] = None
    ):
        """
        Logs API request metrics into api_request_logs.
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO api_request_logs
                    (service_type, keyword, target_code, result_rank, target_found,
                     is_cache_hit, cache_coverage_rank, engine_used, elapsed_ms, client_ip, proxy_used, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    service_type, keyword, target_code, result_rank, int(target_found),
                    int(is_cache_hit), cache_coverage_rank, engine_used, elapsed_ms,
                    client_ip, proxy_used
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging API request: {e}")

    def update_target_daily_history(
        self,
        service_type: str,
        keyword: str,
        target_code: str,
        rank_num: Optional[int],
        product_title: Optional[str] = None,
        mall_name: Optional[str] = None,
        price: int = 0
    ):
        """
        Updates daily rank trend history into api_target_daily_history.
        Detects rank changes and records detailed transitions in api_target_rank_changes.
        """
        if not target_code:
            return

        try:
            conn = self.get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # 1. Fetch previous rank for change comparison
                cur.execute("""
                    SELECT rank_num, product_title, mall_name, price 
                    FROM api_target_daily_history
                    WHERE service_type = %s AND keyword = %s AND target_code = %s AND check_date = CURDATE()
                    LIMIT 1;
                """, (service_type, keyword, target_code))
                prev_row = cur.fetchone()

                curr_r = rank_num if (rank_num is not None and rank_num > 0) else 0
                prev_r = prev_row.get("rank_num") if (prev_row and prev_row.get("rank_num") is not None) else None

                # 2. Check if rank has changed
                if prev_row is None:
                    # First time seen today
                    change_type = "FIRST_SEEN"
                    rank_diff = 0
                    cur.execute("""
                        INSERT INTO api_target_rank_changes
                        (service_type, keyword, target_code, prev_rank, curr_rank, rank_diff, change_type, product_title, mall_name, price, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        service_type, keyword, target_code, None, curr_r, rank_diff, change_type,
                        product_title or (prev_row.get("product_title") if prev_row else None),
                        mall_name or (prev_row.get("mall_name") if prev_row else None),
                        price
                    ))
                    logger.info(f"[RANK FIRST SEEN] [{keyword} + {target_code}]: Rank #{curr_r}")

                elif prev_r != curr_r:
                    # Rank changed!
                    if prev_r == 0 and curr_r > 0:
                        change_type = "ENTER"
                        rank_diff = curr_r
                    elif prev_r > 0 and curr_r == 0:
                        change_type = "OUT"
                        rank_diff = -prev_r
                    elif curr_r < prev_r:
                        change_type = "UP"
                        rank_diff = prev_r - curr_r  # Positive diff means rose N ranks
                    else:
                        change_type = "DOWN"
                        rank_diff = prev_r - curr_r  # Negative diff means fell N ranks

                    cur.execute("""
                        INSERT INTO api_target_rank_changes
                        (service_type, keyword, target_code, prev_rank, curr_rank, rank_diff, change_type, product_title, mall_name, price, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        service_type, keyword, target_code, prev_r, curr_r, rank_diff, change_type,
                        product_title or (prev_row.get("product_title") if prev_row else None),
                        mall_name or (prev_row.get("mall_name") if prev_row else None),
                        price
                    ))
                    logger.info(f"★ [RANK CHANGE: {change_type}] [{keyword} + {target_code}]: Rank #{prev_r} -> Rank #{curr_r} (Diff: {rank_diff:+d})")

                # 3. Update daily history
                cur.execute("""
                    INSERT INTO api_target_daily_history
                    (service_type, keyword, target_code, check_date, rank_num, product_title, mall_name, price, check_count, first_checked_at, last_checked_at)
                    VALUES
                    (%s, %s, %s, CURDATE(), %s, %s, %s, %s, 1, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE
                        rank_num = VALUES(rank_num),
                        product_title = IF(VALUES(product_title) IS NOT NULL AND VALUES(product_title) != '', VALUES(product_title), product_title),
                        mall_name = IF(VALUES(mall_name) IS NOT NULL AND VALUES(mall_name) != '', VALUES(mall_name), mall_name),
                        price = IF(VALUES(price) > 0, VALUES(price), price),
                        check_count = check_count + 1,
                        last_checked_at = NOW();
                """, (
                    service_type, keyword, target_code, rank_num, product_title, mall_name, price
                ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating target daily history & rank changes: {e}")

    def log_block_event(
        self,
        service_type: str,
        keyword: str,
        target_code: Optional[str] = None,
        status_code: int = 418,
        error_message: Optional[str] = None,
        proxy_url: Optional[str] = None,
        client_ip: Optional[str] = None,
        engine_used: Optional[str] = None
    ):
        """
        Logs 418 / rate limit / bot block incidents into api_block_logs table.
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO api_block_logs
                    (service_type, keyword, target_code, status_code, error_message, proxy_url, client_ip, engine_used, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    service_type, keyword, target_code, status_code,
                    (error_message or "")[:1000], proxy_url, client_ip, engine_used
                ))
            conn.commit()
            conn.close()
            logger.warning(f"🚨 [BLOCKED {status_code}] Logged block event for [{service_type.upper()}] '{keyword}' (Proxy: {proxy_url})")
        except Exception as e:
            logger.error(f"Error logging block event: {e}")


db_mgr = DBManager()
