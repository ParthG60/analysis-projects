"""Final consolidated results: bugs ruled out, report numbers."""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_json(ROOT / "data" / "horizons.jsonl", lines=True)
rng = np.random.default_rng(0)
HZ = {"p7d": 7.0, "p3d": 3.0, "p1d": 1.0, "p6h": 0.25}


def boot_ci(x, n=2000):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (np.nan, np.nan)
    s = [rng.choice(x, len(x), replace=True).mean() for _ in range(n)]
    return np.percentile(s, [2.5, 97.5])


print("=" * 84)
print("1) CALIBRATION EDGE (realised - implied, pp) BY BUCKET AND HORIZON  [n, edge, 95% CI]")
print("=" * 84)
BINS = [0, .05, .10, .20, .35, .65, .80, .90, .95, 1.0001]
LAB = ["0-5", "5-10", "10-20", "20-35", "35-65", "65-80", "80-90", "90-95", "95-100"]
for h in ["p7d", "p3d", "p1d"]:
    d = df.dropna(subset=[h]).copy()
    d["b"] = pd.cut(d[h], BINS, labels=LAB, right=False)
    rows = []
    for b, g in d.groupby("b", observed=True):
        if len(g) < 25:
            continue
        edge = (g.resolved0 - g[h])
        lo, hi = boot_ci(edge.values)
        rows.append({"bucket": b, "n": len(g), "implied": round(g[h].mean(), 3),
                     "realised": round(g.resolved0.mean(), 3),
                     "edge_pp": round(edge.mean()*100, 1),
                     "ci": f"[{lo*100:.1f},{hi*100:.1f}]"})
    print(f"\n-- horizon {h} --")
    print(pd.DataFrame(rows).to_string(index=False))

print("\n" + "=" * 84)
print("2) HORIZON DRIFT: mean price vs realised, globally and in the mispriced buckets")
print("=" * 84)
rows = []
for h in HZ:
    d = df.dropna(subset=[h])
    mid = d[d[h].between(.05, .35)]
    fav = d[d[h].between(.65, .90)]
    rows.append({"horizon": h, "n": len(d),
                 "mean_price": round(d[h].mean(), 3), "mean_resolved": round(d.resolved0.mean(), 3),
                 "global_edge_pp": round((d.resolved0-d[h]).mean()*100, 2),
                 "mid_edge_pp": round((mid.resolved0-mid[h]).mean()*100, 1),
                 "fav_edge_pp": round((fav.resolved0-fav[h]).mean()*100, 1)})
print(pd.DataFrame(rows).to_string(index=False))

print("\n" + "=" * 84)
print("3) STRATEGY RETURNS (per trade, fraction of capital staked) with bootstrap CI")
print("=" * 84)


def strat(d, h, kind, lo, hi):
    d = d.dropna(subset=[h])
    if kind == "yes":
        t = d[d[h].between(lo, hi)].copy()
        t["ret"] = np.where(t.resolved0 == 1, (1-t[h])/t[h], -1.0)
    else:
        t = d[d[h].between(lo, hi)].copy()
        t["ret"] = np.where(t.resolved0 == 0, t[h]/(1-t[h]), -1.0)
    ret = t["ret"].values
    lo_ci, hi_ci = boot_ci(ret)
    return dict(n=len(t), win=round(t.resolved0.mean(), 3) if kind == "yes" else round(1-t.resolved0.mean(), 3),
                mean_ret=round(ret.mean(), 3), med_ret=round(np.median(ret), 2),
                ci=f"[{lo_ci:.2f},{hi_ci:.2f}]",
                p_profit=round((ret > 0).mean(), 3))


for label, kind, lo, hi in [
    ("A: buy YES 0.05-0.20 (underdog)", "yes", .05, .20),
    ("B: buy YES 0.20-0.35", "yes", .20, .35),
    ("C: buy NO  0.65-0.90 (short fav)", "no", .65, .90),
    ("D: buy YES 0.05-0.35 (combined)", "yes", .05, .35),
]:
    print(f"\n{label}")
    rows = []
    for h in HZ:
        s = strat(df, h, kind, lo, hi)
        s["horizon"] = h
        rows.append(s)
    print(pd.DataFrame(rows)[["horizon", "n", "win", "mean_ret", "med_ret", "ci", "p_profit"]].to_string(index=False))

print("\n" + "=" * 84)
print("4) HOW OFTEN ARE MARKETS IN THE 'BIG EDGE' ZONE? (p1d)")
print("=" * 84)
d = df.dropna(subset=["p1d"])
for lo, hi in [(.05, .20), (.20, .35), (.65, .90)]:
    z = d[d.p1d.between(lo, hi)]
    print(f"price {lo}-{hi}: {len(z)} markets ({len(z)/len(d)*100:.1f}% of sample), "
          f"avg |edge| = {abs((z.resolved0-z.p1d).mean())*100:.1f}pp")
