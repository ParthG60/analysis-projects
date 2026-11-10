import sqlite3
import time
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from . import config
except (ImportError, ValueError):
    import config

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_uk_tax_year(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if (dt.month > 4) or (dt.month == 4 and dt.day >= 6):
        return f"{dt.year}-{dt.year + 1}"
    else:
        return f"{dt.year - 1}-{dt.year}"

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Table for trades
    c.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        question TEXT NOT NULL,
        series TEXT,
        outcome_name TEXT,
        token_id TEXT NOT NULL,
        stake_usd REAL NOT NULL,
        entry_price REAL NOT NULL,
        shares REAL NOT NULL,
        status TEXT NOT NULL, -- 'OPEN', 'WON', 'LOST', 'CANCELLED'
        payout_usd REAL DEFAULT 0.0,
        pnl_usd REAL DEFAULT 0.0,
        is_dry_run INTEGER NOT NULL,
        created_at REAL NOT NULL,
        closed_at REAL,
        order_id TEXT DEFAULT '',
        tx_hash TEXT DEFAULT '',
        fee_usd REAL DEFAULT 0.0,
        fx_gbp_usd REAL DEFAULT 1.28,
        stake_gbp REAL DEFAULT 0.0,
        payout_gbp REAL DEFAULT 0.0,
        pnl_gbp REAL DEFAULT 0.0,
        tax_year TEXT DEFAULT ''
    );
    """)

    # Check and migrate columns if table was created in earlier session
    c.execute("PRAGMA table_info(trades);")
    existing_cols = {row["name"] for row in c.fetchall()}
    migrations = [
        ("order_id", "TEXT DEFAULT ''"),
        ("tx_hash", "TEXT DEFAULT ''"),
        ("fee_usd", "REAL DEFAULT 0.0"),
        ("fx_gbp_usd", "REAL DEFAULT 1.28"),
        ("stake_gbp", "REAL DEFAULT 0.0"),
        ("payout_gbp", "REAL DEFAULT 0.0"),
        ("pnl_gbp", "REAL DEFAULT 0.0"),
        ("tax_year", "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_def};")
    
    # Table for account balance & equity tracking
    c.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        cash_usd REAL NOT NULL,
        peak_equity REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    """)
    
    # Initialize portfolio if empty
    c.execute("SELECT COUNT(*) FROM portfolio_state;")
    if c.fetchone()[0] == 0:
        c.execute("""
        INSERT INTO portfolio_state (id, cash_usd, peak_equity, updated_at)
        VALUES (1, ?, ?, ?);
        """, (config.DEFAULT_INITIAL_BANKROLL, config.DEFAULT_INITIAL_BANKROLL, time.time()))
        
    conn.commit()
    conn.close()

def get_cash_balance() -> float:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT cash_usd FROM portfolio_state WHERE id = 1;")
    row = c.fetchone()
    conn.close()
    return float(row["cash_usd"]) if row else config.DEFAULT_INITIAL_BANKROLL

def get_peak_equity() -> float:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT peak_equity FROM portfolio_state WHERE id = 1;")
    row = c.fetchone()
    conn.close()
    return float(row["peak_equity"]) if row else config.DEFAULT_INITIAL_BANKROLL

def update_cash_balance(new_cash: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT peak_equity FROM portfolio_state WHERE id = 1;")
    row = c.fetchone()
    current_equity = get_portfolio_equity()
    peak = max(row["peak_equity"] if row else 0.0, current_equity, new_cash)
    c.execute("""
    UPDATE portfolio_state 
    SET cash_usd = ?, peak_equity = ?, updated_at = ?
    WHERE id = 1;
    """, (new_cash, peak, time.time()))
    conn.commit()
    conn.close()

def get_open_trades() -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE status = 'OPEN';")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_open_positions_count() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN';")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_event_open_count(event_id: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN' AND event_id = ?;", (event_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_consecutive_losses() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT status FROM trades WHERE status IN ('WON', 'LOST') ORDER BY closed_at DESC, id DESC;")
    rows = c.fetchall()
    conn.close()
    streak = 0
    for r in rows:
        if r["status"] == "LOST":
            streak += 1
        else:
            break
    return streak

def record_trade(
    market_id: str,
    event_id: str,
    question: str,
    series: str,
    outcome_name: str,
    token_id: str,
    stake_usd: float,
    entry_price: float,
    shares: float,
    is_dry_run: bool = True,
    order_id: str = "",
    tx_hash: str = "",
    fee_usd: float = 0.0,
    fx_gbp_usd: float = config.DEFAULT_GBP_USD_RATE
) -> int:
    conn = get_connection()
    c = conn.cursor()
    
    # Deduct cash
    cash = get_cash_balance()
    update_cash_balance(cash - stake_usd)
    
    now = time.time()
    stake_gbp = round(stake_usd / fx_gbp_usd, 2) if fx_gbp_usd > 0 else 0.0
    tax_year = get_uk_tax_year(now)

    c.execute("""
    INSERT INTO trades (
        market_id, event_id, question, series, outcome_name,
        token_id, stake_usd, entry_price, shares, status,
        is_dry_run, created_at, order_id, tx_hash, fee_usd,
        fx_gbp_usd, stake_gbp, tax_year
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        market_id, event_id, question, series, outcome_name,
        token_id, stake_usd, entry_price, shares,
        1 if is_dry_run else 0, now, order_id, tx_hash, fee_usd,
        fx_gbp_usd, stake_gbp, tax_year
    ))
    trade_id = c.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def settle_trade(trade_id: int, won: bool, payout_per_share: float = 1.0, tx_hash: str = ""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE id = ?;", (trade_id,))
    trade = c.fetchone()
    if not trade or trade["status"] != "OPEN":
        conn.close()
        return

    shares = float(trade["shares"])
    stake = float(trade["stake_usd"])
    fx_rate = float(trade["fx_gbp_usd"]) if trade["fx_gbp_usd"] else config.DEFAULT_GBP_USD_RATE
    
    payout = shares * payout_per_share if won else 0.0
    pnl = payout - stake
    payout_gbp = round(payout / fx_rate, 2) if fx_rate > 0 else 0.0
    pnl_gbp = round(pnl / fx_rate, 2) if fx_rate > 0 else 0.0
    status = "WON" if won else "LOST"
    now = time.time()
    final_tx = tx_hash if tx_hash else trade["tx_hash"]

    c.execute("""
    UPDATE trades 
    SET status = ?, payout_usd = ?, pnl_usd = ?, payout_gbp = ?, pnl_gbp = ?, closed_at = ?, tx_hash = ?
    WHERE id = ?;
    """, (status, payout, pnl, payout_gbp, pnl_gbp, now, final_tx, trade_id))
    
    # Credit cash
    cash = get_cash_balance()
    update_cash_balance(cash + payout)
    
    conn.commit()
    conn.close()

def get_portfolio_equity() -> float:
    cash = get_cash_balance()
    open_trades = get_open_trades()
    open_stake = sum(float(t["stake_usd"]) for t in open_trades)
    return cash + open_stake

def export_tax_csv(output_path: str, include_dry_run: bool = True) -> str:
    conn = get_connection()
    c = conn.cursor()
    
    query = "SELECT * FROM trades"
    if not include_dry_run:
        query += " WHERE is_dry_run = 0"
    query += " ORDER BY created_at ASC;"
    
    c.execute(query)
    rows = c.fetchall()
    conn.close()

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "Trade ID", "Status", "Is Dry Run", "Tax Year (UK)",
        "Entry Time (UTC)", "Exit Time (UTC)",
        "Competition / League", "Question", "Outcome Picked",
        "Market ID", "Token ID", "CLOB Order ID", "Polygon Tx Hash",
        "Entry Price (USD)", "Shares",
        "Stake (USD)", "Payout (USD)", "Net PnL (USD)",
        "FX Rate (GBP/USD)", "Stake (GBP)", "Payout (GBP)", "Net PnL (GBP)"
    ]

    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for r in rows:
            entry_utc = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else ""
            exit_utc = datetime.fromtimestamp(r["closed_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if r["closed_at"] else ""
            writer.writerow([
                r["id"], r["status"], "Simulated" if r["is_dry_run"] else "Live", r["tax_year"],
                entry_utc, exit_utc,
                r["series"], r["question"], r["outcome_name"],
                r["market_id"], r["token_id"], r["order_id"], r["tx_hash"],
                f"{r['entry_price']:.3f}", f"{r['shares']:.2f}",
                f"{r['stake_usd']:.2f}", f"{r['payout_usd']:.2f}", f"{r['pnl_usd']:.2f}",
                f"{r['fx_gbp_usd']:.4f}", f"{r['stake_gbp']:.2f}", f"{r['payout_gbp']:.2f}", f"{r['pnl_gbp']:.2f}"
            ])

    return str(p.resolve())

def get_tax_summary(include_dry_run: bool = True) -> Dict[str, Any]:
    conn = get_connection()
    c = conn.cursor()
    query = """
    SELECT 
        tax_year,
        COUNT(*) as total_trades,
        SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_pos,
        SUM(stake_usd) as total_stake_usd,
        SUM(payout_usd) as total_payout_usd,
        SUM(pnl_usd) as net_pnl_usd,
        SUM(stake_gbp) as total_stake_gbp,
        SUM(payout_gbp) as total_payout_gbp,
        SUM(pnl_gbp) as net_pnl_gbp
    FROM trades
    """
    if not include_dry_run:
        query += " WHERE is_dry_run = 0"
    query += " GROUP BY tax_year ORDER BY tax_year ASC;"
    
    c.execute(query)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"by_tax_year": rows}
