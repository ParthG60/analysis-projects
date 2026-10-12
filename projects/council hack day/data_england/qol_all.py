"""Compile Quality of Life (QoL) indicators for ALL 282 English councils + England.

Indicators included:
1. life_expectancy    : ONS Life expectancy at birth (years, 2025, combined male/female avg)
2. rent_affordability : ONS PIPR median rent / ASHE median FT gross pay (%)
3. air_quality        : Defra/OHID mortality attributable to PM2.5 air pollution (%)
4. child_poverty      : DWP Children in low income families under 16 (%)
5. claimant_rate      : Nomis Claimant count % of 16-64 resident population (July 2026)
6. crime_rate         : ONS CSP recorded crime per 1,000 residents (2024)
7. overall_imd        : MHCLG IoD2025 overall deprivation score, decile, rank

Outputs: data_england/qol_all.csv
"""
import csv
import io
import time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).parent.parent
ENG_DIR = ROOT / "data_england"
DATA_DIR = ROOT / "data"

def get_registry():
    registry = {}
    with open(ENG_DIR / "scorecard_imd.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            registry.setdefault(r["ons_code"], r["council"])
    return registry

def build_qol_dataset():
    registry = get_registry()
    name_map = dict(registry)
    name_map["E92000001"] = "England"
    geo_codes = list(name_map.keys())

    print(f"1. Fetching Nomis Claimant Count for {len(geo_codes)} areas...")
    claimant_map = {}
    for i in range(0, len(geo_codes), 50):
        chunk = geo_codes[i : i + 50]
        url = "https://www.nomisweb.co.uk/api/v01/dataset/NM_162_1.data.csv"
        params = {
            "geography": ",".join(chunk),
            "date": "latest",
            "gender": "0", "age": "0", "measure": "2", "measures": "20100",
            "select": "geography_code,obs_value"
        }
        r = requests.get(url, params=params, timeout=30)
        for line in r.text.splitlines()[1:]:
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) >= 2 and parts[1]:
                try:
                    claimant_map[parts[0]] = round(float(parts[1]), 1)
                except ValueError:
                    pass
        time.sleep(0.1)

    print("2. Fetching Fingertips Life Expectancy, Child Poverty & Air Quality...")
    ft_url = "https://fingertips.phe.org.uk/api/all_data/csv/by_indicator_id?indicator_ids=90366,93701,93861"
    r = requests.get(ft_url, timeout=60)
    df_ft = pd.read_csv(io.StringIO(r.text), low_memory=False)

    # Life Expectancy: indicator 90366, latest period, average male + female
    df_le = df_ft[(df_ft["Indicator ID"] == 90366) & (df_ft["Category Type"].isna())]
    latest_le_period = df_le["Time period"].iloc[-1]
    df_le_latest = df_le[df_le["Time period"] == latest_le_period]
    le_map = {}
    for code, grp in df_le_latest.groupby("Area Code"):
        vals = grp["Value"].dropna().tolist()
        if vals:
            le_map[code] = round(sum(vals) / len(vals), 1)

    # Child Poverty: indicator 93701, latest period
    df_cp = df_ft[(df_ft["Indicator ID"] == 93701) & (df_ft["Category Type"].isna())]
    latest_cp_period = df_cp["Time period"].iloc[-1]
    df_cp_latest = df_cp[df_cp["Time period"] == latest_cp_period]
    cp_map = {}
    for _, row in df_cp_latest.iterrows():
        if pd.notna(row["Value"]):
            cp_map[row["Area Code"]] = round(float(row["Value"]), 1)

    # Air Quality: indicator 93861, latest period
    df_aq = df_ft[(df_ft["Indicator ID"] == 93861) & (df_ft["Category Type"].isna())]
    latest_aq_period = df_aq["Time period"].iloc[-1]
    df_aq_latest = df_aq[df_aq["Time period"] == latest_aq_period]
    aq_map = {}
    for _, row in df_aq_latest.iterrows():
        if pd.notna(row["Value"]):
            aq_map[row["Area Code"]] = round(float(row["Value"]), 2)

    print("3. Loading Rent Affordability, Crime Rate & GCSE Attainment 8...")
    sc_all = pd.read_csv(ENG_DIR / "scorecard_all.csv")
    sc_orig = pd.read_csv(DATA_DIR / "scorecard.csv")
    lad2cty = pd.read_csv(ENG_DIR / "lad_to_county_2023.csv").set_index("LAD23CD")["CTY23CD"].to_dict()

    rent_map = {}
    crime_map = {}
    att_map = {}
    for _, r in sc_all[sc_all["metric"] == "rent_affordability"].iterrows():
        rent_map[r["ons_code"]] = round(float(r["value"]), 1)
    for _, r in sc_all[sc_all["metric"] == "crime_per_1000"].iterrows():
        crime_map[r["ons_code"]] = round(float(r["value"]), 1)
    for _, r in sc_all[sc_all["metric"] == "attainment8"].iterrows():
        att_map[r["ons_code"]] = round(float(r["value"]), 1)

    orig_codes = {
        "Bradford": "E08000032", "Bristol": "E06000023", "Sheffield": "E08000019",
        "Kent": "E10000016", "Bromley": "E09000006", "Bath and North East Somerset": "E06000022",
        "Mid Suffolk": "E07000203", "Tower Hamlets": "E09000030", "Lancashire": "E10000017",
        "Leeds": "E08000035", "Manchester": "E08000003", "Camden": "E09000007",
        "Bexley": "E09000004", "Hillingdon": "E09000017", "Somerset": "E06000066",
        "England": "E92000001"
    }
    for _, r in sc_orig.iterrows():
        c = r["council"]
        code = orig_codes.get(c)
        if code:
            if r["metric"] == "rent_affordability":
                rent_map[code] = round(float(r["value"]), 1)
            elif r["metric"] == "crime_per_1000":
                crime_map[code] = round(float(r["value"]), 1)
            elif r["metric"] == "attainment8":
                att_map[code] = round(float(r["value"]), 1)

    # Proxy shire district missing values to parent county where appropriate
    for code in registry:
        parent = lad2cty.get(code)
        if parent:
            if code not in le_map and parent in le_map:
                le_map[code] = le_map[parent]
            if code not in cp_map and parent in cp_map:
                cp_map[code] = cp_map[parent]
            if code not in aq_map and parent in aq_map:
                aq_map[code] = aq_map[parent]
            if code not in crime_map and parent in crime_map:
                crime_map[code] = crime_map[parent]
            if code not in att_map and parent in att_map:
                att_map[code] = att_map[parent]

    print("4. Loading Overall Deprivation (IoD2025)...")
    imd_df = pd.read_csv(ENG_DIR / "scorecard_imd.csv")
    imd_overall = imd_df[imd_df["domain"] == "IMD"].set_index("ons_code")

    out_rows = []
    for code, name in name_map.items():
        imd_rec = imd_overall.loc[code] if code in imd_overall.index else None
        
        row = {
            "ons_code": code,
            "council": name,
            "life_expectancy": le_map.get(code, le_map.get("E92000001")),
            "rent_affordability": rent_map.get(code, rent_map.get("E92000001")),
            "attainment8": att_map.get(code, att_map.get("E92000001", 46.1)),
            "air_quality_pm25_pct": aq_map.get(code, aq_map.get("E92000001")),
            "child_poverty_pct": cp_map.get(code, cp_map.get("E92000001")),
            "claimant_rate_pct": claimant_map.get(code, claimant_map.get("E92000001")),
            "crime_per_1000": crime_map.get(code, crime_map.get("E92000001")),
            "imd_score": float(imd_rec["score"]) if imd_rec is not None else None,
            "imd_decile": int(imd_rec["decile"]) if imd_rec is not None else None,
            "imd_rank": int(imd_rec["rank"]) if imd_rec is not None else None,
            "imd_pool_n": int(imd_rec["pool_n"]) if imd_rec is not None else None,
            "imd_tier": imd_rec["tier"] if imd_rec is not None else None,
        }
        out_rows.append(row)

    out_df = pd.DataFrame(out_rows)

    # Calculate true national ranks in England (1 to 282)
    # Higher is better: life_expectancy, attainment8
    # Lower is better (best = lowest burden/rate): rent_affordability, air_quality, child_poverty, claimant_rate, crime
    councils_only = out_df[out_df["ons_code"] != "E92000001"].copy()
    councils_only["life_expectancy_rank"] = councils_only["life_expectancy"].rank(ascending=False, method="min").astype(int)
    councils_only["attainment8_rank"] = councils_only["attainment8"].rank(ascending=False, method="min").astype(int)
    councils_only["rent_affordability_rank"] = councils_only["rent_affordability"].rank(ascending=True, method="min").astype(int)
    councils_only["air_quality_rank"] = councils_only["air_quality_pm25_pct"].rank(ascending=True, method="min").astype(int)
    councils_only["child_poverty_rank"] = councils_only["child_poverty_pct"].rank(ascending=True, method="min").astype(int)
    councils_only["claimant_rate_rank"] = councils_only["claimant_rate_pct"].rank(ascending=True, method="min").astype(int)
    councils_only["crime_rank"] = councils_only["crime_per_1000"].rank(ascending=True, method="min").astype(int)
    councils_only["imd_national_rank"] = councils_only["imd_score"].rank(ascending=False, method="min").astype(int)
    
    # Merge national ranks back
    rank_cols = ["life_expectancy_rank", "attainment8_rank", "rent_affordability_rank", "air_quality_rank", "child_poverty_rank", "claimant_rate_rank", "crime_rank", "imd_national_rank"]
    for rc in rank_cols:
        rmap = dict(zip(councils_only["ons_code"], councils_only[rc]))
        out_df[rc] = out_df["ons_code"].map(rmap)

    out_path = ENG_DIR / "qol_all.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nSaved {len(out_df)} rows to {out_path} with all 7 national indicator ranks")
    return out_df

if __name__ == "__main__":
    build_qol_dataset()
