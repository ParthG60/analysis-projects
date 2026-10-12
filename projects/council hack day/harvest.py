"""Harvest council data from the Council Gateway API into tidy CSVs.

Usage:
  python harvest.py --smoke          # 2 councils, 1 month
  python harvest.py                  # full: all curated councils, 3 months
"""
import argparse
import re
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from taxonomy import NOTICE_PATTERN, TOPICS, classify

API = "https://councilgateway.poteris.co.uk/council-api"
OUT = Path(__file__).parent / "data"
SLEEP = 0.15  # be polite

# Curated mix of party control. majority_party in the API is stale (pre-May-2025):
# Kent and County Durham are Reform-run but labelled CON/NOC. Overrides = actual control.
COUNCILS = [217, 238, 201, 9, 10, 191, 172, 233, 74]  # B&D (168) cut: zero usable docs; Durham (243) cut: API too slow
PARTY_OVERRIDES = {9: "REF", 243: "REF", 238: "GRN-led NOC", 10: "REF",
                   208: "LAB-led NOC"}  # Leeds NOC since May 2026, Labour minority

S = requests.Session()


def get(path, **params):
    r = S.get(f"{API}{path}", params=params, timeout=60)
    r.raise_for_status()
    time.sleep(SLEEP)
    return r.json()


def get_all(path, **params):
    items, page = [], 1
    while True:
        batch = get(path, page=page, per_page=100, **params)["items"]
        items += batch
        if len(batch) < 100:
            return items
        page += 1


def harvest(council_ids, months, out=OUT, date_from=None, date_to=None):
    date_from = date_from or (date.today() - timedelta(days=30 * months)).isoformat()
    window = {"date_from": date_from, **({"date_to": date_to} if date_to else {})}
    councils, meetings, decisions, people, doc_rows = [], [], [], [], []

    for cid in council_ids:
        c = get(f"/councils/{cid}")
        c["party"] = PARTY_OVERRIDES.get(cid, c["majority_party"])
        councils.append(c)
        print(f"== {c['name']} ({c['party']})")

        for m in get_all("/meetings", council_id=cid, **window):
            m["council_id"] = cid
            m["cancelled"] = "CANCELLED" in (m["name"] or "").upper()
            m["committee"] = re.split(r" - ", m["name"] or "")[0]
            meetings.append(m)

        for d in get_all("/decisions", council_id=cid, **window):
            d["council_id"] = cid
            decisions.append(d)

        for p in get_all("/people", council_id=cid, is_councillor=True):
            p["council_id"] = cid
            people.append(p)

        # skip statutory-notice fake "committees" (TROs etc.) — not real meetings,
        # and Bradford publishes thousands of them
        live = [
            m for m in meetings
            if m["council_id"] == cid and not m["cancelled"]
            and not re.search(NOTICE_PATTERN, m["committee"])
        ]
        print(f"   {len(live)} live meetings; fetching minutes docs...")
        for m in live:
            for doc in get_all("/documents", meeting_id=m["id"]):
                if doc.get("is_media") or doc.get("extract_status") != "success":
                    continue
                try:
                    full = get(f"/documents/{doc['id']}", include_text=True)
                    text = full.get("text") or ""
                    cls = (get(f"/documents/{doc['id']}/classifications")["items"]
                           if doc.get("is_minutes") else [])
                except Exception as e:
                    print(f"   ! doc {doc['id']}: {e}")
                    continue
                topline = attendees = ""
                if cls:
                    cls_out = cls[0].get("output") or {}
                    topline = cls_out.get("topline") or ""
                    attendees = cls_out.get("attendees") or ""
                    if isinstance(attendees, list):
                        attendees = ", ".join(attendees)
                row = {
                    "doc_id": doc["id"],
                    "council_id": cid,
                    "council": c["name"],
                    "party": c["party"],
                    "meeting_id": m["id"],
                    "meeting_name": m["name"],
                    "committee": m["committee"],
                    "date": m["date"],
                    "kind": doc.get("kind"),
                    "is_minutes": doc.get("is_minutes"),
                    "words": len(text.split()),
                    "snippet": " ".join(text.split())[:300],
                    "topline": topline,
                    "attendees": attendees,
                    "pdf_url": f"{API}/documents/{doc['id']}/file",
                }
                row.update(classify(text))
                doc_rows.append(row)
        print(f"   {len([r for r in doc_rows if r['council_id'] == cid])} docs classified")

        # incremental save after every council so a killed run keeps its progress
        out.mkdir(exist_ok=True)
        pd.DataFrame(councils).to_csv(out / "councils.csv", index=False)
        pd.DataFrame(meetings).to_csv(out / "meetings.csv", index=False)
        pd.DataFrame(decisions).to_csv(out / "decisions.csv", index=False)
        pd.DataFrame(people).to_csv(out / "people.csv", index=False)
        pd.DataFrame(doc_rows).to_csv(out / "doc_topics.csv", index=False)

    print(f"\nWrote {out}: {len(meetings)} meetings, {len(decisions)} decisions, "
          f"{len(people)} people, {len(doc_rows)} docs")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--only", type=int, nargs="*", help="council ids to harvest")
    ap.add_argument("--outdir", type=str, help="write CSVs to this dir instead of data/")
    ap.add_argument("--date-from", type=str, help="ISO date, overrides months window")
    ap.add_argument("--date-to", type=str, help="ISO date, optional window end")
    args = ap.parse_args()
    out = Path(args.outdir) if args.outdir else OUT
    if args.smoke:
        harvest([217, 74], months=1, out=out)
    else:
        harvest(args.only or COUNCILS, months=4, out=out,
                date_from=args.date_from, date_to=args.date_to)
