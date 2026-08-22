import re
from typing import Dict, List, Any


def clean_place_title(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", str(text))
    return clean.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


def parse_mobile_place_items(html_text: str, start_rank: int = 1) -> List[Dict[str, Any]]:
    """
    Parses organic place/maps listings from Naver Search HTML or API state.
    """
    places = []
    # Match data-cid / data-id or place links: https://m.place.naver.com/restaurant/12345678 or /place/12345678
    pattern = r'href=[\'"]https://m\.place\.naver\.com/(?:restaurant|place|hospital|hairshop|accommodation)/(\d+)[^\'"]*[\'"]'
    matches = re.findall(pattern, html_text)
    
    seen_ids = set()
    current_rank = start_rank

    for place_id in matches:
        if place_id in seen_ids:
            continue
        seen_ids.add(place_id)

        places.append({
            "rank": current_rank,
            "id": place_id,
            "placeId": place_id,
            "url": f"https://m.place.naver.com/place/{place_id}",
        })
        current_rank += 1

    return places
