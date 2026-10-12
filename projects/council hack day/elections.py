"""Democracy Club Elections API -> data/elections.csv (upcoming elections for our councils).

Fetches every current/upcoming election, maps Democracy Club organisation slugs onto
our 283-council registry by name, and keeps only polls that have not yet happened.
Output columns: council, election_id, title, poll_date (matches the site's loader).

Usage: python elections.py
"""
import csv
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
OUT = ROOT / "data"
API = "https://elections.democracyclub.org.uk/api/elections/?current=1"

# Democracy Club slug -> our registry name, where the slug does not slugify our name.
SLUG_OVERRIDES = {
    "bournemouth-christchurch-and-poole": "Bournemouth",
    "durham": "County Durham",
    "kingston-upon-hull": "Kingston upon Hull, City of",
}


def slugify(name):
    n = str(name).lower().replace("&", "and").replace(".", "").replace(",", "")
    n = re.sub(r"\s+", " ", n).strip()
    return n.replace(" ", "-")


def load_registry():
    df = pd.read_csv(ROOT / "data_england" / "scorecard_imd.csv").drop_duplicates("ons_code")
    return dict(zip(df["council"], df["ons_code"]))


def fetch_current():
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return data.get("results", [])


def main():
    registry = load_registry()
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    by_slug = {slugify(n): n for n in registry}
    by_slug.update({s: c for s, c in SLUG_OVERRIDES.items() if c in registry})

    results = fetch_current()
    rows, seen = [], set()
    for e in results:
        if e.get("cancelled"):
            continue
        poll = e.get("poll_open_date") or ""
        if poll < today:
            continue  # never advertise a poll that has already closed
        slug = (e.get("organisation") or {}).get("slug")
        council = by_slug.get(slug)
        if not council:
            continue
        key = (council, e["election_id"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "council": council,
            "election_id": e["election_id"],
            "title": e.get("election_title") or "Local election",
            "poll_date": poll,
        })

    # Democracy Club returns an org-level placeholder alongside the real contest
    # for the same council/date (e.g. "Lambeth local election" + "…Myatt's Fields
    # by-election"). Keep one per council/date, preferring the specific contest.
    deduped = {}
    for r in rows:
        key = (r["council"], r["poll_date"])
        prev = deduped.get(key)
        if prev is None or ("by-election" in r["title"].lower() and "by-election" not in prev["title"].lower()):
            deduped[key] = r
    rows = list(deduped.values())

    rows.sort(key=lambda r: (r["poll_date"], r["council"]))
    OUT.mkdir(exist_ok=True)
    with open(OUT / "elections.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["council", "election_id", "title", "poll_date"])
        w.writeheader()
        w.writerows(rows)

    print(f"data/elections.csv: {len(rows)} upcoming elections across "
          f"{len({r['council'] for r in rows})} councils")
    for r in rows:
        print(f"  {r['council']}: {r['title']} on {r['poll_date']}")


if __name__ == "__main__":
    main()
