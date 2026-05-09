import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Exchange configuration
# Options: "coindcx", "wazirx", "binance"
# ---------------------------------------------------------------------------
EXCHANGE_ID = "coindcx"

# ---------------------------------------------------------------------------
# API credentials (set via .env)
# ---------------------------------------------------------------------------
EXCHANGE_CONFIG = {
    "api_key":    os.getenv("CRYPTO_API_KEY", ""),
    "api_secret": os.getenv("CRYPTO_API_SECRET", ""),
}

# ---------------------------------------------------------------------------
# Watchlist  — symbols in ccxt format for the chosen exchange
# ---------------------------------------------------------------------------
CRYPTO_WATCHLIST = ["BTC/INR", "ETH/INR", "SOL/INR", "BNB/INR"]

# ---------------------------------------------------------------------------
# RISK MANAGEMENT
# ---------------------------------------------------------------------------
CRYPTO_RISK_CONFIG = {
    "stop_loss_pct":      2.0,    # % from entry price
    "target_pct":         4.0,    # % from entry price
    "max_daily_loss":    5000,    # ₹ — halt all trading when daily loss exceeds this
    "max_open_positions":   3,    # concurrent open positions cap
    "trade_amount_inr":  1000,    # ₹ per trade (position sizing)
    "daily_reset_hour":     0,    # IST hour to reset daily P&L counter (0 = midnight)
}

# ---------------------------------------------------------------------------
# EMA CROSSOVER STRATEGY  (Triple-EMA Trend Following)
# BUY:  9 EMA crosses above 21 EMA  AND  price > 55 EMA (trend filter)
# SELL: 9 EMA crosses below 21 EMA
# Best timeframe: 15-minute candles
# ---------------------------------------------------------------------------
EMA_CROSSOVER_CONFIG = {
    "symbols":                ["BTC/INR", "ETH/INR"],
    "fast_period":            9,
    "slow_period":            21,
    "trend_period":           55,       # 55 EMA trend filter — only trade with the trend
    "candle_interval":        "15m",    # ccxt timeframe string
    "trade_amount_inr":       1000,     # ₹ per trade
    "check_interval_minutes": 15,
    "stop_on_profit":         False,
    "max_entries_per_day":    0,        # 0 = unlimited
    "active_from":            "00:00",  # crypto is 24/7
    "active_until":           "23:59",
}

# ---------------------------------------------------------------------------
# SUPERTREND STRATEGY  (ATR-based trend following — best for volatile crypto)
# BUY:  price closes above Supertrend line
# SELL: price closes below Supertrend line
# Works brilliantly on trending crypto — very low false signals
# ---------------------------------------------------------------------------
SUPERTREND_CONFIG = {
    "symbols":                ["BTC/INR", "ETH/INR", "SOL/INR"],
    "atr_period":             10,
    "multiplier":             3.0,
    "candle_interval":        "15m",
    "trade_amount_inr":       1000,
    "check_interval_minutes": 15,
    "stop_on_profit":         False,
    "max_entries_per_day":    0,
    "active_from":            "00:00",
    "active_until":           "23:59",
}

# ---------------------------------------------------------------------------
# RSI + BOLLINGER BAND STRATEGY  (Mean-Reversion)
# BUY:  RSI < 35  AND  price <= lower Bollinger Band  (oversold bounce)
# SELL: RSI > 65  OR   price >= upper Bollinger Band  (overbought)
# Best during sideways/consolidating markets
# ---------------------------------------------------------------------------
RSI_BB_CONFIG = {
    "symbols":                ["BTC/INR", "ETH/INR"],
    "rsi_period":             14,
    "rsi_oversold":           35,
    "rsi_overbought":         65,
    "bb_period":              20,
    "bb_std_dev":             2.0,
    "candle_interval":        "1h",     # RSI+BB works better on higher timeframes
    "trade_amount_inr":       1000,
    "check_interval_minutes": 60,
    "stop_on_profit":         False,
    "max_entries_per_day":    0,
    "active_from":            "00:00",
    "active_until":           "23:59",
}
