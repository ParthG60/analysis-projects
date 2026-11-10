"""Fee-adjusted, tick-trade (fillability) analysis of the exploitable pool."""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_json(ROOT / "data" / "trade_fills.jsonl", lines=True)
rng = np.random.default_rng(0)
TICK = 0.01


def ci(x, n=2000):
    x = np.asarray(x, float)
    if len(x) < 8:
        return (np.nan, np.nan)
    s = [rng.choice(x, len(x), replace=True).mean() for _ in range(n)]
    return np.percentile(s, [2.5, 97.5])


print(f"fill records = {len(df)}")
print(f"tape truncated (couldn't reach 28h back): {df.truncated.mean():.1%}")
print(f"median trades scanned: {df.n_trades.median():.0f},  median span covered: {df.span_h.median():.1f}h\n")

print("=" * 84)
print("FILLABILITY: did a taker BUY print at/just below the horizon?")
print("=" * 84)
for hz in ["h24", "h12", "h6"]:
    buy = df[f"{hz}_buy"].notna().mean()
    have = df[f"{hz}_p"].notna().mean()
    print(f"  {hz}: any trade at horizon {have:.1%} | a BUY trade {buy:.1%}")

print("\n" + "=" * 84)
print("ENTRY PRICE: clob last-trade vs taker-buy (does the tape agree?)")
print("=" * 84)
h = pd.read_json(ROOT / "data" / "horizons.jsonl", lines=True)
h["id"] = h["id"].astype(str)
df["id"] = df["id"].astype(str)
c = df.merge(h[["id", "p7d", "p3d", "p1d", "p6h", "p1h"]], on="id", how="left")
for hz, clob in [("h24", "p1d"), ("h6", "p6h")]:
    both = c.dropna(subset=[f"{hz}_ask", clob])
    diff = (both[f"{hz}_ask"] - both[clob])
    print(f"  {hz} ask vs clob {clob}: n={len(both)} mean diff={diff.mean():+.4f} "
          f"median={diff.median():+.4f} |diff|>0.02 in {(diff.abs()>0.02).mean():.1%}")

print("\n" + "=" * 84)
print("FEE-ADJUSTED RETURNS, buy YES at taker-buy price (win: (1-cost)/cost else -1)")
print("=" * 84)


def strat(d, hz, apply_fee=True, use="ask"):
    d = d.dropna(subset=[f"{hz}_{use}"]).copy()
    p = d[f"{hz}_{use}"].clip(0.001, 0.999)
    cost = p + (d.fee_rate * p * (1 - p) if apply_fee else 0.0)
    ret = np.where(d.resolved0 == 1, (1 - cost) / cost, -1.0)
    return d, ret


rows = []
for hz in ["h24", "h12", "h6"]:
    d, ret = strat(df, hz, apply_fee=True)
    lo, hi = ci(ret)
    d0, ret0 = strat(df, hz, apply_fee=False)
    rows.append({"horizon": hz, "n": len(d), "win": round(d.resolved0.mean(), 3),
                 "mean_ret_fees": round(ret.mean(), 3), "ci": f"[{lo:.2f},{hi:.2f}]",
                 "mean_ret_nofee": round(ret0.mean(), 3),
                 "median": round(np.median(ret), 2),
                 "p_profit": round((ret > 0).mean(), 3)})
print(pd.DataFrame(rows).to_string(index=False))

print("\n-- by category (horizon h6, with fees) --")
rows = []
for cat, g in df.groupby("category"):
    d, ret = strat(g, "h6", apply_fee=True)
    if len(d) >= 15:
        rows.append({"category": cat, "n": len(d), "win": round(d.resolved0.mean(), 2),
                     "mean_ret": round(ret.mean(), 2), "median": round(np.median(ret), 2)})
print(pd.DataFrame(rows).sort_values("mean_ret", ascending=False).to_string(index=False))

print("\n-- geopolitics/fee-free subset (fee_rate==0) --")
gf = df[df.fee_rate == 0.0]
print(f"  n={len(gf)}  (all are fee-free by Polymarket rules)")
for hz in ["h24", "h6"]:
    d, ret = strat(gf, hz, apply_fee=True)
    if len(d):
        print(f"  {hz}: n={len(d)} win={d.resolved0.mean():.2f} mean_ret={ret.mean():+.2f}")

print("\n-- does the edge survive only in the liquid names? (h6, fees, by tape depth) --")
df["depth_q"] = pd.qcut(df.n_trades, 3, labels=["thin", "mid", "deep"])
for q, g in df.groupby("depth_q", observed=True):
    d, ret = strat(g, "h6", apply_fee=True)
    print(f"  {q:>5}: n={len(d)} win={d.resolved0.mean():.2f} mean_ret={ret.mean():+.2f} median={np.median(ret):+.2f}")
