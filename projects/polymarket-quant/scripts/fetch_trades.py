"""Tick-trade based fillability + fee-adjusted test for the exploitable pool.

Pool: SINGLE (non-negRisk) markets, price 0.05-0.35 at p1d or p6h.
Walks the trade tape newest-first (cursor pagination) to recover, at each
horizon, the price a *taker buyer* would actually pay, then applies fees.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "trade_fills.jsonl"
LOG = ROOT / "logs" / "fetch_trades.log"

HZ = {"h24": 24 * 3600, "h12": 12 * 3600, "h6": 6 * 3600}
CUTOFF_PAD = 28 * 3600
CAP_PAGES = 25
TICK = 0.01
FEE = {"crypto": .07, "us_sports": .05, "football": .05, "tennis": .05, "esports": .05,
       "us_politics": .04, "intl_politics": .04, "macro_finance": .04, "culture": .05,
       "tech": .04, "science_space": .05, "geopolitics": 0.0, "other": .05}

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    LOG.open("a").write(line + "\n")


def walk(cid, cutoff, max_pages=CAP_PAGES):
    """Return trades newest-first down to cutoff, or (trades, truncated)."""
    trades = []
    cursor = None
    for _ in range(max_pages):
        p = {"condition_id": cid, "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        for attempt in range(4):
            try:
                j = session.get("https://data-api.polymarket.com/v2/trades", params=p, timeout=30).json()
                break
            except Exception:
                time.sleep(1 + attempt)
        else:
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
           "resolved0": int(row["resolved0"]), "fee_rate": FEE.get(row["category"], .05),
           "truncated": trunc, "n_trades": len(trades),
           "span_h": (end - min(ts)) / 3600}
    for lbl, sec in HZ.items():
        target = end - sec
        # trades on the token0 outcome only, at/before horizon
        seg = [t for t in trades if t["timestamp"] <= target and t.get("outcome_index") == 0]
        if not seg:
            out[lbl + "_p"] = None
        else:
            last = max(seg, key=lambda t: t["timestamp"])
            out[lbl + "_p"] = last["price"]
            # last taker BUY at/before horizon = realistic entry for a buyer
            buys = [t for t in seg if t["side"] == "BUY"]
            out[lbl + "_buy"] = max(buys, key=lambda t: t["timestamp"])["price"] if buys else None
            out[lbl + "_ask"] = (out[lbl + "_buy"] if out[lbl + "_buy"] is not None
                                 else last["price"] + TICK)
    return out


def main():
    LOG.write_text("")
    h = pd.read_json(ROOT / "data" / "horizons.jsonl", lines=True)
    h["id"] = h["id"].astype(str)
    u = pd.read_parquet(ROOT / "data" / "universe.parquet")
    u["id"] = u["id"].astype(str)
    raw = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "raw_markets.jsonl").open()}
    u["condition_id"] = u["id"].map(lambda i: raw.get(i, {}).get("conditionId"))
    df = h.merge(u[["id", "neg_risk", "condition_id", "close_ts"]], on="id", how="left")
    # pool: single markets in the mid bucket at p1d OR p6h
    pool = df[(df.neg_risk == False) & (
        df.p1d.between(.05, .35) | df.p6h.between(.05, .35))].dropna(subset=["condition_id"])
    done = set()
    if OUT.exists():
        done = {json.loads(l)["id"] for l in OUT.open()}
    pool = pool[~pool.id.isin(done)]
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else len(pool)
    pool = pool.sort_values("volume", ascending=False).head(lim)
    log(f"pool={len(pool)}")
    f = OUT.open("a")
    n = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for fut in as_completed([ex.submit(process, r) for r in pool.to_dict("records")]):
            res = fut.result()
            if res:
                f.write(json.dumps(res) + "\n")
                f.flush()
            n += 1
            if n % 100 == 0:
                log(f"{n}/{len(pool)}")
    f.close()
    log(f"DONE {n}")


if __name__ == "__main__":
    main()
