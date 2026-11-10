import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load local .env if present (secrets + mode only)
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

def _clean_env(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    if not val:
        return ""
    if "#" in val:
        val = val.split("#", 1)[0]
    return val.strip()

# Authentication & Credentials
SIGNER_PRIVATE_KEY = _clean_env("SIGNER_PRIVATE_KEY", "")
POLYMARKET_WALLET_ADDRESS = _clean_env("POLYMARKET_WALLET_ADDRESS", "")
POLYMARKET_RELAYER_API_KEY = _clean_env("POLYMARKET_RELAYER_API_KEY", "")
POLYMARKET_RELAYER_API_KEY_ADDRESS = _clean_env("POLYMARKET_RELAYER_API_KEY_ADDRESS", "")

# Operation Mode
DRY_RUN = _clean_env("DRY_RUN", "true").lower() in ("true", "1", "yes")
DEFAULT_INITIAL_BANKROLL = float(_clean_env("INITIAL_BANKROLL", "500.0") or 500.0)

# Telegram Mobile Alerts
TELEGRAM_BOT_TOKEN = _clean_env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _clean_env("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Strategy parameters — strategy.yaml is the single source of truth.
# Edit strategy.yaml to tune the strategy, then restart the bot.
# ---------------------------------------------------------------------------
_STRATEGY_PATH = BASE_DIR / "strategy.yaml"

_DEFAULTS = {
    "sizing": {"risk_fraction": 0.04, "min_stake_usd": 5.0, "max_stake_usd": 50.0},
    "risk": {
        "max_open_positions": 10,
        "max_positions_per_event": 2,
        "circuit_breaker_max_drawdown": 0.40,
        "circuit_breaker_max_consecutive_losses": 12,
    },
    "selection": {
        "min_volume_usd": 10000.0,
        "price_min": 0.05,
        "price_max": 0.35,
        "min_hours_to_kickoff": 6.0,
        "max_hours_to_kickoff": 24.0,
        "max_spread": 0.02,
    },
    "tax": {"gbp_usd_rate": 1.28},
    "leagues": {"whitelist": [], "blacklist": []},
}


def _load_strategy() -> dict:
    if _STRATEGY_PATH.exists():
        with open(_STRATEGY_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


_STRAT = _load_strategy()


def _s(section: str, key: str):
    """Return a strategy value: strategy.yaml, else built-in default."""
    if section in _STRAT and key in _STRAT[section]:
        return _STRAT[section][key]
    return _DEFAULTS[section][key]


# Sizing & Bankroll (Dynamic Quarter-Kelly with floor & cap)
RISK_FRACTION = float(_s("sizing", "risk_fraction"))   # e.g. 0.04 = 4% of bankroll
MIN_STAKE_USD = float(_s("sizing", "min_stake_usd"))   # minimum order size floor
MAX_STAKE_USD = float(_s("sizing", "max_stake_usd"))   # per-order cap

# Risk Limits & Circuit Breakers
MAX_OPEN_POSITIONS = int(_s("risk", "max_open_positions"))
MAX_POSITIONS_PER_EVENT = int(_s("risk", "max_positions_per_event"))
CIRCUIT_BREAKER_MAX_DRAWDOWN = float(_s("risk", "circuit_breaker_max_drawdown"))
CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES = int(_s("risk", "circuit_breaker_max_consecutive_losses"))
DEFAULT_GBP_USD_RATE = float(_s("tax", "gbp_usd_rate"))

# Market Selection Criteria
MIN_VOLUME_USD = float(_s("selection", "min_volume_usd"))
PRICE_MIN = float(_s("selection", "price_min"))
PRICE_MAX = float(_s("selection", "price_max"))
MIN_HOURS_TO_KICKOFF = float(_s("selection", "min_hours_to_kickoff"))
MAX_HOURS_TO_KICKOFF = float(_s("selection", "max_hours_to_kickoff"))
MAX_SPREAD = float(_s("selection", "max_spread"))

# Strict Whitelist / Blacklist (from strategy.yaml)
WHITELIST_SERIES = set(_s("leagues", "whitelist"))
BLACKLIST_KEYWORDS = set(_s("leagues", "blacklist"))

# Strict Geographic IP Restrictions (Polymarket Terms of Service Section 1)
# Banned from trading: US, UK, Russia, France, Germany, Italy, Netherlands, Poland, Ireland, Belgium, etc.
# Deliberately NOT in strategy.yaml — compliance, not a tunable.
RESTRICTED_COUNTRIES = {
    "US", "GB", "RU", "FR", "DE", "IT", "NL", "PL", "IE", "BE",
    "AU", "NZ", "SG", "TH", "TW", "SK", "SI", "HU", "CA"
}

def verify_public_ip() -> dict:
    """
    Checks the machine's active public IP address before touching Polymarket.
    Halts trading if the IP is in a restricted jurisdiction (e.g. UK, Russia, US).
    """
    import httpx
    providers = [
        "https://ipinfo.io/json",
        "https://ipapi.co/json/",
    ]
    for url in providers:
        try:
            r = httpx.get(url, timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                cc = (data.get("country") or data.get("country_code") or "").upper()
                ip = data.get("ip", "")
                city = data.get("city", "")
                is_safe = (cc not in RESTRICTED_COUNTRIES) and bool(cc)
                return {
                    "safe": is_safe,
                    "ip": ip,
                    "country": cc,
                    "city": city,
                    "msg": f"Country: {cc} ({city}) | IP: {ip}"
                }
        except Exception:
            continue
    # If network check completely fails, fail closed for security
    return {
        "safe": False,
        "ip": "Unknown",
        "country": "Unknown",
        "city": "Unknown",
        "msg": "Could not determine public IP jurisdiction (network check failed)"
    }

# Database
DB_PATH = BASE_DIR / "trades.db"
