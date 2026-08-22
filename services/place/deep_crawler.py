import json
import time
import urllib.parse
from typing import Dict, Any, Optional, List
import nodriver as uc
from core.logger import get_logger
from core.browser import start_stealth_browser, close_browser, get_browser_semaphore
from config.proxy_manager import proxy_mgr
from services.place.parser import parse_mobile_place_items

logger = get_logger("rank.place.deep")


async def crawl_place_deep_nodriver(
    keyword: str,
    target_id: Optional[str] = None,
    max_scrolls: int = 12,
    headless: bool = True,
    block_media: bool = True,
    proxy_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crawls Place organic rankings up to ~1,000 items via Mobile Nodriver.
    """
    t0 = time.time()
    targets = {str(x).strip() for x in target_id.split(",")} if target_id else set()
    current_proxy = proxy_url or proxy_mgr.get_next_proxy()

    sem = get_browser_semaphore()
    async with sem:
        browser = await start_stealth_browser(
            headless=headless,
            is_mobile=True,
            block_media=block_media,
            proxy_url=current_proxy
        )

        try:
            query_encoded = urllib.parse.quote(keyword)
            search_url = f"https://m.search.naver.com/search.naver?where=m&sm=top_hty&fbm=0&ie=utf8&query={query_encoded}"

            logger.info(f"Navigating to Mobile Place Search: {search_url[:80]}...")
            tab = await browser.get(search_url, new_tab=True)
            await tab.sleep(1.5)

            html = await tab.get_content()
            all_places = parse_mobile_place_items(html, start_rank=1)
            target_found = False
            target_rank = None
            target_item = None

            if targets:
                for p in all_places:
                    if p["placeId"] in targets:
                        target_found = True
                        target_rank = p["rank"]
                        target_item = p
                        break

            return {
                "status": "SUCCESS" if (not target_id or target_found) else "NOT_FOUND",
                "engine": "DEEP_NODRIVER",
                "keyword": keyword,
                "targetCode": target_id,
                "targetFound": target_found,
                "targetRank": target_rank,
                "targetItem": target_item,
                "totalExtracted": len(all_places),
                "places": all_places,
                "elapsedSec": time.time() - t0,
                "proxyUsed": current_proxy
            }

        finally:
            close_browser(browser)
