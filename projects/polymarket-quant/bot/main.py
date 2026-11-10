import os
import sys
import time
import asyncio
import logging
import argparse
from pathlib import Path
from polymarket import AsyncPublicClient

try:
    from . import config
    from . import db
    from . import scanner
    from . import executor
    from . import notifier
except (ImportError, ValueError):
    import config
    import db
    import scanner
    import executor
    import notifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("polybot")

def print_status():
    db.init_db()
    cash = db.get_cash_balance()
    equity = db.get_portfolio_equity()
    peak = db.get_peak_equity()
    open_trades = db.get_open_trades()
    streak = db.get_consecutive_losses()
    drawdown = ((peak - equity) / peak * 100) if peak > 0 else 0.0
    ip_info = config.verify_public_ip()
    ip_badge = f"{ip_info['country']} ({ip_info['city']}) [AUTHORIZED / SAFE]" if ip_info['safe'] else f"{ip_info['country']} [RESTRICTED!]"
    
    print("\n" + "="*60)
    print("           POLYMARKET SOCCER AUTOTRADER STATUS")
    print("="*60)
    print(f"Mode:              {'DRY-RUN (Paper Trading)' if config.DRY_RUN else 'LIVE TRADING'}")
    print(f"Jurisdiction IP:   {ip_badge}")
    print(f"Cash Balance:      {cash:.2f} USD")
    print(f"Total Equity:      {equity:.2f} USD (Peak: {peak:.2f} USD)")
    print(f"Current Drawdown:  {drawdown:.1f}% (Circuit Breaker: {config.CIRCUIT_BREAKER_MAX_DRAWDOWN*100:.0f}%)")
    print(f"Loss Streak:       {streak} (Circuit Breaker: {config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES})")
    print(f"Open Positions:    {len(open_trades)} / {config.MAX_OPEN_POSITIONS}")
    print(f"Dynamic Stake:     {executor.calculate_dynamic_stake(equity):.2f} USD (4% Quarter-Kelly)")
    print("-" * 60)
    
    if open_trades:
        print("ACTIVE POSITIONS:")
        for t in open_trades:
            print(f"  [{t['id']}] {t['series']}: {t['question'][:45]}")
            print(f"      Stake: {t['stake_usd']:.2f} USD @ {t['entry_price']:.3f} | Shares: {t['shares']:.1f}")
    else:
        print("No active open positions.")
    print("="*60 + "\n")

def print_tax_summary():
    db.init_db()
    summary = db.get_tax_summary(include_dry_run=True)
    rows = summary.get("by_tax_year", [])
    print("\n" + "="*70)
    print("           UK TAX & CAPITAL ACCOUNT SUMMARY (HMRC BIM22015)")
    print("="*70)
    print("Note: In the UK, sports betting winnings are generally tax-free under")
    print("Betting and Gaming Duties Act 1981 / HMRC Business Income Manual (BIM22015).")
    print("This ledger is maintained for crypto-asset audit trails and AML records.")
    print("-" * 70)
    if not rows:
        print("No completed trades recorded in the database yet.")
    else:
        for r in rows:
            ty = r["tax_year"] or "Unassigned"
            trades = r["total_trades"] or 0
            wins = r["wins"] or 0
            losses = r["losses"] or 0
            stake_usd = r["total_stake_usd"] or 0.0
            payout_usd = r["total_payout_usd"] or 0.0
            pnl_usd = r["net_pnl_usd"] or 0.0
            pnl_gbp = r["net_pnl_gbp"] or 0.0
            wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
            print(f"Tax Year: {ty}")
            print(f"  Total Trades:     {trades} ({wins}W / {losses}L, Win Rate: {wr:.1f}%)")
            print(f"  Allowable Stakes: {stake_usd:.2f} USD")
            print(f"  Gross Proceeds:   {payout_usd:.2f} USD")
            print(f"  Net P&L (USD):    {pnl_usd:+.2f} USD")
            print(f"  Net P&L (GBP):    {pnl_gbp:+.2f} GBP")
            print("-" * 70)
    print("="*70 + "\n")

async def run_cycle(public_client: AsyncPublicClient, live_client=None):
    logger.info("--- Starting Scan Cycle ---")
    
    # 0. Geographic IP preflight check (Polymarket ToS compliance)
    ip_info = config.verify_public_ip()
    if not ip_info["safe"]:
        logger.critical(f"RESTRICTED IP DETECTED: {ip_info['msg']}. HALTING TRADING TO PROTECT ACCOUNT!")
        await notifier.notify_restricted_ip(ip_info["country"], ip_info["ip"], ip_info["city"])
        return
    
    # 1. Settle existing positions
    await executor.check_and_settle_trades(public_client)
    
    # 2. Portfolio health check
    equity = db.get_portfolio_equity()
    cash = db.get_cash_balance()
    open_count = db.get_open_positions_count()
    stake = executor.calculate_dynamic_stake(equity)
    
    logger.info(f"Portfolio State: Cash={cash:.2f} USD | Equity={equity:.2f} USD | Open={open_count}/{config.MAX_OPEN_POSITIONS} | Target Stake={stake:.2f} USD")
    
    if open_count >= config.MAX_OPEN_POSITIONS:
        logger.info("Maximum open positions reached. Skipping new entries.")
        return

    # 3. Scan for new underdog opportunities
    logger.info("Scanning for soccer underdog opportunities (6h-24h pre-kickoff, vol >= 10k USD)...")
    candidates = await scanner.scan_soccer_opportunities(public_client)
    logger.info(f"Found {len(candidates)} qualified underdog opportunities.")

    # 4. Execute up to capacity
    for cand in candidates:
        if db.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
            break
        await executor.execute_trade(cand, live_client)

async def main():
    parser = argparse.ArgumentParser(description="Polymarket Soccer Quantitative Autotrader")
    parser.add_argument("--once", action="store_true", help="Run a single scan cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run paper trading mode")
    parser.add_argument("--live", action="store_true", help="Force live order execution mode")
    parser.add_argument("--status", action="store_true", help="Print current portfolio status and exit")
    parser.add_argument("--tax-summary", action="store_true", help="Print UK tax year ledger summary and exit")
    parser.add_argument("--export-tax", type=str, nargs="?", const="bot/reports/tax_ledger.csv", default=None, help="Export tax ledger to CSV file and exit")
    parser.add_argument("--interval", type=int, default=900, help="Loop interval in seconds (default: 900s = 15min)")
    args = parser.parse_args()

    if args.dry_run:
        config.DRY_RUN = True
    elif args.live:
        config.DRY_RUN = False

    if args.status:
        print_status()
        return

    if args.tax_summary:
        print_tax_summary()
        return

    if args.export_tax:
        out = db.export_tax_csv(args.export_tax)
        print(f"Tax ledger exported successfully to: {out}")
        return

    db.init_db()
    print_status()

    # Preflight IP verification before connecting or placing orders
    ip_info = config.verify_public_ip()
    if not ip_info["safe"]:
        logger.critical(f"FATAL: Connected from restricted jurisdiction: {ip_info['msg']}. Aborting startup.")
        await notifier.notify_restricted_ip(ip_info["country"], ip_info["ip"], ip_info["city"])
        return

    logger.info(f"Starting bot loop (Interval: {args.interval}s)...")
    live_client = None
    if not config.DRY_RUN:
        live_client = await executor.get_live_client()
        logger.info("Live client authenticated with Polymarket Relayer.")

    mode_str = "DRY-RUN (Paper Trading)" if config.DRY_RUN else "LIVE TRADING"
    cash = db.get_cash_balance()
    equity = db.get_portfolio_equity()
    stake = executor.calculate_dynamic_stake(equity)
    await notifier.notify_startup(mode=mode_str, cash=cash, stake=stake)

    async with AsyncPublicClient() as public_client:
        while True:
            try:
                await run_cycle(public_client, live_client)
            except Exception as e:
                logger.error(f"Error during scan cycle: {e}", exc_info=True)

            if args.once:
                logger.info("Single run completed (--once). Exiting.")
                break

            logger.info(f"Sleeping for {args.interval} seconds...")
            await asyncio.sleep(args.interval)

if __name__ == "__main__":
    asyncio.run(main())
