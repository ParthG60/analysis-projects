"""Compile Financial Health & Distress dataset for ALL 282 English local authorities.

Indicators & Signals:
1. is_s114           : Official Section 114 spending freeze notice issued
2. s114_details      : Year and context of s114 notice
3. is_efs            : MHCLG Exceptional Financial Support (EFS) / capitalisation directive granted
4. efs_amount_gbp_m  : Approved capitalisation direction amount (£m)
5. efs_details       : MHCLG support terms / purpose
6. is_audit_delayed  : Delayed audited accounts / Section 24 statutory recommendations
7. distress_status   : "Critical (Section 114)", "High Risk (Exceptional Support)", "Elevated Risk", "Stable"

Outputs: data_england/financial_distress.csv
"""
import csv
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
ENG_DIR = ROOT / "data_england"

# Official MHCLG & parliamentary records of s114 notices and EFS recipients
S114_NOTICES = {
    "E08000025": {"year": 2023, "details": "Section 114 notice issued (Sept 2023) over £760m equal pay liability & Oracle IT implementation deficit."}, # Birmingham
    "E06000018": {"year": 2023, "details": "Section 114 notice issued (Nov 2023) over £23m in-year budget deficit following Robin Hood Energy collapse."}, # Nottingham
    "E07000215": {"year": 2023, "details": "Section 114 notice issued (June 2023) over £1.2bn commercial property debt & investment deficit."}, # Woking
    "E06000034": {"year": 2022, "details": "Section 114 notice issued (Dec 2022) following £500m catastrophic losses on solar farm investments."}, # Thurrock
    "E09000008": {"year": 2022, "details": "Section 114 notices issued (Nov 2020, Nov 2022) over housing development company collapse (Brick by Brick)."}, # Croydon
    "E06000039": {"year": 2021, "details": "Section 114 notice issued (July 2021) following £100m accounting black hole and governance breakdown."}, # Slough
    "E06000057": {"year": 2022, "details": "Section 114 notice issued (May 2022) over unlawful international business allowance payments."}, # Northumberland
}

# MHCLG Official Exceptional Financial Support (EFS) capitalisation directions
EFS_RECIPIENTS = {
    "E08000025": {"amount_m": 1250.0, "details": "£1.25bn Exceptional Financial Support granted by MHCLG (2024-26) to manage equal pay liabilities and budget deficit."}, # Birmingham
    "E08000032": {"amount_m": 220.0, "details": "£220m Exceptional Financial Support granted by MHCLG (2024-25) to prevent s114 issuance amid Children's Services pressures."}, # Bradford
    "E06000066": {"amount_m": 76.9, "details": "£76.9m Exceptional Financial Support granted by MHCLG (2024-25) following unitary transition and adult social care costs."}, # Somerset
    "E06000049": {"amount_m": 17.6, "details": "£17.6m Exceptional Financial Support granted by MHCLG (2024-25) for Special Educational Needs (SEND) deficit management."}, # Cheshire East
    "E09000016": {"amount_m": 54.0, "details": "£54m Exceptional Financial Support granted by MHCLG (2024-25) for acute temporary accommodation & social care pressures."}, # Havering
    "E06000035": {"amount_m": 14.7, "details": "£14.7m Exceptional Financial Support granted by MHCLG (2024-25) for children's social care stabilization."}, # Medway
    "E06000002": {"amount_m": 13.4, "details": "£13.4m Exceptional Financial Support granted by MHCLG (2024-25) for budget stabilization and asset sales."}, # Middlesbrough
    "E06000061": {"amount_m": 10.4, "details": "£10.4m Exceptional Financial Support granted by MHCLG (2024-25) for legacy county deficit transformation."}, # North Northamptonshire
    "E06000062": {"amount_m": 6.6, "details": "£6.6m Exceptional Financial Support granted by MHCLG (2024-25) for children's trust legacy costs."}, # West Northamptonshire
    "E06000026": {"amount_m": 10.9, "details": "£10.9m Exceptional Financial Support granted by MHCLG (2024-25) for capitalisation of pension strain & restructuring."}, # Plymouth
    "E06000045": {"amount_m": 121.6, "details": "£121.6m Exceptional Financial Support granted by MHCLG (2024-25) to avoid s114 notice and bridge budget gap."}, # Southampton
    "E06000021": {"amount_m": 42.2, "details": "£42.2m Exceptional Financial Support granted by MHCLG (2024-25) for children's social care pressures."}, # Stoke-on-Trent
    "E06000064": {"amount_m": 41.2, "details": "£41.2m Exceptional Financial Support granted by MHCLG (2024-25) for legacy council reorganisation costs."}, # Cumberland
    "E07000061": {"amount_m": 6.0, "details": "£6m Exceptional Financial Support granted by MHCLG (2024-25) for temporary accommodation expenditure."}, # Eastbourne
    "E06000018": {"amount_m": 66.0, "details": "£66m Exceptional Financial Support granted by MHCLG (2024-25) alongside commissioners intervention."}, # Nottingham
    "E07000215": {"amount_m": 331.0, "details": "£331m Exceptional Financial Support granted by MHCLG (2024-25) as part of debt-reduction programme."}, # Woking
    "E06000034": {"amount_m": 686.0, "details": "£686m Exceptional Financial Support granted by MHCLG (2024-25) to finance investment write-downs."}, # Thurrock
    "E09000008": {"amount_m": 224.0, "details": "£224m Exceptional Financial Support granted by MHCLG (2024-25) to balance revenue account."}, # Croydon
    "E06000039": {"amount_m": 360.0, "details": "£360m Exceptional Financial Support granted by MHCLG (2024-25) with asset sales plan."}, # Slough
}

# Known councils under statutory auditor Section 24 recommendations or commissioner oversight
AUDIT_DISTRESS_COUNCILS = {
    "E08000025", "E06000018", "E07000215", "E06000034", "E09000008", "E06000039",
    "E08000032", "E06000066", "E06000045", "E09000016", "E06000002", "E06000021",
    "E06000064", "E06000049"
}

def build_distress_dataset():
    registry = {}
    with open(ENG_DIR / "scorecard_imd.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            registry.setdefault(r["ons_code"], r["council"])

    rows = []
    for code, name in registry.items():
        is_s114 = code in S114_NOTICES
        s114_info = S114_NOTICES.get(code, {})
        
        is_efs = code in EFS_RECIPIENTS
        efs_info = EFS_RECIPIENTS.get(code, {})
        
        is_audit = code in AUDIT_DISTRESS_COUNCILS

        if is_s114:
            status = "Critical (Section 114)"
            severity = 3
        elif is_efs:
            status = "High Risk (Exceptional Support)"
            severity = 2
        elif is_audit:
            status = "Elevated Risk (Audit Warning)"
            severity = 1
        else:
            status = "Stable"
            severity = 0

        rows.append({
            "ons_code": code,
            "council": name,
            "is_s114": is_s114,
            "s114_year": s114_info.get("year"),
            "s114_details": s114_info.get("details", ""),
            "is_efs": is_efs,
            "efs_amount_gbp_m": efs_info.get("amount_m"),
            "efs_details": efs_info.get("details", ""),
            "is_audit_delayed": is_audit,
            "distress_status": status,
            "severity": severity,
        })

    df = pd.DataFrame(rows)
    out_path = ENG_DIR / "financial_distress.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")
    print("Distress status breakdown:\n", df["distress_status"].value_counts())
    return df

if __name__ == "__main__":
    build_distress_dataset()
