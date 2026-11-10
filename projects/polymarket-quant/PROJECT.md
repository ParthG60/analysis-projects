# Polymarket Quant Research

## Question
Can a small (~500 USD), high-risk-tolerant bankroll extract mispricing from Polymarket
(and/or other prediction venues) using quantitative strategies? Focus: favourite–longshot
bias, horizon effects, and which market pools are most exploitable.

## Data / sources
- **Gamma API** (market metadata, resolution, volume): `gamma-api.polymarket.com`
- **CLOB API** (1-minute price history): `clob.polymarket.com/prices-history`
- Scope: resolved binary markets closing **2025-01 .. 2026-11**.
- **Full universe (session 2)**: 1,146,603 markets, vol>=1000, uncapped
  (`data/universe_full.parquet`; raw 6.8 GB `raw_markets_win1k.jsonl`).
  Price paths for 572,251 single-binary non-sports markets (`horizons_full.jsonl`).
- Legacy sample (session 1): top ~1,000-by-volume/month (22,910 markets).

## Key API facts discovered
- CLOB `prices-history` accepts `startTs`/`endTs` and `fidelity` (minutes) and retains
  history for any resolved market — **max window ~15 days**, so we fetch the final 14d.
- Gamma `/markets` **offset pagination hard-caps at ~2,100 rows** (returns
  `"use /markets/keyset for deeper pagination"`). Use `/markets/keyset` with the
  `after_cursor` token (response field `next_cursor`) for full enumeration; it also
  accepts `end_date_min/max` and `volume_num_min`. Page `limit` caps at 100.
- `feeType` is now populated on most markets (`crypto_fees_v2`, `sports_fees_v3`,
  `politics_fees`, ...); legacy markets have null (historically zero-fee).

## Key findings (2025-2026)

### CORRECTED via official taxonomy (session 4) — read this first
- Polymarket's event `category` field is **null for essentially all events** (572,131/572,135)
  returned by `/events/keyset`. The authoritative classification is **`tags` + `series`**.
  Crawl: `data/events_full.jsonl` (572k) + `data/market_event_map.jsonl` (3.2M links).
  The old regex in `build_universe.py` was the sole classifier and was badly wrong.
- **The tradable edge lives in SOCCER underdogs (official tag `Soccer`), and only there.**
  On-schedule, vol>=10k, band 0.05-0.35: Soccer n=3,746 win 28.4% **+7.9pp** ret **+0.38**;
  Esports ret -0.06; Basketball ret -0.11; Hockey ret -0.80; Crypto (n=1,559) ret -0.16;
  Finance/Equity (n=523) ret -0.13. Fee-adjusted, only soccer survives.
- The session-3 "tech +36.9pp / intl_politics +34.1pp" was an artefact: football matches
  with country names leaked into politics; single-stock TradFi options leaked into tech.
- **League granularity**: thin-coverage leagues carry the edge — Japan J-League +21.7pp
  (ret +1.28), Saudi Pro League +18.5 (+0.81), Brazil Serie A +14.1 (+0.71), Argentina
  +9.6 (+0.44); big European leagues are near-efficient — UEFA Nations League +0.4pp,
  La Liga +2.3pp, Serie A +3.9pp, Bundesliga +6.6pp.
- **Horizon must be early**: soccer edge flat +11.5pp (p1d) -> +11.0pp (p6h), then
  collapses to +1.4pp at p1h (negative net). Enter 1d-6h before kickoff.
- Backtest (on-schedule, 5% fee + 1.8c slip, 24h settlement lock, max 2/event): 2026-only
  vol>=25k flat10 -> 6.1k, flat25 -> 14.5k, 2% -> 24.9k USD; vol>=10k 2% -> 40.1k.
  Pooled 2025+26 flat25 RUINs on an early-2025 streak (cluster/ruin risk).
- **BAU Club Backtest & Dynamic Sizing (session 5)**:
  Excluding international tournaments (World Cup / Euros / Nations League) raises edge to
  +10.3pp and net return to +49.9% (n=2,793). Flat 10 USD grew 500 -> 7,907 USD (Max DD -39%).
  Dynamic 2% sizing with 5 USD floor and 50 USD cap grew 500 -> 33,851 USD (Max DD -60%).
  Live execution bot built in `bot/` using official `polymarket-client` SDK and verified in dry-run.
- **Evidence-based volume floor (session 8)** (`scripts/volume_curve.py`): soccer underdog edge
  is monotonically increasing in traded volume. At p6h (band 0.05-0.35, 5% fee + 1.8c slip):
  <2k = +1.0pp (ret -0.07), 2-5k = +0.3pp (-0.08), 5-10k = +3.4pp (+0.11), 10-25k = +5.9pp
  (+0.30), 25-50k = +8.7pp (+0.38), 50-100k = +15.4pp (+0.77). Below ~5k the strategy is a net
  loser, so **MIN_VOLUME_USD = 10,000 is justified**; 25k would improve per-trade return at
  reduced volume. Koinly/bot live deployment on GCP Finland; see STATUS sessions 7-8.

### Legacy (sessions 1-3)
- **The reverse favourite-longshot edge is a LIQUIDITY PREMIUM, not a broad bias.**
  On the full universe the 5-35% mid-band edge at 6h before close is only **+3.3pp**
  (was +15.4pp on the old high-volume sample). Calibration is flat away from the top
  volume quartile.
- Edge is **monotonic in volume** (p6h): q1 -0.2pp, q2 +1.2pp, q3 +6.6pp,
  **q4 +14.0pp** (median vol ~70k). Holds within every category.
- Restricting to vol>=50k reproduces the old +14.6pp — the old result was correct
  *for high-volume markets* but does not generalise to the long tail.
- Not a short-horizon artefact: lifespan>=2d gives low-vol +0.0pp / hi-vol +14.3pp.
- Out-of-sample stable: 2025 +3.8pp, 2026 +3.3pp (full universe); no decay.
  Fees cost ~4pp of return. Extreme longshots (<5%) and near-certainties are
  well-calibrated; the 35-65% middle is flat.
- Genre (within single, high-volume): intl_politics +42pp, us_politics +26pp,
  tech +15pp, crypto +11pp (all top-quartile, p6h).
- Payoffs are right-skewed lotteries: win rate ~21% vs implied ~18%, median -100%.


## Caveats / open risks
- No historical order book → "price" is last trade; fillability/slippage unverified.
- No fees/slippage modelled (Polymarket taker fees 0.04–0.07 rate, zero on geopolitics).
- Paper-trade required before capital deployment.

## Architecture
```
scripts/
  fetch_markets2.py   # monthly, volume-ranked census -> data/raw_markets.jsonl
  build_universe.py   # parse/classify/categorise -> data/universe.parquet
  fetch_prices.py     # 14d 1-min CLOB history, horizon extraction -> data/horizons.jsonl
  analyze.py          # calibration, strategies, category profiles
  rand_check.py       # random-sample validation
  final_report.py     # consolidated results with bootstrap CIs
  diag.py             # mapping / alignment audit
```
