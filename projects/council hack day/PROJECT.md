# Council Receipts — Campaign Lab hack day prototype

## Question / Goal

What are UK councils actually discussing, and can we make that legible to journalists,
campaigners and the public in five minutes? Prototype mixing
Table C "Issue Tracker" and Table D "Weekly Breakdown" challenge briefs.

## Data

- **Council Gateway API** (keyless, hosted): https://councilgateway.poteris.co.uk/council-api
  — councils, meetings, documents (with extracted text), decisions, people, full-text search,
  sparse AI classifications (topline/attendees). Built on Democracy Club LGSF scrapes.
- 282 English local authorities across the political spectrum: Labour, Conservative,
  Liberal Democrat, Reform UK, Green, and No Overall Control / Independent councils.
- Discussion window: FY24-25 (Oct 2024–Mar 2025) matched to the 2024-25 spend year.
  Control from Open Council Data UK (2026).

## Architecture

```
harvest.py     API -> per-shard CSVs (data/, data_england/c<id>/) — councils, meetings, doc_topics
taxonomy.py    10-topic keyword taxonomy; classify(text) -> topic hit counts
finance.py     MHCLG RSX 2024-25 -> gross expenditure (C3) by service + topic shares
scorecard.py   7 Quality of Life outcome indicators (Life Exp, GCSE, Rent, PM2.5, Poverty, Claimant, Crime)
demographics   Nomis 5-year male/female age pyramids across all 282 councils + Census 2021 ethnicity
england_ombudsman.py   LGO annual review -> data_england/ombudsman.csv (upheld rate, compliance)
england_borrowing.py   MHCLG Borrowing Live Table -> data_england/borrowing.csv (debt total + per resident)
england_contracts.py   Contracts Finder API -> data_england/contracts.csv (largest contract awards)
pipeline.py    ONE command: fetchers -> build.py -> build_search.py -> verify.py
site/common.py shared council registry (ONS code <-> Gateway id), used by both builders
site/build.py  bakes everything -> site/data.json (v7 adds ombudsman, borrowing, contracts, briefing, party_by_tier)
site/build_search.py  per-council search indexes + site/search_index_global.json (cross-council)
site/verify.py preflight integrity suite (halts a bad build)
site/          vanilla HTML/JS/Plotly (executive briefing + 4 section tabs + omnibox)
app.py         FROZEN Streamlit fallback (v2)
```
Money measure is GROSS expenditure (resources poured in), not net — net understates
fee-funded services (Camden roads: £37m gross, −£23m net from parking income).
Spend benchmarks are population-weighted England averages.

Design choices: deterministic keyword topics (free, reproducible) as the metric core;
app reads JSON baked from open data CSVs — no API calls at runtime.
Run everything with `python pipeline.py`.

## Key findings

- Talk vs spend gap: Children & Education dominates net service spend everywhere (49-76%,
  MHCLG RO 2024-25) but rarely dominates discussion — councils talk Transport, Housing,
  and Licensing/Finance far more heavily than their budget shares.
- Election hook: Democracy Club Elections API (free, keyless) provides upcoming elections per
  council.
- Simpson's paradox in party aggregates: single-tier councils run all services while shire
  districts run none of social care/education — comparing them raw is meaningless, hence the
  tier toggle.

## Data source shortlist (official files > scraping)

- Single Data List (what councils MUST file): gov.uk/government/publications/single-data-list
- Local gov finance collection (RO/RA/capital/council tax/NNDR):
  data.gov.uk/collections/government/local-government-finance
- Transparency Code 2015 (local publication duties, £500 spend etc.):
  gov.uk/government/publications/local-government-transparency-code-2015
- Democracy Club Elections API (free, keyless, per-council upcoming elections)
- ONS mid-year population estimates & Nomis age distributions (all 282 councils)
- Quality of Life datasets: ONS Life Expectancy (2025), DfE GCSE Attainment 8 (2023/24),
  ONS PIPR/ASHE Rent Affordability, Defra/OHID PM2.5 Mortality, DWP Child Poverty,
  Nomis Claimant Count (July 2026), ONS CSP Recorded Crime.
- Local Government & Social Care Ombudsman annual review (complaints + upheld rates).
- MHCLG Borrowing & Investment Live Table (quarterly debt per authority).
- Crown Commercial Service Contracts Finder API (awarded contracts + suppliers).

## Roadmap (post-hack — v7)

- Topic momentum tracking ✓
- Interactive document search ✓
- Cross-council search (omnibox + global index) ✓
- Watchdog & commercial receipts (Ombudsman, borrowing, contracts) ✓
- Tier-aware party aggregates ✓
- Decision momentum tracking (committee voting patterns and policy shifts).
- Reserves runway (usable reserves as % of net budget) — needs the RA/RS reserves tables.
- Wales/Scotland finance (separate outturn sources; don't mix LA code systems).

## Data issues found (reported to organisers)

- `majority_party` in /councils is stale — pre-May-2025 control (Kent/Durham show CON/NOC,
  actually Reform-run).
- `/people` is empty for every council tried (corpus-wide).
- Barking & Dagenham: meetings exist but zero usable documents in the 4-month window.
- Bradford publishes statutory notices (TROs, parking/path orders) as fake "committees" —
  2808 of its 3379 docs; was 48% of all Transport keyword hits before filtering
  (app.py NOTICE_PATTERN excludes them).
- `topline` on /decisions is auto-generated boilerplate and sometimes FALSE: Tower Hamlets
  has "Cabinet has decided to close a local community centre..." repeated on ~13 unrelated
  decisions (fostering, procurement, school contracts). Never display decision toplines
  without checking against `purpose`.
- Most documents are `kind=unclassified`, `is_minutes=false` — filtering on is_minutes
  discards nearly all content; AI classifications cover only a small subset of the corpus.
