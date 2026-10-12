"""Build an IoD2025 (English Indices of Deprivation) scorecard for all 270 councils.

Pure IMD: overall IMD + 7 domains, keyed on ONS LAD code via data_england/name_map.csv.
County councils (E10) use File 11 (upper-tier, pool of 153); districts / unitaries /
mets / London boroughs use File 10 (lower-tier, pool of 296).

Each sheet layout (values_only tuple):
  [0] code  [1] name  [2] avg_rank  [3] rank_of_avg_rank  [4] avg_score
  [5] rank_of_avg_score  [6] prop_LSOA_in_most_deprived_10pct_nationally  ...

Output data_england/scorecard_imd.csv (long): one row per council per domain.
  rank        = rank of average rank (1 = MOST deprived in its pool)
  score       = average score (nationally comparable across tiers; higher = more deprived)
  prop10      = share of the council's LSOAs in England's most-deprived 10% (national, tier-agnostic)
  decile      = within-pool decile, 1 = most-deprived tenth ... 10 = least-deprived tenth
"""
import csv
import openpyxl

DOMAINS = ["IMD", "Income", "Employment", "Education", "Health", "Crime", "Barriers", "Living"]
F10, N10 = "data_imd/File_10_lower_tier.xlsx", 296  # lower-tier + unitary
F11, N11 = "data_imd/File_11_upper_tier.xlsx", 153  # upper-tier (counties)


def load(fn):
    """{code: {domain: (rank, score, prop10)}}"""
    wb = openpyxl.load_workbook(fn, read_only=True)
    out = {}
    for sh in DOMAINS:
        ws = wb[sh]
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]:
                continue
            out.setdefault(r[0], {})[sh] = (r[3], r[4], r[6])
    wb.close()
    return out


f10, f11 = load(F10), load(F11)

# Original 15 councils (harvested earlier into data_fy*, excluded from the England set).
# Codes lifted from scorecard.py ONS_CODES; Somerset = current unitary E06000066.
ORIGINAL_15 = {
    "E08000032": "Bradford", "E06000023": "Bristol", "E08000019": "Sheffield",
    "E10000016": "Kent", "E09000006": "Bromley", "E06000022": "Bath and North East Somerset",
    "E07000203": "Mid Suffolk", "E09000030": "Tower Hamlets", "E10000017": "Lancashire",
    "E08000035": "Leeds", "E08000003": "Manchester", "E09000007": "Camden",
    "E09000004": "Bexley", "E09000017": "Hillingdon", "E06000066": "Somerset",
}

# Data-only additions: English authorities absent from the Council Gateway (no minutes
# corpus), included so their outcomes/finance/borrowing/contracts still benchmark.
# K&C plus the five London boroughs the Gateway does not harvest (Greenwich, Newham,
# Redbridge, Richmond upon Thames, Waltham Forest).
SUPPLEMENTAL = {
    "E09000020": "Kensington and Chelsea",
    "E09000011": "Greenwich",
    "E09000025": "Newham",
    "E09000026": "Redbridge",
    "E09000027": "Richmond upon Thames",
    "E09000031": "Waltham Forest",
}

# Union: England 267 (name_map) + original 15 + data-only, keyed on ONS code (dedup).
councils = {}  # ons_code -> {"gateway_id", "council"}
with open("data_england/name_map.csv", encoding="utf-8") as fh:
    for c in csv.DictReader(fh):
        councils.setdefault(c["ons_code"], {"gateway_id": c["gateway_id"], "council": c["gateway_name"]})
for code, name in ORIGINAL_15.items():
    councils.setdefault(code, {"gateway_id": "", "council": name})
for code, name in SUPPLEMENTAL.items():
    councils.setdefault(code, {"gateway_id": "", "council": name})

rows = []
for code, c in councils.items():
    upper = code.startswith("E10")
    src, N, tier = (f11, N11, "upper") if upper else (f10, N10, "lower")
    d = src.get(code)
    if not d:  # drop-don't-fake: no IMD row -> skip, log
        print(f"  SKIP {c['council']} ({code}): no IMD row")
        continue
    for dom in DOMAINS:
        rank, score, prop10 = d[dom]
        decile = int((rank - 1) / N * 10) + 1
        rows.append({
            "gateway_id": c["gateway_id"],
            "council": c["council"],
            "ons_code": code,
            "tier": tier,
            "pool_n": N,
            "domain": dom,
            "rank": rank,
            "score": round(score, 3),
            "prop10": round(prop10, 4),
            "decile": decile,
        })

with open("data_england/scorecard_imd.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

councils = len({r["ons_code"] for r in rows})
print(f"Wrote data_england/scorecard_imd.csv: {councils} councils x {len(DOMAINS)} domains = {len(rows)} rows")
