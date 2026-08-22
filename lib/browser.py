"""
Browser manager for nodriver with stealth initialization, mobile emulation, and traffic optimization.
"""

from typing import List, Optional
import nodriver as uc
from nodriver import cdp
from lib.logger import get_logger
from lib.stealth import DEFAULT_BROWSER_ARGS, apply_stealth_to_tab

logger = get_logger("nshop.browser")

MOBILE_USER_AGENT = "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
DESKTOP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# URL patterns to block for near-packet speed & minimal bandwidth usage
BLOCKED_RESOURCE_URLS = [
    # 1. Product Images, Thumbnails (Eliminates 80%+ of total page bandwidth)
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg", "*.avif",
    "*shopping-phinf.pstatic.net*", "*search.pstatic.net/sunny*",
    "*img.danuri.io*", "*image7.coupangcdn.com*",
    # 2. Web Fonts
    "*.woff", "*.woff2", "*.ttf", "*.otf",
    # 3. Media
    "*.mp4", "*.webm", "*.mp3",
    # 4. Third-Party Trackers (Non-Naver only)
    "*google-analytics.com*", "*googletagmanager.com*", "*criteo.com*", "*adnxs.com*",
    "*clarity.ms*", "*facebook.net*", "*g.daum.net*"
]


async def start_stealth_browser(
    headless: bool = False,
    is_mobile: bool = True,
    block_media: bool = True,
    user_data_dir: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    lang: str = "ko-KR",
) -> uc.Browser:
    """
    Launches a stealth Chrome browser instance with bot detection neutralized.
    Supports mobile device metrics and media blocking for ultra-fast near-packet traffic.
    """
    browser_args = list(DEFAULT_BROWSER_ARGS)
    ua = MOBILE_USER_AGENT if is_mobile else DESKTOP_USER_AGENT
    browser_args.append(f"--user-agent={ua}")

    if extra_args:
        browser_args.extend(extra_args)

    mode_str = "Mobile Android Emulation" if is_mobile else "Desktop"
    logger.info(f"Starting Chrome browser [{mode_str}] (headless={headless}, block_media={block_media})...")
    
    browser = await uc.start(
        browser_args=browser_args,
        headless=headless,
        user_data_dir=user_data_dir,
        lang=lang,
    )

    tab = browser.main_tab
    await apply_stealth_to_tab(tab)
    await tab.send(cdp.network.enable())

    if is_mobile:
        # Emulate Galaxy S24 Ultra / standard modern Android viewport
        await tab.send(cdp.emulation.set_device_metrics_override(
            width=412,
            height=915,
            device_scale_factor=2.6,
            mobile=True
        ))
        await tab.send(cdp.emulation.set_touch_emulation_enabled(enabled=True))

    if block_media:
        # Block heavy resources to achieve packet-level speed
        try:
            await tab.send(cdp.network.set_blocked_ur_ls(urls=BLOCKED_RESOURCE_URLS))
            logger.info("CDP media/image resource blocking active (Traffic minimized to near-packet level).")
        except Exception as e:
            logger.warning(f"Failed to set blocked URLs: {e}")

    return browser


def close_browser(browser: uc.Browser) -> None:
    """
    Safely stops and cleans up the browser instance.
    """
    if browser:
        try:
            logger.info("Closing browser session...")
            browser.stop()
            logger.info("Browser session closed.")
        except Exception as e:
            logger.warning(f"Exception during browser close: {e}")
