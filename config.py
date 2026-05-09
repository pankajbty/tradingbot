import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# STOCK WATCHLIST (used for monitoring / data fetching)
# ---------------------------------------------------------------------------
WATCHLIST = ["RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK", "MSUMI"]

# ---------------------------------------------------------------------------
# ENABLED STRATEGIES
# Options: "fixed_buy", "ma_crossover", "open_range_breakout"
# ---------------------------------------------------------------------------
ENABLED_STRATEGIES = ["fixed_buy", "ma_crossover", "open_range_breakout", "bollinger"]

# ---------------------------------------------------------------------------
# FIXED BUY STRATEGY
# Buys a fixed quantity of specified stocks once at market open.
# ---------------------------------------------------------------------------
FIXED_BUY_CONFIG = {
    "stocks": {
        "MSUMI": {"quantity": 1},
        # "INFY":     {"quantity": 2},
    },
    "order_type": "MARKET",   # MARKET or LIMIT
    "execute_at": "09:21",    # HH:MM (IST) — 1 min after open to avoid chaos
}

# ---------------------------------------------------------------------------
# MOVING AVERAGE CROSSOVER STRATEGY
# BUY when fast EMA crosses above slow EMA; SELL on cross below.
# Runs on 5-minute candles, checked every 5 minutes.
# ---------------------------------------------------------------------------
MA_CROSSOVER_CONFIG = {
    "stocks": ["MSUMI"],
    "fast_period": 9,              # Fast EMA period (candles)
    "slow_period": 21,             # Slow EMA period (candles)
    "candle_interval": "5minute",  # kiteconnect interval string
    "quantity_per_stock": 1,
    "check_interval_minutes": 5,
}

# ---------------------------------------------------------------------------
# OPEN RANGE BREAKOUT STRATEGY
# Calculates high/low of the first N minutes.
# BUY on breakout above range high; SELL on breakdown below range low.
# One trade per stock per day.
# ---------------------------------------------------------------------------
OPEN_RANGE_CONFIG = {
    "stocks": ["MSUMI"],
    "opening_range_minutes": 15,   # First 15 min = opening range (9:15–9:30)
    "quantity_per_stock": 1,
    "check_interval_minutes": 1,
    # True  → trade both breakout (BUY) and breakdown (SELL short)
    # False → only BUY on breakout above range high (no short selling)
    "allow_short": False,
    # True  → keep re-entering after a stop-loss until a profitable trade closes
    "stop_on_profit": False,
    # Max re-entry attempts per day (0 = unlimited). Applies when stop_on_profit=True
    "max_entries_per_day": 1,
}

# ---------------------------------------------------------------------------
# BOLLINGER BAND STRATEGY
# BUY when price crosses back above the lower band (oversold bounce).
# Exit via target (upper band) or stop-loss.
# Checked every 5 minutes on 5-min candles.
# ---------------------------------------------------------------------------
BOLLINGER_CONFIG = {
    "stocks": ["MSUMI"],
    "period": 20,                  # SMA & StdDev period
    "std_dev": 2.0,                # Band width multiplier
    "candle_interval": "5minute",
    "quantity_per_stock": 1,
    "check_interval_minutes": 5,
    "allow_short": False,          # True → also SELL when price crosses below upper band
}

# ---------------------------------------------------------------------------
# RISK MANAGEMENT
# ---------------------------------------------------------------------------
RISK_CONFIG = {
    "stop_loss_pct":     1.5,    # Stop loss % from entry
    "target_pct":        3.0,    # Target profit % from entry
    "max_daily_loss":    5000,   # Max cumulative loss per day in ₹
    "max_open_positions": 5,     # Max concurrent open positions
    "auto_squareoff_time": "15:15",  # Square off all MIS positions at this time
}

# ---------------------------------------------------------------------------
# ZERODHA CREDENTIALS  (no API subscription needed)
# ---------------------------------------------------------------------------
ZERODHA_CONFIG = {
    "user_id":  os.getenv("ZERODHA_USER_ID", ""),
    "password": os.getenv("ZERODHA_PASSWORD", ""),
    # Optional: base32 TOTP setup key for fully headless login.
    # If blank, main.py prompts for the 6-digit code from your authenticator app.
    "totp_secret": os.getenv("ZERODHA_TOTP_SECRET", ""),
}

EXCHANGE = "NSE"
PRODUCT  = "MIS"
