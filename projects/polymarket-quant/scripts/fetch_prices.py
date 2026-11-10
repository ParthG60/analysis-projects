"""Fetch 1-minute price history (final 14d) for a sample of markets from CLOB.

Writes incremental rows to data/horizons.jsonl (resumable).
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
UNI = ROOT / "data" / "universe.parquet"
OUT = ROOT / "data" / "horizons.jsonl"
LOG = ROOT / "logs" / "fetch_prices.log"

CLOB = "https://clob.polymarket.com/prices-history"
WINDOW = 14 * 86400  # clob caps ~15d; stay under
HORIZONS = {  # label -> seconds before close
    "p7d": 7 * 86400, "p3d": 3 * 86400, "p1d": 86400,
    "p12h": 43200, "p6h": 21600, "p1h": 3600, "p30m": 1800,
}

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
MIN_VOLUME = 0.0
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
            hist = None
    if not hist:
        return None
    ts = [h["t"] for h in hist]
    ps = [h["p"] for h in hist]
    out = {
        "id": row["id"], "category": row["category"], "volume": row["volume"],
        "lifespan_h": row["lifespan_h"], "resolved0": int(row["resolved0"]),
        "n_points": len(ps),
    }
    for lbl, sec in HORIZONS.items():
        target = end - sec
        price = None
        for t, p in zip(ts, ps):  # ts ascending
            if t <= target:
                price = p
            else:
                break
        out[lbl] = price
    # realized vol over last 24h (1-min log returns)
    import math
    w = [(t, p) for t, p in zip(ts, ps) if t >= end - 86400 and p > 0]
    rets = [math.log(w[i][1] / w[i - 1][1]) for i in range(1, len(w))]
    out["rv_24h"] = (sum(x * x for x in rets) ** 0.5) if rets else None
    out["n_24h"] = len(w)
    return out


def main():
    df = pd.read_parquet(UNI)
    df = df[df["volume"] >= MIN_VOLUME].copy()
    # stratify: sort by volume desc and take top half, random half of rest
    done = set()
    if OUT.exists():
        for line in OUT.open():
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                pass
    df = df[~df["id"].isin(done)]
    # stratified sample across categories, weighted to volume
    df = df.sort_values("volume", ascending=False)
    # stratified: top-N by volume within each category
    cap = max(150, TARGET // max(1, df["category"].nunique()))
    sample = df.groupby("category", group_keys=False).head(cap)
    rows = sample.to_dict("records")
    log(f"target={TARGET} eligible={len(df)} sampling={len(rows)} done={len(done)}")
    f = OUT.open("a")
    n = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_one, r): r for r in rows}
        for fut in as_completed(futs):
            res = fut.result()
            if res:
                f.write(json.dumps(res) + "\n")
                f.flush()
            n += 1
            if n % 500 == 0:
                log(f"progress {n}/{len(rows)}")
    f.close()
    log(f"DONE processed={n}")


if __name__ == "__main__":
    main()
