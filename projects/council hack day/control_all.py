"""Current political control for all 282 councils, from Open Council Data UK's
public-domain compositions file (data_england/ocd_compositions_2016-26.csv,
downloaded 2026-08-23, source last updated 2026-08-21).

Democracy Club publishes election results/candidates, not a clean current-control
table; OCD's `majority` column gives it directly. Joined to our councils by name.

Output data_england/control_all.csv:
  ons_code, council, majority_raw, bucket, control_label, since_year, changed, previous_label
Usage: python control_all.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).parent
LATEST = "2026"

# our gateway name -> OCD `authority` name, for the 3 that differ
NAME_OVERRIDE = {
    "Bournemouth": "Bournemouth, Christchurch and Poole",
    "County Durham": "Durham",
    "Kingston upon Hull, City of": "Kingston upon Hull",
}

# normalise old-year spellings to the recent party codes
ALIAS = {"GREEN": "GRN", "PLAID": "PC"}
# leading party token -> National-view bucket
BUCKET = {"LAB": "Labour", "CON": "Conservative", "LD": "Liberal Democrat",
          "REF": "Reform UK", "GRN": "Green"}
SPELL = {"LAB": "Labour", "CON": "Conservative", "LD": "Liberal Democrat",
         "REF": "Reform UK", "GRN": "Green", "IND": "Independent",
         "PC": "Plaid Cymru", "SNP": "SNP"}


def spell(tok):
    return SPELL.get(tok, tok.title() if tok else tok)


def lead_token(maj):
    """First party code in a majority label, upper-cased so mixed-case old-year
    labels ('Lab plurality') match recent ones ('LAB min'). -> 'LAB', 'LD', ..."""
    if not maj or maj in ("NULL", "TBC"):
        return None
    tok = maj.replace("/", " ").split()[0].upper()
    return ALIAS.get(tok, tok)


def bucket_of(maj):
    return BUCKET.get(lead_token(maj), "Independent/Other")


def _is_noc(maj):
    """Minority / plurality / coalition = no overall control."""
    low = maj.lower()
    return low.endswith("min") or "plurality" in low or "/" in maj


def label_of(maj):
    """Readable control line."""
    if not maj or maj in ("NULL", "TBC"):
        return "No overall control"
    tok = lead_token(maj)
    party = spell(tok)
    if maj.endswith("Mayor"):
        return f"{party} (elected mayor)"
    if "/" in maj:
        parts = []
        for p in maj.split("/"):
            tok = p.strip()
            tok = re.sub(r"\s*(min|max|plurality|majority)\s*$", "", tok, flags=re.I)
            tok = ALIAS.get(tok.upper(), tok.upper())
            if tok:
                parts.append(spell(tok))
        return "No overall control (" + " / ".join(parts) + ")"
    if _is_noc(maj):
        return f"No overall control ({party}-led)"
    return party  # clear single-party majority


# OCD compositions, indexed by (authority, year) -> majority
ocd = {}
with open(ROOT / "data_england" / "ocd_compositions_2016-26.csv", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        ocd[(r["authority"], r["year"])] = r["majority"]
years = sorted({y for (_, y) in ocd}, reverse=True)  # 2026, 2025, ...

# master registry from the IMD scorecard (ons_code, council)
registry = {}
with open(ROOT / "data_england" / "scorecard_imd.csv", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        registry.setdefault(r["ons_code"], r["council"])

rows, missing = [], []
for code, name in registry.items():
    ocd_name = NAME_OVERRIDE.get(name, name)
    maj = ocd.get((ocd_name, LATEST))
    if maj is None:
        missing.append(name)
        continue
    bucket = bucket_of(maj)
    # since_year: walk back while the bucket is unchanged
    since = int(LATEST)
    prev_label = None
    for y in years:
        m = ocd.get((ocd_name, y))
        if m is None:
            break
        if bucket_of(m) == bucket:
            since = int(y)
        else:
            prev_label = label_of(m)
            break
    changed = prev_label is not None
    rows.append({
        "ons_code": code, "council": name, "majority_raw": maj,
        "bucket": bucket, "control_label": label_of(maj),
        "since_year": since, "changed": changed,
        "previous_label": prev_label or "",
    })

with open(ROOT / "data_england" / "control_all.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["ons_code", "council", "majority_raw", "bucket",
                                       "control_label", "since_year", "changed", "previous_label"])
    w.writeheader()
    w.writerows(rows)

from collections import Counter
print(f"data_england/control_all.csv: {len(rows)}/{len(registry)} councils")
if missing:
    print(f"  MISSING ({len(missing)}): {missing}")
print("  bucket distribution:")
for k, v in Counter(r["bucket"] for r in rows).most_common():
    print(f"    {v:>4}  {k}")
