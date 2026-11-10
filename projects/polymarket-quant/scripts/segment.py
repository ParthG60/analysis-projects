"""Segment the favourite-longshot edge by market type / structure."""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
h = pd.read_json(ROOT / "data" / "horizons.jsonl", lines=True)
u = pd.read_parquet(ROOT / "data" / "universe.parquet")
h["id"] = h["id"].astype(str)
u["id"] = u["id"].astype(str)
df = h.merge(u[["id", "neg_risk", "ticker", "question", "outcome0"]], on="id", how="left")

rng = np.random.default_rng(0)
def ci(x, n=2000):
    x = np.asarray(x, float)
    if len(x) < 10: return (np.nan, np.nan)
    s = [rng.choice(x, len(x), replace=True).mean() for _ in range(n)]
    return np.percentile(s, [2.5, 97.5])

MID = (.05, .35)

def edge(d, hz="p1d"):
    d = d.dropna(subset=[hz])
    z = d[d[hz].between(*MID)]
    if len(z) < 10: return None
    e = (z.resolved0 - z[hz]).values
    lo, hi = ci(e)
    return dict(n=len(z), implied=round(z[hz].mean(), 3), realised=round(z.resolved0.mean(), 3),
                edge_pp=round(e.mean()*100, 1), ci=f"[{lo*100:.0f},{hi*100:.0f}]")

print("="*86)
print("MID-BUCKET (0.05-0.35) EDGE, horizon p1d, by segment")
print("="*86)

print("\n-- by category --")
rows = [dict(seg=c, **(edge(g) or {})) for c, g in df.groupby("category")]
print(pd.DataFrame([r for r in rows if r.get("n")]).sort_values("edge_pp", ascending=False).to_string(index=False))

print("\n-- multi-outcome (negRisk) vs single --")
for label, g in [("negRisk (multi-outcome)", df[df.neg_risk == True]), ("single", df[df.neg_risk == False])]:
    e = edge(g)
    print(f"  {label}: {e}" if e else f"  {label}: n/a")

print("\n-- by lifespan --")
df["life_q"] = pd.qcut(df.lifespan_h, 4, labels=["<2d", "2-10d", "10-60d", ">60d"])
for q, g in df.groupby("life_q", observed=True):
    e = edge(g); print(f"  {str(q):>8}: {e}")

print("\n-- by volume --")
df["vol_q"] = pd.qcut(df.volume, 4, labels=["v_low", "v_mid", "v_hi", "v_top"])
for q, g in df.groupby("vol_q", observed=True):
    e = edge(g); print(f"  {q:>6}: {e}")

print("\n-- by question pattern (regex) --")
PATS = {
    "nominee / nomination": r"nominee|nomination",
    "championship / title / win the": r"championship|title|win the|to win",
    "to win (league/cup)": r" to win ",
    "by <date> (deadline 'will X by')": r"\bby (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* \d",
    "election / vote": r"election|vote|electoral|referendum",
    "price / crypto level": r"bitcoin|ethereum|price|above|below|hit \d|\$",
    "qualify / advance / reach": r"qualify|advance|reach the|make the",
    "appear / happen / agree": r"agree|deal|meet|visit|appear|endorse|pardon",
}
for name, pat in PATS.items():
    g = df[df.question.fillna("").str.lower().str.contains(pat, regex=True)]
    e = edge(g); print(f"  {name:<34}: {e}")

print("\n" + "="*86)
print("TOP TICKERS by mid-bucket edge (n>=25)")
print("="*86)
rows = []
for t, g in df.groupby("ticker"):
    e = edge(g)
    if e and e["n"] >= 25:
        rows.append(dict(ticker=t, **e))
t = pd.DataFrame(rows).sort_values("edge_pp", ascending=False)
print(t.head(15).to_string(index=False))
