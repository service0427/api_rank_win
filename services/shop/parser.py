import html
import json
import re
from typing import Dict, List, Any, Set, Optional


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


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("원", "").strip()
        return int(val)
    except Exception:
        return default


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace(",", "").strip()
        return float(val)
    except Exception:
        return default


def extract_products_from_mobile_html(html_content: str, start_rank: int = 1) -> List[Dict[str, Any]]:
    """
    Extracts pure organic non-ad products from m.search.naver.com HTML.
    Accurately classifies CATALOG (가격비교/판매처 N개) vs STORE (단일상품/스마트스토어),
    and strictly deduplicates every slot.
    """
    products: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    current_rank = start_rank

    match = re.search(
        r'naver\.search\.ext\.newshopping\[\"shopping\"\]\._INITIAL_STATE\s*=\s*({.+?})\s*(?:;\s*naver|<\/script>)',
        html_content,
        re.DOTALL
    )
    if not match:
        match = re.search(r'_INITIAL_STATE\s*:\s*(\{.+?\})\s*\}\s*;\s*\(function', html_content, re.DOTALL)

    if match:
        raw = match.group(1).replace('undefined', 'null')
        raw = re.sub(r'new Date\([^)]*\)', '""', raw)

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

                        card_type = str(d.get('cardType') or '').upper()
                        source_type = str(d.get('sourceType') or '').upper()

                        # 1. Filter out all Advertisements
                        is_ad = ('AD' in card_type) or ('AD' in source_type) or ('SUPER_POINT' in card_type) or ('SUPER_POINT' in source_type)
                        if is_ad:
                            continue

                        nv_mid = str(d.get('nvMid') or d.get('id') or '').strip()
                        ch_id = str(d.get('channelProductId') or '').strip()
                        orig_id = str(d.get('originalMallProductId') or d.get('mallProductId') or '').strip()
                        raw_mall = str(d.get('mallName') or d.get('channelName') or '').strip()
                        mall_cnt = _safe_int(d.get('mallCount') or d.get('channelCount'))

                        # 2. Strict Deduplication
                        item_key = nv_mid or ch_id or orig_id
                        if not item_key or (item_key in seen_ids):
                            continue

                        seen_ids.add(item_key)
                        if nv_mid:
                            seen_ids.add(nv_mid)
                        if ch_id:
                            seen_ids.add(ch_id)

                        # 3. Classify Product Type: CATALOG (가격비교) vs STORE (단일상품)
                        is_catalog = (mall_cnt > 1) or (card_type == 'CATALOG_CARD') or (not raw_mall and nv_mid)
                        if is_catalog:
                            prod_type = "CATALOG"
                            prod_type_name = "가격비교"
                            mall_name = f"가격비교 (판매처 {mall_cnt}개)" if mall_cnt > 0 else "가격비교"
                        else:
                            prod_type = "STORE"
                            prod_type_name = "단일상품"
                            mall_name = raw_mall or "스마트스토어"

                        price_val = _safe_int(d.get('discountedSalePrice') or d.get('salePrice') or d.get('lowPrice') or d.get('price'))
                        rev_cnt = _safe_int(d.get('totalReviewCount') or d.get('reviewCount'))
                        score_val = _safe_float(d.get('averageReviewScore') or d.get('score'))

                        products.append({
                            'rank': current_rank,
                            'productType': prod_type,
                            'productTypeName': prod_type_name,
                            'id': nv_mid or ch_id,
                            'nvMid': nv_mid,
                            'channelProductId': ch_id,
                            'originalMallProductId': orig_id,
                            'productTitle': name,
                            'mallName': mall_name,
                            'mallCount': mall_cnt,
                            'price': price_val,
                            'reviewCount': rev_cnt,
                            'score': score_val,
                            'isAd': False
                        })
                        current_rank += 1
            except Exception:
                pass

    return products
