"""Analyse favourite-longshot bias, horizon effects, and category profiles.

Reads data/horizons.jsonl. Prints compact tables and writes data/*.csv.
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_json(ROOT / "data" / "horizons.jsonl", lines=True)
df = df.dropna(subset=["resolved0"])
HZ = ["p7d", "p3d", "p1d", "p12h", "p6h", "p1h", "p30m"]
BINS = [0, .02, .05, .10, .20, .35, .65, .80, .90, .95, .98, 1.0001]
LABELS = ["0-2", "2-5", "5-10", "10-20", "20-35", "35-65", "65-80", "80-90", "90-95", "95-98", "98-100"]

pd.set_option("display.width", 200)
print(f"n markets = {len(df)}\n")

# ---------- 1. Calibration by price bucket at each horizon ----------------
print("=" * 78)
print("CALIBRATION: realised win-rate by price bucket (edge = realised - implied)")
print("=" * 78)
for h in ["p3d", "p1d", "p1h"]:
    d = df.dropna(subset=[h]).copy()
    d["bucket"] = pd.cut(d[h], BINS, labels=LABELS, right=False)
    g = d.groupby("bucket", observed=True).agg(
        n=("resolved0", "size"), implied=(h, "mean"), realised=("resolved0", "mean"))
    g["edge_pp"] = (g.realised - g.implied) * 100
    g = g[g.n >= 20]
    print(f"\n--- horizon = {h} ---")
    print(g.round(3).to_string())

# ---------- 2. Two tail strategies across horizons ------------------------
def strat_stats(d, h, kind, lo, hi=None):
    dd = d.dropna(subset=[h])
    if kind == "buy_yes_range":      # buy YES when lo<=p<=hi
        t = dd[(dd[h] >= lo) & (dd[h] <= hi)].copy()
        t["ret"] = np.where(t.resolved0 == 1, (1 - t[h]) / t[h], -1.0)
    elif kind == "buy_no_range":     # buy NO (short YES) when lo<=p<=hi
        t = dd[(dd[h] >= lo) & (dd[h] <= hi)].copy()
        t["ret"] = np.where(t.resolved0 == 0, t[h] / (1 - t[h]), -1.0)
    elif kind == "short_longshot":   # buy NO when YES <= lo
        t = dd[dd[h] <= lo].copy()
        t["ret"] = np.where(t.resolved0 == 0, t[h] / (1 - t[h]), -1.0)
    elif kind == "near_certainty":   # buy YES when YES >= lo
        t = dd[dd[h] >= lo].copy()
        t["ret"] = np.where(t.resolved0 == 1, (1 - t[h]) / t[h], -1.0)
    else:
        return None
    if len(t) == 0:
        return None
    hold_days = {"p7d": 7, "p3d": 3, "p1d": 1, "p12h": .5, "p6h": .25, "p1h": 1/24, "p30m": 1/48}[h]
    ann = (1 + t.ret.mean()) ** (365 / hold_days) - 1
    return dict(n=len(t), win=t.resolved0.mean(), mean_ret=t.ret.mean(),
                median_ret=t.ret.median(), ann_ret=ann)

print("\n" + "=" * 78)
print("STRATEGY A: SHORT LONGSHOTS (buy NO when YES <= 0.05)")
print("=" * 78)
rows = []
for h in HZ:
    s = strat_stats(df, h, "short_longshot", 0.05)
    if s:
        rows.append({"horizon": h, **s})
print(pd.DataFrame(rows).round(3).to_string(index=False))

print("\n" + "=" * 78)
print("STRATEGY B: BUY NEAR-CERTAINTIES (buy YES when YES >= 0.90)")
print("=" * 78)
rows = []
for h in HZ:
    s = strat_stats(df, h, "near_certainty", 0.90)
    if s:
        rows.append({"horizon": h, **s})
print(pd.DataFrame(rows).round(3).to_string(index=False))

print("\n" + "=" * 78)
print("STRATEGY B2: BUY EXTREME FAVOURITES (buy YES when YES >= 0.97)")
print("=" * 78)
rows = []
for h in ["p7d", "p3d", "p1d", "p6h"]:
    s = strat_stats(df, h, "near_certainty", 0.97)
    if s:
        rows.append({"horizon": h, **s})
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ---------- 3. Category profile -------------------------------------------
print("\n" + "=" * 78)
print("STRATEGY C: BUY UNDERPRICED MID-RANGE (buy YES when 0.05 <= p <= 0.35)")
print("=" * 78)
rows = []
for h in HZ:
    s = strat_stats(df, h, "buy_yes_range", 0.05, 0.35)
    if s:
        rows.append({"horizon": h, **s})
print(pd.DataFrame(rows).round(3).to_string(index=False))

print("\n" + "=" * 78)
print("STRATEGY D: SHORT OVERPRICED FAVOURITES (buy NO when 0.65 <= p <= 0.90)")
print("=" * 78)
rows = []
for h in HZ:
    s = strat_stats(df, h, "buy_no_range", 0.65, 0.90)
    if s:
        rows.append({"horizon": h, **s})
print(pd.DataFrame(rows).round(3).to_string(index=False))

print("\n" + "=" * 78)
print("CATEGORY x STRATEGY C & D (horizon p1d)")
print("=" * 78)
rows = []
for cat, d in df.groupby("category"):
    c = strat_stats(d, "p1d", "buy_yes_range", 0.05, 0.35)
    dd = strat_stats(d, "p1d", "buy_no_range", 0.65, 0.90)
    rows.append({
        "category": cat,
        "C_n": c["n"] if c else 0, "C_ret": round(c["mean_ret"], 3) if c else np.nan,
        "C_win": round(c["win"], 2) if c else np.nan,
        "D_n": dd["n"] if dd else 0, "D_ret": round(dd["mean_ret"], 3) if dd else np.nan,
        "D_win": round(dd["win"], 2) if dd else np.nan,
    })
print(pd.DataFrame(rows).sort_values("C_ret", ascending=False).to_string(index=False))

print("\n" + "=" * 78)
print("SENSITIVITY: exclude ultra-short markets (lifespan < 24h)")
print("=" * 78)
long_only = df[df.lifespan_h >= 24]
for h in ["p3d", "p1d"]:
    c = strat_stats(long_only, h, "buy_yes_range", 0.05, 0.35)
    dd = strat_stats(long_only, h, "buy_no_range", 0.65, 0.90)
    print(f"{h}: C n={c['n']} ret={c['mean_ret']:.3f} | D n={dd['n']} ret={dd['mean_ret']:.3f}")

print("\n" + "=" * 78)
print("CATEGORY PROFILE")
print("=" * 78)
prof = df.groupby("category").agg(
    n=("id", "size"),
    med_life_h=("lifespan_h", "median"),
    med_vol=("volume", "median"),
    med_rv24h=("rv_24h", "median"),
).sort_values("n", ascending=False)
print(prof.round(2).to_string())

# ---------- 4. Category x tail mispricing at 1d ---------------------------
print("\n" + "=" * 78)
print("CATEGORY x TAIL MISPRICING (horizon 1d)")
print("=" * 78)
rows = []
for cat, d in df.groupby("category"):
    s_long = strat_stats(d, "p1d", "short_longshot", 0.05)
    s_near = strat_stats(d, "p1d", "near_certainty", 0.90)
    rows.append({
        "category": cat,
        "n_long": s_long["n"] if s_long else 0,
        "long_win": s_long["win"] if s_long else np.nan,
        "long_ret": s_long["mean_ret"] if s_long else np.nan,
        "n_near": s_near["n"] if s_near else 0,
        "near_win": s_near["win"] if s_near else np.nan,
        "near_ret": s_near["mean_ret"] if s_near else np.nan,
    })
print(pd.DataFrame(rows).round(3).to_string(index=False))

df.to_csv(ROOT / "data" / "horizons_clean.csv", index=False)
print("\nsaved data/horizons_clean.csv")
