"""Trade-tape (order-flow) aware entry test on the FULL universe.

For a sample of mid-band markets, walk the trade tape to recover the price a
*taker buyer* would actually have paid at the horizon (the last BUY print at or
before the horizon), vs the CLOB last-trade price stored in horizons_full.jsonl.
This is our best proxy for an order-book-aware fill.

Output: data/trade_fills_full.jsonl
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "trade_fills_full.jsonl"
LOG = ROOT / "logs" / "fetch_trades_full.log"
HZ = {"h24": 24 * 3600, "h12": 12 * 3600, "h6": 6 * 3600}
CUTOFF_PAD = 28 * 3600
CAP_PAGES = 20
TICK = 0.01
FEE = {"crypto": .07, "us_sports": .05, "football": .05, "tennis": .05, "esports": .05,
       "us_politics": .04, "intl_politics": .04, "macro_finance": .04, "culture": .04,
       "tech": .04, "science_space": .04, "geopolitics": 0.0, "other": .04}

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    LOG.open("a").write(line + "\n")


def walk(cid, cutoff, max_pages=CAP_PAGES):
    trades = []
    cursor = None
    for _ in range(max_pages):
        p = {"condition_id": cid, "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        j = None
        for attempt in range(4):
            try:
                j = session.get("https://data-api.polymarket.com/v2/trades", params=p, timeout=30).json()
                break
            except Exception:
                time.sleep(1 + attempt)
        if j is None:
            break
        d = j.get("data", [])
        if not d:
            return trades, False
        trades.extend(d)
        if d[-1]["timestamp"] <= cutoff:
            return trades, False
        cursor = j.get("pagination", {}).get("next_cursor")
        if not cursor:
            return trades, False
    return trades, True


def process(row):
    cid = row["condition_id"]
    end = int(float(row["close_ts"]))
    cutoff = end - CUTOFF_PAD
    trades, trunc = walk(cid, cutoff)
    if not trades:
        return None
    ts = [t["timestamp"] for t in trades]
    out = {"id": row["id"], "category": row["category"], "volume": row["volume"],
           "resolved0": int(row["resolved0"]), "fee_rate": FEE.get(row["category"], .04),
           "truncated": trunc, "n_trades": len(trades), "span_h": (end - min(ts)) / 3600,
           "clob_p6h": row.get("p6h"), "clob_p1d": row.get("p1d")}
    for lbl, sec in HZ.items():
        target = end - sec
        seg = [t for t in trades if t["timestamp"] <= target and t.get("outcome_index") == 0]
        if not seg:
            out[lbl + "_p"] = None
            continue
        last = max(seg, key=lambda t: t["timestamp"])
        out[lbl + "_p"] = last["price"]
        buys = [t for t in seg if t["side"] == "BUY"]
        out[lbl + "_buy"] = max(buys, key=lambda t: t["timestamp"])["price"] if buys else None
        out[lbl + "_ask"] = (out[lbl + "_buy"] if out[lbl + "_buy"] is not None
                             else last["price"] + TICK)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol-min", type=float, default=10000.0)
    ap.add_argument("--limit", type=int, default=2500)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--hz", type=str, default="p6h")
    args = ap.parse_args()

    h = pd.read_json(ROOT / "data" / "horizons_full.jsonl", lines=True)
    h["id"] = h["id"].astype(str)
    c = pd.read_parquet(ROOT / "data" / "conds_full.parquet")
    c["id"] = c["id"].astype(str)
    df = h.merge(c[["id", "condition_id"]], on="id", how="left")
    pool = df[(df.volume >= args.vol_min) & (df[args.hz].between(.05, .35))].dropna(subset=["condition_id"])
    done = set()
    if OUT.exists():
        done = {json.loads(l)["id"] for l in OUT.open()}
    pool = pool[~pool.id.isin(done)]
    pool = pool.sort_values("volume", ascending=False).head(args.limit)
    log(f"pool={len(pool)} vol_min={args.vol_min} hz={args.hz}")
    f = OUT.open("a")
    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(process, r) for r in pool.to_dict("records")]
        for fut in as_completed(futs):
            res = fut.result()
            if res:
                f.write(json.dumps(res) + "\n")
                f.flush()
            n += 1
            if n % 200 == 0:
                log(f"{n}/{len(pool)}")
    f.close()
    log(f"DONE {n}")


if __name__ == "__main__":
    main()
