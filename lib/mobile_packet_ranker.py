"""
Optimized Mobile Naver Shopping Crawler & Target Rank Finder.

Endpoints:
1. Page 1: https://m.search.naver.com/search.naver?where=m_shopping&query={keyword}
2. Page 2+: https://ns-portal.shopping.naver.com/api/v2/shopping-paged-slot?query={keyword}&page={page}&pageSize={pageSize}

Features:
- Pure HTTP Packet Execution via curl_cffi (impersonate='chrome120').
- Extracts 100% Pure Organic products (filters AD, SUPER_POINT, etc.).
- Sequential overall ranking tracking across Page 1 ~ Page N (up to rank 400+).
- Target ID matching against nvMid, channelProductId, originalMallProductId.
- Robust JSON extraction with title sanitization and rich metadata.
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
from typing import Dict, Any, List, Optional, Set, Tuple, Union

from curl_cffi import requests as cffi_requests
from lib.logger import get_logger

logger = get_logger("nshop.mobile_ranker")

DEFAULT_MOBILE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "user-agent": "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://m.search.naver.com/",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


def clean_product_title(text: Optional[str]) -> str:
    """Sanitizes product titles by stripping HTML tags, entities, and normalizing whitespace."""
    if not text:
        return ""
    try:
        text = json.loads(f'"{text}"')
    except Exception:
        text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'(?i)</?mark>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_products_from_mobile_html(html_content: str, start_rank: int = 1) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extracts organic products from m.search.naver.com HTML (_INITIAL_STATE and fallback card blocks).
    """
    products: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    current_rank = start_rank

    # Method 1: Extract from _INITIAL_STATE JSON object
    match = re.search(
        r'naver\.search\.ext\.newshopping\[\"shopping\"\]\._INITIAL_STATE\s*=\s*({.+?})\s*(?:;\s*naver|<\/script>)',
        html_content,
        re.DOTALL
    )
    if match:
        raw = match.group(1).replace('undefined', 'null')
        raw = re.sub(r'new Date\([^)]*\)', '""', raw)
        
        # Fast balanced bracket parser
        depth = 0
        end_pos = 0
        for idx, ch in enumerate(raw):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_pos = idx + 1
                    break
        
        if end_pos > 0:
            try:
                state = json.loads(raw[:end_pos])
                paged_slots = state.get('initProps', {}).get('pagedSlot', [])
                for ps in paged_slots:
                    for s in ps.get('slots', []):
                        d = s.get('data', {})
                        name = clean_product_title(d.get('productName') or d.get('productTitle') or '')
                        if not name:
                            continue

                        nv_mid = str(d.get('nvMid') or d.get('id') or '').strip()
                        ch_id = str(d.get('channelProductId') or '').strip()
                        orig_id = str(d.get('originalMallProductId') or '').strip()
                        mall = d.get('mallName') or d.get('channelName') or 'N/A'
                        card_type = str(d.get('cardType') or '').upper()
                        source_type = str(d.get('sourceType') or '').upper()

                        is_ad = ('AD' in card_type) or ('AD' in source_type) or ('SUPER_POINT' in card_type) or ('SUPER_POINT' in source_type)
                        
                        if not is_ad and nv_mid and nv_mid not in seen_ids:
                            seen_ids.add(nv_mid)
                            all_ids = list(filter(None, [nv_mid, ch_id, orig_id]))
                            price = d.get('discountedSalePrice') or d.get('salePrice') or d.get('lowPrice') or d.get('price')
                            rev_cnt = d.get('totalReviewCount') or d.get('reviewCount') or 0
                            score = d.get('averageReviewScore')

                            products.append({
                                'rank': current_rank,
                                'page': 1,
                                'pageRank': current_rank,
                                'id': nv_mid,
                                'nvMid': nv_mid,
                                'channelProductId': ch_id,
                                'originalMallProductId': orig_id,
                                'allIds': all_ids,
                                'mallProductId': orig_id or ch_id or nv_mid,
                                'productTitle': name,
                                'brand': d.get('brandName') or '',
                                'mallName': mall,
                                'price': price,
                                'lowPrice': price,
                                'reviewCount': int(rev_cnt) if rev_cnt else 0,
                                'scoreInfo': float(score) if score else None,
                                'imageUrl': d.get('imageUrl') or d.get('productImageUrl') or '',
                                'productUrl': d.get('crUrl') or '',
                            })
                            current_rank += 1
            except Exception as e:
                logger.debug(f"Error parsing _INITIAL_STATE: {e}")

    # Method 2: Fallback regex card blocks in HTML
    card_starts = [m.start() for m in re.finditer(r'\"cardType\":\"([^\"]+)\"', html_content)]
    if card_starts:
        card_starts.append(len(html_content))
        for i in range(len(card_starts) - 1):
            block = html_content[card_starts[i]:card_starts[i+1]]

            card_type_m = re.search(r'\"cardType\":\"([^\"]+)\"', block)
            card_type = card_type_m.group(1).upper() if card_type_m else ''
            source_type_m = re.search(r'\"sourceType\":\"([^\"]+)\"', block)
            source_type = source_type_m.group(1).upper() if source_type_m else ''
            is_ad = 'AD' in card_type or 'SUPER_POINT' in card_type or source_type in ('AD', 'SUPER_POINT')

            nv_mid_m = re.search(r'\"nvMid\":(\d+)', block)
            if not nv_mid_m:
                continue
            nv_mid = nv_mid_m.group(1)

            if not is_ad and nv_mid not in seen_ids:
                seen_ids.add(nv_mid)
                ch_m = re.search(r'\"channelProductId\":\"?(\d+)\"?', block)
                ch_pid = ch_m.group(1) if ch_m else ""
                orig_m = re.search(r'\"originalMallProductId\":\"?(\d+)\"?', block)
                orig_pid = orig_m.group(1) if orig_m else ""

                name_m = re.search(r'\"productName\":\"([^\"]+)\"', block)
                clean_name = clean_product_title(name_m.group(1)) if name_m else ""
                if not clean_name:
                    continue

                rev_m = re.search(r'\"totalReviewCount\":(\d+)', block)
                review_count = int(rev_m.group(1)) if rev_m else 0
                score_m = re.search(r'\"averageReviewScore\":([0-9.]+)', block)
                score_info = float(score_m.group(1)) if score_m else None
                mall_m = re.search(r'\"mallName\":\"([^\"]+)\"', block)
                mall_name = mall_m.group(1) if mall_m else ""
                img_m = re.search(r'\"imageUrl\":\"([^\"]+)\"', block)
                image_url = img_m.group(1).replace(r'\u002F', '/') if img_m else ""
                price_m = re.search(r'\"(?:discountedSalePrice|salePrice|lowPrice|price)\":(\d+)', block)
                price = int(price_m.group(1)) if price_m else None

                all_ids = list(filter(None, [nv_mid, ch_pid, orig_pid]))
                products.append({
                    'rank': current_rank,
                    'page': 1,
                    'pageRank': current_rank,
                    'id': nv_mid,
                    'nvMid': nv_mid,
                    'channelProductId': ch_pid,
                    'originalMallProductId': orig_pid,
                    'allIds': all_ids,
                    'mallProductId': orig_pid or ch_pid or nv_mid,
                    'productTitle': clean_name,
                    'brand': '',
                    'mallName': mall_name,
                    'price': price,
                    'lowPrice': price,
                    'reviewCount': review_count,
                    'scoreInfo': score_info,
                    'imageUrl': image_url,
                    'productUrl': '',
                })
                current_rank += 1

    return products, current_rank


def crawl_mobile_shopping_ranks(
    keyword: str,
    target_id: Optional[Union[str, int, List[Union[str, int]], Set[str]]] = None,
    max_pages: int = 10,
    page_size: int = 10,
    timeout: float = 6.0,
    session: Optional[cffi_requests.Session] = None
) -> Dict[str, Any]:
    """
    Crawls Mobile Naver Shopping ranks using fast pure HTTP packet requests.
    
    Returns:
      {
        'status': 'SUCCESS' | 'BLOCKED' | 'NOT_FOUND',
        'keyword': keyword,
        'targetRank': rank (if target_id found),
        'targetProduct': product dict (if target_id found),
        'totalExtracted': count,
        'pagesScraped': count,
        'products': list of all extracted organic products
      }
    """
    start_time = time.time()
    if session is None:
        session = cffi_requests.Session(impersonate="chrome120")

    # Format target_ids set
    target_ids: Set[str] = set()
    if target_id:
        if isinstance(target_id, (list, tuple, set)):
            target_ids = {str(x).strip() for x in target_id if str(x).strip() not in ('', '0', 'None')}
        else:
            target_ids = {str(x).strip() for x in str(target_id).split(',') if str(x).strip() not in ('', '0', 'None')}

    all_products: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    current_rank = 1
    found_target_product = None

    logger.info(f"Starting Mobile Shopping Rank Crawler | Keyword='{keyword}', MaxPages={max_pages}, Targets={target_ids or 'ALL'}")

    # -------------------------------------------------------------------------
    # STEP 1: Page 1 via m.search.naver.com
    # -------------------------------------------------------------------------
    url_p1 = f"https://m.search.naver.com/search.naver?where=m_shopping&query={urllib.parse.quote(keyword)}"
    try:
        r1 = session.get(url_p1, headers=DEFAULT_MOBILE_HEADERS, timeout=timeout)
        if r1.status_code != 200:
            logger.error(f"Page 1 request failed with HTTP {r1.status_code}")
            return {
                'status': 'BLOCKED' if r1.status_code == 418 else 'ERROR',
                'keyword': keyword,
                'targetRank': None,
                'targetProduct': None,
                'totalExtracted': 0,
                'pagesScraped': 0,
                'products': []
            }

        p1_products, current_rank = extract_products_from_mobile_html(r1.text, start_rank=current_rank)
        for p in p1_products:
            seen_ids.add(p['id'])
            all_products.append(p)
            
            if target_ids and not found_target_product:
                p_id_set = set(p.get('allIds', []) + [p['id'], p.get('mallProductId')])
                if target_ids.intersection(p_id_set):
                    found_target_product = p

        logger.info(f"Page 1 Extracted: {len(p1_products)} organic products (Current Rank: #{current_rank - 1})")
        if found_target_product:
            logger.info(f"Target product FOUND on Page 1 at Rank #{found_target_product['rank']}!")
            return {
                'status': 'SUCCESS',
                'keyword': keyword,
                'targetCode': target_id,
                'targetFound': True,
                'targetRank': found_target_product['rank'],
                'targetProduct': found_target_product,
                'totalExtracted': len(all_products),
                'totalPagesReached': 1,
                'products': all_products
            }

    except Exception as e:
        logger.error(f"Error requesting Page 1: {e}")
        return {'status': 'ERROR', 'error': str(e), 'keyword': keyword, 'products': []}

    # -------------------------------------------------------------------------
    # STEP 2: Page 2+ via ns-portal.shopping.naver.com/api/v2/shopping-paged-slot
    # -------------------------------------------------------------------------
    url_api = "https://ns-portal.shopping.naver.com/api/v2/shopping-paged-slot"
    pages_scraped = 1
    consecutive_empty_batches = 0

    # Loop up to max_pages * 4 (since each slot batch has 10 items)
    max_api_batches = max_pages * 4
    for page_idx in range(1, max_api_batches + 1):
        try:
            r_api = session.get(
                url_api,
                params={"query": keyword, "page": page_idx, "pageSize": page_size},
                headers=API_HEADERS,
                timeout=timeout
            )
            if r_api.status_code != 200:
                if r_api.status_code in (418, 403):
                    break
                continue

            data = r_api.json().get("data", [])
            if not data:
                break

            items_added_this_page = 0
            for ps in data:
                for s in ps.get("slots", []):
                    d = s.get("data", {})
                    name = clean_product_title(d.get("productName") or d.get("productTitle") or "")
                    if not name:
                        continue

                    nv_mid = str(d.get("nvMid") or d.get("id") or "").strip()
                    ch_id = str(d.get("channelProductId") or "").strip()
                    orig_id = str(d.get("originalMallProductId") or "").strip()
                    mall = d.get("mallName") or d.get("channelName") or "N/A"
                    card_type = str(d.get("cardType") or "").upper()
                    source_type = str(d.get("sourceType") or "").upper()

                    is_ad = ('AD' in card_type) or ('AD' in source_type) or ('SUPER_POINT' in card_type) or ('SUPER_POINT' in source_type)

                    if not is_ad and nv_mid and nv_mid not in seen_ids:
                        seen_ids.add(nv_mid)
                        all_ids = list(filter(None, [nv_mid, ch_id, orig_id]))
                        price = d.get("discountedSalePrice") or d.get("salePrice") or d.get("lowPrice") or d.get("price")
                        rev_cnt = d.get("totalReviewCount") or d.get("reviewCount") or 0
                        score = d.get("averageReviewScore")

                        estimated_page = (current_rank - 1) // 40 + 1
                        page_rank = (current_rank - 1) % 40 + 1
                        prod = {
                            "rank": current_rank,
                            "page": estimated_page,
                            "pageRank": page_rank,
                            "id": nv_mid,
                            "nvMid": nv_mid,
                            "channelProductId": ch_id,
                            "originalMallProductId": orig_id,
                            "allIds": all_ids,
                            "mallProductId": orig_id or ch_id or nv_mid,
                            "productTitle": name,
                            "brand": d.get("brandName") or "",
                            "mallName": mall,
                            "price": price,
                            "reviewCount": rev_cnt,
                            "score": score,
                            "isAd": False,
                            "crUrl": d.get("crUrl") or "",
                            "imageUrl": d.get("imageUrl") or d.get("productImageUrl") or ""
                        }

                        all_products.append(prod)
                        current_rank += 1
                        items_added_this_page += 1

                        if target_ids and not found_target_product:
                            p_id_set = set(all_ids + [nv_mid])
                            if target_ids.intersection(p_id_set):
                                found_target_product = prod
                                elapsed = time.time() - start_time
                                logger.info(f"Target product FOUND at Rank #{prod['rank']} (Elapsed: {elapsed:.2f}s)!")
                                return {
                                    'status': 'SUCCESS',
                                    'keyword': keyword,
                                    'targetCode': target_id,
                                    'targetFound': True,
                                    'targetRank': prod['rank'],
                                    'targetProduct': prod,
                                    'totalExtracted': len(all_products),
                                    'totalPagesReached': estimated_page,
                                    'products': all_products
                                }

            if items_added_this_page == 0:
                consecutive_empty_batches += 1
                if consecutive_empty_batches >= 4:
                    break
            else:
                consecutive_empty_batches = 0

            pages_scraped = (current_rank - 1) // 40 + 1

        except Exception as e:
            logger.debug(f"Error requesting API slot batch {page_idx}: {e}")
            continue

    elapsed = time.time() - start_time
    logger.info(f"Crawling finished in {elapsed:.2f}s | Total Organic Products: {len(all_products)} items (Rank 1 ~ {len(all_products)})")

    return {
        'status': 'SUCCESS' if not target_ids else ('NOT_FOUND' if not found_target_product else 'SUCCESS'),
        'keyword': keyword,
        'targetCode': target_id,
        'targetFound': bool(found_target_product),
        'targetRank': found_target_product['rank'] if found_target_product else None,
        'targetProduct': found_target_product,
        'totalExtracted': len(all_products),
        'totalPagesReached': pages_scraped,
        'products': all_products,
        'elapsedSec': elapsed
    }
