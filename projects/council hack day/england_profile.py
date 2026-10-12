"""Socio-economic profile for ALL matched English councils (data_england/name_map.csv)
-> data_england/profile_all.csv. Same schema/sources as profile.py, generalized
from 15 hand-picked councils to all 267 unique ONS codes in the name map:

- Age structure: Nomis NM_2002_1 (ONS mid-2024 population estimates by single
  year of age).
- Median full-time pay: Nomis NM_30_1 (ASHE resident analysis), latest year.
- Ethnicity: Census 2021 TS021 via Nomis NM_2041_1, high-level 5-group breakdown.
- House prices: HM Land Registry UK House Price Index full file, latest common
  month, matched by normalized name (england_name_map.normalize) against the
  HPI's own RegionName column.
- Band D council tax 2025-26: MHCLG Table 10 (data/Table_10_2025-26.ods, already
  cached by profile.py - read only, not re-downloaded/modified). Billing
  authorities (RSX Class != 'SC') use Data_Billing (full resident bill);
  precepting-only counties (RSX Class == 'SC') use Data_Precepting (county
  precept element only), matched by normalized name.

Nomis requests are chunked (CHUNK codes at a time) with a sleep between calls.
Anything that can't be matched in a given source is logged and left null -
never guessed.

Usage: python england_profile.py
"""
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from england_name_map import normalize, subset_match
from finance import load_rsx

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "data_england"
SLEEP = 0.2
CHUNK = 40

TABLE10_FILE = DATA_DIR / "Table_10_2025-26.ods"
AGE_YEAR = 2024


def load_councils():
    """One row per unique ons_code, council label = first gateway_name seen, plus
    RSX Class (for billing/precepting). Data-only councils (the original 15 and the
    supplemental set: K&C + five Gateway-absent London boroughs) are appended from
    the master registry so their scorecard metrics are computed, not defaulted."""
    nm = pd.read_csv(OUT_DIR / "name_map.csv")
    nm = nm[nm["matched"]].drop_duplicates(subset="ons_code", keep="first")

    rsx = load_rsx()
    rsx = rsx[rsx["ONS Code"].str.len() == 9][["ONS Code", "Class"]]
    nm = nm.merge(rsx, left_on="ons_code", right_on="ONS Code", how="left")
    nm = nm[["ons_code", "gateway_name", "Class"]].rename(columns={"gateway_name": "council"})

    reg = pd.read_csv(OUT_DIR / "scorecard_imd.csv").drop_duplicates("ons_code")[["ons_code", "council"]]
    extra = reg[~reg["ons_code"].isin(nm["ons_code"])].copy()
    if not extra.empty:
        extra = extra.merge(rsx, left_on="ons_code", right_on="ONS Code", how="left")
        extra = extra[["ons_code", "council", "Class"]]
        nm = pd.concat([nm, extra], ignore_index=True)
    return nm


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ---------------------------------------------------------------------------
# Age structure
# ---------------------------------------------------------------------------

def fetch_age(codes):
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
    totals, under16, sixteen17, over65 = {}, {}, {}, {}
    for batch in chunks(codes, CHUNK):
        params = {
            "geography": ",".join(batch), "date": AGE_YEAR, "gender": "0",
            "c_age": "200,201,204,209", "measures": "20100",
            "select": "geography_code,c_age,obs_value",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(SLEEP)
        for line in r.text.splitlines()[1:]:
            code, c_age, value = [c.strip('"') for c in line.split(",")]
            value = int(value)
            if c_age == "200":
                totals[code] = value
            elif c_age == "201":
                under16[code] = value
            elif c_age == "204":
                sixteen17[code] = value
            elif c_age == "209":
                over65[code] = value

    out = {}
    for code in codes:
        if code not in totals:
            print(f"age: no data for {code}, skipping")
            continue
        total = totals[code]
        out[code] = {
            "under18_pct": round((under16[code] + sixteen17[code]) / total * 100, 1),
            "over65_pct": round(over65[code] / total * 100, 1),
        }
    return out


# ---------------------------------------------------------------------------
# Median full-time pay (ASHE resident analysis)
# ---------------------------------------------------------------------------

def fetch_pay(codes):
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_30_1.data.csv"
    out = {}
    for batch in chunks(codes, CHUNK):
        params = {
            "geography": ",".join(batch), "date": "latest", "sex": "8", "item": "2",
            "pay": "1", "measures": "20100", "select": "geography_code,obs_value",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(SLEEP)
        for line in r.text.splitlines()[1:]:
            code, value = [c.strip('"') for c in line.split(",")]
            out[code] = float(value)
    missing = set(codes) - set(out)
    if missing:
        print(f"pay: no ASHE data for {len(missing)} councils, skipping: {sorted(missing)}")
    return out


# ---------------------------------------------------------------------------
# Ethnicity (Census 2021 TS021)
# ---------------------------------------------------------------------------

ETH_CODE_TO_COL = {
    "1001": "asian_pct", "1002": "black_pct", "1003": "mixed_pct",
    "1004": "white_pct", "1005": "other_pct",
}


def fetch_ethnicity(codes):
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2041_1.data.csv"
    totals, groups = {}, {}
    for batch in chunks(codes, CHUNK):
        params = {
            "geography": ",".join(batch), "c2021_eth_20": "0,1001,1002,1003,1004,1005",
            "measures": "20100", "select": "geography_code,c2021_eth_20,obs_value",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(SLEEP)
        for line in r.text.splitlines()[1:]:
            code, eth, value = [c.strip('"') for c in line.split(",")]
            value = int(value)
            if eth == "0":
                totals[code] = value
            else:
                groups.setdefault(code, {})[eth] = value

    out = {}
    for code in codes:
        if code not in totals or code not in groups:
            print(f"ethnicity: no data for {code}, skipping")
            continue
        total = totals[code]
        out[code] = {
            col: round(groups[code][eth] / total * 100, 1)
            for eth, col in ETH_CODE_TO_COL.items()
        }
    return out


# ---------------------------------------------------------------------------
# House prices (HM Land Registry UK HPI)
# ---------------------------------------------------------------------------

def fetch_house_prices_all(councils):
    """Full HPI file, latest common month; walk backward from today for a
    month tag that resolves (same approach as profile.py)."""
    from datetime import date
    base = "http://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-{}.csv"
    today = date.today()
    for i in range(12):
        month_idx = today.month - 1 - i
        year = today.year + (month_idx - 1) // 12
        month = (month_idx - 1) % 12 + 1
        tag = f"{year}-{month:02d}"
        r = requests.get(base.format(tag), timeout=60)
        time.sleep(SLEEP)
        if r.status_code == 200 and r.text.startswith("Date,RegionName"):
            break
    else:
        print("house prices: no HPI file found in last 12 months, skipping all")
        return {}

    df = pd.read_csv(StringIO(r.text), usecols=["Date", "RegionName", "AveragePrice"])
    latest_date = df["Date"].max()
    latest = df[df["Date"] == latest_date]
    print(f"house prices: latest common month = {latest_date}")

    region_index = {}
    for region in latest["RegionName"].unique():
        region_index.setdefault(normalize(region), []).append(region)

    out, unmatched = {}, []
    for code, name in councils.items():
        key = normalize(name)
        candidates = region_index.get(key)
        if candidates is None:
            fb = subset_match(key, {k: v for k, v in region_index.items()})
            candidates = region_index.get(fb) if fb else None
        if candidates is None or len(candidates) != 1:
            unmatched.append(name)
            continue
        hit = latest[latest["RegionName"] == candidates[0]]
        out[code] = round(float(hit.iloc[0]["AveragePrice"]))
    if unmatched:
        print(f"house prices: {len(unmatched)} unmatched, skipping: {sorted(unmatched)}")
    return out


# ---------------------------------------------------------------------------
# Band D council tax 2025-26 (MHCLG Table 10, cached in data/ by profile.py)
# ---------------------------------------------------------------------------

def fetch_council_tax_all(councils_df):
    if not TABLE10_FILE.exists():
        print("council tax: Table_10_2025-26.ods not cached in data/ - run profile.py first, skipping")
        return {}

    billing = pd.read_excel(TABLE10_FILE, engine="odf", sheet_name="Data_Billing", header=None)
    precepting = pd.read_excel(TABLE10_FILE, engine="odf", sheet_name="Data_Precepting", header=None)

    def build_index(df, name_col=2):
        idx = {}
        for name in df[name_col].dropna().unique():
            idx.setdefault(normalize(str(name)), []).append(name)
        return idx

    billing_idx = build_index(billing)
    precepting_idx = build_index(precepting)

    out, unmatched = {}, []
    for _, row in councils_df.iterrows():
        code, name, cls = row["ons_code"], row["council"], row["Class"]
        key = normalize(name)
        if cls == "SC":
            idx, df, value_col = precepting_idx, precepting, 13
        else:
            idx, df, value_col = billing_idx, billing, 37
        candidates = idx.get(key)
        if candidates is None:
            fb = subset_match(key, idx)
            candidates = idx.get(fb) if fb else None
        if candidates is None or len(candidates) != 1:
            unmatched.append(name)
            continue
        hit = df[df[2] == candidates[0]]
        out[code] = round(float(hit.iloc[0][value_col]), 2)
    if unmatched:
        print(f"council tax: {len(unmatched)} unmatched, skipping: {sorted(unmatched)}")
    return out


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    councils_df = load_councils()
    codes = councils_df["ons_code"].tolist()
    name_by_code = dict(zip(councils_df["ons_code"], councils_df["council"]))
    print(f"profiling {len(codes)} councils")

    age = fetch_age(codes)
    pay = fetch_pay(codes)
    ethnicity = fetch_ethnicity(codes)
    house_prices = fetch_house_prices_all(name_by_code)
    council_tax = fetch_council_tax_all(councils_df)

    fieldnames = [
        "ons_code", "council", "under18_pct", "over65_pct", "median_ft_pay",
        "median_house_price", "band_d_council_tax", "white_pct", "asian_pct",
        "black_pct", "mixed_pct", "other_pct",
    ]
    rows = []
    for code, name in name_by_code.items():
        row = {"ons_code": code, "council": name}
        row.update(age.get(code, {}))
        row["median_ft_pay"] = pay.get(code)
        row["median_house_price"] = house_prices.get(code)
        row["band_d_council_tax"] = council_tax.get(code)
        row.update(ethnicity.get(code, {}))
        rows.append(row)

    OUT_DIR.mkdir(exist_ok=True)
    out = pd.DataFrame(rows)[fieldnames]
    out.to_csv(OUT_DIR / "profile_all.csv", index=False)
    print(f"\ndata_england/profile_all.csv: {len(out)} councils")
    print(out.isna().sum())
