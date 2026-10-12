"""Ethnicity data for all 282 English councils + England from APS 2025/26
(Nomis NM_17_5) with Census 2021 fallback.

Queries Nomis NM_17_5 for variables 557 (White), 794 (Mixed), 795 (Indian),
796 (Pak/Bang), 797 (Black), 798 (Other).

For each council: if APS has all 6 valid non-suppressed cells, uses APS
(with Asian = Indian + Pak/Bang) and tags source: "ONS Annual Population Survey (2025/26)".
Otherwise, falls back to Census 2021 and tags source: "Census 2021 (ONS)".

Output: data_england/ethnicity_all.csv
"""
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent.parent
ENG_DIR = ROOT / "data_england"
DATA_DIR = ROOT / "data"
SLEEP = 0.2
CHUNK = 40

# Original 15 councils (not in profile_all.csv) by name -> ONS code
ORIGINAL_15 = {
    "Bradford": "E08000032", "Bristol": "E06000023", "Sheffield": "E08000019",
    "Kent": "E10000016", "Bromley": "E09000006", "Bath and North East Somerset": "E06000022",
    "Mid Suffolk": "E07000203", "Tower Hamlets": "E09000030", "Lancashire": "E10000017",
    "Leeds": "E08000035", "Manchester": "E08000003", "Camden": "E09000007",
    "Bexley": "E09000004", "Hillingdon": "E09000017", "Somerset": "E06000066",
}
ENGLAND_CODE = "E92000001"


def get_all_codes():
    """All 282 unique ONS codes from scorecard_imd.csv + England."""
    imd = pd.read_csv(ENG_DIR / "scorecard_imd.csv")
    codes = sorted(imd["ons_code"].unique().tolist())
    if ENGLAND_CODE not in codes:
        codes.append(ENGLAND_CODE)
    return codes


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_aps_ethnicity(codes):
    """Fetch APS 2025/26 ethnicity percentages from NM_17_5.

    Variables:
      557 = White, 794 = Mixed, 795 = Indian, 796 = Pakistani/Bangladeshi,
      797 = Black, 798 = Other

    Returns dict: geo_code -> {var_code: {"value": float, "status": str}}
    """
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_17_5.data.csv"
    variables = [557, 794, 795, 796, 797, 798]

    results = {}
    for batch in chunks(codes, CHUNK):
        params = {
            "geography": ",".join(batch),
            "date": "latest",
            "variable": ",".join(str(v) for v in variables),
            "measures": "20599",  # percentage (Variable measure)
            "select": "geography_code,variable,obs_value,obs_status",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(SLEEP)

        for line in r.text.splitlines()[1:]:
            if not line.strip():
                continue
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) < 4:
                continue
            geo_code = parts[0]
            var_code = int(parts[1])
            obs_value = parts[2]
            obs_status = parts[3]

            results.setdefault(geo_code, {})[var_code] = {
                "value": float(obs_value) if obs_value else None,
                "status": obs_status,
            }

    return results


def is_valid_aps(entry):
    """All 6 variables present, non-null, and status 'A' (Normal Value)."""
    for v in [557, 794, 795, 796, 797, 798]:
        rec = entry.get(v)
        if rec is None:
            return False
        if rec["value"] is None:
            return False
        if rec["status"] != "A":
            return False
    return True


def load_census_fallback():
    """Build ons_code -> {white_pct, asian_pct, black_pct, mixed_pct, other_pct}
    from profile_all.csv (267 councils) + data/profile.csv (15 + England)."""
    lookup = {}

    # 267 councils from profile_all.csv
    profile_all = pd.read_csv(ENG_DIR / "profile_all.csv")
    for _, row in profile_all.iterrows():
        lookup[row["ons_code"]] = {
            "white_pct": row["white_pct"],
            "asian_pct": row["asian_pct"],
            "black_pct": row["black_pct"],
            "mixed_pct": row["mixed_pct"],
            "other_pct": row["other_pct"],
        }

    # 15 original councils + England from data/profile.csv (keyed by name)
    profile_old = pd.read_csv(DATA_DIR / "profile.csv")
    for _, row in profile_old.iterrows():
        cname = row["council"]
        code = ORIGINAL_15.get(cname)
        if cname == "England":
            code = ENGLAND_CODE
        if code:
            lookup[code] = {
                "white_pct": row["white_pct"],
                "asian_pct": row["asian_pct"],
                "black_pct": row["black_pct"],
                "mixed_pct": row["mixed_pct"],
                "other_pct": row["other_pct"],
            }

    return lookup


def get_council_names():
    """Map ons_code -> council name from scorecard_imd.csv (+ England)."""
    imd = pd.read_csv(ENG_DIR / "scorecard_imd.csv")
    names = dict(zip(imd["ons_code"], imd["council"]))
    names[ENGLAND_CODE] = "England"
    return names


def main():
    codes = get_all_codes()
    council_names = get_council_names()
    census = load_census_fallback()

    print(f"1. Fetching APS (NM_17_5) for {len(codes)} geography codes...")
    aps_data = fetch_aps_ethnicity(codes)
    print(f"   Got APS data for {len(aps_data)} geography codes")

    aps_count = 0
    census_count = 0
    missing_count = 0

    rows = []
    for code in codes:
        entry = aps_data.get(code)
        name = council_names.get(code, code)

        if entry and is_valid_aps(entry):
            # Use APS data
            white = entry[557]["value"]
            indian = entry[795]["value"]
            pak_bang = entry[796]["value"]
            mixed = entry[794]["value"]
            black = entry[797]["value"]
            other = entry[798]["value"]
            asian = round(indian + pak_bang, 1)

            rows.append({
                "ons_code": code,
                "council": name,
                "white_pct": white,
                "asian_pct": asian,
                "black_pct": black,
                "mixed_pct": mixed,
                "other_pct": other,
                "source": "ONS Annual Population Survey (2025/26)",
            })
            aps_count += 1
        elif code in census:
            # Fall back to Census 2021
            c = census[code]
            rows.append({
                "ons_code": code,
                "council": name,
                "white_pct": c["white_pct"],
                "asian_pct": c["asian_pct"],
                "black_pct": c["black_pct"],
                "mixed_pct": c["mixed_pct"],
                "other_pct": c["other_pct"],
                "source": "Census 2021 (ONS)",
            })
            census_count += 1
        else:
            print(f"   WARNING: no data for {code} ({name})")
            missing_count += 1

    out_df = pd.DataFrame(rows)
    out_path = ENG_DIR / "ethnicity_all.csv"
    out_df.to_csv(out_path, index=False)

    print(f"\nSaved {len(out_df)} rows to {out_path}")
    print(f"  APS 2025/26:     {aps_count}")
    print(f"  Census 2021:     {census_count}")
    if missing_count:
        print(f"  Missing:         {missing_count}")
    print(f"  Total:           {len(rows)}")


if __name__ == "__main__":
    main()