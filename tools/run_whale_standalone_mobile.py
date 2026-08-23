import asyncio
import os
import sys
import urllib.parse
import json
import nodriver as uc

sys.stdout.reconfigure(encoding='utf-8')

WHALE_PATH = r"C:\Program Files\Naver\Naver Whale\Application\whale.exe"
DATA_DIR = os.path.join(os.getcwd(), "data", "whale_standalone_mobile_user")
os.makedirs(DATA_DIR, exist_ok=True)

async def run_standalone_mobile_window(keyword: str = "스마트폰"):
    q_enc = urllib.parse.quote(keyword)
    target_url = f"https://m.search.naver.com/search.naver?where=m&query={q_enc}"

    print("=" * 80)
    print("  [웨일 메인 브라우저 없이 '단독 모바일창(Standalone App Mode)' 1초 직행 실행기]")
    print(f"  - 바이너리 : {WHALE_PATH}")
    print(f"  - 검색 대상 : '{keyword}'")
    print(f"  - 직행 URL  : {target_url}")
    print("=" * 80)

    # Launch Whale directly in Standalone Mobile App Window (No desktop tabs/toolbars!)
    browser = await uc.start(
        browser_executable_path=WHALE_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=[
            f"--app={target_url}",
            "--window-size=440,920",
            "--window-position=150,80",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    try:
        print("\n1. 단독 모바일 창 즉시 기동 및 검색 화면 로딩...")
        await tab.get(target_url)
        await tab.sleep(3.0)

        title = await tab.evaluate("document.title")
        print(f"2. 모바일 검색 화면 도착 완료: '{title}'")

        # Extract items
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
        print(f"  ★ 모바일 단독 창에서 실시간 상품 {len(items)}개 감지 완료!")
        print("-" * 80)
        for idx, it in enumerate(items[:5]):
            p_str = f"{it['price']:,}원" if it['price'] else "가격비교"
            print(f"  #{idx+1:02d} | {it['title'][:35]:<35} | {p_str:<12} | nvMid: {it['nvMid']}")
        print("-" * 80)

        print("\n💡 메인 데스크톱 창 없이 '순수 단독 모바일 창'만 화면에 떠 있는 상태입니다.")
        print("   화면에서 자유롭게 스크롤하고 확인해보실 수 있습니다.")
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
        uc.loop().run_until_complete(run_standalone_mobile_window(kw))
    except KeyboardInterrupt:
        print("\n정상 종료되었습니다.")
