"""
Shopping navigation and '네이버 가격비교 더보기' interaction service.
Handles target="_blank" removal for seamless in-tab tracking and wait processing.
"""

import json
import os
import time
from typing import Dict, Any, Optional
import nodriver as uc
from lib.logger import get_logger
from lib.ackey import parse_naver_search_url

logger = get_logger("nshop.shopping")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def find_and_sanitize_more_shopping_button(tab: uc.Tab) -> Dict[str, Any]:
    """
    Finds the '네이버 가격비교 더보기' link/button, logs its properties,
    and removes target='_blank' (setting target='_self') for in-tab navigation.
    """
    js_find_and_modify = """(() => {
        // Find by specific selectors, text, or href patterns
        // 1. Target by known class structures (Price compare link with nl-ts-pid -> 100% clean)
        targetEl = document.querySelector('div.LCESjmoP a, a.OCNh8KJm');

        // 2. Target by text content ('가격비교 더보기' or '네이버 가격비교 더보기')
        if (!targetEl) {
            const allLinks = Array.from(document.querySelectorAll('a'));
            targetEl = allLinks.find(a => a.innerText && a.innerText.includes('가격비교 더보기'));
        }

        // 3. Target by shopping search URL with frm=NVSCDIG or NVSC
        if (!targetEl) {
            const allLinks = Array.from(document.querySelectorAll('a'));
            targetEl = allLinks.find(a => a.href && a.href.includes('search.shopping.naver.com/search/all') && a.href.includes('frm=NVSC'));
        }

        // 4. Target GNB '쇼핑' Tab (Fallback)
        if (!targetEl) {
            const allTabLinks = Array.from(document.querySelectorAll('a[role="tab"], a[class*="tab"]'));
            targetEl = allTabLinks.find(a => a.innerText && a.innerText.trim() === '쇼핑' && a.href && a.href.includes('shopping'));
        }

        // 3. Target by shopping search URL with frm=NVSCDIG or NVSC
        if (!targetEl) {
            const allLinks = Array.from(document.querySelectorAll('a'));
            targetEl = allLinks.find(a => a.href && a.href.includes('search.shopping.naver.com/search/all') && a.href.includes('frm=NVSC'));
        }

        // 4. Target by any shopping search all URL
        if (!targetEl) {
            const allLinks = Array.from(document.querySelectorAll('a'));
            targetEl = allLinks.find(a => a.href && a.href.includes('search.shopping.naver.com/search/all'));
        }

        if (!targetEl) {
            return JSON.stringify({ found: false });
        }

        const originalTarget = targetEl.getAttribute('target');
        const href = targetEl.href;
        const text = targetEl.innerText.trim();
        const className = targetEl.className;

        // Remove target="_blank" and set to "_self"
        targetEl.removeAttribute('target');
        targetEl.setAttribute('target', '_self');
        targetEl.setAttribute('data-target-sanitized', 'true');

        // Scroll element into view smoothly
        targetEl.scrollIntoView({ behavior: 'auto', block: 'center' });

        return JSON.stringify({
            found: true,
            text: text,
            href: href,
            className: className,
            originalTarget: originalTarget,
            newTarget: targetEl.getAttribute('target')
        });
    })()"""

    result_json = await tab.evaluate(js_find_and_modify)
    result = json.loads(result_json)
    return result


async def wait_for_shopping_results(tab: uc.Tab, timeout: float = 15.0) -> bool:
    """
    Waits until the Naver Shopping search results page (search.shopping.naver.com)
    is loaded and products list container appears.
    """
    start_time = time.time()
    logger.info(f"Waiting for Naver Shopping results page to load (timeout: {timeout}s)...")

    while time.time() - start_time < timeout:
        current_url = await tab.evaluate("window.location.href")
        if current_url and "search.shopping.naver.com" in current_url:
            has_shopping_content = await tab.evaluate("""(() => {
                return !!(
                    document.querySelector('div[class*="product_list"]') ||
                    document.querySelector('div[class*="basicList_list"]') ||
                    document.querySelector('div[class*="product_item"]') ||
                    document.querySelector('div[class*="adProduct_item"]') ||
                    document.querySelector('div[class*="productBox"]') ||
                    document.querySelector('ul[class*="list_basis"]') ||
                    document.querySelector('#content') ||
                    document.querySelector('#__next')
                );
            })()""")
            if has_shopping_content:
                logger.info(f"Naver Shopping page loaded successfully in {time.time() - start_time:.2f}s.")
                return True
        await tab.sleep(0.3)

    logger.warning(f"Timeout ({timeout}s) waiting for Naver Shopping page.")
    return False


async def extract_shopping_page_info(tab: uc.Tab, save_json_prefix: str = "shopping") -> Dict[str, Any]:
    """
    Extracts summary information, product list from __NEXT_DATA__.props.pageProps.compositeList.list,
    and saves raw __NEXT_DATA__ and parsed products to JSON files.
    """
    next_data_raw = await tab.evaluate("JSON.stringify(window.__NEXT_DATA__ || {})")
    next_data = json.loads(next_data_raw)

    page_props = next_data.get("props", {}).get("pageProps", {})
    composite_list = page_props.get("compositeList", {})
    raw_list = composite_list.get("list", [])

    # Parse product records
    parsed_products = []
    for idx, wrapper in enumerate(raw_list, 1):
        item = wrapper.get("item", {})
        item_type = wrapper.get("type", "PRODUCT")
        record = {
            "rank": idx,
            "id": item.get("id") or item.get("nvMid"),
            "nvMid": item.get("nvMid"),
            "productTitle": item.get("productTitle") or item.get("productName") or item.get("title"),
            "price": item.get("price") or item.get("lowPrice"),
            "lowPrice": item.get("lowPrice"),
            "mallName": item.get("mallName") or item.get("channelName"),
            "mallId": item.get("mallId"),
            "mallNo": item.get("mallNo"),
            "isAd": bool(item.get("adId") or item.get("ad")),
            "adId": item.get("adId"),
            "category1": item.get("category1Name"),
            "category2": item.get("category2Name"),
            "category3": item.get("category3Name"),
            "category4": item.get("category4Name"),
            "reviewCount": item.get("reviewCountSum") or item.get("reviewCount"),
            "score": item.get("scoreInfo"),
            "crUrl": item.get("crUrl"),
            "imageUrl": item.get("imageUrl"),
            "itemType": item_type,
        }
        parsed_products.append(record)

    # Save full __NEXT_DATA__ to file
    full_json_path = os.path.join(OUTPUT_DIR, f"{save_json_prefix}_next_data_full.json")
    with open(full_json_path, "w", encoding="utf-8") as f:
        json.dump(next_data, f, ensure_ascii=False, indent=2)

    # Save parsed products to file
    products_json_path = os.path.join(OUTPUT_DIR, f"{save_json_prefix}_products_parsed.json")
    with open(products_json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_products, f, ensure_ascii=False, indent=2)

    title = await tab.evaluate("document.title")
    url = await tab.evaluate("window.location.href")

    info = {
        "title": title,
        "url": url,
        "totalSearchResults": composite_list.get("total", 0),
        "totalItemsFound": len(parsed_products),
        "sampleProductTitles": [p["productTitle"] for p in parsed_products[:5]],
        "nextDataPath": "window.__NEXT_DATA__.props.pageProps.compositeList.list",
        "fullNextDataJsonPath": full_json_path,
        "productsJsonPath": products_json_path,
        "parsedParams": parse_naver_search_url(url),
    }
    return info


async def click_more_shopping_button_and_navigate(
    tab: uc.Tab,
    wait_timeout: float = 15.0,
    screenshot_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Finds '네이버 가격비교 더보기', strips target='_blank', clicks it,
    waits for in-tab navigation to search.shopping.naver.com, and extracts results.
    """
    logger.info("=" * 60)
    logger.info("Locating '네이버 가격비교 더보기' button and sanitizing target='_blank'...")
    logger.info("=" * 60)

    # 1. Find button and sanitize target
    btn_info = await find_and_sanitize_more_shopping_button(tab)
    if not btn_info.get("found"):
        raise RuntimeError("Could not find '네이버 가격비교 더보기' button on current page.")

    logger.info(f" - Button Text     : '{btn_info.get('text')}'")
    logger.info(f" - Destination Href: {btn_info.get('href')}")
    logger.info(f" - Original target : '{btn_info.get('originalTarget')}' -> Modified to: '{btn_info.get('newTarget')}' (_blank stripped!)")

    # 2. Click the button
    logger.info("Clicking '네이버 가격비교 더보기' link...")
    click_success = await tab.evaluate("""(() => {
        const btn = document.querySelector('[data-target-sanitized="true"]') ||
                    document.querySelector('div.LCESjmoP a, a.OCNh8KJm');
        if (btn) {
            btn.click();
            return true;
        }
        return false;
    })()""")

    if not click_success:
        logger.warning("JS click returned false, attempting direct navigation fallback...")
        await tab.get(btn_info.get("href"))

    # 3. Wait for shopping results page
    logger.info("Waiting for navigation to Naver Shopping (search.shopping.naver.com)...")
    loaded = await wait_for_shopping_results(tab, timeout=wait_timeout)
    if not loaded:
        logger.warning("Shopping results page may not have fully rendered.")

    await tab.sleep(2)

    # 4. Extract shopping page details
    shopping_info = await extract_shopping_page_info(tab)
    logger.info(f"Shopping Page Title: {shopping_info.get('title')}")
    logger.info(f"Shopping Page URL  : {shopping_info.get('url')}")
    logger.info(f"Products Detected  : {shopping_info.get('totalItemsFound')} items")
    if shopping_info.get("sampleProductTitles"):
        logger.info("Sample Products on Page:")
        for idx, title in enumerate(shopping_info["sampleProductTitles"], 1):
            logger.info(f"  [{idx}] {title}")

    # 5. Save screenshot
    shot_name = screenshot_name or "shopping_price_compare_results.png"
    shot_path = os.path.join(OUTPUT_DIR, shot_name)
    await tab.save_screenshot(shot_path)
    logger.info(f"Shopping page screenshot saved to: {shot_path}")
    shopping_info["screenshotPath"] = shot_path

    return shopping_info
