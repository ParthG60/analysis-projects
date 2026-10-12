"""Gross (C3) spend per service for ALL English local authorities in the MHCLG
RSX file -> data_england/finance_all.csv. Long format, same service set/columns
as finance.py's data/finance.csv, but every RSX authority row (SD/MD/UA/LB/SC
classes - districts, counties, unitaries, London boroughs, mets), not just the
15 hand-picked councils.

Usage: python england_finance.py
"""
from pathlib import Path

import pandas as pd

from finance import load_rsx, SERVICES

OUT_DIR = Path(__file__).parent / "data_england"

# real local authority classes in the RSX (excludes 'O' = police/fire/combined
# authority/park/waste/GLA bodies, and 'Eng' = the England aggregate row).
LA_CLASSES = ["SD", "MD", "UA", "LB", "SC"]


def extract_all():
    df = load_rsx()
    la = df[df["Class"].isin(LA_CLASSES)]
    # drop the 5 subtotal rows the RSX embeds under each class ("London Boroughs",
    # "Shire Districts", etc.) - these carry truncated 3-char ONS "codes" (E06,
    # E07, ...) instead of a real 9-char authority code.
    la = la[la["ONS Code"].str.len() == 9]

    rows = []
    for _, rec in la.iterrows():
        for service in SERVICES:
            col = f"{service} - Total Expenditure (C3 = C1 + C2)"
            spend = rec[col]
            if pd.isna(spend):
                continue
            rows.append({
                "ons_code": rec["ONS Code"],
                "authority_name": rec["Local authority"],
                "class": rec["Class"],
                "service": service,
                "spend_gbp_thousands": spend,
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    finance_all = extract_all()
    OUT_DIR.mkdir(exist_ok=True)
    finance_all.to_csv(OUT_DIR / "finance_all.csv", index=False)
    print(f"data_england/finance_all.csv: {len(finance_all)} rows, "
          f"{finance_all['ons_code'].nunique()} authorities, "
          f"{finance_all['service'].nunique()} services")
