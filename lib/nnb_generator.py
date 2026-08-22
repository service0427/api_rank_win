"""
NNB & Session Cookie Generator via Naver LCS (Log Collector Service) Packet Dispatch.

Features:
1. Dispatches an authentic HTTP beacon packet to https://lcs.naver.com/m
2. Extracts fresh, server-issued NNB & BUC cookies from Set-Cookie response headers.
3. Provides helper to inject freshly generated NNB directly into CDP browser context.
"""

import http.cookiejar
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple
import nodriver as uc
from nodriver import cdp
from lib.logger import get_logger

logger = get_logger("nshop.nnb")


def fetch_fresh_nnb_via_lcs(user_agent: Optional[str] = None) -> Dict[str, str]:
    """
    Issues a direct HTTP packet to Naver LCS (lcs.naver.com/m) and parses the Set-Cookie headers
    to obtain authentic server-issued NNB and BUC cookies.
    """
    if not user_agent:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    # Standard LCS packet query parameters
    lcs_params = {
        "u": "https://www.naver.com",
        "e": "1",
        "os": "Win32",
        "ln": "ko-KR",
        "sr": "1920x1080",
        "pr": "1",
        "bw": "1920",
        "bh": "950",
        "c": "24",
        "j": "0",
        "k": "0",
        "v": "1",
        "cnt": "1"
    }

    url = f"https://lcs.naver.com/m?{urllib.parse.urlencode(lcs_params)}"
    logger.info(f"Dispatching LCS beacon packet to: {url[:60]}...")

    headers = {
        "User-Agent": user_agent,
        "Referer": "https://www.naver.com/",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
    }

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(url, headers=headers)

    cookies = {}
    try:
        with opener.open(req, timeout=5.0) as resp:
            set_cookies = resp.headers.get_all("Set-Cookie", [])
            for sc in set_cookies:
                for part in sc.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        if k.strip() in ("NNB", "BUC", "SRT30", "SRT5", "NAC", "NACT"):
                            cookies[k.strip()] = v.strip()

        # Also grab any cookies stored in jar
        for c in cj:
            cookies[c.name] = c.value

        logger.info(f"Successfully obtained {len(cookies)} server-issued cookies from LCS:")
        for k, v in cookies.items():
            logger.info(f" - {k:<10s} = {v}")

        return cookies

    except Exception as e:
        logger.error(f"Error fetching NNB via LCS packet: {e}")
        return {}


async def inject_lcs_cookies_to_tab(tab: uc.Tab, cookies: Optional[Dict[str, str]] = None):
    """
    Injects the server-issued LCS cookies (NNB, BUC, etc.) into the CDP browser context
    for all .naver.com domains.
    """
    if not cookies:
        cookies = fetch_fresh_nnb_via_lcs()

    logger.info(f"Injecting {len(cookies)} LCS-issued cookies into browser context via CDP...")
    for k, v in cookies.items():
        try:
            await tab.send(cdp.network.set_cookie(
                name=k,
                value=v,
                domain=".naver.com",
                path="/"
            ))
            await tab.send(cdp.network.set_cookie(
                name=k,
                value=v,
                domain=".shopping.naver.com",
                path="/"
            ))
        except Exception as e:
            logger.debug(f"Error setting cookie {k}: {e}")

    logger.info("LCS cookies (NNB, BUC) successfully injected into browser context.")
