"""Build a clean market universe table from a raw markets NDJSON dump.

Output: data/universe.parquet (default) or --out

Usage:
  python3 scripts/build_universe.py --raw data/raw_markets_win.jsonl --out data/universe_full.parquet
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_markets.jsonl"
OUT = ROOT / "data" / "universe.parquet"

# --- category classifier (regex on question + event ticker/slug) -------------
CATS = [
    ("crypto", r"\b(bitcoin|btc|ethereum|eth|xrp|dogecoin|doge|solana|\bsol\b|bnb|cardano|memecoin|token|defi|nft|stablecoin|coinbase|binance|microstrategy|satoshi)\b"),
    ("us_politics", r"\b(president|presidential|senate|senator|house|congress|congressional|governor|scotus|supreme court|cabinet|democrat|republican|\bgop\b|trump|biden|harris|electoral college|speaker|impeach|midterm|primary|nominee|inaugur)\b"),
    ("macro_finance", r"\b(fed|federal reserve|fomc|cpi|inflation|gdp|interest rate|rate cut|rate hike|recession|jobs report|nonfarm|unemployment|s&p|nasdaq|dow|treasury|yield)\b"),
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
    "us_sports": {"nba", "mlb", "nhl", "nfl", "cfb", "cbb", "ncaab", "ncaaf",
                  "wnba", "ufc", "mls", "f1", "nascar", "ncaa", "cws"},
    "tennis": {"atp", "wta", "tennis"},
    "football": {"epl", "ucl", "uel", "fifwc", "laliga", "seriea", "bundesliga",
                 "ligue1", "concacaf", "copa", "euro"},
    "esports": {"lol", "cs2", "dota2", "valorant", "cod", "ow", "rl"},
    "crypto": {"bitcoin", "ethereum", "btc", "eth", "solana", "xrp", "dogecoin",
               "doge", "bnb", "crypto", "microstrategy"},
}


def categorize(question, ticker):
    tk = (ticker or "").strip().lower()
    pref = tk.split("-")[0]
    for name, prefs in TICKER_CATS.items():
        if pref in prefs:
            return name
    text = f"{question or ''} {ticker or ''}".lower()
    for name, pat in CATS:
        if re.search(pat, text):
            return name
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=str, default=str(RAW))
    ap.add_argument("--out", type=str, default=str(OUT))
    args = ap.parse_args()
    raw_path, out_path = Path(args.raw), Path(args.out)

    rows = []
    n_in = 0
    for line in raw_path.open():
        try:
            m = json.loads(line)
        except Exception:
            continue
        try:
            outs = json.loads(m.get("outcomes") or "[]")
            toks = json.loads(m.get("clobTokenIds") or "[]")
            prices = json.loads(m.get("outcomePrices") or "[]")
        except Exception:
            continue
        if len(outs) != 2 or len(toks) != 2 or len(prices) != 2:
            continue
        try:
            p0, p1 = float(prices[0]), float(prices[1])
        except Exception:
            continue
        if abs((p0 + p1) - 1.0) > 0.02:  # resolved cleanly (0/1)
            continue
        if not (p0 > 0.5 or p1 > 0.5):  # still unresolved (0.5/0.5)
            continue
        closed = m.get("closedTime")
        start = m.get("startDate")
        if not closed or not start:
            continue
        try:
            c = pd.Timestamp(closed)
            s = pd.Timestamp(start)
        except Exception:
            continue
        ev = (m.get("events") or [{}])
        ticker = ev[0].get("ticker") if ev else None
        nr = m.get("negRisk")
        if nr is None:
            nr = m.get("negRiskOther")
        rows.append({
            "id": m.get("id"),
            "slug": m.get("slug"),
            "question": m.get("question"),
            "volume": m.get("volumeNum") or 0.0,
            "liquidity": m.get("liquidityNum") or 0.0,
            "start_ts": s.timestamp(),
            "close_ts": c.timestamp(),
            "end_ts": pd.Timestamp(m["endDate"]).timestamp() if m.get("endDate") else None,
            "lifespan_h": (c - s).total_seconds() / 3600.0,
            "token0": toks[0],
            "token1": toks[1],
            "outcome0": outs[0],
            "resolved0": 1 if p0 > 0.5 else 0,
            "neg_risk": bool(nr),
            "fee_type": m.get("feeType"),
            "category": categorize(m.get("question"), ticker),
            "ticker": ticker,
        })
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset="id")
    df.to_parquet(out_path, index=False)
    print(f"markets: {len(df)}")
    print(df["category"].value_counts().to_string())
    print("\nvolume quantiles:")
    print(df["volume"].describe().to_string())


if __name__ == "__main__":
    main()
