"""
Rank Reporter module for exporting pure non-ad (organic) product rankings into JSON, CSV, and Text formats.
Filters out all advertisement items.
"""

import csv
import json
import os
from datetime import datetime
from typing import Dict, Any, List

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def export_rank_report(
    keyword: str,
    all_products: List[Dict[str, Any]],
    search_meta: Dict[str, Any],
    stopped_due_to_418: bool = False,
    total_pages_reached: int = 1,
    reached_end_of_results: bool = False
) -> Dict[str, str]:
    """
    Exports a clean and concise ranking report containing ONLY pure non-ad (organic) products.
    """
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_kw = keyword.replace(" ", "_")

    # Strictly filter out any ads and re-calculate continuous organic rank
    pure_organic_products = []
    current_rank = 1
    for p in all_products:
        if not p.get("isAd"):
            p_copy = dict(p)
            p_copy["rank"] = current_rank
            pure_organic_products.append(p_copy)
            current_rank += 1

    report_payload = {
        "searchKeyword": keyword,
        "createdAt": timestamp_str,
        "totalPagesScraped": total_pages_reached,
        "totalPureOrganicProducts": len(pure_organic_products),
        "stoppedDueTo418": stopped_due_to_418,
        "reachedEndOfResults": reached_end_of_results,
        "totalSearchResults": search_meta.get("totalSearchResults", 0),
        "directSearchUrl": search_meta.get("directSearchUrl", ""),
        "shoppingUrl": search_meta.get("shoppingUrl", ""),
        "products": pure_organic_products
    }

    # 1. JSON Report
    json_filename = f"rank_report_{safe_kw}.json"
    json_path = os.path.join(OUTPUT_DIR, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)

    # 2. CSV Report (Excel-compatible UTF-8 with BOM)
    csv_filename = f"rank_report_{safe_kw}.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "순수순위", "페이지", "페이지내순위", "상품명", "가격(원)",
            "판매처(몰명)", "상품ID(MID)", "리뷰수", "평점", "카테고리", "상품링크"
        ])
        for p in pure_organic_products:
            writer.writerow([
                p.get("rank", ""),
                p.get("page", ""),
                p.get("pageRank", ""),
                p.get("productTitle", ""),
                p.get("price", ""),
                p.get("mallName", ""),
                p.get("id", "") or p.get("nvMid", ""),
                p.get("reviewCount", ""),
                p.get("score", ""),
                f"{p.get('category1', '')}>{p.get('category2', '')}>{p.get('category3', '')}",
                p.get("crUrl", "") or p.get("link", "")
            ])

    # 3. TXT Human-readable Table Report
    txt_filename = f"rank_report_{safe_kw}.txt"
    txt_path = os.path.join(OUTPUT_DIR, txt_filename)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 105 + "\n")
        f.write(f" [네이버 쇼핑 순수 비광고 상품 순위 리포트] 키워드: '{keyword}'\n")
        f.write(f" 생성일시: {timestamp_str} | 수집 페이지: 1 ~ {total_pages_reached}페이지 | 총 순수 상품: {len(pure_organic_products)}개 (광고 100% 제외)\n")
        if stopped_due_to_418:
            f.write(" ※ [주의] 418 차단 응답이 감지되어 추가 페이지 이동이 즉시 안전하게 중단되었습니다.\n")
        elif reached_end_of_results:
            f.write(" ※ [안내] 검색 결과의 마지막 페이지에 도달하여 '다음' 버튼이 없어 크롤링을 정상 완료했습니다.\n")
        f.write("=" * 105 + "\n")
        f.write(f"{'순수순위':<6} | {'페이지':<6} | {'페이지내':<6} | {'가격(원)':<12} | {'몰명':<16} | {'상품명'}\n")
        f.write("-" * 105 + "\n")

        for p in pure_organic_products:
            price_val = p.get("price")
            price_formatted = f"{int(price_val):,}원" if price_val and str(price_val).isdigit() else str(price_val or "")
            mall_str = (p.get("mallName") or "N/A")[:15]
            title_str = (p.get("productTitle") or "N/A")[:50]
            page_val = p.get('page') or 1
            page_rank_val = p.get('pageRank') or p.get('rank') or 1
            f.write(f"#{p.get('rank'):<5} | P.{page_val:<4} | #{page_rank_val:<5} | {price_formatted:<12} | {mall_str:<16} | {title_str}\n")

        f.write("=" * 105 + "\n")

    return {
        "json": json_path,
        "csv": csv_path,
        "txt": txt_path,
        "totalPureCount": len(pure_organic_products)
    }
