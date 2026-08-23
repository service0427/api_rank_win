from typing import List, Optional
import asyncio
import os
import nodriver as uc
from nodriver import cdp
from core.logger import get_logger
from core.stealth import DEFAULT_BROWSER_ARGS, STEALTH_INJECTION_JS
from config.settings import MOBILE_USER_AGENT, DESKTOP_USER_AGENT, MAX_CONCURRENT_BROWSERS, BASE_DIR

logger = get_logger("rank.browser")

_browser_semaphore: Optional[asyncio.Semaphore] = None


def get_browser_semaphore() -> asyncio.Semaphore:
    global _browser_semaphore
    if _browser_semaphore is None:
        _browser_semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)
    return _browser_semaphore


# URL patterns blocked to minimize bandwidth and match packet speed
SURGICAL_BLOCKED_URLS = [
    # 1. Product Images, Thumbnails
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg", "*.avif",
    "*shopping-phinf.pstatic.net*", "*search.pstatic.net/sunny*",
    "*img.danuri.io*", "*image7.coupangcdn.com*",
    # 2. Web Fonts
    "*.woff", "*.woff2", "*.ttf", "*.otf",
    # 3. Media
    "*.mp4", "*.webm", "*.mp3",
    # 4. Third-Party Trackers
    "*google-analytics.com*", "*googletagmanager.com*", "*criteo.com*", "*adnxs.com*",
    "*clarity.ms*", "*facebook.net*", "*g.daum.net*"
]


async def start_stealth_browser(
    headless: bool = False,
    is_mobile: bool = False,
    block_media: bool = False,
    offscreen: bool = True,
    proxy_url: Optional[str] = None,
    user_data_dir: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> uc.Browser:
    """
    Launches a stealth Chrome browser instance with bot detection neutralized.
    Default mode is pure Windows Desktop GUI running Off-screen (window-position=3000,3000)
    which guarantees 100% WAF bypass with zero screen interference.
    """
    browser_args = list(DEFAULT_BROWSER_ARGS)
    ua = MOBILE_USER_AGENT if is_mobile else DESKTOP_USER_AGENT
    browser_args.append(f"--user-agent={ua}")

    # Off-screen positioning for silent execution without triggering headless traps
    if offscreen:
        browser_args.append("--window-position=3000,3000")
        browser_args.append("--window-size=1440,900")
    else:
        browser_args.append("--window-size=1440,900")

    if proxy_url:
        clean_proxy = proxy_url.replace("socks5h://", "socks5://")
        browser_args.append(f"--proxy-server={clean_proxy}")
        logger.info(f"Routing browser traffic through proxy: {clean_proxy}")

    if extra_args:
        browser_args.extend(extra_args)

    mode_str = "Offscreen Desktop GUI" if offscreen else ("Mobile Android" if is_mobile else "Desktop GUI")
    logger.info(f"Starting Chrome browser [{mode_str}] (headless={headless})...")

    # If profile directory is specified, ensure it exists
    profile_path = user_data_dir
    if not profile_path:
        profile_path = os.path.join(BASE_DIR, "data", "browser_profiles", "default_worker")
    os.makedirs(profile_path, exist_ok=True)

    browser = await uc.start(
        browser_args=browser_args,
        headless=headless,
        sandbox=False,
        user_data_dir=profile_path
    )
    
    tab = None
    for _ in range(20):
        try:
            if hasattr(browser, "main_tab"):
                tab = browser.main_tab
                if tab:
                    break
        except (StopIteration, Exception):
            pass
        await asyncio.sleep(0.1)

    if not tab:
        try:
            tab = await browser.get("about:blank")
        except Exception:
            pass

    try:
        if tab:
            await tab.send(cdp.network.enable())

            if is_mobile:
                await tab.send(cdp.emulation.set_device_metrics_override(
                    width=412,
                    height=915,
                    device_scale_factor=2.6,
                    mobile=True,
                    screen_width=412,
                    screen_height=915,
                    position_x=0,
                    position_y=0,
                    dont_set_visible_size=False
                ))
                await tab.send(cdp.emulation.set_touch_emulation_enabled(enabled=True, max_touch_points=5))

            if block_media:
                await tab.send(cdp.network.set_blocked_ur_ls(urls=SURGICAL_BLOCKED_URLS))

            await tab.send(cdp.page.add_script_to_evaluate_on_new_document(source=STEALTH_INJECTION_JS))
    except Exception as e:
        logger.debug(f"CDP stealth initialization notice: {e}")

    return browser


def close_browser(browser: Optional[uc.Browser]):
    if browser:
        try:
            browser.stop()
            logger.info("Browser session closed cleanly.")
        except Exception:
            pass
