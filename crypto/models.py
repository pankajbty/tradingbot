from __future__ import annotations

import datetime
from django.db import models


# ---------------------------------------------------------------------------
# Singleton base — only one row allowed per table
# ---------------------------------------------------------------------------

class SingletonModel(models.Model):
    """
    Abstract base that enforces exactly one configuration row per table.
    Saving always upserts to pk=1. Deletion is disabled.
    Use MyModel.load() to get (or create with defaults) the single instance.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # prevent accidental deletion

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ---------------------------------------------------------------------------
# Interval choices for crypto (ccxt timeframe strings)
# ---------------------------------------------------------------------------

_CRYPTO_INTERVAL_CHOICES = [
    ("1m",  "1 min"),
    ("3m",  "3 min"),
    ("5m",  "5 min"),
    ("15m", "15 min"),
    ("30m", "30 min"),
    ("1h",  "1 hour"),
    ("2h",  "2 hours"),
    ("4h",  "4 hours"),
    ("1d",  "1 day"),
]

_EXCHANGE_CHOICES = [
    ("coindcx", "CoinDCX"),
    ("wazirx",  "WazirX"),
    ("binance",  "Binance"),
]


# ---------------------------------------------------------------------------
# Exchange configuration
# ---------------------------------------------------------------------------

class CryptoExchangeConfig(SingletonModel):
    exchange_id = models.CharField(
        max_length=30,
        default="coindcx",
        choices=_EXCHANGE_CHOICES,
        verbose_name="Exchange",
        help_text="The ccxt exchange identifier to use.",
    )
    api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="API Key",
        help_text="Exchange API key. Stored in SQLite — keep db.sqlite3 out of version control.",
    )
    api_secret = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="API Secret",
        help_text="Exchange API secret.",
    )
    testnet = models.BooleanField(
        default=False,
        verbose_name="Use Testnet",
        help_text="If enabled, connect to the exchange's sandbox/testnet environment.",
    )

    class Meta:
        verbose_name        = "Exchange Configuration"
        verbose_name_plural = "Exchange Configuration"

    def __str__(self):
        return f"Crypto Exchange: {self.exchange_id} ({'testnet' if self.testnet else 'live'})"

    def to_dict(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "api_key":     self.api_key,
            "api_secret":  self.api_secret,
            "testnet":     self.testnet,
        }


# ---------------------------------------------------------------------------
# Risk management
# ---------------------------------------------------------------------------

class CryptoRiskConfig(SingletonModel):
    stop_loss_pct = models.FloatField(
        default=2.0,
        verbose_name="Stop Loss %",
        help_text="Stop loss as % below (BUY) or above (SELL) entry price.",
    )
    target_pct = models.FloatField(
        default=4.0,
        verbose_name="Target Profit %",
        help_text="Profit target as % above (BUY) or below (SELL) entry price.",
    )
    max_daily_loss = models.FloatField(
        default=5000,
        verbose_name="Max Daily Loss (Rs)",
        help_text="Halt all new trades for the day once cumulative loss exceeds this.",
    )
    max_open_positions = models.IntegerField(
        default=3,
        verbose_name="Max Open Positions",
        help_text="Maximum number of concurrent open crypto positions.",
    )
    trade_amount_inr = models.FloatField(
        default=1000,
        verbose_name="Trade Amount (Rs)",
        help_text="Default INR amount per trade for position sizing.",
    )
    daily_reset_hour = models.IntegerField(
        default=0,
        verbose_name="Daily Reset Hour (IST)",
        help_text="IST hour at which daily P&L counter and halt flag are reset. 0 = midnight.",
    )

    class Meta:
        verbose_name        = "Risk Configuration"
        verbose_name_plural = "Risk Configuration"

    def __str__(self):
        return f"Crypto Risk Config — SL {self.stop_loss_pct}%  Target {self.target_pct}%"

    def to_dict(self) -> dict:
        return {
            "stop_loss_pct":      self.stop_loss_pct,
            "target_pct":         self.target_pct,
            "max_daily_loss":     self.max_daily_loss,
            "max_open_positions": self.max_open_positions,
            "trade_amount_inr":   self.trade_amount_inr,
            "daily_reset_hour":   self.daily_reset_hour,
        }


# ---------------------------------------------------------------------------
# EMA Crossover strategy
# ---------------------------------------------------------------------------

class EMACrossoverConfig(SingletonModel):
    enabled = models.BooleanField(default=True)
    symbols = models.JSONField(
        default=list,
        help_text='JSON list of ccxt symbols — e.g. ["BTC/INR", "ETH/INR"]',
    )
    fast_period = models.IntegerField(
        default=9,
        verbose_name="Fast EMA Period",
        help_text="Number of candles for the fast EMA (typically 9).",
    )
    slow_period = models.IntegerField(
        default=21,
        verbose_name="Slow EMA Period",
        help_text="Number of candles for the slow EMA (typically 21).",
    )
    trend_period = models.IntegerField(
        default=55,
        verbose_name="Trend EMA Period",
        help_text="Long-term EMA used as a trend filter. Only BUY when price > trend EMA.",
    )
    candle_interval = models.CharField(
        max_length=10,
        default="15m",
        choices=_CRYPTO_INTERVAL_CHOICES,
        verbose_name="Candle Interval",
    )
    trade_amount_inr = models.FloatField(
        default=1000,
        verbose_name="Trade Amount (Rs)",
        help_text="INR amount per trade. Overrides the global risk config for this strategy.",
    )
    check_interval_minutes = models.IntegerField(
        default=15,
        verbose_name="Check Every (minutes)",
    )
    stop_on_profit = models.BooleanField(
        default=False,
        verbose_name="Trade Until Profit",
        help_text=(
            "Wait for each position to close before looking for the next crossover. "
            "Stop trading for the day once a trade closes profitably."
        ),
    )
    max_entries_per_day = models.IntegerField(
        default=0,
        verbose_name="Max Entries Per Day",
        help_text="Max entry attempts per symbol per day. 0 = unlimited.",
    )
    active_from = models.TimeField(
        default=datetime.time(0, 0),
        verbose_name="Active From (HH:MM)",
        help_text="Strategy will not run before this time. Crypto is 24/7 — use 00:00.",
    )
    active_until = models.TimeField(
        default=datetime.time(23, 59),
        verbose_name="Active Until (HH:MM)",
        help_text="Strategy will not run after this time. Crypto is 24/7 — use 23:59.",
    )

    class Meta:
        verbose_name        = "EMA Crossover Strategy"
        verbose_name_plural = "EMA Crossover Strategy"

    def __str__(self):
        return (
            f"EMA Crossover ({self.fast_period}/{self.slow_period}/{self.trend_period}) "
            f"— {'ON' if self.enabled else 'OFF'}"
        )

    def to_dict(self) -> dict:
        return {
            "symbols":                self.symbols,
            "fast_period":            self.fast_period,
            "slow_period":            self.slow_period,
            "trend_period":           self.trend_period,
            "candle_interval":        self.candle_interval,
            "trade_amount_inr":       self.trade_amount_inr,
            "check_interval_minutes": self.check_interval_minutes,
            "stop_on_profit":         self.stop_on_profit,
            "max_entries_per_day":    self.max_entries_per_day,
            "active_from":            self.active_from.strftime("%H:%M"),
            "active_until":           self.active_until.strftime("%H:%M"),
        }


# ---------------------------------------------------------------------------
# Supertrend strategy
# ---------------------------------------------------------------------------

class SupertrendConfig(SingletonModel):
    enabled = models.BooleanField(default=True)
    symbols = models.JSONField(
        default=list,
        help_text='JSON list of ccxt symbols — e.g. ["BTC/INR", "ETH/INR", "SOL/INR"]',
    )
    atr_period = models.IntegerField(
        default=10,
        verbose_name="ATR Period",
        help_text="Lookback period for the Average True Range calculation.",
    )
    multiplier = models.FloatField(
        default=3.0,
        verbose_name="ATR Multiplier",
        help_text="Band width = (high+low)/2 +/- multiplier x ATR. Standard: 3.0.",
    )
    candle_interval = models.CharField(
        max_length=10,
        default="15m",
        choices=_CRYPTO_INTERVAL_CHOICES,
        verbose_name="Candle Interval",
    )
    trade_amount_inr = models.FloatField(
        default=1000,
        verbose_name="Trade Amount (Rs)",
        help_text="INR amount per trade.",
    )
    check_interval_minutes = models.IntegerField(
        default=15,
        verbose_name="Check Every (minutes)",
    )
    stop_on_profit = models.BooleanField(
        default=False,
        verbose_name="Trade Until Profit",
        help_text=(
            "Wait for each position to close before looking for the next signal. "
            "Stop for the day once a trade closes profitably."
        ),
    )
    max_entries_per_day = models.IntegerField(
        default=0,
        verbose_name="Max Entries Per Day",
        help_text="Max entry attempts per symbol per day. 0 = unlimited.",
    )
    active_from = models.TimeField(
        default=datetime.time(0, 0),
        verbose_name="Active From (HH:MM)",
    )
    active_until = models.TimeField(
        default=datetime.time(23, 59),
        verbose_name="Active Until (HH:MM)",
    )

    class Meta:
        verbose_name        = "Supertrend Strategy"
        verbose_name_plural = "Supertrend Strategy"

    def __str__(self):
        return (
            f"Supertrend ATR({self.atr_period}) x{self.multiplier} "
            f"— {'ON' if self.enabled else 'OFF'}"
        )

    def to_dict(self) -> dict:
        return {
            "symbols":                self.symbols,
            "atr_period":             self.atr_period,
            "multiplier":             float(self.multiplier),
            "candle_interval":        self.candle_interval,
            "trade_amount_inr":       self.trade_amount_inr,
            "check_interval_minutes": self.check_interval_minutes,
            "stop_on_profit":         self.stop_on_profit,
            "max_entries_per_day":    self.max_entries_per_day,
            "active_from":            self.active_from.strftime("%H:%M"),
            "active_until":           self.active_until.strftime("%H:%M"),
        }


# ---------------------------------------------------------------------------
# RSI + Bollinger Band strategy
# ---------------------------------------------------------------------------

class RSIBBConfig(SingletonModel):
    enabled = models.BooleanField(default=True)
    symbols = models.JSONField(
        default=list,
        help_text='JSON list of ccxt symbols — e.g. ["BTC/INR", "ETH/INR"]',
    )
    rsi_period = models.IntegerField(
        default=14,
        verbose_name="RSI Period",
        help_text="Lookback period for the RSI calculation.",
    )
    rsi_oversold = models.IntegerField(
        default=35,
        verbose_name="RSI Oversold Threshold",
        help_text="BUY when RSI falls below this value. Standard crypto setting: 35.",
    )
    rsi_overbought = models.IntegerField(
        default=65,
        verbose_name="RSI Overbought Threshold",
        help_text="SELL when RSI rises above this value. Standard crypto setting: 65.",
    )
    bb_period = models.IntegerField(
        default=20,
        verbose_name="Bollinger Band Period",
        help_text="Lookback period for the Bollinger Band SMA and standard deviation.",
    )
    bb_std_dev = models.FloatField(
        default=2.0,
        verbose_name="Bollinger Band Std Dev",
        help_text="Band width = SMA +/- std_dev x StdDev. Standard value: 2.0.",
    )
    allow_short = models.BooleanField(
        default=False,
        verbose_name="Allow Short Selling",
        help_text=(
            "If enabled, places a SELL order when overbought signal fires even without a prior long. "
            "Leave disabled for long-only operation."
        ),
    )
    candle_interval = models.CharField(
        max_length=10,
        default="1h",
        choices=_CRYPTO_INTERVAL_CHOICES,
        verbose_name="Candle Interval",
    )
    trade_amount_inr = models.FloatField(
        default=1000,
        verbose_name="Trade Amount (Rs)",
        help_text="INR amount per trade.",
    )
    check_interval_minutes = models.IntegerField(
        default=60,
        verbose_name="Check Every (minutes)",
    )
    stop_on_profit = models.BooleanField(
        default=False,
        verbose_name="Trade Until Profit",
        help_text=(
            "Wait for each position to close before looking for the next signal. "
            "Stop for the day once a trade closes profitably."
        ),
    )
    max_entries_per_day = models.IntegerField(
        default=0,
        verbose_name="Max Entries Per Day",
        help_text="Max entry attempts per symbol per day. 0 = unlimited.",
    )
    active_from = models.TimeField(
        default=datetime.time(0, 0),
        verbose_name="Active From (HH:MM)",
    )
    active_until = models.TimeField(
        default=datetime.time(23, 59),
        verbose_name="Active Until (HH:MM)",
    )

    class Meta:
        verbose_name        = "RSI + Bollinger Band Strategy"
        verbose_name_plural = "RSI + Bollinger Band Strategy"

    def __str__(self):
        return (
            f"RSI({self.rsi_period}) + BB({self.bb_period}) "
            f"— {'ON' if self.enabled else 'OFF'}"
        )

    def to_dict(self) -> dict:
        return {
            "symbols":                self.symbols,
            "rsi_period":             self.rsi_period,
            "rsi_oversold":           self.rsi_oversold,
            "rsi_overbought":         self.rsi_overbought,
            "bb_period":              self.bb_period,
            "bb_std_dev":             float(self.bb_std_dev),
            "allow_short":            self.allow_short,
            "candle_interval":        self.candle_interval,
            "trade_amount_inr":       self.trade_amount_inr,
            "check_interval_minutes": self.check_interval_minutes,
            "stop_on_profit":         self.stop_on_profit,
            "max_entries_per_day":    self.max_entries_per_day,
            "active_from":            self.active_from.strftime("%H:%M"),
            "active_until":           self.active_until.strftime("%H:%M"),
        }


# ---------------------------------------------------------------------------
# Crypto Bot process control
# ---------------------------------------------------------------------------

class CryptoBotControl(SingletonModel):
    is_running = models.BooleanField(default=False)
    pid        = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Crypto Bot Control"
        verbose_name_plural = "Crypto Bot Control"

    def __str__(self):
        return "Running" if self.is_running else "Stopped"


# ---------------------------------------------------------------------------
# Crypto Trade Log — written by LoggingCryptoTrader, read-only in admin
# ---------------------------------------------------------------------------

class CryptoTradeLog(models.Model):
    timestamp  = models.DateTimeField(auto_now_add=True)
    strategy   = models.CharField(max_length=30, blank=True)
    symbol     = models.CharField(max_length=20)
    side       = models.CharField(max_length=4)    # BUY / SELL
    quantity   = models.FloatField(default=0.0)
    price      = models.FloatField(default=0.0)
    amount_inr = models.FloatField(default=0.0)
    order_id   = models.CharField(max_length=100, blank=True)
    tag        = models.CharField(max_length=30, blank=True)
    status     = models.CharField(max_length=20, default="PLACED")
    notes      = models.TextField(blank=True)

    class Meta:
        ordering            = ["-timestamp"]
        verbose_name        = "Crypto Trade"
        verbose_name_plural = "Crypto Trade Log"

    def __str__(self):
        return (
            f"{self.timestamp.strftime('%d %b %H:%M')}  "
            f"{self.side} {self.symbol}  qty={self.quantity:.8f}"
        )
