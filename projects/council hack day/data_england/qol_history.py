"""Build multi-year Quality of Life time series -> site/qol_history.json + qol_trends.csv.

Sources (same OHID/Fingertips endpoint the snapshot uses, which carries full annual
history):
  - 90366 Life expectancy at birth (male + female averaged)
  - 93701 Children in absolute low income families (under 16s)
  - 93861 Air pollution: fraction of mortality attributable to PM2.5

For each metric we keep one value per council per period, rank councils 1..N (1 = best),
and precompute the median benchmark for three comparison scopes (England / ONS region /
authority class). We also emit per-council trend flags (materially improved/worsened vs
the cross-council distribution of changes).

Usage: python data_england/qol_history.py
"""
import csv
import io
import json
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent.parent
ENG_DIR = ROOT / "data_england"
SITE_DIR = ROOT / "site"

# metric key -> (indicator id, label, unit, lower_better, min_year)
METRICS = {
    "life_expectancy": (90366, "Life expectancy", "yrs", False, 2010),
    "child_poverty_pct": (93701, "Child poverty", "%", True, 2015),
    "air_quality_pm25_pct": (93861, "Air quality (PM2.5)", "%", True, 2015),
}
FT_URL = ("https://fingertips.phe.org.uk/api/all_data/csv/by_indicator_id"
          "?indicator_ids=90366,93701,93861")


def registry():
    reg = {}
    with open(ENG_DIR / "scorecard_imd.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            reg.setdefault(r["ons_code"], r["council"])
    return reg


def load_region():
    out = {}
    p = ENG_DIR / "lad_to_region.csv"
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                out[r["LAD23CD"]] = r["RGN23NM"]
    return out


def load_class():
    out = {}
    p = ENG_DIR / "finance_all.csv"
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                out[r["ons_code"]] = r["class"]
    return out


def end_year(period):
    """'2001 - 03' -> 2003; '2023/24' -> 2024; '2025' -> 2025."""
    p = str(period).strip()
    m = re.search(r"(\d{4})\s*-\s*(\d{2})$", p)          # '2001 - 03'
    if m:
        return int(m.group(1)[:2] + m.group(2))
    m = re.search(r"(\d{4})/(\d{2})$", p)                 # '2023/24'
    if m:
        return int(m.group(1)[:2] + m.group(2))
    m = re.search(r"(\d{4})", p)
    return int(m.group(1)) if m else None


def main():
    reg = registry()
    council_codes = set(reg.keys())
    region_of = load_region()
    class_of = load_class()

    print("Fetching Fingertips history...")
    r = requests.get(FT_URL, timeout=90)
    df = pd.read_csv(io.StringIO(r.text), low_memory=False)
    df = df[df["Category Type"].isna()]

    out_metrics = {}
    out_councils = {code: {} for code in council_codes}
    raw = {}   # metric -> {year: {code: value}}

    for key, (iid, label, unit, lower_better, min_year) in METRICS.items():
        sub = df[df["Indicator ID"] == iid]
        by_year = {}
        for _, row in sub.iterrows():
            code = row["Area Code"]
            if code not in council_codes:
                continue
            y = end_year(row["Time period"])
            v = row["Value"]
            if y is None or pd.isna(v) or y < min_year:
                continue
            by_year.setdefault(y, {}).setdefault(code, []).append(float(v))
        # average multi-row indicators (male/female life expectancy)
        by_year = {y: {c: round(sum(vs) / len(vs), 3) for c, vs in m.items()}
                   for y, m in by_year.items()}
        years = sorted(by_year.keys())
        raw[key] = (by_year, years)
        out_metrics[key] = {
            "label": label, "unit": unit, "lower_better": lower_better,
            "periods": years,
        }
        print(f"  {label}: {len(years)} periods ({years[0]}–{years[-1]})")

    # ---- per-council series + ranks -------------------------------------------
    for key, (by_year, years) in raw.items():
        lower_better = METRICS[key][3]
        for y in years:
            vals = by_year[y]
            ordered = sorted(vals.items(), key=lambda kv: kv[1], reverse=not lower_better)
            rank = {code: i for i, (code, _) in enumerate(ordered, 1)}
            for code in council_codes:
                series = out_councils[code].setdefault(key, {"v": [], "r": []})
                series["v"].append(vals.get(code))
                series["r"].append(rank.get(code))

    # ---- benchmarks: median per scope per year --------------------------------
    def median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        n = len(vals)
        m = n // 2
        return round((vals[m] if n % 2 else (vals[m - 1] + vals[m]) / 2), 3)

    benchmarks = {"england": {}, "region": {}, "type": {}}
    for key, (by_year, years) in raw.items():
        benchmarks["england"][key] = {"v": [median(by_year[y].values()) for y in years]}
        # region
        rscope = {}
        for code in council_codes:
            rg = region_of.get(code)
            if rg:
                rscope.setdefault(rg, []).append(code)
        for rg, codes in rscope.items():
            benchmarks["region"].setdefault(rg, {})[key] = {
                "v": [median([by_year[y].get(c) for c in codes]) for y in years]
            }
        # type
        tscope = {}
        for code in council_codes:
            cl = class_of.get(code)
            if cl:
                tscope.setdefault(cl, []).append(code)
        for cl, codes in tscope.items():
            benchmarks["type"].setdefault(cl, {})[key] = {
                "v": [median([by_year[y].get(c) for c in codes]) for y in years]
            }

    # ---- trend flags: material change vs cross-council distribution -----------
    trend_rows = []
    for key, (by_year, years) in raw.items():
        lower_better = METRICS[key][3]
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
            if abs(z) < 1.28:            # top/bottom ~10% of change
                continue
            worse = (d > 0) if lower_better else (d < 0)
            trend_rows.append({
                "ons_code": code, "metric": key,
                "direction": "worse" if worse else "better",
                "change": round(d, 3), "z": round(z, 2),
            })

    payload = {
        "metrics": out_metrics,
        "councils": out_councils,
        "benchmarks": benchmarks,
    }
    (SITE_DIR / "qol_history.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    with open(ENG_DIR / "qol_trends.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ons_code", "metric", "direction", "change", "z"])
        w.writeheader()
        w.writerows(sorted(trend_rows, key=lambda r: (r["ons_code"], r["metric"])))
    print(f"wrote qol_history.json ({len(out_councils)} councils) + "
          f"{len(trend_rows)} trend flags")


if __name__ == "__main__":
    main()
