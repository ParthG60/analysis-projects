"""ONS mid-year population estimates (via the Nomis API, dataset NM_2002_1 -
'Population estimates - local authority based by single year of age', which is
ONS's official mid-year population estimate series rebased to the 2021/2022
censuses) -> data/demographics.csv.

Usage: python demographics.py
"""
import csv
from pathlib import Path

import requests

OUT = Path(__file__).parent / "data"
SOURCE_YEAR = 2024  # mid-2024 population estimate

# ONS code -> canonical name (matches councils.csv `name`). Kent is the upper-tier
# county (E10000016, ~1.6M), not its constituent districts. County Durham is the
# unitary (E06000047).
ONS_CODES = {
    "E08000032": "Bradford",
    "E06000023": "Bristol",
    "E08000019": "Sheffield",
    "E10000016": "Kent",
    "E06000047": "County Durham",
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

NOMIS_URL = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"


def fetch():
    params = {
        "geography": ",".join(ONS_CODES),
        "date": SOURCE_YEAR,
        "gender": "0",  # total (both sexes)
        "c_age": "200",  # all ages
        "measures": "20100",  # value
        "select": "geography_code,obs_value",
    }
    r = requests.get(NOMIS_URL, params=params, timeout=30)
    r.raise_for_status()

    rows = []
    for line in r.text.splitlines()[1:]:
        code, value = [c.strip('"') for c in line.split(",")]
        rows.append({
            "council": ONS_CODES[code],
            "population": int(value),
            "source_year": SOURCE_YEAR,
        })
    return rows


if __name__ == "__main__":
    rows = fetch()
    rows.sort(key=lambda r: -r["population"])

    OUT.mkdir(exist_ok=True)
    with open(OUT / "demographics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["council", "population", "source_year"])
        w.writeheader()
        w.writerows(rows)

    print(f"data/demographics.csv: {len(rows)} councils (ONS mid-{SOURCE_YEAR} estimates)")
    for r in rows:
        print(f"  {r['council']:<32} {r['population']:>10,}")
