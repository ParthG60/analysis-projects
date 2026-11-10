"""Crawl the full Polymarket event catalog for authoritative taxonomy.

Source: Gamma /events/keyset (after_cursor pagination, unlike /events which
422s past offset ~2100).

Stores lightweight event metadata (category, tags, series) plus the
market_id -> event_id linkage embedded in each event's `markets` array.

Outputs
-------
data/events_full.jsonl         one event per line:
    {event_id, ticker, slug, title, category, tags, series, end_date,
     closed_time, volume}
data/market_event_map.jsonl    one market per line:
    {market_id, event_id}

Resumable: re-reads the cursor state file if present.
"""
import json
import time
import argparse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_EV = ROOT / "data" / "events_full.jsonl"
OUT_MAP = ROOT / "data" / "market_event_map.jsonl"
STATE = ROOT / "data" / "_events_cursor.txt"
LOG = ROOT / "logs" / "fetch_events_full.out"

BASE = "https://gamma-api.polymarket.com/events/keyset"

session = requests.Session()
session.headers.update({"User-Agent": "research/1.0"})


def log(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end-min", default="2024-06-01T00:00:00Z")
    ap.add_argument("--vol-min", type=float, default=1000.0)
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    cursor = STATE.read_text().strip() if STATE.exists() else None
    ev_f = OUT_EV.open("a")
    map_f = OUT_MAP.open("a")

    params = {
        "closed": "true",
        "end_date_min": args.end_min,
        "volume_min": args.vol_min,
        "limit": args.limit,
    }

    n_ev = 0
    n_mk = 0
    t0 = time.time()
    while True:
        p = dict(params)
        if cursor:
            p["after_cursor"] = cursor
        j = None
        for attempt in range(5):
            try:
                r = session.get(BASE, params=p, timeout=40)
                if r.status_code == 200:
                    j = r.json()
                    break
                if r.status_code in (429, 500, 502, 503):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                log(f"status {r.status_code} on cursor={cursor}")
                time.sleep(2)
            except Exception as e:
                time.sleep(1.5 * (attempt + 1))
        if j is None:
            log("gave up on page, sleeping 5s")
            time.sleep(5)
            continue

        events = j.get("events", [])
        if not events:
            break
        for ev in events:
            eid = str(ev.get("id"))
            series = ev.get("series") or []
            tags = ev.get("tags") or []
            ev_f.write(json.dumps({
                "event_id": eid,
                "ticker": ev.get("ticker"),
                "slug": ev.get("slug"),
                "title": ev.get("title"),
                "category": ev.get("category"),
                "tags": [t.get("label") for t in tags if t.get("label")],
                "tag_slugs": [t.get("slug") for t in tags if t.get("slug")],
                "series": [s.get("title") for s in series if s.get("title")],
                "series_slugs": [s.get("slug") for s in series if s.get("slug")],
                "volume": ev.get("volume"),
                "end_date": ev.get("endDate"),
                "closed_time": ev.get("closedTime"),
            }) + "\n")
            n_ev += 1
            for mk in ev.get("markets") or []:
                mid = mk.get("id")
                if mid is not None:
                    map_f.write(json.dumps({"market_id": str(mid), "event_id": eid}) + "\n")
                    n_mk += 1
        ev_f.flush()
        map_f.flush()

        cursor = j.get("next_cursor")
        if not cursor:
            break
        STATE.write_text(cursor)

        if n_ev % 2000 < len(events):
            rate = n_ev / max(time.time() - t0, 1)
            log(f"events={n_ev} markets={n_mk} rate={rate:.0f}/s")

    log(f"DONE events={n_ev} markets={n_mk} in {time.time()-t0:.0f}s")
    ev_f.close()
    map_f.close()


if __name__ == "__main__":
    main()
