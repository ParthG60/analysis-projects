"""Audit & Governance committee scan via Council Gateway -> data_england/audit_scan.csv.

For each council with a Gateway id we:
  1. find its audit/governance committee (name match, preferring audit + governance),
  2. get its most recent meeting (date + link),
  3. probe the council's document corpus for high-consequence audit language
     (Section 24 public-interest reports, statutory recommendations, limited
     assurance opinions, disclaimed opinions) via the full-text search endpoint,
     counting only hits whose meeting belongs to the audit committee.

Cached under data_england/audit_cache/ so re-runs are cheap and resumable.
Usage: python audit_scan.py [--refresh] [CouncilName ...]
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
ENG_DIR = BASE / "data_england"
CACHE_DIR = ENG_DIR / "audit_cache"
OUT = ENG_DIR / "audit_scan.csv"
API = "https://councilgateway.poteris.co.uk/council-api"
SLEEP = 0.12

# High-signal phrases only. Each maps a search query to a short label.
FLAG_QUERIES = [
    ("Section 24", "Section 24 report"),
    ("statutory recommendation", "statutory recommendation"),
    ("limited assurance", "limited assurance"),
    ("disclaimed opinion", "disclaimed opinion"),
    ("public interest report", "public interest report"),
]

AUDIT_RE = re.compile(r"audit", re.I)
GOV_RE = re.compile(r"governance|standards|risk", re.I)
# committees that merely contain "audit" but aren't the assurance committee
EXCLUDE_RE = re.compile(r"scrutiny|overview|housing|pension|education|health|licensing", re.I)


def get(path, **params):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "council-receipts/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            return data
        except Exception as e:
            last = e
            time.sleep(0.4 * (attempt + 1))
    raise last


def pick_committee(committees):
    cands = [c for c in committees if AUDIT_RE.search(c.get("name") or "")]
    cands = [c for c in cands if not EXCLUDE_RE.search(c.get("name") or "")]
    if not cands:
        return None
    # prefer names that also mention governance / standards / risk
    cands.sort(key=lambda c: (0 if GOV_RE.search(c["name"]) else 1, len(c["name"])))
    return cands[0]


def scan_council(gid, refresh=False):
    cache = CACHE_DIR / f"c{gid}.json"
    if cache.exists() and not refresh:
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass
    out = {"gateway_id": gid}
    try:
        committees = get(f"/councils/{gid}/committees", per_page=100).get("items", [])
        cm = pick_committee(committees)
        if not cm:
            out["error"] = "no audit committee"
            cache.write_text(json.dumps(out))
            return out
        out["committee_id"] = cm["id"]
        out["committee_name"] = cm["name"]
        meetings = get("/meetings", committee_id=cm["id"], per_page=5).get("items", [])
        # newest first: the API returns them unsorted, so sort by date desc
        def mdate(m):
            return m.get("date") or ""
        meetings = [m for m in meetings if m.get("date")]
        meetings.sort(key=mdate, reverse=True)
        if meetings:
            latest = get(f"/meetings/{meetings[0]['id']}")
            out["latest_date"] = (latest.get("date") or "")[:10]
            out["latest_url"] = latest.get("url")
            out["latest_name"] = latest.get("name")
        out["n_meetings"] = len(meetings)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        cache.write_text(json.dumps(out))
        return out

    # full-text flags, restricted to the audit committee's own meetings.
    # The Gateway search is loose (token-based), so we re-check that every word of
    # the query actually appears in the highlighted snippet before counting a hit.
    flags = []
    cname = (out.get("committee_name") or "").lower()
    for q, label in FLAG_QUERIES:
        try:
            res = get("/search", q=q, council_id=gid, size=50)
        except Exception:
            continue
        toks = re.findall(r"[a-z0-9]+", q.lower())
        n = 0
        sample_url = None
        for h in res.get("hits", []):
            src = h.get("source") or {}
            mname = (src.get("meeting_name") or "").lower()
            if cname and cname[:20] not in mname:
                continue
            snip = " ".join((h.get("highlight") or {}).get("text", []))
            snip = re.sub(r"</?strong>", "", snip).lower()
            if not all(t in snip for t in toks):
                continue
            n += 1
            if not sample_url:
                sample_url = (h.get("record") or {}).get("url")
        if n:
            flags.append({"label": label, "n": n, "url": sample_url})
    out["flags"] = flags
    cache.write_text(json.dumps(out))
    return out


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    refresh = "--refresh" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    nm = pd.read_csv(ENG_DIR / "name_map.csv")
    nm = nm[nm["gateway_id"].notna()].copy()
    if args:
        nm = nm[nm["gateway_name"].isin(args) | nm["ons_code"].isin(args)]

    from concurrent.futures import ThreadPoolExecutor, as_completed
    jobs = [(int(r.gateway_id), r.ons_code, r.gateway_name) for r in nm.itertuples()]
    rows = []
    total = len(jobs)
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(scan_council, gid, refresh): (gid, code, name) for gid, code, name in jobs}
        for fut in as_completed(futs):
            gid, code, name = futs[fut]
            done += 1
            try:
                res = fut.result()
            except Exception as e:
                res = {"gateway_id": gid, "error": f"{type(e).__name__}: {e}"}
            res["ons_code"] = code
            res["council"] = name
            rows.append(res)
            status = res.get("error") or f"{res.get('committee_name','?')[:38]} | {res.get('latest_date','?')} | {len(res.get('flags',[]))} flags"
            print(f"[{done}/{total}] {name}: {status}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    n_ok = df["error"].isna().sum() if "error" in df else len(df)
    n_flags = df["flags"].apply(lambda f: bool(f) if isinstance(f, list) else False).sum() if "flags" in df else 0
    print(f"\nwrote {OUT}: {len(df)} councils, {n_ok} scanned, {n_flags} with flags")


if __name__ == "__main__":
    main()
