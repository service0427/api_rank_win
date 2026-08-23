import asyncio
import os
import sys
import json
import time
import urllib.parse
import nodriver as uc

sys.stdout.reconfigure(encoding='utf-8')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DATA_DIR = os.path.join(os.getcwd(), "data", "offscreen_user_test")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_KEYWORDS = ["노트북", "스마트폰", "만두", "원두커피", "게이밍마우스"]

async def run_offscreen_search_suite(custom_keyword: str = ""):
    keywords = [custom_keyword] if custom_keyword else DEFAULT_KEYWORDS

    print("=" * 85)
    print("  [오프스크린(Off-Screen) 가상 좌표 기반 무간섭 쇼핑 순위 수집 실전 테스트]")
    print(f"  - 브라우저 모드   : 진짜 GUI (headless=False) + 모니터 바깥 배치 (--window-position=3000,3000)")
    print(f"  - 테스트 키워드   : {keywords}")
    print("  - 특징           : 화면에 창이 안 떠서 헤드리스처럼 편하고, 네이버는 100% 정상 PC로 인식!")
    print("=" * 85)

    # Launch Chrome in Real GUI mode, but positioned OFF-SCREEN!
    browser = await uc.start(
        browser_executable_path=CHROME_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=[
            "--window-size=1440,900",
            "--window-position=3000,3000",   # ★ 화면 밖 가상 좌표 배치
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    results = []
    total_start = time.time()

    try:
        active_tab = tab

        for idx, kw in enumerate(keywords, 1):
            q_start = time.time()
            q_enc = urllib.parse.quote(kw)
            search_url = f"https://search.naver.com/search.naver?where=nexearch&query={q_enc}"

            print(f"\n[{idx:02d}/{len(keywords):02d}] '{kw}' 검색 시작 (통합검색 직행 중...)")
            await active_tab.get(search_url)
            await active_tab.sleep(2.0)

            # Click '가격비교 더보기'
            await active_tab.evaluate("""
                (() => {
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    const moreBtn = allLinks.find(a => 
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

            await active_tab.sleep(2.5)

            tabs = browser.tabs
            active_tab = tabs[-1] if len(tabs) > 1 else tab

            curr_url = await active_tab.evaluate("window.location.href")
            page_title = await active_tab.evaluate("document.title")

            # Extract __NEXT_DATA__
            next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
            item_count = 0
            sample_top = []
            if next_data_str:
                d = json.loads(next_data_str)
                pp = d.get('props', {}).get('pageProps', {})
                comp_list = pp.get('compositeList', {}).get('list', []) or pp.get('compositeProducts', {}).get('list', [])
                organic_list = [it for it in comp_list if not bool(it.get('item', it).get('ad') or it.get('item', it).get('adId'))]
                item_count = len(organic_list)
                for it in organic_list[:3]:
                    item = it.get('item', it)
                    sample_top.append({
                        "title": (item.get('productTitle') or item.get('productName') or '')[:32],
                        "mall": item.get('mallName') or item.get('channelName') or '',
                        "price": item.get('lowPrice') or item.get('price') or 0,
                        "nvMid": item.get('id') or item.get('nvMid') or ''
                    })

            elapsed = time.time() - q_start
            is_blocked = "nidlogin" in curr_url or item_count == 0
            status_text = "❌ 차단/로그인" if is_blocked else f"★ 200 OK 성공 ({item_count}개)"

            print(f"      -> 상태: {status_text} | 소요시간: {elapsed:.2f}초")
            if sample_top:
                print(f"      -> 1위: {sample_top[0]['title']} ({sample_top[0]['mall']}) | {sample_top[0]['price']:,}원 | nvMid: {sample_top[0]['nvMid']}")

            results.append({"kw": kw, "items": item_count, "time": elapsed, "blocked": is_blocked})
            await active_tab.sleep(1.0)

    finally:
        browser.stop()

    total_elapsed = time.time() - total_start
    success_count = sum(1 for r in results if not r["blocked"])

    print("\n" + "=" * 85)
    print("  ★ [오프스크린 실전 테스트 최종 결과]")
    print(f"  - 총 테스트 키워드 : {len(keywords)}개")
    print(f"  - 성공 (200 OK)   : {success_count}개 (성공률: {success_count / len(keywords) * 100:.1f}%)")
    print(f"  - 차단 (로그인/418): {len(keywords) - success_count}개")
    print(f"  - 총 소요 시간     : {total_elapsed:.2f}초 (평균: {total_elapsed / len(keywords):.2f}초)")
    print("=" * 85)

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        uc.loop().run_until_complete(run_offscreen_search_suite(kw))
    except KeyboardInterrupt:
        print("\n정상 종료되었습니다.")
