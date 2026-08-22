import hashlib
import json
import os
import re
import sys
import time
from typing import Dict, Any, List, Optional
import pymysql
from core.logger import get_logger
from config.db_manager import db_mgr

logger = get_logger("rank.sync")

CONFIG_PATH = "/home/tech/rank/common/config/external_dbs.json"


def get_external_db_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_external_profiles():
    cfg = get_external_db_config()
    servers = cfg.get('servers', {})
    result = {'place': {}, 'shop': {}}

    # 1. nplace_profiles
    nplace_profs = cfg.get('nplace_profiles', {})
    for code, prof in nplace_profs.items():
        srv_key = prof.get('server')
        srv = servers.get(srv_key, {})
        result['place'][code] = {
            'host': srv.get('host'),
            'port': srv.get('port', 3306),
            'user': srv.get('user'),
            'password': srv.get('password'),
            'database': prof.get('database'),
            'charset': srv.get('charset', 'utf8mb4'),
            'connect_timeout': 10
        }

    # 2. nshop_databases (server1)
    srv1 = servers.get('server1', {})
    nshop_dbs = cfg.get('nshop_databases', [])
    for db in nshop_dbs:
        code = db.replace('adslot_', '')
        result['shop'][code] = {
            'host': srv1.get('host'),
            'port': srv1.get('port', 3306),
            'user': srv1.get('user'),
            'password': srv1.get('password'),
            'database': db,
            'charset': srv1.get('charset', 'utf8mb4'),
            'connect_timeout': 10
        }

    return result


def generate_push_hash(item):
    data = [
        str(item.get('rank') or 0),
        str(item.get('place_name') or item.get('title') or item.get('product_name') or ''),
        str(item.get('image_url') or ''),
        str(item.get('price') or item.get('product_price') or 0),
        str(item.get('visitor_review_count') or item.get('review_count') or 0),
        str(item.get('blog_cafe_review_count') or 0),
        str(item.get('save_count') or '0')
    ]
    return hashlib.md5('|'.join(data).encode('utf-8')).hexdigest()


def pull_slots(service_name: str, site_code: Optional[str] = None):
    """
    Pulls ad_slots from external marketing agency DBs into local assignments table.
    """
    srv_key = "shop" if service_name in ("shop", "nshop") else "place"
    profiles = load_external_profiles().get(srv_key, {})
    codes = [site_code] if site_code and site_code in profiles else list(profiles.keys())
    is_shop = (srv_key == "shop")

    ass_table = "nshop_assignments" if is_shop else "nplace_assignments"
    dr_table = "nshop_daily_ranks" if is_shop else "nplace_daily_ranks"

    logger.info(f"Starting [{srv_key.upper()}] PULL from external databases ({len(codes)} sites)...")

    for code in codes:
        ext_cfg = profiles[code]
        try:
            ext_conn = pymysql.connect(**ext_cfg)
            local_conn = db_mgr.get_connection()
        except Exception as e:
            logger.error(f"  ✗ Connection error ({srv_key}/{code}): {e}")
            continue

        try:
            with ext_conn.cursor(pymysql.cursors.DictCursor) as ext_cur:
                if is_shop:
                    ext_cur.execute("""
                        SELECT ad_slot_id, work_keyword, price_compare_mid, product_mid, product_name
                        FROM ad_slots
                        WHERE status = 'ACTIVE' AND is_active = 1 AND work_keyword IS NOT NULL
                    """)
                else:
                    ext_cur.execute("""
                        SELECT ad_slot_id, work_keyword, place_mid
                        FROM ad_slots
                        WHERE status = 'ACTIVE' AND is_active = 1 AND place_mid IS NOT NULL AND work_keyword IS NOT NULL
                    """)
                slots = ext_cur.fetchall()

            with local_conn.cursor() as loc_cur:
                loc_cur.execute(f"SELECT slot_id FROM {ass_table} WHERE site_code = %s", (code,))
                existing_slot_ids = set(row[0] for row in loc_cur.fetchall())
                current_slot_ids = set()

                for s in slots:
                    slot_id = str(s['ad_slot_id'])
                    current_slot_ids.add(slot_id)
                    query = s['work_keyword'].strip()

                    if is_shop:
                        pc_mid = str(s.get('price_compare_mid') or '0').strip()
                        prod_mid = str(s.get('product_mid') or '').strip()
                        target_id = pc_mid if (pc_mid and pc_mid != '0') else prod_mid
                        if not target_id:
                            continue

                        loc_cur.execute(f"""
                            INSERT INTO {ass_table} (site_code, slot_id, query, target_id, price_compare_mid, product_mid, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                            ON DUPLICATE KEY UPDATE 
                                query = VALUES(query), 
                                target_id = VALUES(target_id),
                                price_compare_mid = VALUES(price_compare_mid), 
                                product_mid = VALUES(product_mid), 
                                is_active = TRUE
                        """, (code, slot_id, query, target_id, pc_mid, prod_mid))

                        loc_cur.execute(f"""
                            INSERT INTO {dr_table} (rank_date, query, target_id, price_compare_mid, product_mid, is_active)
                            VALUES (CURDATE(), %s, %s, %s, %s, TRUE)
                            ON DUPLICATE KEY UPDATE 
                                price_compare_mid = VALUES(price_compare_mid), 
                                product_mid = VALUES(product_mid), 
                                is_active = TRUE
                        """, (query, target_id, pc_mid, prod_mid))

                    else:
                        raw_place_id = str(s.get('place_mid', '') or '').strip()
                        match = re.search(r'(\d+)', raw_place_id)
                        if not match:
                            continue
                        place_id = match.group(1)

                        loc_cur.execute(f"""
                            INSERT INTO {ass_table} (site_code, slot_id, query, place_id, is_active)
                            VALUES (%s, %s, %s, %s, TRUE)
                            ON DUPLICATE KEY UPDATE 
                                query = VALUES(query), 
                                place_id = VALUES(place_id), 
                                is_active = TRUE
                        """, (code, slot_id, query, place_id))

                        loc_cur.execute(f"""
                            INSERT INTO {dr_table} (rank_date, query, place_id, is_active)
                            VALUES (CURDATE(), %s, %s, TRUE)
                            ON DUPLICATE KEY UPDATE is_active = TRUE
                        """, (query, place_id))

                removed_ids = existing_slot_ids - current_slot_ids
                if removed_ids:
                    fmt = ','.join(['%s'] * len(removed_ids))
                    loc_cur.execute(f"UPDATE {ass_table} SET is_active = FALSE WHERE site_code = %s AND slot_id IN ({fmt})", [code] + list(removed_ids))

            local_conn.commit()
            logger.info(f"  ✓ [{code}] PULL complete ({len(slots)} slots active)")
        except Exception as e:
            logger.error(f"  ✗ [{code}] Error during pull: {e}")
        finally:
            ext_conn.close()
            local_conn.close()


def push_ranks(service_name: str, site_code: Optional[str] = None):
    """
    Pushes today's ranks to external databases.
    Delegates cleanly to /home/tech/rank/main.py sync.
    """
    import subprocess
    srv_key = "shop" if service_name in ("shop", "nshop") else "place"
    logger.info(f"Starting [{srv_key.upper()}] Rank PUSH to external databases...")
    try:
        cmd = ["python3", "/home/tech/rank/main.py", "sync", srv_key]
        if site_code:
            cmd.append(site_code)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        for line in res.stdout.splitlines():
            if line.strip():
                logger.info(f"  {line}")
        if res.returncode != 0 and res.stderr:
            logger.error(f"  Push stderr: {res.stderr.strip()}")
        logger.info(f"[{srv_key.upper()}] PUSH completed.")
    except Exception as e:
        logger.error(f"Error during push: {e}")
