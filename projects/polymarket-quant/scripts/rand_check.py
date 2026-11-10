"""Random-sample validation (no volume ranking) to rule out selection bias."""
import numpy as np
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time, math

ROOT = Path(__file__).resolve().parent.parent
uni = pd.read_parquet(ROOT / "data" / "universe.parquet")
samp = uni.sample(n=2500, random_state=42)
session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})
HZ = {"p7d": 7*86400, "p3d": 3*86400, "p1d": 86400, "p6h": 21600, "p1h": 3600}


def one(r):
    end = int(float(r.close_ts))
    try:
        h = session.get("https://clob.polymarket.com/prices-history",
                        params={"market": r.token0, "startTs": end-14*86400,
                                "endTs": end, "fidelity": 1}, timeout=30).json().get("history", [])
    except Exception:
        return None
    if not h:
        return None
    ts = [x["t"] for x in h]; ps = [x["p"] for x in h]
    out = {"id": r.id, "category": r.category, "volume": r.volume, "resolved0": int(r.resolved0)}
    for lbl, sec in HZ.items():
        tgt = end - sec; price = None
        for t, p in zip(ts, ps):
            if t <= tgt: price = p
            else: break
        out[lbl] = price
    return out


rows = []
t0 = time.time()
with ThreadPoolExecutor(max_workers=6) as ex:
    for f in as_completed([ex.submit(one, r) for r in samp.itertuples()]):
        res = f.result()
        if res: rows.append(res)
df = pd.DataFrame(rows)
print(f"fetched {len(df)} of {len(samp)} in {time.time()-t0:.0f}s")
print("base rate resolved0:", round(df.resolved0.mean(), 3))

BINS = [0, .05, .10, .20, .35, .65, .80, .90, .95, 1.0001]
LAB = ["0-5", "5-10", "10-20", "20-35", "35-65", "65-80", "80-90", "90-95", "95-100"]
for h in ["p3d", "p1d"]:
    d = df.dropna(subset=[h]).copy()
    d["b"] = pd.cut(d[h], BINS, labels=LAB, right=False)
    g = d.groupby("b", observed=True).agg(n=("resolved0", "size"), implied=(h, "mean"), realised=("resolved0", "mean"))
    g["edge_pp"] = (g.realised - g.implied)*100
    print(f"\n--- random sample, horizon {h} ---")
    print(g[g.n >= 15].round(3).to_string())
    print(f"global: mean_price={d[h].mean():.3f} mean_resolved={d.resolved0.mean():.3f}")
PY = None
df.to_json(ROOT / "data" / "random_sample.jsonl", orient="records", lines=True)
