#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver Organic Ranking Unified CLI & Daemon Entrypoint (Shop & Place).

Usage Examples:
1. Shopping Rank:
   python main.py shop --keyword "노트북" --target 52631236642
   python main.py shop --keyword "무선이어폰" --maxpage 13

2. Place Rank:
   python main.py place --keyword "강남역 맛집" --target 1047144456

3. Cron Rank Check (Auto DB Assignment Pipeline):
   python main.py check shop
   python main.py check place

4. External Slot Sync:
   python main.py sync shop
   python main.py sync place

5. Start API Server:
   python main.py api --port 8888
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.shop.runner import get_shop_rank_sync
from services.place.runner import get_place_rank_sync
from services.cron_handler import run_cron_check
from services.sync_handler import pull_slots, push_ranks


def handle_shop(args):
    result = get_shop_rank_sync(
        keyword=args.keyword,
        target_id=args.target,
        max_pages=args.maxpage,
        headless=args.headless,
        block_media=not args.no_block_media,
        proxy_url=args.proxy
    )
    print("\n" + "=" * 80)
    print("SHOP RANKING RESULT:")
    print("=" * 80)
    print(f"Status          : {result.get('status')}")
    print(f"Keyword         : '{result.get('keyword')}'")
    print(f"Engine / Stage  : {result.get('engine', result.get('stage'))}")
    print(f"isCacheHit      : {result.get('isCacheHit', False)}")
    print(f"Total Time      : {result.get('totalTime', result.get('elapsedSec', 0)):.2f}s")
    print(f"Total Extracted : {result.get('totalExtracted')} organic products")
    if result.get("proxyUsed"):
        print(f"Proxy Used      : {result.get('proxyUsed')}")

    if args.target:
        print("\n" + "★" * 50)
        print(f"Target ID       : {args.target}")
        print(f"Target Found    : {result.get('targetFound')}")
        if result.get('targetFound'):
            tp = result.get('targetProduct', {})
            print(f"Target Rank     : #{result.get('targetRank')}")
            print(f"Product Title   : {tp.get('productTitle')}")
            print(f"Mall Name       : {tp.get('mallName')}")
            print(f"Price           : {tp.get('price')}원")
            print(f"nvMid           : {tp.get('nvMid')}")
        else:
            print("Target Result   : Product not found within search boundary.")
        print("★" * 50)
    print("=" * 80)


def handle_place(args):
    result = get_place_rank_sync(
        keyword=args.keyword,
        target_id=args.target,
        max_pages=args.maxpage,
        headless=args.headless,
        block_media=not args.no_block_media,
        proxy_url=args.proxy
    )
    print("\n" + "=" * 80)
    print("PLACE RANKING RESULT:")
    print("=" * 80)
    print(f"Status          : {result.get('status')}")
    print(f"Keyword         : '{result.get('keyword')}'")
    print(f"Engine / Stage  : {result.get('engine', result.get('stage'))}")
    print(f"isCacheHit      : {result.get('isCacheHit', False)}")
    print(f"Total Time      : {result.get('totalTime', result.get('elapsedSec', 0)):.2f}s")
    print(f"Total Extracted : {result.get('totalExtracted')} places")

    if args.target:
        print("\n" + "★" * 50)
        print(f"Target Place ID : {args.target}")
        print(f"Target Found    : {result.get('targetFound')}")
        if result.get('targetFound'):
            print(f"Target Rank     : #{result.get('targetRank')}")
        print("★" * 50)
    print("=" * 80)


def handle_check(args):
    services = ["shop", "place"] if args.service == "all" else [args.service]
    for s in services:
        lock_file = f"/tmp/rank_checker_{s}.lock"
        f = None
        if os.name == "posix":
            try:
                import fcntl
                f = open(lock_file, "w")
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, BlockingIOError):
                print(f"[{s.upper()}] Another checker process is already running. Skipping overlapping cycle.")
                continue
            except Exception:
                f = None

        try:
            run_cron_check(service_name=s, limit=args.limit, force=args.force)
        finally:
            if f and os.name == "posix":
                try:
                    import fcntl
                    fcntl.flock(f, fcntl.LOCK_UN)
                    f.close()
                except Exception:
                    pass


def handle_sync(args):
    services = ["shop", "place"] if args.service == "all" else [args.service]
    for s in services:
        pull_slots(s)
        push_ranks(s)


def handle_api(args):
    import uvicorn
    from config.settings import API_HOST
    uvicorn.run("api_server:app", host=API_HOST, port=args.port, reload=False, workers=1)


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() == "test" and len(sys.argv) >= 5:
        # Legacy backward compatibility: python main.py test shop <keyword> <target_id>
        srv = sys.argv[2].lower()
        kw = sys.argv[3]
        tid = sys.argv[4]
        if srv in ("shop", "nshop"):
            res = get_shop_rank_sync(keyword=kw, target_id=tid)
            print(f"Result: {res.get('status')} | Rank: #{res.get('targetRank')} | Time: {res.get('totalTime', 0):.2f}s")
        else:
            res = get_place_rank_sync(keyword=kw, target_id=tid)
            print(f"Result: {res.get('status')} | Rank: #{res.get('targetRank')} | Time: {res.get('totalTime', 0):.2f}s")
        return

    parser = argparse.ArgumentParser(description="Naver Organic Ranking Engine")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Shop Subcommand
    shop_parser = subparsers.add_parser("shop", help="Search Shopping pure organic ranking")
    shop_parser.add_argument("--keyword", "-k", type=str, default="노트북", help="Search keyword")
    shop_parser.add_argument("--target", "-t", type=str, default=None, help="Target product ID/nvMid")
    shop_parser.add_argument("--maxpage", "-m", type=int, default=13, help="Max pages (13 = ~500 items)")
    shop_parser.add_argument("--proxy", "-p", type=str, default=None, help="Custom SOCKS5 proxy")
    shop_parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    shop_parser.add_argument("--no-block-media", action="store_true", help="Disable media blocking")

    # Place Subcommand
    place_parser = subparsers.add_parser("place", help="Search Place pure organic ranking")
    place_parser.add_argument("--keyword", "-k", type=str, default="강남역 맛집", help="Search keyword")
    place_parser.add_argument("--target", "-t", type=str, default=None, help="Target place ID")
    place_parser.add_argument("--maxpage", "-m", type=int, default=12, help="Max scrolls")
    place_parser.add_argument("--proxy", "-p", type=str, default=None, help="Custom SOCKS5 proxy")
    place_parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    place_parser.add_argument("--no-block-media", action="store_true", help="Disable media blocking")

    # Check Subcommand (Cron batch execution)
    check_parser = subparsers.add_parser("check", help="Execute batch rank checking for pending DB items")
    check_parser.add_argument("service", nargs="?", default="shop", choices=["shop", "place", "all"], help="Service to check")
    check_parser.add_argument("--limit", "-l", type=int, default=100, help="Max items to process in batch")
    check_parser.add_argument("--force", "-f", action="store_true", help="Force check items even if checked recently")

    # Sync Subcommand
    sync_parser = subparsers.add_parser("sync", help="Sync ad slots from/to external DBs")
    sync_parser.add_argument("service", nargs="?", default="shop", choices=["shop", "place", "all"], help="Service to sync")

    # API Subcommand
    api_parser = subparsers.add_parser("api", help="Start FastAPI REST API Server")
    api_parser.add_argument("--port", type=int, default=8888, help="API Server port")

    if len(sys.argv) == 1:
        shop_parser.print_help()
        return

    if sys.argv[1].startswith("-"):
        sys.argv.insert(1, "shop")

    args = parser.parse_args()

    if args.command == "shop":
        handle_shop(args)
    elif args.command == "place":
        handle_place(args)
    elif args.command == "check":
        handle_check(args)
    elif args.command == "sync":
        handle_sync(args)
    elif args.command == "api":
        handle_api(args)


if __name__ == "__main__":
    main()
