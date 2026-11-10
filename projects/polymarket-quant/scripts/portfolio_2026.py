"""2026-only bankroll test: 500 USD start, grid over filters x position sizing.

Plain ending-wealth results (no annualisation / ratio metrics).

Entry = price at 6h before close, taker-ask proxy (clob price + 1.8c slip), plus
per-category fees. Capital committed at entry, released at resolution.

Sizing schemes:
  flat N      -> stake min(N, cash)
  pct X       -> stake min(X * cash, cap)
  half-kelly  -> stake min(0.5 * kelly * cash, cap), kelly from p_hat (2025 bin
                 calibration for the same volume gate; fallback = implied price)

Filters: volume gate, price band, theme exclusions.
"""
import argparse
import re

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HZ_SEC = {"p6h": 21600, "p1d": 86400, "p12h": 43200}
FEE = {"crypto": 0.07, "us_politics": 0.04, "intl_politics": 0.04, "macro_finance": 0.04,
       "tech": 0.04, "geopolitics": 0.0, "culture": 0.04, "science_space": 0.04,
       "other": 0.04}
SLIP = 0.018
START = 500.0
CAP = 50.0


def theme(q):
    q = (q or "").lower()
    if "iran" in q:
        return "iran"
    if re.search(r"ukraine|russia|putin|zelensky", q):
        return "ukraine"
    if re.search(r"israel|gaza|hamas|lebanon", q):
        return "israel"
    if re.search(r"\b(bitcoin|btc|ethereum|eth|solana|xrp|doge|dogecoin|crypto)\b", q):
        return "crypto"
    if re.search(r" vs\.? | o/u|spread:|game total|completed match| to win |beat |map \d", q):
        return "sports"
    if re.search(r"trump|biden|election|senate|congress|shutdown|government|nominee", q):
        return "us_pol"
    return "other"


def calibrate(df, vol_min):
    """p_hat by 0.05 price bin from the OTHER year (avoids look-ahead)."""
    d = df[(df.volume >= vol_min) & df.p6h.between(0.05, 0.35)]
    d = d.copy()
    d["b"] = (d.p6h * 20).round() / 20
    g = d.groupby("b").resolved0.mean()
    return g


def sim(d, size, cal=None, kelly_frac=0.5):
    """d: candidate trades sorted by entry_ts. size: ('flat',N)|('pct',X)|('kelly',)."""
    cash = START
    peak = cash
    maxdd = 0.0
    openp = []
    wins = 0
    n = 0
    for row in d.itertuples(index=False):
        still = []
        for r_ts, payoff in openp:
            if r_ts <= row.entry_ts:
                cash += payoff
                peak = max(peak, cash)
                maxdd = max(maxdd, (peak - cash) / peak)
            else:
                still.append((r_ts, payoff))
        openp = still
        if size[0] == "flat":
            stake = min(size[1], cash)
        elif size[0] == "pct":
            stake = min(size[1] * cash, CAP)
        else:  # kelly
            ph = cal.get(round(row.price * 20) / 20, row.price) if cal is not None else row.price
            b = (1 - row.cost) / row.cost
            k = ph - (1 - ph) / b
            stake = min(max(k, 0) * kelly_frac * cash, CAP)
        if stake < 1.0 or stake > cash:
            continue
        cash -= stake
        payoff = stake / row.cost if row.resolved0 == 1 else 0.0
        openp.append((row.close_ts, payoff))
        wins += int(row.resolved0 == 1)
        n += 1
    for r_ts, payoff in sorted(openp):
        cash += payoff
        peak = max(peak, cash)
        maxdd = max(maxdd, (peak - cash) / peak)
    return cash, n, (wins / n if n else 0.0), maxdd


def main():
    ap = argparse.ArgumentParser()
    args = ap.parse_args()

    h = pd.read_json(ROOT / "data" / "horizons_full.jsonl", lines=True)
    u = pd.read_parquet(ROOT / "data" / "universe_full.parquet")
    u["id"] = u["id"].astype(str)
    h["id"] = h["id"].astype(str)
    df = h.merge(u[["id", "question"]], on="id", how="left")
    df = df.dropna(subset=["p6h"]).copy()
    df["year"] = pd.to_datetime(df.close_ts, unit="s").dt.year
    df["fee"] = df.category.map(FEE).fillna(0.04)
    df["theme"] = df.question.map(theme)

    cur = df[df.year == 2026]
    prev = df[df.year == 2025]

    filters = {
        "vol>=5k, band .05-.35":       dict(vmin=5000, lo=.05, hi=.35, drop=()),
        "vol>=10k, band .05-.35":      dict(vmin=10000, lo=.05, hi=.35, drop=()),
        "vol>=25k, band .05-.35":      dict(vmin=25000, lo=.05, hi=.35, drop=()),
        "vol>=50k, band .05-.35":      dict(vmin=50000, lo=.05, hi=.35, drop=()),
        "vol>=100k, band .05-.35":     dict(vmin=100000, lo=.05, hi=.35, drop=()),
        "vol>=25k, band .05-.20":      dict(vmin=25000, lo=.05, hi=.20, drop=()),
        "vol>=25k, band .20-.35":      dict(vmin=25000, lo=.20, hi=.35, drop=()),
        "vol>=25k, no geopolitics":    dict(vmin=25000, lo=.05, hi=.35, drop=("iran","israel","ukraine")),
        "vol>=25k, no crypto":         dict(vmin=25000, lo=.05, hi=.35, drop=("crypto",)),
        "vol>=25k, no geo+crypto":     dict(vmin=25000, lo=.05, hi=.35, drop=("iran","israel","ukraine","crypto")),
        "vol>=25k, only us/intl_pol":  dict(vmin=25000, lo=.05, hi=.35, drop=(), only=("us_pol",)),
    }
    sizings = {
        "flat 5 USD": ("flat", 5.0),
        "flat 10 USD": ("flat", 10.0),
        "flat 25 USD": ("flat", 25.0),
        "flat 50 USD": ("flat", 50.0),
        "1% of bankroll": ("pct", 0.01),
        "2% of bankroll": ("pct", 0.02),
        "5% of bankroll": ("pct", 0.05),
        "half-Kelly": ("kelly",),
    }

    print(f"2026-only, start {START:.0f} USD, taker-ask proxy (+{SLIP*100:.1f}c slip) + fees, entry @p6h")
    print(f"{'filter':<30}{'sizing':<16}{'trades':>7}{'win%':>6}{'ending USD':>14}")
    print("-" * 73)
    for fname, f in filters.items():
        d = cur[(cur.volume >= f["vmin"]) & (cur.p6h.between(f["lo"], f["hi"]))]
        if f.get("only"):
            d = d[d.theme.isin(f["only"])]
        if f["drop"]:
            d = d[~d.theme.isin(f["drop"])]
        d = d.copy()
        d["cost"] = (d.p6h.clip(.001, .999) + d.fee * d.p6h.clip(.001, .999) * (1 - d.p6h.clip(.001, .999)) + SLIP)
        d["price"] = d.p6h
        d["entry_ts"] = d.close_ts - HZ_SEC["p6h"]
        d = d.sort_values("entry_ts").reset_index(drop=True)
        cal = calibrate(prev, f["vmin"])
        for sname, size in sizings.items():
            end, n, win, dd = sim(d, size, cal=cal)
            tag = f"{end:,.0f}" if end >= 1 else "RUIN"
            print(f"{fname:<30}{sname:<16}{n:>7}{win*100:>5.0f}%{tag:>14}")


if __name__ == "__main__":
    main()
