import asyncio
import os
import sys
import ctypes
import time
import urllib.parse
import nodriver as uc
from nodriver import cdp

sys.stdout.reconfigure(encoding='utf-8')

WHALE_PATH = r"C:\Program Files\Naver\Naver Whale\Application\whale.exe"
DATA_DIR = os.path.join(os.getcwd(), "data", "whale_ctrl_shift_m_user")
os.makedirs(DATA_DIR, exist_ok=True)

user32 = ctypes.windll.user32

def trigger_ctrl_shift_m():
    print("\n2. [웨일 공식] Ctrl + Shift + M 모바일창 단축키 입력 중...")
    hwnd = user32.FindWindowW(None, "NAVER - 네이버 웨일")
    if not hwnd:
        hwnd = user32.FindWindowW("Chrome_WidgetWin_1", None)
    if hwnd:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)

    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_M = 0x4D
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    user32.keybd_event(VK_M, 0, 0, 0)
    time.sleep(0.15)
    user32.keybd_event(VK_M, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    print("★ [완료] 네이버 웨일 네이티브 모바일창이 화면에 생성되었습니다!")

async def run_whale_mobile_window_feature(keyword: str = "스마트폰"):
    print("=" * 80)
    print("  [네이버 공식 웨일 브라우저 네이티브 '모바일창(Ctrl+Shift+M)' 구동기]")
    print(f"  - 바이너리 : {WHALE_PATH}")
    print(f"  - 키워드   : '{keyword}'")
    print("=" * 80)

    # 1. Launch Whale PC
    browser = await uc.start(
        browser_executable_path=WHALE_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=[
            "--window-size=1280,850",
            "--window-position=50,50",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    try:
        print("1. 웨일 메인 브라우저 기동 완료...")
        await tab.get("https://www.naver.com")
        await tab.sleep(2.0)

        # 2. Trigger native Whale Mobile Window
        trigger_ctrl_shift_m()
        await tab.sleep(3.0)

        print("\n3. 웨일 공식 모바일창이 열린 상태입니다.")
        print("   화면에서 모바일창의 동작 및 검색을 자유롭게 확인해보실 수 있습니다.")
        print("   (종료 시 터미널에서 Ctrl + C 를 누르시거나 창을 닫으시면 됩니다.)\n")

        while True:
            await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        try:
            browser.stop()
        except:
            pass

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "스마트폰"
    try:
        uc.loop().run_until_complete(run_whale_mobile_window_feature(kw))
    except KeyboardInterrupt:
        print("\n정상 종료되었습니다.")
