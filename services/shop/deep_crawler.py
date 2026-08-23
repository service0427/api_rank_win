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

logger = get_logger("rank.shop.deep")


async def crawl_shop_deep_nodriver(
    keyword: str,
    target_id: Optional[str] = None,
    max_pages: int = 13,
    headless: bool = False,
    offscreen: bool = True,
    block_media: bool = False,
    proxy_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deep Shopping Rank Crawler (Pure Windows Desktop Human Flow):
    1. Directly visits https://search.naver.com?where=nexearch&query={keyword} (Search Gateway).
    2. Clicks '네이버 가격비교 더보기' link to obtain valid nl-ts-pid session token.
    3. Extracts Page 1 products (1~44) from __NEXT_DATA__ (0% login rate).
    4. Progressively paginates Page 2 ~ max_pages (up to 500 items) via pagination buttons.
    5. Returns immediately once target_id is discovered.
    """
    t0 = time.time()
    targets = {str(x).strip() for x in target_id.split(",")} if target_id else set()
    current_proxy = proxy_url or proxy_mgr.get_next_proxy()

    sem = get_browser_semaphore()
    async with sem:
        browser = await start_stealth_browser(
            headless=headless,
            is_mobile=False,
            block_media=block_media,
            offscreen=offscreen,
            proxy_url=current_proxy
        )

        try:
            tab = await browser.get("about:blank")
            await tab.sleep(0.3)

            all_products: List[Dict[str, Any]] = []
            seen_ids = set()
            target_found = False
            target_rank = None
            target_prod = None

            # Step 1: Direct Unified Search Gateway
            q_enc = urllib.parse.quote(keyword)
            search_url = f"https://search.naver.com/search.naver?where=nexearch&query={q_enc}"
            logger.info(f"Step 1: Navigating to Unified Search Gateway: {search_url} ...")
            await tab.get(search_url)
            await tab.sleep(2.0)

            # Step 3: Click '네이버 가격비교 더보기' button
            logger.info("Step 3: Locating and clicking '네이버 가격비교 더보기' link...")
            btn_clicked = await tab.evaluate("""
                (() => {
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    const moreBtn = allLinks.find(a => 
                        (a.textContent.includes('가격비교') && a.textContent.includes('더보기')) || 
                        (a.href.includes('search.shopping.naver.com') && a.textContent.includes('더보기')) ||
                        (a.href.includes('search.shopping.naver.com') && a.href.includes('frm=NVSC'))
                    );
                    if (moreBtn) {
                        moreBtn.removeAttribute('target');
                        moreBtn.setAttribute('target', '_self');
                        moreBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        moreBtn.click();
                        return true;
                    }
                    return false;
                })()
            """)

            if not btn_clicked:
                logger.warning("More button not found directly, attempting search.shopping fallback...")
                q_enc = urllib.parse.quote(keyword)
                await tab.get(f"https://search.shopping.naver.com/search/all?query={q_enc}")

            await tab.sleep(3.0)

            # Check active tab
            tabs = browser.tabs
            active_tab = tabs[-1] if len(tabs) > 1 else tab

            curr_url = await active_tab.evaluate("window.location.href")
            curr_title = await active_tab.evaluate("document.title")
            logger.info(f"Step 4: Shopping Specialist Mall Loaded: '{curr_title}' ({curr_url[:80]}...)")

            # Step 5: Extract Page 1 from __NEXT_DATA__
            next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
            if next_data_str:
                d = json.loads(next_data_str)
                pp = d.get('props', {}).get('pageProps', {})
                comp_list = pp.get('compositeList', {}).get('list', []) or pp.get('compositeProducts', {}).get('list', [])
                logger.info(f"Page 1 Extracted: {len(comp_list)} items from __NEXT_DATA__.")

                for wrapper in comp_list:
                    it = wrapper.get('item', wrapper)
                    if bool(it.get('ad') or it.get('adId') or 'AD' in str(it.get('cardType', ''))):
                        continue
                    iid = str(it.get('id') or it.get('nvMid') or '')
                    title = it.get('productTitle') or it.get('productName') or it.get('title') or ''
                    mall = it.get('mallName') or it.get('channelName') or ''
                    price = int(it.get('lowPrice') or it.get('price') or 0)
                    ch_prod_id = str(it.get('channelProductId') or '')
                    orig_prod_id = str(it.get('originalMallProductId') or '')

                    key = iid or title
                    if not key or key in seen_ids:
                        continue
                    seen_ids.add(key)

                    prod_record = {
                        "rank": len(all_products) + 1,
                        "page": 1,
                        "id": iid,
                        "nvMid": iid,
                        "channelProductId": ch_prod_id,
                        "originalMallProductId": orig_prod_id,
                        "productTitle": title,
                        "mallName": mall,
                        "price": price,
                        "isAd": False,
                        "source": "PAGE_1_NEXT_DATA"
                    }
                    all_products.append(prod_record)

                    # Target match check
                    if targets and not target_found:
                        if any(t in [iid, ch_prod_id, orig_prod_id] for t in targets):
                            target_found = True
                            target_rank = prod_record["rank"]
                            target_prod = prod_record
                            logger.info(f"★ Target Found on Page 1 at Rank #{target_rank}!")
                            break

            # Step 6: Multi-Page Pagination (Page 2 to max_pages) if target not yet found
            if not target_found and max_pages > 1:
                for target_page in range(2, max_pages + 1):
                    if len(all_products) >= 500:
                        logger.info(f"[500 Threshold Reached] Total items: {len(all_products)}. Stopping pagination.")
                        break

                    logger.info(f"Step 6.{target_page}: Navigating to Page {target_page}...")

                    # Scroll down to bottom to mount pagination buttons
                    for _ in range(4):
                        await active_tab.evaluate("window.scrollBy({ top: 1800, behavior: 'smooth' });")
                        await active_tab.sleep(0.4)

                    # Click target page button
                    p_clicked = await active_tab.evaluate(f"""
                        (() => {{
                            const targetP = '{target_page}';
                            const allLinks = Array.from(document.querySelectorAll('a'));
                            const pBtn = allLinks.find(a => 
                                a.textContent.trim() === targetP || 
                                a.getAttribute('data-shp-contents-id') === targetP ||
                                (a.className.includes('pagination') && a.textContent.trim() === targetP)
                            );
                            if (pBtn) {{
                                pBtn.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                pBtn.click();
                                return true;
                            }}
                            const nextBtn = document.querySelector('a.pagination_next__kh_cw, a[class*="pagination_next"]');
                            if (nextBtn) {{
                                nextBtn.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                nextBtn.click();
                                return true;
                            }}
                            return false;
                        }})()
                    """)

                    if not p_clicked:
                        logger.info(f"No further page buttons found at Page {target_page}. Search ended.")
                        break

                    await active_tab.sleep(2.5)

                    # Extract Page DOM elements
                    dom_str = await active_tab.evaluate("""
                        JSON.stringify((() => {
                            const items = document.querySelectorAll('div[class*="product_item"], div[class*="basicList_item"], div[class*="product_list_item"], div[id^="_sr_lst_"]');
                            const list = [];
                            for (const node of items) {
                                const classAttr = node.className || '';
                                if (classAttr.includes('adProduct') || classAttr.includes('ad_') || node.querySelector('[class*="ad_badge"], [class*="adTag"]') !== null) continue;

                                const idAttr = node.id || '';
                                let nvMid = idAttr.startsWith('_sr_lst_') ? idAttr.replace('_sr_lst_', '').trim() : '';

                                const titleEl = node.querySelector('a[class*="product_title"], a[class*="product_link"], a[class*="basicList_link"], a[title]');
                                const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
                                if (!title) continue;

                                const priceEl = node.querySelector('[class*="price_num"], [class*="price"] strong, [class*="price"]');
                                const price = priceEl ? parseInt(priceEl.textContent.replace(/[^0-9]/g, ''), 10) || 0 : 0;

                                const mallEl = node.querySelector('a[class*="product_mall"], a[class*="mall"], [class*="mall_name"]');
                                const mall = mallEl ? mallEl.textContent.trim() : '';

                                list.push({ nvMid, productTitle: title, mallName: mall, price });
                            }
                            return list;
                        })())
                    """)

                    if dom_str:
                        dom_items = json.loads(dom_str)
                        new_count = 0
                        for it in dom_items:
                            key = it['nvMid'] or it['productTitle']
                            if key not in seen_ids:
                                seen_ids.add(key)
                                it['rank'] = len(all_products) + 1
                                it['page'] = target_page
                                it['isAd'] = False
                                it['source'] = f"PAGE_{target_page}_DOM"
                                all_products.append(it)
                                new_count += 1

                                if targets and not target_found:
                                    p_mid = str(it.get('nvMid') or '')
                                    if p_mid in targets:
                                        target_found = True
                                        target_rank = it["rank"]
                                        target_prod = it
                                        logger.info(f"★ Target Found on Page {target_page} at Rank #{target_rank}!")
                                        break

                        logger.info(f"Page {target_page}: {new_count} new products parsed (Accumulated: {len(all_products)}).")

                    if target_found:
                        break

            elapsed = time.time() - t0
            logger.info(f"Deep Search Complete: {len(all_products)} items in {elapsed:.2f}s (Target Found: {target_found}, Rank: {target_rank})")

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
