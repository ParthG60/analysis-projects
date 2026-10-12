"""Contracts Finder (Crown Commercial Service) -> data_england/contracts.csv.

For each English council we query the Contracts Finder legacy search API by council
name, keep only notices whose *buyer* organisation is that council, and aggregate
awarded contracts (dated 2025 onward) by supplier. Output is long format, one row
per (council, supplier) with total awarded value and contract count, capped to the
top suppliers per council.

API: POST https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json
Free, keyless. Results cached under data_england/contracts_cache/ so re-runs are cheap.

Usage:
    python england_contracts.py            # all councils (uses cache)
    python england_contracts.py --refresh  # ignore cache, refetch everything
    python england_contracts.py Sheffield Camden   # only named councils (for testing)
"""
from pathlib import Path
import html
import json
import re
import sys
import time
import urllib.request

import pandas as pd

OUT_DIR = Path(__file__).parent / "data_england"
CACHE_DIR = OUT_DIR / "contracts_cache"
API = "https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json"
TOP_N = 5
SIZE = 200          # API accepts >100; needed to capture recent high-value awards
MIN_CONTRACTS = 1  # councils with >=1 matched award get a supplier panel
PUBLISHED_FROM = "2025-01-01T00:00:00Z"  # recency window; older awards are stale for a citizen site
MIN_AWARD_DATE = "2025-01-01"  # keep only awards on/after this date (publishedDate fallback)
PORTALS_CSV = OUT_DIR / "council_portals.csv"  # ons_code -> official_name (+ portal_url)

_PREFIXES = ["the borough council of", "borough council of", "the council of the borough of",
             "london borough of", "royal borough of", "metropolitan borough of",
             "the city of", "city of", "county of", "the"]
_SUFFIXES = ["metropolitan borough council", "metropolitan district council",
             "london borough council", "city council", "county council",
             "district council", "borough council", "unitary authority", "council"]
_ALIASES = {"durham": "county durham", "bournemouth christchurch and poole": "bournemouth",
            "kingston upon hull": "kingston upon hull city of",
            "hull": "kingston upon hull city of"}


def normalise(name):
    # Unescape FIRST: some buyer names arrive as "Hammersmith &amp; Fulham", and
    # replacing "&" before unescaping would corrupt them to "andamp;".
    n = html.unescape(str(name)).strip().lower().replace("&", "and").replace(".", "").replace(",", "")
    n = re.sub(r"\s+", " ", n)
    for pre in _PREFIXES:
        if n.startswith(pre + " "):
            n = n[len(pre) + 1:].strip()
            break
    for suf in _SUFFIXES:
        if n.endswith(" " + suf):
            n = n[: -(len(suf) + 1)].strip()
            break
    return _ALIASES.get(n, n)


def query(keyword):
    body = json.dumps({
        "searchCriteria": {"types": ["Contract"], "keyword": keyword, "statuses": ["Awarded"],
                           "publishedFrom": PUBLISHED_FROM},
        "size": SIZE,
    }).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read().decode())
    time.sleep(0.4)  # be polite to Contracts Finder
    return data


def candidate_terms(council, official_name=None):
    """Quoted phrases likely to surface this council as the *buyer*.
    The API keyword-searches the whole notice text, so we cast the strongest phrasing
    (the official register name, e.g. 'Manchester City Council') and filter on
    organisationName in aggregate()."""
    primary = official_name or council
    terms = [f'"{primary}"']
    if official_name and official_name != council:
        terms.append(f'"{council}"')
    return terms


def fetch_council(council, official_name=None, refresh=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{normalise(council).replace(' ', '_')}.json"
    if cache.exists() and not refresh:
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass
    merged, seen = [], set()
    for term in candidate_terms(council, official_name):
        try:
            data = query(term)
        except Exception as e:
            print(f"  {council}: API error on {term!r} ({e})")
            continue
        for n in data.get("noticeList", []):
            it = n["item"]
            nid = it.get("id") or it.get("noticeIdentifier")
            if nid in seen:
                continue
            seen.add(nid)
            merged.append(it)
    if not merged:
        return None
    cache.write_text(json.dumps(merged))
    return merged


_PLACEHOLDER_SUPPLIERS = {
    "various", "n/a", "na", "tbc", "to be confirmed", "not applicable",
    "please see webpage for contract award details", "see award details",
}


def _award_date(it, today):
    """Best honest award date: prefer awardedDate, but fall back to publishedDate when
    awardedDate is missing or implausibly in the future (data-entry errors exist: some
    notices carry a contract *end* year as the award date)."""
    awarded = (it.get("awardedDate") or "")[:10]
    published = (it.get("publishedDate") or "")[:10]
    if awarded and awarded <= today:
        return awarded
    return published


def aggregate(council, notices):
    """Top individual contract awards for this council (one notice = one row), so the
    displayed value always matches the notice the link opens. Sorted by value desc."""
    want = normalise(council)
    seen_awards = set()  # content-keyed, to collapse Contracts Finder re-publications
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    awards = []
    for it in notices:
        buyer = normalise(it.get("organisationName") or "")
        if buyer != want:
            continue
        d = _award_date(it, today)
        if d < MIN_AWARD_DATE:
            continue  # keep the panel to awards from 2025 onward
        supplier = html.unescape((it.get("awardedSupplier") or "").strip())
        # Skip multi-supplier framework lots (dozens of comma-separated names),
        # placeholder/non-supplier strings, and zero-value awards: all would
        # misrepresent who the council actually pays.
        if not supplier or "," in supplier or supplier.lower() in _PLACEHOLDER_SUPPLIERS:
            continue
        value = it.get("awardedValue") or 0
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        if value <= 0:
            continue
        # Contracts Finder often carries the same award twice under two notice ids
        # (a correction/re-publication: identical supplier, title, value and award
        # date, days apart). Dedupe on that content.
        title = html.unescape((it.get("title") or "").strip())
        award_key = (supplier.lower(), title.lower(), value, d)
        if award_key in seen_awards:
            continue
        seen_awards.add(award_key)
        awards.append({
            "council": council, "supplier": supplier, "total_value_gbp": round(value, 0),
            "n_contracts": 1, "latest_award": d,
            "top_notice_id": it.get("id"), "top_title": title,
        })
    awards.sort(key=lambda r: -r["total_value_gbp"])
    return awards[:TOP_N]


def _official_names():
    if not PORTALS_CSV.exists():
        return {}
    df = pd.read_csv(PORTALS_CSV)
    return dict(zip(df["ons_code"], df["official_name"]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refresh = "--refresh" in sys.argv
    official = _official_names()

    reg = pd.read_csv(OUT_DIR / "scorecard_imd.csv").drop_duplicates("ons_code")[["ons_code", "council"]]
    if args:
        reg = reg[reg["council"].isin(args)]

    all_rows = []
    for i, (_, rr) in enumerate(reg.iterrows(), 1):
        council = rr["council"]
        notices = fetch_council(council, official.get(rr["ons_code"]), refresh=refresh)
        if notices is None:
            continue
        agg = aggregate(council, notices)
        n = sum(r["n_contracts"] for r in agg)
        if n >= MIN_CONTRACTS:
            for r in agg:
                r["ons_code"] = rr["ons_code"]
            all_rows.extend(agg)
        if i % 25 == 0:
            print(f"  ... {i}/{len(reg)} councils")

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_DIR / "contracts.csv", index=False)
    n_councils = df["ons_code"].nunique() if not df.empty else 0
    print(f"data_england/contracts.csv: {len(df)} rows, {n_councils} councils "
          f"with >= {MIN_CONTRACTS} matched contracts")


if __name__ == "__main__":
    main()
