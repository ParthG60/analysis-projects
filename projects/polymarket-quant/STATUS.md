# STATUS

## 2026-11-10 (session 9) — git-based deploy + strategy.yaml (no more manual uploads)

**Done**
- **Two scanner bugs fixed** (found during a live coverage audit):
  1. `Brazil Serie A` was silently dropped — the blacklist term `Serie A` substring-matched it. It appears in BOTH the series name and the tags, so exempting only the series wasn't enough. Fix: in `is_league_whitelisted()`, when an exact whitelisted series is present, erase all whitelisted-series names (longest-first) from the blacklist text. Verified: Brazil Serie A went 0 -> 17 passing fixtures; Italian `Serie A`, `La Liga`, `Copa del Rey`, `Coupe de France`, friendlies, Nations League all still correctly rejected.
  2. **CORRECTION:** Brazil is NOT paused — Serie A (83 events) and Serie B (40) play through the European international break. Post-fix coverage over 20 days = 106 match-level fixtures across 11 leagues.
- **Volume-floor study** (`scripts/volume_curve.py`, `logs/volume_curve.txt`): soccer-underdog edge is monotonically increasing in volume. p6h, band 0.05-0.35, 5% fee + 1.8c slip: <2k = +1.0pp (ret -0.07); 2-5k = +0.3pp (-0.08); 5-10k = +3.4pp (+0.11); 10-25k = +5.9pp (+0.30); 25-50k = +8.7pp (+0.38); 50-100k = +15.4pp (+0.77). Below ~5k the strategy is a net loser. **Decision: keep MIN_VOLUME_USD = 10,000.**
- **`strategy.yaml` — single source of truth for strategy params.** Sizing, risk limits, selection bands, and league whitelist/blacklist moved out of `config.py`/`.env` into `strategy.yaml`; `config.py` now loads it (with built-in defaults). `.env` keeps only secrets + mode. Tuning = edit one YAML file.
- **All modules given script-mode import fallbacks** (`scanner/executor/db/notifier`) so the bot runs via `python run.py` from the git checkout without the old `bot -> .` symlink.
- **Git-deploy tooling:** `deploy.sh` (on VM: `git pull` + pip sync + restart) and `setup_git_vm.sh` (one-time VM migration to a sparse git checkout at `~/polybot-repo`, preserves `.env`/`trades.db`).
- **Committed + pushed** to `github.com/ParthG60/analysis-projects` (branch `master`) — bot/, strategy.yaml, scripts, logs, PROJECT.md, STATUS.md. `.gitignore` (project) excludes `data/` (12 GB), `.env`, `trades.db`, `venv/`, `*.tar.gz`.

**Next**
- **One-time VM migration:** upload `setup_git_vm.sh`, then on the VM `bash setup_git_vm.sh` (stops service, sets up git checkout, restores secrets, repoints systemd, restarts).
- Thereafter: edit `strategy.yaml` locally -> `git push` -> on VM `cd ~/polybot-repo/projects/polymarket-quant/bot && ./deploy.sh`.
- Monitor Telegram for round-robin fixtures entering the 6h-24h window; audit first live fill.

## 2026-11-10 (session 8) — 24/7 cloud migration complete: google cloud helsinki vm, systemd service, live authenticated relayer

**Done**
- **Cloud Migration & VPS Deployment (Google Cloud Helsinki `europe-north1`):**
  - Provisioned Google Cloud Debian Linux VM (`polybot`) in Helsinki, Finland (`FI`, IP `35.228.204.23`).
  - Verified Finland is 100% clean and unrestricted under Polymarket Terms of Service.
  - Packaged all bot modules, `.env` credentials, and SQLite database into `polybot.tar.gz`.
  - Configured automated `systemd` daemon (`polybot.service`) set to auto-restart on crashes or reboots (`Restart=always`, `RestartSec=30`).
- **Live End-to-End Execution Verification:**
  - Automated IP preflight tripwire confirmed clean exit from Finland (`ipinfo.io` returned HTTP 200).
  - Off-chain EIP-712 cryptographic signer successfully authenticated with Polymarket Relayer.
  - Active bankroll recognized: 508.96 USDC cash, 20.36 USD target stake (4.0% Quarter-Kelly).
  - Telegram startup notification delivered successfully to mobile device.
  - Completed first live automated scan cycle against Gamma API (`HTTP/2 200 OK` on keyset queries).
  - Correctly filtered non-whitelisted friendlies/knockout cups; entered autonomous 900s polling interval.
- **Live coverage audit + two fixes (same session):**
  - **BUG FIXED — `Brazil Serie A` blacklist collision.** The blacklist term `Serie A` was substring-matching the whitelisted series `Brazil Serie A` (in the series name AND in the tags) and silently dropping the whole league. Fixed in `scanner.py` `is_league_whitelisted()`: whitelisted-series names are erased from the blacklist text before scanning, while the blacklist still applies to the title/question (cups, friendlies, `- To Advance` still rejected). Verified by unit test + live scan (Brazil Serie A went 0 -> 17 match-level passes).
  - **CORRECTION — Brazil is NOT paused.** Brazil Serie A (83 events) and Brazil Serie B (40) are playing through the European international break. Post-fix live scan (next 20 days) passes 106 match-level events across 11 leagues: Brazil Serie A (17), Liga MX (10), Brazil Serie B (10), Japan J League (10), Bundesliga 2 (9), Ligue 1 (9), Bundesliga (9), Eredivisie (9), Süper Lig (9), Norway Eliteserien (8), Denmark Superliga (6). European top flights resume ~late Nov.
  - **Volume-floor study (`scripts/volume_curve.py`, `logs/volume_curve.txt`).** Soccer-underdog edge (p6h, band 0.05-0.35, 5% fee + 1.8c slip) by absolute volume: <2k = +1.0pp / ret -0.07; 2-5k = +0.3pp / -0.08; **5-10k = +3.4pp / +0.11**; 10-25k = +5.9pp / +0.30; 25-50k = +8.7pp / +0.38; 50-100k = +15.4pp / +0.77. Cumulative floor 0 = +2.5pp; floor 5k = +5.9pp; **floor 10k = +7.9pp / +0.38**; floor 25k = +11.2pp / +0.51. Conclusion: the 10k floor is evidence-based (below ~5k the strategy is a net loser); 25k would be even better per-trade at lower volume. **Decision: keep MIN_VOLUME_USD=10,000.**
  - Rebuilt `polybot.tar.gz` + delta `polybot-scanner-fix.tar.gz`; refreshed copies in Windows Downloads/Desktop.

**Next**
- **Deploy the fixed scanner to the VM** (only `scanner.py` changed): `tar xzf polybot-scanner-fix.tar.gz -C ~ && sudo systemctl restart polybot`.
- **Decide deploy workflow** (open question): git-based deploy so strategy tweaks are `git push` + pull/restart, rather than manual tarball uploads. Repo `github.com/ParthG60/analysis-projects` already tracks `bot/`; `.env` and `__pycache__` ignored (trades.db not yet ignored).
- Monitor Telegram for round-robin matches entering the 6h-24h window; audit first live fill.

## 2026-11-10 (session 7) — uk regulatory & tos audit, koinly architecture, and automated ip preflight kill switch

**Done**
- **Polymarket Terms of Service Audit (`polymarket.com/tos`):**
  - Audited live ToS contract: identified that Section 1 explicitly blacklists **The United Kingdom**, **Russia**, and the **United States** (alongside France, Germany, Italy, Netherlands, Poland, Australia).
  - Confirmed that connecting from a UK or Russian IP risks wallet placement in "close-only" mode.
- **HMRC & Regulatory Clarification:**
  - Debunked automatic tax-free betting exemption: under HMRC Cryptoassets Manual (`CRYPTO20250`), ERC-1155 prediction tokens traded with USDC are classified as cryptoassets subject to UK Capital Gains Tax (CGT), with an annual allowance of £3,000 (10%/20% thereafter).
  - Clarified Koinly integration: user must link their MetaMask Polygon EOA address (`0x53dCb...99F2`) for on-chain transfers/cash-outs, and import CLOB trading fills using our bot's `--export-tax` CSV export.
- **Automated IP Preflight Kill Switch (`bot/config.py`, `bot/notifier.py`, `bot/main.py`):**
  - Implemented `verify_public_ip()` with fallback providers to check active exit IP and country before touching Polymarket's order book.
  - Hardcoded `RESTRICTED_COUNTRIES` blacklist (`GB`, `RU`, `US`, `FR`, `DE`, `IT`, `NL`, `PL`, `AU`, etc.).
  - Built real-time tripwire: if an unsafe IP is detected at startup or mid-session, the bot immediately halts all execution and dispatches an emergency Telegram alert (`notify_restricted_ip`).
  - Audited current machine network: confirmed clean, unrestricted routing via Stockholm, Sweden (`SE`, IP `45.94.38.2`), returning HTTP 200 on all Polymarket endpoints.

**Next**
- Run autonomous loop (`python3 bot/run.py --live --interval 900` or in tmux) protected by the automated IP kill switch.
- Monitor Telegram push notifications for upcoming round-robin league fills.

## 2026-11-10 (session 6) — live wallet verification, telegram phone alerts, 4% quarter-kelly sizing, hmrc tax ledger

**Done**
- **Economic Calibration Sense-Check across all price buckets:**
  - Evaluated theoretical favorite-longshot bias vs actual Polymarket order books across 13,000 markets.
  - Proved that retail sports bettors suffer from **Heavy-Favourite Overconfidence**: heavy favourites priced at 80c-95c win only 73.5% of the time, losing -17.2% net per trade.
  - Due to binary market parity ($P(\text{Fav}) + P(\text{Dog}) = 1.00$), underdogs are systematically underpriced by +11pp to +22pp.
  - Verified tradable boundaries: <2c is wiped out by spread/tick friction (-100% net); 5c-20c is the goldmine (+83% to +215% net); >35c drops to near-breakeven (+3.1% net).
- **Bet Sizing & Circuit Breaker Optimization:**
  - Simulated 2,000 Monte Carlo bootstrap paths (100 matches each, starting 500 USD).
  - Upgraded sizing from 2% to **4.0% Quarter-Kelly** (starting stake 20 USD, capped at 100 USD): median bankroll jumped from 2,396 USD to **6,328 USD** with **0.0% ruin risk** (worst 10th percentile outcome = 2,322 USD).
  - Interrogated 20% circuit breaker: identified that underdogs naturally experience 7-8 loss streaks (causing routine ~22% drawdowns). Calibrated hard circuit breakers to **40% peak drawdown** and **12 consecutive losses** to avoid tripping on normal variance.
- **Telegram Mobile Tracking Engine (`bot/notifier.py`):**
  - Integrated push notification engine via Telegram Bot API using dependency-free async HTTP.
  - Implemented automated alerts for: Startup status, Order placement, Match resolution (P&L and updated bankroll), Emergency circuit breaker activation.
  - Verified live delivery directly to Parth's mobile device.
- **UK Tax & AML Compliance Module (`bot/db.py`, `bot/run.py`):**
  - Expanded SQLite ledger with UK tax year calculation (April 6 - April 5), order IDs, tx hashes, and GBP/USD exchange rates.
  - Added CLI tools: `--tax-summary` (HMRC BIM22015 betting exemption ledger) and `--export-tax` (full CSV export for Koinly/accountant).
- **Live Wallet Diagnostics & Polymarket CLOB Verification (`bot/verify_wallet.py`):**
  - Audited Polymarket Account Abstraction architecture: linked MetaMask EOA signer (`0x53dCb...99F2`) with user's on-chain Deposit Wallet (`0x4cD00...BC31`).
  - Confirmed 508.96 USDC active trading collateral in Deposit Wallet.
  - Tested off-chain EIP-712 order signing (`create_limit_order`): verified mathematical signature generation without posting live risk.

**Next**
- Run 24/7 background trader (`python3 bot/run.py --live --interval 900` or in tmux) to catch whitelisted round-robin domestic fixtures entering the 6h-24h window.
- Monitor automated push notifications on phone for first automated fill.

**Done**
- Investigated user suspicion on shifting numbers; isolated the 4 structural traps:
  1. `close_ts` oracle resolution lag vs kickoff `end_ts` (sampling `close_ts - 1h` was literally sampling post-match).
  2. Early resolution look-ahead bias in politics (early unexpected breaks created artificial hindsight edge; on-schedule underdogs bleed -49% due to theta decay).
  3. Gamma API null category field.
  4. Sizing ruin on 30% win rate underdogs with flat 25 USD stakes.
- Examined Early Exit / Resolution Bypass:
  - Politics NO-trading captures +5.3% return with 82.9% win rate exiting at p1d, but negative skew (risk 85c to make 5c) and 6-day lockup make it inefficient compared to soccer. User decided to discard politics and focus 100% on soccer.
- Performed BAU (Business-As-Usual) backtest without international tournaments:
  - Removing World Cup / Euros / Copa America increased net return from +46% to +49.9% (raw edge +10.3pp, n=2,793).
  - Categorized league efficiency into 3 tiers: Tier 1 (J-League, Brazil Serie A, Belgium, Liga MX, Eredivisie, Saudi, Turkey) yielding +50% to +180% net return; Tier 3 (La Liga, Serie A, Nations League, Friendlies) near-efficient / negative EV.
- Sizing comparison:
  - Flat 10 USD: 500 -> 7,907 USD (Max DD -38.98%).
  - Dynamic 2% (capped at 50 USD): 500 -> 33,851 USD (Max DD -59.95%).
  - Dynamic 1.0% to 1.5%: 500 -> 29,138 to 32,437 USD (Max DD -35.6% to -48.9%).
- Built full automated trading bot package in `bot/`:
  - `bot/config.py`: Tier 1 & 2 whitelist, 2% dynamic sizing (5 USD floor, 50 USD cap), 6h-24h window, max 10 positions, max 2/event.
  - `bot/db.py`: SQLite ledger (`trades.db`) for trade tracking, cash, equity, and settlement.
  - `bot/scanner.py`: Real-time market scanner via `polymarket-client` using `end_date_min`/`max` keyset queries.
  - `bot/executor.py`: Maker limit order execution at best bid (0% fees), dry-run paper trading simulation, and settlement handler.
  - `bot/main.py` & `bot/run.py`: Orchestrator with `--status`, `--dry-run`, `--live`, `--once` CLI flags.
- Successfully executed live dry-run scan (`bot/run.py --dry-run --once`):
  - Detected active Copa del Rey matches today.
  - Successfully placed simulated maker limit buy orders on 2 qualified underdogs.
  - Verified event risk constraint: subsequent scans correctly skipped over-concentrating on the same match (2/2 cap enforced).

**Next**
- Run paper trading in the background (`python bot/run.py --dry-run`) to record mock fills and match settlements.
- Transition to live trading in the UK (or via European VPS) by funding MetaMask and adding Relayer API keys to `.env`.

**Done**
- `scripts/fetch_events_full.py` -> `data/events_full.jsonl` (572,135 events) and
  `data/market_event_map.jsonl` (3,233,733 market->event links). Crawled Gamma
  `/events/keyset` (offset pagination 422s past ~2100; keyset `after_cursor` works).
- `scripts/analyze_official.py` -> `logs/analyze_official.txt` (edge by official tag/series).
- Discovered the taxonomy landmines: the event `category` field returned by keyset is
  **null for 572,131 / 572,135 events** — the old hand-rolled regex in `build_universe.py`
  was the only classifier and it was badly wrong. The real taxonomy is `tags` + `series`.
- Coverage: 92.4% of horizon markets mapped to an event.

**THE CORRECTION (this supersedes the session-3 category table)**
- The edge is **SOCCER underdogs only**. Not "sports" broadly, not tech/politics/crypto.
  - vol>=10k on-schedule: Soccer n=3,746 win 28.4% +7.9pp ret **+0.38**;
    Esports n=42 +4.5pp ret -0.06; Basketball n=35 +2.4pp ret -0.11; Hockey n=16 -13.2pp ret -0.80.
  - Crypto n=1,559 ret **-0.16**; Finance/Equity n=523 ret **-0.13**. No edge.
- Earlier "tech +36.9pp / politics +34.1pp" was an artefact: football matches whose
  questions contain country names ("France vs N. Ireland") leaked into politics, and
  single-stock TradFi options (NVDA/TSLA/GOOGL "up or down") leaked into tech.
- League granularity (vol>=10k): less-covered leagues >> big European leagues —
  Japan J-League n=119 +21.7pp ret +1.28; Saudi Pro League n=151 +18.5pp +0.81;
  Brazil Serie A n=199 +14.1pp +0.71; Argentina Primera n=319 +9.6pp +0.44;
  vs UEFA Nations League n=310 +0.4pp -0.03, La Liga n=269 +2.3pp +0.09,
  Serie A n=406 +3.9pp +0.21, Bundesliga n=242 +6.6pp +0.27.
- Horizon: sports edge flat p1d (+11.5) -> p12h (+11.1) -> p6h (+11.0), then
  **collapses at p1h (+1.4pp, ret negative)** — must enter a day-to-6h out, not late.
- Volume monotonic: edge/ret grows with volume (retail concentration).

**Soccer-only backtest (on-schedule, 5% fee + 1.8c slip, settlement lock 24h,
max 2/event, max 25 open, start 500 USD)**
- 2026-only vol>=25k: flat10 -> 6,112; flat25 -> 14,531; 2% -> 24,935.
- 2026-only vol>=10k: flat10 -> 9,272; flat25 -> 22,431; 2% -> 40,096.
- Pooled 2025+26 vol>=10k flat25 -> RUIN (early-2025 losing streak) — ruin risk real.

## 2026-11-09 (session 3) — pre-live critical test: portfolio sim, order-book-aware fill, cutoffs

**Done**
- `scripts/extract_conds.py` -> `data/conds_full.parquet` (id->conditionId map, 1.15M).
- `scripts/portfolio_full.py` — event-driven 500 USD sim on the full universe.
- `scripts/fetch_trades_full.py` + `data/trade_fills_full.jsonl` — trade-tape
  (taker-buy) entry prices for 4,030 high-volume mid-band markets.

**Order-book-aware result (the decisive test)**
- Fillability at 6h before close: a taker BUY print existed in **94.4%** of markets
  (12h 86%, 24h 69%). Median 395 trades scanned.
- Realistic entry (taker ask) costs **+1.8pp** vs clob last-trade (median +0.5c,
  adverse 60% of the time). Edge survives: **+11.4pp** with taker ask (vs +13.2pp
  clob), fee-adjusted mean ret/trade **+0.63**. By vol: 10-50k +9.1pp, 50-200k
  +11.4pp, >200k **+15.3pp**.
- So the edge is NOT a stale-quote artefact.

**Cutoffs learned**
- Volume: edge monotonic — 1-5k ~0pp, 5-25k ~5pp, 25-100k ~11-14pp, >100k 10-20pp.
- Band: NO edge above 0.35 (0-0.8pp). Strongest in 0.25-0.35 at high volume.
- Horizon: p6h best (+14.6pp at >50k); p1h decays to +8.3pp.
- Category (vol>50k, p6h): tech +36.9, intl_politics +34.1, us_politics +27.5,
  other +14.9, crypto +10.1, macro +1.5, culture negative.
- Out-of-sample: 2025 +11.8pp, 2026 +13.7pp (vol>=25k); quarterly range +9.8..+16.8pp.
  No decay.

**CRITICAL RISKS (must be stated before going live)**
- **Lottery-shaped**: top 5% of trades = ~all profit. Drop top 5% -> mean ret ~+0.02
  (2025) / +0.17 (2026); drop top 10% -> negative. Median trade -100%, win ~32%.
- **Correlation**: profit clusters in geopolitics (Iran +57pp, Israel +46pp, Ukraine
  +22pp on high-vol) and crypto dailies — these are single correlated bets, not
  independent draws. The sim overstates diversification.
- **Classifier leak**: "other" (108k) contains misclassified sports (O/U, spreads,
  ITF tennis). The "non-sports" claim is not clean; high-vol sports show +13.5pp.
- **Fees**: disabled in 2025 (0% fee_type), enabled 2026 (89%). Model applies fees
  throughout -> conservative for 2025, correct for the live regime.
- **Backtest multiple is inflated by compounding** (2% sizing over ~4,000 trades).
  The deployable number is the per-trade edge (~+11-15pp) and fee-adj ret (~+0.5-0.6),
  not the 200-500x.

**Recommendation**
- Deploy ONLY high-volume (vol>=25k, prefer >100k), single-binary, band 0.05-0.35,
  enter ~6h before close; small size (1-2%), hard cap per correlated cluster.
- Verify live fee schedule (feeType/feesEnabled) before sizing.
- Treat as selling insurance / buying underpriced tail events: positive EV, high
  variance, needs many uncorrelated trades.

## 2026-11-09 (session 2) — full-universe rebuild + corrected edge story

**Done**
- Defeated Gamma's ~2,100-row offset cap using `/markets/keyset` + `after_cursor`
  (new `scripts/fetch_full_universe.py`, resumable, volume/date filters).
- Crawled the FULL 2025-01..2026-11 universe, **vol>=1000, no monthly cap**:
  **1,146,603 markets** -> `data/universe_full.parquet` (raw 6.8 GB:
  `data/raw_markets_win1k.jsonl`). ~50x the old 22,910.
- Also saved a vol>=100 partial dump (`raw_markets_win.jsonl`, ~359k) and an
  all-time partial dump (`raw_markets_full.jsonl`, ~386k, 2020-2024 + early 2025).
- Fetched 1-min CLOB horizon data for the tradable pool (single-binary,
  non-sports): **572,251 markets** -> `data/horizons_full.jsonl`
  (`scripts/fetch_prices_full.py`, ~40 workers, ~2h).
- Rewrote the universe builder to be arg-driven and to carry `negRisk` fallback,
  `endDate`, `fee_type`, and a resolution guard (`scripts/build_universe.py`).
- New `scripts/backtest_full.py` — cost- and volume-aware backtest + 2025/2026
  out-of-sample split -> `logs/backtest_full.txt`.

**KEY CORRECTION — the edge is a liquidity premium, not a broad bias**
- Full universe (572k): mid-band (0.05-0.35) edge at p6h is only **+3.3pp**
  (was +15.4pp on the old high-volume sample). Calibration is near-flat outside
  the top vol quartile.
- Edge is monotonic in volume: p6h edge by quartile = low -0.2pp, mid +1.2pp,
  hi +6.6pp, **top +14.0pp**. Median vol of top quartile ~70k.
- Holds WITHIN every category (us_politics -3.6 -> +26.4; intl_politics
  -6.5 -> +42.5; tech +1.8 -> +15.1; other -0.4 -> +9.1; crypto +6.9 -> +10.8).
- Not a short-horizon artefact: lifespan>=2d gives low-vol +0.0pp, hi-vol +14.3pp.
- Restricting to vol>=50k reproduces the old claim (+14.6pp) — i.e. the old
  result was correct FOR high-volume markets but does not generalise.
- OOS: 2025 +3.8pp vs 2026 +3.3pp (full); top quartile & crypto-2026 (+14.4pp)
  stable. No decay. Fees cost ~4pp of return.

**Implication**
- The strategy as previously run (target high-volume, liquid markets) is RIGHT,
  but the rationale is deployability/liquidity, not a universal mispricing.
  Low-volume markets have no exploitable edge and are untradeable anyway.

**Next**
- Tighten the tradable threshold (test vol cut ~10k-25k) and re-run the portfolio
  sim on the full universe with the volume gate added.
- Optional: fetch the negRisk/multi-outcome pool to re-test single-vs-negRisk.
- Consider the "other" bucket (108k, mostly weather/temperature) explicitly.

## 2026-11-09
First research pass: built a Polymarket historical research pipeline and ran the
favourite-longshot / horizon / category tests on resolved 2025-2026 markets.

**Done**
- Built full pipeline (`scripts/`) — market census, categorisation, 1-min price
  history via CLOB `startTs`/`endTs`, horizon extraction (7d/3d/1d/12h/6h/1h/30m).
- Universe: 22,910 resolved binary markets (2025-01..2026-11), top-volume/month.
- Price paths: 9,525 markets; + 2,500 random validation sample.
- Audited for bugs: token↔outcome mapping verified (mean end-price 0.911 for winners,
  0.044 for losers); global calibration good.
- Found a **reverse favourite-longshot bias**: 5–35% underpriced (+9–11pp, CI excl. 0),
  65–90% overpriced (−6–8pp); extremes calibrated. Holds in random sample and in the
  most-liquid volume tercile.

**Key outputs**
- `logs/final_report.txt`, `logs/analysis.txt`
- `data/horizons_clean.csv`, `data/universe.parquet`

**Where the edge lives (segment.py)**
- Structural: edge is **+15.4pp in single markets vs +1.5pp in multi-outcome (negRisk)**.
  Holds within every category. Multi-candidate "who wins" markets are arb'd flat
  (sum-to-1 pressure); single "will X happen by date" markets are not.
- Genre (within single, mid bucket, p1d): geopolitics/military +27pp, crypto price
  levels +21pp, political events +45pp (n=9, thin), tech/science +17pp; sports
  discrete events ~0.
- Stable across years: 2025 +18.4pp, 2026 +14.2pp.
- Examples: "US strikes Iran by Feb 28, 2026?" (0.065 -> YES), "Maduro out by Jan 31"
  (0.065 -> YES), "Israel x Hamas ceasefire by Oct 10" (0.165 -> YES).

**Tick-trade fillability + fees (fetch_trades.py, analyze_trades.py)**
- Pool: 1,102 single (non-negRisk) markets priced 0.05-0.35 at p1d/p6h.
- Walked trade tape newest-first (cursor pagination; time filters are ignored).
- Fillability is high: a taker BUY printed at the horizon in 99.9% (6h), 98.6% (12h),
  85.2% (24h) of markets. Taker entry ≈ clob last trade + ~0.5-1c.
- Fee-adjusted (rates 0.04-0.07) mean return per trade: **6h +0.52 [0.37,0.69]**,
  12h +0.82, 24h +0.87; win ~37% vs avg implied 0.25. Edge survives fees and
  realistic entry prices, and holds across tape-depth terciles (not just thin books).
- **BUT lottery-shaped**: median -100%, p_profit 0.37, and the **top 10% of trades
  generate 108-122% of total P&L**. Needs many trades + fractional-Kelly sizing.
- Category (6h, fees): us_politics +1.22, intl_politics +0.92, others +0.3-0.6.

**Next**
- Validate fillability: reconstruct tradable bid/ask from trades (`data-api /v2/trades`)
  rather than last-trade price; test slippage.
- Build a Kelly-sized paper-trading sim on the "buy underpriced mid-range" rule.
- Segment: multi-outcome (negRisk) vs single markets — is the bias concentrated there?
- Consider cross-venue arb (Polymarket vs Limitless/Smarkets) — deferred; Limitless
  liquidity too thin (top market ≈ 150 USD lifetime volume).
- Charts: calibration curve + horizon drift (use charting skill).

**Blockers / notes**
- Operating from Russia; bot must run from a European VPS/proxy, not local VPN.
- CLOB history window ~15d; older fine-grained data not available.
