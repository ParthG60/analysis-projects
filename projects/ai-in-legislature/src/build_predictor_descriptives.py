"""Descriptive transparency table for the predictor forest.

For each variable in the headline model (119th Congress, calibrated binary c≥0.65),
shows raw counts, AI-positive rates, and progression rates — unadjusted by any model.
"""
import pathlib
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parents[1]
DATA = HERE / "data"
FIG = HERE / "figures"

# ── Load and filter to 119th Congress content bills (same as model sample) ──

df = pd.read_csv(DATA / "federal_content_bills_extended.csv", low_memory=False)
d119 = df[df["congress"] == 119].copy()

# Same outcome as the headline forest: calibrated binary flag
# ai_c65 = score_max >= 0.65 (is also available as a column, but compute it fresh)
d119["ai_c65"] = (d119["score_max"] >= 0.65).astype(int)

# Progression metric: succeeded in 12 months
d119["succeeded"] = d119["succeeded_12m"].astype(int)

N = len(d119)
print(f"119th Congress content bills: N = {N:,}")
print(f"  AI-positive (c≥0.65): {d119['ai_c65'].sum():,} ({d119['ai_c65'].mean()*100:.1f}%)")
print(f"  Succeeded in 12m: {d119['succeeded'].sum():,} ({d119['succeeded'].mean()*100:.1f}%)")
print()

# ── Helper ──

def describe_binary(series, label, group0="No", group1="Yes"):
    """Describe a binary variable: group sizes, AI rate, progression rate."""
    rows = []
    for v, gname in [(0, group0), (1, group1)]:
        sub = d119[series == v]
        n = len(sub)
        n_ai = sub["ai_c65"].sum()
        pct_ai = sub["ai_c65"].mean() * 100
        n_succ = sub["succeeded"].sum()
        pct_succ = sub["succeeded"].mean() * 100
        rows.append({
            "Variable": label,
            "Group": gname,
            "N bills": n,
            "% of total": n / N * 100,
            "N AI-positive": n_ai,
            "% AI-positive": pct_ai,
            "N succeeded": n_succ,
            "% succeeded": pct_succ,
        })
    return rows


def describe_categorical(series, name):
    """Describe a multi-category variable (like topic dummies)."""
    rows = []
    # Reference: all other topics
    sub_other = d119[series == 0]
    n_other = len(sub_other)
    pct_ai_other = sub_other["ai_c65"].mean() * 100
    pct_succ_other = sub_other["succeeded"].mean() * 100

    rows.append({
        "Variable": name,
        "Group": f"All other topics",
        "N bills": n_other,
        "% of total": n_other / N * 100,
        "N AI-positive": int(sub_other["ai_c65"].sum()),
        "% AI-positive": pct_ai_other,
        "N succeeded": int(sub_other["succeeded"].sum()),
        "% succeeded": pct_succ_other,
    })

    sub = d119[series == 1]
    n = len(sub)
    rows.append({
        "Variable": name,
        "Group": name,
        "N bills": n,
        "% of total": n / N * 100,
        "N AI-positive": int(sub["ai_c65"].sum()),
        "% AI-positive": sub["ai_c65"].mean() * 100,
        "N succeeded": int(sub["succeeded"].sum()),
        "% succeeded": sub["succeeded"].mean() * 100,
    })
    return rows


# ── Build table ──

all_rows = []

# Compute needed columns first
age_med = d119["member_age"].median()
d119["is_solo"] = (d119["n_cosponsors"].fillna(0) == 0).astype(int)
d119["younger"] = (d119["member_age"] <= age_med).astype(int)

# 0. Reference category (model intercept): Senate, not solo, older, not crime/finance/labor
intercept_mask = (
    (d119["is_house"] == 0) &
    (d119["is_solo"] == 0) &
    (d119["member_age"] > age_med) &
    (d119["topic_crime_and_law_enforcement"] == 0) &
    (d119["topic_finance_and_financial_sector"] == 0) &
    (d119["topic_labor_and_employment"] == 0)
)
sub = d119[intercept_mask]
all_rows.append({
    "Variable": "Reference category",
    "Group": "Senate, has cosponsors, older, non-pole topics",
    "N bills": len(sub),
    "% of total": len(sub) / N * 100,
    "N AI-positive": int(sub["ai_c65"].sum()),
    "% AI-positive": sub["ai_c65"].mean() * 100,
    "N succeeded": int(sub["succeeded"].sum()),
    "% succeeded": sub["succeeded"].mean() * 100,
})

# 1. Institutional capacity: House vs Senate
all_rows += describe_binary(d119["is_house"], "House sponsor", group0="Senate", group1="House")

# 2. Coalition scrutiny: solo sponsor
# is_solo_sponsor not in extended CSV? Let's compute it
all_rows += describe_binary(d119["is_solo"], "Solo sponsor", group0="Has cosponsors", group1="Solo sponsor")

# 3. Age: split at median for a clean binary comparison
all_rows += describe_binary(d119["younger"], f"Age ≤{age_med:.0f}", group0=f"Older (>{age_med:.0f})", group1=f"Younger (≤{age_med:.0f})")

# 4. Policy area poles: Crime
all_rows += describe_categorical(d119["topic_crime_and_law_enforcement"], "Crime & Law Enforcement")

# 5. Finance
all_rows += describe_categorical(d119["topic_finance_and_financial_sector"], "Finance & Financial Sector")

# 6. Labor
all_rows += describe_categorical(d119["topic_labor_and_employment"], "Labor & Employment")

# 7. Bill length: split at median ln_words
words_med = d119["ln_words"].median()
d119["long_bill"] = (d119["ln_words"] > words_med).astype(int)
all_rows += describe_binary(d119["long_bill"], "Bill length (ln_words)",
                            group0=f"Shorter (≤{words_med:.1f} ln words)",
                            group1=f"Longer (>{words_med:.1f} ln words)")

# ── Format and export ──

table = pd.DataFrame(all_rows)

# Round
table["% of total"] = table["% of total"].round(1)
table["% AI-positive"] = table["% AI-positive"].round(1)
table["% succeeded"] = table["% succeeded"].round(1)

# Print
print("=" * 120)
print(f"{'Variable':<35} {'Group':<30} {'N':>6} {'%tot':>5} {'N_AI':>6} {'%AI':>6} {'N_succ':>7} {'%succ':>7}")
print("=" * 120)
for _, r in table.iterrows():
    print(f"{r['Variable']:<35} {r['Group']:<30} {r['N bills']:>6} {r['% of total']:>5} {r['N AI-positive']:>6} {r['% AI-positive']:>6} {r['N succeeded']:>7} {r['% succeeded']:>7}")

# Also add a reference row for the full sample
ref = pd.DataFrame([{
    "Variable": "All bills",
    "Group": "119th Congress content bills",
    "N bills": N,
    "% of total": 100.0,
    "N AI-positive": int(d119["ai_c65"].sum()),
    "% AI-positive": d119["ai_c65"].mean() * 100,
    "N succeeded": int(d119["succeeded"].sum()),
    "% succeeded": d119["succeeded"].mean() * 100,
}])
table = pd.concat([ref, table], ignore_index=True)

# Export
xlsx_path = FIG / "predictor_forest_descriptives.xlsx"
table.to_excel(xlsx_path, index=False)
csv_path = FIG / "predictor_forest_descriptives.csv"
table.to_csv(csv_path, index=False)
print(f"\nSaved -> {xlsx_path}")
print(f"Saved -> {csv_path}")