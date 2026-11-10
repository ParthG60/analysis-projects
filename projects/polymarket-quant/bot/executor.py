import os
import asyncio
import logging
from typing import Dict, Any, Optional
from polymarket import AsyncSecureClient, RelayerApiKey

try:
    from . import config
    from . import db
    from . import notifier
except (ImportError, ValueError):
    import config
    import db
    import notifier

logger = logging.getLogger("executor")

def calculate_dynamic_stake(equity: float) -> float:
    raw_stake = equity * config.RISK_FRACTION
    safe_stake = max(config.MIN_STAKE_USD, min(raw_stake, config.MAX_STAKE_USD))
    return round(safe_stake, 2)

async def get_live_client() -> Optional[AsyncSecureClient]:
    if config.DRY_RUN:
        return None
    if not (config.SIGNER_PRIVATE_KEY and config.POLYMARKET_WALLET_ADDRESS):
        raise ValueError("Live execution requires SIGNER_PRIVATE_KEY and POLYMARKET_WALLET_ADDRESS in .env")

    kwargs = {
        "private_key": config.SIGNER_PRIVATE_KEY,
        "wallet": config.POLYMARKET_WALLET_ADDRESS,
    }
    if config.POLYMARKET_RELAYER_API_KEY and config.POLYMARKET_RELAYER_API_KEY_ADDRESS:
        kwargs["api_key"] = RelayerApiKey(
            key=config.POLYMARKET_RELAYER_API_KEY,
            address=config.POLYMARKET_RELAYER_API_KEY_ADDRESS,
        )
    return await AsyncSecureClient.create(**kwargs)

async def execute_trade(candidate: Dict[str, Any], live_client: Optional[AsyncSecureClient] = None) -> Optional[int]:
    market_id = candidate["market_id"]
    event_id = candidate["event_id"]
    
    # 0. Hard Circuit Breakers (Protect bankroll from structural anomalies)
    peak = db.get_peak_equity()
    equity = db.get_portfolio_equity()
    if peak > 0:
        drawdown = (peak - equity) / peak
        if drawdown >= config.CIRCUIT_BREAKER_MAX_DRAWDOWN:
            logger.critical(
                f"[CIRCUIT BREAKER ACTIVE] Drawdown {drawdown*100:.1f}% >= threshold {config.CIRCUIT_BREAKER_MAX_DRAWDOWN*100:.1f}%. "
                f"Peak: {peak:.2f} USD, Current: {equity:.2f} USD. Halting new trades!"
            )
            await notifier.notify_circuit_breaker(
                reason=f"Drawdown {drawdown*100:.1f}% >= {config.CIRCUIT_BREAKER_MAX_DRAWDOWN*100:.0f}%",
                details=f"Peak: {peak:.2f} USD, Current: {equity:.2f} USD"
            )
            return None

    loss_streak = db.get_consecutive_losses()
    if loss_streak >= config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES:
        logger.critical(
            f"[CIRCUIT BREAKER ACTIVE] Consecutive losses {loss_streak} >= limit {config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES}. "
            f"Halting new trades!"
        )
        await notifier.notify_circuit_breaker(
            reason=f"Loss streak of {loss_streak} hit limit {config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES}",
            details="Trading halted automatically."
        )
        return None

    # 1. Capacity & event risk checks
    open_count = db.get_open_positions_count()
    if open_count >= config.MAX_OPEN_POSITIONS:
        logger.info(f"Skipping {market_id}: Max open positions reached ({open_count}/{config.MAX_OPEN_POSITIONS})")
        return None

    event_open = db.get_event_open_count(event_id)
    if event_open >= config.MAX_POSITIONS_PER_EVENT:
        logger.info(f"Skipping {market_id}: Max open positions for event {event_id} reached ({event_open}/{config.MAX_POSITIONS_PER_EVENT})")
        return None

    # 2. Bankroll & stake sizing
    equity = db.get_portfolio_equity()
    cash = db.get_cash_balance()
    stake = calculate_dynamic_stake(equity)

    if cash < stake:
        logger.warning(f"Skipping {market_id}: Insufficient cash ({cash:.2f} USD < {stake:.2f} USD)")
        return None

    # Entry target price: Best Bid (maker order)
    # If best_bid is 0, fall back to best_ask
    entry_price = candidate["best_bid"] if candidate["best_bid"] > 0 else candidate["best_ask"]
    if entry_price <= 0:
        logger.warning(f"Invalid entry price for {market_id}: {entry_price}")
        return None

    shares = round(stake / entry_price, 2)
    token_id = candidate["token_id"]

    # 3. Execution routing
    if config.DRY_RUN:
        logger.info(f"[DRY-RUN] Placing simulated Maker Limit BUY on {candidate['series']}: {candidate['question']}")
        logger.info(f"          Stake: {stake:.2f} USD @ {entry_price:.3f} | Shares: {shares} | Cash remaining: {cash - stake:.2f} USD")
        trade_id = db.record_trade(
            market_id=market_id,
            event_id=event_id,
            question=candidate["question"],
            series=candidate["series"],
            outcome_name=candidate["outcome_name"],
            token_id=token_id,
            stake_usd=stake,
            entry_price=entry_price,
            shares=shares,
            is_dry_run=True
        )
        await notifier.notify_order(
            candidate=candidate,
            stake=stake,
            entry_price=entry_price,
            shares=shares,
            is_dry_run=True
        )
        return trade_id
    else:
        if live_client is None:
            live_client = await get_live_client()
        logger.info(f"[LIVE] Submitting Maker Limit Order to CLOB for {candidate['question']}...")
        try:
            # Place limit order at best bid
            resp = await live_client.place_limit_order(
                asset_id=token_id,
                side="BUY",
                price=str(round(entry_price, 3)),
                size=str(int(shares))
            )
            if resp.ok:
                logger.info(f"[LIVE] Order accepted by CLOB! OrderID: {resp.order_id}, Status: {resp.status}")
                trade_id = db.record_trade(
                    market_id=market_id,
                    event_id=event_id,
                    question=candidate["question"],
                    series=candidate["series"],
                    outcome_name=candidate["outcome_name"],
                    token_id=token_id,
                    stake_usd=stake,
                    entry_price=entry_price,
                    shares=shares,
                    is_dry_run=False,
                    order_id=str(getattr(resp, 'order_id', '') or '')
                )
                await notifier.notify_order(
                    candidate=candidate,
                    stake=stake,
                    entry_price=entry_price,
                    shares=shares,
                    is_dry_run=False
                )
                return trade_id
            else:
                logger.error(f"[LIVE] Order rejected: {resp.code} - {resp.message}")
                return None
        except Exception as e:
            logger.error(f"[LIVE] Error placing order: {e}")
            return None

async def check_and_settle_trades(public_client):
    open_trades = db.get_open_trades()
    if not open_trades:
        return

    logger.info(f"Checking settlement status for {len(open_trades)} open positions...")
    for t in open_trades:
        market_id = t["market_id"]
        try:
            m = await public_client.get_market(market_id=market_id)
            if not m or not m.state:
                continue

            # If closed or resolved
            if m.state.closed:
                # Check resolved outcome
                # If market resolves to YES outcome:
                p_yes = float(getattr(m.outcomes.yes, 'price', 0.0) or 0.0)
                won = p_yes > 0.5 if t["outcome_name"] == "Yes" else p_yes <= 0.5
                logger.info(f"Position {t['id']} ({t['question']}) resolved: {'WON' if won else 'LOST'}")
                db.settle_trade(trade_id=t["id"], won=won)
                payout = t["shares"] * 1.0 if won else 0.0
                pnl = payout - t["stake_usd"]
                new_cash = db.get_cash_balance()
                await notifier.notify_settlement(
                    trade=t,
                    won=won,
                    payout=payout,
                    pnl=pnl,
                    new_cash=new_cash
                )
        except Exception as e:
            logger.debug(f"Error checking market {market_id}: {e}")
