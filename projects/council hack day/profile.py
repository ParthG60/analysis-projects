"""Socio-economic profile per council -> data/profile.csv.

Sources:
- Age structure: Nomis NM_2002_1 (ONS mid-2024 population estimates by single year
  of age), same dataset demographics.py uses.
- Median full-time pay: Nomis NM_30_1 (ASHE resident analysis), latest year.
- Ethnicity: Census 2021 TS021 via Nomis NM_2041_1, high-level 5-group breakdown.
- House prices: HM Land Registry UK House Price Index full file, latest common month.
- Band D council tax 2025-26: MHCLG "Council tax levels set by local authorities"
  Table 10 (local authority level data). For the 6 unitary/London-borough councils
  and Mid Suffolk this is the full resident bill (billing authority + county/GLA +
  police + fire major precepts, Data_Billing col 17). For Kent and Lancashire
  (upper-tier counties, not billing authorities) this is only the county precept
  element (Data_Precepting), not a full resident bill.

Usage: python profile.py
"""
import csv
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data"
SLEEP = 0.15

# ONS code -> canonical name (matches councils.csv `name`)
ONS_CODES = {
    "E08000032": "Bradford",
    "E06000023": "Bristol",
    "E08000019": "Sheffield",
    "E10000016": "Kent",
    "E09000006": "Bromley",
    "E06000022": "Bath and North East Somerset",
    "E07000203": "Mid Suffolk",
    "E09000030": "Tower Hamlets",
    "E10000017": "Lancashire",
    "E08000035": "Leeds",
    "E08000003": "Manchester",
    "E09000007": "Camden",
    "E09000004": "Bexley",
    "E09000017": "Hillingdon",
    "E06000066": "Somerset",
}
COUNCILS = list(ONS_CODES.values())

# House Price Index RegionName for each council (differs from ONS name for Bristol)
HPI_REGION_NAME = {
    "Bradford": "Bradford",
    "Bristol": "City of Bristol",
    "Sheffield": "Sheffield",
    "Kent": "Kent",
    "Bromley": "Bromley",
    "Bath and North East Somerset": "Bath and North East Somerset",
    "Mid Suffolk": "Mid Suffolk",
    "Tower Hamlets": "Tower Hamlets",
    "Lancashire": "Lancashire",
    "Leeds": "Leeds",
    "Manchester": "Manchester",
    "Camden": "Camden",
    "Bexley": "Bexley",
    "Hillingdon": "Hillingdon",
    "Somerset": "Somerset",
}

AGE_YEAR = 2024


# ---------------------------------------------------------------------------
# Age structure
# ---------------------------------------------------------------------------

def fetch_age():
    """under18_pct, over65_pct via NM_2002_1. c_age has no single 0-17 band, so
    0-17 = 'Aged 0 to 15' (201) + 'Aged 16 to 17' (204); 65+ = 'Aged 65+' (209)."""
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
    params = {
        "geography": ",".join(ONS_CODES),
        "date": AGE_YEAR,
        "gender": "0",
        "c_age": "200,201,204,209",
        "measures": "20100",
        "select": "geography_code,c_age,obs_value",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)

    totals, under16, sixteen17, over65 = {}, {}, {}, {}
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
    for code, name in ONS_CODES.items():
        total = totals[code]
        out[name] = {
            "under18_pct": round((under16[code] + sixteen17[code]) / total * 100, 1),
            "over65_pct": round(over65[code] / total * 100, 1),
        }
    return out


# ---------------------------------------------------------------------------
# Median full-time pay (ASHE resident analysis)
# ---------------------------------------------------------------------------

def fetch_pay():
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_30_1.data.csv"
    params = {
        "geography": ",".join(ONS_CODES),
        "date": "latest",
        "sex": "8",  # full-time workers
        "item": "2",  # median
        "pay": "1",  # weekly pay, gross
        "measures": "20100",
        "select": "geography_code,obs_value",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)

    out = {}
    for line in r.text.splitlines()[1:]:
        code, value = [c.strip('"') for c in line.split(",")]
        if code in ONS_CODES:
            out[ONS_CODES[code]] = float(value)
    return out


# ---------------------------------------------------------------------------
# Ethnicity (Census 2021 TS021)
# ---------------------------------------------------------------------------

ETH_CODE_TO_COL = {
    "1001": "asian_pct",
    "1002": "black_pct",
    "1003": "mixed_pct",
    "1004": "white_pct",
    "1005": "other_pct",
}


def fetch_ethnicity():
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2041_1.data.csv"
    params = {
        "geography": ",".join(ONS_CODES),
        "c2021_eth_20": "0,1001,1002,1003,1004,1005",
        "measures": "20100",
        "select": "geography_code,c2021_eth_20,obs_value",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)

    totals, groups = {}, {}
    for line in r.text.splitlines()[1:]:
        code, eth, value = [c.strip('"') for c in line.split(",")]
        value = int(value)
        if eth == "0":
            totals[code] = value
        else:
            groups.setdefault(code, {})[eth] = value

    out = {}
    for code, name in ONS_CODES.items():
        total = totals[code]
        out[name] = {
            col: round(groups[code][eth] / total * 100, 1)
            for eth, col in ETH_CODE_TO_COL.items()
        }
    return out


# ---------------------------------------------------------------------------
# House prices (HM Land Registry UK HPI)
# ---------------------------------------------------------------------------

def fetch_house_prices():
    """Full HPI file is published under a month tag that lags the actual latest
    data month; walk backward from today to find a month tag that resolves."""
    base = "http://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-{}.csv"
    today = date.today()
    for i in range(12):
        month_idx = today.month - 1 - i
        year = today.year + (month_idx - 1) // 12
        month = (month_idx - 1) % 12 + 1
        tag = f"{year}-{month:02d}"
        url = base.format(tag)
        r = requests.get(url, timeout=60)
        time.sleep(SLEEP)
        if r.status_code == 200 and r.text.startswith("Date,RegionName"):
            break
    else:
        print("house prices: no HPI file found in last 12 months, skipping")
        return {}

    from io import StringIO
    df = pd.read_csv(StringIO(r.text), usecols=["Date", "RegionName", "AveragePrice"])
    latest_date = df["Date"].max()
    latest = df[df["Date"] == latest_date]

    out = {}
    for name, region in HPI_REGION_NAME.items():
        hit = latest[latest["RegionName"] == region]
        if len(hit) == 1:
            out[name] = round(float(hit.iloc[0]["AveragePrice"]))
        else:
            print(f"house prices: {len(hit)} matches for {name!r} ({region!r}), skipping")
    print(f"house prices: latest common month = {latest_date}")
    return out


# ---------------------------------------------------------------------------
# Band D council tax 2025-26 (MHCLG Table 10)
# ---------------------------------------------------------------------------

TABLE10_URL = "https://assets.publishing.service.gov.uk/media/6a02f143e71c4cdf4026ba48/Table_10_2025-26.ods"
TABLE10_FILE = DATA_DIR / "Table_10_2025-26.ods"

BILLING_AUTHORITY = {
    "Bradford": "Bradford",
    "Bristol": "Bristol",
    "Sheffield": "Sheffield",
    "Bromley": "Bromley",
    "Bath and North East Somerset": "Bath and North East Somerset",
    "Mid Suffolk": "Mid Suffolk",
    "Tower Hamlets": "Tower Hamlets",
    "Leeds": "Leeds",
    "Manchester": "Manchester",
    "Camden": "Camden",
    "Bexley": "Bexley",
    "Hillingdon": "Hillingdon",
    "Somerset": "Somerset",
}
PRECEPTING_AUTHORITY = {
    "Kent": "Kent",
    "Lancashire": "Lancashire",
}


def fetch_council_tax():
    if not TABLE10_FILE.exists():
        r = requests.get(TABLE10_URL, timeout=60)
        r.raise_for_status()
        TABLE10_FILE.write_bytes(r.content)

    out = {}

    # Billing authorities: col 37 = full Band D bill incl. major precepts (county/
    # GLA + police + fire) — what a resident actually pays.
    billing = pd.read_excel(TABLE10_FILE, engine="odf", sheet_name="Data_Billing", header=None)
    for name, la in BILLING_AUTHORITY.items():
        hit = billing[billing.iloc[:, 2] == la]
        if len(hit) == 1:
            out[name] = round(float(hit.iloc[0, 37]), 2)
        else:
            print(f"council tax: {len(hit)} matches for {name!r} in Data_Billing, skipping")

    # Precepting authorities (upper-tier counties): col 13 = county's own Band D
    # precept element only, not a full resident bill.
    precepting = pd.read_excel(TABLE10_FILE, engine="odf", sheet_name="Data_Precepting", header=None)
    for name, la in PRECEPTING_AUTHORITY.items():
        hit = precepting[precepting.iloc[:, 2] == la]
        if len(hit) == 1:
            out[name] = round(float(hit.iloc[0, 13]), 2)
        else:
            print(f"council tax: {len(hit)} matches for {name!r} in Data_Precepting, skipping")

    return out


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    age = fetch_age()
    pay = fetch_pay()
    ethnicity = fetch_ethnicity()
    house_prices = fetch_house_prices()
    council_tax = fetch_council_tax()

    fieldnames = [
        "council", "under18_pct", "over65_pct", "median_ft_pay", "median_house_price",
        "band_d_council_tax", "white_pct", "asian_pct", "black_pct", "mixed_pct", "other_pct",
    ]
    rows = []
    for name in COUNCILS:
        row = {"council": name}
        row.update(age.get(name, {}))
        row["median_ft_pay"] = pay.get(name)
        row["median_house_price"] = house_prices.get(name)
        row["band_d_council_tax"] = council_tax.get(name)
        row.update(ethnicity.get(name, {}))
        rows.append(row)

    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "profile.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\ndata/profile.csv: {len(rows)} councils")
    print(pd.DataFrame(rows).to_string(index=False))
