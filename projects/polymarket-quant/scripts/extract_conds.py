"""Extract id -> conditionId (and token ids) map from the raw full dump.

Streams data/raw_markets_win1k.jsonl once (6.8 GB) and writes a compact parquet.
Output: data/conds_full.parquet  [id, condition_id, token0, token1]
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_markets_win1k.jsonl"
OUT = ROOT / "data" / "conds_full.parquet"

rows = []
for line in RAW.open():
    try:
        m = json.loads(line)
    except Exception:
        continue
    toks = m.get("clobTokenIds")
    try:
        toks = json.loads(toks) if toks else []
    except Exception:
        toks = []
    rows.append({
        "id": str(m.get("id")),
        "condition_id": m.get("conditionId"),
        "token0": toks[0] if len(toks) == 2 else None,
        "token1": toks[1] if len(toks) == 2 else None,
    })

df = pd.DataFrame(rows).drop_duplicates(subset="id")
df = df[df.condition_id.notna()]
df.to_parquet(OUT, index=False)
print(f"wrote {len(df)} conditionIds -> {OUT}")
