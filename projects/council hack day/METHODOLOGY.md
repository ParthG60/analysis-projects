# Council Receipts — Methodology & Data

**What it is.** Pick your council, see what it talks about, where its money goes, and how it compares. Covers all **282 English local authorities** in the Council Gateway across the political spectrum: Labour, Conservative, Liberal Democrat, Reform UK, Green, and No Overall Control / Independent councils.

Each council opens with an **executive briefing** (governance, fiscal health, accountability, and the biggest talk-vs-spend gap) followed by four sections: **Overview**, **Agenda & minutes** (topics, momentum, document search), **Money & contracts** (budget, talk-vs-spend, borrowing, contract awards) and **Outcomes & watchdog** (Ombudsman, Quality of Life, financial distress). The header search box queries a council directly, or runs a **cross-council search** for an issue or contractor across every council at once.

## What they talk about

Meeting minutes come from the [Council Gateway API](https://councilgateway.poteris.co.uk) (Poteris), covering **October 2024 – March 2025** — deliberately matched to the 2024-25 financial year so discussion and spend cover the same period. Each minutes document is classified by keyword counting against a fixed taxonomy (Children & Education, Social Care, Housing & Planning, Transport & Highways, Climate & Environment, Finance & Budget, Health, Licensing & Regulation, Community Safety, Local Economy). A council's *discussion share* for a topic = that topic's keyword hits ÷ all topic hits across its minutes. Statutory notices (licensing orders, road closures, traffic regulation orders) are filtered out at source — they are procedural, not deliberation.

## Where the money goes

Spend is from the **MHCLG Revenue Outturn 2024-25** (RSX summary): gross expenditure by service (staff + running costs), converted to £ per resident using ONS mid-year population estimates. Service lines map onto the matched discussion topics, making "do they talk about what they spend on?" a consistent comparison.

**Why gross?** Gross expenditure measures the resources a council actually pours into each service. The alternative — net expenditure, i.e. gross minus fees-and-charges income — measures the burden on council tax instead, and understates activity wherever charging is heavy: Camden runs a £37m-a-year roads operation that shows up as *negative* on a net basis because parking income (£57m) more than covers it. One caveat with gross: it includes activity funded by fees and charges, not just council tax — Bath's Roman Baths spend, for instance, is more than covered by admissions.

**England benchmarks:** England spend figures are calculated as true **population-weighted England averages** across all local authorities (£ total expenditure divided by total English population for £/resident, and total service spend divided by total expenditure for budget shares).

## Council tiers & remits

England uses a mixed local government structure:
- **Unitary Authorities, London Boroughs & Metropolitan Districts:** Single-tier councils responsible for all local services (Education, Social Care, Housing, Planning, Highways, Public Health, Waste, Leisure).
- **Shire Counties & Shire Districts (Two-Tier):** In two-tier areas, functions are divided. Shire Districts (e.g. Mid Suffolk, Fareham) deliver Housing, Local Planning, Waste Collection, and Leisure. County Councils (e.g. Kent, Lancashire, Essex) deliver Education, Children's & Adult Social Care, Public Health, and Highways. District receipts clearly flag £0 lines for county-level statutory services to reflect this division of responsibility.

## Quality of Life scorecard (7 outcome metrics)

Every council displays 7 outcome-based Quality of Life indicators alongside its national rank across England (`Rank #X of 282`):

| Metric | Source | Period | Better direction |
|---|---|---|---|
| Life Expectancy at Birth (years) | ONS Health State Life Expectancies | 2025 (2021–23 pool) | Higher is better |
| GCSE Attainment 8 (points) | DfE Key Stage 4 Performance | 2023/24 | Higher is better |
| Rent Affordability (rent ÷ pay %) | ONS PIPR private rents ÷ ASHE gross full-time earnings | 2024/latest | Lower is better |
| Air Quality PM2.5 (% mortality) | Defra / OHID Public Health Outcomes Framework | Latest | Lower is better |
| Child Poverty (%) | DWP Children in Low Income Families | 2022/23 | Lower is better |
| Claimant Rate (%) | Nomis Claimant Count (% of 16–64 population) | July 2026 | Lower is better |
| Recorded Crime (per 1,000 residents) | ONS Community Safety Partnerships | 2024 | Lower is better |

The national league table allows sorting by any metric individually; there is deliberately no composite score, avoiding arbitrary weighting across unrelated outcome dimensions.

## Financial health & distress check

Tracks local authorities operating under statutory Section 114 spending freeze notices or receiving Ministry of Housing, Communities and Local Government (MHCLG) Exceptional Financial Support (EFS) capitalisation directives (2024–2026).

## Ombudsman watchdog

The **Local Government & Social Care Ombudsman (LGO)** publishes an annual review covering every English council. For each council we show:

- **Upheld rate** — the share of investigated complaints where the Ombudsman found the council at fault, alongside the LGO's own **peer average** ("similar authorities").
- **Complaints decided** — total enquiries and complaints decided during the year.
- **Cases upheld** — number of complaints upheld.
- **Recommendations met** — the share of Ombudsman recommendations the council implemented to the LGO's satisfaction.

Source: LGO annual review 2024-25. A high upheld rate relative to peers is a scrutiny signal, not proof of service failure on its own — it reflects complaints that escalated to the Ombudsman.

## Borrowing & debt

Outstanding borrowing per authority from the **MHCLG quarterly Borrowing & Investment Live Table** (latest available quarter). We sum every loan and securities category into total outstanding borrowing, then divide by ONS mid-2024 population for **debt per resident**. High or fast-rising debt is a lead indicator of financial stress (e.g. Woking, Thurrock, Spelthorne). The live table occasionally carries stale ONS codes; we reconcile to our canonical registry by authority name.

## Largest contract awards

The largest **single-supplier** contracts each council has published to the **Crown Commercial Service Contracts Finder**. Multi-supplier framework lots (which list dozens of names and a framework ceiling rather than actual spend) and zero-value awards are excluded. Values are the published award values and may reflect framework ceilings; they are a guide to commercial exposure, not confirmed spend.

## Smart party aggregates (tier-aware)

Party comparisons are restricted to **comparable tiers**, because English councils do different jobs:

- **Single-tier** (unitaries, metropolitan boroughs, London boroughs) run all services.
- **Shire districts** (lower tier) run housing, planning, waste collection and leisure — and have **no** education or social care budget.
- **Shire counties** (upper tier) run education, social care, public health and highways.

Averaging all authorities together produces spurious party differences (Simpson's paradox): a party that happens to control more single-tier cities will appear to "spend more on housing" purely because it controls the councils that provide housing. The National tab therefore defaults to single-tier and lets you switch tier; each party bar shows its sample size (`n`).

## Demographics & elections

- **Population & Age Profile:** ONS mid-2024 population estimates; 5-year male/female population pyramids from Nomis (`NM_2002_1`) across all 282 councils and England.
- **Ethnicity:** Census 2021 (ONS).
- **Control:** Current political control and council composition from Open Council Data UK (2026).
- **Elections:** Live upcoming election dates from the Democracy Club API.

## Honest limitations

- **Counties vs districts:** Two-tier district councils do not fund or provide Education or Social Care; spending sits with the parent County Council.
- **Proxy values:** Where district-level data is unavailable for certain county-administered indicators (e.g. GCSE Attainment 8), the parent county value is assigned and noted.
- **Recorded crime:** Reflects reporting and recording practices alongside underlying incidents; rates vary with local policing and reporting rates.
- **Keyword classification:** Deterministic keyword matching measures what minutes and agenda packs discuss, not debate quality or voting outcomes.
- **Discussion corpus coverage:** Councils with incomplete Gateway minutes for FY2024-25 omit discussion panels while retaining all finance, demographic, and Quality of Life data.

*Built at Campaign Lab hack day, August 2026. All sources are open data; no scraping beyond public APIs.*
