import json
import time
import urllib.parse
from typing import Dict, Any, Optional
from curl_cffi import requests as cffi_requests
from core.logger import get_logger
from core.ackey import generate_ackey
from config.proxy_manager import proxy_mgr
from services.place.parser import parse_mobile_place_items

logger = get_logger("rank.place.packet")


def crawl_place_packet(
    keyword: str,
    target_id: Optional[str] = None,
    max_retries: int = 6,
    proxy_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crawls organic place ranking via curl_cffi.
    """
    t0 = time.time()
    targets = {str(x).strip() for x in target_id.split(",")} if target_id else set()

    for attempt in range(max_retries):
        current_proxy = proxy_url or proxy_mgr.get_next_proxy()
        proxies = {"http": current_proxy, "https": current_proxy} if current_proxy else None

        ackey = generate_ackey()
        query_encoded = urllib.parse.quote(keyword)
        url = f"https://m.search.naver.com/search.naver?where=m&sm=top_hty&fbm=0&ie=utf8&query={query_encoded}&ackey={ackey}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Referer": "https://m.naver.com/",
        }

        try:
            r = cffi_requests.get(url, headers=headers, proxies=proxies, impersonate="chrome120", timeout=8.0)
            if r.status_code == 200 and len(r.text) > 5000:
                places = parse_mobile_place_items(r.text, start_rank=1)

                target_found = False
                target_rank = None
                target_item = None

                if targets:
                    for p in places:
                        if p["placeId"] in targets:
                            target_found = True
                            target_rank = p["rank"]
                            target_item = p
                            break

                return {
                    "status": "SUCCESS",
                    "engine": "PACKET_CURL_CFFI",
                    "keyword": keyword,
                    "targetCode": target_id,
                    "targetFound": target_found,
                    "targetRank": target_rank,
                    "targetItem": target_item,
                    "totalExtracted": len(places),
                    "places": places,
                    "elapsedSec": time.time() - t0,
                    "proxyUsed": current_proxy
                }
            elif r.status_code in (418, 403, 429):
                from config.db_manager import db_mgr
                db_mgr.log_block_event(
                    service_type="place",
                    keyword=keyword,
                    target_code=target_id,
                    status_code=r.status_code,
                    error_message=f"HTTP {r.status_code} blocked on place packet probe.",
                    proxy_url=current_proxy,
                    engine_used="PACKET_CURL_CFFI"
                )
                if current_proxy:
                    proxy_mgr.mark_proxy_failed(current_proxy, reason=f"HTTP {r.status_code} Blocked")
                time.sleep(0.3)
        except Exception as e:
            if "418" in str(e) or "403" in str(e):
                from config.db_manager import db_mgr
                db_mgr.log_block_event(
                    service_type="place",
                    keyword=keyword,
                    target_code=target_id,
                    status_code=418 if "418" in str(e) else 403,
                    error_message=str(e),
                    proxy_url=current_proxy,
                    engine_used="PACKET_CURL_CFFI"
                )
            if current_proxy:
                proxy_mgr.mark_proxy_failed(current_proxy, reason=str(e))
            time.sleep(0.2)

    return {
        "status": "FAILED",
        "engine": "PACKET_CURL_CFFI",
        "keyword": keyword,
        "targetCode": target_id,
        "targetFound": False,
        "totalExtracted": 0,
        "places": [],
        "elapsedSec": time.time() - t0,
        "error": "All proxy retries exhausted or blocked"
    }
