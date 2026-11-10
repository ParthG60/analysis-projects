"""Soccer underdog edge vs. market volume, at absolute USD thresholds.

Answers: what is the minimum viable volume (and spread proxy) for the
round-robin domestic-league underdog strategy? Reuses the official-taxonomy
pool definition from analyze_official.py but bins by ABSOLUTE volume instead
of global quartiles, and restricts to Soccer-tagged events only.

Entry modelled as a taker BUY: p_hz + Sports fee (0.05) + slip (0.018).

Output: logs/volume_curve.txt
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "logs" / "volume_curve.txt"
SLIP = 0.018
FEE = 0.05  # Sports
BAND = (0.05, 0.35)
HZ = "p6h"

BINS = [0, 2000, 5000, 10000, 25000, 50000, 100000, 1e15]
LAB = ["<2k", "2-5k", "5-10k", "10-25k", "25-50k", "50-100k", "100k+"]


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
            ev[r["event_id"]] = {"tags": list(r.get("tags") or [])}
    return ev


def main():
    lines = []

    def p(*a):
        s = " ".join(str(x) for x in a)
        print(s, flush=True)
        lines.append(s)

    h = pd.read_json(ROOT / "data" / "horizons_full.jsonl", lines=True)
    h["id"] = h["id"].astype(str)
    u = pd.read_parquet(ROOT / "data" / "universe_full.parquet")
    u["id"] = u["id"].astype(str)
    d = h.merge(u[["id", "end_ts"]], on="id", how="left")

    m2e = load_map()
    ev = load_events()
    d["ev_tags"] = d["id"].map(m2e).map(lambda e: ev.get(e, {}).get("tags", []))

    is_soccer = d.ev_tags.map(lambda ts: "Soccer" in ts)
    d = d[is_soccer & (~d.neg_risk.fillna(False).astype(bool))].copy()

    d["diff_h"] = (d.close_ts - d.end_ts) / 3600.0
    pool = d[d.diff_h.between(-2, 6) & d[HZ].between(*BAND)].dropna(subset=[HZ]).copy()

    pcol = pool[HZ]
    cost = pcol + FEE * pcol * (1 - pcol) + SLIP
    pool["ret"] = np.where(pool.resolved0 == 1, (1 - cost) / cost, -1.0)
    pool["edge_pp"] = (pool.resolved0 - pcol) * 100

    p(f"Soccer single-binary on-schedule pool @ {HZ}, band {BAND}, fee 0.05 + slip 0.018")
    p(f"total soccer markets in band: {len(pool)}\n")
    p(f"{'volume':>10s} {'n':>6s} {'win%':>6s} {'mean_px':>8s} {'edge_pp':>8s} {'mean_ret':>9s} {'p_profit':>9s}")
    p("-" * 62)
    for lo, hi, lab in zip(BINS[:-1], BINS[1:], LAB):
        g = pool[(pool.volume >= lo) & (pool.volume < hi)]
        if len(g) < 15:
            p(f"{lab:>10s} {len(g):>6d}   (too few)")
            continue
        p(f"{lab:>10s} {len(g):>6d} {g.resolved0.mean()*100:>5.1f}% "
          f"{g[HZ].mean():>8.3f} {g.edge_pp.mean():>+8.1f} {g.ret.mean():>+9.3f} "
          f"{(g.ret>0).mean():>8.1%}")

    p("\n-- cumulative: volume >= threshold --")
    p(f"{'floor':>10s} {'n':>6s} {'win%':>6s} {'edge_pp':>8s} {'mean_ret':>9s}")
    p("-" * 45)
    for floor in [0, 2000, 5000, 10000, 25000, 50000]:
        g = pool[pool.volume >= floor]
        if len(g) < 5:
            continue
        p(f"{floor:>10d} {len(g):>6d} {g.resolved0.mean()*100:>5.1f}% "
          f"{g.edge_pp.mean():>+8.1f} {g.ret.mean():>+9.3f}")

    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nsaved {OUT}")


if __name__ == "__main__":
    main()
