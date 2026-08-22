import json
import time
import urllib.request
from typing import Dict, List, Optional
from core.logger import get_logger
from config.settings import PROXY_STATUS_API, USE_PROXY_POOL

logger = get_logger("rank.proxy")


class ProxyManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxyManager, cls).__new__(cls)
            cls._instance._proxies = []
            cls._instance._current_idx = 0
            cls._instance._last_sync_time = 0
            cls._instance._failed_proxies = {}  # proxy -> timestamp
        return cls._instance

    def refresh_proxies(self, force: bool = False) -> List[Dict[str, any]]:
        now = time.time()
        if not force and (now - self._last_sync_time < 30) and self._proxies:
            return self._proxies

        try:
            req = urllib.request.urlopen(PROXY_STATUS_API, timeout=3.0)
            data = json.loads(req.read().decode())
            active = data.get("proxies", [])
            if active:
                self._proxies = active
                self._last_sync_time = now
                logger.info(f"Refreshed proxy pool: {len(self._proxies)} active proxies available.")
                return self._proxies
        except Exception as e:
            logger.debug(f"Proxy status API {PROXY_STATUS_API} not reachable: {e}")

        return self._proxies

    def get_next_proxy(self) -> Optional[str]:
        if not USE_PROXY_POOL:
            return None

        proxies = self.refresh_proxies()
        if not proxies:
            return None

        for _ in range(len(proxies)):
            p = proxies[self._current_idx % len(proxies)]
            self._current_idx += 1
            proxy_addr = p.get("proxy")

            # Check if temporarily cooldown
            fail_time = self._failed_proxies.get(proxy_addr, 0)
            if time.time() - fail_time < 60:  # 60s cooldown for bad IP
                continue

            return f"socks5://{proxy_addr}"

        # If all in cooldown, return the least recently used
        p = proxies[self._current_idx % len(proxies)]
        self._current_idx += 1
        return f"socks5://{p.get('proxy')}"

    def mark_proxy_failed(self, proxy_url: str, reason: str = ""):
        clean = proxy_url.replace("socks5://", "").replace("http://", "")
        self._failed_proxies[clean] = time.time()
        logger.warning(f"Marked proxy {clean} as temporarily degraded ({reason}). Switching to next.")

    def get_all_status(self) -> List[Dict[str, any]]:
        self.refresh_proxies(force=True)
        return self._proxies


proxy_mgr = ProxyManager()
