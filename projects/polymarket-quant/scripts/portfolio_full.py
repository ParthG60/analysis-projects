"""Event-driven 500 USD portfolio simulation on the full universe.

Strategy: buy YES when the market's price at a fixed horizon is inside a band.
Capital is committed at entry (close_ts - horizon) and released at resolution
(close_ts). Entries compete for a shared cash pool.

Outputs: final equity, multiple, max drawdown, win rate, trade count, P&L
concentration, and a monthly breakdown.

Usage:
  python3 scripts/portfolio_full.py --vol-min 10000 --band 0.05 0.35 --hz p6h
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
HZ_SEC = {"p7d": 7*86400, "p3d": 3*86400, "p1d": 86400,
          "p12h": 43200, "p6h": 21600, "p1h": 3600, "p30m": 1800}
FEE = {"crypto": 0.07, "us_sports": 0.05, "football": 0.05, "esports": 0.05,
       "tennis": 0.05, "us_politics": 0.04, "intl_politics": 0.04,
       "macro_finance": 0.04, "tech": 0.04, "geopolitics": 0.0,
       "culture": 0.04, "science_space": 0.04, "other": 0.04}


def run(args):
    df = pd.read_json(ROOT / "data" / "horizons_full.jsonl", lines=True)
    hz = args.hz
    d = df.dropna(subset=[hz]).copy()
    d = d[d.volume >= args.vol_min]
    d = d[d[hz].between(args.band[0], args.band[1])]
    if args.neg_risk_only:
        d = d[d.neg_risk == True]
    d["fee_rate"] = d.category.map(FEE).fillna(0.05)
    pcol = d[hz].clip(0.001, 0.999)
    d["cost"] = pcol + d.fee_rate * pcol * (1 - pcol) + args.slip
    d["entry_ts"] = d["close_ts"] - HZ_SEC[hz]
    d = d.sort_values("entry_ts").reset_index(drop=True)

    cash = args.start
    peak = cash
    max_dd = 0.0
    open_pos = []  # (resolve_ts, payoff_value)
    trades = []
    n_skipped = 0
    equity_curve = []

    # merge entry and resolution events
    entries = d[["entry_ts", "cost", "resolved0", "close_ts", "category", "volume", "id"]]
    for row in entries.itertuples(index=False):
        # settle positions that resolved before this entry
        still = []
        for r_ts, payoff in open_pos:
            if r_ts <= row.entry_ts:
                cash += payoff
                equity_curve.append((r_ts, cash))
                peak = max(peak, cash)
                max_dd = max(max_dd, (peak - cash) / peak)
            else:
                still.append((r_ts, payoff))
        open_pos = still
        if len(open_pos) >= args.max_concurrent or cash < args.min_stake:
            n_skipped += 1
            continue
        stake = min(args.stake_cap, args.stake_frac * cash)
        if stake > cash or stake < args.min_stake:
            n_skipped += 1
            continue
        cash -= stake
        payoff = stake / row.cost if row.resolved0 == 1 else 0.0
        open_pos.append((row.close_ts, payoff))
        trades.append({"id": row.id, "category": row.category, "volume": row.volume,
                       "entry_ts": row.entry_ts, "close_ts": row.close_ts,
                       "cost": row.cost, "stake": stake, "win": int(row.resolved0 == 1),
                       "pnl": payoff - stake})
    # settle remaining
    for r_ts, payoff in sorted(open_pos):
        cash += payoff
        equity_curve.append((r_ts, cash))
        peak = max(peak, cash)
        max_dd = max(max_dd, (peak - cash) / peak)

    tr = pd.DataFrame(trades)
    eq = pd.DataFrame(equity_curve, columns=["ts", "equity"])
    # mark-to-market-ish daily equity for a smoother drawdown
    print(f"config: start={args.start} vol_min={args.vol_min:.0f} band={args.band} hz={hz} "
          f"slip={args.slip} stake={args.stake_frac:.1%}/cap{args.stake_cap}")
    print(f"candidates in-band: {len(d)}  traded: {len(tr)}  skipped: {n_skipped}")
    if tr.empty:
        print("no trades")
        return
    print(f"final equity: {cash:,.0f} USD  ({cash/args.start:.2f}x)")
    print(f"max realized drawdown: {max_dd:.1%}")
    print(f"win rate: {tr.win.mean():.1%}  avg entry cost: {tr.cost.mean():.3f}")
    print(f"gross staked: {tr.stake.sum():,.0f}  net PnL: {tr.pnl.sum():,.0f}")
    # P&L concentration
    pnl_sorted = tr.pnl.sort_values(ascending=False).values
    tot = pnl_sorted.sum()
    if tot > 0:
        top10 = pnl_sorted[:max(1, len(pnl_sorted)//10)].sum()
        print(f"top-10% of trades contribute {top10/tot:.0%} of net PnL")
    # how many trades carry the whole result
    cum = np.cumsum(pnl_sorted)
    frac_needed = (cum >= tot).argmax() + 1
    print(f"{frac_needed/len(pnl_sorted):.1%} of trades account for 100% of net PnL")

    # monthly
    tr["month"] = pd.to_datetime(tr.close_ts, unit="s").dt.to_period("M").astype(str)
    m = tr.groupby("month").agg(n=("pnl", "size"), pnl=("pnl", "sum"),
                                win=("win", "mean")).round(2)
    print("\nmonthly (last 24):")
    print(m.tail(24).to_string())
    # by category
    print("\nby category:")
    c = tr.groupby("category").agg(n=("pnl", "size"), win=("win", "mean"),
                                   pnl=("pnl", "sum"), avg_cost=("cost", "mean")).round(3)
    print(c.sort_values("pnl", ascending=False).to_string())
    return tr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, default=500.0)
    ap.add_argument("--vol-min", type=float, default=10000.0)
    ap.add_argument("--band", type=float, nargs=2, default=[0.05, 0.35])
    ap.add_argument("--hz", type=str, default="p6h")
    ap.add_argument("--stake-frac", type=float, default=0.02)
    ap.add_argument("--stake-cap", type=float, default=50.0)
    ap.add_argument("--min-stake", type=float, default=5.0)
    ap.add_argument("--slip", type=float, default=0.005)
    ap.add_argument("--max-concurrent", type=int, default=50)
    ap.add_argument("--neg-risk-only", action="store_true")
    run(ap.parse_args())
