import logging
import httpx
from typing import Dict, Any, Optional

try:
    from . import config
except (ImportError, ValueError):
    import config

logger = logging.getLogger("notifier")

async def send_telegram(text: str):
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Telegram alert failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.warning(f"Failed to send Telegram alert: {e}")

async def notify_startup(mode: str, cash: float, stake: float):
    msg = (
        f"🤖 <b>Polymarket Value Bot Online</b>\n\n"
        f"<b>Mode:</b> {mode}\n"
        f"<b>Bankroll:</b> {cash:.2f} USD\n"
        f"<b>Target Stake:</b> {stake:.2f} USD (4% Quarter-Kelly)\n"
        f"<b>Status:</b> Scanning whitelisted round-robin leagues..."
    )
    await send_telegram(msg)

async def notify_order(
    candidate: Dict[str, Any],
    stake: float,
    entry_price: float,
    shares: float,
    is_dry_run: bool
):
    potential_payout = shares * 1.0
    mode_badge = "🟡 [DRY-RUN]" if is_dry_run else "🟢 [LIVE]"
    msg = (
        f"{mode_badge} <b>Order Placed (Maker Limit BUY)</b>\n\n"
        f"<b>League:</b> {candidate.get('series', 'Soccer')}\n"
        f"<b>Match:</b> {candidate.get('question', '')}\n"
        f"<b>Pick:</b> {candidate.get('outcome_name', 'Yes')} (Underdog)\n"
        f"<b>Price:</b> {entry_price:.3f} ({entry_price*100:.1f}c)\n"
        f"<b>Stake:</b> {stake:.2f} USD\n"
        f"<b>Shares:</b> {shares:.1f}\n"
        f"<b>Potential Payout:</b> {potential_payout:.2f} USD (+{(potential_payout - stake):.2f} USD)"
    )
    await send_telegram(msg)

async def notify_settlement(
    trade: Dict[str, Any],
    won: bool,
    payout: float,
    pnl: float,
    new_cash: float
):
    icon = "🏆" if won else "❌"
    outcome = "WON" if won else "LOST"
    sign = "+" if pnl >= 0 else ""
    pnl_pct = (pnl / trade['stake_usd']) * 100 if trade.get('stake_usd') else 0.0

    msg = (
        f"{icon} <b>Match Resolved: {outcome}</b>\n\n"
        f"<b>League:</b> {trade.get('series', '')}\n"
        f"<b>Match:</b> {trade.get('question', '')}\n"
        f"<b>Pick:</b> {trade.get('outcome_name', 'Yes')}\n"
        f"<b>Stake:</b> {trade.get('stake_usd', 0.0):.2f} USD\n"
        f"<b>Payout:</b> {payout:.2f} USD\n"
        f"<b>Net P&L:</b> {sign}{pnl:.2f} USD ({sign}{pnl_pct:.1f}%)\n\n"
        f"<b>Updated Bankroll:</b> {new_cash:.2f} USD"
    )
    await send_telegram(msg)

async def notify_circuit_breaker(reason: str, details: str):
    msg = (
        f"🚨 <b>EMERGENCY CIRCUIT BREAKER ACTIVATED</b> 🚨\n\n"
        f"<b>Reason:</b> {reason}\n"
        f"<b>Details:</b> {details}\n\n"
        f"<b>Action Taken:</b> New entries halted automatically to protect capital."
    )
    await send_telegram(msg)

async def notify_restricted_ip(country: str, ip: str, city: str):
    msg = (
        f"🚨 <b>CRITICAL: RESTRICTED IP DETECTED</b>\n\n"
        f"<b>Detected Country:</b> {country} ({city})\n"
        f"<b>Public IP:</b> {ip}\n\n"
        f"⚠️ <i>Polymarket Terms of Service strictly prohibit trading from {country}. "
        f"The bot has halted all trading activities immediately to protect your wallet from being placed in close-only mode.</i>\n\n"
        f"<b>Action Required:</b> Please connect to an authorized non-restricted location (e.g. Switzerland or Sweden) and restart."
    )
    await send_telegram(msg)
