"""MHCLG quarterly local authority borrowing live table -> data_england/borrowing.csv.

Source (discovered from the gov.uk collection page so it survives URL churn):
  https://www.gov.uk/government/statistical-data-sets/live-tables-on-local-government-finance

For each English local authority we take the most recent quarter's total outstanding
borrowing (sum of every loan/securities category, £ thousand -> £ million), plus the
class of authority. Joined to our ONS codes directly (the table carries an ONS column).

Usage: python england_borrowing.py
"""
from pathlib import Path
import io
import re
import urllib.request

import pandas as pd

OUT_DIR = Path(__file__).parent / "data_england"
COLLECTION = "https://www.gov.uk/government/statistical-data-sets/live-tables-on-local-government-finance"
# stable fallback if discovery fails
FALLBACK = "https://assets.publishing.service.gov.uk/media/6a85a7a61b45e4e555421ec6/Q1_2026_27_Borrowing_and_Investment_Live_Table.ods"


def discover_url():
    req = urllib.request.Request(COLLECTION, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=30).read().decode()
        hits = re.findall(r'href=["\']([^"\']*[Bb]orrowing[^"\']*\.ods)["\']', html)
        if hits:
            return hits[0]
    except Exception as e:
        print(f"  discovery failed ({e}); using fallback URL")
    return FALLBACK


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def latest_borrowing_sheet(xl):
    sheets = [s for s in xl.sheet_names if s.startswith("LA_Borrowing_")]
    if not sheets:
        raise ValueError("no LA_Borrowing_* sheets found")
    # sheets are listed most-recent-first; the first is the latest quarter
    return sheets[0]


def parse(content):
    xl = pd.ExcelFile(io.BytesIO(content), engine="odf")
    sheet = latest_borrowing_sheet(xl)
    raw = pd.read_excel(io.BytesIO(content), engine="odf", sheet_name=sheet, header=None)

    hdr = None
    for i in range(len(raw)):
        if str(raw.iloc[i, 0]).strip() == "LGF code":
            hdr = i
            break
    if hdr is None:
        raise ValueError("could not find 'LGF code' header in borrowing sheet")

    cols = [str(c).strip() for c in raw.iloc[hdr].tolist()]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = cols

    ons_col = next((c for c in cols if c == "ONS code"), None)
    name_col = next((c for c in cols if "authority name" in c.lower()), "Local authority name")
    class_col = next((c for c in cols if "class of authority" in c.lower()), None)

    # every £ thousand column between LGF code and Country/Class/ONS metadata
    money_cols = [c for c in cols if "£ thousand" in c.lower()]
    for c in money_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df[df[ons_col].notna()]
    # keep real 9-char English ONS codes only
    df = df[df[ons_col].astype(str).str.match(r"^E\d{8}$")]

    rows = []
    for _, r in df.iterrows():
        total_k = r[money_cols].sum(min_count=1)
        if pd.isna(total_k):
            continue
        rows.append({
            "ons_code": r[ons_col],
            "authority_name": r[name_col],
            "class": r[class_col] if class_col else None,
            "total_borrowing_gbp_m": round(float(total_k) / 1000.0, 1),
        })
    out = pd.DataFrame(rows)

    # The live table occasionally carries stale ONS codes (e.g. Barnsley/Sheffield
    # under E08000038/E08000039). Reconcile to our registry by normalised name so the
    # join key is always our canonical code.
    reg = pd.read_csv(OUT_DIR / "scorecard_imd.csv").drop_duplicates("ons_code")[["ons_code", "council"]]
    name_to_ons = {_norm(n): c for c, n in zip(reg["ons_code"], reg["council"])}
    out["ons_code"] = [
        name_to_ons.get(_norm(nm), oc) for nm, oc in zip(out["authority_name"], out["ons_code"])
    ]
    return sheet, out


def _norm(name):
    n = str(name).strip().lower().replace("&", "and")
    for suf in ["metropolitan borough council", "city council", "county council",
                "district council", "borough council", "council"]:
        if n.endswith(" " + suf):
            return n[: -(len(suf) + 1)].strip()
    return n


def main():
    url = discover_url()
    print(f"borrowing source: {url}")
    sheet, df = parse(fetch(url))
    df.to_csv(OUT_DIR / "borrowing.csv", index=False)
    print(f"data_england/borrowing.csv: {len(df)} authorities from sheet '{sheet}' "
          f"(median debt £{df['total_borrowing_gbp_m'].median():.0f}m)")


if __name__ == "__main__":
    main()
