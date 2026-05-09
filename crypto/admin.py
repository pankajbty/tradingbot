from __future__ import annotations

from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    CryptoBotControl,
    CryptoExchangeConfig,
    CryptoRiskConfig,
    CryptoTradeLog,
    EMACrossoverConfig,
    RSIBBConfig,
    SupertrendConfig,
)


# ---------------------------------------------------------------------------
# Singleton admin base
# ---------------------------------------------------------------------------

class SingletonModelAdmin(admin.ModelAdmin):
    """
    Shared base for all singleton config models.
    - Hides the Add / Delete buttons.
    - Redirects the change-list straight to the single object's edit page.
    """

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        try:
            obj = self.model.load()
            url = reverse(
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                args=[obj.pk],
            )
            return HttpResponseRedirect(url)
        except Exception:
            return super().changelist_view(request, extra_context)


# ---------------------------------------------------------------------------
# Exchange configuration
# ---------------------------------------------------------------------------

class CryptoExchangeConfigForm(forms.ModelForm):
    api_secret = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Exchange API secret. Stored as plaintext in SQLite. Keep db.sqlite3 out of version control.",
    )

    class Meta:
        model  = CryptoExchangeConfig
        fields = "__all__"


@admin.register(CryptoExchangeConfig)
class CryptoExchangeConfigAdmin(SingletonModelAdmin):
    form = CryptoExchangeConfigForm
    fieldsets = [
        ("Exchange Selection", {
            "fields": ["exchange_id", "testnet"],
            "description": (
                "Choose the exchange and whether to connect to the live or sandbox environment. "
                "Supported: CoinDCX, WazirX, Binance (via ccxt)."
            ),
        }),
        ("API Credentials", {
            "fields": ["api_key", "api_secret"],
            "description": (
                "API key and secret from your exchange account. "
                "Required before starting the crypto bot. "
                "Stored in SQLite — keep db.sqlite3 out of version control."
            ),
        }),
    ]


# ---------------------------------------------------------------------------
# Risk configuration
# ---------------------------------------------------------------------------

@admin.register(CryptoRiskConfig)
class CryptoRiskConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Per-Trade Risk", {
            "fields": ["stop_loss_pct", "target_pct"],
            "description": "Applied to every trade placed by any crypto strategy.",
        }),
        ("Daily Limits", {
            "fields": ["max_daily_loss"],
            "description": (
                "When cumulative daily P&L drops below -max_daily_loss, "
                "all new trades are halted and open positions are squared off."
            ),
        }),
        ("Position Sizing", {
            "fields": ["trade_amount_inr", "max_open_positions"],
            "description": (
                "trade_amount_inr is the default INR amount per trade. "
                "Individual strategies can override this in their own config."
            ),
        }),
        ("Daily Reset", {
            "fields": ["daily_reset_hour"],
            "description": (
                "IST hour at which the daily P&L counter and trading halt are cleared. "
                "0 = midnight (recommended). Change if you prefer a different reset time."
            ),
        }),
    ]


# ---------------------------------------------------------------------------
# EMA Crossover strategy
# ---------------------------------------------------------------------------

@admin.register(EMACrossoverConfig)
class EMACrossoverConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled"]}),
        ("Symbols", {
            "fields": ["symbols"],
            "description": 'Enter as a JSON list, e.g. ["BTC/INR", "ETH/INR"]',
        }),
        ("EMA Parameters", {
            "fields": ["fast_period", "slow_period", "trend_period", "candle_interval"],
            "description": (
                "BUY when fast EMA crosses above slow EMA AND price is above trend EMA. "
                "SELL when fast EMA crosses below slow EMA. "
                "The trend EMA (55) prevents counter-trend trades."
            ),
        }),
        ("Scheduling", {
            "fields": ["check_interval_minutes", "trade_amount_inr"],
        }),
        ("Re-entry / Trade Until Profit", {
            "fields": ["stop_on_profit", "max_entries_per_day"],
            "description": (
                "Enable 'Trade Until Profit' to wait for each position to close before "
                "looking for the next crossover signal, and stop for the day once a trade "
                "closes profitably. Set 'Max Entries Per Day' to cap losses (e.g. 3-5). "
                "0 = unlimited."
            ),
        }),
        ("Active Hours", {
            "fields": ["active_from", "active_until"],
            "description": (
                "Strategy fires only within this daily time window. "
                "Crypto markets are 24/7 — default is 00:00-23:59 (always active). "
                "Narrow this window to trade only during high-liquidity hours if desired."
            ),
        }),
    ]


# ---------------------------------------------------------------------------
# Supertrend strategy
# ---------------------------------------------------------------------------

@admin.register(SupertrendConfig)
class SupertrendConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled"]}),
        ("Symbols", {
            "fields": ["symbols"],
            "description": 'Enter as a JSON list, e.g. ["BTC/INR", "ETH/INR", "SOL/INR"]',
        }),
        ("Supertrend Parameters", {
            "fields": ["atr_period", "multiplier", "candle_interval"],
            "description": (
                "Supertrend = (high+low)/2 +/- multiplier x ATR(atr_period). "
                "BUY when price crosses above the Supertrend line. "
                "SELL when price crosses below it. "
                "Community-proven defaults for 15m crypto: ATR=10, multiplier=3.0."
            ),
        }),
        ("Scheduling", {
            "fields": ["check_interval_minutes", "trade_amount_inr"],
        }),
        ("Re-entry / Trade Until Profit", {
            "fields": ["stop_on_profit", "max_entries_per_day"],
            "description": (
                "Enable 'Trade Until Profit' to keep re-entering after a stop-loss "
                "until a trade closes profitably, then stop for the day. "
                "Set 'Max Entries Per Day' to limit attempts (e.g. 3-5). 0 = unlimited."
            ),
        }),
        ("Active Hours", {
            "fields": ["active_from", "active_until"],
            "description": (
                "Strategy fires only within this daily time window. "
                "Default: 00:00-23:59 (24/7). "
            ),
        }),
    ]


# ---------------------------------------------------------------------------
# RSI + Bollinger Band strategy
# ---------------------------------------------------------------------------

@admin.register(RSIBBConfig)
class RSIBBConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled", "allow_short"]}),
        ("Symbols", {
            "fields": ["symbols"],
            "description": 'Enter as a JSON list, e.g. ["BTC/INR", "ETH/INR"]',
        }),
        ("RSI Parameters", {
            "fields": ["rsi_period", "rsi_oversold", "rsi_overbought"],
            "description": (
                "BUY when RSI < rsi_oversold (default: 35). "
                "SELL when RSI > rsi_overbought (default: 65). "
                "These thresholds are deliberately tighter than equities (30/70) to suit crypto volatility."
            ),
        }),
        ("Bollinger Band Parameters", {
            "fields": ["bb_period", "bb_std_dev"],
            "description": (
                "BUY signal also requires price <= lower Bollinger Band (statistical oversold). "
                "SELL signal also requires price >= upper Bollinger Band (statistical overbought). "
                "Classic setting: period=20, std_dev=2.0."
            ),
        }),
        ("Scheduling", {
            "fields": ["check_interval_minutes", "candle_interval", "trade_amount_inr"],
            "description": "RSI+BB works best on higher timeframes (1h). Recommended check interval: 60 min.",
        }),
        ("Re-entry / Trade Until Profit", {
            "fields": ["stop_on_profit", "max_entries_per_day"],
            "description": (
                "Enable 'Trade Until Profit' to keep re-entering after a stop-loss "
                "until a trade closes profitably, then stop for the day. "
                "Set 'Max Entries Per Day' to limit attempts. 0 = unlimited."
            ),
        }),
        ("Active Hours", {
            "fields": ["active_from", "active_until"],
            "description": "Default: 00:00-23:59 (24/7 for crypto).",
        }),
    ]


# ---------------------------------------------------------------------------
# Crypto Trade Log (read-only)
# ---------------------------------------------------------------------------

@admin.register(CryptoTradeLog)
class CryptoTradeLogAdmin(admin.ModelAdmin):
    list_display    = [
        "timestamp", "strategy_badge", "side_badge",
        "symbol", "quantity_display", "price", "amount_inr", "order_id", "status_badge",
    ]
    list_filter     = ["strategy", "side", "status"]
    search_fields   = ["symbol", "order_id", "tag"]
    date_hierarchy  = "timestamp"
    readonly_fields = [f.name for f in CryptoTradeLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # -- coloured badges ------------------------------------------------

    def strategy_badge(self, obj):
        colours = {
            "ema_crossover": "#0d6efd",
            "supertrend":    "#fd7e14",
            "rsi_bb":        "#6f42c1",
        }
        colour = colours.get(obj.strategy, "#adb5bd")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colour, obj.strategy or "—",
        )
    strategy_badge.short_description = "Strategy"

    def side_badge(self, obj):
        colour = "#198754" if obj.side == "BUY" else "#dc3545"
        return format_html(
            '<strong style="color:{}">{}</strong>', colour, obj.side,
        )
    side_badge.short_description = "Side"

    def quantity_display(self, obj):
        return f"{obj.quantity:.8f}"
    quantity_display.short_description = "Quantity"

    def status_badge(self, obj):
        colour = "#198754" if obj.status == "PLACED" else "#dc3545"
        return format_html(
            '<span style="color:{}">{}</span>', colour, obj.status,
        )
    status_badge.short_description = "Status"


# ---------------------------------------------------------------------------
# Crypto Bot Control — redirects changelist straight to the custom control page
# ---------------------------------------------------------------------------

@admin.register(CryptoBotControl)
class CryptoBotControlAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("crypto:control"))
