"""
Search Service implementing both Version A (via Main Page UI) and Version B (Direct Search URL).
"""

import json
import os
import time
from typing import Dict, Any, Optional
import nodriver as uc
from lib.logger import get_logger
from lib.ackey import generate_ackey, build_naver_search_url, parse_naver_search_url

logger = get_logger("nshop.search")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def wait_for_search_results(tab: uc.Tab, timeout: float = 15.0) -> bool:
    """
    Waits until the Naver search results page is loaded and main content container appears.
    """
    start_time = time.time()
    logger.info(f"Waiting for search results page to load (timeout: {timeout}s)...")

    while time.time() - start_time < timeout:
        current_url = await tab.evaluate("window.location.href")
        if current_url and "search.naver.com" in current_url:
            # Check if search content or search input on result page is rendered
            has_content = await tab.evaluate("""(() => {
                return !!(
                    document.querySelector('#main_pack') ||
                    document.querySelector('.main_pack') ||
                    document.querySelector('#container') ||
                    document.querySelector('input#nx_query') ||
                    document.querySelector('.api_subject_bx')
                );
            })()""")
            if has_content:
                logger.info(f"Search results page successfully detected in {time.time() - start_time:.2f}s.")
                return True
        await tab.sleep(0.3)

    logger.warning(f"Timeout ({timeout}s) waiting for search results.")
    return False


async def extract_search_page_info(tab: uc.Tab) -> Dict[str, Any]:
    """
    Extracts URL, title, query params, and presence of bot detection from the current page.
    """
    info_json = await tab.evaluate("""(() => {
        return JSON.stringify({
            title: document.title,
            url: window.location.href,
            webdriver: navigator.webdriver,
            hasCaptcha: !!(document.querySelector('#captcha') || document.querySelector('.captcha_box')),
            firstSectionTitle: document.querySelector('.api_title_area .title, .api_subject_bx .fds-comps-header-headline, h2.title')?.innerText || ''
        });
    })()""")
    info = json.loads(info_json)
    params = parse_naver_search_url(info.get("url", ""))
    info["parsedParams"] = params
    return info


async def search_via_main_ui(
    tab: uc.Tab,
    keyword: str = "노트북",
    wait_timeout: float = 15.0,
    screenshot_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    [Version A] UI Navigation Flow:
    1. Access https://www.naver.com
    2. Type keyword into search input (<input id="query">)
    3. Click search button (or submit form)
    4. Wait for navigation to search.naver.com with ackey
    5. Capture info and screenshot
    """
    logger.info("=" * 60)
    logger.info(f"[Version A] Starting UI Search via Main Page: keyword='{keyword}'")
    logger.info("=" * 60)

    # 1. Access Naver main page
    logger.info("Step 1: Navigating to https://www.naver.com ...")
    await tab.get("https://www.naver.com")
    await tab.sleep(2)

    # 2. Find and interact with search input box
    logger.info("Step 2: Locating search box (<input id='query'>) ...")
    query_box = await tab.select("input#query, input[name='query']")
    if not query_box:
        raise RuntimeError("Could not find search input box on Naver main page.")

    await query_box.click()
    logger.info(f"Step 3: Typing keyword '{keyword}' into search box ...")
    await query_box.send_keys(keyword)
    await tab.sleep(0.5)

    # 3. Submit search
    logger.info("Step 4: Submitting search form ...")
    search_btn = await tab.select("button.btn_search, button[type='submit'], .btn_search")
    if search_btn:
        await search_btn.click()
    else:
        logger.info("Search button element not found, submitting form via JS...")
        await tab.evaluate("document.querySelector('#query').form.submit()")

    # 4. Wait for search results navigation
    logger.info("Step 5: Waiting for search results page (search.naver.com) ...")
    loaded = await wait_for_search_results(tab, timeout=wait_timeout)
    if not loaded:
        logger.warning("Search results page might not have fully loaded.")

    await tab.sleep(1.5)

    # 5. Extract results
    info = await extract_search_page_info(tab)
    logger.info(f"Page Title: {info.get('title')}")
    logger.info(f"Result URL: {info.get('url')}")
    logger.info(f"ackey param: {info.get('parsedParams', {}).get('ackey', 'N/A')}")
    logger.info(f"sm param: {info.get('parsedParams', {}).get('sm', 'N/A')} (top_hty expected for main UI search)")

    # 6. Save screenshot
    shot_name = screenshot_name or f"search_ui_{keyword}.png"
    shot_path = os.path.join(OUTPUT_DIR, shot_name)
    await tab.save_screenshot(shot_path)
    logger.info(f"Screenshot saved to: {shot_path}")
    info["screenshotPath"] = shot_path

    return info


async def search_via_direct_url(
    tab: uc.Tab,
    keyword: str = "노트북",
    ackey: Optional[str] = None,
    wait_timeout: float = 15.0,
    screenshot_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    [Version B] Direct Search Flow:
    1. Generate authentic ackey parameter
    2. Construct full search URL (https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query=...&ackey=...)
    3. Directly navigate to the constructed URL
    4. Wait for search results to load
    5. Capture info and screenshot
    """
    logger.info("=" * 60)
    logger.info(f"[Version B] Starting Direct URL Search: keyword='{keyword}'")
    logger.info("=" * 60)

    # 1. Generate ackey and construct URL
    if ackey is None:
        ackey = generate_ackey()
        logger.info(f"Generated synthetic ackey: '{ackey}' (via base36 random algorithm)")
    else:
        logger.info(f"Using specified ackey: '{ackey}'")

    target_url = build_naver_search_url(query=keyword, ackey=ackey)
    logger.info(f"Constructed Direct Search URL: {target_url}")

    # 2. Navigate directly to search URL
    logger.info("Step 1: Navigating directly to search URL ...")
    await tab.get(target_url)

    # 3. Wait for search results
    logger.info("Step 2: Waiting for search results page to render ...")
    loaded = await wait_for_search_results(tab, timeout=wait_timeout)
    if not loaded:
        logger.warning("Search results page might not have fully loaded.")

    await tab.sleep(1.5)

    # 4. Extract results
    info = await extract_search_page_info(tab)
    logger.info(f"Page Title: {info.get('title')}")
    logger.info(f"Result URL: {info.get('url')}")
    logger.info(f"ackey param: {info.get('parsedParams', {}).get('ackey', 'N/A')}")
    logger.info(f"sm param: {info.get('parsedParams', {}).get('sm', 'N/A')}")

    # 5. Save screenshot
    shot_name = screenshot_name or f"search_direct_{keyword}.png"
    shot_path = os.path.join(OUTPUT_DIR, shot_name)
    await tab.save_screenshot(shot_path)
    logger.info(f"Screenshot saved to: {shot_path}")
    info["screenshotPath"] = shot_path

    return info
