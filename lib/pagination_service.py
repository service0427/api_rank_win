"""
Multi-Page Pagination and 418 Anti-Bot Verification Service for Naver Shopping.
Features:
1. Pure Non-Ad (Organic) product extraction (100% ad filtration).
2. Graceful stop when '다음' / next page button does not exist (search results end).
3. Immediate abort on HTTP 418 block detection.
4. Progressive human-like scroll per page.
5. Real-time API response interception (shoppingResult.products).
"""

import json
import os
import time
from typing import Dict, Any, List, Optional, Tuple
import nodriver as uc
from nodriver import cdp
from lib.logger import get_logger

logger = get_logger("nshop.pagination")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


class PaginationMonitor:
    """
    Monitors CDP network events, intercepts HTTP response bodies for api/search/all,
    and detects HTTP 418 blocks or HTTP 200 successes in real-time.
    """

    def __init__(self, tab: uc.Tab):
        self.tab = tab
        self.intercepted_responses: List[Dict[str, Any]] = []
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.captured_api_bodies: Dict[str, Any] = {}
        self._enabled = False

    async def start_monitoring(self):
        """Attaches network response handlers and enables CDP Network domain."""
        async def on_response(event: cdp.network.ResponseReceived):
            resp = event.response
            if "api/search/all" in resp.url or resp.status == 418 or "shopping.naver.com/api" in resp.url or "volts" in resp.url:
                record = {
                    "requestId": str(event.request_id),
                    "url": resp.url,
                    "status": resp.status,
                    "statusText": resp.status_text,
                    "mimeType": resp.mime_type,
                    "timestamp": time.time(),
                }
                self.intercepted_responses.append(record)
                if "api/search/all" in resp.url:
                    self.pending_requests[str(event.request_id)] = record

                if resp.status == 418:
                    logger.error(f"[HTTP 418 DETECTED] {resp.url}")
                elif resp.status == 200 and "api/search/all" in resp.url:
                    logger.info(f"[HTTP 200 OK] {resp.url[:120]}")

        async def on_loading_finished(event: cdp.network.LoadingFinished):
            req_id_str = str(event.request_id)
            if req_id_str in self.pending_requests:
                try:
                    body_tuple = await self.tab.send(cdp.network.get_response_body(request_id=event.request_id))
                    body_text = body_tuple[0]
                    self.captured_api_bodies[req_id_str] = {
                        "url": self.pending_requests[req_id_str]["url"],
                        "json": json.loads(body_text),
                        "raw": body_text
                    }
                    logger.debug(f"Captured API response JSON ({len(body_text)} chars) for {self.pending_requests[req_id_str]['url'][:60]}...")
                except Exception as e:
                    logger.debug(f"Could not retrieve response body for {req_id_str}: {e}")

        self.tab.add_handler(cdp.network.ResponseReceived, on_response)
        self.tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)
        await self.tab.send(cdp.network.enable())
        self._enabled = True
        logger.info("CDP Network monitoring active for pagination responses.")

    def clear(self):
        self.intercepted_responses.clear()
        self.pending_requests.clear()
        self.captured_api_bodies.clear()


async def perform_progressive_scroll(tab: uc.Tab, step_px: int = 600, delay_sec: float = 0.22) -> Dict[str, Any]:
    """
    Progressively scrolls down the page to trigger lazy-loading
    and dynamic product card expansion, mounting the pagination bar naturally.
    """
    max_steps = 35
    for step_num in range(1, max_steps + 1):
        scroll_raw = await tab.evaluate("""(() => {
            const products = document.querySelectorAll(
                'div[class*="product_item"], div[class*="basicList_item"], div[class*="adProduct_item"]'
            );
            const pagin = document.querySelector('div[class*="pagination_pagination"], a.pagination_next__kh_cw');
            return JSON.stringify({
                scrollY: Math.round(window.scrollY),
                scrollHeight: Math.round(document.body.scrollHeight),
                innerHeight: window.innerHeight,
                productsCount: products.length,
                hasPaginDOM: !!pagin
            });
        })()""")

        s_data = json.loads(scroll_raw)
        await tab.evaluate(f"window.scrollBy({{ top: {step_px}, behavior: 'smooth' }})")
        await tab.sleep(delay_sec)

        if s_data["hasPaginDOM"] and s_data["scrollY"] + s_data["innerHeight"] >= s_data["scrollHeight"] - 300:
            break

    await tab.sleep(0.8)
    final_count = await tab.evaluate("document.querySelectorAll('div[class*=\"product_item\"]').length")
    return {"totalProducts": final_count}


async def verify_and_highlight_page_button(tab: uc.Tab, target_page: int) -> Dict[str, Any]:
    """
    Locates the target page button (page N button or '다음' button).
    If no next button exists (e.g. search results exhausted), returns verified: False.
    """
    js_find_btn = f"""(() => {{
        const targetPage = {target_page};
        let targetBtn = null;

        // 1. Try explicit page number button (e.g. 2, 3, 4, 5)
        targetBtn = document.querySelector(`a[data-shp-contents-id="${{targetPage}}"], a[data-shp-contents-txt="${{targetPage}}"]`);

        // 2. Try match by exact text
        if (!targetBtn) {{
            const allLinks = Array.from(document.querySelectorAll('a[class*="pagination"], div[class*="pagination"] a'));
            targetBtn = allLinks.find(a => a.innerText && a.innerText.trim() === String(targetPage));
        }}

        // 3. Fallback to '다음' button
        if (!targetBtn) {{
            targetBtn = document.querySelector('a.pagination_next__kh_cw, a[class*="pagination_next"]');
            if (!targetBtn) {{
                const allLinks = Array.from(document.querySelectorAll('a[class*="pagination"], div[class*="pagination"] a'));
                targetBtn = allLinks.find(a => a.innerText && a.innerText.trim() === '다음');
            }}
        }}

        if (!targetBtn) {{
            return JSON.stringify({{ verified: false, reason: `No next button ('다음' or Page ${{targetPage}}) found in DOM` }});
        }}

        targetBtn.scrollIntoView({{ behavior: 'smooth', block: 'center', inline: 'center' }});

        // Apply bright highlight
        targetBtn.style.outline = '4px solid #ff0000';
        targetBtn.style.backgroundColor = '#ffff00';
        targetBtn.style.color = '#000000';
        targetBtn.style.boxShadow = '0 0 25px rgba(255, 0, 0, 1)';
        targetBtn.style.borderRadius = '4px';
        targetBtn.style.fontWeight = 'bold';
        targetBtn.setAttribute('data-target-active-btn', 'true');

        const rect = targetBtn.getBoundingClientRect();
        return JSON.stringify({{
            verified: true,
            text: targetBtn.innerText.trim(),
            className: targetBtn.className,
            targetPage: targetPage,
            position: {{
                top: Math.round(rect.top),
                left: Math.round(rect.left),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            }}
        }});
    }})()"""

    res_raw = await tab.evaluate(js_find_btn)
    return json.loads(res_raw) if isinstance(res_raw, str) else dict(res_raw)


def parse_page_api_organic_only(api_json: Dict[str, Any], page_num: int, start_overall_rank: int) -> List[Dict[str, Any]]:
    """
    Parses ONLY pure non-ad (organic) products from shoppingResult.products.
    Filters out and completely ignores searchAdResult.products.
    """
    shopping_result = api_json.get("shoppingResult", {})
    raw_organic = shopping_result.get("products", [])

    parsed_organic = []
    current_overall = start_overall_rank
    for idx, p in enumerate(raw_organic, 1):
        parsed_organic.append({
            "rank": current_overall,
            "overallRank": current_overall,
            "page": page_num,
            "pageRank": idx,
            "isAd": False,
            "id": p.get("id"),
            "nvMid": p.get("nvMid"),
            "productTitle": p.get("productTitle") or p.get("productName"),
            "price": p.get("price") or p.get("lowPrice"),
            "lowPrice": p.get("lowPrice"),
            "mallName": p.get("mallName") or "N/A (카탈로그/가격비교)",
            "mallId": p.get("mallId"),
            "reviewCount": p.get("reviewCountSum") or p.get("reviewCount"),
            "score": p.get("scoreInfo"),
            "category1": p.get("category1Name"),
            "category2": p.get("category2Name"),
            "category3": p.get("category3Name"),
            "crUrl": p.get("crUrl"),
            "imageUrl": p.get("imageUrl"),
        })
        current_overall += 1

    return parsed_organic


def parse_page1_organic_only(page_props: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parses ONLY pure non-ad (organic) products from Page 1 compositeList.list.
    Excludes any items having adId / ad flag.
    """
    composite_list = page_props.get("compositeList", {})
    raw_list = composite_list.get("list", [])

    pure_organic = []
    org_rank = 1

    for wrapper in raw_list:
        item = wrapper.get("item", {})
        ad_id = item.get("adId")

        # AD FILTER: If adId exists, skip completely
        if ad_id and str(ad_id).strip():
            continue

        record = {
            "rank": org_rank,
            "overallRank": org_rank,
            "page": 1,
            "pageRank": org_rank,
            "isAd": False,
            "id": item.get("id") or item.get("nvMid"),
            "nvMid": item.get("nvMid"),
            "productTitle": item.get("productTitle") or item.get("productName") or item.get("title"),
            "price": item.get("price") or item.get("lowPrice"),
            "lowPrice": item.get("lowPrice"),
            "mallName": item.get("mallName") or item.get("channelName") or "N/A (카탈로그/가격비교)",
            "mallId": item.get("mallId"),
            "mallNo": item.get("mallNo"),
            "reviewCount": item.get("reviewCountSum") or item.get("reviewCount"),
            "score": item.get("scoreInfo"),
            "category1": item.get("category1Name"),
            "category2": item.get("category2Name"),
            "category3": item.get("category3Name"),
            "crUrl": item.get("crUrl"),
            "imageUrl": item.get("imageUrl"),
        }
        pure_organic.append(record)
        org_rank += 1

    return pure_organic


async def crawl_multi_pages(
    tab: uc.Tab,
    monitor: PaginationMonitor,
    keyword: str,
    target_code: Optional[str] = None,
    max_page: int = 13,
    wait_before_click_sec: float = 1.0,
    screenshot_prefix: str = "shopping"
) -> Dict[str, Any]:
    """
    Crawls from Page 1 up to max_page (default 13 = ~520 items).
    If target_code is given, immediately halts when matched.
    """
    targets = {str(x).strip() for x in target_code.split(",")} if target_code else set()
    all_organic_products: List[Dict[str, Any]] = []
    reached_end_of_results = False
    current_page = 1
    stopped_due_to_418 = False
    current_page_reached = 1

    target_found = False
    target_rank = None
    target_product = None

    logger.info("=" * 80)
    logger.info(f"STARTING MULTI-PAGE PIPELINE (Target Max Page: {max_page}) | Keyword: '{keyword}' | Targets: {targets or 'ALL'}")
    logger.info("=" * 80)

    # -------------------------------------------------------------
    # 1. Parse Page 1 Pure Organic Data
    # -------------------------------------------------------------
    logger.info("\n>>> [PAGE 1] Extracting Pure Organic Products from Initial __NEXT_DATA__ (Ads Excluded)...")
    next_data_raw = await tab.evaluate("JSON.stringify(window.__NEXT_DATA__ || {})")
    next_data = json.loads(next_data_raw)
    page_props = next_data.get("props", {}).get("pageProps", {})

    p1_organic = parse_page1_organic_only(page_props)
    all_organic_products.extend(p1_organic)

    logger.info(f"Page 1 Pure Organic Extracted: {len(p1_organic)} products (Ads 100% Filtered Out).")
    if p1_organic:
        logger.info(f" - [P1 Organic #1] {p1_organic[0].get('productTitle')} ({p1_organic[0].get('mallName')})")

    # Target match check on Page 1
    if targets:
        for p in p1_organic:
            p_mid = str(p.get("nvMid") or p.get("id") or "")
            p_mall_id = str(p.get("mallId") or "")
            p_mall_no = str(p.get("mallNo") or "")
            if any(t in [p_mid, p_mall_id, p_mall_no] for t in targets):
                target_found = True
                target_rank = p.get("rank")
                target_product = p
                logger.info(f"★ TARGET FOUND ON PAGE 1 AT RANK #{target_rank}!")
                break

    # -------------------------------------------------------------
    # 2. Loop for Page 2 to max_page (if target not yet found)
    # -------------------------------------------------------------
    if not target_found:
        for target_page in range(2, max_page + 1):
            if not targets and len(all_organic_products) >= 500:
                logger.info(f"[500 THRESHOLD REACHED] Cumulative items: {len(all_organic_products)}. Stopping further pagination cleanly.")
                break

            logger.info("\n" + "-" * 75)
            logger.info(f">>> [PAGE {target_page}] Preparing Navigation to Page {target_page}...")
            logger.info("-" * 75)

            # 2.1 Progressive scroll to expand products
            logger.info(f"Step 1: Progressively scrolling down Page {target_page - 1}...")
            await perform_progressive_scroll(tab)

            # 2.2 Verify and highlight page button
            logger.info(f"Step 2: Locating and highlighting Page {target_page} button...")
            btn_info = await verify_and_highlight_page_button(tab, target_page=target_page)

            # CHECK: If next button does not exist (Search results exhausted) -> STOP CLEANLY
            if not btn_info.get("verified"):
                logger.info("=" * 75)
                logger.info(f" [END OF RESULTS] No next page button ('다음' or Page {target_page}) found.")
                logger.info(f" Search results ended at Page {current_page}. Finishing crawl cleanly without error.")
                logger.info("=" * 75)
                reached_end_of_results = True
                break

            logger.info(f" - Button Text: '{btn_info.get('text')}' | Class: '{btn_info.get('className')}'")

            # 2.3 Visual wait
            if wait_before_click_sec > 0:
                logger.info(f"Step 3: Waiting {wait_before_click_sec}s with Page {target_page} button highlighted...")
                await tab.sleep(wait_before_click_sec)

            # 2.4 Click target page button
            monitor.clear()
            logger.info(f"Step 4: Clicking Page {target_page} button...")
            await tab.evaluate("""(() => {
                const btn = document.querySelector('[data-target-active-btn="true"]') ||
                            document.querySelector('a.pagination_next__kh_cw, a[class*="pagination_next"]');
                if (btn) {
                    btn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    btn.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    btn.focus();
                    btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                    btn.click();
                    return true;
                }
                return false;
            })()""")

            # 2.5 Monitor network response
            logger.info(f"Step 5: Monitoring API response...")
            has_418 = False
            for _ in range(25):
                for resp in monitor.intercepted_responses:
                    if resp.get("status") == 418:
                        has_418 = True
                        break
                if has_418:
                    break

                matched_200 = False
                for resp in monitor.intercepted_responses:
                    if resp.get("status") == 200 and f"pagingIndex={target_page}" in resp.get("url", ""):
                        matched_200 = True
                        break
                if matched_200:
                    break
                await tab.sleep(0.3)

            # 2.6 CHECK 418 ERROR -> IMMEDIATE ABORT!
            if has_418:
                logger.critical("=" * 80)
                logger.critical(f" [418 DETECTED] Naver returned HTTP 418 on Page {target_page}!")
                logger.critical(" IMMEDIATELY ABORTING FURTHER PAGINATION AS REQUESTED.")
                logger.critical("=" * 80)
                stopped_due_to_418 = True
                break

            # Settle React DOM
            await tab.sleep(1.5)

            # 2.7 Parse Pure Organic Products from Intercepted shoppingResult.products
            page_organic = []
            if monitor.captured_api_bodies:
                for req_id, body_info in monitor.captured_api_bodies.items():
                    if f"pagingIndex={target_page}" in body_info.get("url", ""):
                        api_json = body_info.get("json", {})
                        start_rank = len(all_organic_products) + 1
                        page_organic = parse_page_api_organic_only(
                            api_json,
                            page_num=target_page,
                            start_overall_rank=start_rank
                        )
                        break

            if page_organic:
                all_organic_products.extend(page_organic)
                current_page = target_page
                logger.info(f"Page {target_page} Scraped Successfully: {len(page_organic)} pure organic products (Ads Filtered).")
                logger.info(f" - [P{target_page} Organic #1 (Pure Rank #{page_organic[0]['rank']})] {page_organic[0].get('productTitle')} ({page_organic[0].get('mallName')})")

                # Target match check on deeper page
                if targets:
                    for p in page_organic:
                        p_mid = str(p.get("nvMid") or p.get("id") or "")
                        p_mall_id = str(p.get("mallId") or "")
                        p_mall_no = str(p.get("mallNo") or "")
                        if any(t in [p_mid, p_mall_id, p_mall_no] for t in targets):
                            target_found = True
                            target_rank = p.get("rank")
                            target_product = p
                            logger.info(f"\n★ TARGET FOUND ON PAGE {target_page} AT RANK #{target_rank}!")
                            break
                    if target_found:
                        break
            else:
                logger.warning(f"Could not parse API response for Page {target_page}. Finishing crawl at Page {current_page}.")
                break

    # Save page screenshot
    final_shot = os.path.join(OUTPUT_DIR, f"{screenshot_prefix}_final_page_{current_page}.png")
    try:
        await tab.save_screenshot(final_shot)
    except Exception:
        pass

    return {
        "targetFound": target_found,
        "targetRank": target_rank,
        "targetProduct": target_product,
        "totalPagesReached": current_page,
        "stoppedDueTo418": stopped_due_to_418,
        "reachedEndOfResults": reached_end_of_results,
        "totalPureProducts": len(all_organic_products),
        "allOrganicProducts": all_organic_products,
        "finalScreenshot": final_shot
    }
