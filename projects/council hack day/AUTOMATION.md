# Automation scope: APIs in Council Receipts (future versions)

## Update (v7, 2026-10-05): the pipeline exists

`python pipeline.py` is now the single entrypoint. It runs, in order:

1. `england_ombudsman.py` — LGO complaints CSV (network).
2. `england_borrowing.py` — MHCLG Borrowing Live Table (network; URL discovered from the gov.uk collection page).
3. `england_contracts.py` — Contracts Finder API (network; results cached in `data_england/contracts_cache/`).
4. `site/build.py` — bake `site/data.json`.
5. `site/build_search.py` — per-council indexes + `site/search_index_global.json`.
6. `site/verify.py` — preflight integrity suite; non-zero exit halts the run.

Flags: `--skip-fetch` (rebuild from existing `data_england/*.csv`), `--skip-contracts` (skip the slow Contracts Finder fetch).

**Scheduled refresh:** `.github/workflows/refresh.yml` (currently in the project dir — copy to the repo-root `.github/workflows/` to activate). It checks out the data repo and the nested site repo, runs the pipeline, and commits the refreshed `data.json` + `search_index*`. Needs a `DATA_REPO_TOKEN` secret.

**Still manual (no API):** the annual bulk releases (MHCLG RSX, ONS/Nomis profiles, DfE, Defra/OHID, DWP) that feed the existing panels. These change once a year; the best we can do without department APIs is a "new release?" watch that opens an issue.

---

Scoping note, not a build task. Question from Parth: "can we use APIs in the website
where possible, to make it more automatable?"

## The distinction that matters

"Use APIs in the website" splits into two very different things:

- **(A) Runtime** — the browser calls APIs live on page load, instead of reading a
  pre-baked `data.json`.
- **(B) Build-time** — the pipeline that *produces* `data.json` pulls from APIs
  automatically, instead of someone downloading files by hand, and re-runs on a
  schedule.

For this site, (B) is where the automatability win is. (A) is the wrong lever for
almost every panel, for concrete reasons below. The site is static (GitHub Pages,
no server), which shapes both answers.

## Why the core can't be runtime (A)

1. **Classification is a batch job.** "What they talk about" isn't a value you fetch;
   it's the output of downloading each council's meeting minutes and keyword-counting
   them against the taxonomy. That's seconds per council and hundreds of documents.
   It cannot happen per page load. It has to be pre-computed.
2. **CORS.** A static page can only call APIs that send `Access-Control-Allow-Origin`.
   Most of these gov sources don't (MHCLG, DESNZ, DfT are file downloads, not APIs at
   all). Anything without CORS needs a proxy, which means running a server, which
   defeats the point of a static site.
3. **Cadence vs. cost.** Live fetching only earns its complexity if the data changes
   often. Here almost nothing does: spend is annual, census is decadal, scorecard
   metrics are annual. Fetching them live buys near-zero freshness while adding
   latency and new failure modes to a currently bulletproof page.

So: keep the browser reading one static `data.json`. Make the *generation* of that
file automatic.

## Source-by-source

| Panel | Source | API? | Browser-fetchable (CORS)? | Changes | Verdict |
|---|---|---|---|---|---|
| What they talk about | Council Gateway (Poteris) | Yes (harvest.py uses it) | No + needs classification | rolling | **build-time only** |
| Where the money goes | MHCLG Revenue Outturn (RSX) | No, annual `.ods` | n/a | annual | build-time, file watch |
| Population / ethnicity / age | ONS Nomis | Yes (profile.py, demographics.py use it) | Historically yes | annual / decadal | build-time API (already) |
| Scorecard: Attainment 8 | DfE Explore Education Statistics | Yes (EES API) + bulk CSV | partial | annual | build-time API |
| Scorecard: CO2 | DESNZ GHG | No, annual CSV | n/a | annual | build-time, file watch |
| Scorecard: rent | ONS PIPR | bulk `.xlsx`, some ONS API | limited | monthly | build-time |
| Scorecard: crime | police.uk / Home Office | **police.uk has a CORS API** | plausibly yes | monthly | build-time; runtime candidate |
| Scorecard: congestion | DfT | No, `.ods` | n/a | annual | build-time, file watch |
| Party control / elections | Democracy Club | Yes (DC API) | plausibly yes | May elections | build-time API; runtime candidate |
| Read up on it | web search | No clean API | n/a | rolling | stays manual/curated |

Note the pattern: the fast-moving inputs (minutes, crime, elections) are exactly the
ones that either can't be classified in-browser (minutes) or sit behind niche APIs.
The slow-moving inputs are annual bulk files with no API at all.

## Recommended architecture (the automatability win)

Keep the static site. Automate the build.

**Phase 1 — one refresh entrypoint.** Wrap the existing source scripts behind a single
`refresh.py` that: pulls everything with an API (Nomis, Gateway, DfE EES, police.uk,
Democracy Club), downloads the annual bulk files where a URL is stable, then runs
`site/build.py`. This already half-exists; it's mostly consolidation and a manifest of
source URLs.

**Phase 2 — scheduled build.** A GitHub Action on a cron (monthly is plenty given the
cadences) runs `refresh.py` and commits the regenerated `data.json`. The site
self-updates with no server and no manual step. This is the standard pattern for a
data-backed static site and fits the current deploy (push to main).

**The residual manual touchpoints** are the three annual bulk releases with no API
(MHCLG RSX, DESNZ CO2, DfT congestion). Best we can do is a "has a newer release
dropped?" check that opens an issue when the department publishes, rather than fully
hands-off ingestion. Can't be removed until those departments ship APIs.

## Narrow runtime-API candidates (optional, later)

If we want a genuinely-live element for its own sake, two are cheap and CORS-friendly:

- **Next election / current control** from Democracy Club, fetched client-side with a
  graceful fallback to the baked value. Gives a live "control could change on [date]"
  line without a rebuild.
- **Latest month crime** from the police.uk API, same pattern.

Both are additive garnish, not a reason to move the core off the static model.

## Rough effort

- Phase 1 (`refresh.py` consolidation + source manifest): ~half a day.
- Phase 2 (GitHub Action cron + commit): ~an hour once Phase 1 is clean.
- Runtime garnish: ~half a day each, only if wanted.

## Bottom line

Don't put data fetching in the browser. Put it in a scheduled build. That makes the
site "automatable" in the sense meant, keeps it a zero-server static page, and leaves
only the three no-API annual downloads as human touchpoints.
