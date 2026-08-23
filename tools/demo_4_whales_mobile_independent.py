import asyncio
import os
import sys
import json
import urllib.parse
import nodriver as uc
from nodriver import cdp

sys.stdout.reconfigure(encoding='utf-8')

WHALE_PATH = r"C:\Program Files\Naver\Naver Whale\Application\whale.exe"
BASE_DATA_DIR = os.path.join(os.getcwd(), "data", "whale_mobile_4_independent")
os.makedirs(BASE_DATA_DIR, exist_ok=True)

# 4 Independent Whale Mobile Workers layout across screen
WORKERS = [
    {"id": 1, "keyword": "노트북", "pos": "50,50", "model": "SM-S928N", "dpr": 3.0},
    {"id": 2, "keyword": "스마트폰", "pos": "520,50", "model": "SM-S918N", "dpr": 3.0},
    {"id": 3, "keyword": "만두", "pos": "990,50", "model": "SM-G998N", "dpr": 2.75},
    {"id": 4, "keyword": "커피", "pos": "1460,50", "model": "SM-F946N", "dpr": 2.5},
]

async def run_single_mobile_whale(w_cfg: dict, results_dict: dict):
    wid = w_cfg["id"]
    keyword = w_cfg["keyword"]
    profile_dir = os.path.join(BASE_DATA_DIR, f"worker_{wid}")
    os.makedirs(profile_dir, exist_ok=True)

    print(f"[{wid}번 웨일 모바일] 브라우저 인스턴스 기동 (키워드: '{keyword}', 모델: {w_cfg['model']})")

    browser = await uc.start(
        browser_executable_path=WHALE_PATH,
        headless=False,
        user_data_dir=profile_dir,
        browser_args=[
            "--window-size=440,950",
            f"--window-position={w_cfg['pos']}",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    # 1. Inject Whale Native Mobile Window Metadata & Touch Emulation
    whale_ua = f"Mozilla/5.0 (Linux; Android 14; {w_cfg['model']}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36 Whale/4.39.410.14"
    ua_metadata = cdp.emulation.UserAgentMetadata(
        brands=[
            cdp.emulation.UserAgentBrandVersion(brand="Chromium", version="131"),
            cdp.emulation.UserAgentBrandVersion(brand="Whale", version="4"),
            cdp.emulation.UserAgentBrandVersion(brand="Not.A/Brand", version="99")
        ],
        full_version_list=[
            cdp.emulation.UserAgentBrandVersion(brand="Chromium", version="131.0.7871.212"),
            cdp.emulation.UserAgentBrandVersion(brand="Whale", version="4.39.410.14"),
            cdp.emulation.UserAgentBrandVersion(brand="Not.A/Brand", version="99.0.0.0")
        ],
        platform="Android",
        platform_version="14.0.0",
        architecture="arm64",
        model=w_cfg['model'],
        mobile=True,
        bitness="64",
        wow64=False
    )

    await tab.send(cdp.emulation.set_user_agent_override(
        user_agent=whale_ua,
        accept_language="ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        platform="Android",
        user_agent_metadata=ua_metadata
    ))
    await tab.send(cdp.emulation.set_device_metrics_override(
        width=430,
        height=932,
        device_scale_factor=w_cfg['dpr'],
        mobile=True,
        screen_width=430,
        screen_height=932
    ))
    await tab.send(cdp.emulation.set_touch_emulation_enabled(enabled=True, max_touch_points=5))

    all_products = []
    seen_ids = set()

    try:
        # Step 1: Open Mobile Main
        print(f"[{wid}번 웨일 모바일] 1. m.naver.com 접속...")
        await tab.get("https://m.naver.com")
        await tab.sleep(2.0)

        # Step 2: Search Keyword
        print(f"[{wid}번 웨일 모바일] 2. 검색창에 '{keyword}' 입력 및 검색...")
        q_enc = urllib.parse.quote(keyword)
        search_url = f"https://m.search.naver.com/search.naver?sm=mtp_sly.hst&where=m&query={q_enc}&acr=1"
        await tab.get(search_url)
        await tab.sleep(3.0)

        # Step 3: Locate and click Shopping / Price Comparison More link
        print(f"[{wid}번 웨일 모바일] 3. 가격비교 더보기 버튼 클릭...")
        click_res = await tab.evaluate("""
            (() => {
                const allLinks = Array.from(document.querySelectorAll('a'));
                const moreBtn = allLinks.find(a => 
                    (a.textContent.includes('가격비교') && a.textContent.includes('더보기')) || 
                    (a.href.includes('msearch.shopping.naver.com') && a.textContent.includes('더보기')) ||
                    (a.href.includes('msearch.shopping.naver.com') && a.href.includes('frm=MAUI')) ||
                    (a.textContent.trim() === '쇼핑' && a.href.includes('msearch.shopping'))
                );
                if (moreBtn) {
                    moreBtn.removeAttribute('target');
                    moreBtn.setAttribute('target', '_self');
                    moreBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    moreBtn.click();
                    return { found: true, href: moreBtn.href, text: moreBtn.textContent.trim() };
                }
                return { found: false };
            })()
        """)

        await tab.sleep(3.5)

        tabs = browser.tabs
        active_tab = tabs[-1] if len(tabs) > 1 else tab

        curr_url = await active_tab.evaluate("window.location.href")
        page_title = await active_tab.evaluate("document.title")

        # Step 4: Extract __NEXT_DATA__
        next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
        item_count = 0
        if next_data_str:
            d = json.loads(next_data_str)
            pp = d.get('props', {}).get('pageProps', {})
            comp_list = pp.get('compositeList', {}).get('list', []) or pp.get('compositeProducts', {}).get('list', [])
            item_count = len(comp_list)
            for it in comp_list:
                item = it.get('item', it)
                if not item.get('ad'):
                    all_products.append({
                        "id": item.get('id') or item.get('nvMid'),
                        "title": item.get('productTitle') or item.get('productName'),
                        "mall": item.get('mallName'),
                        "price": item.get('lowPrice') or item.get('price')
                    })

        results_dict[wid] = {
            "keyword": keyword,
            "title": page_title,
            "url": curr_url,
            "is_login_redirect": "nidlogin" in curr_url,
            "products_extracted": len(all_products),
            "sample_top": all_products[:3]
        }
        print(f"★ [{wid}번 웨일 모바일] 완료! (도착: '{page_title}', 오가닉 상품 {len(all_products)}개 수집)")

        # Keep open for inspection
        await active_tab.sleep(15.0)

    finally:
        browser.stop()

async def main():
    print("=" * 85)
    print("  [4개 완전히 독립된 웨일 모바일 브라우저 동시 구동 및 제어 실측]")
    print("=" * 85)

    results = {}
    tasks = [run_single_mobile_whale(cfg, results) for cfg in WORKERS]
    await asyncio.gather(*tasks)

    print("\n" + "=" * 85)
    print("  ★ [4개 독립 웨일 모바일 인스턴스 동시 제어 최종 결과 리포트]")
    print("=" * 85)

    for wid in sorted(results.keys()):
        r = results[wid]
        status = "★ 성공 (200 OK)" if r["products_extracted"] > 0 else ("로그인 리다이렉트" if r["is_login_redirect"] else "페이지 로드 대기")
        print(f"\n[웨일 모바일 #{wid}] (키워드: '{r['keyword']}')")
        print(f"  - 결과 상태        : {status}")
        print(f"  - 도착 페이지 제목 : '{r['title']}'")
        print(f"  - 추출된 상품 개수 : {r['products_extracted']}개")
        if r['sample_top']:
            print(f"  - 1위 상품 샘플    : {r['sample_top'][0].get('title')} ({r['sample_top'][0].get('mall')})")

    print("\n" + "=" * 85)

if __name__ == "__main__":
    uc.loop().run_until_complete(main())
