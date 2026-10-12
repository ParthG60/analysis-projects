"""Extract gross total expenditure (C3: staff + running costs) by service from the MHCLG
Revenue Outturn (RO) 2024-25 Service Expenditure Summary (RSX), and map services
onto our topic taxonomy.

Usage: python finance.py
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
RSX_FILE = DATA_DIR / "RSX_LA_2024-25.ods"
SHEET = "RSX_LA_Data_202425"

# canonical name (matches councils.csv `name`) -> flexible search term against the
# RSX "Local authority" column
COUNCIL_MATCH = {
    "Sheffield": "Sheffield",
    "Bristol": "Bristol",
    "Bradford": "Bradford",
    "Kent": "Kent",
    "County Durham": "Durham",
    "Bromley": "Bromley",
    "Bath and North East Somerset": "Bath",
    "Mid Suffolk": "Mid Suffolk",
    "Tower Hamlets": "Tower Hamlets",
    "Lancashire": "^Lancashire",  # anchor: avoid matching West Lancashire district
    "Leeds": "Leeds",
    "Manchester": "^Manchester",  # anchor: avoid Greater Manchester bodies
    "Camden": "Camden",
    "Bexley": "Bexley",
    "Hillingdon": "Hillingdon",
    "Somerset": "^Somerset",  # anchor: avoid North Somerset / Bath and NE Somerset
}

# RSX service label -> our topic taxonomy. None = drop (not a frontline-service topic).
SERVICE_TO_TOPIC = {
    "Education services": "Children & Education",
    "Highways and transport services": "Transport & Highways",
    "Children Social Care": "Children & Education",
    "Adult Social Care": "Social Care",
    "Public Health": "Health",
    "Housing services (GFRA only)": "Housing & Planning",
    "Cultural and related services": "Local Economy",
    "Environmental and regulatory services": "Climate & Environment",
    "Planning and development services": "Housing & Planning",
    "Police services": None,
    "Fire and rescue services": None,
    "Central services": None,
    "Other services": None,
    "Total Service Expenditure": None,
}
SERVICES = [s for s, topic in SERVICE_TO_TOPIC.items() if topic is not None]


def find_header_row(raw):
    """The header row is buried a few rows down under notes — find it by locating
    the 'E-code' column label rather than hardcoding a row number."""
    for i in range(len(raw)):
        if str(raw.iloc[i, 0]).strip() == "E-code":
            return i
    raise ValueError("could not find RSX header row")


def load_rsx():
    raw = pd.read_excel(RSX_FILE, engine="odf", sheet_name=SHEET, header=None)
    header_row = find_header_row(raw)
    df = raw.iloc[header_row + 1:].copy()
    df.columns = raw.iloc[header_row]
    # Row 431 is hidden and holds column reference codes, not LA data — it has no
    # "Local authority" / "Class" value, so this filter drops it along with any
    # other blank rows.
    df = df[df["Local authority"].notna() & df["Class"].notna()]
    return df.reset_index(drop=True)


def match_council(df, term):
    hits = df[df["Local authority"].str.contains(term, case=False, na=False)]
    # exclude police/fire bodies, which share LA names in their titles (e.g. "Kent")
    return hits[~hits["Detailed Class"].isin(["Police", "Fire"])]


def extract():
    df = load_rsx()
    rows, unmatched = [], []
    for council, term in COUNCIL_MATCH.items():
        hits = match_council(df, term)
        if len(hits) != 1:
            unmatched.append((council, term, len(hits)))
            continue
        rec = hits.iloc[0]
        for service in SERVICES:
            col = f"{service} - Total Expenditure (C3 = C1 + C2)"
            spend = rec[col]
            if pd.isna(spend):
                continue
            rows.append({"council": council, "service": service, "spend_gbp_thousands": spend})
    if unmatched:
        print("Unmatched councils:", unmatched)
    return pd.DataFrame(rows)


def build_finance_topics(finance):
    ft = finance.copy()
    ft["topic"] = ft["service"].map(SERVICE_TO_TOPIC)
    ft = ft.dropna(subset=["topic"])
    grouped = ft.groupby(["council", "topic"], as_index=False)["spend_gbp_thousands"].sum()
    grouped["spend_share_pct"] = grouped.groupby("council")["spend_gbp_thousands"].transform(
        lambda s: s / s.sum() * 100
    )
    return grouped[["council", "topic", "spend_share_pct"]]


def england_average_topic_shares(df):
    """England-wide spend share per topic, read straight off the RSX's own
    'ENGLAND' aggregate row (Class == 'Eng') rather than summing all ~420
    individual LA/GLA/combined-authority rows — summing everything would
    double- and triple-count spend across tiers (county + district, GLA +
    London boroughs, combined authority + constituent councils)."""
    row = df[df["Local authority"] == "ENGLAND"].iloc[0]
    rows = []
    for service in SERVICES:
        col = f"{service} - Total Expenditure (C3 = C1 + C2)"
        rows.append({"council": "England average", "service": service, "spend_gbp_thousands": row[col]})
    england = pd.DataFrame(rows)
    return build_finance_topics(england)


if __name__ == "__main__":
    df = load_rsx()
    finance = extract()
    finance.to_csv(DATA_DIR / "finance.csv", index=False)
    print(f"finance.csv: {len(finance)} rows, {finance['council'].nunique()} councils")
    print(finance.to_string())

    finance_topics = build_finance_topics(finance)
    england_topics = england_average_topic_shares(df)
    finance_topics = pd.concat([finance_topics, england_topics], ignore_index=True)
    finance_topics.to_csv(DATA_DIR / "finance_topics.csv", index=False)
    print(f"\nfinance_topics.csv: {len(finance_topics)} rows")
    print(finance_topics.to_string())
    print("\nEngland average spend share by topic:")
    print(england_topics[["topic", "spend_share_pct"]].sort_values("spend_share_pct", ascending=False).to_string(index=False))
