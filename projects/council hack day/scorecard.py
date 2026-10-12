"""Socio-economic scorecard per council (+ England) -> data/scorecard.csv (long
format) and data/age_bands.csv.

Same 15 councils as profile.py, plus an England row (E92000001) on every metric.
v4: expanded from 9 to 15 councils (added Leeds, Manchester, Camden, Bexley,
Hillingdon, Somerset). v5: aroad_delay reinstated (v4 had dropped it, then
Parth asked for it back) - Leeds/Manchester/Camden/Bexley/Hillingdon are direct
DfT rows; Somerset matches by name only (DfT file predates the 2023 LGR and
still lists it under the old county code, not a proxy - same geography).
Deadline-driven build: any metric that couldn't be sourced cleanly within the
~30 min budget was dropped rather than approximated (see report / prints below).

Metrics in data/scorecard.csv (council, metric, value, year, source, proxy):
- attainment8      DfE KS4 performance (revised), 2023/24, LA-level avg Attainment 8.
                    Mid Suffolk is not an education authority -> Suffolk (proxy).
- co2_per_capita    DESNZ UK local authority & regional GHG emissions 2005-2024,
                    territorial CO2 only, tonnes/person. Kent & Lancashire (upper-
                    tier counties, not published directly) = sum of constituent
                    districts' emissions / summed population (true aggregate).
- rent_affordability  Median monthly private rent (ONS PIPR, latest month) as a
                    % of median monthly full-time pay (profile.csv median_ft_pay
                    * 52/12; England pay via Nomis NM_30_1). Kent & Lancashire
                    rent = unweighted mean of constituent districts (proxy).
- crime_per_1000    ONS "Recorded crime by Community Safety Partnership area",
                    year ending March 2024, Total recorded crime (excl. fraud)
                    per 1,000 population (ONS mid-2024 pop). Kent = sum of its
                    11 CSPs (Dartford+Gravesham published as one combined CSP)
                    / summed population - true aggregate, not proxy. Lancashire
                    = sum of its 12 districts / summed population, true
                    aggregate. Mid Suffolk has no own CSP (merged into "Western
                    Suffolk" with West Suffolk) -> proxy.
- aroad_delay       DfT CGN0504d, average delay on locally managed 'A' roads by
                    LA, 2024, seconds per vehicle per mile. Mid Suffolk -> Suffolk
                    (proxy). Somerset matched by name against the old pre-2023
                    county code (not a proxy - same highway authority footprint).
                    All other 13 councils + England matched directly.

data/age_bands.csv: council, band, sex, pct - Nomis NM_2002_1 mid-2024 population
estimates, 15 councils + England, bands 0-15/16-29/30-44/45-64/65+, sex in
{male, female}. pct is % of TOTAL (both-sex) population, so male+female pct sum
to 100 for a given council (built for a population-pyramid chart).

Usage: python scorecard.py
"""
import csv
import time
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data"
SLEEP = 0.15

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
COUNCILS = list(ONS_CODES.values()) + ["England"]

KENT_DISTRICTS = {
    "Ashford": "E07000105", "Canterbury": "E07000106", "Dartford": "E07000107",
    "Dover": "E07000108", "Gravesham": "E07000109", "Maidstone": "E07000110",
    "Sevenoaks": "E07000111", "Folkestone and Hythe": "E07000112", "Swale": "E07000113",
    "Thanet": "E07000114", "Tonbridge and Malling": "E07000115", "Tunbridge Wells": "E07000116",
}
LANCS_DISTRICTS = {
    "Burnley": "E07000117", "Chorley": "E07000118", "Fylde": "E07000119",
    "Hyndburn": "E07000120", "Lancaster": "E07000121", "Pendle": "E07000122",
    "Preston": "E07000123", "Ribble Valley": "E07000124", "Rossendale": "E07000125",
    "South Ribble": "E07000126", "West Lancashire": "E07000127", "Wyre": "E07000128",
}

rows = []  # scorecard.csv rows accumulate here


def add(council, metric, value, year, source, proxy):
    if value is None:
        return
    rows.append({
        "council": council, "metric": metric, "value": value, "year": year,
        "source": source, "proxy": proxy,
    })


# ---------------------------------------------------------------------------
# 1. Attainment 8 (DfE KS4 performance, revised, 2023/24)
# ---------------------------------------------------------------------------

KS4_ZIP_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/b76a938a-7875-4542-af20-0b23ecb99a49/files"
KS4_CACHE = DATA_DIR / "202324_la_data_revised.csv"
KS4_SOURCE = "DfE explore-education-statistics, Key stage 4 performance (revised) 2023/24, LA data (avg_att8)"

KS4_NAME_MAP = {
    "Bradford": ("Bradford", False),
    "Bristol": ("Bristol, City of", False),
    "Sheffield": ("Sheffield", False),
    "Kent": ("Kent", False),
    "Bromley": ("Bromley", False),
    "Bath and North East Somerset": ("Bath and North East Somerset", False),
    "Mid Suffolk": ("Suffolk", True),
    "Tower Hamlets": ("Tower Hamlets", False),
    "Lancashire": ("Lancashire", False),
    "Leeds": ("Leeds", False),
    "Manchester": ("Manchester", False),
    "Camden": ("Camden", False),
    "Bexley": ("Bexley", False),
    "Hillingdon": ("Hillingdon", False),
    "Somerset": ("Somerset", False),
}


def fetch_attainment8():
    if not KS4_CACHE.exists():
        print("attainment8: downloading KS4 release zip (large, ~70MB)...")
        r = requests.get(KS4_ZIP_URL, timeout=180)
        r.raise_for_status()
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            with z.open("data/202324_la_data_revised.csv") as f:
                KS4_CACHE.write_bytes(f.read())
        time.sleep(SLEEP)

    df = pd.read_csv(KS4_CACHE)
    la = df[(df["geographic_level"] == "Local authority") & (df["sex"] == "Total") & (df["time_period"] == 202324)]
    nat = df[(df["geographic_level"] == "National") & (df["sex"] == "Total") & (df["time_period"] == 202324)]

    for council, (la_name, proxy) in KS4_NAME_MAP.items():
        hit = la[la["la_name"] == la_name]
        if len(hit) == 1:
            add(council, "attainment8", float(hit.iloc[0]["avg_att8"]), "2023/24", KS4_SOURCE, proxy)
        else:
            print(f"attainment8: {len(hit)} matches for {council!r} ({la_name!r}), dropping")

    eng = nat[nat["country_name"] == "England"]
    if len(eng) == 1:
        add("England", "attainment8", float(eng.iloc[0]["avg_att8"]), "2023/24", KS4_SOURCE, False)


# ---------------------------------------------------------------------------
# 2. CO2 per capita (DESNZ local authority GHG emissions)
# ---------------------------------------------------------------------------

GHG_URL = "https://assets.publishing.service.gov.uk/media/6a3bacc9d52550a19950f2f5/2005-24-local-authority-ghg-emissions-csv-dataset.csv"
GHG_CACHE = DATA_DIR / "ghg_emissions_2024.csv"
GHG_SOURCE = "DESNZ UK local authority and regional greenhouse gas emissions statistics 2005-2024, territorial CO2"

GHG_DIRECT_NAMES = {
    "Bradford": "Bradford",
    "Bristol": "Bristol, City of",
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


def fetch_co2_per_capita():
    if not GHG_CACHE.exists():
        r = requests.get(GHG_URL, timeout=120)
        r.raise_for_status()
        GHG_CACHE.write_bytes(r.content)
        time.sleep(SLEEP)

    df = pd.read_csv(GHG_CACHE)
    d = df[(df["Calendar Year"] == 2024) & (df["Greenhouse gas"] == "CO2")]

    def per_capita(mask):
        sub = d[mask]
        emissions_kt = sub["Territorial emissions (kt CO2e)"].sum()
        pop_thousands = sub.drop_duplicates(subset=["Local Authority Code"])["Mid-year Population (thousands)"].sum()
        return round(emissions_kt / pop_thousands, 2)

    for council, la_name in GHG_DIRECT_NAMES.items():
        hit = d[d["Local Authority"] == la_name]
        if len(hit):
            add(council, "co2_per_capita", per_capita(d["Local Authority"] == la_name), 2024, GHG_SOURCE, False)
        else:
            print(f"co2_per_capita: no match for {council!r} ({la_name!r}), dropping")

    add("Kent", "co2_per_capita", per_capita(d["Second Tier Authority"] == "Kent"), 2024, GHG_SOURCE, False)
    add("Lancashire", "co2_per_capita", per_capita(d["Second Tier Authority"] == "Lancashire"), 2024, GHG_SOURCE, False)
    add("England", "co2_per_capita", per_capita(d["Country"] == "England"), 2024, GHG_SOURCE, False)


# ---------------------------------------------------------------------------
# 3. Rent affordability (ONS PIPR rent / ASHE resident pay)
# ---------------------------------------------------------------------------

PIPR_URL = "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/priceindexofprivaterentsukmonthlypricestatistics/19august2026/priceindexofprivaterentsukmonthlypricestatistics.xlsx"
PIPR_CACHE = DATA_DIR / "pipr_latest.xlsx"
# NB: ONS publishes this dataset under a date-stamped URL each month, so PIPR_URL
# will 404 once superseded - re-find the current link from the dataset landing
# page (ons.gov.uk .../datasets/priceindexofprivaterentsukmonthlypricestatistics)
# if PIPR_CACHE is deleted and the download fails.

RENT_DIRECT_NAMES = {
    "Bradford": "Bradford",
    "Bristol": "Bristol, City of",
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
    "England": "England",
}


def fetch_rent_affordability():
    if not PIPR_CACHE.exists():
        r = requests.get(PIPR_URL, timeout=120)
        r.raise_for_status()
        PIPR_CACHE.write_bytes(r.content)
        time.sleep(SLEEP)

    pipr = pd.read_excel(PIPR_CACHE, sheet_name="Table 1", header=2)
    period = pipr["Time period"].max()
    latest = pipr[pipr["Time period"] == period]
    year = period.strftime("%Y-%m")
    source = f"ONS Price Index of Private Rents, monthly price statistics {year} rent / Nomis NM_30_1 ASHE resident 2025 median FT weekly pay"

    profile = pd.read_csv(DATA_DIR / "profile.csv").set_index("council")["median_ft_pay"]

    def rent_for(name):
        hit = latest[latest["Area name"] == name]
        return float(hit.iloc[0]["Rental price"]) if len(hit) == 1 else None

    for council, area_name in RENT_DIRECT_NAMES.items():
        rent = rent_for(area_name)
        if rent is None:
            print(f"rent_affordability: no PIPR match for {council!r}, dropping")
            continue
        if council == "England":
            weekly_pay = fetch_ashe_pay("E92000001")
        else:
            weekly_pay = profile.get(council)
        if weekly_pay is None:
            print(f"rent_affordability: no pay figure for {council!r}, dropping")
            continue
        monthly_pay = weekly_pay * 52 / 12
        add(council, "rent_affordability", round(rent / monthly_pay * 100, 1), year, source, False)

    for council, districts in [("Kent", KENT_DISTRICTS), ("Lancashire", LANCS_DISTRICTS)]:
        rents = [rent_for(n) for n in districts]
        rents = [r for r in rents if r is not None]
        if len(rents) != len(districts):
            print(f"rent_affordability: only {len(rents)}/{len(districts)} district matches for {council!r}")
        mean_rent = sum(rents) / len(rents)
        monthly_pay = profile.get(council) * 52 / 12
        add(council, "rent_affordability", round(mean_rent / monthly_pay * 100, 1), year, source, True)


def fetch_ashe_pay(geo_code):
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_30_1.data.csv"
    params = {
        "geography": geo_code, "date": "latest", "sex": "8", "item": "2", "pay": "1",
        "measures": "20100", "select": "obs_value",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)
    line = r.text.splitlines()[1]
    return float(line.strip('"'))


# ---------------------------------------------------------------------------
# 4. Crime per 1,000 (ONS recorded crime by CSP/LA, year ending March 2024)
# ---------------------------------------------------------------------------

CSP_URL = "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/crimeandjustice/datasets/recordedcrimedatabycommunitysafetypartnershiparea/yearendingmarch2024/csptablesyemar24correction.xlsx"
CSP_CACHE = DATA_DIR / "csp_crime_yemar2024.xlsx"
CRIME_SOURCE = "ONS recorded crime by Community Safety Partnership area, year ending March 2024, Total recorded crime (excl. fraud) / ONS mid-2024 population (Nomis NM_2002_1)"

CRIME_DIRECT_CODES = {
    "Bradford": "E08000032", "Bristol": "E06000023", "Sheffield": "E08000019",
    "Bromley": "E09000006", "Bath and North East Somerset": "E06000022",
    "Tower Hamlets": "E09000030", "Leeds": "E08000035", "Manchester": "E08000003",
    "Camden": "E09000007", "Bexley": "E09000004", "Hillingdon": "E09000017",
    "Somerset": "E06000066",
}


def fetch_population(geo_codes):
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
    params = {
        "geography": ",".join(geo_codes), "date": 2024, "gender": "0", "c_age": "200",
        "measures": "20100", "select": "geography_code,obs_value",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)
    out = {}
    for line in r.text.splitlines()[1:]:
        code, value = [c.strip('"') for c in line.split(",")]
        out[code] = int(value)
    return out


def fetch_crime_per_1000():
    if not CSP_CACHE.exists():
        r = requests.get(CSP_URL, timeout=120)
        r.raise_for_status()
        CSP_CACHE.write_bytes(r.content)
        time.sleep(SLEEP)

    crime = pd.read_excel(CSP_CACHE, sheet_name="Table C2", header=7)
    crime_col = "Total recorded crime\n (excluding fraud)"
    la_col = "Local Authority\n code"

    demo = pd.read_csv(DATA_DIR / "demographics.csv").set_index("council")["population"]

    for council, code in CRIME_DIRECT_CODES.items():
        hit = crime[crime[la_col] == code]
        if len(hit) == 1 and council in demo.index:
            rate = round(float(hit.iloc[0][crime_col]) / demo[council] * 1000, 1)
            add(council, "crime_per_1000", rate, "2023/24", CRIME_SOURCE, False)
        else:
            print(f"crime_per_1000: no match for {council!r}, dropping")

    # Kent: 10 districts match directly; Dartford+Gravesham are published as one
    # combined CSP ("Dartford and Gravesham") - still a true Kent-only aggregate.
    kent_direct = crime[crime[la_col].isin(KENT_DISTRICTS.values())][crime_col].sum()
    dartford_gravesham = crime[crime["Community Safety\n Partnership name"] == "Dartford and Gravesham"][crime_col].sum()
    kent_crime = kent_direct + dartford_gravesham
    kent_pop_map = fetch_population(list(KENT_DISTRICTS.values()))
    kent_pop = sum(kent_pop_map.values())
    add("Kent", "crime_per_1000", round(kent_crime / kent_pop * 1000, 1), "2023/24", CRIME_SOURCE, False)

    lancs_crime = crime[crime[la_col].isin(LANCS_DISTRICTS.values())][crime_col].sum()
    lancs_pop_map = fetch_population(list(LANCS_DISTRICTS.values()))
    lancs_pop = sum(lancs_pop_map.values())
    add("Lancashire", "crime_per_1000", round(lancs_crime / lancs_pop * 1000, 1), "2023/24", CRIME_SOURCE, False)

    # Mid Suffolk has no own CSP - merged into "Western Suffolk" with West Suffolk
    # (a different, larger geography), so this is a genuine proxy substitution.
    western_suffolk_crime = crime[crime["Community Safety\n Partnership name"] == "Western Suffolk"][crime_col].sum()
    ws_pop_map = fetch_population(["E07000203", "E07000245"])  # Mid Suffolk + West Suffolk
    ws_pop = sum(ws_pop_map.values())
    add("Mid Suffolk", "crime_per_1000", round(western_suffolk_crime / ws_pop * 1000, 1), "2023/24", CRIME_SOURCE, True)

    eng = crime[crime[la_col].astype(str).str.startswith("E", na=False)]
    eng_crime = eng[crime_col].sum()
    eng_pop = fetch_population(["E92000001"])["E92000001"]
    add("England", "crime_per_1000", round(eng_crime / eng_pop * 1000, 1), "2023/24", CRIME_SOURCE, False)


# ---------------------------------------------------------------------------
# 5. A-road delay (DfT CGN0504d)
# ---------------------------------------------------------------------------

CGN_URL = "https://assets.publishing.service.gov.uk/media/6a5df5406a89fb816eea4b4b/cgn0504.ods"
CGN_CACHE = DATA_DIR / "cgn0504.ods"
AROAD_SOURCE = "DfT CGN0504d, average delay on locally managed 'A' roads by local authority, 2024 (seconds per vehicle per mile)"

AROAD_PROXY_CODE = {"Mid Suffolk": ("Suffolk", "E10000029")}
# Somerset: CGN0504d predates the 2023 LGR and still lists "Somerset" under the
# old two-tier county code E10000027. Somerset Council (the new unitary) is the
# sole highway authority for exactly that same area (districts were never
# highway authorities), so this is a direct name match, not a proxy.
AROAD_NAME_OVERRIDE = {"Somerset": "E10000027"}
AROAD_CODE_MAP = {
    c: n for c, n in ONS_CODES.items()
    if n not in AROAD_PROXY_CODE and n not in AROAD_NAME_OVERRIDE
}
AROAD_CODE_MAP["E92000001"] = "England"


def fetch_aroad_delay():
    if not CGN_CACHE.exists():
        r = requests.get(CGN_URL, timeout=120)
        r.raise_for_status()
        CGN_CACHE.write_bytes(r.content)
        time.sleep(SLEEP)

    df = pd.read_excel(CGN_CACHE, engine="odf", sheet_name="CGN0504d", header=3)

    for code, council in AROAD_CODE_MAP.items():
        hit = df[df["ONS area code"] == code]
        if len(hit) == 1:
            add(council, "aroad_delay", float(hit.iloc[0]["2024"]), 2024, AROAD_SOURCE, False)
        else:
            print(f"aroad_delay: no match for {council!r} ({code}), dropping")

    for council, code in AROAD_NAME_OVERRIDE.items():
        hit = df[df["ONS area code"] == code]
        if len(hit) == 1:
            add(council, "aroad_delay", float(hit.iloc[0]["2024"]), 2024, AROAD_SOURCE, False)
        else:
            print(f"aroad_delay: no match for {council!r} ({code}), dropping")

    for council, (proxy_name, proxy_code) in AROAD_PROXY_CODE.items():
        hit = df[df["ONS area code"] == proxy_code]
        if len(hit) == 1:
            add(council, "aroad_delay", float(hit.iloc[0]["2024"]), 2024, AROAD_SOURCE, True)
        else:
            print(f"aroad_delay: no match for {council!r} proxy ({proxy_name}), dropping")


# ---------------------------------------------------------------------------
# Age bands by sex (Nomis NM_2002_1, mid-2024): 0-15, 16-29, 30-44, 45-64, 65+.
# pct is % of TOTAL (both-sex) population, i.e. male + female pct sum to 100
# for a given council - built for a population-pyramid chart.
# ---------------------------------------------------------------------------

def fetch_age_bands():
    geo_codes = list(ONS_CODES) + ["E92000001"]
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
    # c_age: 200=all ages, 201=0-15, 209=65+, 5/6/7=15-19/20-24/25-29 (5yr bands),
    # 116=single age 15 (subtracted from the 15-19 band to get 16-29),
    # 8/9/10=30-34/35-39/40-44, 11/12/13/14=45-49/50-54/55-59/60-64
    # gender: 1=male, 2=female (verified against NM_2002_1: male+female=total)
    params = {
        "geography": ",".join(geo_codes), "date": 2024, "gender": "1,2",
        "c_age": "200,201,209,5,6,7,116,8,9,10,11,12,13,14",
        "measures": "20100", "select": "geography_code,gender,c_age,obs_value",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)

    v = {}
    for line in r.text.splitlines()[1:]:
        code, gender, c_age, value = [c.strip('"') for c in line.split(",")]
        v.setdefault(code, {}).setdefault(gender, {})[c_age] = int(value)

    name_map = dict(ONS_CODES)
    name_map["E92000001"] = "England"
    sex_map = {"1": "male", "2": "female"}

    out = []
    for code, name in name_map.items():
        d = v[code]
        total = d["1"]["200"] + d["2"]["200"]
        for gender, sex in sex_map.items():
            g = d[gender]
            bands = {
                "0-15": g["201"],
                "16-29": g["5"] + g["6"] + g["7"] - g["116"],
                "30-44": g["8"] + g["9"] + g["10"],
                "45-64": g["11"] + g["12"] + g["13"] + g["14"],
                "65+": g["209"],
            }
            for band, count in bands.items():
                out.append({"council": name, "band": band, "sex": sex, "pct": round(count / total * 100, 1)})
    return out


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    fetch_attainment8()
    fetch_co2_per_capita()
    fetch_rent_affordability()
    fetch_crime_per_1000()
    fetch_aroad_delay()

    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "scorecard.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["council", "metric", "value", "year", "source", "proxy"])
        w.writeheader()
        w.writerows(rows)
    print(f"\ndata/scorecard.csv: {len(rows)} rows, {len({r['metric'] for r in rows})} metrics, {len({r['council'] for r in rows})} councils")
    sc = pd.DataFrame(rows)
    print(sc.pivot(index="council", columns="metric", values="value").reindex(COUNCILS).to_string())

    age_rows = fetch_age_bands()
    with open(DATA_DIR / "age_bands.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["council", "band", "sex", "pct"])
        w.writeheader()
        w.writerows(age_rows)
    print(f"\ndata/age_bands.csv: {len(age_rows)} rows")
    ab = pd.DataFrame(age_rows)
    for sex in ["male", "female"]:
        print(f"\n-- {sex} --")
        s = ab[ab["sex"] == sex]
        print(s.pivot(index="council", columns="band", values="pct").reindex(COUNCILS)[["0-15", "16-29", "30-44", "45-64", "65+"]].to_string())
