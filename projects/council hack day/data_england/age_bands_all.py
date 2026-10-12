"""Fetch mid-2024 Nomis population age bands (NM_2002_1) for ALL 282 English councils + England.
Schema: ons_code, council, band, sex, pct
Outputs: data_england/age_bands_all.csv
"""
import csv
import time
from pathlib import Path
import requests

ROOT = Path(__file__).parent.parent
ENG_DIR = ROOT / "data_england"
NOMIS_URL = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
SLEEP = 0.15

def get_registry():
    registry = {}
    with open(ENG_DIR / "scorecard_imd.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            registry.setdefault(r["ons_code"], r["council"])
    return registry

def fetch_all_age_bands():
    registry = get_registry()
    name_map = dict(registry)
    name_map["E92000001"] = "England"
    geo_codes = list(name_map.keys())

    v = {}
    chunk_size = 40
    print(f"Fetching Nomis age bands for {len(geo_codes)} geographies in chunks of {chunk_size}...")

    for i in range(0, len(geo_codes), chunk_size):
        chunk = geo_codes[i : i + chunk_size]
        params = {
            "geography": ",".join(chunk),
            "date": 2024,
            "gender": "1,2",
            "c_age": "200,201,209,5,6,7,116,8,9,10,11,12,13,14",
            "measures": "20100",
            "select": "geography_code,gender,c_age,obs_value",
        }
        r = requests.get(NOMIS_URL, params=params, timeout=60)
        r.raise_for_status()
        time.sleep(SLEEP)

        for line in r.text.splitlines()[1:]:
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) < 4:
                continue
            code, gender, c_age, value = parts[0], parts[1], parts[2], parts[3]
            v.setdefault(code, {}).setdefault(gender, {})[c_age] = int(value)

    sex_map = {"1": "male", "2": "female"}
    out = []

    for code, name in name_map.items():
        if code not in v:
            print(f"  WARNING: missing Nomis data for {name} ({code})")
            continue
        d = v[code]
        if "1" not in d or "2" not in d or "200" not in d["1"] or "200" not in d["2"]:
            print(f"  WARNING: incomplete Nomis gender data for {name} ({code})")
            continue

        total = d["1"]["200"] + d["2"]["200"]
        if total == 0:
            continue

        for gender, sex in sex_map.items():
            g = d[gender]
            bands = {
                "0-15": g.get("201", 0),
                "16-29": g.get("5", 0) + g.get("6", 0) + g.get("7", 0) - g.get("116", 0),
                "30-44": g.get("8", 0) + g.get("9", 0) + g.get("10", 0),
                "45-64": g.get("11", 0) + g.get("12", 0) + g.get("13", 0) + g.get("14", 0),
                "65+": g.get("209", 0),
            }
            for band, count in bands.items():
                pct = round(count / total * 100, 1)
                out.append({
                    "ons_code": code,
                    "council": name,
                    "band": band,
                    "sex": sex,
                    "pct": pct
                })

    out_path = ENG_DIR / "age_bands_all.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ons_code", "council", "band", "sex", "pct"])
        w.writeheader()
        w.writerows(out)

    print(f"Saved {len(out)} rows to {out_path} ({len(name_map)} geographies, 10 rows each)")
    return out

if __name__ == "__main__":
    fetch_all_age_bands()
