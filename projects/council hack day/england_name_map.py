"""Gateway council id/name (data_england/england_names.json, 270 councils) ->
ONS code + RSX authority name -> data_england/name_map.csv.

Matching: normalize both sides (lowercase, & -> and, hyphens -> spaces, strip
apostrophes/punctuation, drop authority-type/filler tokens), then exact match;
councils that don't exact-match fall back to a token-subset match (handles
"County Durham" -> "Durham", "Newcastle upon Tyne" -> "Newcastle", "Bournemouth"
-> "Bournemouth, Christchurch and Poole" post-2019-merger, etc). Anything left
unmatched is logged, not guessed.

Usage: python england_name_map.py
"""
import json
import re
from pathlib import Path

import pandas as pd

from finance import load_rsx

BASE = Path(__file__).parent
OUT_DIR = BASE / "data_england"
LA_CLASSES = ["SD", "MD", "UA", "LB", "SC"]

# tokens that are authority-type suffixes or filler words carrying no
# distinguishing information, dropped from both sides before comparing.
DROP_TOKENS = {"ua", "cc", "mbc", "bc", "dc", "sd", "sc", "md", "lb",
               "city", "of", "the", "towns", "council", "county"}


def normalize(name):
    s = name.lower()
    s = s.replace("&", " and ")
    s = s.replace("-", " ")
    s = s.replace("'", "")
    s = re.sub(r"[.,]", " ", s)
    tokens = [t for t in s.split() if t not in DROP_TOKENS]
    return " ".join(tokens)


def build_rsx_index():
    df = load_rsx()
    la = df[df["Class"].isin(LA_CLASSES)]
    la = la[la["ONS Code"].str.len() == 9]  # drop the 5 subtotal rows
    index = {}
    for _, rec in la.iterrows():
        key = normalize(rec["Local authority"])
        index.setdefault(key, []).append((rec["ONS Code"], rec["Local authority"]))
    return index


def subset_match(gateway_key, rsx_index):
    """Fallback: accept a match if one side's token set is a subset of the
    other's (e.g. rsx 'durham' <= gateway 'county durham'). Only accepted if
    exactly one rsx key qualifies, to avoid guessing between ambiguous
    candidates."""
    g_tokens = set(gateway_key.split())
    candidates = []
    for rsx_key, entries in rsx_index.items():
        r_tokens = set(rsx_key.split())
        if r_tokens and g_tokens and (r_tokens <= g_tokens or g_tokens <= r_tokens):
            candidates.append(rsx_key)
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_index(values):
    """Generic version of build_rsx_index for any iterable of raw name strings
    (e.g. a source file's own LA-name column) -> {normalized_key: [raw names]}."""
    index = {}
    for v in values:
        index.setdefault(normalize(str(v)), []).append(v)
    return index


def match_name(name, index):
    """Look up `name` (raw, un-normalized) in an index built by build_index/
    build_rsx_index. Exact-normalize match first, then token-subset fallback.
    Returns the single matching raw name, or None if zero/ambiguous matches."""
    key = normalize(name)
    entries = index.get(key)
    if entries is None:
        fb = subset_match(key, index)
        entries = index.get(fb) if fb else None
    if entries is not None and len(entries) == 1:
        return entries[0]
    return None


def build_name_map():
    gateway = json.load(open(BASE / "data_england" / "england_names.json", encoding="utf-8"))
    rsx_index = build_rsx_index()

    rows, unmatched = [], []
    for gid, gname in gateway.items():
        gkey = normalize(gname)
        entries = rsx_index.get(gkey)
        if entries is None:
            fallback_key = subset_match(gkey, rsx_index)
            entries = rsx_index.get(fallback_key) if fallback_key else None

        if entries is not None and len(entries) == 1:
            ons_code, rsx_name = entries[0]
            rows.append({
                "gateway_id": gid, "gateway_name": gname, "ons_code": ons_code,
                "rsx_name": rsx_name, "matched": True,
            })
        else:
            rows.append({
                "gateway_id": gid, "gateway_name": gname, "ons_code": None,
                "rsx_name": None, "matched": False,
            })
            unmatched.append(gname)

    return pd.DataFrame(rows), unmatched


if __name__ == "__main__":
    name_map, unmatched = build_name_map()
    OUT_DIR.mkdir(exist_ok=True)
    name_map.to_csv(OUT_DIR / "name_map.csv", index=False)
    print(f"data_england/name_map.csv: {len(name_map)} rows, "
          f"{name_map['matched'].sum()} matched, {len(unmatched)} unmatched")
    if unmatched:
        print("\nUnmatched gateway councils:", "; ".join(sorted(set(unmatched))))
