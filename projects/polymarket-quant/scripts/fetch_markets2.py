"""Fetch resolved markets via monthly windows, ranked by volume.

Output: data/raw_markets.jsonl
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw_markets.jsonl"
LOG = ROOT / "logs" / "fetch_markets.log"
BASE = "https://gamma-api.polymarket.com/markets"

MONTHS = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13)]
MONTHS = [m for m in MONTHS if m <= "2026-11"]
VOL_MIN = 1000
PER_MONTH_CAP = 1000

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def month_bounds(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    d1 = f"{y}-{m:02d}-01T00:00:00Z"
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d2 = f"{ny}-{nm:02d}-01T00:00:00Z"
    return d1, d2


def get(params, tries=6):
    for i in range(tries):
        try:
            r = session.get(BASE, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(2 * (i + 1))
                continue
            log(f"HTTP {r.status_code}")
        except Exception as e:
            log(f"ERR {e}")
        time.sleep(1.5 * (i + 1))
    return []


def main():
    LOG.write_text("")
    seen = set()
    total = 0
    with OUT.open("w") as f:
        for ym in MONTHS:
            d1, d2 = month_bounds(ym)
            got = 0
            for off in range(0, PER_MONTH_CAP, 100):
                params = {
                    "closed": "true", "limit": 100, "offset": off,
                    "volume_num_min": VOL_MIN,
                    "end_date_min": d1, "end_date_max": d2,
                    "order": "volumeNum", "ascending": "false",
                }
                page = get(params)
                if not page:
                    break
                for m in page:
                    if m.get("id") in seen:
                        continue
                    seen.add(m.get("id"))
                    f.write(json.dumps(m) + "\n")
                    got += 1
                    total += 1
                if len(page) < 100:
                    break
            log(f"{ym}: +{got} (total {total})")
    log(f"DONE total={total}")


if __name__ == "__main__":
    main()
