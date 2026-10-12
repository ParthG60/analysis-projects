"""Resumable all-England harvest shard: python england_runner.py <shard> <of>.

Each council goes to data_england/c<id>/ (skipped if doc_topics.csv already there,
unless FORCE=1), so a killed shard resumes where it left off. One council failing
= one FAIL line.

Window: rolling 12 months ending at the most recent completed month. Override with
DATE_FROM / DATE_TO env vars (ISO dates).
"""
import json
import os
import sys
import traceback
from datetime import date
from pathlib import Path

from harvest import harvest

BASE = Path(__file__).parent
OUT = Path(os.environ.get("OUT_DIR") or (BASE / "data_england"))
FORCE = os.environ.get("FORCE") == "1"

today = date.today()
# End at the most recent completed month; default window = trailing 12 months.
_date_to = os.environ.get("DATE_TO") or date(today.year, today.month, 1).isoformat()
_start_month = today.month - 12
_start_year = today.year + (_start_month - 1) // 12
_start_month = (_start_month - 1) % 12 + 1
_date_from = os.environ.get("DATE_FROM") or date(_start_year, _start_month, 1).isoformat()

shard, of = int(sys.argv[1]), int(sys.argv[2])
ids = json.load(open(BASE / "data_england" / "england_ids.json"))
mine = [c for i, c in enumerate(ids) if i % of == shard]
print(f"shard {shard}/{of}: {len(mine)} councils | window {_date_from} -> {_date_to}", flush=True)

for n, cid in enumerate(mine):
    cdir = OUT / f"c{cid}"
    if not FORCE and (cdir / "doc_topics.csv").exists():
        print(f"SKIP {cid} (done)", flush=True)
        continue
    try:
        harvest([cid], months=12, out=cdir, date_from=_date_from, date_to=_date_to)
        print(f"OK {cid} ({n + 1}/{len(mine)})", flush=True)
    except Exception:
        print(f"FAIL {cid}: {traceback.format_exc(limit=1)}", flush=True)

print(f"SHARD {shard} DONE", flush=True)
