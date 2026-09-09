"""Export exact chart data for 3 figures — one Excel file with 3 sheets + CSVs.

Charts:
  1. crec_prevalence_calibrated_raw — CREC Extensions quarterly prevalence
  2. prevalence_quarterly_raw — Bills quarterly prevalence (aggregate, control, party)
  3. predictor_forest_119_binary — Predictor forest coefficients
"""
import pathlib
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parents[1]
DATA = HERE / "data"
FIG = HERE / "figures"

# ── Sheet 1: CREC Prevalence ──────────────────────────────────────────────

print("Sheet 1: Extension of Remarks ...")
cal = pd.read_csv(DATA / "crec_prevalence_calibrated.csv")
cal = cal[(cal.quarter >= "2023Q1") & (cal.quarter <= "2026Q2")].copy()
crec = pd.DataFrame({
    "quarter": cal["quarter"],
    "n_granules": cal["n_granules"],
    "prevalence_pct": (cal["point"] * 100).round(4),
})
print(f"  {len(crec)} quarters, 2026Q2 = {crec[crec.quarter=='2026Q2']['prevalence_pct'].values[0]:.2f}%")

# ── Sheet 2: Bills Prevalence ─────────────────────────────────────────────

print("Sheet 2: Bills ...")
# Reuse the same data pipeline as the chart
from generate_effort_style_charts import build_series  # noqa
quarters, comb, p_piv, comb_boot, dem_boot, rep_boot, ctrl = build_series()

bills = pd.DataFrame({
    "quarter": [str(q) for q in quarters],
    "n_bills": comb["n_bills"].values,
    "aggregate_pct": comb["pct_ai"].values.round(4),
    "control_pct": ctrl["pct_ai"].values.round(4),
    "dem_pct": p_piv["D"].values.round(4),
    "rep_pct": p_piv["R"].values.round(4),
})
print(f"  {len(bills)} quarters, 2026Q2 aggregate = {bills[bills.quarter=='2026Q2']['aggregate_pct'].values[0]:.2f}%")
print(f"  2026Q2 D = {bills[bills.quarter=='2026Q2']['dem_pct'].values[0]:.2f}%, "
      f"R = {bills[bills.quarter=='2026Q2']['rep_pct'].values[0]:.2f}%")

# ── Sheet 3: LPM Coefficients ─────────────────────────────────────────────

print("Sheet 3: LPM coefficients ...")
res = pd.read_csv(DATA / "federal_content_bill_classification_results.csv")
sub = res[(res["angle"] == "119th_binary") & (res["outcome"] == "ai_c65") & (res["model"] == "LPM")].copy()

VAR_LABELS = {
    "intercept": "Intercept (baseline prevalence)",
    "is_house": "House sponsor (vs Senate)",
    "is_solo_sponsor": "Solo sponsor (vs has cosponsors)",
    "age_per_decade_younger": "Per decade younger (vs 60yo)",
    "topic_crime_and_law_enforcement": "Crime & Law Enforcement (vs other topics)",
    "topic_finance_and_financial_sector": "Finance & Financial Sector (vs other topics)",
    "topic_labor_and_employment": "Labor & Employment (vs other topics)",
}

forest_rows = []
for _, r in sub.iterrows():
    coeff_pp = r["coeff"] * 100
    se_pp = r["se"] * 100
    ci_lo = coeff_pp - 1.96 * se_pp
    ci_hi = coeff_pp + 1.96 * se_pp
    label = VAR_LABELS.get(r["variable"], r["variable"])
    forest_rows.append({
        "variable": r["variable"],
        "label": label,
        "coeff_pp": round(coeff_pp, 4),
        "se_pp": round(se_pp, 4),
        "ci_lo_pp": round(ci_lo, 4),
        "ci_hi_pp": round(ci_hi, 4),
        "p_value": r["p"],
        "n": int(r["n"]),
    })

forest = pd.DataFrame(forest_rows)
print(f"  {len(forest)} predictors")

# ── Write Excel ───────────────────────────────────────────────────────────

xlsx_path = FIG / "chart_data_for_recreation.xlsx"
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
    crec.to_excel(writer, sheet_name="Extension of Remarks", index=False)
    bills.to_excel(writer, sheet_name="Bills", index=False)
    forest.to_excel(writer, sheet_name="LPM", index=False)
print(f"\nExcel -> {xlsx_path}")

# ── Write CSVs ────────────────────────────────────────────────────────────

crec.to_csv(FIG / "chart_data_extension_of_remarks.csv", index=False)
bills.to_csv(FIG / "chart_data_bills.csv", index=False)
forest.to_csv(FIG / "chart_data_lpm.csv", index=False)
print(f"CSV   -> {FIG / 'chart_data_extension_of_remarks.csv'}")
print(f"CSV   -> {FIG / 'chart_data_bills.csv'}")
print(f"CSV   -> {FIG / 'chart_data_lpm.csv'}")

print("\nDone.")