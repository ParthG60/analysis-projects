"""Socio-economic scorecard for ALL matched English councils (data_england/
name_map.csv, 267 unique ONS codes) -> data_england/scorecard_all.csv (long
format), reusing scorecard.py's source files/URLs (all cached in data/, read
only - never re-downloaded/modified here) and matching logic, generalized from
the original 15 hand-picked councils to the full set.

Metrics (council, metric, value, year, source, proxy) - see scorecard.py's
docstring for full source detail per metric. Generalization notes:

- attainment8    DfE KS4 is published at "education authority" level (unitaries,
                  London boroughs, metropolitan districts, counties). Shire
                  districts (SD class) are not education authorities -> proxy
                  to their parent county (data_england/lad_to_county_2023.csv),
                  same rule Mid Suffolk -> Suffolk used in scorecard.py.
- co2_per_capita  DESNZ GHG data's own "Second Tier Authority" field already
                  encodes the district->county hierarchy, so counties (SC
                  class) aggregate via that field (true aggregate, not proxy);
                  everyone else matches their own "Local Authority" row
                  directly.
- rent_affordability  ONS PIPR "Area code" column matches ONS geography codes
                  directly for all district/unitary/borough councils. Counties
                  (SC) = unweighted mean of constituent districts' rent (proxy,
                  same convention as Kent/Lancashire in scorecard.py). Monthly
                  pay from data_england/profile_all.csv median_ft_pay.
- crime_per_1000  ONS CSP "Local Authority code" column matches directly for
                  most LAs. A few councils only exist in the source as part of
                  a merged "Combined Local Authorities" CSP shared with a
                  neighbour (e.g. Devon's "East and Mid Devon") - these are
                  dropped, not guessed, same as scorecard.py's own "deadline-
                  driven build" convention. Counties (SC) aggregate = sum of
                  constituent districts with a direct match / summed pop of
                  those same districts; proxy=True if coverage is partial
                  (some constituent districts fell into a combined CSP),
                  proxy=False if every constituent district matched directly.
                  Cumberland, Westmorland and Furness, North Northamptonshire
                  and West Northamptonshire are dropped outright: this crime
                  source predates their local government reorganisation and
                  still lists only their old, superseded constituent districts.
- aroad_delay     DfT CGN0504d matches unitaries/boroughs/mets/counties by ONS
                  code directly. Shire districts proxy to their parent county
                  (districts are never highway authorities). North Yorkshire UA
                  is a direct match against the pre-2023 county code E10000023
                  (same highway-authority footprint, not a proxy - same
                  reasoning scorecard.py already applies to Somerset).

Usage: python england_scorecard.py
"""
import time
from pathlib import Path

import pandas as pd
import requests

from england_name_map import build_index, match_name
from england_profile import load_councils
from scorecard import fetch_ashe_pay

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "data_england"
SLEEP = 0.15
CHUNK = 40

LAD_TO_COUNTY = pd.read_csv(OUT_DIR / "lad_to_county_2023.csv")

rows = []  # scorecard_all.csv rows accumulate here


def add(council, ons_code, metric, value, year, source, proxy):
    if value is None:
        return
    rows.append({
        "council": council, "ons_code": ons_code, "metric": metric, "value": value,
        "year": year, "source": source, "proxy": proxy,
    })


def county_districts(county_name):
    """Constituent district ONS codes for a shire county, from the ONS LAD23->
    CTY23 lookup (data_england/lad_to_county_2023.csv, built from the ONS Open
    Geography Portal 'Local Authority District to County (April 2023) Lookup
    in England')."""
    hit = LAD_TO_COUNTY[LAD_TO_COUNTY["CTY23NM"].str.lower() == county_name.lower()]
    return hit["LAD23CD"].tolist()


# ---------------------------------------------------------------------------
# 1. Attainment 8 (DfE KS4 performance, revised, 2023/24)
# ---------------------------------------------------------------------------

KS4_CACHE = DATA_DIR / "202324_la_data_revised.csv"
KS4_SOURCE = "DfE explore-education-statistics, Key stage 4 performance (revised) 2023/24, LA data (avg_att8)"


def fetch_attainment8(councils):
    if not KS4_CACHE.exists():
        print("attainment8: data/202324_la_data_revised.csv not cached - run scorecard.py first, skipping")
        return

    df = pd.read_csv(KS4_CACHE)
    la = df[(df["geographic_level"] == "Local authority") & (df["sex"] == "Total") & (df["time_period"] == 202324)]
    idx = build_index(la["la_name"].unique())
    values = la.set_index("la_name")["avg_att8"]

    for _, c in councils.iterrows():
        if c["Class"] == "SD":
            county = LAD_TO_COUNTY[LAD_TO_COUNTY["LAD23CD"] == c["ons_code"]]["CTY23NM"]
            if county.empty:
                print(f"attainment8: no parent county for {c['council']!r}, dropping")
                continue
            target, proxy = county.iloc[0], True
        else:
            target, proxy = c["council"], False

        hit = match_name(target, idx)
        if hit is None:
            print(f"attainment8: no match for {c['council']!r} ({target!r}), dropping")
            continue
        add(c["council"], c["ons_code"], "attainment8", float(values[hit]), "2023/24", KS4_SOURCE, proxy)


# ---------------------------------------------------------------------------
# 2. CO2 per capita (DESNZ local authority GHG emissions)
# ---------------------------------------------------------------------------

GHG_CACHE = DATA_DIR / "ghg_emissions_2024.csv"
GHG_SOURCE = "DESNZ UK local authority and regional greenhouse gas emissions statistics 2005-2024, territorial CO2"


def fetch_co2_per_capita(councils):
    if not GHG_CACHE.exists():
        print("co2_per_capita: data/ghg_emissions_2024.csv not cached - run scorecard.py first, skipping")
        return

    df = pd.read_csv(GHG_CACHE)
    d = df[(df["Calendar Year"] == 2024) & (df["Greenhouse gas"] == "CO2")]

    def per_capita(mask):
        sub = d[mask]
        emissions_kt = sub["Territorial emissions (kt CO2e)"].sum()
        pop_thousands = sub.drop_duplicates(subset=["Local Authority Code"])["Mid-year Population (thousands)"].sum()
        return round(emissions_kt / pop_thousands, 2)

    la_idx = build_index(d["Local Authority"].dropna().unique())
    sta_idx = build_index(d["Second Tier Authority"].dropna().unique())

    for _, c in councils.iterrows():
        if c["Class"] == "SC":
            hit = match_name(c["council"], sta_idx)
            mask_col = "Second Tier Authority"
        else:
            hit = match_name(c["council"], la_idx)
            mask_col = "Local Authority"
        if hit is None:
            print(f"co2_per_capita: no match for {c['council']!r}, dropping")
            continue
        add(c["council"], c["ons_code"], "co2_per_capita", per_capita(d[mask_col] == hit), 2024, GHG_SOURCE, False)


# ---------------------------------------------------------------------------
# 3. Rent affordability (ONS PIPR rent / ASHE resident pay)
# ---------------------------------------------------------------------------

PIPR_CACHE = DATA_DIR / "pipr_latest.xlsx"


def fetch_rent_affordability(councils):
    if not PIPR_CACHE.exists():
        print("rent_affordability: data/pipr_latest.xlsx not cached - run scorecard.py first, skipping")
        return

    pipr = pd.read_excel(PIPR_CACHE, sheet_name="Table 1", header=2)
    period = pipr["Time period"].max()
    latest = pipr[pipr["Time period"] == period]
    year = period.strftime("%Y-%m")
    source = f"ONS Price Index of Private Rents, monthly price statistics {year} rent / data_england/profile_all.csv median_ft_pay"

    by_code = latest.set_index("Area code")["Rental price"]
    name_idx = build_index(latest["Area name"].unique())
    pay = pd.read_csv(OUT_DIR / "profile_all.csv").set_index("ons_code")["median_ft_pay"]

    def rent_for(code, name):
        if code in by_code.index:
            v = by_code.loc[code]
            return float(v.iloc[0]) if hasattr(v, "iloc") else float(v)
        hit = match_name(name, name_idx)
        return float(latest[latest["Area name"] == hit].iloc[0]["Rental price"]) if hit else None

    for _, c in councils.iterrows():
        if c["Class"] == "SC":
            district_codes = county_districts(c["council"])
            rents = [rent_for(code, code) for code in district_codes]
            rents = [r for r in rents if r is not None]
            if not rents:
                print(f"rent_affordability: no district rents for {c['council']!r}, dropping")
                continue
            rent, proxy = sum(rents) / len(rents), True
            if len(rents) != len(district_codes):
                print(f"rent_affordability: only {len(rents)}/{len(district_codes)} district matches for {c['council']!r}")
        else:
            rent = rent_for(c["ons_code"], c["council"])
            proxy = False
            if rent is None:
                print(f"rent_affordability: no PIPR match for {c['council']!r}, dropping")
                continue

        weekly_pay = pay.get(c["ons_code"])
        if pd.isna(weekly_pay):
            print(f"rent_affordability: no pay figure for {c['council']!r}, dropping")
            continue
        monthly_pay = weekly_pay * 52 / 12
        add(c["council"], c["ons_code"], "rent_affordability", round(rent / monthly_pay * 100, 1), year, source, proxy)


# ---------------------------------------------------------------------------
# 4. Crime per 1,000 (ONS recorded crime by CSP/LA, year ending March 2024)
# ---------------------------------------------------------------------------

CSP_CACHE = DATA_DIR / "csp_crime_yemar2024.xlsx"
CRIME_SOURCE = "ONS recorded crime by Community Safety Partnership area, year ending March 2024, Total recorded crime (excl. fraud) / ONS mid-2024 population (Nomis NM_2002_1)"

# these 4 new unitaries (Cumbria's 2023 split; Northamptonshire's 2021 split)
# postdate the CSP crime source, which still lists only their superseded old
# constituent districts under different geographies - dropping rather than
# building a from-scratch old-district-to-new-unitary remap.
CRIME_LGR_GAP = {"Cumberland", "Westmorland and Furness", "North Northamptonshire", "West Northamptonshire"}


def fetch_population_all(codes):
    url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
    out = {}
    for i in range(0, len(codes), CHUNK):
        batch = codes[i:i + CHUNK]
        params = {
            "geography": ",".join(batch), "date": 2024, "gender": "0", "c_age": "200",
            "measures": "20100", "select": "geography_code,obs_value",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        time.sleep(SLEEP)
        for line in r.text.splitlines()[1:]:
            code, value = [c.strip('"') for c in line.split(",")]
            out[code] = int(value)
    return out


def fetch_crime_per_1000(councils):
    if not CSP_CACHE.exists():
        print("crime_per_1000: data/csp_crime_yemar2024.xlsx not cached - run scorecard.py first, skipping")
        return

    crime = pd.read_excel(CSP_CACHE, sheet_name="Table C2", header=7)
    crime_col = "Total recorded crime\n (excluding fraud)"
    la_col = "Local Authority\n code"
    # drop the literal "Combined Local Authorities" placeholder rows (not a
    # real geography code); group-sum the rest - a handful of codes appear
    # more than once where a pre-2019/2020 CSP-level district split has since
    # been merged into a single current LA (e.g. old Suffolk Coastal +
    # Waveney rows both roll up to East Suffolk's E07000244).
    d = crime[crime[la_col].notna() & (crime[la_col] != "Combined Local Authorities")]
    direct = d.groupby(la_col)[crime_col].sum()

    pop = fetch_population_all([c for c in councils["ons_code"] if c is not None])

    for _, c in councils.iterrows():
        if c["council"] in CRIME_LGR_GAP:
            print(f"crime_per_1000: {c['council']!r} postdates this source's LGR coverage, dropping")
            continue

        if c["Class"] == "SC":
            district_codes = county_districts(c["council"])
            matched = [d for d in district_codes if d in direct.index]
            if not matched:
                print(f"crime_per_1000: no district crime data for {c['council']!r}, dropping")
                continue
            crime_total = direct.loc[matched].sum()
            pop_total = sum(pop[d] for d in matched if d in pop)
            rate = round(crime_total / pop_total * 1000, 1)
            proxy = len(matched) != len(district_codes)
            if proxy:
                print(f"crime_per_1000: {c['council']!r} partial county coverage {len(matched)}/{len(district_codes)} districts (combined CSPs excluded)")
            add(c["council"], c["ons_code"], "crime_per_1000", rate, "2023/24", CRIME_SOURCE, proxy)
        else:
            if c["ons_code"] not in direct.index or c["ons_code"] not in pop:
                print(f"crime_per_1000: no match for {c['council']!r}, dropping")
                continue
            rate = round(float(direct.loc[c["ons_code"]]) / pop[c["ons_code"]] * 1000, 1)
            add(c["council"], c["ons_code"], "crime_per_1000", rate, "2023/24", CRIME_SOURCE, False)


# ---------------------------------------------------------------------------
# 5. A-road delay (DfT CGN0504d)
# ---------------------------------------------------------------------------

CGN_CACHE = DATA_DIR / "cgn0504.ods"
AROAD_SOURCE = "DfT CGN0504d, average delay on locally managed 'A' roads by local authority, 2024 (seconds per vehicle per mile)"

# North Yorkshire UA: CGN0504d predates the 2023 LGR and still lists "North
# Yorkshire" under the old two-tier county code - same highway-authority
# footprint (districts were never highway authorities), so this is a direct
# match, not a proxy. Same reasoning scorecard.py already applies to Somerset.
AROAD_NAME_OVERRIDE = {"North Yorkshire": "E10000023"}


def fetch_aroad_delay(councils):
    if not CGN_CACHE.exists():
        print("aroad_delay: data/cgn0504.ods not cached - run scorecard.py first, skipping")
        return

    df = pd.read_excel(CGN_CACHE, engine="odf", sheet_name="CGN0504d", header=3)
    by_code = df.set_index("ONS area code")["2024"]

    for _, c in councils.iterrows():
        if c["council"] in AROAD_NAME_OVERRIDE:
            code, proxy = AROAD_NAME_OVERRIDE[c["council"]], False
        elif c["Class"] == "SD":
            county = LAD_TO_COUNTY[LAD_TO_COUNTY["LAD23CD"] == c["ons_code"]]["CTY23CD"]
            if county.empty:
                print(f"aroad_delay: no parent county for {c['council']!r}, dropping")
                continue
            code, proxy = county.iloc[0], True
        else:
            code, proxy = c["ons_code"], False

        if code not in by_code.index or pd.isna(by_code.loc[code]):
            print(f"aroad_delay: no match for {c['council']!r} ({code}), dropping")
            continue
        add(c["council"], c["ons_code"], "aroad_delay", float(by_code.loc[code]), 2024, AROAD_SOURCE, proxy)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    councils = load_councils()
    print(f"scorecarding {len(councils)} councils")

    fetch_attainment8(councils)
    fetch_co2_per_capita(councils)
    fetch_rent_affordability(councils)
    fetch_crime_per_1000(councils)
    fetch_aroad_delay(councils)

    OUT_DIR.mkdir(exist_ok=True)
    sc = pd.DataFrame(rows)
    sc.to_csv(OUT_DIR / "scorecard_all.csv", index=False)
    print(f"\ndata_england/scorecard_all.csv: {len(sc)} rows, "
          f"{sc['metric'].nunique()} metrics, {sc['council'].nunique()} councils")
    print(sc.groupby("metric").agg(n=("value", "size"), proxies=("proxy", "sum")))
