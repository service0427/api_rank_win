import asyncio
import os
import sys
import json
import nodriver as uc

sys.stdout.reconfigure(encoding='utf-8')

WHALE_PATH = r"C:\Program Files\Naver\Naver Whale\Application\whale.exe"
BASE_DATA_DIR = os.path.join(os.getcwd(), "data", "whale_live_demo")
os.makedirs(BASE_DATA_DIR, exist_ok=True)

# 4 Quadrant screen layout for visible demo
WORKER_CONFIGS = [
    {"id": 1, "keyword": "노트북", "pos": "50,50", "size": "880,620"},
    {"id": 2, "keyword": "스마트폰", "pos": "950,50", "size": "880,620"},
    {"id": 3, "keyword": "만두", "pos": "50,420", "size": "880,620"},
    {"id": 4, "keyword": "커피", "pos": "950,420", "size": "880,620"},
]

async def run_single_whale(cfg: dict, results: dict):
    wid = cfg["id"]
    keyword = cfg["keyword"]
    profile_dir = os.path.join(BASE_DATA_DIR, f"worker_{wid}")
    os.makedirs(profile_dir, exist_ok=True)

    print(f"[{wid}번 웨일] 브라우저 창 기동 중... (키워드: '{keyword}', 위치: {cfg['pos']})")

    browser = await uc.start(
        browser_executable_path=WHALE_PATH,
        headless=False,
        user_data_dir=profile_dir,
        browser_args=[
            f"--window-size={cfg['size']}",
            f"--window-position={cfg['pos']}",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    try:
        # Step 1: Open Naver Main
        print(f"[{wid}번 웨일] 1. 네이버 메인 접속...")
        await tab.get("https://www.naver.com")
        await tab.sleep(2.0)

        # Step 2: Type keyword
        print(f"[{wid}번 웨일] 2. 검색창에 '{keyword}' 입력 및 검색...")
        q_input = await tab.select("input#query, input[name='query']")
        if q_input:
            await q_input.click()
            await q_input.send_keys(keyword)
            await tab.sleep(0.3)
            s_btn = await tab.select("button.btn_search, .btn_search")
            if s_btn:
                await s_btn.click()
            else:
                await tab.evaluate("document.querySelector('input#query').form.submit()")
        await tab.sleep(3.0)

        # Step 3: Click '가격비교 더보기'
        print(f"[{wid}번 웨일] 3. '가격비교 더보기' 링크 클릭...")
        await tab.evaluate("""
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
        await tab.sleep(3.5)

        tabs = browser.tabs
        active_tab = tabs[-1] if len(tabs) > 1 else tab

        curr_url = await active_tab.evaluate("window.location.href")
        page_title = await active_tab.evaluate("document.title")

        # Check __NEXT_DATA__
        next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
        item_count = 0
        if next_data_str:
            d = json.loads(next_data_str)
            pp = d.get('props', {}).get('pageProps', {})
            comp_list = pp.get('compositeList', {}).get('list', []) or pp.get('compositeProducts', {}).get('list', [])
            item_count = len(comp_list)

        results[wid] = {
            "keyword": keyword,
            "title": page_title,
            "url": curr_url,
            "items": item_count
        }
        print(f"★ [{wid}번 웨일] 쇼핑 전문관 도착 완료! ('{page_title}', 상품 {item_count}개 감지)")

        # Keep windows open for 20 seconds so user can directly inspect them on monitor
        print(f"[{wid}번 웨일] 화면 확인을 위해 20초간 대기합니다...")
        await active_tab.sleep(20.0)

    finally:
        browser.stop()

async def main():
    print("=" * 80)
    print("  [실시간 화면 시연: 4개 독립 웨일(Whale) 브라우저 동시 구동 및 쇼핑 탐색]")
    print("=" * 80)

    results = {}
    tasks = [run_single_whale(cfg, results) for cfg in WORKER_CONFIGS]
    await asyncio.gather(*tasks)

    print("\n" + "=" * 80)
    print("  ★ [4개 웨일 브라우저 동시 실행 결과 요약]")
    print("=" * 80)
    for wid, r in sorted(results.items()):
        print(f"  - 웨일 #{wid} ({r['keyword']:<5}) : {r['title']} -> 상품 {r['items']}개 수집 성공 (URL: {r['url'][:60]}...)")
    print("=" * 80)

if __name__ == "__main__":
    uc.loop().run_until_complete(main())
