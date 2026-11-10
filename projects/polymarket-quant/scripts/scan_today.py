"""Live scanner: which currently-open Polymarket markets meet our strategy criteria?

Pulls active markets from the Gamma API, classifies them with the same regex
classifier used to build the historical universe, then applies the strategy
filters (single binary, price band, time-to-end window, category tiers,
no equities) and prints the candidates with an expected-edge estimate.

Usage:
    python scripts/scan_today.py                 # default window 6-24h
    python scripts/scan_today.py --min-h 4 --max-h 48
    python scripts/scan_today.py --max-ask 0.40 --include-sports
    python scripts/scan_today.py --json out.json

Notes
-----
- Only the Gamma API is used (clob.polymarket.com is Cloudflare-blocked from
  some networks, including this dev box in Russia). Gamma returns bestAsk/bestBid
  directly, which is all we need for discovery.
- Run this from a Europe/US VPS in production; Russian IPs are OFAC-blocked.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GAMMA = "https://gamma-api.polymarket.com/markets"
HORIZONS = ROOT / "data" / "horizons_clean.csv"

# --- category classifier (identical logic to build_universe.py) --------------
CATS = [
    ("crypto", r"\b(bitcoin|btc|ethereum|eth|xrp|dogecoin|doge|solana|\bsol\b|bnb|cardano|memecoin|token|defi|nft|stablecoin|coinbase|binance|microstrategy|satoshi)\b"),
    ("us_politics", r"\b(president|presidential|senate|senator|house|congress|congressional|governor|scotus|supreme court|cabinet|democrat|republican|\bgop\b|trump|biden|harris|electoral college|speaker|impeach|midterm|primary|nominee|inaugur)\b"),
    ("macro_finance", r"\b(fed|federal reserve|fomc|cpi|inflation|gdp|interest rate|rate cut|rate hike|recession|jobs report|nonfarm|unemployment|s&p|nasdaq|dow|treasury|yield|wti|brent|crude oil|oil price|natural gas|gold price|silver price|commodity)\b"),
    ("us_sports", r"\b(nba|nfl|mlb|nhl|ncaa|ncaab|ncaaf|ufc|wnba|super bowl|world series|stanley cup|march madness|playoff|mvp|draft|afc|nfc|quarterback|touchdown)\b"),
    ("football", r"\b(premier league|champions league|la liga|serie a|bundesliga|ligue 1|world cup|europa league|soccer|real madrid|barcelona|uefa|fifa|fc\b|cf\b)\b"),
    ("esports", r"\b(league of legends|cs2|counter-strike|dota|valorant|esports|gaming)\b"),
    ("tennis", r"\b(tennis|atp|wta|grand slam|wimbledon)\b"),
    ("intl_politics", r"\b(uk|britain|british|parliament|prime minister|france|french|germany|german|india|indian|china|chinese|xi jinping|israel|iran|russia|putin|ukraine|zelensky|ceasefire|war\b|nato|election in|referendum|eu\b|european union|modi|macron|labour|tory)\b"),
    ("culture", r"\b(oscar|academy award|grammy|emmy|box office|album|taylor swift|celebrity|movie|film|billboard|netflix|spotify|golden globe|eurovision)\b"),
    ("tech", r"\b(openai|chatgpt|\bgpt\b|artificial intelligence|\bai\b|anthropic|claude|gemini|apple|google|meta|microsoft|tesla|spacex|starlink|launch|chip|semiconductor|nvidia)\b"),
    ("science_space", r"\b(nasa|space|rocket|mars|moon|asteroid|climate|hurricane|weather|temperature|earthquake|volcano|science)\b"),
    ("geopolitics", r"\b(conflict|sanction|treaty|invasion|military|missile|nuclear|hostage|border)\b"),
]
TICKER_CATS = {
    "us_sports": {"nba", "mlb", "nhl", "nfl", "cfb", "cbb", "ncaab", "ncaaf", "wnba", "ufc", "mls", "f1", "nascar", "ncaa", "cws"},
    "tennis": {"atp", "wta", "tennis"},
    "football": {"epl", "ucl", "uel", "fifwc", "laliga", "seriea", "bundesliga", "ligue1", "concacaf", "copa", "euro"},
    "esports": {"lol", "cs2", "dota2", "valorant", "cod", "ow", "rl"},
    "crypto": {"bitcoin", "ethereum", "btc", "eth", "solana", "xrp", "dogecoin", "doge", "bnb", "crypto", "microstrategy"},
}
SPORTS = {"us_sports", "tennis", "esports", "football"}
TIER1 = {"intl_politics", "us_politics", "geopolitics", "macro_finance"}
TIER2 = {"crypto", "tech", "culture", "science_space", "other"}

# single-stock / equity filter — the user wants these excluded
EQUITY_RE = re.compile(
    r"(market cap|stock price|share price|earnings|ipo\b|s&p 500|nasdaq-100|"
    r"\b(apple|tesla|nvidia|microsoft|amazon|alphabet|meta platforms|"
    r"berkshire|jpmorgan|goldman|netflix stock)\b)",
    re.I,
)

# historical taker fee rates by category (used in the backtests)
FEE_RATE = {
    "crypto": 0.07, "tennis": 0.05, "us_sports": 0.05, "esports": 0.05,
    "football": 0.05, "us_politics": 0.04, "intl_politics": 0.04,
    "macro_finance": 0.04, "tech": 0.04, "geopolitics": 0.00,
}


def categorize(question: str, ticker: str) -> str:
    tk = (ticker or "").strip().lower()
    pref = tk.split("-")[0]
    for name, prefs in TICKER_CATS.items():
        if pref in prefs:
            return name
    text = f"{question or ''} {ticker or ''}".lower()
    # head-to-head matchups (team vs team) are almost always sport/esport
    if re.search(r"\bvs\.?\b", text) and re.search(
        r"\((w|m)\)|\b(game|match|series|map|nba|nfl|mlb|nhl|ncaa|college|cup|open|league|esports|lol|cs2|dota|valorant)\b",
        text,
    ):
        return "us_sports"
    for name, pat in CATS:
        if re.search(pat, text):
            return name
    return "other"


def tier_of(cat: str) -> int:
    if cat in TIER1:
        return 1
    if cat in TIER2:
        return 2
    return 3


# --- empirical calibration lookup from our backtest --------------------------
def build_calibration() -> dict:
    """group -> list of (lo, hi, win_rate) from horizons_clean.csv at 12h."""
    try:
        import pandas as pd
    except ImportError:
        return {}
    if not HORIZONS.exists():
        return {}
    df = pd.read_csv(HORIZONS)
    df["id"] = df["id"].astype(str)
    u_path = ROOT / "data" / "universe.parquet"
    if u_path.exists():
        u = pd.read_parquet(u_path)
        u["id"] = u["id"].astype(str)
        df = df.merge(u[["id", "neg_risk"]], on="id", how="left")
    else:
        df["neg_risk"] = True
    df = df.dropna(subset=["p12h"]).copy()
    df = df[df["neg_risk"] == False]  # noqa: E712

    def grp(cat):
        if cat in TIER1:
            return "tier1"
        if cat in {"crypto", "tech"}:
            return "tier2"
        if cat in SPORTS:
            return "sports"
        return "other"

    df["grp"] = df["category"].map(grp)
    edges = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.45, 0.55, 0.70, 1.0]
    df["bin"] = pd.cut(df["p12h"], bins=edges)
    out = {}
    for g, gg in df.groupby("grp"):
        rows = []
        for b, gb in gg.groupby("bin", observed=True):
            if len(gb) >= 8:
                rows.append((float(b.left), float(b.right), float(gb["resolved0"].mean()), len(gb)))
        out[g] = rows
    return out


def model_winrate(cal: dict, cat: str, ask: float):
    if cat in TIER1:
        g = "tier1"
    elif cat in {"crypto", "tech"}:
        g = "tier2"
    elif cat in SPORTS:
        g = "sports"
    else:
        g = "other"
    for lo, hi, wr, n in cal.get(g, []):
        if lo <= ask < hi:
            return wr, n, g
    return None, 0, g


def fetch_active(min_h: float, max_h: float, pages: int = 8):
    now = datetime.now(timezone.utc)
    lo = (now + timedelta(hours=min_h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (now + timedelta(hours=max_h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sess = requests.Session()
    sess.headers.update({"User-Agent": "research/1.0"})
    seen, rows = set(), []
    for off in range(0, pages * 100, 100):
        params = {
            "closed": "false", "active": "true", "limit": 100, "offset": off,
            "end_date_min": lo, "end_date_max": hi,
            "order": "volume24hr", "ascending": "false",
        }
        for attempt in range(4):
            try:
                r = sess.get(GAMMA, params=params, timeout=25)
                if r.status_code == 200:
                    page = r.json()
                    break
                if r.status_code == 429:
                    import time as _t; _t.sleep(2 * (attempt + 1)); continue
            except Exception:
                import time as _t; _t.sleep(1.5 * (attempt + 1))
        else:
            break
        if not page:
            break
        for m in page:
            if m.get("id") in seen:
                continue
            seen.add(m.get("id"))
            rows.append(m)
        if len(page) < 100:
            break
    return rows


def parse(m, now):
    try:
        outs = json.loads(m.get("outcomes") or "[]")
        toks = json.loads(m.get("clobTokenIds") or "[]")
        prices = json.loads(m.get("outcomePrices") or "[]")
    except Exception:
        return None
    if len(outs) != 2 or len(toks) != 2 or len(prices) != 2:
        return None
    ev = (m.get("events") or [{}])
    ticker = (ev[0].get("ticker") if ev else None) or ""
    try:
        end = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
    except Exception:
        return None
    hours = (end - now).total_seconds() / 3600
    ask = m.get("bestAsk")
    bid = m.get("bestBid")
    try:
        ask = float(ask)
    except (TypeError, ValueError):
        return None
    return {
        "id": m.get("id"),
        "slug": m.get("slug"),
        "question": m.get("question"),
        "category": categorize(m.get("question"), ticker),
        "neg_risk": bool(m.get("negRisk")),
        "ask": ask,
        "bid": float(bid) if bid is not None else None,
        "yes_price": float(prices[0]),
        "hours": round(hours, 1),
        "end": end.strftime("%Y-%m-%d %H:%M"),
        "vol24": float(m.get("volume24hr") or 0),
        "liq": float(m.get("liquidityNum") or 0),
        "fees": m.get("feeType"),
        "accepting": bool(m.get("acceptingOrders")),
        "spread": m.get("spread"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-h", type=float, default=6.0)
    ap.add_argument("--max-h", type=float, default=24.0)
    ap.add_argument("--min-ask", type=float, default=0.05)
    ap.add_argument("--max-ask", type=float, default=0.35)
    ap.add_argument("--min-vol24", type=float, default=250.0)
    ap.add_argument("--min-liq", type=float, default=250.0)
    ap.add_argument("--pages", type=int, default=40)
    ap.add_argument("--include-sports", action="store_true")
    ap.add_argument("--include-negrisk", action="store_true")
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    raw = fetch_active(args.min_h, args.max_h, pages=args.pages)
    print(f"Active markets ending in {args.min_h:.0f}-{args.max_h:.0f}h: {len(raw)}")

    cal = build_calibration()
    parsed = [p for p in (parse(m, now) for m in raw) if p]

    funnel = {"pulled": len(parsed)}
    drops = {"not_accepting": 0, "neg_risk": 0, "sports": 0, "equity": 0, "price_band": 0, "low_volume": 0}
    stage = []
    for p in parsed:
        if not p["accepting"]:
            drops["not_accepting"] += 1; continue
        if not args.include_negrisk and p["neg_risk"]:
            drops["neg_risk"] += 1; continue
        if not args.include_sports and p["category"] in SPORTS:
            drops["sports"] += 1; continue
        if EQUITY_RE.search(p["question"] or ""):
            drops["equity"] += 1; continue
        if not (args.min_ask <= p["ask"] <= args.max_ask):
            drops["price_band"] += 1; continue
        if p["vol24"] < args.min_vol24 or p["liq"] < args.min_liq:
            drops["low_volume"] += 1; continue
        stage.append(p)
    funnel["passed"] = len(stage)

    rows = []
    for p in stage:
        wr, n, grp = model_winrate(cal, p["category"], p["ask"])
        fee = FEE_RATE.get(p["category"], 0.04)
        cost = p["ask"] + fee * p["ask"] * (1 - p["ask"])
        edge = (wr - cost) * 100 if wr is not None else None
        ev = (wr / cost) if (wr is not None and cost > 0) else None
        p2 = dict(p, wr=wr, n_hist=n, edge=edge, ev=ev, tier=tier_of(p["category"]), cost=cost)
        rows.append(p2)

    # rank by expected edge (then EV)
    rows.sort(key=lambda r: (r["edge"] if r["edge"] is not None else -99), reverse=True)

    print(f"Funnel: {funnel['pulled']} pulled -> {funnel['passed']} passed all filters")
    print("  dropped: " + ", ".join(f"{k}={v}" for k, v in drops.items() if v))
    print()
    if not rows:
        print("No markets meet the criteria in this window. Try --max-h 48 or --max-ask 0.40.")
        return

    hdr = f"{'tier':>4} {'cat':<14} {'end(h)':>6} {'ask':>6} {'spread':>6} {'histWR':>7} {'edge':>6} {'EV':>5} {'vol24':>9}  question"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        wr = f"{r['wr']*100:.0f}%" if r["wr"] is not None else "  -"
        edge = f"{r['edge']:+.0f}pp" if r["edge"] is not None else "   -"
        ev = f"{r['ev']:.2f}" if r["ev"] is not None else "  -"
        sp = f"{r['spread']}" if r["spread"] is not None else "-"
        print(f"{r['tier']:>4} {r['category']:<14} {r['hours']:>6.1f} {r['ask']:>6.2f} {sp:>6} {wr:>7} {edge:>6} {ev:>5} {r['vol24']:>9,.0f}  {r['question'][:64]}")

    print(f"\n{len(rows)} candidates. (histWR = realized win-rate of this price bucket in our backtest at 12h; edge = histWR - fee-adjusted cost.)")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2, default=str))
        print(f"Wrote {args.json}")


if __name__ == "__main__":
    main()
