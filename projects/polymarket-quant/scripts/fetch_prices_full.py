"""Fetch 1-minute CLOB price history (final 14d) for the full tradable universe.

Pool: single-binary, non-sports, resolved markets from data/universe_full.parquet.
Writes one JSON row per market to data/horizons_full.jsonl (resumable).

Usage:
  python3 scripts/fetch_prices_full.py [--workers 20] [--vol-min 1000] [--limit N]
"""
import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
UNI = ROOT / "data" / "universe_full.parquet"
OUT = ROOT / "data" / "horizons_full.jsonl"
LOG = ROOT / "logs" / "fetch_prices_full.log"
CLOB = "https://clob.polymarket.com/prices-history"
WINDOW = 14 * 86400

SPORTS = {"us_sports", "football", "esports", "tennis"}
HORIZONS = {"p7d": 7 * 86400, "p3d": 3 * 86400, "p1d": 86400,
            "p12h": 43200, "p6h": 21600, "p1h": 3600, "p30m": 1800}

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def fetch_one(row):
    tok = row["token0"]
    end = int(float(row["close_ts"]))
    start = end - WINDOW
    params = {"market": tok, "startTs": start, "endTs": end, "fidelity": 1}
    hist = None
    for i in range(4):
        try:
            r = session.get(CLOB, params=params, timeout=30)
            if r.status_code == 200:
                hist = r.json().get("history", [])
                break
            if r.status_code == 429:
                time.sleep(1.5 * (i + 1))
                continue
            hist = []
            break
        except Exception:
            time.sleep(1.0 * (i + 1))
    if hist is None:
        return None
    if not hist:
        return {"id": row["id"], "n_points": 0}
    ts = [h["t"] for h in hist]
    ps = [h["p"] for h in hist]
    out = {"id": row["id"], "category": row["category"], "volume": row["volume"],
           "lifespan_h": row["lifespan_h"], "resolved0": int(row["resolved0"]),
           "neg_risk": bool(row["neg_risk"]), "n_points": len(ps),
           "close_ts": row["close_ts"]}
    for lbl, sec in HORIZONS.items():
        target = end - sec
        price = None
        for t, p in zip(ts, ps):
            if t <= target:
                price = p
            else:
                break
        out[lbl] = price
    w = [(t, p) for t, p in zip(ts, ps) if t >= end - 86400 and p > 0]
    rets = [math.log(w[i][1] / w[i - 1][1]) for i in range(1, len(w))]
    out["rv_24h"] = (sum(x * x for x in rets) ** 0.5) if rets else None
    out["n_24h"] = len(w)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--vol-min", type=float, default=1000.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    u = pd.read_parquet(UNI)
    s = u[(~u.neg_risk) & (~u.category.isin(SPORTS)) & (u.volume >= args.vol_min)].copy()
    done = set()
    if OUT.exists():
        for line in OUT.open():
            try:
                done.add(str(json.loads(line)["id"]))
            except Exception:
                pass
    s["id"] = s["id"].astype(str)
    s = s[~s["id"].isin(done)]
    s = s.sort_values("volume", ascending=False)
    rows = s.to_dict("records")
    if args.limit:
        rows = rows[:args.limit]
    log(f"eligible={len(s)} todo={len(rows)} done={len(done)} workers={args.workers}")

    f = OUT.open("a")
    n = ok = 0
    CHUNK = 20000
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for res in ex.map(fetch_one, chunk):
                n += 1
                if res:
                    f.write(json.dumps(res) + "\n")
                    ok += 1
        f.flush()
        log(f"progress {n}/{len(rows)} written={ok}")
    f.close()
    log(f"DONE processed={n} written={ok}")


if __name__ == "__main__":
    main()
