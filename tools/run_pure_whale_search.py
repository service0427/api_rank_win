import asyncio
import os
import sys
import json
import urllib.parse
import nodriver as uc

sys.stdout.reconfigure(encoding='utf-8')

WHALE_PATH = r"C:\Program Files\Naver\Naver Whale\Application\whale.exe"
DATA_DIR = os.path.join(os.getcwd(), "data", "pure_whale_user_run")
os.makedirs(DATA_DIR, exist_ok=True)

async def run_pure_whale(keyword: str = "노트북"):
    print("=" * 80)
    print("  [100% 순수 네이버 웨일 브라우저 네이티브 모바일 뷰 실행기]")
    print(f"  - 실행 바이너리 : {WHALE_PATH}")
    print(f"  - 검색 키워드   : '{keyword}'")
    print("  - 특징          : 인위적 UA 변조 제로 / 순수 Whale.exe 100% 그대로 구동")
    print("=" * 80)

    # Launch Pure Whale PC in Mobile Window Aspect Ratio
    browser = await uc.start(
        browser_executable_path=WHALE_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=[
            "--window-size=460,920",
            "--window-position=120,60",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    try:
        # Step 1: Open m.naver.com
        print(f"\n1. 모바일 네이버 메인(m.naver.com) 접속 중...")
        await tab.get("https://m.naver.com")
        await tab.sleep(2.0)

        # Step 2: Search Keyword
        print(f"2. 검색창에 '{keyword}' 입력 및 검색 실행...")
        q_enc = urllib.parse.quote(keyword)
        search_url = f"https://m.search.naver.com/search.naver?where=m&query={q_enc}"
        await tab.get(search_url)
        await tab.sleep(3.0)

        title = await tab.evaluate("document.title")
        print(f"3. 모바일 통합검색 도착: '{title}'")

        # Step 3: Extract Live Shopping Products on Mobile Search Page
        print("\n4. 모바일 화면에 노출된 실시간 쇼핑 랭킹 상품 추출 중...")
        dom_data_str = await tab.evaluate("""
            JSON.stringify((() => {
                const links = Array.from(document.querySelectorAll('a'));
                const gateLinks = links.filter(a => a.href && a.href.includes('bridge/searchGate'));
                const results = [];
                const seenMid = new Set();

                for (const a of gateLinks) {
                    const href = a.href || '';
                    const match = href.match(/nv_mid=([0-9]+)/);
                    const nvMid = match ? match[1] : '';
                    if (!nvMid || seenMid.has(nvMid)) continue;
                    seenMid.add(nvMid);

                    // Find parent card
                    let card = a.closest('div[class*="item"], li, div[class*="box"]') || a;
                    const titleEl = card.querySelector('a[title], strong, [class*="title"], [class*="name"]');
                    const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : a.textContent.trim();

                    const priceEl = card.querySelector('[class*="price"] strong, [class*="price"] em, [class*="price"]');
                    const price = priceEl ? priceEl.textContent.replace(/[^0-9]/g, '') : '';

                    if (title) {
                        results.push({ nvMid, title: title.replace(/\\s+/g, ' '), price: price ? parseInt(price, 10) : 0 });
                    }
                }
                return results;
            })())
        """)

        items = json.loads(dom_data_str) if dom_data_str else []
        print("\n" + "-" * 80)
        print(f"  ★ 모바일 검색 화면에서 실시간 쇼핑 상품 {len(items)}개 감지 완료!")
        print("-" * 80)
        for idx, it in enumerate(items[:8]):
            p_str = f"{it['price']:,}원" if it['price'] else "가격비교"
            print(f"  #{idx+1:02d} | {it['title'][:35]:<35} | {p_str:<12} | nvMid: {it['nvMid']}")
        print("-" * 80)

        print("\n💡 직접 모바일 화면을 확인하고 조작해 보실 수 있도록 브라우저 창을 유지합니다.")
        print("   (종료하시려면 터미널에서 Ctrl + C 를 누르시거나 창을 닫으시면 됩니다.)")

        # Keep open indefinitely until user closes or presses Ctrl+C
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
    kw = sys.argv[1] if len(sys.argv) > 1 else "노트북"
    try:
        uc.loop().run_until_complete(run_pure_whale(kw))
    except KeyboardInterrupt:
        print("\n정상 종료되었습니다.")
