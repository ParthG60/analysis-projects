"""Diagnostics to validate the calibration result before trusting it."""
import json
import numpy as np
import pandas as pd
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_json(ROOT / "data" / "horizons.jsonl", lines=True)

for h in ["p3d", "p1d"]:
    d = df.dropna(subset=[h])
    print(f"{h}: mean_price={d[h].mean():.4f}  mean_resolved={d.resolved0.mean():.4f}  "
          f"n={len(d)}  Brier={np.mean((d[h]-d.resolved0)**2):.4f}")

# distribution checks
d = df.dropna(subset=["p1d"])
print("\nprice p1d describe:\n", d["p1d"].describe().round(3).to_string())

# how many markets have token0 price >= 0.5 at 1d but resolved0 == 0 (should be allowed)
print("\nsanity: share with p1d>=0.5 and resolved0==0:",
      ((d.p1d >= 0.5) & (d.resolved0 == 0)).mean().round(3))

# concrete examples: low price winners
print("\n--- 8 markets with p1d in [0.05,0.20] that RESOLVED YES ---")
ex = d[(d.p1d.between(0.05, 0.20)) & (d.resolved0 == 1)]
print(ex[["id", "category", "p1d", "p3d", "p7d", "resolved0", "volume"]].head(8).to_string(index=False))

print("\n--- 8 markets with p1d in [0.05,0.20] that resolved NO ---")
ex2 = d[(d.p1d.between(0.05, 0.20)) & (d.resolved0 == 0)]
print(ex2[["id", "category", "p1d", "p3d", "p7d", "resolved0", "volume"]].head(8).to_string(index=False))

# pull one live example and verify against the actual market + price path
uni = pd.read_parquet(ROOT / "data" / "universe.parquet").set_index("id")
row = ex.iloc[0]
mid = row["id"]
m = uni.loc[mid]
print(f"\n=== VERIFY market {mid} ===")
print("question:", m["question"], "| outcome0:", m["outcome0"], "| resolved0:", m["resolved0"])
print("token0:", m["token0"])
end = int(float(m["close_ts"]))
r = requests.get("https://clob.polymarket.com/prices-history",
                 params={"market": m["token0"], "startTs": end - 3*86400,
                         "endTs": end, "fidelity": 60}, timeout=30).json()["history"]
print("first:", r[0], "last:", r[-1], "n:", len(r))
print("price at ~close-1d:", [x for x in r if x["t"] <= end-86400][-1])
