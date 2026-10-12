"""Local Government & Social Care Ombudsman (LGO) annual complaints data ->
data_england/ombudsman.csv.

Source (published July each year, one national CSV, all English councils):
  https://www.lgo.org.uk/information-centre/reports/annual-review-reports/local-government-complaint-reviews

For each council we take, from the "Complaints Decided" and "Remedy & Compliance
Outcomes" sheets:
  - upheld:            number of complaints upheld
  - uphold_rate:       % of investigated decisions that were upheld
  - uphold_rate_peer:  average uphold rate of "similar authorities" (LGO's own peer group)
  - per_100k:          upheld decisions per 100,000 residents
  - per_100k_peer:     peer average upheld decisions per 100k
  - compliance_rate:   % of recommendations the council implemented to LGO's satisfaction
  - complaints_total:  total complaints/enquiries decided

Joined to our ONS codes by normalising the LGO authority name. Usage:
    python england_ombudsman.py
"""
from pathlib import Path
import io
import re
import urllib.request

import pandas as pd

OUT_DIR = Path(__file__).parent / "data_england"

YEAR = "24-25"
DECIDED_URL = "https://www.lgo.org.uk/assets/attach/6818/2-Complaints-Decided-24-25.csv"
OUTCOMES_URL = "https://www.lgo.org.uk/assets/attach/6821/3-Remedy-Compliance-Outcomes-24-25.csv"

# suffixes that differ between LGO naming and our registry naming.
# longest first so "metropolitan borough council" is stripped before "borough council"
_SUFFIXES = [
    "metropolitan borough council", "metropolitan district council",
    "london borough council", "city council", "county council",
    "district council", "borough council", "unitary authority", "council",
]
# leading phrases LGO uses that our registry does not
_PREFIXES = [
    "london borough of", "royal borough of", "metropolitan borough of",
    "the city of", "city of", "county of", "the",
]
# LGO name -> our registry name, for genuinely different labels.
# Keys/values are comma-free because normalise() strips commas.
_ALIASES = {
    "durham": "county durham",
    "herefordshire": "county of herefordshire",
    "kingston upon hull": "kingston upon hull city of",
    "bournemouth christchurch and poole": "bournemouth",
}


def normalise(name):
    n = str(name).strip().lower()
    n = n.replace("&", "and").replace(".", "").replace(",", "")
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


def fetch_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_decided(content):
    """LGO sheets have a 2-row banner then a 2-row header. Locate 'Authority Name'."""
    raw = pd.read_csv(io.BytesIO(content), header=None)
    hdr = None
    for i in range(len(raw)):
        if str(raw.iloc[i, 0]).strip() == "Authority Name":
            hdr = i
            break
    if hdr is None:
        raise ValueError("could not find 'Authority Name' header in LGO decided sheet")
    cols = raw.iloc[hdr].tolist()
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in cols]
    df = df[df["Authority Name"].notna()]
    return df


def pct(v):
    if pd.isna(v):
        return None
    return float(str(v).replace("%", "").strip()) if str(v).strip() else None


def num(v):
    if pd.isna(v):
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def main():
    decided = parse_decided(fetch_csv(DECIDED_URL))
    outcomes = parse_decided(fetch_csv(OUTCOMES_URL))

    # normalise column access by position-independent label matching
    def col(df, *needles):
        for c in df.columns:
            low = c.lower()
            if all(n in low for n in needles):
                return c
        return None

    d_name = "Authority Name"
    d_total = col(decided, "total")
    d_upheld = col(decided, "upheld") if col(decided, "upheld") else None
    # 'Upheld' exact column (there is also 'Not Upheld' and 'Upheld decisions per 100,000')
    d_upheld = None
    d_per100 = None
    d_per100_peer = None
    d_rate = None
    d_rate_peer = None
    for c in decided.columns:
        low = c.lower()
        if low == "upheld":
            d_upheld = c
        elif "per 100,000 residents" in low and "average" not in low and "upheld" in low:
            d_per100 = c
        elif "per 100,000 residents" in low and "average" in low:
            d_per100_peer = c
        elif low == "uphold rate (%)":
            d_rate = c
        elif "average uphold rate" in low:
            d_rate_peer = c

    o_rate = col(outcomes, "compliance rate") if col(outcomes, "compliance rate") else None
    for c in outcomes.columns:
        low = c.lower()
        if low.startswith("cases we were satisfied") and "compliance rate" in low:
            o_rate = c

    rows = {}
    for _, r in decided.iterrows():
        key = normalise(r[d_name])
        rows[key] = {
            "lgo_name": r[d_name],
            "complaints_total": num(r[d_total]) if d_total else None,
            "upheld": num(r[d_upheld]) if d_upheld else None,
            "uphold_rate": pct(r[d_rate]) if d_rate else None,
            "uphold_rate_peer": pct(r[d_rate_peer]) if d_rate_peer else None,
            "per_100k": num(r[d_per100]) if d_per100 else None,
            "per_100k_peer": num(r[d_per100_peer]) if d_per100_peer else None,
            "compliance_rate": None,
        }
    for _, r in outcomes.iterrows():
        key = normalise(r[d_name])
        if key in rows and o_rate:
            rows[key]["compliance_rate"] = pct(r[o_rate])

    # join to our ONS registry
    reg = pd.read_csv(OUT_DIR / "scorecard_imd.csv").drop_duplicates("ons_code")[["ons_code", "council"]]
    out = []
    unmatched = []
    for _, rr in reg.iterrows():
        key = normalise(rr["council"])
        rec = rows.get(key)
        if rec is None:
            unmatched.append(rr["council"])
            continue
        out.append({"ons_code": rr["ons_code"], "council": rr["council"], **rec})

    df = pd.DataFrame(out)
    df.to_csv(OUT_DIR / "ombudsman.csv", index=False)
    print(f"data_england/ombudsman.csv: {len(df)} councils matched "
          f"({len(unmatched)} unmatched)")
    if unmatched:
        print("  unmatched:", unmatched[:20])


if __name__ == "__main__":
    main()
