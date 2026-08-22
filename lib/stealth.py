"""
Stealth configuration and CDP injection scripts for nodriver.
Eliminates WebDriver and automated browser detection indicators.
"""

from nodriver import cdp

STEALTH_JS = r"""
(() => {
    // 1. Remove and override navigator.webdriver
    try {
        if (Object.prototype.hasOwnProperty.call(navigator, 'webdriver')) {
            delete navigator.webdriver;
        }
        Object.defineProperty(Object.getPrototypeOf(navigator), 'webdriver', {
            get: () => undefined,
            set: () => {},
            configurable: true,
            enumerable: true
        });
    } catch (e) {}

    // 2. Ensure window.chrome and sub-properties exist and look authentic
    try {
        if (!window.chrome) {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {
                OnInstalledReason: {
                    CHROME_UPDATE: 'chrome_update',
                    INSTALL: 'install',
                    SHARED_MODULE_UPDATE: 'shared_module_update',
                    UPDATE: 'update'
                },
                OnRestartRequiredReason: {
                    APP_UPDATE: 'app_update',
                    OS_UPDATE: 'os_update',
                    PERIODIC: 'periodic'
                },
                PlatformArch: {
                    ARM: 'arm',
                    ARM64: 'arm64',
                    MIPS: 'mips',
                    MIPS64: 'mips64',
                    X86_32: 'x86-32',
                    X86_64: 'x86-64'
                },
                PlatformNaclArch: {
                    ARM: 'arm',
                    MIPS: 'mips',
                    MIPS64: 'mips64',
                    X86_32: 'x86-32',
                    X86_64: 'x86-64'
                },
                PlatformOs: {
                    ANDROID: 'android',
                    CROS: 'cros',
                    LINUX: 'linux',
                    MAC: 'mac',
                    OPENBSD: 'openbsd',
                    WIN: 'win'
                },
                RequestUpdateCheckStatus: {
                    NO_UPDATE: 'no_update',
                    THROTTLED: 'throttled',
                    UPDATE_AVAILABLE: 'update_available'
                },
                connect: function() {},
                sendMessage: function() {}
            };
        }
        if (!window.chrome.app) {
            window.chrome.app = {
                isInstalled: false,
                InstallState: {
                    DISABLED: 'disabled',
                    INSTALLED: 'installed',
                    NOT_INSTALLED: 'not_installed'
                },
                RunningState: {
                    CANNOT_RUN: 'cannot_run',
                    READY_TO_RUN: 'ready_to_run',
                    RUNNING: 'running'
                },
                getIsInstalled: () => false,
                getDetails: () => null
            };
        }
        if (!window.chrome.csi) {
            window.chrome.csi = function() {
                return {
                    startE: Date.now(),
                    onloadT: Date.now(),
                    pageT: Math.random() * 100,
                    tran: 15
                };
            };
        }
        if (!window.chrome.loadTimes) {
            window.chrome.loadTimes = function() {
                return {
                    commitLoadTime: Date.now() / 1000,
                    connectionInfo: 'h2',
                    finishDocumentLoadTime: Date.now() / 1000,
                    finishLoadTime: Date.now() / 1000,
                    firstPaintAfterLoadTime: 0,
                    firstPaintTime: Date.now() / 1000,
                    navigationType: 'Other',
                    npnNegotiatedProtocol: 'h2',
                    requestTime: Date.now() / 1000,
                    startLoadTime: Date.now() / 1000,
                    wasAlternateProtocolAvailable: false,
                    wasFetchedViaSpdy: true,
                    wasNpnNegotiated: true
                };
            };
        }
    } catch (e) {}

    // 3. Remove common automation indicators & variables
    const propsToClean = [
        'webdriver',
        '_Selenium_IDE_Recorder',
        '_selenium',
        'calledSelenium',
        '_WEBDRIVER_ELEM_CACHE',
        'ChromeDriverw',
        'driver-evaluate',
        'webdriver-evaluate',
        'selenium-evaluate',
        'webdriverCommand',
        'webdriver-evaluate-response',
        '__webdriverFunc',
        '__webdriver_script_fn',
        '__$webdriverAsyncExecutor',
        '__lastWatirAlert',
        '__lastWatirConfirm',
        '__lastWatirPrompt',
        '$chrome_asyncScriptInfo',
        '$cdc_asdjflasutopfhvcZLmcfl_'
    ];
    for (const prop of propsToClean) {
        try {
            if (prop in window) delete window[prop];
            if (prop in document) delete document[prop];
        } catch(e) {}
    }

    // 4. Permissions API consistency
    try {
        if (navigator.permissions && navigator.permissions.query) {
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) => (
                parameters && parameters.name === 'notifications' ?
                    Promise.resolve({
                        state: (typeof Notification !== 'undefined' && Notification.permission === 'granted') ? 'granted' : (typeof Notification !== 'undefined' && Notification.permission === 'denied' ? 'denied' : 'prompt'),
                        onchange: null
                    }) :
                    originalQuery(parameters)
            );
        }
    } catch(e) {}

    // 5. Ensure navigator.plugins has standard entries if empty
    try {
        if (navigator.plugins.length === 0) {
            const pluginData = [
                { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
            ];
            Object.defineProperty(navigator, 'plugins', {
                get: () => pluginData,
                configurable: true
            });
        }
    } catch(e) {}

    // 6. Ensure navigator.languages has natural Korean/English locales
    try {
        if (!navigator.languages || navigator.languages.length === 0) {
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en'],
                configurable: true
            });
        }
    } catch(e) {}

    // 7. Native function toString protection
    try {
        const nativeToString = Function.prototype.toString;
        const customToString = function() {
            if (this === (navigator.permissions && navigator.permissions.query)) {
                return 'function query() { [native code] }';
            }
            if (this === window.chrome.csi) {
                return 'function csi() { [native code] }';
            }
            if (this === window.chrome.loadTimes) {
                return 'function loadTimes() { [native code] }';
            }
            return nativeToString.call(this);
        };
        Function.prototype.toString = customToString;
        customToString.toString = () => 'function toString() { [native code] }';
    } catch(e) {}
})();
"""

DEFAULT_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--lang=ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "--start-maximized",
    "--no-default-browser-check",
    "--no-first-run",
    "--disable-infobars",
    "--disable-notifications",
    "--disable-popup-blocking",
    "--window-size=1920,1080",
]


async def apply_stealth_to_tab(tab) -> None:
    """
    Applies stealth scripts to the target tab via CDP Page.addScriptToEvaluateOnNewDocument.
    """
    await tab.send(cdp.page.add_script_to_evaluate_on_new_document(source=STEALTH_JS))
