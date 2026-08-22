"""
Naver ackey (Autocomplete Key) Analysis and Generator

[Analysis of Naver's ackey]
-------------------------------------------------------------------------------
1. Origin:
   Naver main search script (e.g. https://pm.pstatic.net/resources/js/search.*.js)
   Initializes an autocomplete session store with:
       acKey: Math.random().toString(36).substr(2, 8)
   
2. Role & Purpose:
   - Unique session / interaction identifier generated upon page initialization.
   - Appended to search form as a hidden input:
       o.$form.append('<input type="hidden" name="ackey" value="' + o.store.get("acKey") + '" />')
   - Transmitted in autocomplete AJAX requests (`https://ac.search.naver.com/...&ackey=...`)
     and included in final search submission URL:
       https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query=...&ackey=...
   - Used for search log correlation (nlog / analytics) and bot pattern heuristics.

3. Algorithm:
   - `Math.random()` -> Generates floating point in [0, 1)
   - `.toString(36)`  -> Converts to base 36 representation ('0'-'9', 'a'-'z')
   - `.substr(2, 8)`  -> Extracts 8 characters following "0."
   Resulting string format: 8 lowercase alphanumeric characters [0-9a-z]{8}
-------------------------------------------------------------------------------
"""

import random
import string
import urllib.parse
from typing import Dict, Optional


def generate_ackey() -> str:
    """
    Generates an 8-character base-36 random string identical to Naver's
    JavaScript `Math.random().toString(36).substr(2, 8)`.
    """
    chars = string.digits + string.ascii_lowercase
    return "".join(random.choices(chars, k=8))


def build_naver_search_url(
    query: str,
    ackey: Optional[str] = None,
    where: str = "nexearch",
    sm: str = "top_hty",
    fbm: int = 0,
    ie: str = "utf8",
    extra_params: Optional[Dict[str, str]] = None,
) -> str:
    """
    Constructs a complete Naver Integrated Search URL matching Naver's form submission.

    Example URL:
    https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query=%EB%85%B8%ED%8A%B8%EB%B6%81&ackey=9a68qvto
    """
    if ackey is None:
        ackey = generate_ackey()

    params = {
        "where": where,
        "sm": sm,
        "fbm": str(fbm),
        "ie": ie,
        "query": query,
        "ackey": ackey,
    }

    if extra_params:
        params.update(extra_params)

    base_url = "https://search.naver.com/search.naver"
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"


def parse_naver_search_url(url: str) -> Dict[str, str]:
    """
    Parses a Naver search URL and returns a dictionary of query parameters.
    """
    parsed = urllib.parse.urlparse(url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    # Flatten single value lists
    return {k: v[0] if len(v) == 1 else v for k, v in query_dict.items()}
