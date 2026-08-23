import random
import json
import os
import socket
import time
import urllib.request
from typing import Dict, List, Optional
from core.logger import get_logger
from config.settings import PROXY_STATUS_API, USE_PROXY_POOL, BASE_DIR

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
        if not force and (now - self._last_sync_time < 20) and self._proxies:
            return self._proxies

        # 1. Check local proxy list file (config/proxies.txt)
        proxy_file = os.path.join(BASE_DIR, "config", "proxies.txt")
        if os.path.exists(proxy_file):
            try:
                with open(proxy_file, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                if lines:
                    self._proxies = [{"proxy": p} for p in lines]
                    self._last_sync_time = now
                    return self._proxies
            except Exception as e:
                logger.debug(f"Failed to read {proxy_file}: {e}")

        # 2. Check if proxy status API is available
        try:
            req = urllib.request.urlopen(PROXY_STATUS_API, timeout=1.5)
            data = json.loads(req.read().decode())
            active = data.get("proxies", [])
            if active:
                self._proxies = active
                self._last_sync_time = now
                logger.info(f"Refreshed proxy pool from API: {len(self._proxies)} active proxies available.")
                return self._proxies
        except Exception:
            pass

        return self._proxies

    def test_proxy_alive(self, proxy_str: str, timeout: float = 1.0) -> bool:
        """Quick TCP handshake check to avoid browser freezing on whitelisted/dead proxies."""
        clean = proxy_str.replace("socks5://", "").replace("http://", "").replace("socks5h://", "")
        if ":" not in clean:
            return False
        host, port = clean.split(":", 1)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, int(port)))
            sock.close()
            return True
        except Exception:
            return False

    def get_next_proxy(self, random_choice: bool = True, check_alive: bool = False) -> Optional[str]:
        proxies = self.refresh_proxies()
        if not proxies:
            return None

        # Filter out failed/cooldown proxies
        available = []
        now = time.time()
        for p in proxies:
            addr = p.get("proxy")
            if addr and (now - self._failed_proxies.get(addr, 0) >= 60):
                available.append(addr)

        if not available:
            available = [p.get("proxy") for p in proxies if p.get("proxy")]

        if not available:
            return None

        # Randomize selection
        if random_choice:
            random.shuffle(available)

        for candidate in available:
            if check_alive:
                if self.test_proxy_alive(candidate, timeout=0.8):
                    return candidate if candidate.startswith(("socks5://", "http://")) else f"socks5://{candidate}"
                else:
                    self._failed_proxies[candidate] = now
            else:
                return candidate if candidate.startswith(("socks5://", "http://")) else f"socks5://{candidate}"

        return None

    def mark_proxy_failed(self, proxy_url: str, reason: str = ""):
        clean = proxy_url.replace("socks5://", "").replace("http://", "")
        self._failed_proxies[clean] = time.time()
        logger.warning(f"Marked proxy {clean} as temporarily degraded ({reason}). Switching to next.")

    def get_all_status(self) -> List[Dict[str, any]]:
        self.refresh_proxies(force=True)
        return self._proxies


proxy_mgr = ProxyManager()
