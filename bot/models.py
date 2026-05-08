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
# Zerodha credentials
# ---------------------------------------------------------------------------

class ZerodhaConfig(SingletonModel):
    user_id      = models.CharField(max_length=20, blank=True, verbose_name="User ID")
    password     = models.CharField(
        max_length=255, blank=True,
        verbose_name="Password",
        help_text="Stored as plaintext in SQLite. Keep db.sqlite3 out of version control.",
    )
    totp_secret  = models.CharField(
        max_length=100, blank=True,
        verbose_name="TOTP Secret (optional)",
        help_text=(
            "Base-32 TOTP setup key from Zerodha 2FA setup. "
            "Leave blank to be prompted for the 6-digit code when the bot starts."
        ),
    )

    class Meta:
        verbose_name        = "Zerodha Credentials"
        verbose_name_plural = "Zerodha Credentials"

    def __str__(self):
        return f"Zerodha Config ({self.user_id or 'not set'})"

    def to_dict(self) -> dict:
        return {
            "user_id":      self.user_id,
            "password":     self.password,
            "totp_secret":  self.totp_secret,
        }


# ---------------------------------------------------------------------------
# Risk management
# ---------------------------------------------------------------------------

class RiskConfig(SingletonModel):
    stop_loss_pct       = models.FloatField(
        default=1.5, verbose_name="Stop Loss %",
        help_text="Stop loss as % below (BUY) or above (SELL) entry price.",
    )
    target_pct          = models.FloatField(
        default=3.0, verbose_name="Target Profit %",
        help_text="Profit target as % above (BUY) or below (SELL) entry price.",
    )
    max_daily_loss      = models.FloatField(
        default=5000, verbose_name="Max Daily Loss (₹)",
        help_text="Halt all new trades for the day once cumulative loss exceeds this.",
    )
    max_open_positions  = models.IntegerField(
        default=5, verbose_name="Max Open Positions",
        help_text="Maximum number of concurrent open MIS positions.",
    )
    auto_squareoff_time = models.CharField(
        max_length=5, default="15:15", verbose_name="Auto Square-off Time (HH:MM IST)",
        help_text="All open positions will be squared off at this time daily.",
    )

    class Meta:
        verbose_name        = "Risk Configuration"
        verbose_name_plural = "Risk Configuration"

    def __str__(self):
        return f"Risk Config — SL {self.stop_loss_pct}%  Target {self.target_pct}%"

    def to_dict(self) -> dict:
        return {
            "stop_loss_pct":        self.stop_loss_pct,
            "target_pct":           self.target_pct,
            "max_daily_loss":       self.max_daily_loss,
            "max_open_positions":   self.max_open_positions,
            "auto_squareoff_time":  self.auto_squareoff_time,
        }


# ---------------------------------------------------------------------------
# Fixed Buy strategy
# ---------------------------------------------------------------------------

class FixedBuyConfig(SingletonModel):
    enabled    = models.BooleanField(default=True)
    order_type = models.CharField(
        max_length=10, default="MARKET",
        choices=[("MARKET", "Market"), ("LIMIT", "Limit")],
    )
    execute_at = models.CharField(
        max_length=5, default="09:21",
        verbose_name="Execute At (HH:MM IST)",
        help_text="Time to place the fixed buy orders. Typically 1–2 minutes after market open.",
    )

    class Meta:
        verbose_name        = "Fixed Buy Strategy"
        verbose_name_plural = "Fixed Buy Strategy"

    def __str__(self):
        return f"Fixed Buy — {'ON' if self.enabled else 'OFF'}  @ {self.execute_at}"

    def to_dict(self) -> dict:
        stocks = {
            s.symbol: {"quantity": s.quantity}
            for s in self.fixedbuystock_set.all()
        }
        return {
            "stocks":     stocks,
            "order_type": self.order_type,
            "execute_at": self.execute_at,
        }


class FixedBuyStock(models.Model):
    config   = models.ForeignKey(FixedBuyConfig, on_delete=models.CASCADE)
    symbol   = models.CharField(max_length=20, help_text="NSE trading symbol, e.g. MSUMI")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name        = "Stock"
        verbose_name_plural = "Stocks"
        unique_together     = ("config", "symbol")

    def __str__(self):
        return f"{self.symbol}  ×{self.quantity}"


# ---------------------------------------------------------------------------
# MA Crossover strategy
# ---------------------------------------------------------------------------

_INTERVAL_CHOICES = [
    ("minute",   "1 min"),
    ("3minute",  "3 min"),
    ("5minute",  "5 min"),
    ("10minute", "10 min"),
    ("15minute", "15 min"),
    ("30minute", "30 min"),
    ("60minute", "60 min"),
]


class MACrossoverConfig(SingletonModel):
    enabled                 = models.BooleanField(default=True)
    stocks                  = models.JSONField(
        default=list,
        help_text='JSON list of NSE symbols — e.g. ["MSUMI", "RELIANCE"]',
    )
    fast_period             = models.IntegerField(
        default=9, verbose_name="Fast EMA Period",
        help_text="Number of candles for the fast EMA (typically 9).",
    )
    slow_period             = models.IntegerField(
        default=21, verbose_name="Slow EMA Period",
        help_text="Number of candles for the slow EMA (typically 21).",
    )
    candle_interval         = models.CharField(
        max_length=20, default="5minute", choices=_INTERVAL_CHOICES,
    )
    quantity_per_stock      = models.IntegerField(default=1)
    check_interval_minutes  = models.IntegerField(
        default=5, verbose_name="Check Every (minutes)",
    )

    class Meta:
        verbose_name        = "MA Crossover Strategy"
        verbose_name_plural = "MA Crossover Strategy"

    def __str__(self):
        return (
            f"MA Crossover EMA({self.fast_period}/{self.slow_period}) "
            f"— {'ON' if self.enabled else 'OFF'}"
        )

    def to_dict(self) -> dict:
        return {
            "stocks":                 self.stocks,
            "fast_period":            self.fast_period,
            "slow_period":            self.slow_period,
            "candle_interval":        self.candle_interval,
            "quantity_per_stock":     self.quantity_per_stock,
            "check_interval_minutes": self.check_interval_minutes,
        }


# ---------------------------------------------------------------------------
# Open Range Breakout strategy
# ---------------------------------------------------------------------------

class OpenRangeConfig(SingletonModel):
    enabled                 = models.BooleanField(default=True)
    stocks                  = models.JSONField(
        default=list,
        help_text='JSON list of NSE symbols — e.g. ["MSUMI"]',
    )
    opening_range_minutes   = models.IntegerField(
        default=15, verbose_name="Opening Range (minutes)",
        help_text="High/low of the first N minutes forms the trading range. Default = 15 (9:15–9:30).",
    )
    quantity_per_stock      = models.IntegerField(default=1)
    check_interval_minutes  = models.IntegerField(default=1, verbose_name="Check Every (minutes)")
    allow_short             = models.BooleanField(
        default=False, verbose_name="Allow Short Selling",
        help_text="If enabled, places a SELL order when price breaks below the range low.",
    )

    class Meta:
        verbose_name        = "Open Range Breakout Strategy"
        verbose_name_plural = "Open Range Breakout Strategy"

    def __str__(self):
        return f"Open Range Breakout — {'ON' if self.enabled else 'OFF'}"

    def to_dict(self) -> dict:
        return {
            "stocks":                 self.stocks,
            "opening_range_minutes":  self.opening_range_minutes,
            "quantity_per_stock":     self.quantity_per_stock,
            "check_interval_minutes": self.check_interval_minutes,
            "allow_short":            self.allow_short,
        }


# ---------------------------------------------------------------------------
# Bollinger Band strategy
# ---------------------------------------------------------------------------

class BollingerConfig(SingletonModel):
    enabled                 = models.BooleanField(default=True)
    stocks                  = models.JSONField(
        default=list,
        help_text='JSON list of NSE symbols — e.g. ["MSUMI"]',
    )
    period                  = models.IntegerField(
        default=20, verbose_name="SMA Period",
        help_text="Lookback period for the simple moving average and standard deviation.",
    )
    std_dev                 = models.FloatField(
        default=2.0, verbose_name="Std Dev Multiplier",
        help_text="Band width = SMA ± (std_dev × StdDev). Standard value is 2.0.",
    )
    candle_interval         = models.CharField(
        max_length=20, default="5minute", choices=_INTERVAL_CHOICES,
    )
    quantity_per_stock      = models.IntegerField(default=1)
    check_interval_minutes  = models.IntegerField(default=5, verbose_name="Check Every (minutes)")
    allow_short             = models.BooleanField(
        default=False, verbose_name="Allow Short Selling",
        help_text="If enabled, places a SELL order when price crosses back below the upper band.",
    )

    class Meta:
        verbose_name        = "Bollinger Band Strategy"
        verbose_name_plural = "Bollinger Band Strategy"

    def __str__(self):
        return f"Bollinger Band SMA({self.period}) — {'ON' if self.enabled else 'OFF'}"

    def to_dict(self) -> dict:
        return {
            "stocks":                 self.stocks,
            "period":                 self.period,
            "std_dev":                float(self.std_dev),
            "candle_interval":        self.candle_interval,
            "quantity_per_stock":     self.quantity_per_stock,
            "check_interval_minutes": self.check_interval_minutes,
            "allow_short":            self.allow_short,
        }


# ---------------------------------------------------------------------------
# Bot process control
# ---------------------------------------------------------------------------

class BotControl(SingletonModel):
    is_running = models.BooleanField(default=False)
    pid        = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Bot Control"
        verbose_name_plural = "Bot Control"

    def __str__(self):
        return "Running" if self.is_running else "Stopped"


# ---------------------------------------------------------------------------
# Trade log — written by LoggingTrader, read-only in admin
# ---------------------------------------------------------------------------

class TradeLog(models.Model):
    timestamp        = models.DateTimeField(auto_now_add=True)
    strategy         = models.CharField(max_length=30, blank=True)
    symbol           = models.CharField(max_length=20)
    transaction_type = models.CharField(max_length=4)   # BUY / SELL
    quantity         = models.IntegerField()
    order_type       = models.CharField(max_length=10, default="MARKET")
    order_id         = models.CharField(max_length=50, blank=True)
    tag              = models.CharField(max_length=20, blank=True)
    status           = models.CharField(max_length=20, default="PLACED")
    notes            = models.TextField(blank=True)

    class Meta:
        ordering            = ["-timestamp"]
        verbose_name        = "Trade"
        verbose_name_plural = "Trade Log"

    def __str__(self):
        return (
            f"{self.timestamp.strftime('%d %b %H:%M')}  "
            f"{self.transaction_type} {self.symbol} ×{self.quantity}"
        )
