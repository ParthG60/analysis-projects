"""Merge side-harvest dirs into data/ — run ONLY after the main harvest has stopped.

Usage: python merge_th.py data_th data_rest ...
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
KEYS = {"councils.csv": "id", "meetings.csv": "id", "decisions.csv": "id", "doc_topics.csv": "doc_id"}

for side in sys.argv[1:]:
    for name, key in KEYS.items():
        main = pd.read_csv(BASE / "data" / name)
        extra = pd.read_csv(BASE / side / name)
        merged = pd.concat([main, extra]).drop_duplicates(subset=key, keep="last")
        merged.to_csv(BASE / "data" / name, index=False)
        print(f"{side}/{name}: {len(main)} + {len(extra)} -> {len(merged)}")
