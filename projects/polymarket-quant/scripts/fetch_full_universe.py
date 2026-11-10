"""Full-universe census of ALL closed Polymarket markets via keyset pagination.

Gamma /markets offset pagination caps at ~2100; /markets/keyset exposes an
``after_cursor`` token for deep pagination. This crawls the entire closed-market
history (no volume / date filter) in id order and appends raw market JSON to NDJSON.

Resumable: the cursor is checkpointed after every page, and ids already present in
the output file are skipped on restart.

Output:
  data/raw_markets_full.jsonl   one market JSON per line (append, deduped)
  data/fetch_full_state.json    {cursor, n_written, last_id, done}

Usage:
  python3 scripts/fetch_full_universe.py            # resume / run to completion
  python3 scripts/fetch_full_universe.py --max-pages 50   # bounded test run
"""
import argparse
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw_markets_full.jsonl"
STATE = ROOT / "data" / "fetch_full_state.json"
LOG = ROOT / "logs" / "fetch_full.log"
BASE = "https://gamma-api.polymarket.com/markets/keyset"

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"cursor": None, "n_written": 0, "last_id": None, "done": False}


def save_state(st):
    STATE.write_text(json.dumps(st))


def existing_ids():
    ids = set()
    if OUT.exists():
        with OUT.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(str(json.loads(line).get("id")))
                except Exception:
                    continue
    return ids


FILTERS = {}


def fetch_page(cursor, tries=6):
    params = {"closed": "true", "limit": 100, **FILTERS}
    if cursor:
        params["after_cursor"] = cursor
    for i in range(tries):
        try:
            r = session.get(BASE, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            log(f"HTTP {r.status_code} {r.text[:120]}")
        except Exception as e:
            log(f"ERR {e}")
        time.sleep(1.5 * (i + 1))
    return None


def main():
    global OUT, STATE
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.05)
    ap.add_argument("--vol-min", type=float, default=0.0,
                    help="skip markets with lifetime volume below this (USD)")
    ap.add_argument("--end-min", type=str, default=None, help="ISO end_date lower bound")
    ap.add_argument("--end-max", type=str, default=None, help="ISO end_date upper bound")
    ap.add_argument("--out", type=str, default=str(OUT))
    ap.add_argument("--state", type=str, default=str(STATE))
    args = ap.parse_args()

    OUT = Path(args.out)
    STATE = Path(args.state)
    if args.vol_min > 0:
        FILTERS["volume_num_min"] = args.vol_min
    if args.end_min:
        FILTERS["end_date_min"] = args.end_min
    if args.end_max:
        FILTERS["end_date_max"] = args.end_max
    log(f"filters: {FILTERS or 'none'} -> {OUT.name}")

    st = load_state()
    if st.get("done"):
        log("state says done; pass --max-pages to force more or delete state file")
    seen = existing_ids()
    log(f"resume: {len(seen)} markets already on disk, cursor={str(st['cursor'])[:24]}")

    with OUT.open("a") as f:
        page = 0
        while True:
            j = fetch_page(st["cursor"])
            if j is None:
                log("page fetch failed after retries; stopping (resumable)")
                break
            markets = j.get("markets", [])
            if not markets:
                log("no more markets; DONE")
                st["done"] = True
                break
            n_new = 0
            for m in markets:
                mid = str(m.get("id"))
                if mid in seen:
                    continue
                seen.add(mid)
                f.write(json.dumps(m) + "\n")
                n_new += 1
            f.flush()
            page += 1
            st["n_written"] += n_new
            st["last_id"] = str(markets[-1].get("id"))
            st["cursor"] = j.get("next_cursor")
            save_state(st)
            if page % 10 == 0 or page <= 3:
                log(f"page {page}: +{n_new} (total {len(seen)}), last_id {st['last_id']}")
            if not st["cursor"]:
                log("cursor exhausted; DONE")
                st["done"] = True
                break
            if args.max_pages and page >= args.max_pages:
                log(f"reached --max-pages {args.max_pages}; stopping (resumable)")
                break
            time.sleep(args.sleep)

    save_state(st)
    log(f"STOP total_on_disk={len(seen)} pages={page} done={st['done']}")


if __name__ == "__main__":
    main()
