"""ONS mid-2024 population (Nomis NM_2002_1) for all 282 councils, keyed on ONS
code. Master council list = distinct ons_code in data_england/scorecard_imd.csv
(the IMD scorecard already unions the 267 England set + original 15).

Output data_england/population_all.csv: ons_code, council, population, source_year.
Usage: python population_all.py
"""
import csv
from pathlib import Path

import requests

ROOT = Path(__file__).parent
SOURCE_YEAR = 2024
NOMIS_URL = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"

# master registry: ons_code -> council name (from the IMD scorecard)
registry = {}
with open(ROOT / "data_england" / "scorecard_imd.csv", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        registry.setdefault(r["ons_code"], r["council"])

codes = list(registry)
pop = {}
# Nomis caps geography list length; chunk it.
for i in range(0, len(codes), 100):
    chunk = codes[i:i + 100]
    params = {
        "geography": ",".join(chunk),
        "date": SOURCE_YEAR,
        "gender": "0", "c_age": "200", "measures": "20100",
        "select": "geography_code,obs_value",
    }
    r = requests.get(NOMIS_URL, params=params, timeout=60)
    r.raise_for_status()
    for line in r.text.splitlines()[1:]:
        code, value = [c.strip('"') for c in line.split(",")]
        pop[code] = int(value)

rows = []
for code, name in registry.items():
    if code not in pop:  # drop-don't-fake
        print(f"  SKIP {name} ({code}): no Nomis population")
        continue
    rows.append({"ons_code": code, "council": name, "population": pop[code], "source_year": SOURCE_YEAR})

with open(ROOT / "data_england" / "population_all.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["ons_code", "council", "population", "source_year"])
    w.writeheader()
    w.writerows(rows)

print(f"data_england/population_all.csv: {len(rows)}/{len(registry)} councils (ONS mid-{SOURCE_YEAR})")
