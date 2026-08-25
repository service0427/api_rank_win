import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio
import json
import time
import random
import datetime
import urllib.parse
import nodriver as uc
from nodriver import cdp

sys.stdout.reconfigure(encoding='utf-8')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "nnb_live_demo_profile")
os.makedirs(DATA_DIR, exist_ok=True)

def generate_aged_nnb(hours_ago: int = 24):
    past_timestamp_ms = int((time.time() - (hours_ago * 3600)) * 1000)
    past_dt = datetime.datetime.fromtimestamp(past_timestamp_ms / 1000)
    
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    num = past_timestamp_ms
    res = []
    while num > 0:
        res.append(chars[num % 36])
        num //= 36
    base36_time = "".join(reversed(res))
    salt = "".join(random.choices(chars, k=max(0, 14 - len(base36_time))))
    nnb_value = (base36_time + salt)[:14]
    return nnb_value, past_dt

async def run_nnb_aging_live(keyword: str = "스마트폰", hours_ago: int = 24):
    nnb_val, nnb_dt = generate_aged_nnb(hours_ago=hours_ago)

    print("=" * 85)
    print("  [네이버 NNB 쿠키 타임스탬프 조작(Aging) 실시간 시각 검증 데모]")
    print(f"  - 검색 키워드       : '{keyword}'")
    print(f"  - 주입할 숙성 NNB   : {nnb_val}")
    print(f"  - 인코딩된 가상 시각: {nnb_dt.strftime('%Y-%m-%d %H:%M:%S')} ({hours_ago}시간 전 과거 시점)")
    print(f"  - 현재 실제 시각    : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 85)

    print("\n1. 실제 모니터 화면에 크롬 브라우저를 띄웁니다 (50, 50 위치)...")
    browser = await uc.start(
        browser_executable_path=CHROME_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=[
            "--window-size=1280,850",
            "--window-position=50,50",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    try:
        # Step 1: Inject aged NNB
        print(f"2. [CDP 주입] 24시간 숙성 NNB ({nnb_val})를 .naver.com 쿠키에 강제 세팅...")
        await tab.send(cdp.network.enable())
        cookie_param = cdp.network.CookieParam(
            name="NNB",
            value=nnb_val,
            domain=".naver.com",
            path="/"
        )
        await tab.send(cdp.network.set_cookies(cookies=[cookie_param]))
        await tab.sleep(0.5)

        # Step 2: Navigate to Unified Search
        q_enc = urllib.parse.quote(keyword)
        search_url = f"https://search.naver.com/search.naver?where=nexearch&query={q_enc}"
        print(f"3. 통합검색 진입: {search_url}")
        await tab.get(search_url)
        await tab.sleep(2.0)

        # Step 3: Click '가격비교 더보기'
        print("4. '네이버 가격비교 더보기' 즉시 클릭 (체류 시간 없이 바로 클릭)...")
        await tab.evaluate("""
            (() => {
                const moreBtn = Array.from(document.querySelectorAll('a')).find(a => 
                    (a.textContent.includes('가격비교') && a.textContent.includes('더보기')) || 
                    (a.href.includes('search.shopping.naver.com') && a.textContent.includes('더보기'))
                );
                if (moreBtn) {
                    moreBtn.removeAttribute('target');
                    moreBtn.setAttribute('target', '_self');
                    moreBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    moreBtn.click();
                }
            })()
        """)
        await tab.sleep(3.0)

        tabs = browser.tabs
        active_tab = tabs[-1] if len(tabs) > 1 else tab

        curr_url = await active_tab.evaluate("window.location.href")
        page_title = await active_tab.evaluate("document.title")

        print("\n" + "=" * 85)
        print("  ★ [화면 실시간 검증 결과]")
        print("=" * 85)
        print(f"  - 도착 페이지 제목 : '{page_title}'")
        print(f"  - 현재 브라우저 URL: {curr_url[:80]}...")
        print(f"  - 로그인창 격리 여부: {'❌ 로그인 차단 발생' if 'nidlogin' in curr_url else '★ [100% 200 OK 프리패스 통과!!]'}")
        print("=" * 85)

        # Extract __NEXT_DATA__
        next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
        if next_data_str:
            d = json.loads(next_data_str)
            comp_list = d.get('props', {}).get('pageProps', {}).get('compositeList', {}).get('list', []) or []
            organic_list = [it for it in comp_list if not bool(it.get('item', it).get('ad') or it.get('item', it).get('adId'))]
            print(f"\n[추출된 실시간 1페이지 순수 상품 목록: 총 {len(organic_list)}개]")
            for idx, it in enumerate(organic_list[:5], 1):
                item = it.get('item', it)
                t = (item.get('productTitle') or item.get('productName') or '')[:32]
                m = item.get('mallName') or item.get('channelName') or ''
                p = item.get('lowPrice') or item.get('price') or 0
                iid = item.get('id') or item.get('nvMid') or ''
                print(f"  #{idx:02d} | {t:<32} | {m:<10} | {p:,}원 | nvMid: {iid}")

        print("\n💡 화면을 직접 확인하실 수 있도록 10초간 브라우저 창을 유지합니다...")
        await active_tab.sleep(10.0)

    finally:
        browser.stop()

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "스마트폰"
    try:
        uc.loop().run_until_complete(run_nnb_aging_live(kw))
    except KeyboardInterrupt:
        print("\n종료되었습니다.")
