"""
python manage.py seed_crypto_config

Populates the database with default values from crypto_config.py.
Safe to re-run — skips tables that already have a row.
"""
from __future__ import annotations

import datetime

from django.core.management.base import BaseCommand

import crypto_config as C
from crypto.models import (
    CryptoBotControl,
    CryptoExchangeConfig,
    CryptoRiskConfig,
    EMACrossoverConfig,
    RSIBBConfig,
    SupertrendConfig,
)


class Command(BaseCommand):
    help = "Seed the database with default crypto strategy configs from crypto_config.py"

    def handle(self, *args, **options):
        self._seed_exchange()
        self._seed_risk()
        self._seed_ema_crossover()
        self._seed_supertrend()
        self._seed_rsi_bb()
        self._seed_bot_control()
        self.stdout.write(self.style.SUCCESS("Database seeded with default crypto configuration."))
        self.stdout.write(
            "   Open http://127.0.0.1:8000/admin/ to review and update settings."
        )
        self.stdout.write(
            "   Remember to configure your API key and secret in Crypto Exchange Config."
        )

    # ------------------------------------------------------------------

    def _seed_exchange(self):
        obj, created = CryptoExchangeConfig.objects.get_or_create(pk=1)
        if created:
            obj.exchange_id = C.EXCHANGE_ID
            obj.api_key     = C.EXCHANGE_CONFIG.get("api_key", "")
            obj.api_secret  = C.EXCHANGE_CONFIG.get("api_secret", "")
            obj.testnet     = False
            obj.save()
            self.stdout.write("  Created CryptoExchangeConfig")
        else:
            self.stdout.write("  CryptoExchangeConfig already exists — skipped")

    def _seed_risk(self):
        obj, created = CryptoRiskConfig.objects.get_or_create(pk=1)
        if created:
            obj.stop_loss_pct      = C.CRYPTO_RISK_CONFIG["stop_loss_pct"]
            obj.target_pct         = C.CRYPTO_RISK_CONFIG["target_pct"]
            obj.max_daily_loss     = C.CRYPTO_RISK_CONFIG["max_daily_loss"]
            obj.max_open_positions = C.CRYPTO_RISK_CONFIG["max_open_positions"]
            obj.trade_amount_inr   = C.CRYPTO_RISK_CONFIG["trade_amount_inr"]
            obj.daily_reset_hour   = C.CRYPTO_RISK_CONFIG["daily_reset_hour"]
            obj.save()
            self.stdout.write("  Created CryptoRiskConfig")
        else:
            self.stdout.write("  CryptoRiskConfig already exists — skipped")

    def _seed_ema_crossover(self):
        obj, created = EMACrossoverConfig.objects.get_or_create(pk=1)
        if created:
            cfg = C.EMA_CROSSOVER_CONFIG
            obj.enabled                 = True
            obj.symbols                 = cfg["symbols"]
            obj.fast_period             = cfg["fast_period"]
            obj.slow_period             = cfg["slow_period"]
            obj.trend_period            = cfg.get("trend_period", 55)
            obj.candle_interval         = cfg["candle_interval"]
            obj.trade_amount_inr        = cfg["trade_amount_inr"]
            obj.check_interval_minutes  = cfg["check_interval_minutes"]
            obj.stop_on_profit          = cfg.get("stop_on_profit", False)
            obj.max_entries_per_day     = cfg.get("max_entries_per_day", 0)
            obj.active_from             = _parse_time(cfg.get("active_from", "00:00"))
            obj.active_until            = _parse_time(cfg.get("active_until", "23:59"))
            obj.save()
            self.stdout.write("  Created EMACrossoverConfig")
        else:
            self.stdout.write("  EMACrossoverConfig already exists — skipped")

    def _seed_supertrend(self):
        obj, created = SupertrendConfig.objects.get_or_create(pk=1)
        if created:
            cfg = C.SUPERTREND_CONFIG
            obj.enabled                 = True
            obj.symbols                 = cfg["symbols"]
            obj.atr_period              = cfg["atr_period"]
            obj.multiplier              = cfg["multiplier"]
            obj.candle_interval         = cfg["candle_interval"]
            obj.trade_amount_inr        = cfg["trade_amount_inr"]
            obj.check_interval_minutes  = cfg["check_interval_minutes"]
            obj.stop_on_profit          = cfg.get("stop_on_profit", False)
            obj.max_entries_per_day     = cfg.get("max_entries_per_day", 0)
            obj.active_from             = _parse_time(cfg.get("active_from", "00:00"))
            obj.active_until            = _parse_time(cfg.get("active_until", "23:59"))
            obj.save()
            self.stdout.write("  Created SupertrendConfig")
        else:
            self.stdout.write("  SupertrendConfig already exists — skipped")

    def _seed_rsi_bb(self):
        obj, created = RSIBBConfig.objects.get_or_create(pk=1)
        if created:
            cfg = C.RSI_BB_CONFIG
            obj.enabled                 = True
            obj.symbols                 = cfg["symbols"]
            obj.rsi_period              = cfg["rsi_period"]
            obj.rsi_oversold            = cfg["rsi_oversold"]
            obj.rsi_overbought          = cfg["rsi_overbought"]
            obj.bb_period               = cfg["bb_period"]
            obj.bb_std_dev              = cfg["bb_std_dev"]
            obj.allow_short             = cfg.get("allow_short", False)
            obj.candle_interval         = cfg["candle_interval"]
            obj.trade_amount_inr        = cfg["trade_amount_inr"]
            obj.check_interval_minutes  = cfg["check_interval_minutes"]
            obj.stop_on_profit          = cfg.get("stop_on_profit", False)
            obj.max_entries_per_day     = cfg.get("max_entries_per_day", 0)
            obj.active_from             = _parse_time(cfg.get("active_from", "00:00"))
            obj.active_until            = _parse_time(cfg.get("active_until", "23:59"))
            obj.save()
            self.stdout.write("  Created RSIBBConfig")
        else:
            self.stdout.write("  RSIBBConfig already exists — skipped")

    def _seed_bot_control(self):
        obj, created = CryptoBotControl.objects.get_or_create(pk=1)
        if created:
            obj.is_running = False
            obj.save()
            self.stdout.write("  Created CryptoBotControl")
        else:
            self.stdout.write("  CryptoBotControl already exists — skipped")


def _parse_time(t_str: str) -> datetime.time:
    """Parse "HH:MM" string into a datetime.time object."""
    try:
        h, m = t_str.split(":")
        return datetime.time(int(h), int(m))
    except Exception:
        return datetime.time(0, 0)
