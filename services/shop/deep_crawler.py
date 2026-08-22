import json
import os
import sys
import time
import urllib.parse
from typing import Dict, Any, Optional, List
import nodriver as uc
from core.logger import get_logger
from core.browser import start_stealth_browser, close_browser, get_browser_semaphore
from core.ackey import generate_ackey
from config.settings import OUTPUT_DIR
from config.proxy_manager import proxy_mgr
from services.shop.parser import extract_products_from_mobile_html

logger = get_logger("rank.shop.deep")

JS_DYNAMIC_DOM_EXTRACTOR = """
(() => {
    const organicList = [];
    const seenMids = new Set();
    let currentRank = 1;

    // 1. Target all items matching id starting with '_sr_lst_' or matching CSS module pattern
    const itemNodes = document.querySelectorAll('div[id^="_sr_lst_"], div[class*="product_list_item"], div[class*="adProduct_list_item"], div[class*="product_item"]');
    
    for (const node of itemNodes) {
        const idAttr = node.id || '';
        const classAttr = node.className || '';
        
        // 2. Strict Ad Filtering
        const isAd = classAttr.includes('adProduct') || 
                     classAttr.includes('ad_') || 
                     node.querySelector('[class*="ad_badge"], [class*="adTag"], button[class*="ad"]') !== null;
        if (isAd) continue;
        
        // 3. Extract nvMid directly from id="_sr_lst_{nvMid}" or data attributes
        let nvMid = '';
        if (idAttr.startsWith('_sr_lst_')) {
            nvMid = idAttr.replace('_sr_lst_', '').trim();
        }
        
        // 4. Extract Title
        const titleEl = node.querySelector('a[class*="product_link"], a[class*="product_title"], a[class*="title"], a[title]');
        const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
        if (!title) continue;
        
        // Extract Price
        const priceEl = node.querySelector('[class*="price_num"], [class*="price"]');
        let priceStr = priceEl ? priceEl.textContent.replace(/[^0-9]/g, '') : '0';
        let price = parseInt(priceStr, 10) || 0;
        
        // Extract Mall Name
        const mallEl = node.querySelector('a[class*="product_mall"], a[class*="mall"], [class*="mall_name"]');
        const mallName = mallEl ? mallEl.textContent.trim() : '';
        
        // Extract Mall Count (for Catalog items)
        const mallCntEl = node.querySelector('[class*="mall_count"] em, [class*="mall_count"]');
        const mallCount = mallCntEl ? parseInt(mallCntEl.textContent.replace(/[^0-9]/g, ''), 10) || 0 : 1;
        
        // Extract Review & Score
        const revEl = node.querySelector('[class*="product_review"] em, [class*="review"] em, [class*="review"]');
        const reviewCount = revEl ? parseInt(revEl.textContent.replace(/[^0-9]/g, ''), 10) || 0 : 0;
        
        const scoreEl = node.querySelector('[class*="grade"], [class*="score"]');
        const scoreMatch = scoreEl ? scoreEl.textContent.match(/([0-9]+\\.?[0-9]*)/) : null;
        const score = scoreMatch ? parseFloat(scoreMatch[1]) : 0.0;
        
        const key = nvMid || title;
        if (seenMids.has(key)) continue;
        seenMids.add(key);
        
        organicList.push({
            rank: currentRank,
            productType: mallCount > 1 ? "CATALOG" : "STORE",
            productTypeName: mallCount > 1 ? "가격비교" : "단일상품",
            id: nvMid,
            nvMid: nvMid,
            channelProductId: "",
            originalMallProductId: "",
            productTitle: title,
            mallName: mallName || (mallCount > 1 ? `가격비교 (쇼핑몰 ${mallCount}개)` : "스마트스토어"),
            mallCount: mallCount,
            price: price,
            reviewCount: reviewCount,
            score: score,
            isAd: false,
            elementId: idAttr
        });
        currentRank++;
    }
    
    return {
        totalNodes: itemNodes.length,
        organicCount: organicList.length,
        products: organicList
    };
})()
"""


async def crawl_shop_deep_nodriver(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 13,
    headless: bool = True,
    block_media: bool = True,
    proxy_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deep Shopping Rank Crawler:
    1. Loads Page 1 HTML and parses INITIAL_STATE JSON.
    2. If target is deeper (> 70 or not on page 1), performs smooth scrolls and
       dynamically extracts up to 500 organic items using div[id^="_sr_lst_"].
    3. Stops early as soon as target_id is discovered.
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
            ackey = generate_ackey()
            query_encoded = urllib.parse.quote(keyword)
            search_url = f"https://m.search.naver.com/search.naver?where=m_shopping&sm=top_hty&fbm=0&ie=utf8&query={query_encoded}&ackey={ackey}"

            logger.info(f"Navigating to Mobile Shopping Search: {search_url[:80]}...")
            tab = await browser.get(search_url, new_tab=True)
            await tab.sleep(2.0)

            all_products = []
            seen_keys = set()
            target_found = False
            target_rank = None
            target_prod = None

            # 1. Initial Page 1 Extraction via INITIAL_STATE JSON
            html = await tab.get_content()
            if html:
                p1_prods = extract_products_from_mobile_html(html, start_rank=1)
                for p in p1_prods:
                    p_key = p.get("nvMid") or p.get("id") or p.get("productTitle")
                    if p_key and p_key not in seen_keys:
                        seen_keys.add(p_key)
                        all_products.append(p)

                logger.info(f"Page 1 State Extracted: {len(all_products)} pure organic products (Rank 1 ~ {len(all_products)}).")

                if targets:
                    for p in all_products:
                        p_id = str(p.get("id") or p.get("nvMid") or "")
                        p_ch = str(p.get("channelProductId") or "")
                        p_orig = str(p.get("originalMallProductId") or "")
                        if any(t in [p_id, p_ch, p_orig] for t in targets):
                            target_found = True
                            target_rank = p["rank"]
                            target_prod = p
                            logger.info(f"★ Target Found on Page 1 at Rank #{target_rank}!")
                            break

            # 2. If target not found or full scan requested, perform deep scrolling up to 500 items
            if not target_found:
                logger.info(f"Target not in Page 1. Starting Deep Scroll Expansion up to 500 items...")
                max_scroll_cycles = min(max_pages, 15)

                for cycle in range(1, max_scroll_cycles + 1):
                    # Scroll down
                    await tab.evaluate("""
                        window.scrollBy({
                            top: 2500,
                            behavior: 'smooth'
                        });
                    """)
                    await tab.sleep(1.5)

                    # Extract DOM elements
                    dom_data_str = await tab.evaluate(f"JSON.stringify({JS_DYNAMIC_DOM_EXTRACTOR})")
                    if dom_data_str and isinstance(dom_data_str, str):
                        try:
                            dom_res = json.loads(dom_data_str)
                            dom_prods = dom_res.get("products", [])

                            # Merge new items
                            for p in dom_prods:
                                p_key = p.get("nvMid") or p.get("id") or p.get("productTitle")
                                if p_key and p_key not in seen_keys:
                                    seen_keys.add(p_key)
                                    p["rank"] = len(all_products) + 1
                                    all_products.append(p)

                                    if targets and not target_found:
                                        p_id = str(p.get("id") or p.get("nvMid") or "")
                                        p_ch = str(p.get("channelProductId") or "")
                                        p_orig = str(p.get("originalMallProductId") or "")
                                        if any(t in [p_id, p_ch, p_orig] for t in targets):
                                            target_found = True
                                            target_rank = p["rank"]
                                            target_prod = p
                                            logger.info(f"★ Target Found via Deep DOM Scroll at Rank #{target_rank} (Cycle {cycle})!")
                                            break

                            logger.debug(f"Scroll Cycle {cycle}/{max_scroll_cycles}: Total Products Accumulated: {len(all_products)}")

                        except Exception as e:
                            logger.error(f"Error parsing DOM products on cycle {cycle}: {e}")

                    if target_found:
                        break

            elapsed = time.time() - t0
            logger.info(f"Deep Search Completed: Total {len(all_products)} products extracted in {elapsed:.2f}s (Target Found: {target_found}, Rank: {target_rank})")

            return {
                "status": "SUCCESS" if (not target_id or target_found) else "NOT_FOUND",
                "engine": "DEEP_NODRIVER",
                "keyword": keyword,
                "targetCode": target_id,
                "targetFound": target_found,
                "targetRank": target_rank,
                "targetProduct": target_prod,
                "totalExtracted": len(all_products),
                "products": all_products,
                "elapsedSec": elapsed,
                "proxyUsed": current_proxy
            }

        finally:
            close_browser(browser)
