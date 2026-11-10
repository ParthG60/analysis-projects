import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from polymarket import AsyncPublicClient

try:
    from . import config
except (ImportError, ValueError):
    import config

def is_league_whitelisted(event_series: list, event_tags: list, title: str, question: str = "") -> bool:
    # An explicitly authorised series (exact match) is a known-good league. Its name
    # can appear in the series AND the tags, and some whitelisted names contain a
    # blacklist substring ("Brazil Serie A" contains "Serie A"). Before the blacklist
    # scan we erase any whitelisted-series name from the text so those collisions
    # don't silently drop a whole league. The blacklist still applies to the match
    # title and market question, so genuine derivatives ("- To Advance") and cups
    # are still rejected.
    exact_whitelisted = any(s in config.WHITELIST_SERIES for s in event_series)

    text_parts = [title, " ".join(event_tags), question]
    if not exact_whitelisted:
        text_parts.append(" ".join(event_series))
    full_text = " ".join(text_parts).lower()

    if exact_whitelisted:
        # longest names first so "Brazil Serie A" is removed before any shorter overlap
        for w in sorted(config.WHITELIST_SERIES, key=len, reverse=True):
            full_text = full_text.replace(w.lower(), " ")

    # 1. Reject if ANY blacklist keyword is present (Cups, Pokal, Friendly, La Liga, Serie A, To Advance)
    for b in config.BLACKLIST_KEYWORDS:
        if b.lower() in full_text:
            return False

    if exact_whitelisted:
        return True

    # 2. Must match an authorized domestic league in series or tags
    for s in event_series:
        if s in config.WHITELIST_SERIES:
            return True
        for w in config.WHITELIST_SERIES:
            if w.lower() in s.lower():
                return True

    for t in event_tags:
        if t in config.WHITELIST_SERIES:
            return True
        for w in config.WHITELIST_SERIES:
            if w.lower() in t.lower():
                return True

    return False

def get_kickoff_time(ev, m) -> Optional[datetime]:
    # Check sports metadata first
    if hasattr(m, 'sports') and m.sports and getattr(m.sports, 'game_start_time', None):
        return m.sports.game_start_time
    # Check market state
    if hasattr(m, 'state') and m.state:
        if getattr(m.state, 'start_date', None):
            return m.state.start_date
        if getattr(m.state, 'end_date', None):
            return m.state.end_date
    # Check event schedule
    if hasattr(ev, 'schedule') and ev.schedule:
        if getattr(ev.schedule, 'start_date', None):
            return ev.schedule.start_date
        if getattr(ev.schedule, 'end_date', None):
            return ev.schedule.end_date
    return None

async def scan_soccer_opportunities(client: Optional[AsyncPublicClient] = None) -> List[Dict[str, Any]]:
    close_client = False
    if client is None:
        client = AsyncPublicClient()
        close_client = True

    candidates = []
    now = datetime.now(timezone.utc)
    # Search window: events ending between now+6h and now+30h
    end_min = (now + timedelta(hours=config.MIN_HOURS_TO_KICKOFF)).isoformat()
    end_max = (now + timedelta(hours=config.MAX_HOURS_TO_KICKOFF + 6)).isoformat()

    try:
        # Fetch active soccer events ending in the target window
        pages = client.list_events(
            closed=False,
            tag_slug="soccer",
            end_date_min=end_min,
            end_date_max=end_max,
            page_size=50
        )
        
        async for ev in pages.iter_items():
            title = ev.title or ""
            # Must look like an individual match
            if not (" vs " in title or " vs. " in title or " - " in title or "beat" in title.lower()):
                continue

            event_series = [s.title for s in ev.series] if hasattr(ev, 'series') and ev.series else []
            event_tags = [t.label for t in ev.tags] if hasattr(ev, 'tags') and ev.tags else []

            if not is_league_whitelisted(event_series, event_tags, title):
                continue

            series_name = event_series[0] if event_series else (event_tags[0] if event_tags else "Soccer")

            if not hasattr(ev, 'markets') or not ev.markets:
                continue

            for m in ev.markets:
                # We want main match win or draw markets
                q = (m.question or "").lower()
                if not ("win" in q or "draw" in q or "beat" in q):
                    continue

                if not is_league_whitelisted(event_series, event_tags, title, m.question):
                    continue

                kickoff = get_kickoff_time(ev, m)
                if not kickoff:
                    continue

                # Check kickoff window (6h to 24h away)
                hours_to_kickoff = (kickoff - now).total_seconds() / 3600.0
                if not (config.MIN_HOURS_TO_KICKOFF <= hours_to_kickoff <= config.MAX_HOURS_TO_KICKOFF):
                    continue

                # Check volume (either market volume or parent event volume >= threshold)
                m_vol = float(getattr(m.metrics, 'volume', 0) or 0)
                ev_vol = float(getattr(ev.metrics, 'volume', 0) or 0)
                vol = max(m_vol, ev_vol)
                if vol < config.MIN_VOLUME_USD:
                    continue

                # Check prices
                prices = getattr(m, 'prices', None)
                if not prices or prices.best_bid is None or prices.best_ask is None:
                    continue

                best_bid = float(prices.best_bid)
                best_ask = float(prices.best_ask)
                spread = float(prices.spread or (best_ask - best_bid))

                if spread > config.MAX_SPREAD:
                    continue

                # Evaluate outcomes for underdog band [0.05, 0.35]
                outcomes = getattr(m, 'outcomes', None)
                if not outcomes:
                    continue

                # Check YES outcome
                yes_outcome = getattr(outcomes, 'yes', None)
                if yes_outcome and yes_outcome.token_id:
                    price = float(yes_outcome.price or best_ask)
                    if config.PRICE_MIN <= price <= config.PRICE_MAX:
                        candidates.append({
                            "market_id": str(m.id),
                            "event_id": str(ev.id),
                            "question": m.question,
                            "series": series_name,
                            "outcome_name": yes_outcome.label or "Yes",
                            "token_id": str(yes_outcome.token_id),
                            "best_bid": best_bid,
                            "best_ask": best_ask,
                            "price": price,
                            "spread": spread,
                            "volume": vol,
                            "kickoff_dt": kickoff.isoformat(),
                            "hours_to_kickoff": round(hours_to_kickoff, 2)
                        })

    finally:
        if close_client:
            await client.__aexit__(None, None, None)

    return candidates
