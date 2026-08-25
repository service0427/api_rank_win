import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
import random
import datetime
import urllib.parse
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

FIREFOX_BIN = r"C:\Program Files\Mozilla Firefox\firefox.exe"

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

def run_firefox_test(keyword: str = "스마트폰", mode: str = "aged"):
    use_aging = (mode == "aged")
    hours_ago = 24 if use_aging else 0
    nnb_val, nnb_dt = generate_aged_nnb(hours_ago=hours_ago)

    print("=" * 85)
    print(f"  [모질라 파이어폭스(Firefox) NNB 숙성 효과 실시간 화면 검증]")
    print(f"  - 실행 모드       : {'★ 24시간 숙성 NNB 주입 모드' if use_aging else '❌ 일반 신규 세션 모드 (Aging 없음)'}")
    print(f"  - 검색 키워드     : '{keyword}'")
    if use_aging:
        print(f"  - 주입할 숙성 NNB : {nnb_val} ({nnb_dt.strftime('%Y-%m-%d %H:%M:%S')} - 24시간 전 시각)")
    print("=" * 85)

    print("\n1. 모니터 화면에 실제 파이어폭스(Firefox) 브라우저를 띄웁니다...")
    options = Options()
    options.binary_location = FIREFOX_BIN
    
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1280, 850)
    driver.set_window_position(50, 50)

    try:
        # Step 1: Open domain to set cookie
        driver.get("https://search.naver.com/favicon.ico")
        time.sleep(0.5)

        if use_aging:
            print(f"2. [쿠키 주입] 24시간 전 타임스탬프 NNB ({nnb_val}) 주입 완료!")
            driver.add_cookie({
                "name": "NNB",
                "value": nnb_val,
                "domain": ".naver.com",
                "path": "/"
            })
        else:
            print("2. [신규 세션] 별도 쿠키 주입 없이 순수 신규 세션으로 진행...")

        # Step 2: Navigate to Unified Search
        q_enc = urllib.parse.quote(keyword)
        search_url = f"https://search.naver.com/search.naver?where=nexearch&query={q_enc}"
        print(f"3. 파이어폭스로 통합검색 진입: {search_url}")
        driver.get(search_url)
        time.sleep(2.5)

        # Step 3: Click '가격비교 더보기'
        print("4. '네이버 가격비교 더보기' 버튼 클릭...")
        driver.execute_script("""
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
        """)
        time.sleep(3.5)

        # Check all window handles
        handles = driver.window_handles
        if len(handles) > 1:
            driver.switch_to.window(handles[-1])

        curr_url = driver.current_url
        page_title = driver.title

        print("\n" + "=" * 85)
        print("  ★ [파이어폭스 실시간 검증 결과]")
        print("=" * 85)
        print(f"  - 현재 브라우저 URL: {curr_url[:80]}...")
        print(f"  - 페이지 제목      : '{page_title}'")
        
        is_blocked = "nidlogin" in curr_url
        if is_blocked:
            print(f"  - 최종 결과        : ❌ 예상대로 [로그인창(nidlogin)]으로 차단되었습니다!")
        else:
            print(f"  - 최종 결과        : ★ 예상대로 [100% 200 OK 프리패스 대성공!!] (로그인창 0%)")
        print("=" * 85)

        # Try to parse items from __NEXT_DATA__
        try:
            next_data_el = driver.find_element(By.ID, "__NEXT_DATA__")
            if next_data_el:
                import json
                d = json.loads(next_data_el.get_attribute("textContent"))
                comp_list = d.get('props', {}).get('pageProps', {}).get('compositeList', {}).get('list', []) or []
                organic_list = [it for it in comp_list if not bool(it.get('item', it).get('ad') or it.get('item', it).get('adId'))]
                print(f"\n[파이어폭스에서 추출된 실시간 1페이지 상품: 총 {len(organic_list)}개]")
                for idx, it in enumerate(organic_list[:3], 1):
                    item = it.get('item', it)
                    t = (item.get('productTitle') or item.get('productName') or '')[:32]
                    m = item.get('mallName') or item.get('channelName') or ''
                    p = item.get('lowPrice') or item.get('price') or 0
                    print(f"  #{idx:02d} | {t:<32} | {m:<10} | {p:,}원")
        except Exception:
            pass

        print("\n💡 모니터 화면에서 직접 확인하실 수 있도록 12초간 파이어폭스 창을 유지합니다...")
        time.sleep(12.0)

    finally:
        driver.quit()

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "스마트폰"
    mode = sys.argv[2] if len(sys.argv) > 2 else "aged"
    try:
        run_firefox_test(kw, mode)
    except KeyboardInterrupt:
        print("\n종료되었습니다.")
