"""Build multi-year Quality of Life time series -> site/qol_history.json + qol_trends.csv.

One series per council per indicator, for all eight scorecard cards, so every card
can show a trend. Sources:

  life_expectancy      OHID Fingertips 90366 (annual, male+female averaged)
  child_poverty_pct    OHID Fingertips 93701 (annual)
  air_quality_pm25_pct OHID Fingertips 93861 (annual)
  rent_affordability   ONS PIPR monthly rent / ASHE median full-time pay (Nomis NM_30_1)
  house_earnings       HM Land Registry UK HPI average price / ASHE pay
  claimant_rate_pct    Nomis NM_162_1 claimant count (July each year)
  crime_per_1000       ONS recorded crime by Community Safety Partnership / mid-year pop
  attainment8          DfE Key stage 4 performance (explore-education-statistics API)

County (E10) and shire-district (E07) councils are rolled up the same way the
snapshot scorecard does: counties = mean of districts (rent, house price) or
offence/population sum (crime); shire districts inherit their parent county for
attainment. Per-year national ranks (1 = best) and the median benchmark for three
comparison scopes (England / ONS region / authority class) are precomputed, plus
per-council trend flags (materially improved/worsened vs the cross-council spread).

Usage: python data_england/qol_history.py
"""
import csv
import io
import json
import re
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent.parent
ENG_DIR = ROOT / "data_england"
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
CACHE = ENG_DIR / "history_cache"
CACHE.mkdir(exist_ok=True)

SLEEP = 0.15
CHUNK = 50


def _get(url, **kw):
    """GET with retries — public stats endpoints occasionally drop connections."""
    last = None
    for attempt in range(5):
        try:
            r = requests.get(url, **kw)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last

FT_URL = ("https://fingertips.phe.org.uk/api/all_data/csv/by_indicator_id"
          "?indicator_ids=90366,93701,93861")
NOMIS_ASHE = "https://www.nomisweb.co.uk/api/v01/dataset/NM_30_1.data.csv"
NOMIS_CLAIM = "https://www.nomisweb.co.uk/api/v01/dataset/NM_162_1.data.csv"
NOMIS_POP = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
HMLR_BASE = ("http://publicdata.landregistry.gov.uk/market-trend-data/"
             "house-price-index-data/UK-HPI-full-file-{}.csv")
EES_PUB = "https://content.explore-education-statistics.service.gov.uk/api/publications/key-stage-4-performance"
ONS_CRIME_PAGE = ("https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/"
                  "datasets/recordedcrimedatabycommunitysafetypartnershiparea")

# key -> (label, unit, lower_better, min_year, first_year)
METRICS = {
    "life_expectancy":      ("Life expectancy", "yrs", False, 2004),
    "attainment8":          ("GCSE Attainment 8", "pts", False, 2019),
    "rent_affordability":   ("Rent affordability", "%", True, 2015),
    "air_quality_pm25_pct": ("Air quality (PM2.5)", "%", True, 2015),
    "child_poverty_pct":    ("Child poverty", "%", True, 2015),
    "claimant_rate_pct":    ("Claimant rate", "%", True, 2004),
    "crime_per_1000":       ("Crime rate", "", True, 2015),
    "house_earnings":       ("House / earnings", "×", True, 2004),
}


# --------------------------------------------------------------- reference ---
def registry():
    reg = {}
    with open(ENG_DIR / "scorecard_imd.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            reg.setdefault(r["ons_code"], r["council"])
    return reg


def _csv_map(path, key_col, val_col):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r[key_col]] = r[val_col]
    return out


def load_region():
    return _csv_map(ENG_DIR / "lad_to_region.csv", "LAD23CD", "RGN23NM")


def load_class():
    return _csv_map(ENG_DIR / "finance_all.csv", "ons_code", "class")


def load_parent_county():
    return _csv_map(ENG_DIR / "lad_to_county_2023.csv", "LAD23CD", "CTY23CD")


def load_districts_by_county():
    out = {}
    with open(ENG_DIR / "lad_to_county_2023.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["CTY23CD"], []).append(r["LAD23CD"])
    return out


def end_year(period):
    p = str(period).strip()
    m = re.match(r"^(\d{4})(\d{2})$", p)          # '202324' (DfE academic year) -> 2024
    if m:
        return int(m.group(1)[:2] + m.group(2))
    m = re.search(r"(\d{4})\s*-\s*(\d{2})$", p)
    if m:
        return int(m.group(1)[:2] + m.group(2))
    m = re.search(r"(\d{4})/(\d{2})$", p)
    if m:
        return int(m.group(1)[:2] + m.group(2))
    m = re.search(r"(\d{4})", p)
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------- sources ---
def _fingertips_from_previous(council_codes):
    """Reconstruct the three Fingertips series from an existing qol_history.json,
    so a Fingertips outage doesn't wipe trends for life expectancy / child poverty /
    air quality. Returns None if nothing usable is on disk."""
    p = SITE_DIR / "qol_history.json"
    if not p.exists():
        return None
    try:
        hist = json.loads(p.read_text())
    except Exception:
        return None
    keys = ["life_expectancy", "child_poverty_pct", "air_quality_pm25_pct"]
    if not all(k in hist.get("metrics", {}) for k in keys):
        return None
    out = {}
    for k in keys:
        years = hist["metrics"][k]["periods"]
        by_year = {y: {} for y in years}
        for code, series in hist.get("councils", {}).items():
            vals = series.get(k, {}).get("v", [])
            for y, v in zip(years, vals):
                if v is not None:
                    by_year[y][code] = v
        out[k] = {y: m for y, m in by_year.items() if m}
    print("  (Fingertips unavailable — reused cached series from qol_history.json)")
    return out


def fetch_fingertips(council_codes):
    print("Fingertips (life expectancy, child poverty, air quality)...")
    cache_f = CACHE / "fingertips.csv"
    csv_text = None
    if cache_f.exists():
        csv_text = cache_f.read_text()
    else:
        try:
            csv_text = _get(FT_URL, timeout=120).text
            cache_f.write_text(csv_text)
        except Exception as e:
            print(f"  Fingertips fetch failed: {e}")
    if csv_text is None:
        fallback = _fingertips_from_previous(council_codes)
        if fallback is not None:
            return fallback
        raise RuntimeError("Fingertips unavailable and no cached series on disk")

    df = pd.read_csv(io.StringIO(csv_text), low_memory=False)
    df = df[df["Category Type"].isna()]
    specs = {"life_expectancy": 90366, "child_poverty_pct": 93701, "air_quality_pm25_pct": 93861}
    out = {}
    for key, iid in specs.items():
        sub = df[df["Indicator ID"] == iid]
        by_year = {}
        for _, row in sub.iterrows():
            code = row["Area Code"]
            if code not in council_codes:
                continue
            y = end_year(row["Time period"])
            v = row["Value"]
            if y is None or pd.isna(v) or y < METRICS[key][3]:
                continue
            by_year.setdefault(y, {}).setdefault(code, []).append(float(v))
        out[key] = {y: {c: round(sum(vs) / len(vs), 3) for c, vs in m.items()}
                    for y, m in by_year.items()}
        print(f"  {key}: {len(out[key])} years")
    return out


def fetch_ashe(codes, years):
    """{year: {ons_code: weekly_pay}} — ASHE resident analysis, full-time, all."""
    print("ASHE median full-time pay (Nomis)...")
    out = {y: {} for y in years}
    codes = list(codes)
    for i in range(0, len(codes), CHUNK):
        batch = codes[i:i + CHUNK]
        params = {
            "geography": ",".join(batch), "date": ",".join(str(y) for y in years),
            "sex": "8", "item": "2", "pay": "1", "measures": "20100",
            "select": "geography_code,date,obs_value",
        }
        r = _get(NOMIS_ASHE, params=params, timeout=60)
        r.raise_for_status()
        time.sleep(SLEEP)
        for line in r.text.splitlines()[1:]:
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) < 3 or not parts[2]:
                continue
            out[int(parts[1])][parts[0]] = float(parts[2])
    return out


def _pipr_file():
    local = DATA_DIR / "pipr_latest.xlsx"
    if local.exists():
        return local
    raise FileNotFoundError("data/pipr_latest.xlsx missing")


def fetch_rent(pay_by_year, years):
    """{year: {ons_code: rent_as_pct_of_monthly_pay}} using July of each year."""
    print("Rent affordability (PIPR monthly rent / ASHE pay)...")
    pipr = pd.read_excel(_pipr_file(), sheet_name="Table 1", header=2)
    pipr["Time period"] = pd.to_datetime(pipr["Time period"])
    pipr["Rental price"] = pd.to_numeric(pipr["Rental price"], errors="coerce")
    pipr = pipr[pipr["Rental price"].notna()]
    out = {}
    for y in years:
        # July of the year (fall back to nearest month <= July)
        months = pipr[pipr["Time period"].dt.year == y]
        if months.empty:
            continue
        jul = months[months["Time period"].dt.month == 7]
        row = jul if not jul.empty else months.sort_values("Time period").tail(1)
        rent = row.groupby("Area code")["Rental price"].mean()
        pay = pay_by_year.get(min(y, max(pay_by_year)), {})
        vals = {}
        for code, rv in rent.items():
            wk = pay.get(code)
            if wk is None or pd.isna(rv):
                continue
            vals[code] = round(float(rv) / (wk * 52 / 12) * 100, 1)
        out[y] = vals
    print(f"  rent: {len(out)} years")
    return out


def _hmlr_file():
    cached = sorted(CACHE.glob("hmlr_*.csv"))
    if cached:
        return cached[-1]
    from datetime import date
    today = date.today()
    for i in range(12):
        idx = today.month - 1 - i
        year = today.year + (idx - 1) // 12
        month = (idx - 1) % 12 + 1
        tag = f"{year}-{month:02d}"
        r = _get(HMLR_BASE.format(tag), timeout=180)
        time.sleep(SLEEP)
        if r.status_code == 200 and r.content[:4] == b"Date":
            p = CACHE / f"hmlr_{tag}.csv"
            p.write_bytes(r.content)
            return p
    raise RuntimeError("no HMLR file found")


def fetch_house_earnings(pay_by_year, years):
    """{year: {ons_code: avg_price / annual_ft_pay}} using July price of each year."""
    print("House / earnings (HM Land Registry HPI / ASHE pay)...")
    df = pd.read_csv(_hmlr_file(), usecols=["Date", "AreaCode", "AveragePrice"])
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    df["AveragePrice"] = pd.to_numeric(df["AveragePrice"], errors="coerce")
    df = df[df["AveragePrice"].notna()]
    out = {}
    for y in years:
        rows = df[df["Date"].dt.year == y]
        if rows.empty:
            continue
        jul = rows[rows["Date"].dt.month == 7]
        price = (jul if not jul.empty else rows.sort_values("Date").tail(1)).groupby("AreaCode")["AveragePrice"].mean()
        pay = pay_by_year.get(min(y, max(pay_by_year)), {})
        vals = {}
        for code, pv in price.items():
            wk = pay.get(code)
            if wk is None or pd.isna(pv):
                continue
            vals[code] = round(float(pv) / (wk * 52), 1)
        out[y] = vals
    print(f"  house_earnings: {len(out)} years")
    return out


def fetch_claimant(codes, years):
    print("Claimant rate (Nomis, July each year)...")
    out = {}
    codes = list(codes)
    dates = [f"{y}-07" for y in years]
    for i in range(0, len(codes), CHUNK):
        batch = codes[i:i + CHUNK]
        params = {"geography": ",".join(batch), "date": ",".join(dates),
                  "gender": "0", "age": "0", "measure": "2", "measures": "20100",
                  "select": "geography_code,date,obs_value"}
        r = _get(NOMIS_CLAIM, params=params, timeout=60)
        r.raise_for_status()
        time.sleep(SLEEP)
        for line in r.text.splitlines()[1:]:
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) < 3 or not parts[2]:
                continue
            out.setdefault(int(parts[1][:4]), {})[parts[0]] = float(parts[2])
    print(f"  claimant: {len(out)} years")
    return out


def fetch_population(codes, years):
    print("Population by year (Nomis)...")
    out = {}
    codes = list(codes)
    for y in years:
        out[y] = {}
        for i in range(0, len(codes), CHUNK):
            batch = codes[i:i + CHUNK]
            params = {"geography": ",".join(batch), "date": y, "gender": "0",
                      "c_age": "200", "measures": "20100", "select": "geography_code,obs_value"}
            r = _get(NOMIS_POP, params=params, timeout=60)
            r.raise_for_status()
            time.sleep(SLEEP)
            for line in r.text.splitlines()[1:]:
                parts = [c.strip('"') for c in line.split(",")]
                if len(parts) < 2 or not parts[1]:
                    continue
                out[y][parts[0]] = int(float(parts[1]))
    return out


def _ons_crime_files():
    """Year-ending-March CSP tables only, for a consistent annual series
    (matches the card's 'year ending March 2024' definition)."""
    r = _get(ONS_CRIME_PAGE, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    out = {}
    for href, year in re.findall(r'href="(/file\?uri=[^"]*yearendingmarch(\d{4})[^"]*\.xlsx)"', r.text, re.I):
        out[int(year)] = "https://www.ons.gov.uk" + href
    return out


def _read_csp_table(content):
    """Read the LA-level crime table from a CSP workbook, locating the header row
    and normalising column names (layout/wording drifts between releases)."""
    raw = pd.read_excel(io.BytesIO(content), sheet_name="Table C2", header=None)
    hdr = None
    for i in range(min(15, len(raw))):
        if any("Local Authority" in str(v) for v in raw.iloc[i].tolist()):
            hdr = i
            break
    if hdr is None:
        return None
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in raw.iloc[hdr].tolist()]
    return df


def _col_starting(df, prefix):
    for c in df.columns:
        if c.lower().startswith(prefix):
            return c
    return None


def fetch_crime(years):
    """Returns (offences, pop): {year: {ons_code: n}}. Rates are computed later so
    counties can be rolled up as summed offences / summed population."""
    print("Crime per 1,000 (ONS CSP tables, year ending March)...")
    files = _ons_crime_files()
    offences = {}
    for y in sorted(files):
        if y < min(years):
            continue
        try:
            cached = CACHE / f"crime_yemar{y}.xlsx"
            if cached.exists():
                content = cached.read_bytes()
            else:
                content = _get(files[y], timeout=120).content
                cached.write_bytes(content)
            crime = _read_csp_table(content)
        except Exception as e:
            print(f"  crime {y}: failed ({e})")
            continue
        time.sleep(SLEEP)
        if crime is None:
            print(f"  crime {y}: no header row found, skipping")
            continue
        la_col = _col_starting(crime, "local authority code")
        crime_col = _col_starting(crime, "total recorded crime")
        if not la_col or not crime_col:
            print(f"  crime {y}: expected columns missing, skipping")
            continue
        d = crime[crime[la_col].notna() & (crime[la_col] != "Combined Local Authorities")]
        vals = pd.to_numeric(d[crime_col], errors="coerce")
        d = d.assign(_v=vals).dropna(subset=["_v"])
        offences[y] = d.groupby(la_col)["_v"].sum().to_dict()
    if not offences:
        return {}, {}
    all_codes = list({c for m in offences.values() for c in m})
    pop = fetch_population(all_codes, sorted(offences))
    print(f"  crime: {len(offences)} years")
    return offences, pop


def crime_rates(offences, pop, council_codes, class_of, districts_of):
    """{year: {ons_code: rate}} — counties = summed district offences / summed pop."""
    out = {}
    for y, m in offences.items():
        yr_pop = pop.get(y, {})
        vals = {}
        for code in council_codes:
            cls = class_of.get(code)
            if cls == "SC":
                ds = districts_of.get(code, [])
                off = sum(m[d] for d in ds if d in m)
                pp = sum(yr_pop[d] for d in ds if d in yr_pop)
            else:
                off = m.get(code)
                pp = yr_pop.get(code)
            if off is not None and pp:
                vals[code] = round(float(off) / pp * 1000, 1)
        out[y] = vals
    return out


def _ees_la_files():
    pub = _get(EES_PUB, timeout=60).json()
    rels = _get(EES_PUB + "/releases", timeout=60).json()
    out = []  # (end_year, url_to_zip)
    for rel in rels:
        rid = rel.get("id")  # the release `id` is the /files path key (releaseId is not)
        year_title = rel.get("yearTitle") or ""
        m = re.search(r"(\d{4})/(\d{2})", year_title)
        if not m or not rid:
            continue
        end = int(m.group(1)[:2] + m.group(2))
        out.append((end, f"https://content.explore-education-statistics.service.gov.uk/api/releases/{rid}/files"))
    return out


def fetch_attainment(years):
    """{year: {new_la_code: avg_att8}} from the latest DfE KS4 release, whose LA
    file carries the full year series (district->county proxy applied later)."""
    print("Attainment 8 (DfE KS4 release)...")
    rels = _ees_la_files()
    if not rels:
        return {}
    df = None
    for end, url in sorted(rels, reverse=True):
        try:
            cached = CACHE / f"ks4_{end}.zip"
            if cached.exists():
                content = cached.read_bytes()
            else:
                content = _get(url, timeout=300).content
                cached.write_bytes(content)
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                cands = [n for n in z.namelist()
                         if re.search(r"\d{6}_la_data.*\.csv$", n, re.I)
                         and "_ap_" not in n and "subject" not in n]
                if not cands:
                    continue
                df = pd.read_csv(z.open(sorted(cands)[0]))
            break
        except Exception as e:
            print(f"  attainment release {end}: failed ({e}); trying older")
            continue
    if df is None:
        print("  attainment: no usable release")
        return {}

    code_col = "new_la_code" if "new_la_code" in df.columns else None
    if not code_col or "avg_att8" not in df.columns or "time_period" not in df.columns:
        print("  attainment: missing code/avg_att8/time_period columns")
        return {}
    sub = df
    if "geographic_level" in sub.columns:
        sub = sub[sub["geographic_level"] == "Local authority"]
    if "sex" in sub.columns:
        sub = sub[sub["sex"] == "Total"]
    sub = sub.assign(_att=pd.to_numeric(sub["avg_att8"], errors="coerce")).dropna(subset=["_att"])

    out = {}
    for tp, grp in sub.groupby("time_period"):
        y = end_year(str(tp))
        if y is None or y < min(years) or y > max(years):
            continue
        out[y] = {str(r[code_col]): round(float(r["_att"]), 1) for _, r in grp.iterrows()}
    print(f"  attainment: {len(out)} years")
    return out


# ------------------------------------------------------------- rollup logic ---
def rollup(by_year, council_codes, class_of, parent_of, districts_of, mode):
    """Fill county / shire-district values in a per-LAD map.
    mode: 'county_mean' | 'district_parent' | 'direct'."""
    out = {y: dict(m) for y, m in by_year.items()}
    for y, m in by_year.items():
        for code in council_codes:
            cls = class_of.get(code)
            if mode == "county_mean" and cls == "SC":
                vals = [m[d] for d in districts_of.get(code, []) if d in m]
                if vals:
                    out[y][code] = round(sum(vals) / len(vals), 2)
            elif mode == "district_parent" and cls == "SD":
                p = parent_of.get(code)
                if p in m:
                    out[y][code] = m[p]
    return out


def main():
    council_codes = set(registry())
    region_of = load_region()
    class_of = load_class()
    parent_of = load_parent_county()
    districts_of = load_districts_by_county()

    ashe_years = list(range(2004, 2026))
    years_common = list(range(2004, 2027))

    raw = {}
    raw.update(fetch_fingertips(council_codes))

    pay = fetch_ashe(council_codes, ashe_years)
    raw["rent_affordability"] = rollup(fetch_rent(pay, years_common), council_codes, class_of, parent_of, districts_of, "county_mean")
    raw["house_earnings"] = rollup(fetch_house_earnings(pay, years_common), council_codes, class_of, parent_of, districts_of, "county_mean")
    raw["claimant_rate_pct"] = rollup(fetch_claimant(council_codes, years_common), council_codes, class_of, parent_of, districts_of, "direct")
    crime_off, crime_pop = fetch_crime(list(range(2015, 2025)))
    raw["crime_per_1000"] = crime_rates(crime_off, crime_pop, council_codes, class_of, districts_of)
    raw["attainment8"] = rollup(fetch_attainment(list(range(2019, 2025))), council_codes, class_of, parent_of, districts_of, "district_parent")

    # ---- assemble per-council series, ranks, benchmarks -----------------------
    out_metrics = {}
    out_councils = {code: {} for code in council_codes}
    for key, by_year in raw.items():
        label, unit, lower_better, min_year = METRICS[key]
        by_year = {y: m for y, m in by_year.items() if y >= min_year and m}
        if not by_year:
            continue
        years = sorted(by_year)
        out_metrics[key] = {"label": label, "unit": unit, "lower_better": lower_better, "periods": years}
        for y in years:
            vals = by_year[y]
            ordered = sorted(vals.items(), key=lambda kv: kv[1], reverse=not lower_better)
            rank = {code: i for i, (code, _) in enumerate(ordered, 1)}
            for code in council_codes:
                s = out_councils[code].setdefault(key, {"v": [], "r": []})
                s["v"].append(vals.get(code))
                s["r"].append(rank.get(code))

    def median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        n = len(vals)
        m = n // 2
        return round((vals[m] if n % 2 else (vals[m - 1] + vals[m]) / 2), 3)

    benchmarks = {"england": {}, "region": {}, "type": {}}
    for key, by_year in raw.items():
        if key not in out_metrics:
            continue
        years = out_metrics[key]["periods"]
        by_year = {y: by_year.get(y, {}) for y in years}
        benchmarks["england"][key] = {"v": [median(by_year[y].values()) for y in years]}
        for scope, groups in (("region", region_of), ("type", class_of)):
            codes_by = {}
            for code in council_codes:
                g = groups.get(code)
                if g:
                    codes_by.setdefault(g, []).append(code)
            for g, codes in codes_by.items():
                benchmarks[scope].setdefault(g, {})[key] = {
                    "v": [median([by_year[y].get(c) for c in codes]) for y in years]
                }

    # ---- trend flags ----------------------------------------------------------
    trend_rows = []
    for key, by_year in raw.items():
        if key not in out_metrics:
            continue
        lower_better = METRICS[key][2]
        deltas = {}
        for code in council_codes:
            series = [v for v in out_councils[code][key]["v"] if v is not None]
            if len(series) >= 3:
                deltas[code] = series[-1] - series[0]
        if len(deltas) < 20:
            continue
        s = pd.Series(list(deltas.values()))
        mu, sd = s.mean(), s.std()
        if not sd:
            continue
        for code, d in deltas.items():
            z = (d - mu) / sd
            if abs(z) < 1.28:
                continue
            worse = (d > 0) if lower_better else (d < 0)
            trend_rows.append({"ons_code": code, "metric": key,
                               "direction": "worse" if worse else "better",
                               "change": round(d, 3), "z": round(z, 2)})

    payload = {"metrics": out_metrics, "councils": out_councils, "benchmarks": benchmarks}
    (SITE_DIR / "qol_history.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    with open(ENG_DIR / "qol_trends.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ons_code", "metric", "direction", "change", "z"])
        w.writeheader()
        w.writerows(sorted(trend_rows, key=lambda r: (r["ons_code"], r["metric"])))
    print(f"wrote qol_history.json ({len(out_councils)} councils, {len(out_metrics)} metrics) + "
          f"{len(trend_rows)} trend flags")


if __name__ == "__main__":
    main()
