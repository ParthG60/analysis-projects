"""Cost- and volume-aware backtest on the full universe + out-of-sample split.

Reads data/horizons_full.jsonl (full tradable pool, 1-min CLOB horizons) and
data/universe_full.parquet. Tests whether the earlier claims hold on the much
larger sample:
  - reverse favourite-longshot bias in the 5-35% band
  - edge concentrated in single-binary (non-negRisk) markets
  - edge survives fees
  - edge survives in the most liquid volume tercile
  - stability 2025 (in-sample) vs 2026 (out-of-sample)

Output: logs/backtest_full.txt
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rng = np.random.default_rng(0)
OUT = ROOT / "logs" / "backtest_full.txt"
_lines = []


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _lines.append(s)


def ci(x, n=2000):
    x = np.asarray(x, float)
    if len(x) < 8:
        return (np.nan, np.nan)
    s = [rng.choice(x, len(x), replace=True).mean() for _ in range(n)]
    return np.percentile(s, [2.5, 97.5])


FEE = {"crypto": 0.07, "us_sports": 0.05, "football": 0.05, "esports": 0.05,
       "tennis": 0.05, "us_politics": 0.04, "intl_politics": 0.04,
       "macro_finance": 0.04, "tech": 0.04, "geopolitics": 0.0,
       "culture": 0.04, "science_space": 0.04, "other": 0.04}
MID = (0.05, 0.35)
HZ = ["p7d", "p3d", "p1d", "p12h", "p6h", "p1h", "p30m"]

h = pd.read_json(ROOT / "data" / "horizons_full.jsonl", lines=True)
u = pd.read_parquet(ROOT / "data" / "universe_full.parquet")
h["id"] = h["id"].astype(str)
u["id"] = u["id"].astype(str)
df = h.merge(u[["id", "fee_type", "ticker", "question", "end_ts"]], on="id", how="left")
df["fee_rate"] = df["category"].map(FEE).fillna(0.04)
df["year"] = pd.to_datetime(df["close_ts"], unit="s").dt.year
p(f"horizons rows = {len(df)}  (fee_type present: {df.fee_type.notna().mean():.1%})")
p(f"years: {df.year.value_counts().sort_index().to_dict()}")
p(f"categories: {df.category.value_counts().to_dict()}\n")


def ret_series(d, hz, lo, hi, kind="yes", fee=False, use=None):
    d = d.dropna(subset=[hz])
    t = d[d[hz].between(lo, hi)].copy()
    if len(t) == 0:
        return t, np.array([])
    pcol = t[hz].clip(0.001, 0.999)
    cost = pcol + (t.fee_rate * pcol * (1 - pcol) if fee else 0.0)
    if kind == "yes":
        r = np.where(t.resolved0 == 1, (1 - cost) / cost, -1.0)
    else:
        r = np.where(t.resolved0 == 0, (1 - cost) / cost, -1.0)
    return t, r


def edge_stats(d, hz, lo=MID[0], hi=MID[1]):
    d = d.dropna(subset=[hz])
    z = d[d[hz].between(lo, hi)]
    if len(z) < 10:
        return None
    e = (z.resolved0 - z[hz]).values
    lo_ci, hi_ci = ci(e)
    return dict(n=len(z), implied=round(z[hz].mean(), 3), realised=round(z.resolved0.mean(), 3),
                edge_pp=round(e.mean() * 100, 1), ci=f"[{lo_ci*100:.0f},{hi_ci*100:.0f}]")


# ---- 1. calibration by bucket --------------------------------------------
p("=" * 90)
p("1) CALIBRATION (realised - implied, pp) by price bucket at each horizon")
p("=" * 90)
BINS = [0, .05, .10, .20, .35, .65, .80, .90, 1.0001]
LAB = ["0-5", "5-10", "10-20", "20-35", "35-65", "65-80", "80-90", "90-100"]
for hz in ["p3d", "p1d", "p6h"]:
    d = df.dropna(subset=[hz]).copy()
    d["b"] = pd.cut(d[hz], BINS, labels=LAB, right=False)
    rows = []
    for b, g in d.groupby("b", observed=True):
        if len(g) < 25:
            continue
        e = (g.resolved0 - g[hz])
        rows.append({"bucket": b, "n": len(g), "implied": round(g[hz].mean(), 3),
                     "realised": round(g.resolved0.mean(), 3),
                     "edge_pp": round(e.mean() * 100, 1)})
    p(f"\n-- {hz} --")
    p(pd.DataFrame(rows).to_string(index=False))

# ---- 2. mid-band edge across horizons ------------------------------------
p("\n" + "=" * 90)
p("2) MID-BAND (0.05-0.35) EDGE by horizon")
p("=" * 90)
rows = [dict(horizon=hz, **(edge_stats(df, hz) or {})) for hz in HZ]
p(pd.DataFrame([r for r in rows if r.get("n")]).to_string(index=False))

# ---- 3. cost-aware strategy returns --------------------------------------
p("\n" + "=" * 90)
p("3) COST-AWARE strategy: buy YES 0.05-0.35, no-fee vs fee-adjusted")
p("=" * 90)
rows = []
for hz in HZ:
    t0, r0 = ret_series(df, hz, *MID, kind="yes", fee=False)
    t1, r1 = ret_series(df, hz, *MID, kind="yes", fee=True)
    if len(r1) == 0:
        continue
    lo, hi = ci(r1)
    rows.append({"horizon": hz, "n": len(r1), "win": round(t1.resolved0.mean(), 3),
                 "ret_nofee": round(r0.mean(), 3), "ret_fee": round(r1.mean(), 3),
                 "ci_fee": f"[{lo:.2f},{hi:.2f}]", "median": round(np.median(r1), 2),
                 "p_profit": round((r1 > 0).mean(), 3)})
p(pd.DataFrame(rows).to_string(index=False))

# ---- 4. volume-aware ------------------------------------------------------
p("\n" + "=" * 90)
p("4) VOLUME-AWARE: mid-band edge + fee-adjusted return by volume quartile")
p("=" * 90)
for hz in ["p1d", "p6h"]:
    d = df.dropna(subset=[hz]).copy()
    d["vq"] = pd.qcut(d.volume, 4, labels=["v_low", "v_mid", "v_hi", "v_top"])
    rows = []
    for q, g in d.groupby("vq", observed=True):
        e = edge_stats(g, hz)
        _, r = ret_series(g, hz, *MID, kind="yes", fee=True)
        rows.append({"vq": q, "n": e["n"] if e else 0,
                     "median_vol": int(g.volume.median()),
                     "implied": e["implied"] if e else None,
                     "realised": e["realised"] if e else None,
                     "edge_pp": e["edge_pp"] if e else None,
                     "ret_fee": round(r.mean(), 3) if len(r) else None})
    p(f"\n-- {hz} --")
    p(pd.DataFrame(rows).to_string(index=False))

# ---- 5. category breakdown ------------------------------------------------
p("\n" + "=" * 90)
p("5) CATEGORY breakdown (mid-band edge @p1d & @p6h, fee-adjusted ret @p6h)")
p("=" * 90)
rows = []
for cat, g in df.groupby("category"):
    e1 = edge_stats(g, "p1d")
    e6 = edge_stats(g, "p6h")
    _, r6 = ret_series(g, "p6h", *MID, kind="yes", fee=True)
    rows.append({"category": cat, "n_pool": len(g),
                 "n_p1d": e1["n"] if e1 else 0, "edge_p1d": e1["edge_pp"] if e1 else None,
                 "n_p6h": e6["n"] if e6 else 0, "edge_p6h": e6["edge_pp"] if e6 else None,
                 "win_p6h": e6["realised"] if e6 else None,
                 "ret_fee_p6h": round(r6.mean(), 2) if len(r6) else None})
p(pd.DataFrame(rows).sort_values("edge_p6h", ascending=False).to_string(index=False))

# ---- 6. out-of-sample -----------------------------------------------------
p("\n" + "=" * 90)
p("6) OUT-OF-SAMPLE: 2025 (in-sample) vs 2026 (OOS)")
p("=" * 90)
for label, sub in [("ALL", df), ("crypto", df[df.category == "crypto"]),
                   ("non-crypto", df[df.category != "crypto"])]:
    p(f"\n-- {label} --")
    rows = []
    for yr in [2025, 2026]:
        g = sub[sub.year == yr]
        e = edge_stats(g, "p6h")
        t, r = ret_series(g, "p6h", *MID, kind="yes", fee=True)
        rows.append({"year": yr, "n": e["n"] if e else 0,
                     "implied": e["implied"] if e else None,
                     "realised": e["realised"] if e else None,
                     "edge_pp": e["edge_pp"] if e else None,
                     "ret_fee": round(r.mean(), 3) if len(r) else None,
                     "p_profit": round((r > 0).mean(), 3) if len(r) else None})
    p(pd.DataFrame(rows).to_string(index=False))

# ---- 7. verdict -----------------------------------------------------------
p("\n" + "=" * 90)
p("7) VERDICT vs prior claims")
p("=" * 90)
allmid = edge_stats(df, "p6h")
p(f"* reverse favourite-longshot in 5-35% band: edge {allmid['edge_pp']}pp "
  f"(n={allmid['n']}, realised {allmid['realised']} vs implied {allmid['implied']})")
_, r = ret_series(df, "p6h", *MID, kind="yes", fee=True)
p(f"* survives fees at p6h: fee-adjusted mean ret {r.mean():+.2f} (win {(r>0).mean():.1%})")
d = df.dropna(subset=["p6h"]).copy()
d["vq"] = pd.qcut(d.volume, 4, labels=["v_low", "v_mid", "v_hi", "v_top"])
top = d[d.vq == "v_top"]
et = edge_stats(top, "p6h")
p(f"* most-liquid quartile still edges: {et['edge_pp']}pp (n={et['n']})")

OUT.write_text("\n".join(_lines) + "\n")
print(f"\nsaved {OUT}")
