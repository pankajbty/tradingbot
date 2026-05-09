"""
python manage.py seed_config

Populates the database with default values from config.py.
Safe to re-run — skips tables that already have a row.
"""
from django.core.management.base import BaseCommand

import config as C
from bot.models import (
    BollingerConfig,
    FixedBuyConfig,
    FixedBuyStock,
    MACrossoverConfig,
    OpenRangeConfig,
    RiskConfig,
    ZerodhaConfig,
)


class Command(BaseCommand):
    help = "Seed the database with default strategy configs from config.py"

    def handle(self, *args, **options):
        self._seed_zerodha()
        self._seed_risk()
        self._seed_fixed_buy()
        self._seed_ma_crossover()
        self._seed_open_range()
        self._seed_bollinger()
        self.stdout.write(self.style.SUCCESS("✅  Database seeded with default configuration."))
        self.stdout.write(
            "   Open http://127.0.0.1:8000/admin/ to review and update settings."
        )

    # ------------------------------------------------------------------

    def _seed_zerodha(self):
        obj, created = ZerodhaConfig.objects.get_or_create(pk=1)
        if created:
            obj.user_id     = C.ZERODHA_CONFIG.get("user_id", "")
            obj.password    = C.ZERODHA_CONFIG.get("password", "")
            obj.totp_secret = C.ZERODHA_CONFIG.get("totp_secret", "")
            obj.save()
            self.stdout.write("  Created ZerodhaConfig")
        else:
            self.stdout.write("  ZerodhaConfig already exists — skipped")

    def _seed_risk(self):
        obj, created = RiskConfig.objects.get_or_create(pk=1)
        if created:
            obj.stop_loss_pct       = C.RISK_CONFIG["stop_loss_pct"]
            obj.target_pct          = C.RISK_CONFIG["target_pct"]
            obj.max_daily_loss      = C.RISK_CONFIG["max_daily_loss"]
            obj.max_open_positions  = C.RISK_CONFIG["max_open_positions"]
            obj.auto_squareoff_time = C.RISK_CONFIG["auto_squareoff_time"]
            obj.save()
            self.stdout.write("  Created RiskConfig")
        else:
            self.stdout.write("  RiskConfig already exists — skipped")

    def _seed_fixed_buy(self):
        obj, created = FixedBuyConfig.objects.get_or_create(pk=1)
        if created:
            obj.order_type = C.FIXED_BUY_CONFIG.get("order_type", "MARKET")
            obj.execute_at = C.FIXED_BUY_CONFIG.get("execute_at", "09:21")
            obj.save()
            for symbol, params in C.FIXED_BUY_CONFIG["stocks"].items():
                FixedBuyStock.objects.create(
                    config=obj, symbol=symbol, quantity=params["quantity"]
                )
            self.stdout.write("  Created FixedBuyConfig")
        else:
            self.stdout.write("  FixedBuyConfig already exists — skipped")

    def _seed_ma_crossover(self):
        obj, created = MACrossoverConfig.objects.get_or_create(pk=1)
        if created:
            obj.stocks                  = C.MA_CROSSOVER_CONFIG["stocks"]
            obj.fast_period             = C.MA_CROSSOVER_CONFIG["fast_period"]
            obj.slow_period             = C.MA_CROSSOVER_CONFIG["slow_period"]
            obj.candle_interval         = C.MA_CROSSOVER_CONFIG["candle_interval"]
            obj.quantity_per_stock      = C.MA_CROSSOVER_CONFIG["quantity_per_stock"]
            obj.check_interval_minutes  = C.MA_CROSSOVER_CONFIG["check_interval_minutes"]
            obj.save()
            self.stdout.write("  Created MACrossoverConfig")
        else:
            self.stdout.write("  MACrossoverConfig already exists — skipped")

    def _seed_open_range(self):
        obj, created = OpenRangeConfig.objects.get_or_create(pk=1)
        if created:
            obj.stocks                  = C.OPEN_RANGE_CONFIG["stocks"]
            obj.opening_range_minutes   = C.OPEN_RANGE_CONFIG["opening_range_minutes"]
            obj.quantity_per_stock      = C.OPEN_RANGE_CONFIG["quantity_per_stock"]
            obj.check_interval_minutes  = C.OPEN_RANGE_CONFIG["check_interval_minutes"]
            obj.allow_short             = C.OPEN_RANGE_CONFIG.get("allow_short", False)
            obj.stop_on_profit          = C.OPEN_RANGE_CONFIG.get("stop_on_profit", False)
            obj.max_entries_per_day     = C.OPEN_RANGE_CONFIG.get("max_entries_per_day", 1)
            obj.save()
            self.stdout.write("  Created OpenRangeConfig")
        else:
            self.stdout.write("  OpenRangeConfig already exists — skipped")

    def _seed_bollinger(self):
        obj, created = BollingerConfig.objects.get_or_create(pk=1)
        if created:
            obj.stocks                  = C.BOLLINGER_CONFIG["stocks"]
            obj.period                  = C.BOLLINGER_CONFIG["period"]
            obj.std_dev                 = C.BOLLINGER_CONFIG["std_dev"]
            obj.candle_interval         = C.BOLLINGER_CONFIG["candle_interval"]
            obj.quantity_per_stock      = C.BOLLINGER_CONFIG["quantity_per_stock"]
            obj.check_interval_minutes  = C.BOLLINGER_CONFIG["check_interval_minutes"]
            obj.allow_short             = C.BOLLINGER_CONFIG.get("allow_short", False)
            obj.save()
            self.stdout.write("  Created BollingerConfig")
        else:
            self.stdout.write("  BollingerConfig already exists — skipped")
