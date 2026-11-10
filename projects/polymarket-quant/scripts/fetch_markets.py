"""Fetch resolved (closed) Polymarket markets for 2025-2026 via keyset pagination.

Outputs: data/raw_markets.jsonl (one market JSON per line)
Logs:    logs/fetch_markets.log
"""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://gamma-api.polymarket.com/markets/keyset"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw_markets.jsonl"
LOG = ROOT / "logs" / "fetch_markets.log"

PARAMS = {
    "closed": "true",
    "end_date_min": "2025-01-01T00:00:00Z",
    "end_date_max": "2027-01-01T00:00:00Z",
    "order": "endDate",
    "ascending": "true",
    "limit": "100",
}

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def get(params, tries=5):
    for i in range(tries):
        try:
            r = session.get(BASE, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            log(f"HTTP {r.status_code} retry {i+1}")
        except Exception as e:  # noqa
            log(f"ERR {e} retry {i+1}")
        time.sleep(2 * (i + 1))
    raise RuntimeError("fetch failed")


def main():
    LOG.write_text("")
    cursor = None
    total = 0
    binary = 0
    pages = 0
    with OUT.open("w") as f:
        while True:
            params = dict(PARAMS)
            if cursor:
                params["next_cursor"] = cursor
            data = get(params)
            markets = data.get("markets", [])
            cursor = data.get("next_cursor")
            if not markets:
                break
            for m in markets:
                total += 1
                out = m.get("outcomes")
                try:
                    n_out = len(json.loads(out)) if out else 0
                except Exception:
                    n_out = 0
                if n_out == 2:
                    binary += 1
                    f.write(json.dumps(m) + "\n")
            pages += 1
            if pages % 20 == 0:
                log(f"pages={pages} total={total} binary={binary}")
            if not cursor:
                break
            if total > 400000:
                log("SAFETY CAP reached")
                break
    log(f"DONE pages={pages} total={total} binary={binary}")


if __name__ == "__main__":
    main()
