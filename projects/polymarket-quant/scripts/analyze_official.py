"""Re-run the on-schedule underdog edge analysis using Polymarket's OFFICIAL
event taxonomy (category / tags / series) instead of the homebrewed regex.

Pool definition (same as the corrected backtest):
  - single binary, non-negRisk
  - on-schedule: closed within [-2h, +6h] of the published endDate
  - volume >= VOL_MIN, underdog price (outcome0) in [BAND_LO, BAND_HI] at p6h
  - entry is a taker BUY: p6h + category fee + SLIP

Reports edge by official event category and by event series.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "logs" / "analyze_official.txt"

# official-category fee map (Polymarket 2026 regime)
FEE = {
    "Sports": 0.05, "Crypto": 0.07, "Politics": 0.04, "Business": 0.04,
    "Pop-Culture": 0.04, "Ukraine & Russia": 0.00, "Chess": 0.05,
    "Tech": 0.04, "Science": 0.04, "World": 0.04,
}
SLIP = 0.018


def log(lines):
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def load_map():
    mp = {}
    with (ROOT / "data" / "market_event_map.jsonl").open() as f:
        for line in f:
            try:
                r = json.loads(line)
                mp[r["market_id"]] = r["event_id"]
            except Exception:
                pass
    return mp


def load_events():
    ev = {}
    with (ROOT / "data" / "events_full.jsonl").open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            series = r.get("series") or []
            ev[r["event_id"]] = {
                "category": r.get("category") or "UNKNOWN",
                "tags": list(r.get("tags") or []),
                "series": series[0] if series else "none",
                "title": r.get("title"),
                "ticker": r.get("ticker"),
            }
    return ev


SPORTS_TAGS = {"Sports", "Soccer", "Tennis", "Esports", "Basketball",
               "Baseball", "Hockey", "Football", "Golf", "Cricket", "Boxing",
               "MMA", "Chess", "Games"}
CRYPTO_TAGS = {"Crypto", "Crypto Prices", "Bitcoin", "Ethereum", "Solana",
               "XRP", "Ripple", "Dogecoin", "Altcoins", "Up or Down"}
FIN_TAGS = {"Finance", "Business", "Stocks", "Earnings"}


def bucket(tags, series, title):
    ts = set(tags)
    s = (series or "").lower()
    # sports by tag OR by series keyword
    if ts & SPORTS_TAGS:
        return "Sports"
    if any(k in s for k in ["liga", "serie", "bundesliga", "ligue", "league",
                            "atp", "wta", "itf", "nba", "nfl", "mlb", "nhl",
                            "counter strike", "dota", "valorant", "esports",
                            "cricket", "ufc", "f1", "grand prix", "copa"]):
        return "Sports"
    if any(k in s for k in ["up or down", "multi strikes", "hit price",
                            "btc", "eth ", "sol ", "xrp", "doge"]) or (ts & CRYPTO_TAGS):
        return "Crypto"
    if "Weather" in ts or "Temperature" in ts:
        return "Weather"
    if ts & FIN_TAGS or "spx" in s or "spy" in s:
        return "Finance"
    return "Other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol-min", type=float, default=25000.0)
    ap.add_argument("--lo", type=float, default=0.05)
    ap.add_argument("--hi", type=float, default=0.35)
    ap.add_argument("--hz", default="p6h")
    args = ap.parse_args()

    h = pd.read_json(ROOT / "data" / "horizons_full.jsonl", lines=True)
    h["id"] = h["id"].astype(str)
    u = pd.read_parquet(ROOT / "data" / "universe_full.parquet")
    u["id"] = u["id"].astype(str)
    d = h.merge(u[["id", "question", "end_ts"]], on="id", how="left")

    m2e = load_map()
    ev = load_events()
    d["event_id"] = d["id"].map(m2e)
    d["ev_cat"] = d["event_id"].map(lambda e: ev.get(e, {}).get("category", "UNMAPPED"))
    d["ev_series"] = d["event_id"].map(lambda e: ev.get(e, {}).get("series", "UNMAPPED"))
    d["ev_tags"] = d["event_id"].map(lambda e: ev.get(e, {}).get("tags", []))
    d["ev_title"] = d["event_id"].map(lambda e: ev.get(e, {}).get("title", ""))
    d["bucket"] = [bucket(t or [], s or "", ti or "")
                   for t, s, ti in zip(d.ev_tags, d.ev_series, d.ev_title)]

    lines = []
    lines.append(f"Official-taxonomy edge analysis | {args.hz} | vol>={args.vol_min:.0f} | band [{args.lo},{args.hi}]")
    lines.append(f"events loaded={len(ev)}  market->event map={len(m2e)}")
    mapped = d.event_id.notna().sum()
    lines.append(f"horizon markets={len(d)}  mapped to event={mapped} ({mapped/len(d):.1%})")

    d["diff_h"] = (d.close_ts - d.end_ts) / 3600.0
    pool = d[d.diff_h.between(-2, 6) & (d.volume >= args.vol_min)
             & d[args.hz].between(args.lo, args.hi)].dropna(subset=[args.hz]).copy()
    lines.append(f"\nON-SCHEDULE pool n={len(pool)}")

    pool["fee"] = pool.bucket.map({"Sports": 0.05, "Crypto": 0.07, "Weather": 0.04,
                                   "Finance": 0.04, "Other": 0.04}).fillna(0.04)
    p = pool[args.hz]
    pool["cost"] = p + pool.fee * p * (1 - p) + SLIP
    pool["ret"] = np.where(pool.resolved0 == 1, (1 - pool.cost) / pool.cost, -1.0)
    pool["edge_pp"] = (pool.resolved0 - p) * 100

    def agg(df, by):
        g = df.groupby(by).agg(
            n=("id", "size"),
            win=("resolved0", "mean"),
            mean_price=(args.hz, "mean"),
            edge_pp=("edge_pp", "mean"),
            ret=("ret", "mean"),
        ).sort_values("n", ascending=False)
        g["win"] = (g["win"] * 100).round(1)
        g["mean_price"] = g["mean_price"].round(3)
        g["edge_pp"] = g["edge_pp"].round(1)
        g["ret"] = g["ret"].round(2)
        return g

    lines.append("\n=== BY TAG-BUCKET (official tags) ===")
    lines.append(agg(pool, "bucket").to_string())

    lines.append("\n=== BY EVENT SERIES (n>=20) ===")
    ser = agg(pool, "ev_series")
    lines.append(ser[ser.n >= 20].to_string())

    lines.append("\n=== BY INDIVIDUAL TAG (n>=50, multi-tag) ===")
    rows = []
    for tag in sorted({t for ts in pool.ev_tags for t in ts}):
        sub = pool[pool.ev_tags.map(lambda ts, tag=tag: tag in ts)]
        if len(sub) >= 50:
            rows.append({"tag": tag, "n": len(sub),
                         "win": round(sub.resolved0.mean() * 100, 1),
                         "mean_price": round(sub[args.hz].mean(), 3),
                         "edge_pp": round(sub.edge_pp.mean(), 1),
                         "ret": round(sub.ret.mean(), 2)})
    lines.append(pd.DataFrame(rows).sort_values("n", ascending=False).to_string(index=False))

    lines.append("\n=== SPORTS vs NON-SPORTS (official tags/series) ===")
    pool["is_sports"] = pool.bucket.eq("Sports")
    lines.append(agg(pool, "is_sports").to_string())

    lines.append("\n=== OVERALL ===")
    lines.append(f"n={len(pool)} win={pool.resolved0.mean()*100:.1f}% "
                 f"edge={pool.edge_pp.mean():+.1f}pp ret={pool.ret.mean():+.2f}")

    log(lines)


if __name__ == "__main__":
    main()
