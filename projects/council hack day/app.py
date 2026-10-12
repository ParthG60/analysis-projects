"""Council Radar — hack-day prototype making UK council minutes transparent."""
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from taxonomy import TOPICS

DATA_DIR = Path(__file__).parent / "data"
BRIEFINGS_DIR = Path(__file__).parent / "briefings"

# Statutory notices (TROs, path orders) published as fake "committees" — Bradford does
# this at scale (2808 docs) and it swamps the Transport topic corpus-wide.
NOTICE_PATTERN = r"(?i)\border\b|notice|traffic|speed limit|parking|prohibition|public path"

# Fixed colour per topic, from a colour-blind-safe qualitative palette, so a topic
# keeps the same colour across every chart in the app. The 11th (grey) colour in the
# palette is reserved as a neutral "reference"/"average" colour, not used for a topic.
_SAFE_PALETTE = px.colors.qualitative.Safe
TOPIC_COLORS = {topic: _SAFE_PALETTE[i] for i, topic in enumerate(TOPICS)}
NEUTRAL_GREY = _SAFE_PALETTE[10]
COUNCIL_COLOR = "#3366CC"  # accent for "this council" in council-vs-average charts

px.defaults.template = "simple_white"

# Election-year control changes: {council: (current party, since, previous party)}.
# Used to render "Control: X (since Y · previously Z)" and to caption the spend-vs-
# discussion accountability gap in Talk vs Spend.
PREVIOUS_CONTROL = {
    "Kent": ("REF", "May 2025", "CON"),
    "Lancashire": ("REF", "May 2025", "CON"),
    "Sheffield": ("NOC (LAB-led)", "May 2025", "NOC"),
    "Bristol": ("GRN-led NOC", "May 2024", "GRN-led NOC"),
    "Bradford": ("LAB", "May 2022", "LAB"),
    "Bromley": ("CON", "long-standing", "CON"),
    "Bath and North East Somerset": ("LD", "May 2019", "LD"),
    "Mid Suffolk": ("GRN", "May 2023", "CON"),
    "Tower Hamlets": ("Aspire", "May 2022", "LAB"),
}

# Rough classification of decisions.csv `decision_maker` strings, for the "Decision
# style" board — officer-delegated casework vs decisions taken by a member body.
OFFICER_RE = re.compile("|".join(["director", "officer", "head of", "chief", "executive director"]), re.I)
MEMBER_RE = re.compile("|".join(["cabinet", "council", "committee", "mayor", "leader", "portfolio"]), re.I)

# For these two councils, profile.csv's band_d_council_tax is the COUNTY PRECEPT
# element only (district/police/fire precepts are separate) — not a full resident bill
# like the other 7 councils (MHCLG Table 10, 2025-26).
COUNTY_PRECEPT_ONLY = {"Kent", "Lancashire"}

st.set_page_config(page_title="Council Radar", page_icon="📡", layout="wide")


@st.cache_data
def load_data():
    councils = pd.read_csv(DATA_DIR / "councils.csv")

    meetings = pd.read_csv(DATA_DIR / "meetings.csv")
    meetings["date"] = pd.to_datetime(meetings["date"], errors="coerce")
    meetings = meetings[~meetings["committee"].str.contains(NOTICE_PATTERN, na=False)]

    decisions = pd.read_csv(DATA_DIR / "decisions.csv")
    decision_date_col = [c for c in decisions.columns if "date" in c.lower()][0]
    decisions[decision_date_col] = pd.to_datetime(decisions[decision_date_col], errors="coerce")

    try:
        people = pd.read_csv(DATA_DIR / "people.csv")
    except pd.errors.EmptyDataError:
        people = pd.DataFrame()

    doc_topics = pd.read_csv(DATA_DIR / "doc_topics.csv")
    doc_topics["date"] = pd.to_datetime(doc_topics["date"], errors="coerce")
    doc_topics = doc_topics[~doc_topics["committee"].str.contains(NOTICE_PATTERN, na=False)]

    finance_topics = pd.read_csv(DATA_DIR / "finance_topics.csv")

    try:
        finance = pd.read_csv(DATA_DIR / "finance.csv")
    except FileNotFoundError:
        finance = pd.DataFrame(columns=["council", "service", "spend_gbp_thousands"])

    try:
        elections = pd.read_csv(DATA_DIR / "elections.csv")
    except FileNotFoundError:
        elections = pd.DataFrame(columns=["council", "election_id", "title", "poll_date"])

    try:
        demographics = pd.read_csv(DATA_DIR / "demographics.csv")
    except FileNotFoundError:
        demographics = pd.DataFrame(columns=["council", "population", "source_year"])

    try:
        profile = pd.read_csv(DATA_DIR / "profile.csv")
    except FileNotFoundError:
        profile = pd.DataFrame(columns=[
            "council", "under18_pct", "over65_pct", "median_ft_pay", "median_house_price",
            "band_d_council_tax", "white_pct", "asian_pct", "black_pct", "mixed_pct", "other_pct",
        ])

    return (
        councils, meetings, decisions, decision_date_col, people, doc_topics,
        finance_topics, finance, elections, demographics, profile,
    )


(
    councils, meetings, decisions, decision_date_col, people, doc_topics,
    finance_topics, finance, elections, demographics, profile,
) = load_data()

# Derive defensively: a future backfill shouldn't schema-change, but don't assume
# every topic column is present.
TOPIC_COLS = [t for t in TOPICS if t in doc_topics.columns]


def format_population(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n / 1_000:.0f}k"


def render_control_line(name, party):
    info = PREVIOUS_CONTROL.get(name)
    if info is None:
        st.caption(f"Control: **{party}**")
        return
    current, since, previous = info
    if current == previous:
        st.caption(f"Control: **{current}** (since {since})")
    else:
        st.caption(f"Control: **{current}** (since {since} · previously {previous})")


def classify_decision_maker(maker):
    """officer / member / None (unclassifiable or ambiguous)."""
    if pd.isna(maker):
        return None
    is_officer = bool(OFFICER_RE.search(maker))
    is_member = bool(MEMBER_RE.search(maker))
    if is_officer and not is_member:
        return "officer"
    if is_member and not is_officer:
        return "member"
    return None


st.title("📡 Council Radar")
st.caption(
    "What are UK councils actually discussing? Built at Campaign Lab hack day "
    "from council minutes via the Council Gateway API."
)

view = st.sidebar.radio(
    "View",
    ["Council overview", "Topic trends", "Issue explorer", "Compare councils", "Talk vs Spend"],
)

# ---------------------------------------------------------------- View 1 ---
if view == "Council overview":
    council_name = st.sidebar.selectbox("Council", sorted(councils["name"]))
    council_row = councils[councils["name"] == council_name].iloc[0]
    council_id = council_row["id"]

    c_meetings = meetings[meetings["council_id"] == council_id]
    c_decisions = decisions[decisions["council_id"] == council_id]
    c_people = people[people["council_id"] == council_id] if "council_id" in people.columns else people.iloc[0:0]
    c_docs = doc_topics[doc_topics["council_id"] == council_id]
    c_demo = demographics[demographics["council"] == council_name]
    c_profile = profile[profile["council"] == council_name]
    p = c_profile.iloc[0] if len(c_profile) else None

    held = (~c_meetings["cancelled"]).sum()
    cancel_pct = c_meetings["cancelled"].mean() * 100 if len(c_meetings) else 0
    key_decisions = c_decisions["is_key"].sum() if "is_key" in c_decisions.columns else 0
    n_docs = len(c_docs)

    for _, e in elections[elections["council"] == council_name].sort_values("poll_date").iterrows():
        st.warning(f"🗳️ Upcoming election: **{e['title']}** — polls open {e['poll_date']}")

    # -- civic metric cards --------------------------------------------------
    cols = st.columns(4)
    cols[0].metric("Meetings held", int(held))
    cols[1].metric(
        "Cancelled", f"{cancel_pct:.0f}%",
        help="Scheduling conventions differ across councils; the within-council trend is the signal, not the level.",
    )
    cols[2].metric(
        "Key decisions", int(key_decisions),
        help="The statutory 'key decision' threshold is set by each council — this is the closest available "
             "measure of consequential output, not a directly comparable count.",
    )
    cols[3].metric("Documents analysed", n_docs)

    # -- profile strip ---------------------------------------------------------
    profile_cards = []
    if len(c_demo):
        profile_cards.append(("Population", format_population(c_demo["population"].iloc[0])))
    if p is not None:
        if "under18_pct" in p.index and pd.notna(p["under18_pct"]):
            profile_cards.append(("Under 18", f"{p['under18_pct']:.0f}%"))
        if "over65_pct" in p.index and pd.notna(p["over65_pct"]):
            profile_cards.append(("Over 65", f"{p['over65_pct']:.0f}%"))
        if "median_ft_pay" in p.index and pd.notna(p["median_ft_pay"]):
            profile_cards.append(("Median weekly pay (FT)", f"£{p['median_ft_pay']:,.0f}"))
        if "median_house_price" in p.index and pd.notna(p["median_house_price"]):
            profile_cards.append(("Median house price", f"£{p['median_house_price']:,.0f}"))
        if "band_d_council_tax" in p.index and pd.notna(p["band_d_council_tax"]):
            tax_label = "Band D council tax*" if council_name in COUNTY_PRECEPT_ONLY else "Band D council tax"
            profile_cards.append((tax_label, f"£{p['band_d_council_tax']:,.0f}"))

    if profile_cards:
        pcols = st.columns(len(profile_cards))
        for pcol, (label, value) in zip(pcols, profile_cards):
            pcol.metric(label, value)
        st.caption(
            "Source: ONS mid-2024 population estimates; profile.csv (ASHE 2025 weekly pay, housing, "
            "council tax)." + (
                " *County precept only, not a full resident bill (district/police/fire precepts separate)."
                if council_name in COUNTY_PRECEPT_ONLY else ""
            )
        )

    if p is not None:
        eth_parts = []
        for key, label in [
            ("white_pct", "White"), ("asian_pct", "Asian"), ("black_pct", "Black"),
            ("mixed_pct", "Mixed"), ("other_pct", "Other"),
        ]:
            if key in p.index and pd.notna(p[key]):
                eth_parts.append(f"{label} {p[key]:.0f}%")
        if eth_parts:
            st.caption("Ethnicity (2021 Census): " + " · ".join(eth_parts))

    render_control_line(council_name, council_row["party"])

    # -- topic share vs corpus average -----------------------------------------
    st.subheader("Topic share vs corpus average")
    topic_sums = c_docs[TOPIC_COLS].sum().sort_values(ascending=False)
    if topic_sums.sum() > 0:
        topic_share = (topic_sums / topic_sums.sum() * 100).reset_index()
        topic_share.columns = ["topic", "share_pct"]

        # corpus-wide average topic mix: each council's own % mix, weighted equally
        # (not pooled hit counts, which Kent/Bradford/Lancashire would swamp).
        council_shares = []
        for _, grp in doc_topics.groupby("council"):
            s = grp[TOPIC_COLS].sum()
            if s.sum() > 0:
                council_shares.append(s / s.sum() * 100)
        corpus_avg = (
            pd.concat(council_shares, axis=1).mean(axis=1) if council_shares
            else pd.Series(0.0, index=TOPIC_COLS)
        )

        compare_df = topic_share.copy()
        compare_df["avg_pct"] = compare_df["topic"].map(corpus_avg)
        long_compare = compare_df.melt(
            id_vars="topic", value_vars=["share_pct", "avg_pct"], var_name="series", value_name="pct"
        )
        long_compare["series"] = long_compare["series"].map(
            {"share_pct": council_name, "avg_pct": "All-council avg"}
        )
        fig_share = px.bar(
            long_compare, x="topic", y="pct", color="series", barmode="group",
            color_discrete_map={council_name: COUNCIL_COLOR, "All-council avg": NEUTRAL_GREY},
            title=f"{council_name} vs the corpus average — topic share (%)",
        )
        fig_share.update_layout(xaxis_title="", yaxis_title="Share of discussion (%)", legend_title="")
        st.plotly_chart(fig_share, use_container_width=True)
        st.caption(
            "Source: Council Gateway API meeting documents (topic keyword hits). "
            "All-council avg weights each harvested council equally, not by document volume."
        )

        # -- weekly topic share (line, not stacked area) ------------------------
        st.subheader("Topic share over time")
        c_weekly = c_docs.set_index("date")[TOPIC_COLS].groupby(pd.Grouper(freq="W")).sum()
        c_total = c_weekly.sum(axis=1)
        c_weekly_share = c_weekly.div(c_total.replace(0, pd.NA), axis=0) * 100
        top5 = topic_sums.head(5).index.tolist()
        long_time = (
            c_weekly_share[top5].reset_index()
            .melt(id_vars="date", var_name="topic", value_name="share_pct")
            .dropna(subset=["share_pct"])
        )
        if not long_time.empty:
            fig_time = px.line(
                long_time, x="date", y="share_pct", color="topic",
                color_discrete_map=TOPIC_COLORS, markers=False,
                title="Weekly topic share (top 5 topics)",
            )
            fig_time.update_layout(
                hovermode="x unified", yaxis_title="Share of discussion (%)", xaxis_title=""
            )
            st.plotly_chart(fig_time, use_container_width=True)
            st.caption("Source: Council Gateway API meeting documents (topic keyword hits), weekly.")
    else:
        st.info("No documents analysed for this council yet.")

    # -- where the money goes ---------------------------------------------------
    st.subheader("Where the money goes")
    c_finance = finance[finance["council"] == council_name]
    if c_finance.empty or c_demo.empty:
        st.info("No finance/population match for this council yet.")
    else:
        pop = c_demo["population"].iloc[0]
        money = c_finance.copy()
        money["gbp_per_resident"] = money["spend_gbp_thousands"] * 1000 / pop
        money = money.sort_values("gbp_per_resident", ascending=False)

        money_col, tax_col = st.columns([3, 1])
        with money_col:
            fig_money = px.bar(money, x="gbp_per_resident", y="service", orientation="h")
            fig_money.update_yaxes(autorange="reversed")
            fig_money.update_layout(yaxis_title="", xaxis_title="£ per resident")
            st.plotly_chart(fig_money, use_container_width=True)
            st.caption(
                "Source: MHCLG Revenue Outturn 2024-25 (RSX) net current expenditure by service, "
                "divided by ONS mid-2024 population."
            )
        with tax_col:
            if p is not None and "band_d_council_tax" in p.index and pd.notna(p.get("band_d_council_tax")):
                tax_label = "Band D council tax*" if council_name in COUNTY_PRECEPT_ONLY else "Band D council tax"
                st.metric(tax_label, f"£{p['band_d_council_tax']:,.0f}")
                note = (
                    " *County precept only, not a full resident bill."
                    if council_name in COUNTY_PRECEPT_ONLY else ""
                )
                st.caption(
                    "Council tax is only ~a quarter of council income — most spend is grant- and "
                    "business-rate funded." + note
                )

    st.subheader("Briefing")
    briefing_path = BRIEFINGS_DIR / f"{council_name}.md"
    if briefing_path.exists():
        st.markdown(briefing_path.read_text(encoding="utf-8"))
    else:
        st.info("Briefing not generated yet")

# ---------------------------------------------------------------- View 2 ---
elif view == "Topic trends":
    council_choices = st.multiselect(
        "Councils", sorted(councils["name"]), default=sorted(councils["name"])
    )
    trend_docs = doc_topics[doc_topics["council"].isin(council_choices)]

    weekly = trend_docs.set_index("date")[TOPIC_COLS].groupby(pd.Grouper(freq="W")).sum()
    weekly["total"] = weekly.sum(axis=1)
    weekly = weekly[weekly["total"] >= 50]  # drop recess-noise weeks
    weekly_share = (weekly[TOPIC_COLS].div(weekly["total"], axis=0) * 100).reset_index()
    weekly_share = weekly_share.sort_values("date").reset_index(drop=True)

    overall_top6 = trend_docs[TOPIC_COLS].sum().sort_values(ascending=False).head(6).index.tolist()
    topic_choices = st.multiselect("Topics", TOPIC_COLS, default=overall_top6)

    if weekly_share.empty or not topic_choices:
        st.info("Not enough data yet to show topic trends.")
    else:
        long = weekly_share.melt(
            id_vars="date", value_vars=topic_choices, var_name="topic", value_name="share_pct"
        )
        fig_trend = px.line(long, x="date", y="share_pct", color="topic", color_discrete_map=TOPIC_COLORS, markers=False)
        fig_trend.update_layout(
            hovermode="x unified", yaxis_title="share of discussion (%)", xaxis_title=""
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        st.subheader("Movers")
        recent = weekly_share.tail(4)[TOPIC_COLS].mean()
        earlier = weekly_share.iloc[-8:-4][TOPIC_COLS].mean()
        movers = pd.DataFrame(
            {"Topic": TOPIC_COLS, "Recent %": recent.values, "Earlier %": earlier.values}
        )
        movers["Change (pp)"] = movers["Recent %"] - movers["Earlier %"]
        movers = movers.reindex(movers["Change (pp)"].abs().sort_values(ascending=False).index)
        st.dataframe(movers, hide_index=True, use_container_width=True)

    st.caption("Source: Council Gateway API meeting documents. Share of keyword hits across all harvested councils, weekly.")

# ---------------------------------------------------------------- View 3 ---
elif view == "Issue explorer":
    topic = st.selectbox("Topic", TOPIC_COLS)
    council_choices = st.multiselect(
        "Councils", sorted(councils["name"]), default=sorted(councils["name"])
    )

    filtered = doc_topics[doc_topics["council"].isin(council_choices) & (doc_topics[topic] > 0)]
    filtered = filtered.sort_values(topic, ascending=False)
    filtered["display_topline"] = filtered["topline"].where(
        filtered["topline"].notna() & (filtered["topline"].astype(str).str.strip() != ""),
        filtered["snippet"],
    )

    st.write(f"{len(filtered)} matching documents")
    table = filtered[["council", "committee", "date", topic, "display_topline", "pdf_url"]].rename(
        columns={topic: "topic_hits", "display_topline": "topline"}
    )
    st.dataframe(
        table,
        column_config={"pdf_url": st.column_config.LinkColumn("PDF")},
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Source: Council Gateway API meeting documents.")

# ---------------------------------------------------------------- View 4 ---
elif view == "Compare councils":
    st.subheader("Topic mix by council")
    party_lookup = councils.set_index("name")["party"]

    group_by_party = st.toggle("Group by party")

    if group_by_party:
        council_topic_pct = doc_topics.groupby("council")[TOPIC_COLS].sum()
        council_topic_pct = council_topic_pct.div(council_topic_pct.sum(axis=1), axis=0) * 100
        council_topic_pct = council_topic_pct.reset_index()
        council_topic_pct["party"] = council_topic_pct["council"].map(party_lookup)
        council_topic_pct = council_topic_pct.dropna(subset=["party"])

        party_n = council_topic_pct.groupby("party")["council"].nunique()
        party_avg = council_topic_pct.groupby("party")[TOPIC_COLS].mean().reset_index()
        party_avg["label"] = party_avg["party"].map(lambda pt: f"{pt} (n={party_n.get(pt, 0)})")

        long = party_avg.melt(
            id_vars=["party", "label"], value_vars=TOPIC_COLS, var_name="topic", value_name="pct"
        )
        fig_mix = px.bar(
            long, x="pct", y="label", color="topic", orientation="h", color_discrete_map=TOPIC_COLORS
        )
        fig_mix.update_layout(barmode="stack", yaxis_title="", xaxis_title="Share of topic hits (%)")
        st.plotly_chart(fig_mix, use_container_width=True)
        st.caption(
            "Source: Council Gateway API meeting documents. Grouped by current controlling party, each "
            "council weighted equally. Small-n caveat: several parties here are represented by a single "
            "council, so this reflects that council, not the party generally."
        )

        st.subheader("Spend share by party")
        ft = finance_topics[finance_topics["council"] != "England average"].copy()
        ft["party"] = ft["council"].map(party_lookup)
        ft = ft.dropna(subset=["party"])
        party_spend = ft.groupby(["party", "topic"], as_index=False)["spend_share_pct"].mean()
        pivot = party_spend.pivot(index="party", columns="topic", values="spend_share_pct").round(1)
        st.dataframe(pivot, use_container_width=True)
        st.caption(
            "Source: MHCLG RSX 2024-25. Average net-current-expenditure share by topic across councils "
            "under each party, equally weighted — same small-n caveat as above."
        )
    else:
        grouped = doc_topics.groupby("council")[TOPIC_COLS].sum()
        grouped_pct = grouped.div(grouped.sum(axis=1), axis=0) * 100
        grouped_pct = grouped_pct.reset_index()
        grouped_pct["label"] = grouped_pct["council"].map(
            lambda c: f"{c} ({party_lookup.get(c, '')})"
        )
        long = grouped_pct.melt(
            id_vars=["council", "label"], value_vars=TOPIC_COLS, var_name="topic", value_name="pct"
        )
        fig_mix = px.bar(
            long, x="pct", y="label", color="topic", orientation="h", color_discrete_map=TOPIC_COLORS
        )
        fig_mix.update_layout(barmode="stack", yaxis_title="", xaxis_title="Share of topic hits (%)")
        st.plotly_chart(fig_mix, use_container_width=True)
        st.caption("Source: Council Gateway API meeting documents (topic keyword hits).")

    left, mid, right = st.columns(3)

    with left:
        st.subheader("Cancellation rate")
        cancel_board = (
            meetings.groupby("council_id")["cancelled"].mean().mul(100).sort_values(ascending=False)
        ).reset_index()
        cancel_board.columns = ["council_id", "cancel_pct"]
        cancel_board = cancel_board.merge(councils[["id", "name"]], left_on="council_id", right_on="id")
        cancel_board["cancel_pct"] = cancel_board["cancel_pct"].round(1)
        st.dataframe(
            cancel_board[["name", "cancel_pct"]].rename(columns={"name": "Council", "cancel_pct": "Cancelled %"}),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Scheduling conventions differ across councils — compare trends within a council, not levels across councils.")

    with mid:
        st.subheader("Key decisions")
        key_board = (
            decisions[decisions["is_key"]].groupby("council_id").size().sort_values(ascending=False)
        ).reset_index(name="key_decisions")
        all_board = decisions.groupby("council_id").size().reset_index(name="all_decisions")
        key_board = all_board.merge(key_board, on="council_id", how="left").fillna({"key_decisions": 0})
        key_board = key_board.merge(councils[["id", "name"]], left_on="council_id", right_on="id")
        key_board = key_board.sort_values("key_decisions", ascending=False)
        st.dataframe(
            key_board[["name", "key_decisions", "all_decisions"]].rename(
                columns={"name": "Council", "key_decisions": "Key decisions", "all_decisions": "All decisions logged"}
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "'Key decision' is a self-set statutory threshold, not comparable like-for-like. "
            "Raw 'all decisions logged' reflects publishing completeness, not government speed — "
            "e.g. Lancashire's high count is delegated officer casework being published, not faster government."
        )

    with right:
        st.subheader("Docs per 1k residents")
        if demographics.empty:
            st.info("No population data yet.")
        else:
            docs_board = doc_topics.groupby("council").size().reset_index(name="n_docs")
            docs_board = docs_board.merge(demographics[["council", "population"]], on="council")
            docs_board["docs_per_1k"] = (docs_board["n_docs"] / docs_board["population"] * 1000).round(2)
            docs_board = docs_board.sort_values("docs_per_1k", ascending=False)
            st.dataframe(
                docs_board[["council", "docs_per_1k"]].rename(
                    columns={"council": "Council", "docs_per_1k": "Docs / 1k residents"}
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Source: Council Gateway API + ONS mid-2024 population estimates.")

    st.subheader("Decision style")
    style_rows = []
    for _, crow in councils.iterrows():
        cid, cname = crow["id"], crow["name"]
        c_dec = decisions[decisions["council_id"] == cid]
        c_meet = meetings[meetings["council_id"] == cid]
        held = (~c_meet["cancelled"]).sum()
        key_n = c_dec["is_key"].sum() if "is_key" in c_dec.columns else 0
        key_per_meeting = key_n / held if held else None

        classified = (
            c_dec["decision_maker"].apply(classify_decision_maker)
            if "decision_maker" in c_dec.columns else pd.Series(dtype=object)
        )
        classified = classified.dropna()
        officer_pct = (classified == "officer").mean() * 100 if len(classified) else None

        style_rows.append({
            "Council": cname,
            "Key decisions / meeting": round(key_per_meeting, 2) if key_per_meeting is not None else None,
            "Officer-delegated %": round(officer_pct, 0) if officer_pct is not None else None,
        })
    style_board = pd.DataFrame(style_rows).sort_values(
        "Officer-delegated %", ascending=False, na_position="last"
    )
    st.dataframe(style_board, use_container_width=True, hide_index=True)
    st.caption(
        "High officer share = routine casework delegated and published (e.g. Lancashire); low = decisions "
        "flow through committee. A style difference, not a performance ranking."
    )

# ---------------------------------------------------------------- View 5 ---
elif view == "Talk vs Spend":
    council_name = st.sidebar.selectbox("Council", sorted(councils["name"]))
    council_row = councils[councils["name"] == council_name].iloc[0]
    council_id = council_row["id"]

    council_finance = finance_topics[finance_topics["council"] == council_name]
    if council_finance.empty:
        st.info(f"No finance data matched for {council_name} yet.")
    else:
        finance_topic_list = council_finance["topic"].tolist()
        c_docs = doc_topics[doc_topics["council_id"] == council_id]
        topic_sums = c_docs[finance_topic_list].sum()
        if topic_sums.sum() > 0:
            discussion_share = (topic_sums / topic_sums.sum() * 100).reset_index()
            discussion_share.columns = ["topic", "discussion_pct"]
        else:
            discussion_share = pd.DataFrame({"topic": finance_topic_list, "discussion_pct": 0})

        spend_share = council_finance[["topic", "spend_share_pct"]].rename(
            columns={"spend_share_pct": "spend_pct"}
        )
        merged = discussion_share.merge(spend_share, on="topic")

        england = finance_topics[finance_topics["council"] == "England average"][["topic", "spend_share_pct"]]
        england = england.rename(columns={"spend_share_pct": "england_pct"})
        merged = merged.merge(england, on="topic", how="left")

        value_vars = ["discussion_pct", "spend_pct"] + (["england_pct"] if not england.empty else [])
        long = merged.melt(id_vars="topic", value_vars=value_vars, var_name="measure", value_name="pct")
        long["measure"] = long["measure"].map(
            {"discussion_pct": "Discussion share", "spend_pct": "Spend share", "england_pct": "England avg spend"}
        )

        fig_talk_spend = px.bar(
            long, x="topic", y="pct", color="measure", barmode="group",
            color_discrete_map={
                "Discussion share": COUNCIL_COLOR, "Spend share": "#DDCC77", "England avg spend": NEUTRAL_GREY,
            },
            title=f"{council_name} — talk vs spend (%)",
        )
        st.plotly_chart(fig_talk_spend, use_container_width=True)

        prev_info = PREVIOUS_CONTROL.get(council_name)
        if prev_info:
            current, since, previous = prev_info
            if current != previous:
                accountability_note = (
                    f" Accountability note: the 2024-25 spend was committed under the then-{previous} "
                    f"administration; the discussion window falls under the current {current} administration "
                    f"(since {since}) — treat this as a handover snapshot, not one party's record."
                )
            else:
                accountability_note = f" {current} has controlled this council through both the spend year and the discussion window."
        else:
            accountability_note = ""

        st.caption(
            "Spend = MHCLG RSX 2024-25 net current expenditure by service. "
            "Discussion = Council Gateway API meeting documents, restricted to topics with a finance match."
            + accountability_note
        )
