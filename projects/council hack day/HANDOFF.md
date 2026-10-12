# HANDOFF — Council Receipts (Campaign Lab hack day, 2026-08-22)

_v7 — PRODUCTION REBUILD (2026-10-05):_
- New datasets: LGO Ombudsman (`england_ombudsman.py`), MHCLG borrowing (`england_borrowing.py`), Contracts Finder (`england_contracts.py`) → `data_england/{ombudsman,borrowing,contracts}.csv`.
- 6 formerly-missing councils (Leeds, Manchester, Camden, Bexley, Hillingdon, Somerset) now mapped via `site/common.py`; all 282 have Gateway ids.
- `pipeline.py` = one command (fetch → build → build_search → verify). `site/verify.py` = preflight integrity gate.
- Frontend: executive briefing + 4 section tabs + omnibox cross-council search + tier-aware party aggregates + borrowing/contracts/ombudsman panels.
- Coverage: 282 councils, 232 topic, 224 momentum, 250 contracts, 282 ombudsman+borrowing.

_v6 — MOMENTUM + DOCUMENT SEARCH SHIPPED (2026-09-30):_

Purpose of this file: complete working context so a cheaper-model session can continue
without re-deriving anything. Update the "Live state" section as things change.

## The product

**Council Receipts** — Streamlit dashboard making UK council minutes legible: what issues
councils discuss (keyword-taxonomy topic tracking), quantitative metrics (meetings,
cancellation %, key decisions), and per-council journalist briefings. Mixes hack-day
challenge briefs Table C "Issue Tracker" + Table D "Weekly Breakdown".
Demo at 17:10; final commit 17:00. Register team: https://team-showcase-vote.vercel.app/

## Files (this folder)

- `harvest.py` — Council Gateway API → `data/*.csv`. Incremental save after each council.
  `python harvest.py` (full: 9 councils, 4 months) / `--smoke` / `--only <ids>`.
- `taxonomy.py` — `TOPICS` dict (10 topics → keyword lists), `classify(text)` → hit counts.
- `app.py` — Streamlit, 4 views (Council overview / Issue explorer / Compare councils /
  Talk vs Spend). Reads `data/*.csv` + `briefings/<Council Name>.md` only; no API calls at
  runtime. Run: `streamlit run app.py` (currently live headless on port 8599).
  NB: `@st.cache_data` — restart the app after harvest updates CSVs, or data stays stale.
- `finance.py` — parses `data/RSX_LA_2024-25.ods` (MHCLG Revenue Outturn 2024-25, net
  current expenditure by service) → `data/finance.csv` (council, service, spend_gbp_thousands)
  + `data/finance_topics.csv` (council, topic, spend_share_pct). Service→topic mapping
  inside. Gotcha: police/fire bodies share LA names — excluded via `Detailed Class` column.
  All 9 councils matched; Mid Suffolk is a district so upper-tier services are zero.
- `briefings/<Council>.md` — journalist briefings, one per council.
- `data/` — councils, meetings, decisions, people, doc_topics CSVs.
- `PROJECT.md` — spec; `Campaign Lab Council Data - Hack Day.md` — challenge sheet.

## API cheat-sheet (councilgateway.poteris.co.uk/council-api — keyless)

- `/councils` (`majority_party` is STALE pre-May-2025 — Kent 9 + County Durham 243 are
  actually Reform; harvest.py PARTY_OVERRIDES corrects), `/councils/{id}`
- `/meetings?council_id&date_from&date_to` — name contains "CANCELLED" for cancelled
- `/documents?meeting_id` then `/documents/{id}?include_text=true` → field `text`
  (filter `extract_status=="success"`, skip `is_media`; do NOT filter `is_minutes` —
  it discards ~80% of usable docs)
- `/documents/{id}/classifications` → `items[0].output` {topline, attendees(list|str)} — sparse
- `/documents/{id}/file` → original PDF (works from anywhere)
- `/decisions?council_id&date_from` (`is_key`, `purpose`, `outcome`, `date`),
  `/people?council_id` (EMPTY for some councils, e.g. Sheffield), `/search?q&mode=document|classification`
- Be polite: serial requests, ~0.15s sleep.

## CSV schemas (data/)

- `doc_topics.csv`: doc_id, council_id, council, party, meeting_id, meeting_name,
  committee, date, kind, is_minutes, words, snippet(300ch), topline, attendees, pdf_url,
  then one int column per topic (exact names = `list(TOPICS.keys())`).
- `meetings.csv`: id, council_id, committee_id, name, url, date, topline, cancelled(bool), committee.
- `decisions.csv`: id, council_id, url, decision_maker, outcome, is_key, is_callable_in,
  purpose, content, date, topline.
- `councils.csv`: id, name, ..., majority_party, party (corrected). `people.csv`: often empty.

## Curated councils (id: name, corrected party)

217 Sheffield NOC · 238 Bristol GRN-led NOC · 201 Bradford LAB · 168 Barking&Dagenham LAB ·
9 Kent REF · 243 County Durham REF · 172 Bromley CON · 233 Bath&NES LD · 74 Mid Suffolk GRN

## Briefing format & quality bar

Sections: "What's dominating the agenda" (2-3 sentences, top topics + driving committees) /
"Notable decisions" (4-6 bullets, PARAPHRASED plain English — never paste raw PDF/purpose
text or mid-word truncations, each with date+outcome) / "Worth a closer look" (3-4 bullets,
each ending [source](pdf_url)). <400 words, UTF-8, plain hyphens. Ground everything in CSV
rows. Haiku produced raw-paste bullets — use Sonnet-tier for these.

## Live state (update me)

_v6 — MOMENTUM + DOCUMENT SEARCH SHIPPED (2026-09-30):_
- Added monthly topic share time-series (218 councils) with trend direction -> `panel-momentum` in council view.
- Added per-council document search indexes (226 councils, compact format) -> `panel-docsearch`.
- `site/build_search.py` generates `site/search_index/<ons_code>.json` (500 newest classified docs each, ~168 KB avg).
- Load the site data.json with `python site/build.py`, search indexes with `python site/build_search.py`.

_v5 — FULL STATIC SITE (see STATUS.md):_
- Parth rejected Streamlit UI ("dead looking") → full switch to a static site in `site/`:
  `build.py` bakes `site/data.json` from the CSVs; `index.html`/`app.js`/`style.css`,
  vanilla JS + Plotly CDN, mobile-first, his parthgoyal.uk/ai-economic-indicators-uk bar.
  Serve: `python -m http.server 8600 -d site` (running, ID b4cpb2urp). Rebuild after any
  CSV change: `python site/build.py` (idempotent). Streamlit 8599 kept as FALLBACK only —
  app.py is FROZEN (do not edit).
- Council view (default): header+control line (parties spelled out) → profile strip →
  age-vs-England bars → "what they talk about" (topic share vs 9-council avg) → "where the
  money goes" (£/resident + median tick; negatives footnoted = service earns>costs) →
  matched talk-vs-spend (FY24-25 minutes vs 2024-25 spend, matched topics only) →
  scorecard (5 metrics) → "read up on it" (3 news links) → methodology <details>.
  National view: 6-bucket party spend + scorecard league table.
- CUT per Parth: issue explorer, topic trends, weekly time-series, civic cards
  (meetings/cancelled/key-decisions), Band D absolute, long briefings, standalone
  Talk-vs-Spend view. Party buckets = 6 (LAB/CON/LD/REF/GRN/Independent+Other).
- NEW DATA built this round:
  - `data/scorecard.csv` (long: council,metric,value,year,source,proxy) — attainment8
    (DfE KS4 23/24), co2_per_capita (DESNZ 2024), rent_affordability (ONS PIPR 2026-07 ÷
    ASHE pay), crime_per_1000 (ONS CSP yr-end Mar24), aroad_delay (DfT CGN0504d 2024);
    England row each; spot-checked sane; ranking dirs verified (attainment higher=better,
    rest lower=better). Proxies flagged: Mid Suffolk→Suffolk (schools/roads) + Western
    Suffolk CSP (crime); Kent/Lancs rent=district mean (co2/crime are true aggregates).
  - `data/age_bands.csv` (council,band,pct; 0-15/16-29/30-44/45-64/65+; +England).
  - `data/reading_links.csv` (3/council, 26 news + 1 council fallback for TH).
  - `data_fy1..4/` = FY24-25 (Oct24–Mar25) harvest, 4 shards, NOT merged into data/ —
    build.py reads them directly for matched talk-vs-spend. Talk-vs-spend live 8/9;
    BRISTOL has zero minutes pre-Apr-2026 in the API (both backfill windows) → its panel
    is correctly omitted, noted in methodology. 8/9 is the true ceiling.
- scorecard.py wrote 10-row CSVs (incl. stale County Durham) — harmless, site uses the
  9 from councils.csv. Sheffield ONS code is E08000039 in DfE/DESNZ/HPI/MHCLG (should be
  E08000019) — matched by name everywhere.
- REMAINING: Parth's UI feedback round; then ship pass (DEMO.md rewrite for the
  pick-your-council story, STATUS/PROJECT, Drive folder, register team). Repo push parked.

_As of ~14:20 (real time — earlier "15:xx" labels below were wrong):_
- B&D CUT (Parth: missing data). **9 councils final**: 217 Sheffield NOC · 238 Bristol
  GRN-led NOC · 201 Bradford LAB · 9 Kent REF · 10 Lancashire REF · 172 Bromley CON ·
  233 Bath&NES LD · 74 Mid Suffolk GRN · 191 Tower Hamlets IND/Aspire. B&D removed from
  harvest.py/finance.py/demographics.py/elections.py + councils.csv (orphan rows in
  meetings/decisions harmless — inner joins drop them).
- YTD BACKFILL MERGED: harvest.py gained `--date-from/--date-to` + notice-skip at source
  (NOTICE_PATTERN moved to taxonomy.py, shared with app.py). 4 shards (data_bf1..4,
  Jan 1→Apr 22) merged via merge_th.py. `data/` now **12,238 docs spanning
  2026-01-05 → 2026-08-20**. Per-council: Bradford 4525, Sheffield 1594, TH 1291,
  Lancs 1211, Kent 1003, Bromley 994, Bath 893, Bristol 588, Mid Suffolk 139.
  GOTCHA: Bristol has ZERO Jan–Apr meetings in the Gateway (their gap) — series starts Apr.
- PROFILE DATA DONE: `profile.py` → `data/profile.csv`, 9 councils × (under18/over65 %,
  median weekly FT pay ASHE-2025, median house price HPI, Band D CT 2025-26, ethnicity
  White/Asian/Black/Mixed/Other %). Kent + Lancashire Band D = county precept ONLY
  (~£1691/£1736) — captioned in app. Sheffield ONS code wrong in MHCLG+HPI files
  (E08000039 vs E08000019) — matched by name.
- v2 UI SHIPPED (app.py fully rewritten, ~450 lines) and app RESTARTED on 8599 with YTD
  data. Overview: election banner → civic cards (help= tooltips carry the honest
  cancellation/key-decision interpretations) → profile strip (profile.csv + population)
  → control line from PREVIOUS_CONTROL dict → grouped bars council-vs-avg (diamonds gone)
  → top-5-topic weekly line chart → "Where the money goes" £/resident (finance.csv ÷
  demographics.csv) with Band D card. Compare: "Group by party" toggle (equal-weighted,
  n= caveats) + Decision style board (key decisions/meeting; officer-delegated % via
  OFFICER_RE/MEMBER_RE on decision_maker — Lancashire 57% officer, Kent 0%; captioned as
  style not performance). Talk vs Spend: dynamic caption when spend year belongs to
  previous administration. Colour-blind Safe palette via TOPIC_COLORS, simple_white
  template, source captions everywhere. Known cosmetic: use_container_width deprecation
  warnings (harmless).
- Briefing "Projects on residents' radar" sections: agent a9da5a2ad399cb2a8 appending to
  all 9 briefings/<Council>.md — markdown is read fresh per render, NO restart needed.
  If the agent died, spot-check which files have the section and regenerate the rest
  (3-5 named local projects/schemes with [source](pdf_url) links, paraphrased, grounded
  in decisions.csv purpose + doc_topics snippets; TH toplines hallucinate — don't trust).
- USAGE BUDGET: ~70% of Max quota burned at 14:30; reset ~16:30 (demo 17:10). Parth's
  call: main loop OPUS 4.8 (not Fable — too expensive) with standard tier-gap delegation —
  implementation/multi-file edits to coder-sonnet, mechanical work to utility-haiku,
  trivial single-file tweaks done directly. Post-reset he may switch models again.

_As of ~15:55 (stale label, really ~13:00):_
- COUNTY DURHAM CUT (Parth's call — its harvest was too slow). Replaced by **Lancashire
  (id 10, REF-run county, pop 1,292,439)** — probed best of 7 Reform-county candidates
  (44 meetings, richest docs). Harvested to data_lancs/ and merged.
- `data/` now: **10 councils, 7,080 docs, 680 meetings, 1,261 decisions**. Lancashire alone
  = 548 docs + 660 decisions (very delegated-decision-heavy). Side dirs data_th/, data_rest/,
  data_lancs/ retained but stale — data/ is canonical.
- Councils final: 217 Sheffield NOC · 238 Bristol GRN-led NOC · 201 Bradford LAB ·
  168 B&D LAB (zero docs) · 9 Kent REF · 10 Lancashire REF · 172 Bromley CON ·
  233 Bath&NES LD · 74 Mid Suffolk GRN · 191 Tower Hamlets IND/Aspire.
- v0 BENCHMARK BUILT (Parth approved): Council overview topic chart has "All-council avg"
  diamond overlay (equal-weighted per-council shares); Talk vs Spend has third bar
  "England avg spend" from RSX's own ENGLAND aggregate row (Class=="Eng") — England:
  Education 54.7% / Social Care 23.0%. finance_topics.csv has council="England average" rows.
- Briefings done: all except Lancashire (generating now, sonnet agent a6ec5f3df13986661).
- App restarted on 8599 with everything above. DEMO.md numbers updated.
- GRILL DECISIONS PARKED (Parth wants to play with the app first): deploy (repo/Streamlit
  Cloud) vs local-only; Drive folder contents; DEMO.md sign-off; TH party label confirm.

_As of ~15:10:_
- TH harvest DONE (558 docs in data_th/). finance.py now matches 10 councils (TH:
  Education 59% of spend). demographics.csv live (ONS mid-2024 via Nomis, 10 councils);
  Population metric + docs-per-1k board wired into app. TH briefing generating from
  data_th/. `merge_th.py` ready — run ONLY after main harvest exits, then restart app.
- Tower Hamlets (id 191, IND/Aspire, Parth's council) being added as 10th council: rich
  data (63 meetings/4mo). Harvesting in PARALLEL to `data_th/` via new `--outdir` flag
  (harvest.py rewrites CSVs from memory — never run two harvests into the same dir).
  When both harvests finish: merge data_th/*.csv into data/*.csv, add TH to finance.py
  matching + rerun, TH briefing, restart app. (task #7)
- demographics.py delegated to sonnet agent: ONS mid-year population → data/demographics.csv,
  Population metric card + docs-per-1k-residents in Compare view.
- elections.py now includes tower-hamlets slug (no upcoming TH elections; Sheffield's 2
  by-elections still the hook).
- Briefings done: Sheffield, Bristol, Bradford, Kent (Bradford's opening hand-fixed after
  the TRO filter changed its top topic to Finance & Budget).
- DATA CLEANING: Bradford publishes 2808 statutory notices (TROs/parking orders) as fake
  "committees" — was 48% of ALL Transport hits. app.py `NOTICE_PATTERN` now filters
  doc_topics + meetings at load (zero false positives on other councils). Reported in
  PROJECT.md data issues. App restarted with filter live.
- App now has 5 views ("Topic trends" added second: weekly cross-council topic share lines
  + movers table). Election banner on Council overview from `data/elections.csv`
  (elections.py → Democracy Club Elections API, free/keyless; Sheffield has 2 by-elections:
  Southey 27 Aug, Walkley 17 Sep). "Councillors" metric dropped (always 0). App restarted.
- Harvest: Sheffield, Bristol, Bradford (3379 docs!), Kent done; Barking & Dagenham done
  but ZERO usable docs (data issue — report it); County Durham in flight, then 172/233/74.
- Briefings: Bradford + Kent generating now (sonnet agent). Remaining after: Durham,
  Bromley, Bath&NES, Mid Suffolk (skip B&D — no docs).
- Harvest running in background: Sheffield + Bristol complete (1220 docs), Bradford in
  flight, 6 more queued. If it dies: `python harvest.py --only <remaining ids>`.
- Briefings done: Sheffield, Bristol. Remaining 7: generate when their data lands
  (single Sonnet agent, prompt per format above).
- Finance DONE: finance.csv (81 rows) + finance_topics.csv (63 rows), all 9 councils.
  "Talk vs Spend" is live as the 4th view. Restarted app on 8599 to pick it up.
- Finance sanity notes: Children & Education dominates spend everywhere (49-76%) —
  correct, schools funding. Small NEGATIVE shares exist (net income exceeds spend,
  e.g. Bath&NES Local Economy -2.6%) — fine, explain if asked. Mid Suffolk (district):
  spend is Housing 57% / Environment 30% — no social care/education duty.
- /people is EMPTY for ALL councils tried (corpus-wide) — "Councillors" metric always 0;
  drop it in polish pass.
- Early finding for demo: Sheffield agenda dominated by Licensing (4720 hits);
  Bristol by Transport (6327). Cross-council contrast works.

## Remaining to ship (in order) — hard deadline: commit 17:00, demo 17:10

1. Parth's next feedback round(s) on the v2 app — small app.py edits, done directly.
2. Verify "Projects on residents' radar" landed in all 9 briefings; spot-check one link.
3. PARKED DECISIONS Parth must call: deploy (repo/Streamlit Cloud) vs local-only demo;
   what goes in the hackday Drive "Hackday work and outputs" folder; DEMO.md rewrite
   (numbers stale: says 10 councils/7,080 docs — now 9 councils/12,238 docs YTD);
   Tower Hamlets party label (API says IND/Aspire — Parth to confirm).
4. STATUS.md session entry; PROJECT.md "Key findings" fill-in.
5. Register team: https://team-showcase-vote.vercel.app/; demo run-through.

## User's working preferences (apply them)

Minimal MVP, no defensive code. Token economy: delegate mechanical work to haiku,
implementation to sonnet; keep raw file_text out of main context. Data issues get
reported to the challenge sheet's "Data Issues" section (stale party labels + empty
/people + is_minutes trap already reported).
