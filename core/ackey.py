import math
import random
import time
from urllib.parse import urlparse, parse_qs


def generate_ackey() -> str:
    """Generates synthetic 8-char base36 ackey token matching Naver natural search."""
    def to_base36(num: int) -> str:
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        if num == 0:
            return "0"
        res = []
        while num > 0:
            res.append(chars[num % 36])
            num //= 36
        return "".join(reversed(res))

    rand_int = math.floor(random.random() * (36 ** 8))
    ackey_val = to_base36(rand_int).zfill(8)
    return ackey_val


def parse_naver_search_url(url: str) -> dict:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return {k: v[0] if len(v) == 1 else v for k, v in qs.items()}
