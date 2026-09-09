"""Export per-observation Excel files for the two raw prevalence charts.

Outputs:
  - figures/prevalence_quarterly_raw_data.xlsx
    Columns: quarter, congress, bill_url, sponsor_party, expected_ai_pct
    One row per bill (findings/preamble max score aggregated to bill level).

  - figures/crec_prevalence_calibrated_raw_data.xlsx
    Columns: quarter, crec_url, member_name, expected_ai_pct
    One row per CREC Extensions of Remarks granule.
"""
import json
import pathlib
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parents[1]
DATA = HERE / "data"
V = HERE / "data" / "validation"
# Write to a temp dir first, then copy to the final path (avoids WSL file locking issues)
FIG = pathlib.Path("/tmp/ai_legislature_exports")
FIG.mkdir(parents=True, exist_ok=True)
FINAL = HERE / "figures"
FINAL.mkdir(exist_ok=True)

# ── Reusable helpers ──────────────────────────────────────────────────────

BINS_6 = ["[0.00, 0.20)", "[0.20, 0.35)", "[0.35, 0.50)",
          "[0.50, 0.65)", "[0.65, 0.80)", "[0.80, 1.00]"]
MIDS = np.array([0.10, 0.275, 0.425, 0.575, 0.725, 0.90])


def load_isotonic_calibration(corpus="federal_bills"):
    """Load corrected calibration, return empirical rates array."""
    calib = pd.read_csv(V / "joint_calibration_tables_corrected.csv")
    sub = calib[calib.corpus == corpus]
    emp = np.array([float(sub[sub.score_bin == b]["empirical_rate"].values[0]) for b in BINS_6])
    for i in range(1, len(emp)):
        if emp[i] < emp[i-1]:
            emp[i] = emp[i-1]
    return emp


def p_ai(score, rates):
    return np.interp(score, MIDS, rates, left=0.0, right=float(rates[-1]))


# ── 1. Bills export ───────────────────────────────────────────────────────

print("Exporting bills data...")

emp_rates = load_isotonic_calibration("federal_bills")

scores = pd.read_csv(DATA / "block_scores_3b.csv", low_memory=False)
scores["action_date"] = pd.to_datetime(scores["action_date"], errors="coerce")
scores = scores.dropna(subset=["action_date"])
scores["quarter"] = scores["action_date"].dt.to_period("Q")

# Content bills only (findings + preamble)
fb = scores[scores.block_type.isin(["findings", "preamble"])].copy()
fb["bill_url"] = "https://www.govinfo.gov/content/pkg/" + fb["package_id"] + "/html/" + fb["package_id"] + ".htm"

# Aggregate to bill level: max score per (congress, bill_type, bill_num, quarter, sponsor_party)
bills = fb.groupby(["congress", "bill_type", "bill_num", "quarter", "sponsor_party"], as_index=False).agg(
    max_score=("score", "max"),
    bill_url=("bill_url", "first"),
    package_id=("package_id", "first"),
)
bills["expected_ai_pct"] = p_ai(bills["max_score"].values, emp_rates) * 100

# Filter to chart range
bills = bills[(bills.quarter >= "2023Q1") & (bills.quarter <= "2026Q2")].copy()
bills["quarter"] = bills["quarter"].astype(str)
bills["congress"] = bills["congress"].astype(int)

out = bills[["quarter", "congress", "bill_url", "sponsor_party", "expected_ai_pct"]].copy()
out.columns = ["quarter", "congress", "bill_url", "sponsor_party", "expected_ai_pct"]
out = out.sort_values(["quarter", "sponsor_party"])

out_path = FIG / "prevalence_quarterly_raw_data.xlsx"
out.to_excel(out_path, index=False)
print(f"  Bills: {len(out):,} rows -> {out_path}")
csv_path = FIG / "prevalence_quarterly_raw_data.csv"
out.to_csv(csv_path, index=False)
print(f"  Bills: {len(out):,} rows -> {csv_path}")
print(f"  Columns: {list(out.columns)}")
print(f"  Quarter range: {out.quarter.min()} to {out.quarter.max()}")
print(f"  Expected AI % range: {out.expected_ai_pct.min():.2f}% to {out.expected_ai_pct.max():.2f}%")


# ── 2. CREC export ────────────────────────────────────────────────────────

print("\nExporting CREC data...")

# CREC-specific calibration bins (same as crec_prevalence_calibrated.py)
CREC_BINS = [0, .10, .20, .30, .40, .60, .876, 1.01]
CREC_LAB = ["<0.10", ".10-.20", ".20-.30", ".30-.40", ".40-.60", ".60-.876", ">.876"]

# Load CREC gold and compute bin rates (post-period only)
g1 = pd.DataFrame([json.loads(l) for l in open(V / "crec_gold.jsonl", encoding="utf-8")])
g2 = pd.DataFrame([json.loads(l) for l in open(V / "crec_gold_topup.jsonl", encoding="utf-8")])
g3 = pd.DataFrame([json.loads(l) for l in open(V / "recalibration_scores_600.jsonl", encoding="utf-8")])
g3_crec = g3[g3.corpus == "floor_speeches"].rename(columns={"editlens_score": "score_mean"}).copy()
g3_crec["pre"] = False
g = pd.concat([g1, g2, g3_crec], ignore_index=True)
g["ai"] = (g.fraction_ai.fillna(0) > 0.5).astype(int)
gp = g[~g.pre.astype(bool)].copy()
gp["bin"] = pd.cut(gp.score_mean, CREC_BINS, right=False, labels=CREC_LAB)
rates = gp.groupby("bin", observed=False).ai.agg(["sum", "count"])
# Convert to numpy arrays aligned with CREC_LAB
rate_map = {}
for lab in CREC_LAB:
    if lab in rates.index:
        rate_map[lab] = rates.loc[lab, "sum"] / rates.loc[lab, "count"]
    else:
        rate_map[lab] = 0.0
crec_rates = np.array([rate_map[lab] for lab in CREC_LAB])
crec_mids = np.array([0.05, 0.15, 0.25, 0.35, 0.50, 0.738, 0.943])

# Load scores and merge with metadata
scores_df = pd.read_json(DATA / "gpu" / "crec_scores.jsonl", lines=True)
agg = scores_df.groupby("text_sha").agg(
    score_mean=("score", "mean"),
).reset_index().rename(columns={"text_sha": "sha"})
tmap = pd.read_csv(DATA / "crec_text_map.csv")
corpus = agg.merge(tmap, on="sha", how="inner")
corpus = corpus[corpus.n_words >= 50].copy()
corpus["date"] = pd.to_datetime(corpus.date, errors="coerce")
corpus = corpus[corpus.date.notna()]
corpus["quarter"] = corpus.date.dt.to_period("Q").astype(str)

# Compute expected AI probability per granule
corpus["expected_ai_pct"] = np.interp(corpus.score_mean, crec_mids, crec_rates, left=0.0, right=float(crec_rates[-1])) * 100

# Build CREC URL — the HTML rendition path is dead (redirects to /error),
# but the govinfo app/details viewer works (confirmed 200).
corpus["crec_url"] = "https://www.govinfo.gov/app/details/" + corpus["package_id"]

# Filter to chart range
corpus = corpus[(corpus.quarter >= "2023Q1") & (corpus.quarter <= "2026Q2")].copy()

out2 = corpus[["quarter", "crec_url", "member_name", "expected_ai_pct"]].copy()
out2.columns = ["quarter", "crec_url", "member_name", "expected_ai_pct"]
out2 = out2.sort_values(["quarter", "member_name"])

out2_path = FIG / "crec_prevalence_calibrated_raw_data.xlsx"
out2.to_excel(out2_path, index=False)
print(f"  CREC: {len(out2):,} rows -> {out2_path}")
csv2_path = FIG / "crec_prevalence_calibrated_raw_data.csv"
out2.to_csv(csv2_path, index=False)
print(f"  CREC: {len(out2):,} rows -> {csv2_path}")
print(f"  Columns: {list(out2.columns)}")
print(f"  Quarter range: {out2.quarter.min()} to {out2.quarter.max()}")
print(f"  Expected AI % range: {out2.expected_ai_pct.min():.2f}% to {out2.expected_ai_pct.max():.2f}%")

# Copy to final figures directory (skip if locked by Windows)
import shutil
for f in ["prevalence_quarterly_raw_data.xlsx", "prevalence_quarterly_raw_data.csv",
          "crec_prevalence_calibrated_raw_data.xlsx", "crec_prevalence_calibrated_raw_data.csv"]:
    src = FIG / f
    dst = FINAL / f
    try:
        shutil.copy2(src, dst)
        print(f"  Copied -> {dst}")
    except PermissionError:
        print(f"  WARNING: could not copy to {dst} (file locked on Windows side)")
        print(f"  File is available at {src}")
print(f"  Columns: {list(out2.columns)}")
print(f"  Quarter range: {out2.quarter.min()} to {out2.quarter.max()}")
print(f"  Expected AI % range: {out2.expected_ai_pct.min():.2f}% to {out2.expected_ai_pct.max():.2f}%")

print("\nDone.")