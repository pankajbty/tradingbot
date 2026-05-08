from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    BollingerConfig,
    BotControl,
    FixedBuyConfig,
    FixedBuyStock,
    MACrossoverConfig,
    OpenRangeConfig,
    RiskConfig,
    TradeLog,
    ZerodhaConfig,
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
# Zerodha credentials
# ---------------------------------------------------------------------------

class ZerodhaConfigForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Stored as plaintext in SQLite. Keep db.sqlite3 out of version control.",
    )

    class Meta:
        model  = ZerodhaConfig
        fields = "__all__"


@admin.register(ZerodhaConfig)
class ZerodhaConfigAdmin(SingletonModelAdmin):
    form = ZerodhaConfigForm
    fieldsets = [
        ("Login Credentials", {
            "fields": ["user_id", "password"],
            "description": (
                "Zerodha web login credentials. "
                "The TOTP code is entered manually each time you start the bot."
            ),
        }),
        ("TOTP (optional)", {
            "fields": ["totp_secret"],
            "classes": ["collapse"],
            "description": (
                "Provide your base-32 TOTP setup key here to skip the manual "
                "6-digit code prompt at bot startup. Leave blank to be prompted."
            ),
        }),
    ]


# ---------------------------------------------------------------------------
# Risk configuration
# ---------------------------------------------------------------------------

@admin.register(RiskConfig)
class RiskConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Per-Trade Risk", {
            "fields": ["stop_loss_pct", "target_pct"],
            "description": "Applied to every trade placed by any strategy.",
        }),
        ("Daily Limits", {
            "fields": ["max_daily_loss", "max_open_positions"],
        }),
        ("Timing", {
            "fields": ["auto_squareoff_time"],
            "description": "All open MIS positions will be closed at this time.",
        }),
    ]


# ---------------------------------------------------------------------------
# Fixed Buy strategy
# ---------------------------------------------------------------------------

class FixedBuyStockInline(admin.TabularInline):
    model      = FixedBuyStock
    extra      = 1
    min_num    = 0
    can_delete = True
    fields     = ["symbol", "quantity"]


@admin.register(FixedBuyConfig)
class FixedBuyConfigAdmin(SingletonModelAdmin):
    inlines = [FixedBuyStockInline]
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled"]}),
        ("Order Settings", {"fields": ["order_type", "execute_at"]}),
    ]


# ---------------------------------------------------------------------------
# MA Crossover strategy
# ---------------------------------------------------------------------------

@admin.register(MACrossoverConfig)
class MACrossoverConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled"]}),
        ("Stocks", {
            "fields": ["stocks", "quantity_per_stock"],
            "description": 'Enter as a JSON list, e.g. ["MSUMI", "RELIANCE"]',
        }),
        ("EMA Parameters", {"fields": ["fast_period", "slow_period", "candle_interval"]}),
        ("Scheduling", {"fields": ["check_interval_minutes"]}),
    ]


# ---------------------------------------------------------------------------
# Open Range Breakout strategy
# ---------------------------------------------------------------------------

@admin.register(OpenRangeConfig)
class OpenRangeConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled", "allow_short"]}),
        ("Stocks", {
            "fields": ["stocks", "quantity_per_stock"],
            "description": 'Enter as a JSON list, e.g. ["MSUMI"]',
        }),
        ("Range & Scheduling", {
            "fields": ["opening_range_minutes", "check_interval_minutes"],
            "description": (
                "Opening range = high/low of the first N minutes (9:15 to 9:15+N). "
                "Buy when price breaks above range high; sell (if allow_short) on breakdown."
            ),
        }),
    ]


# ---------------------------------------------------------------------------
# Bollinger Band strategy
# ---------------------------------------------------------------------------

@admin.register(BollingerConfig)
class BollingerConfigAdmin(SingletonModelAdmin):
    fieldsets = [
        ("Strategy Toggle", {"fields": ["enabled", "allow_short"]}),
        ("Stocks", {
            "fields": ["stocks", "quantity_per_stock"],
            "description": 'Enter as a JSON list, e.g. ["MSUMI"]',
        }),
        ("Band Parameters", {
            "fields": ["period", "std_dev", "candle_interval"],
            "description": "Bands = SMA(period) ± std_dev × StdDev(period). Classic setting: period=20, std_dev=2.0.",
        }),
        ("Scheduling", {"fields": ["check_interval_minutes"]}),
    ]


# ---------------------------------------------------------------------------
# Trade log (read-only)
# ---------------------------------------------------------------------------

@admin.register(TradeLog)
class TradeLogAdmin(admin.ModelAdmin):
    list_display    = [
        "timestamp", "strategy_badge", "transaction_type_badge",
        "symbol", "quantity", "order_type", "order_id", "status_badge",
    ]
    list_filter     = ["strategy", "transaction_type", "status", "order_type"]
    search_fields   = ["symbol", "order_id", "tag"]
    date_hierarchy  = "timestamp"
    readonly_fields = [f.name for f in TradeLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # -- coloured badges ------------------------------------------------

    def strategy_badge(self, obj):
        colours = {
            "fixed_buy":           "#6c757d",
            "ma_crossover":        "#0d6efd",
            "open_range_breakout": "#fd7e14",
            "bollinger":           "#6f42c1",
        }
        colour = colours.get(obj.strategy, "#adb5bd")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colour, obj.strategy or "—",
        )
    strategy_badge.short_description = "Strategy"

    def transaction_type_badge(self, obj):
        colour = "#198754" if obj.transaction_type == "BUY" else "#dc3545"
        return format_html(
            '<strong style="color:{}">{}</strong>', colour, obj.transaction_type,
        )
    transaction_type_badge.short_description = "Side"

    def status_badge(self, obj):
        colour = "#198754" if obj.status == "PLACED" else "#dc3545"
        return format_html(
            '<span style="color:{}">{}</span>', colour, obj.status,
        )
    status_badge.short_description = "Status"


# ---------------------------------------------------------------------------
# Bot Control — redirects changelist straight to the custom control page
# ---------------------------------------------------------------------------

@admin.register(BotControl)
class BotControlAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("bot:control"))
