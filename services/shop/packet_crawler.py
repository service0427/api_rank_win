import json
import time
import urllib.parse
from typing import Dict, Any, Optional
from curl_cffi import requests as cffi_requests
from core.logger import get_logger
from core.ackey import generate_ackey
from config.proxy_manager import proxy_mgr
from services.shop.parser import extract_products_from_mobile_html

logger = get_logger("rank.shop.packet")


def crawl_shop_packet(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 10,
    max_retries: int = 4,
    proxy_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crawls mobile pure organic shopping products via high-speed curl_cffi packets across multiple pages (up to 500 items).
    - Page 1 is fetched first in 0.5s. If target is found, returns immediately.
    - If target is deeper (e.g. Page 2, 3, 5), seamlessly iterates pages in 0.2s/page.
    - Supports automatic SOCKS5 proxy rotation on 403 or throttling.
    """
    t0 = time.time()
    targets = {str(x).strip() for x in target_id.split(",")} if target_id else set()

    all_products = []
    seen_ids = set()
    current_rank = 1
    target_found = False
    target_rank = None
    target_prod = None
    last_proxy = proxy_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://m.naver.com/",
    }

    query_encoded = urllib.parse.quote(keyword)

    for page in range(1, max_pages + 1):
        page_prods = []
        page_success = False

        for attempt in range(max_retries):
            current_proxy = proxy_url or proxy_mgr.get_next_proxy()
            last_proxy = current_proxy
            proxies = {"http": current_proxy, "https": current_proxy} if current_proxy else None

            ackey = generate_ackey()
            if page == 1:
                url = f"https://m.search.naver.com/search.naver?where=m_shopping&sm=top_hty&fbm=0&ie=utf8&query={query_encoded}&ackey={ackey}"
            else:
                url = f"https://m.search.naver.com/search.naver?where=m_shopping&page={page}&qdt=0&query={query_encoded}&ackey={ackey}"

            try:
                r = cffi_requests.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    impersonate="chrome120",
                    timeout=6.0
                )

                if r.status_code == 200 and len(r.text) > 5000:
                    prods = extract_products_from_mobile_html(r.text, start_rank=current_rank)
                    if prods:
                        page_prods = prods
                        page_success = True
                        break
                    else:
                        # Empty page reached (end of search results)
                        page_success = True
                        break

                elif r.status_code in (418, 403, 429):
                    from config.db_manager import db_mgr
                    db_mgr.log_block_event(
                        service_type="shop",
                        keyword=keyword,
                        target_code=target_id,
                        status_code=r.status_code,
                        error_message=f"HTTP {r.status_code} blocked on packet page {page}. Length: {len(r.text)}",
                        proxy_url=current_proxy,
                        engine_used="PACKET"
                    )
                    if current_proxy:
                        proxy_mgr.mark_proxy_failed(current_proxy, reason=f"HTTP {r.status_code} Blocked")
                    time.sleep(0.2)

            except Exception as e:
                if current_proxy:
                    proxy_mgr.mark_proxy_failed(current_proxy, reason=str(e))
                time.sleep(0.2)

        if not page_success or not page_prods:
            break

        # Process page products
        for p in page_prods:
            p_id = str(p.get("id") or p.get("nvMid") or "")
            p_ch = str(p.get("channelProductId") or "")
            p_orig = str(p.get("originalMallProductId") or "")

            item_key = p_id or p_ch or p_orig
            if item_key in seen_ids:
                continue
            seen_ids.add(item_key)

            p["rank"] = current_rank
            all_products.append(p)
            current_rank += 1

            if targets and not target_found:
                if any(t in [p_id, p_ch, p_orig] for t in targets):
                    target_found = True
                    target_rank = p["rank"]
                    target_prod = p

        # If target found, we can return early!
        if target_id and target_found:
            logger.info(f"★ Target '{target_id}' found on Page {page} at Rank #{target_rank} ({time.time() - t0:.2f}s)!")
            break

    if all_products:
        return {
            "status": "SUCCESS" if (not target_id or target_found) else "NOT_FOUND",
            "engine": "PACKET",
            "keyword": keyword,
            "targetCode": target_id,
            "targetFound": target_found,
            "targetRank": target_rank,
            "targetProduct": target_prod,
            "totalExtracted": len(all_products),
            "products": all_products,
            "elapsedSec": time.time() - t0,
            "proxyUsed": last_proxy
        }

    return {
        "status": "FAILED",
        "engine": "PACKET",
        "keyword": keyword,
        "targetCode": target_id,
        "targetFound": False,
        "totalExtracted": 0,
        "products": [],
        "elapsedSec": time.time() - t0,
        "error": "All proxy retries exhausted or blocked"
    }
