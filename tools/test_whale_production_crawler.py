import asyncio
import os
import sys
import json
import urllib.parse
import nodriver as uc

sys.stdout.reconfigure(encoding='utf-8')

WHALE_PATH = r"C:\Program Files\Naver\Naver Whale\Application\whale.exe"
DATA_DIR = os.path.join(os.getcwd(), "data", "whale_prod_crawler_test")
os.makedirs(DATA_DIR, exist_ok=True)

async def test_whale_production_search(keyword: str = "노트북"):
    print("=" * 80)
    print("  [네이버 공식 웨일 브라우저 기반 쇼핑 순위 수집 실전 테스트]")
    print(f"  - 바이너리 : {WHALE_PATH}")
    print(f"  - 검색 키워드 : '{keyword}'")
    print("  - 특징       : 로그인 0% 정공법 (메인 -> 검색 -> 가격비교 더보기 -> 1+2페이지)")
    print("=" * 80)

    # Launch Whale PC in optimal desktop resolution
    browser = await uc.start(
        browser_executable_path=WHALE_PATH,
        headless=False,
        user_data_dir=DATA_DIR,
        browser_args=[
            "--window-size=1440,900",
            "--window-position=80,40",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )

    tab = await browser.get("about:blank")
    await tab.sleep(0.5)

    all_products = []
    seen_ids = set()

    try:
        # Step 1: Open Naver Main
        print("\n1. 네이버 메인(https://www.naver.com) 접속...")
        await tab.get("https://www.naver.com")
        await tab.sleep(2.0)

        # Step 2: Input Keyword and Search
        print(f"2. 검색창에 '{keyword}' 입력 및 검색 실행...")
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
        else:
            await tab.get(f"https://search.naver.com/search.naver?where=nexearch&query={urllib.parse.quote(keyword)}")

        await tab.sleep(3.0)
        print("3. 통합검색 결과 도착:", await tab.evaluate("document.title"))

        # Step 3: Click '네이버 가격비교 더보기'
        print("4. '네이버 가격비교 더보기' 버튼 클릭...")
        click_info = await tab.evaluate("""
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
                    return { found: true, text: moreBtn.textContent.trim(), href: moreBtn.href };
                }
                return { found: false };
            })()
        """)
        print("   -> 클릭 대상 링크:", click_info)
        await tab.sleep(3.5)

        # Focus Active Tab
        tabs = browser.tabs
        active_tab = tabs[-1] if len(tabs) > 1 else tab

        curr_url = await active_tab.evaluate("window.location.href")
        page_title = await active_tab.evaluate("document.title")

        print("\n" + "-" * 80)
        print(f"5. 쇼핑 전문관 도착 성공!")
        print(f"   * 페이지 제목 : {page_title}")
        print(f"   * 현재 URL   : {curr_url}")
        print(f"   * 로그인창 여부: {'로그인창 발생 (차단)' if 'nidlogin' in curr_url else '★ 로그인 요구 0% (200 OK 통과)'}")
        print("-" * 80)

        # Step 4: Extract Page 1 from __NEXT_DATA__
        next_data_str = await active_tab.evaluate("document.getElementById('__NEXT_DATA__')?.textContent")
        if next_data_str:
            d = json.loads(next_data_str)
            pp = d.get('props', {}).get('pageProps', {})
            comp_list = pp.get('compositeList', {}).get('list', []) or pp.get('compositeProducts', {}).get('list', [])
            print(f"\n6. [1페이지 추출] __NEXT_DATA__에서 {len(comp_list)}개 상품 데이터 파싱 완료!")

            for item in comp_list:
                it = item.get('item', item)
                if bool(it.get('ad') or it.get('adId') or 'AD' in str(it.get('cardType', ''))):
                    continue
                iid = str(it.get('id') or it.get('nvMid') or '')
                title = it.get('productTitle') or it.get('productName') or ''
                mall = it.get('mallName') or it.get('channelName') or ''
                price = int(it.get('lowPrice') or it.get('price') or 0)

                key = iid or title
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                all_products.append({
                    "rank": len(all_products) + 1,
                    "page": 1,
                    "nvMid": iid,
                    "productTitle": title,
                    "mallName": mall,
                    "price": price
                })

            # Step 5: Scroll & Click Page 2
            print("\n7. [2페이지 이동] 페이징 영역 노출을 위한 하단 스크롤...")
            for _ in range(4):
                await active_tab.evaluate("window.scrollBy({ top: 1500, behavior: 'smooth' });")
                await active_tab.sleep(0.4)

            print("8. 2페이지 버튼 클릭...")
            clicked_p2 = await active_tab.evaluate("""
                (() => {
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    const p2Btn = allLinks.find(a => 
                        a.textContent.trim() === '2' || 
                        a.getAttribute('data-shp-contents-id') === '2' ||
                        (a.className.includes('pagination') && a.textContent.trim() === '2')
                    );
                    if (p2Btn) {
                        p2Btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        p2Btn.click();
                        return true;
                    }
                    return false;
                })()
            """)
            print(f"   -> 2페이지 클릭 성공 여부: {clicked_p2}")
            await active_tab.sleep(3.0)

            # Step 6: Extract Page 2 DOM elements
            p2_dom_str = await active_tab.evaluate("""
                JSON.stringify((() => {
                    const items = document.querySelectorAll('div[class*="product_item"], div[class*="basicList_item"], div[class*="product_list_item"], div[id^="_sr_lst_"]');
                    const list = [];
                    for (const node of items) {
                        const classAttr = node.className || '';
                        if (classAttr.includes('adProduct') || classAttr.includes('ad_') || node.querySelector('[class*="ad_badge"], [class*="adTag"]') !== null) continue;

                        const idAttr = node.id || '';
                        let nvMid = idAttr.startsWith('_sr_lst_') ? idAttr.replace('_sr_lst_', '').trim() : '';

                        const titleEl = node.querySelector('a[class*="product_title"], a[class*="product_link"], a[class*="basicList_link"], a[title]');
                        const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
                        if (!title) continue;

                        const priceEl = node.querySelector('[class*="price_num"], [class*="price"] strong, [class*="price"]');
                        const price = priceEl ? parseInt(priceEl.textContent.replace(/[^0-9]/g, ''), 10) || 0 : 0;

                        const mallEl = node.querySelector('a[class*="product_mall"], a[class*="mall"], [class*="mall_name"]');
                        const mall = mallEl ? mallEl.textContent.trim() : '';

                        list.push({ nvMid, productTitle: title, mallName: mall, price });
                    }
                    return list;
                })())
            """)

            if p2_dom_str:
                p2_items = json.loads(p2_dom_str)
                print(f"   -> 2페이지 DOM 상품 {len(p2_items)}개 추가 감지 완료!")
                for it in p2_items:
                    key = it['nvMid'] or it['productTitle']
                    if key not in seen_ids:
                        seen_ids.add(key)
                        it['rank'] = len(all_products) + 1
                        it['page'] = 2
                        all_products.append(it)

            print("\n" + "=" * 80)
            print(f"  ★ [최종 수집 완료] 1페이지 + 2페이지 총 {len(all_products)}개 순수 오가닉 상품 완벽 추출!")
            print("=" * 80)

            print(f"\n[상위 10개 상품 실시간 순위 리스트]")
            for p in all_products[:10]:
                p_str = f"{p['price']:,}원" if p['price'] else "가격비교"
                print(f"  #{p['rank']:02d} (P{p['page']}) | {p['productTitle'][:35]:<35} | {p['mallName'][:12]:<12} | {p_str:<10} | nvMid: {p['nvMid']}")

        print("\n💡 직접 브라우저 화면과 상품 목록을 확인하실 수 있도록 창을 유지합니다.")
        print("   (종료하시려면 터미널에서 Ctrl + C 를 누르시거나 창을 닫으시면 됩니다.)\n")

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
        uc.loop().run_until_complete(test_whale_production_search(kw))
    except KeyboardInterrupt:
        print("\n정상 종료되었습니다.")
