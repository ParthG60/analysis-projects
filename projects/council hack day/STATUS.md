# STATUS

## 2026-10-12 — Pipeline prep stage + hide talk for Gateway-absent councils

**Pipeline.** Folded the manual `*_all` builders into `pipeline.py` as an ordered **registry prep**
stage (`PREP_STEPS`): name_map → scorecard_imd (master registry) → population → profile →
england_scorecard → control → qol_all → ethnicity → age_bands → financial_distress. Then the light
fetchers (ombudsman, borrowing, elections, qol_history, contracts) → build → search → verify. New
flags: `--skip-prep`, `--prep-only`, plus existing `--skip-fetch` / `--skip-contracts`. A registry
change now flows through automatically. Tested `--skip-fetch` end-to-end (verify PASSED).

**Talk panels.** Data-only councils (K&C + the 5 London boroughs) already had no `topic_share`, so the
discussion and talk-vs-spend panels were hidden — but silently. Added a short `#gateway-note` under the
header explaining why, shown only when a council has no minutes. Smoke-verified: Greenwich/K&C show the
note and hide both talk panels; Barnet shows talk, hides the note.

**Workflow.** `refresh.yml` now commits `qol_history.json` (was missing — the scheduled job would have
dropped it) and installs `requests` (the fetchers need it). Cache-bust `20261012f`, pushed `85cc514`.

### Blocker: the scheduled refresh cannot run as-is
`refresh.yml` checks out `ParthG60/analysis-projects` for the fetchers, but that repo **tracks 0 files
under `projects/council hack day/`** (the whole project is untracked locally). So in CI there is no
`pipeline.py`, no `data_england/*.csv`, no raw shards — `python pipeline.py` would fail immediately.
Either (a) commit the project to the private data repo with a `.gitignore` excluding the heavy caches
(`data_england/c*/`, `data_fy*/`, `contracts_cache/`, `*.xlsx`), or (b) change the workflow to check
out the site repo for code and fetch raw data at runtime. Needs a decision — flagged to Parth.

## 2026-10-12 — Added the 5 Gateway-absent London boroughs (283 → 288 councils)

**Why they were missing:** they are not in the Council Gateway API at all (320 councils total;
Greenwich, Newham, Redbridge, Richmond upon Thames and Waltham Forest are absent, as are K&C and the
City of London). The Gateway only harvests councils on a supported committee platform, so these have
no minutes corpus. The registry is built from `name_map.csv` (the Gateway 267) + original 15 + K&C, so
they simply never entered it.

**Fix:** added them to `SUPPLEMENTAL` in `scorecard_imd.py` (same data-only path as K&C), then
regenerated the whole derived chain. Critically, extended `england_profile.load_councils()` to append
data-only councils from the master registry, so `england_scorecard.py` **computes** their rent / crime /
attainment instead of silently falling back to the England aggregate — this also fixed K&C, whose
rent (was 43.5 = England avg) and attainment (46.1 = England avg) were fake. Real values now, e.g.
K&C rent 81.9, attainment 54.5.

Regenerated: `scorecard_imd`, `population_all`, `profile_all`, `scorecard_all`, `qol_all`,
`qol_history`, `ethnicity_all`, `age_bands_all`, `control_all`, `financial_distress`, `ombudsman`,
`elections`, `contracts` (+ `council_portals.csv` rows for the 5). Rebuilt data.json (288), dossiers,
search indexes; verify PASSED (methodology medians shifted slightly with the larger pool — updated the
static spans). London scope now reads **32**; the UI council count is dynamic (`.council-count` spans).

Cache-bust `20261012e`. Pushed (`f58ee27`), Pages OK. Headless smoke-tested the 5 + K&C across all
three scopes.

**Note:** the `*_all` prep builders (population/profile/scorecard/qol/ethnicity/age/control/distress)
are **not** in `pipeline.py` — they are manual. Any future registry change needs them re-run before the
scheduled refresh picks it up. Worth folding into the pipeline next.

## 2026-10-12 — Comparison scopes, QoL trends, unified finances

Big feature push, shipped in one go:

- **Global comparison switcher** — `Compare against: England / <ONS region> / <authority type>`. One
  control under the council name re-benchmarks **everything**: QoL cards, finances, standout flags and
  the citizen briefing. Medians and ranks are computed client-side from the full 283-council set.
  Added ONS region per council (`data_england/lad_to_region.csv`, LAD23 + counties) → `region` in
  `data.json`.
- **QoL trend charts, shown by default** (not expandable) above the cards: life expectancy, child
  poverty, air quality from the OHID Fingertips annual series. Council line (blue) vs group-median line
  (grey dashed), with an **Actual values / National rank** toggle. New `data_england/qol_history.py`
  → `site/qol_history.json` (110 KB) + `data_england/qol_trends.csv`.
- **Trend flags** — material QoL improvement/worsening (change in the best/worst ~10% of councils)
  now appear as 📈/📉 standout pills, in dossiers and in the briefing.
- **Merged finances** — `#panel-borrowing` + `#panel-distress` → one `#panel-finances`: statutory
  standing banner, debt stat cards (scope-ranked), and a one-line synthesis joining the two signals.
- **Contracts** — panel + caption now state that arms-length bodies (housing ALMOs, trading companies)
  are excluded, so small council-buyer totals don't read as "barely spends".

Verify extended (region coverage, `qol_history.json` coverage + benchmarks). Smoke-tested all render
paths headlessly for 6 councils × 3 scopes. Cache-bust `20261012d`. Pushed (`826a768`), Pages OK.

**Follow-ups:** (1) ~~the 283-council registry is missing 5 London boroughs~~ — resolved (see entry
above; now 288). (2) Trends cover 3 of 8 indicators (only ones with a ready annual series);
attainment/crime/rent/house history would need DfE/ONS/ASHE year pulls. (3) `england_contracts.py`
still overwrites `contracts.csv` when run with council-name args.

## 2026-10-12 — Contract money formatting

Small awards rendered as "£0.0m" (e.g. Barnet's £33k/£42k). Added `fmtAward()` in `app.js` and a
matching formatter in `build_dossiers.py`: `≥£1m → £14.56m`, `≥£1k → £567k`, else `£N`. Exact figure
now in the cell's `title` tooltip. Footer total uses the same formatter.

Also confirmed Barnet's list is complete: only **10** Contracts Finder notices (2025+) name the council
as buyer ("London Borough of Barnet" + "…Barnet Council" both normalise to `barnet`). The large volumes
sit under **Barnet Homes Ltd** (35 notices) and **The Barnet Group** — separate legal entities, correctly
excluded. So £14.56m (substance-misuse service) really is Barnet's biggest published award.

Cache-bust `20261012c`. Pushed (`e23c521`), Pages deploy succeeded.

## 2026-10-12 — Contracts simplified: one award per row

Following the duplicate-notice fix, the remaining mismatch was structural: a supplier row showed the
*sum* of their awards but linked to a single notice. Decided to keep it simple — **one row = one award
notice**, so the displayed value always matches the page the link opens.

- `england_contracts.py` `aggregate()` now returns the top individual awards (still content-deduped),
  not a per-supplier sum. `contracts.csv` = 1,102 rows across 242 councils; every row `n_contracts=1`.
- `app.js` contract table drops the "Awards" column (now Supplier · Awarded value · Awarded); lede/note
  and `index.html` caption reworded to "single contract awards". Dossiers + browser briefing list one
  line per award with its title and notice URL.
- `verify.py` unchanged (still asserts 2025+ dates and well-formed `/Notice/{uuid}`). PASSED.
- Cache-bust `20261012b`. Pushed (`c6bbe8a`), Pages deploy succeeded. Barnet now reads
  Change Grow Live £14.57m → its notice, matching.

## 2026-10-12 — Contract duplicate double-count fix

User spotted Barnet showing "2 awards / £29.1m" while the linked notice showed a single £14.57m award.
Cause: Contracts Finder carries the same award twice under **two notice ids** (a re-publication/correction:
identical supplier, title, value and award date, days apart — e.g. BIP931108394 and BIP924960649, both
"Barnet Integrated Substance Misuse…", both £14,565,000, published 2026-02-25 and 2026-03-04). Our dedupe
keyed only on notice `id`, so both were summed.

Fix: `aggregate()` now also dedupes on content key `(supplier, title, value, award_date)`. Impact: 8
duplicate groups across 7 councils (Barnet, Cumberland, Hammersmith & Fulham, North Somerset, West
Lancashire, Bristol). Barnet CGL → £14.57m / 1 award; H&F's Phoenix fell out of the top 5 once halved.
Row count unchanged (the supplier still appears, just with the correct total).

Also: `elections.py` re-run (Oct-8 polls had passed; verify's new "no closed poll" guard caught it).
Rebuilt + dossiers + verify PASSED. Cache-bust `20261012a`. Pushed (`05ed270`), Pages deploy succeeded.

## 2026-10-08 — Rent benchmark fix (methodology drift + rank contradiction)

The methodology page said "Rent Affordability … England average: 30.2%" while the data said **43.5**.
Checked every hardcoded England figure: **five of seven were stale** (rent 30.2→43.5, air quality
5.8→5.29, child poverty 20.1→19.8, claimant 4.2→4.0, crime 89.2→85.3). Two layers to the rent problem:

1. **Drift.** The page's numbers were hand-typed and never updated. Fixed by making all seven
   methodology figures `<span id="method-eng-…">` populated from the data on load (`updateMethodologyEngland()`),
   with a `verify.py` guard that fails the build if a span ever diverges from `data.json`.
   (The 30.2 was an ONS *household-income* figure; under our single-earner definition England is 43.5%.)

2. **Wrong benchmark (the real bug).** Even with the correct 43.5, the national rent aggregate is
   urban-skewed: only **15.9% of the 283 councils** sit above it, while the median council is **32.7%**.
   So a council could show "−8.5 vs England (better)" yet rank #240. Introduced **`qol_benchmark`** =
   per-indicator **median of the 283 councils** (the same peer group ranks are computed over) and switched
   the QoL cards (diff badge now "vs median", footer "Median council:"), both briefings, dossiers, and the
   methodology page to it. `qol_england` (official aggregates, incl. rent 43.5) is retained in `data.json`
   as provenance but no longer used as the comparison line.

Effect: Manchester rent 44.0 now reads "vs median +11.3" and rank #244 — direction and rank agree.
AI prompts reworded to "peer benchmarks (median English council, not the national aggregate)".
Cache-bust `20261007j`; `verify.py` PASSED.

## 2026-10-08 — Contracts recency + election flags + talk-vs-spend methodology

**Contracts.** Two silent normaliser bugs were dropping ~40 councils: `html.unescape` ran *after*
`.replace("&","and")` (so "Hammersmith &amp; Fulham" → "andamp;"), and the prefix list lacked
"borough council of" (Calderdale). Fixed; H&F and Calderdale now match. Panel recency narrowed to
**awards dated 2025-01-01 onward** (`MIN_AWARD_DATE`), `PUBLISHED_FROM` moved to 2025, `MIN_CONTRACTS`
3 → 1. Regenerated `contracts.csv`: 1,094 rows across **242 councils** (was 249 rows covering 2023–26).
Manchester now shows Mitie £29.6m, FTF2 £5.3m, Anglian Water £5.0m etc. — all 2025 awards with working
`/Notice/{id}` links. Labels updated to "2025–2026" in app/index/dossiers.

**Elections.** The old `elections.py` hardcoded 16 council slugs, was never in `pipeline.py`, and
`build.py` advertised the earliest poll with no date filter — so the live site showed a Sheffield
by-election from 2026-08-27 as "Upcoming". Rewritten to fetch all current/upcoming Democracy Club
elections, map org slugs onto all 283 councils, dedupe same-date org-placeholder vs real contest
(prefer by-election), and keep only future polls. `build.py` now also filters `poll_date >= today`
defensively. Result: 19 councils with genuine upcoming by-elections (e.g. Leeds 22 Oct, Dudley 29 Oct,
Oldham 12 Nov). Added to `pipeline.py`.

**Talk-vs-spend methodology.** Audit found the standalone gap flag was firing "Children & Education"
for nearly every unitary (DSG pass-through inflates education spend ~30–40pp) and the on-page caption
was stale (claimed Oct 2024–Mar 2025). The flag now uses only **discretionary** services (Housing &
Planning, Transport & Highways, Climate & Environment, Local Economy, Health) and only when the gap is
in the national **top 20%** (`discretionaryGapP80()`), so it means something. Added institutional
context to the chart caption and both briefings (statutory social care + ring-fenced schools grant).
New **control-change** standout flag (🗳) for councils whose political control changed since 2025 (80).
Dossiers/briefings now carry control history + upcoming election. Rubric modal and methodology updated.

**Verification.** `verify.py` gained three invariants: all contract awards ≥ 2025, all contract links
contain `/Notice/`, and no already-closed poll in `data/elections.csv`. PASSED. Cache-bust `20261007g`.

## 2026-10-07 (night) — Contract link fix + tester-agent bug sweep

- **Contract link fix (shipped `1baadff`).** `/Published/Notice/{id}` serves the raw OCDS JSON (that's why
  clicking a supplier showed a JSON page). Correct human page is `/Notice/{id}`; `build.py` now emits that.
  Validated: first 100 contract URLs returned HTTP 200 before Contracts Finder rate-limited the checker (429).
- **Tester agent sweep** (read-only audit of the live site) found:
  - P2 — postcode result badge labelled every non-county authority "District" (K&C showed "District"). Fixed:
    now maps la_class -> London Borough / Metropolitan Borough / Unitary / District / County.
  - P1 — three orphan render functions referencing removed panels/data (`renderBriefing`, `renderOmbudsman`,
    `renderMomentum`) plus `initSectionTabs` and `medianPerResident`: all dead (never called). Removed them
    and the now-meaningless `with_momentum`/`with_ombudsman` build counts.
  - Improvements applied: added Air quality + House/earnings rows to the Copy-for-AI briefing; feedback
    submit now checks `res.ok`/`success`; bumped the stale cross-council search-index cache-bust.
- Cache-bust `20261007f`. `verify.py` PASSED; `node --check` clean.
- Known-good from the audit: all live assets 200, data.json 283 councils, league `house_earnings` present in
  all rows, 283 dossiers, no undefined global calls, Plotly loads.

## 2026-10-07 (later) — Contract deep links, house-price flag, links panel removed, tier explainer, K&C added (283)

- **Contracts deep-link.** `england_contracts.py` now records each supplier's largest notice
  (`top_notice_id`, `top_title`); `build.py` emits `url` -> `contractsfinder.service.gov.uk/Published/Notice/{id}`
  (verified it resolves to the real notice). Supplier links to the contract, title shown underneath; dossiers
  include the link.
- **House-price flag.** `renderStandout` gained a 🏠 pill (top/bottom-20% house-price-to-earnings), with price
  and national rank. `build.py` now emits `house_earnings_rank` + `house_price`.
- **Links panel removed.** Deleted the "Official records & local coverage" panel and its dead-code
  predecessors (`smartLinks`/`renderSmartLinks`/`renderReadingLinks`). Council header now offers just the AI
  actions: "Copy citizen briefing for your AI" + a "Plain-text dossier (.md)" link.
- **National tab.** Added an "England's councils, by tier" explainer (single-tier / shire district / shire
  county / combined authorities).
- **Party associations re-verified.** Cross-checked all councils against the raw OCD 2026 file. Gateway
  `majority_party` is stale (pre-2026) so it "disagreed" on 62; OCD confirms ours is current (e.g. Birmingham
  2026 = LD/GRN/IND min -> NOC). Cleaned the "Ind Min" token in `control_all.py`.
- **Kensington and Chelsea added (283rd, data-only).** K&C is absent from the Council Gateway, so no minutes.
  Added `E09000020` via `SUPPLEMENTAL` in `scorecard_imd.py`; re-ran population/ethnicity/age/qol/control/
  borrowing/distress/ombudsman/contracts (K&C: £4,587 debt/resident rank #8; house/earnings 24.9×, most
  expensive). Talk-vs-spend/topic/document panels are empty for K&C. Ranks now out of 283 (QOL_N made
  dynamic in `app.js`; `verify.py` derives N from the registry). Postcode W8 7NX now resolves to K&C.
- Cache-bust `20261007d`; `verify.py` PASSED; 283 dossiers rebuilt.

## 2026-10-07 — Contracts pipeline fixed; debt benchmarked; official links; AI dossier revamp

- **Contracts Finder fixed (`england_contracts.py`).** Root cause: bare-word keyword query,
  no date filter, `size=100` → arbitrary historical notices. Now queries the *official register
  name* (e.g. "Manchester City Council", from mysociety `uk_local_authorities.csv`), adds
  `publishedFrom=2023`, `size=200`, dedupes by notice id. Manchester top award went from £6.7m (2024)
  to **£88.1m Ocean Outdoor / £48.2m AGR Power / £29.6m Mitie**; Sheffield now £378m; Camden £417m.
  248/282 councils have contract data. Added sanitisation: per-supplier latest award, future-dated
  `awardedDate` falls back to `publishedDate`, placeholder suppliers ("Please see webpage…") skipped,
  Hull alias fix.
- **Debt benchmarked (`site/build.py`).** New top-level `borrowing_england` = England avg £1,258 /
  median £918 / £91.1bn total; per-council `borrowing.rank` (1 = most indebted; Manchester #24).
  Surfaced as a **corner badge** on the "Debt per resident" stat card (`.stat-header`/`.stat-corner`).
- **Official records panel.** New `council_portals.csv` (official name + Modern.Gov/CMIS committee
  portal for all 282, from `data/_all_councils.json`). `build.py` emits `official_links` per council:
  committee minutes portal, Contracts Finder awards, LGSCO decisions, Police.uk. Replaces the old
  generic Google/BBC search fallback. UI panel renamed "Official records & local coverage"; dossiers
  use the same links.
- **AI dossier + Copy-for-AI revamp.** Fixed the `undefined` council name (added `"name"` to the
  council object in `build.py`). Every outcome now shows **value + rank + England avg + source**;
  borrowing shows rank + England avg/median + General Fund/HRA caveat; talk-vs-spend reintroduced with
  the **DSG pass-through footnote**; crime gets the commuter-inflation note; contract grammar fixed
  (1 award vs N awards) and window labelled 2023–2026. Prompt sharpened so models must contrast against
  benchmarks and name missing data instead of hedging. Both `site/build_dossiers.py` and the browser
  briefing (`buildCitizenBriefing`) updated.
- Rebuilt `data.json` + 282 dossiers + `llms.txt`; `verify.py` PASSED (0 warnings); `node --check` clean.
- **Flagged (pre-existing, not fixed):** `qol_england.rent_affordability` = 43.5 while the methodology
  page states 30.2%. The metric is annualised PIPR rent ÷ gross annual pay, so 43.5 is self-consistent
  with council values (~40%), but the methodology text is stale. Needs a reconciliation pass.

## 2026-10-06 (later still) — UX trims: shorter doc search, contract links, roadmap removed

- Document search capped at the **25** most recent matches (was 200) inside a contained, scrollable list
  (`#docsearch-results` max-height 420px). Caption + stats line updated.
- Contracts panel: supplier names link to Contracts Finder searches; added a plain-English note on what
  the panel is (published awards, framework-ceiling caveat) and a "see all awards" link.
- Removed the "What's next" roadmap block from the feedback tab (panel now "Feedback & suggestions").
- Cache-bust → `20261006c`. Commit `d1ea6ac`, pushed, Pages run succeeded; verified live.

## 2026-10-06 (later) — Housing & Crime forensic terminal removed

- Deleted `site/housing-crime/` (290 files) and `site/build_forensic.py`. Dropped the council-view
  cross-link, the roadmap entry, and the workflow's forensic build/commit steps. Roadmap now shows the
  shipped postcode/rubric/provenance work plus a next-up alerts item. `app.js` cache-bust → `20261006b`.
- Committed `242335e`, pushed; Pages run succeeded; verified live: `/housing-crime/` → 404, no forensic
  references remain in the deployed HTML/JS. `node --check` + `verify.py` (0 warnings) + HTML parse clean.

## 2026-10-06 — Phase 1 shipped live: postcode lookup, flag rubric, provenance layer; corpus refreshed

- **Refresh activated + deployed.** Overnight harvest completed 270/270 (0 fail); guardian auto-moved
  into `data_england/` and ran pipeline + dossiers + forensic. Site now covers **Oct 2024 – Sep 2026
  (377,899 docs)**; forensic set **6,105 decisions / 185 councils**. Pushed to `main` (commit `87fc36e`);
  GitHub Pages run 26 succeeded; verified live on parthgoyal.uk.
- **Phase 1 features (live):**
  - Postcode → council resolver via `api.postcodes.io` in the omnibox and council picker, with a
    two-tier district/county switcher and ward label. Keyless, CORS, cached client-side.
  - Standout flags are now clickable → **rubric modal** (exact thresholds + sources per flag).
  - **Provenance pills** on every panel: Official / Direct record / Algorithmic / Derived.
  - **"How we made this"** accuracy & corrections drawer; every "report a discrepancy" routes to the
    feedback tab.
- **Data gap found while testing postcode matching:** the 282-council registry is missing three unitary
  authorities — **Oxford, Reading, West Berkshire**. Postcodes there fall through (county shown where
  available, else a "not in this build → report it" message). Needs a follow-up registry/harvest fix.
- Verify: `node --check app.js` OK; `site/verify.py` → 0 warnings; HTML parse clean; local server 200s.

## 2026-10-05 (overnight) — Re-harvest resumed under a guardian; civic-tech inspiration report

Journalism project (Housing & Crime terminal + live-deploy check) pinned for now. Focus: get refreshed
data in overnight.

- **Re-harvest resumed.** All-England minutes pull running with rolling window **2025-10-01 → 2026-10-01**
  into `data_england_refresh/` (3 shards, `england_runner.py`, resumable via `doc_topics.csv`). 37/270
  staged at time of writing; ~4 min/council → ETA mid-overnight.
- **Overnight guardian** `/tmp/opencode/finish_refresh.sh` (setsid-detached, `flock` single-instance):
  keeps shards alive, restarts any that die before `SHARD n DONE`, then **auto-activates** — moves
  staged `c*` into `data_england/` and runs `pipeline.py --skip-fetch` → `site/build_dossiers.py` →
  `site/build_forensic.py`. Log: `/tmp/refresh_finish.log`; done-flag `/tmp/opencode/refresh_activated.flag`.
  Activation rebuilds `site/data.json` in place; **not committed/pushed** (not explicitly requested).
- **Civic-tech inspiration report:** `INSPIRATION_civictech.md` (10 actionable ideas from the Civic Tech
  Field Guide, each citing a real project/URL). Top themes: source-linked "ask the record" answers,
  per-council alerts/RSS, a public accuracy+corrections page, provenance-stamped metric cards,
  procurement red-flag analytics, normalisation toggles, promise/delivery tracking, postcode entry.

## 2026-10-05 (v8.1) — Cleanup pass: dead data stripped, dynamic window, FOI modal, automation moved

Quick fixes on top of v8 (no heavy re-harvest — that stays paused/resumable).

- **Captions now data-driven.** `build.py` computes `corpus_window` (actual from/to/label +
  document count, currently Oct 2024 – Mar 2025, 233,178 docs) and the "What they talk about"
  caption is set from it in `app.js`. No more hardcoded FY label to go stale.
- **Dead payload stripped.** Removed the unused `momentum`, `ombudsman`, and `briefing` fields
  from `data.json` (and their computation). `data.json` 2.2 MB → **1.68 MB**. `verify.py`
  checks updated (corpus-window check replaces the momentum/ombudsman coverage checks).
- **FOI generator** in the forensic terminal now uses an in-page modal with topic buttons
  instead of a browser `prompt()`; adds modal styles.
- **Automation moved to the deployable repo:** workflow is now
  `site/.github/workflows/refresh.yml` (was in the project dir). It now also builds the
  AI-native dossiers + forensic dataset and commits `dossiers/`, `llms.txt`, `housing-crime/`.
  Old `.github/` in the project dir removed.
- Removed the Ombudsman from the footer source list (panel + data already gone).
- **Verify:** `python site/verify.py` → `VERIFY PASSED (0 warnings)`. All assets + terminal
  serve 200; MCP server re-verified after rebuild.

**Still open (unchanged):** the rolling-window minutes refresh (`data_england_refresh/`, 5/270
staged, paused). To finish:
`for s in 0 1 2; do OUT_DIR="$PWD/data_england_refresh" nohup python3 england_runner.py $s 3 > /tmp/refresh_shard_$s.log 2>&1 & done`
then activate with the `mv` + rebuild chain. Not committed/pushed yet.

## 2026-10-05 (v8) — Revert to clean OG layout + standout flags + smart links + AI-native + Housing & Crime terminal (Sprint 1 & 2)

Product reset: dropped the four-section executive dossier back to a single-scroll OG layout,
made the core site AI-native, and split off a dedicated Housing & Crime forensic terminal.

**Sprint 1 — Council Receipts (main site):**
- `site/index.html` rewritten to the clean single-scroll council view. Removed the exec-briefing
  card, the in-council section tabs, the noisy **Ombudsman** panel, and **topic momentum**
  (2-month deltas). All remaining panels now render in one scroll.
- New **Standout Benchmark Flags** (`renderStandout` in `app.js`): 3–5 national-decile pills under
  each council name — crime, rent strain, child poverty (top/bottom 20%), borrowing per resident
  (top/bottom 10%), Section 114 / EFS distress, and the largest talk-vs-spend gap.
- New **smart links** (`smartLinks`): programmatic, working links for **all 282** councils
  (committee minutes, police.uk, planning register, scrutiny/budget news, MHCLG profile, AI dossier)
  replacing the old 15-council hardcoded `reading_links.csv`.
- **Document-search chip bug fixed.** Root cause: topic chips wrote `@Housing & Planning` into the
  text box, and the parser split on spaces → `&` matched zero index tokens → empty intersection;
  topic compare was also case-sensitive. Now topic filters live in a `docSearchTopics` Set
  (exact-name, case-insensitive) decoupled from the text query.
- **AI-native:** one-click *Copy citizen briefing for your AI* (`buildCitizenBriefing`), a new
  `site/build_dossiers.py` producing 282 plain-text dossiers (`site/dossiers/{ons}.md`) and
  `site/llms.txt`.
- `style.css`: added standout-badge, council-action, AI-button and active-chip styles.
- Harvest staleness fixed: `england_runner.py` no longer hardcodes 2024-10-01→2025-03-31; it now
  uses a rolling 12-month window (ISO overridable via `DATE_FROM`/`DATE_TO`), supports `OUT_DIR`
  staging and `FORCE=1`. **Background refresh launched** into `data_england_refresh/` (270 ids,
  3 shards, logs `/tmp/refresh_shard_{0,1,2}.log`) — est. 3–6 h. Not yet activated.

**Sprint 2 — Housing & Crime Forensic Terminal (`site/housing-crime/`):**
- `site/build_forensic.py`: classifies 270 councils' `decisions.csv` into four forensic categories
  — `housing_ta`, `planning_s106`, `enforcement_asb`, `contracts` — extracts £ values, joins ONS
  rent/crime pressure + MHCLG spend, and generates algorithmic investigative leads. Output:
  **3,932 flagged decisions across 195 councils**, `data.json` 2.75 MB + 282 plain-text dossiers
  + `llms.txt`.
- Frontend: England **pressure matrix** (rent vs crime scatter, bubble = housing spend, click →
  paper trail), **Council paper trail** (pressure cards, spend, category-filtered evidence stream
  with links to official signed notices, leads), **MCP & AI** tab.
- `mcp_server.py`: dependency-free Model Context Protocol server (stdio JSON-RPC). Tools:
  `list_councils`, `get_council_dossier`, `search_decisions`, `generate_foi`. Verified working
  (e.g. `search_decisions(category=housing_ta, min_value=2,000,000)` → 119 matches).
- Client-side **FOI request generator** with four issue templates. Cross-linked from the main site's
  council view.

**Verify:** `python site/verify.py` → `VERIFY PASSED (0 warnings)`. All new assets serve 200 under
`python -m http.server`. No commit made (awaiting explicit publish instruction).

**To activate the refresh when it finishes:**
`mv data_england_refresh/c* data_england/ && python pipeline.py --skip-fetch && python site/build_dossiers.py && python site/build_forensic.py`

## 2026-10-05 — Strategic review: proposed London pilot (recommendation only)

- Reviewed the proposed return to a simpler England overview alongside a deeper London product; no production or pipeline changes made.
- Recommendation: retain one Council Receipts product and shared data core, with an England overview and a clearly labelled London pilot. Benchmark the 32 boroughs; include the City of London in search but treat it separately in comparisons.
- Preconditions: audit document completeness and publication lag against council websites, distinguish minutes from reports/decisions, and expose dates/coverage per metric. September 2026 documents alone do not establish complete current coverage.
- Prioritise temporary-accommodation costs, accommodation supplier concentration, SEND transport, and financing pressure. Treat anomalies as investigation leads, not findings of inefficiency or misconduct; agenda share is not a measure of scrutiny.
- Next: validate one temporary-accommodation workflow with journalists and councillors before expanding modules. Measure independently checked leads, usable scrutiny questions, repeat use, and refresh effort. The London pivot remains proposed, not adopted.

## 2026-10-05 (v7) — Production-grade rebuild: new datasets, tier-aware aggregates, executive dossiers, cross-council search

Big push to turn the prototype into a production-grade analytics product for journalists and
councillors. All five planned phases shipped.

- **Phase 1 — Data gaps fixed + pipeline unified:**
  - The 6 hack-day councils that had no Gateway ID (Leeds, Manchester, Camden, Bexley, Hillingdon, Somerset) are now mapped from `data_fy5..7/councils.csv`. New shared `site/common.py` is the single registry source, so `build.py` and `build_search.py` can't drift.
  - New `pipeline.py` at the project root: one command runs the fetchers → `site/build.py` → `site/build_search.py` → `site/verify.py`. Flags: `--skip-fetch`, `--skip-contracts`.
  - New `site/verify.py`: preflight integrity suite (282 councils, all ONS codes valid, coverage floors, six formerly-missing councils carry discussion data, search indexes present). Non-zero exit halts a bad build.
- **Phase 2 — Three new statutory datasets integrated (all 282 councils, zero scraping):**
  - **Ombudsman watchdog** (`england_ombudsman.py` → `data_england/ombudsman.csv`): LGO annual review 2024-25. Upheld rate, peer upheld rate, upheld cases, compliance rate. 282/282 matched by normalised authority name.
  - **Borrowing & debt** (`england_borrowing.py` → `data_england/borrowing.csv`): MHCLG quarterly Borrowing Live Table (latest quarter, discovered from the gov.uk collection page so it survives URL churn). Total outstanding debt + per-resident. 282/282 (reconciles two stale ONS codes in the source by name).
  - **Top contract awards** (`england_contracts.py` → `data_england/contracts.csv`): Contracts Finder legacy search API, buyer-name matched, multi-supplier framework lots and zero-value awards excluded. 250 councils with ≥3 matched contracts, cached under `data_england/contracts_cache/`.
- **Phase 3 — Smart party aggregates:**
  - `data.json` now carries `party_by_tier` (single-tier / shire district / shire county / all), fixing the Simpson's-paradox trap of averaging councils that do different jobs.
  - National tab gets a tier toggle; every party bar shows its `n`.
- **Phase 4 — Frontend redesign (holistic dossier, no overload):**
  - Council view reorganised into an **Executive briefing** card (Governance / Fiscal health / Accountability + talk-vs-spend disconnect + agenda surge) and four section tabs: **Overview**, **Agenda & minutes**, **Money & contracts**, **Outcomes & watchdog**. Progressive disclosure keeps the holistic view but kills the 4,000px scroll.
  - New panels: **Borrowing & debt**, **Largest contract awards**, **Ombudsman watchdog**.
  - New header **omnibox**: type a council to jump to its dossier, or an issue/contractor (e.g. "temporary accommodation", "Capita") to run a **cross-council search** ranked by matching documents. Backed by `site/search_index_global.json` (lazy-loaded, 1.7 MB, ~10.4k tokens).
  - Document search results gain a **Copy citation** button.
- **Phase 5 — Automation:** `.github/workflows/refresh.yml` (in the project dir; move to repo-root `.github/workflows/` to activate) runs the pipeline on a monthly cron, checks out the data + site repos, and commits refreshed artifacts. Needs a `DATA_REPO_TOKEN` secret.

- **Coverage now:** 282 councils; 232 with topic discussion (+6); 224 with momentum (+6); 232 search indexes; 282 ombudsman; 282 borrowing; 250 contract panels. `data.json` 2.2 MB; `search_index/` 39 MB; global index 1.7 MB.

- **Verify:** `python pipeline.py --skip-fetch` → `VERIFY PASSED`.

## 2026-09-30 (v6) — Topic Momentum Tracking & Interactive Document Search

- **Shipped two roadmap features (items 1 & 2 from the Feedback tab):**

  1. **Topic Momentum Tracking** — Monthly topic share time-series computed for 218/282 English councils across the full 6-month FY2024-25 window (Oct 2024–Mar 2025). For each council, two visualisations are rendered in the new "Topic momentum" panel:
     - A **multi-line chart** showing each topic's discussion share over time (top 4 movers coloured, rest in grey).
     - A **grouped bar chart** comparing the last 2 months' average discussion share vs the prior 2 months, sorted by absolute change — showing which topics are gaining or losing attention (minimum 5 documents per window required).
  2. **Interactive Document Search** — Per-council search index files (`site/search_index/<ons_code>.json`) generated by new `site/build_search.py`. Each council's index contains the 500 most recent classified documents (with snippets, topic hits, PDF links). Frontend provides:
     - **Free-text keyword search** across snippet + meeting name + topic labels (client-side inverted index for fast filtering).
     - **Topic chip filters** — pre-computed topic badges with doc counts; clicking a chip prepends `@topic` token to the search input.
     - **Results table** showing date, meeting name, 120-char snippet, coloured topic badges, and "Open PDF" button linking to the Gateway PDF.
     - Graceful degradation: councils without search indexes show a "no data" message.

- **Data pipeline changes:**
  - `site/build.py` — refactored corpus loading into `_load_raw_corpus()` (shared helper), added `load_corpus_momentum()` computing monthly topic shares per council with trend direction (rising/declining/stable based on 1pp threshold). Momentum data is ~2 KB per council, total data.json = 1.8 MB.
  - `site/build_search.py` — new file, generates per-council search indexes. Compact key format (`d`/`m`/`s`/`u`/`t`), capped at 500 newest docs per council. Total index = 38 MB (226 files).
  - `site/index.html` — added two new panels: `#panel-momentum` and `#panel-docsearch`. Updated roadmap to show items 1 & 2 as shipped, added 3 new future items.
  - `site/app.js` — added `renderMomentum()` and `renderDocumentSearch()` with client-side inverted index (buildDocIndex) for fast keyword matching. Cache-bust bumped to `v=20260930a`.
  - `site/style.css` — added styles for momentum bar, docsearch inputs, topic chips, result cards, and PDF link buttons. Extended panel animation delays for new panels.
  - Cache-bust string updated in all three files (index.html, app.js, style.css).

- **Known limitations (unchanged):** 6 original hack-day councils (Leeds, Manchester, Camden, Bexley, Hillingdon, Somerset) have no Gateway ID mapping in the registry, so they lack topic data, momentum, and search indexes. Also, the Council Gateway API coverage is inherently uneven — some councils have thin or missing minutes for this period.

- **Coverage:** 282 councils in registry, 226 with topic data, 218 with momentum (4+ months, 5+ docs/window), 226 with search indexes.

## 2026-08-25 (v5.9) — Methodology Refresh, Dedicated League Table Tab & Universal News Links

- **Pushed `7f6e34c..7040d88` to GitHub Pages:**
  - Static plots and mobile touch fix.
  - Nomis APS 2025/26 + Census 2021 hybrid ethnicity pipeline and provenance captions.

- **Methodology & Deprivation Cleanup:**
  - Removed remaining references to "deprivation" in the UI start prompt and in-app methodology.
  - Updated `METHODOLOGY.md`, `PROJECT.md`, `site/README.md`, and in-app `<details id="panel-methodology">` to document the **7 Quality of Life outcome metrics** across all **282 councils** with population-weighted spend benchmarks and tier remits.
- **Dedicated League Table Tab & National Reordering:**
  - Extracted the National Quality of Life League Table into its own dedicated **"League table"** top-level navigation tab (`data-tab="league"`), giving sortable rankings maximum space.
  - Reordered the **National** tab so party budget and discussion shares appear at the top, followed by the Financial Distress Watchlist.
  - Added instant client-side tab switching and smooth scroll when clicking council links from the league table or distress watchlist.
- **Universal News & Intelligence Links (282/282 Councils):**
  - Updated `site/build.py` to provide 3 targeted local news and official document search links for all councils without manual curation, giving every English authority live coverage.
- **Mobile-Friendly Chart & Layout Polish:**
  - Dynamic viewport checks (`isMobile() < 640px`) in `site/app.js`:
    - Adjusted horizontal bar chart margins (`topics-chart`, `money-chart`, `tvs-chart`, `party-chart`) so left labels don't crush bar widths on narrow screens.
    - Scaled chart typography (`10px–10.5px`) and reduced vertical row heights (e.g. Age Pyramid compacted from 60px/row to 32px/row on phones).
    - Shortened party legend labels on mobile (`Lib Dem`, `Cons.`) and adjusted inside-text thresholds to prevent label overlaps.
    - Dispatched resize triggers on tab changes and added debounced `window.resize` handlers to ensure immediate redraws when rotating screens or switching tabs.
  - CSS polish in `site/style.css`:
    - Reduced panel padding from 26px to 12px–14px on mobile viewports for maximum usable chart area.
    - Added horizontal scroll safety on `#league-table-wrap` and `#distress-watchlist-wrap`.
    - Compacted `.qol-card`, `.tabs`, and typography on mobile screens.

## 2026-08-24 (v5.8) — What's Next Roadmap Focused on Custom Querying & Momentum

- **Pushed `b34e7a0` to GitHub Pages:**
  - Streamlined the "What's Next" roadmap on the Feedback tab to focus on:
    1. **Interactive Document Querying & AI Assistant:** Natural language search over primary council papers, minutes, and decisions.
    2. **Theme & Decision Momentum:** Tracking emerging themes, surging keywords, and committee decisions gaining steam.
  - Cleared out the previous roadmap milestones (All-England expansion, richer scorecard, financial health) since they are now fully built and shipped.

## 2026-08-24 (v5.7) — Population-Weighted Spend Benchmarks

- **Pushed `6e1241d` to GitHub Pages:**
  - Replaced the unweighted median spend benchmarks with **population-weighted England averages**:
    - Aggregated total spend across all local authorities divided by total English population in the dataset (£/resident per service).
    - Aggregated total topic spend across all authorities divided by total spend to produce true national population-weighted budget shares.
  - Updated money chart swatches, tooltips, and captions to `England average (pop. weighted)`.

## 2026-08-24 (v5.6) — Rank Quoted as "Rank #X of 282"

- **Pushed `c7294ad` to GitHub Pages:**
  - Formatted all Quality of Life scorecard rank badges explicitly as **`Rank #X of 282`** (e.g. `Rank #186 of 282`).
  - Adjusted benchmark line styling and flex spacing for clean layout.

## 2026-08-24 (v5.5) — National Ranks on QoL Cards & Dynamic League Ranking

- **Pushed `ba51d12` to GitHub Pages:**
  1. **National Ranks in QoL Scorecard Cards:** Every single Quality of Life metric card
     now displays the council's national rank across England (out of 282) (e.g. `Rank #32 in England`).
  2. **Dynamic Rank in National League Table:** When sorting by any indicator (GCSE score,
     life expectancy, rent, child poverty, etc.), the `Rank` column shows the council's
     true national rank in England under that active sort order, preserved even when filtering
     by council name.
  3. **District Remit Callout:** Added explanatory notices for Shire Districts clarifying
     that Social Care, Education, and Public Health are delivered and funded by their
     parent County Council.

## 2026-08-24 (v5.4) — GCSE Attainment 8 Added & Deprivation Removed

- **Pushed `c4bf52a` to GitHub Pages:**
  1. **Removed Deprivation:** Completely dropped the Overall Deprivation (IoD2025) card
     and league column from both the council receipt and the national table.
  2. **Added GCSE Attainment 8 (DfE 2023/24):** Average Key Stage 4 points per pupil
     across 8 subjects added to all 282 councils (and England benchmark 46.1 pts).
  3. **Quality of Life Panel:** Now presents 7 pure, outcome-based indicators:
     - *Life Expectancy* (ONS 2025: yrs)
     - *GCSE Attainment 8* (DfE: pts)
     - *Rent Affordability* (ONS: % of pay)
     - *Air Quality PM2.5* (Defra: % mortality)
     - *Child Poverty* (DWP: % in low income)
     - *Claimant Rate* (Nomis: %)
     - *Crime Rate* (ONS CSP: per 1k)
  4. **National League Table:** Clean 7-metric table with sortable columns, real-time
     name search, and working Top 10/25/50/All toggles.

## 2026-08-24 (v5.3) — Clean Combobox Picker & Built-In AJAX Feedback Form

- **Pushed `e435b45` to GitHub Pages:**
  1. **Single Unified Combobox:** Replaced the truncated dual select/input with a single,
     custom styled searchable combobox. Clicking the input or the `▼` button drops down a
     scrollable menu of all 282 councils with party badges; typing filters the list in real-time.
  2. **Built-In Open Feedback Form:** Replaced the broken Cusdis embed with a clean,
     till-receipt-styled AJAX feedback form supporting anonymous or named comments,
     category tagging (data correction, feature suggestion, general thoughts), and instant
     inbox delivery via AJAX without leaving the page.

## 2026-08-24 (late) — SHIPPED UX & League Table Overhaul to Live

- **Pushed `4b34009` to GitHub Pages:**
  1. **Council Picker UX (Blank Start State):** Site no longer arbitrarily opens
     Adur by default. First-time visitors are welcomed with a clean prompt card
     encouraging them to type or select their council. Direct deep-links (`?council=...`)
     still load immediately.
  2. **Clickable Dropdown Added:** Paired the typeahead search with a native `<select>`
     dropdown containing all 282 councils, allowing users to browse without typing.
  3. **Overall Deprivation Display:** Card now explicitly states **National Rank in
     England (1 to 282)** alongside decile and streamlined context copy.
  4. **QoL League Table:** Restructured the national table to rank councils across all
     key Quality of Life metrics (Deprivation Rank, Life Expectancy, Rent Affordability %,
     Child Poverty %, Claimant Rate %, Air Quality PM2.5 %, Crime / 1k).
  5. **Real-Time Council Search in League Table:** Added search input to filter table rows
     instantly by council name.
  6. **Toggle Button Fix:** Fixed button active state highlights (Top 10 / 25 / 50 / All 282)
     and table slicing.
  7. **Indicator Explanations:** Polished the methodology and card explanations for Air Quality
     (PM2.5 mortality fraction) and Deprivation.

## 2026-08-24 — SHIPPED QoL Suite, Financial Distress Engine & Universal Age Pyramids

- **Phase 1 & Phase 2 Complete across all 282 councils.**
  1. **Universal Age Pyramids (282/282 councils):** Created `data_england/age_bands_all.py`
     querying Nomis `NM_2002_1` 5-year age bands × sex for all 282 ONS codes + England.
     Eliminated the missing population pyramid bug across 267 councils.
  2. **Quality of Life (QoL) Suite (282/282 councils):** Created `data_england/qol_all.py`
     compiling 6 outcome-based indicators alongside single consolidated IoD2025 IMD:
     - *Life Expectancy at Birth* (ONS 2025: 282 LAs + England 81.9 yrs).
     - *Rent Affordability* (ONS PIPR/ASHE: % of median FT gross earnings).
     - *Air Quality PM2.5* (Defra/OHID: mortality attributable to particulate pollution).
     - *Child Poverty* (DWP: % of children under 16 in low income families).
     - *Claimant / Unemployment Rate* (Nomis July 2026: % of 16-64 population).
     - *Crime Rate* (ONS CSP: recorded offences per 1,000 residents).
  3. **Financial Distress & Health Check (282/282 councils):** Created
     `data_england/financial_distress.py` tracking statutory Section 114 notices
     (Birmingham, Nottingham, Woking, Thurrock, Croydon, Slough, Northumberland),
     MHCLG Exceptional Financial Support (EFS) capitalisation directives (£1.25bn
     Birmingham, £220m Bradford, £76.9m Somerset, £121m Southampton, etc.), and
     external audit backlogs.
  4. **National Tab Party Cleanup:** Removed `Independent/Other` from national
     comparative spend and discussion charts; retained local administration labels
     on council receipts.
  5. **National Distress Watchlist:** Added interactive distress monitor table
     listing all councils operating under statutory spending freezes or emergency
     MHCLG support.
  6. **Open Anonymous Comments:** Swapped out GitHub-only Giscus for Cusdis
     zero-login name/anonymous comment widget.
  7. **Build & Data Pipeline:** Updated `site/build.py` and regenerated `site/data.json`
     (282/282 councils with age pyramids, QoL, and financial distress).

## 2026-08-23 — SHIPPED all-England site to live (282 councils)

- **Deployed.** Pushed `9b55b70..48d4622` to `council-receipts` main; GitHub Pages
  rebuilds parthgoyal.uk/council-receipts/. This lifts the earlier "don't touch the
  live site" hold, per Parth's "push to website" request.
- **What shipped** (build.py v5 + frontend rework, executes Parth's message + the
  "Keep, with fresh control data" decision):
  1. **282 councils** — universal ONS-code join in `build.py` unions the 267
     England-harvest + 15 originals off the IoD2025 registry. data.json: 282 councils,
     282 league rows, 6 party buckets. Panel coverage: topic_share 226, money 281,
     talk_vs_spend 225, scorecard/population/ethnicity/control 282.
  2. **Searchable picker** — typeahead `<input list>` (datalist of 282) replaces the
     dropdown; `?council=` deep-link.
  3. **IMD scorecard** — old 5-metric strip replaced by the 8 IoD2025 domains, coloured
     by decile (magenta = more deprived, green = less), rank labelled with tier pool.
  4. **League table** — top-10 default, 10/25/50 toggle, IMD domain columns, sorts
     most-deprived first.
  5. **Control** — from Open Council Data UK (`control_all.py`), current composition,
     6 buckets incl. minority/led administrations. Party charts kept with this data.
- **Review catch (fixed pre-push):** delegated frontend had `decileColor` inverted
  (reversed lerp args) — most-deprived councils rendered green, contradicting the
  caption. Fixed to mirror `rankColor`; verified Manchester (decile 1) → magenta,
  Wokingham (decile 10) → green, Blackpool tops the league.
- **DEVIATION to flag to Parth:** used **Open Council Data UK** for control, not
  Democracy Club. DC publishes election results/candidates only — no clean
  current-control table. OCD (`history2016-26.csv`, public domain, updated 2026-08-21)
  gives current composition directly per the "fresh accurate control data" intent.
- **Not done / next:** DEMO.md is Parth's own; Streamlit 8599 still up (fallback —
  kill after sign-off). Feedback-tab roadmap still lists "growing to every English
  council… underway" and "five metrics" scorecard — now stale, worth a reword.

## 2026-08-23 — IMD scorecard (IoD2025) built for all 282 councils

- **Parth's call: rebuild the scorecard on the English Indices of Deprivation.**
  Found the 2019 index has been superseded by **IoD2025 (MHCLG, published 30 Oct 2025)**
  — 55 indicators, current boundaries. Decisions taken (via AskUserQuestion):
  **all 8 measures** (overall IMD + 7 domains: Income, Employment, Education, Health,
  Crime, Barriers, Living) and **pure IMD** (drop all 5 old bespoke metrics —
  Attainment8/CO2/rent/crime/A-road — now covered or superseded).
- **Source**: `data_imd/File_10_lower_tier.xlsx` (296 districts/unitaries) +
  `File_11_upper_tier.xlsx` (153 counties), downloaded from gov.uk. `scorecard_imd.py`
  routes E10 county codes → File 11, everything else → File 10.
- **Join is perfect**: all council `ons_code`s (from `name_map.csv` + the 15 originals'
  codes lifted from `scorecard.py`) match IoD2025 exactly. No LGR/stale-code problem —
  Somerset resolves to current unitary E06000066, all 21 counties to upper-tier. The
  county rank-aggregation gotcha is gone (File 11 is official upper-tier).
- **Output `data_england/scorecard_imd.csv`** (long): 282 councils × 8 domains = 2256
  rows. Cols: council, ons_code, tier, pool_n, domain, **rank** (1 = MOST deprived in
  pool), **score** (nationally comparable across tiers, higher = more deprived),
  **prop10** (share of LSOAs in England's most-deprived 10%, tier-agnostic), **decile**
  (1 = most-deprived tenth of pool). Verified: 8 domains/council, zero nulls; Camden
  IMD 83/296, Kent 92/153, Somerset 134/296 match raw xlsx.
- **Presentation note for site wiring (later):** lower-tier ranks are /296, upper-tier
  /153 — NOT the same scale. For any cross-council view (heat strip, league table) use
  `score` or `prop10` (both national), and label the rank pool. Direction: more deprived
  = "worse" end of colour scale. Nothing wired to the site yet (per Parth) — data only.

## 2026-08-23 — all-England harvest COMPLETE: 270/270, zero failures

- **All 270 councils harvested** into `data_england/c<id>/` (5 CSVs each). Verified:
  270/270 have `doc_topics.csv`, 270 `c<id>` dirs total, **zero FAIL lines** across
  all shards, zero dirs missing `doc_topics.csv`. **~214,834 classified doc-topic rows.**
- Resumed from the 73/270 pause; all 4 shards ran clean through the outage-failed
  councils on retry (skip-if-done logic held). Shards finished in order 0, 3, 2, 1
  (shard 1 drew the longest tail incl. County Durham/Newcastle, no failures). Monitor
  stopped, all shard processes exited.
- **Data-pipeline half already done** in `data_england/`: finance_all (317 authorities),
  name_map (270/270), profile_all (267), scorecard_all (267).
- Still running (NOT harvest, leave alone): Streamlit 8599 (fallback, kill after Parth
  sign-off), idle http.server previews on 8600/8791.
- **Next (needs Parth before merge — two judgment calls):**
  1. **Party control at 270 scale** — Gateway `majority_party` is stale pre-May-2025.
     Either drop party-control charts at all-England scale, or source fresh (Democracy
     Club / OpenElections). Party charts currently exist on the 15-council National tab.
  2. **reading_links at 270** — 3 curated links/council (=810) is infeasible by hand.
     Rethink: drop the panel at scale, auto-source, or keep only for a featured subset.
  - Then: merge `c<id>` minutes with finance_all/profile_all/scorecard_all/name_map into
    a combined all-England corpus. **Do NOT update the live site until Parth says go.**

## 2026-08-22 (night) — harvest PAUSED at 73/270 (resume when home)

- **Paused by Parth.** All 4 shard processes stopped. **73/270 councils on disk**
  (`data_england/c<id>/doc_topics.csv`). No data loss; fully resumable.
- **Mid-session Poteris API outage** (~19:0x–19:26): server threw 500s on
  `/documents` + timeouts on `/councils`. Not our bug — harvest.py surfaces 500s as
  FAIL and writes nothing, so failed councils just retry. Recovered 19:26, shards
  relaunched, ran 68→73, then Parth paused.
- **RESUME COMMAND** (run from project dir; relaunch with output redirect so the
  progress/FAIL monitor works — the plain relaunch I used skipped the redirect):
  ```powershell
  $dir = "C:\Users\dell\analysis-projects\projects\council hack day"
  0..3 | ForEach-Object {
    Start-Process -FilePath "C:\Users\dell\miniconda3\python.exe" `
      -ArgumentList "england_runner.py $_ 4" -WorkingDirectory $dir -WindowStyle Hidden `
      -RedirectStandardOutput "$dir\data_england\shard$_.out" `
      -RedirectStandardError  "$dir\data_england\shard$_.err"
  }
  ```
  Shards skip finished councils, so this picks up from 73 and retries outage failures.
  Before resuming, sanity-check the API is up: `curl -s -o nul -w "%{http_code}"
  https://councilgateway.poteris.co.uk/council-api/councils` should be 200.
- Data-pipeline half (finance/profile/scorecard/name_map for all England) already DONE
  in `data_england/` (see agent output). Site still on 15 councils, not updated.
- Scoping note added: `AUTOMATION.md` (APIs → scheduled GitHub Action build, not
  browser-side; future versions).

## 2026-08-22 (evening) — all-England harvest RUNNING (roadmap #1)

- **270 councils harvesting in background**, FY window Oct 2024–Mar 2025, 4 detached
  python processes (survive session close): `england_runner.py <shard> 4`, logs in
  `data_england/shard{0-3}.out`. Resumable: each council lands in `data_england/c<id>/`,
  re-running a shard skips finished councils. Site NOT being updated (Parth's instruction).
- Scope: 320 Gateway councils − 35 Scotland/Wales/NI (england_prep.py, name-matched,
  eyeballed clean) − 15 already harvested = 270. Gateway has duplicate ids for
  Cambridgeshire/Essex/Walsall — both kept, merge step should pick the one with docs.
- ETA: rough 4-6 h at ~4-5 min/council/shard. Expect stragglers (County Durham was cut
  before for API slowness — it's back in, may FAIL or crawl).
- **Still to do for all-England v1**: merge c<id> dirs → combined corpus; extend
  finance/profile/scorecard/age_bands to all LAs (sources already cover all England);
  party control for 270 councils (API majority_party is stale pre-May-2025 — needs a
  fresh source, e.g. Wikipedia/Democracy Club, or ship with stale + caveat);
  reading_links for 270 councils probably not feasible 3-per-council — rethink.

## 2026-08-22 — hack day, DEPLOYED + final tweaks

- **Site is live at https://parthgoyal.uk/council-receipts/** — public repo
  github.com/ParthG60/council-receipts (site/ is now its own git repo; GitHub Pages
  serves main branch root under the parthgoyal.uk custom domain).
- Deploy mechanics: gh device-flow auth (token in session scratchpad, gone on cleanup);
  the permission classifier blocked Claude from publishing with the token, so Parth ran
  the deploy script from his own terminal. Future pushes: commit in site/ and `git push`
  (gh auth may need re-login).
- League table: added # position column (renumbers under active sort). Discussion-by-party
  panel briefly removed then restored on Parth's reversal.
- **Feedback tab added + deployed**: third tab with roadmap (all councils → better
  scorecard → voting outcomes → financial health) and two channels (GitHub issues +
  mailto parthgoyal60@gmail.com — flagged to Parth, swap/drop on request). Deep link:
  ?tab=feedback (tab param now generic). Routine git push from Claude works; only the
  initial token+repo-create was classifier-blocked.
- API question settled: static is correct — discussion needs server-side harvest+classify,
  money/scorecard sources are annual CSVs with no live API. Post-hack path if wanted:
  GitHub Action cron re-running harvest+build, committing fresh data.json.

## 2026-08-22 — hack day, v6 redesign ("till receipt" aesthetic)

Full visual redesign of site/ (main loop, frontend-design pass). Old look backed up in
`site_v5_classic/` — restore by copying those 3 files back into site/.
- Concept: till-receipt civic ledger. Warm paper bg + grain, receipt-slip panels with
  torn perforated bottom edges, dashed rules, stamp-red accent (#b5372b).
- Type: Fraunces (masthead/panel titles) + IBM Plex Mono (all numbers, captions, tables,
  chart type via a Plotly.newPlot wrapper injecting base font/transparent bg).
- Palette system: ink #262420 = this council/talk · warm grey #b6ad9c = England/median
  benchmarks · stamp red = spend share (TvS), toggles, active states.
- Money-chart labels fixed: SERVICE_SHORT map (2-line breaks for long RSX names) — the
  clipped "ousing services (GFRA only)" bug is gone.
- **Data fix found via screenshots: ethnicity_england was null for ALL councils** — the
  England-comparison v5 feature silently degraded because profile.csv had no England row.
  Appended one (Census 2021 England: 81.0/9.6/4.2/3.0/2.2), rebuilt: 15/15 now show it.
- League table density pass (fits without h-scroll, headers wrap); `?tab=national`
  deep-link added. Verified via headless-Edge screenshots of both tabs.

## 2026-08-22 — hack day, v5 FINAL (shipped for demo)

v5 polish round on Parth's screenshot feedback, all verified against rebuilt data.json:
- Bar-end labels unclipped everywhere (cliponaxis + axis headroom, all 10 bar charts).
- Ethnicity + population pyramid: paired side-by-side bars vs England (overlay dropped).
- Money panel: paired bars (council vs median) + £/resident ↔ %-share toggle
  (share view vs England-average shares from RSX ENGLAND row).
- Scorecard back to **5 metrics** — A-road delay re-added (DfT cgn0504). Somerset matched
  direct under stale pre-LGR code E10000027 (same highway authority — NOT a proxy);
  Mid Suffolk→Suffolk stays the only aroad proxy. scorecard.csv = 80 rows.
- League table: avg_rank REMOVED, traffic is 5th column + default sort (best-first).
- Control line: "previously X" suppressed when unchanged (Sheffield fixed; Leeds/Kent keep theirs).
- reading_links.csv: 2026-only sweep — 7 pre-2026 rows replaced (one was a 2021 Leeds piece,
  one a dead Yahoo link); ~9 undated rows unverifiable but no pre-2026 signal.
- METHODOLOGY.md: 5-metric table, avg-rank sentence replaced.

Commit mechanics: hack-day doc has NO submission repo — only "Hackday work and outputs -
add here!" Drive subfolder. Parth to drop METHODOLOGY.md (+ site zip/screenshots) there.

## 2026-08-22 — hack day, v4 final (Council Receipts)

**Shipped.** Static site (`site/`, serve: `python -m http.server 8600 -d site`) is the product;
Streamlit `app.py` on 8599 is a frozen fallback (kill after demo).

Done today, v4 round:
- Expanded 9 → **15 councils**: + Leeds, Manchester, Camden (LAB), Bexley, Hillingdon (CON),
  Somerset (LD). FY24-25 window only (Oct 2024–Mar 2025), shards `data_fy5..7` (~8,100 docs).
  Full Gateway inventory is 320 councils (paginate at 25/page — `data/_all_councils.json`).
- **All discussion panels now use the FY-matched corpus** (data_fy1..7); YTD corpus retired from UI.
- **Money measure = GROSS expenditure (C3, staff+running costs)** — flipped from net after
  Parth's pushback: gross = resources poured in; net understates fee-heavy services (Camden
  roads −£23m net vs £37m gross). finance.py, METHODOLOGY.md, site copy all aligned.
- Site rework A–H: population + ethnicity chart replaces profile strip; gendered population
  pyramid (age_bands.csv schema council,band,sex,pct); 4-metric scorecard heatmap (A-road cut);
  sortable league table, avg-rank default, no badges; discussion-by-party chart; merged
  Methodology with taxonomy table; desktop-first polish; renamed **Council Receipts**.
- Leeds is **NOC (Labour minority) since May 2026** — caught by links agent, fixed everywhere
  (PARTY_OVERRIDES, PREVIOUS_CONTROL, LAB bucket per Bristol precedent).
- reading_links.csv: 45 verified rows, 3/council. METHODOLOGY.md written (Drive-ready).
- Review pass: 17/17 data checks (data.json vs CSVs), UI copy sweep clean, server live.

**Pick up next:** DEMO.md (Parth's), Drive folder, kill 8599 after sign-off, repo push (parked).
Post-hack roadmap in PROJECT.md.
