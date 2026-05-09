import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Exchange — CoinDCX (direct REST API, no ccxt required)
# Docs: https://docs.coindcx.com/
# ---------------------------------------------------------------------------
EXCHANGE_ID = "coindcx"

# ---------------------------------------------------------------------------
# API credentials  (set via .env or Admin → Crypto Exchange Config)
# ---------------------------------------------------------------------------
EXCHANGE_CONFIG = {
    "api_key":    os.getenv("CRYPTO_API_KEY", ""),
    "api_secret": os.getenv("CRYPTO_API_SECRET", ""),
}

# ---------------------------------------------------------------------------
# Watchlist  — CoinDCX symbol format: "BTCINR", "ETHINR" etc.
# (no slash, no space — this is how CoinDCX REST API identifies markets)
# ---------------------------------------------------------------------------
CRYPTO_WATCHLIST = ["BTCINR", "ETHINR", "SOLINR", "BNBINR"]

# ---------------------------------------------------------------------------
# RISK MANAGEMENT
# All monetary values in ₹ (Indian Rupees)
# ---------------------------------------------------------------------------
CRYPTO_RISK_CONFIG = {
    "stop_loss_pct":       2.0,    # % from entry price
    "target_pct":          4.0,    # % from entry price
    "max_daily_loss":    5000,     # ₹ — halt all trading when cumulative loss exceeds this
    "max_open_positions":    3,    # max concurrent open positions
    "trade_amount_inr":   1000,    # ₹ per trade (position sizing)
    "daily_reset_hour":      0,    # IST hour to reset daily P&L counter (0 = midnight)
}

# ---------------------------------------------------------------------------
# EMA CROSSOVER STRATEGY  (Triple-EMA Trend Following)
#
# BUY:  9 EMA crosses above 21 EMA  AND  price > 55 EMA (macro trend filter)
# SELL: 9 EMA crosses below 21 EMA
#
# Why triple-EMA: The 55 EMA filters out counter-trend crossovers which are
# the #1 killer of naive dual-EMA systems. Only trade WITH the trend.
# Best timeframe: 15-minute candles on BTC and ETH.
# ---------------------------------------------------------------------------
EMA_CROSSOVER_CONFIG = {
    "symbols":                ["BTCINR", "ETHINR"],
    "fast_period":            9,
    "slow_period":            21,
    "trend_period":           55,       # 55 EMA — macro trend filter
    "candle_interval":        "15m",    # CoinDCX interval string
    "trade_amount_inr":       1000,     # ₹ per trade
    "check_interval_minutes": 15,
    "stop_on_profit":         False,
    "max_entries_per_day":    0,        # 0 = unlimited
    "active_from":            "00:00",  # crypto is 24/7
    "active_until":           "23:59",
}

# ---------------------------------------------------------------------------
# SUPERTREND STRATEGY  (ATR-based Trend Following)
#
# BUY:  price closes ABOVE the Supertrend line  (bullish flip)
# SELL: price closes BELOW the Supertrend line  (bearish flip)
#
# Why Supertrend for crypto: Uses ATR so bands widen automatically during
# high-volatility periods — dramatically fewer whipsaws vs plain moving
# averages. 10-period ATR × 3.0 multiplier is the community-proven default
# for 15-minute crypto charts.
# ---------------------------------------------------------------------------
SUPERTREND_CONFIG = {
    "symbols":                ["BTCINR", "ETHINR", "SOLINR"],
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
#
# BUY:  RSI(14) < 35  AND  close <= lower Bollinger Band  (double-confirmation oversold)
# SELL: RSI(14) > 65  OR   close >= upper Bollinger Band  (exit / take profit)
#
# Why RSI+BB: Crypto frequently has sharp 5-15% dips followed by fast recoveries.
# Requiring BOTH RSI oversold AND price at the lower BB eliminates ~60% of false
# entries vs using either indicator alone. 1h candles filter out short-term noise.
# ---------------------------------------------------------------------------
RSI_BB_CONFIG = {
    "symbols":                ["BTCINR", "ETHINR"],
    "rsi_period":             14,
    "rsi_oversold":           35,
    "rsi_overbought":         65,
    "bb_period":              20,
    "bb_std_dev":             2.0,
    "candle_interval":        "1h",
    "trade_amount_inr":       1000,
    "check_interval_minutes": 60,
    "stop_on_profit":         False,
    "max_entries_per_day":    0,
    "active_from":            "00:00",
    "active_until":           "23:59",
}
