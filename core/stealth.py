DEFAULT_BROWSER_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process,InterestFeedContentSuggestions",
    "--disable-infobars",
    "--disable-notifications",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-background-timer-throttling",
    "--disable-ipc-flooding-protection",
    "--disable-hang-monitor",
    "--disable-quic",  # Crucial: Disables HTTP/3 QUIC UDP to prevent proxy bypass & IP leaks
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--lang=ko-KR,ko",
]

STEALTH_INJECTION_JS = """
(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    window.chrome = window.chrome || { runtime: {}, loadTimes: () => {}, csi: () => {} };
})();
"""
