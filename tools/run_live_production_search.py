import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio
import json
import time
import urllib.parse
import nodriver as uc
from nodriver import cdp
from config.proxy_manager import proxy_mgr
from config.settings import DESKTOP_USER_AGENT
from core.browser import SURGICAL_BLOCKED_URLS

sys.stdout.reconfigure(encoding='utf-8')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "live_production_profile")
os.makedirs(DATA_DIR, exist_ok=True)

async def run_live_search(keyword: str, target_id: str = "", max_pages: int = 3):
    print("=" * 85)
    print("  [네이버 쇼핑 순수 오가닉 실시간 순위 조회 (실전 프로덕션 모드)]")
    print(f"  - 검색 키워드 : '{keyword}'")
    print(f"  - 타겟 상품 ID: '{target_id}' (발견 시 즉시 반환)")
    print(f"  - 실행 모드   : 화면 표시 리얼 브라우저 (headless=False) + 트래픽 95% 절감")
    
    # 1. Random Proxy Selection from dedicated pool (115.21.112.42:10016~10020)
    current_proxy = proxy_mgr.get_next_proxy(random_choice=True)
    if current_proxy:
        print(f"  - 프록시 연결 : {current_proxy} (115.21.112.42:10016~10020 풀 랜덤 회전)")
    else:
        print("  - 프록시 연결 : 로컬 다이렉트")
    print("=" * 85)

    browser_args = [
        "--window-size=1280,850",
        "--window-position=60,60",
        f"--user-agent={DESKTOP_USER_AGENT}",
        "--disable-background-networking",
        "--disable-component-update",
        "--no-first-run",
        "--no-default-browser-check"
    ]

    if current_proxy:
        clean_proxy = current_proxy.replace("socks5h://", "socks5://")
        browser_args.append(f"--proxy-server={clean_proxy}")

    t0 = time.time()

    browser = await uc.start(
        browser_executable_path=CHROME_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=browser_args
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.3)

    # Apply 95% traffic surgical blocking
    await tab.send(cdp.network.enable())
    await tab.send(cdp.network.set_blocked_ur_ls(urls=SURGICAL_BLOCKED_URLS))

    try:
        # Step 1: Search Gateway
        q_enc = urllib.parse.quote(keyword)
        search_url = f"https://search.naver.com/search.naver?where=nexearch&query={q_enc}"
        print(f"\n1. 통합검색 진입 중: {search_url}")
        await tab.get(search_url)
        await tab.sleep(2.0)

        # Step 2: Click '네이버 가격비교 더보기'
        print("2. '네이버 가격비교 더보기' 클릭...")
        btn_clicked = await tab.evaluate("""
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
                    return true;
                }
                return false;
            })()
        """)

        await tab.sleep(2.5)

        tabs = browser.tabs
        active_tab = tabs[-1] if len(tabs) > 1 else tab

        curr_url = await active_tab.evaluate("window.location.href")
        page_title = await active_tab.evaluate("document.title")
        print(f"3. 쇼핑 전문관 도착: '{page_title}'")
        print(f"   로그인 여부: {'❌ 로그인 차단' if 'nidlogin' in curr_url else '★ 200 OK 무통과'}")

        # Step 3: Extract Page 1 from __NEXT_DATA__
        all_products = []
        seen_ids = set()
        target_found = False
        target_prod = None

        next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
        if next_data_str:
            d = json.loads(next_data_str)
            pp = d.get('props', {}).get('pageProps', {})
            comp_list = pp.get('compositeList', {}).get('list', []) or pp.get('compositeProducts', {}).get('list', [])
            
            for item in comp_list:
                it = item.get('item', item)
                if bool(it.get('ad') or it.get('adId') or 'AD' in str(it.get('cardType', ''))):
                    continue
                iid = str(it.get('id') or it.get('nvMid') or '')
                t = it.get('productTitle') or it.get('productName') or ''
                m = it.get('mallName') or it.get('channelName') or ''
                p = int(it.get('lowPrice') or it.get('price') or 0)
                ch_id = str(it.get('channelProductId') or '')

                key = iid or t
                if key not in seen_ids:
                    seen_ids.add(key)
                    record = {
                        "rank": len(all_products) + 1,
                        "page": 1,
                        "nvMid": iid,
                        "title": t,
                        "mall": m,
                        "price": p
                    }
                    all_products.append(record)

                    if target_id and (target_id in [iid, ch_id] or target_id in t):
                        target_found = True
                        target_prod = record
                        break

        print(f"4. [1페이지] {len(all_products)}개 상품 추출 완료")

        # Step 4: Multi-Page Pagination (if target not found and max_pages > 1)
        if not target_found and max_pages > 1:
            for p_num in range(2, max_pages + 1):
                for _ in range(3):
                    await active_tab.evaluate("window.scrollBy({ top: 1500, behavior: 'smooth' });")
                    await active_tab.sleep(0.3)

                clicked = await active_tab.evaluate(f"""
                    (() => {{
                        const allLinks = Array.from(document.querySelectorAll('a'));
                        const pBtn = allLinks.find(a => 
                            a.textContent.trim() === '{p_num}' || 
                            a.getAttribute('data-shp-contents-id') === '{p_num}'
                        );
                        if (pBtn) {{
                            pBtn.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            pBtn.click();
                            return true;
                        }}
                        return false;
                    }})()
                """)

                if not clicked:
                    break

                await active_tab.sleep(2.5)

                dom_str = await active_tab.evaluate("""
                    JSON.stringify((() => {
                        const items = document.querySelectorAll('div[class*="product_item"], div[class*="basicList_item"], div[class*="product_list_item"], div[id^="_sr_lst_"]');
                        const list = [];
                        for (const node of items) {
                            if (node.className.includes('adProduct') || node.className.includes('ad_') || node.querySelector('[class*="ad_badge"], [class*="adTag"]') !== null) continue;
                            const idAttr = node.id || '';
                            let nvMid = idAttr.startsWith('_sr_lst_') ? idAttr.replace('_sr_lst_', '').trim() : '';
                            const titleEl = node.querySelector('a[class*="product_title"], a[class*="product_link"], a[class*="basicList_link"], a[title]');
                            const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
                            if (!title) continue;
                            const priceEl = node.querySelector('[class*="price_num"], [class*="price"] strong, [class*="price"]');
                            const price = priceEl ? parseInt(priceEl.textContent.replace(/[^0-9]/g, ''), 10) || 0 : 0;
                            const mallEl = node.querySelector('a[class*="product_mall"], a[class*="mall"], [class*="mall_name"]');
                            const mall = mallEl ? mallEl.textContent.trim() : '';
                            list.push({ nvMid, title, mall, price });
                        }
                        return list;
                    })())
                """)

                if dom_str:
                    dom_items = json.loads(dom_str)
                    for it in dom_items:
                        key = it['nvMid'] or it['title']
                        if key not in seen_ids:
                            seen_ids.add(key)
                            record = {
                                "rank": len(all_products) + 1,
                                "page": p_num,
                                "nvMid": it['nvMid'],
                                "title": it['title'],
                                "mall": it['mall'],
                                "price": it['price']
                            }
                            all_products.append(record)

                            if target_id and (target_id in [it['nvMid']] or target_id in it['title']):
                                target_found = True
                                target_prod = record
                                break

                    print(f"   -> [{p_num}페이지] 누적 {len(all_products)}개 상품 확보")

                if target_found:
                    break

        elapsed = time.time() - t0
        print("\n" + "=" * 85)
        print(f"  ★ [조회 결과 완료] 총 소요시간: {elapsed:.2f}초 (수집된 상품: {len(all_products)}개)")
        print("=" * 85)

        if target_id:
            if target_found:
                print(f"  ★ 타겟 발견 성공! -> [ {target_prod['rank']}위 ] (페이지: {target_prod['page']}P)")
                print(f"  - 상품명 : {target_prod['title']}")
                print(f"  - 쇼핑몰 : {target_prod['mall']}")
                print(f"  - 가  격 : {target_prod['price']:,}원")
                print(f"  - nvMid  : {target_prod['nvMid']}")
            else:
                print(f"  ❌ 타겟 미발견: {target_id} (수집 범위 내 없음)")
        else:
            print("[상위 5개 순수 오가닉 상품 랭킹]")
            for it in all_products[:5]:
                print(f"  #{it['rank']:02d} (P{it['page']}) | {it['title'][:32]:<32} | {it['mall']:<10} | {it['price']:,}원 | nvMid: {it['nvMid']}")

    finally:
        browser.stop()

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "스마트폰"
    tg = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        uc.loop().run_until_complete(run_live_search(kw, tg))
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
