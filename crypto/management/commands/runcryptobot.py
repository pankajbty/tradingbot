"""
python manage.py runcryptobot

Reads all crypto strategy configuration from the database (via Django models),
builds the trading components, and starts the 24/7 crypto scheduler.

This is the crypto equivalent of runbot — completely standalone, does not
import anything from the equities bot.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from django.core.management.base import BaseCommand

from crypto.config_loader import load_all_configs, get_enabled_strategies
from crypto.logging_trader import LoggingCryptoTrader, set_current_strategy
from crypto_market_data import CryptoMarketData
from crypto_risk_manager import CryptoRiskManager
from crypto_scheduler import CryptoScheduler
from crypto_strategies import (
    EMACrossoverStrategy,
    SupertrendStrategy,
    RSIBBStrategy,
)


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _setup_logger(name: str) -> logging.Logger:
    """
    Configure file + console logging for the crypto bot.
    Log format matches the equities bot for consistency.
    """
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    from datetime import datetime
    log_file = log_dir / f"crypto_{datetime.now().strftime('%Y%m%d')}.log"

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger(name)
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger


class Command(BaseCommand):
    help = "Run the crypto trading bot using configuration from the admin database"

    def handle(self, *args, **options):
        log = _setup_logger("CryptoApp")
        log.info("=" * 60)
        log.info("  Crypto Bot Starting  (Django DB config)")
        log.info("=" * 60)

        # ---- Load all configs from DB ----
        exchange_cfg, risk_cfg, ema_cfg, st_cfg, rsi_bb_cfg = load_all_configs()
        enabled = get_enabled_strategies()

        log.info("Enabled crypto strategies: %s", [k for k, v in enabled.items() if v])
        log.info("Exchange: %s", exchange_cfg.get("exchange_id", "coindcx"))

        # ---- Core components ----
        trader = LoggingCryptoTrader(
            exchange_id=exchange_cfg.get("exchange_id", "coindcx"),
            credentials={
                "api_key":    exchange_cfg.get("api_key", ""),
                "api_secret": exchange_cfg.get("api_secret", ""),
            },
        )
        market_data = CryptoMarketData(trader.exchange)
        risk_mgr    = CryptoRiskManager(trader, config=risk_cfg)

        # ---- Build active strategies (only if enabled in DB) ----
        all_strategies = {}

        if enabled.get("ema_crossover"):
            all_strategies["ema_crossover"] = EMACrossoverStrategy(
                trader, market_data, risk_mgr, config=ema_cfg
            )
            log.info("EMA Crossover strategy loaded — symbols: %s", ema_cfg.get("symbols", []))

        if enabled.get("supertrend"):
            all_strategies["supertrend"] = SupertrendStrategy(
                trader, market_data, risk_mgr, config=st_cfg
            )
            log.info("Supertrend strategy loaded — symbols: %s", st_cfg.get("symbols", []))

        if enabled.get("rsi_bb"):
            all_strategies["rsi_bb"] = RSIBBStrategy(
                trader, market_data, risk_mgr, config=rsi_bb_cfg
            )
            log.info("RSI+BB strategy loaded — symbols: %s", rsi_bb_cfg.get("symbols", []))

        if not all_strategies:
            log.warning("No crypto strategies enabled. Enable at least one in the admin UI.")
            return

        # Inject strategy-name setter so CryptoTradeLog rows get the correct strategy tag
        _patch_strategies(all_strategies)

        # ---- Scheduler ----
        scheduler = CryptoScheduler(
            strategies        = all_strategies,
            risk_manager      = risk_mgr,
            market_data       = market_data,
            ema_config        = ema_cfg,
            supertrend_config = st_cfg,
            rsi_bb_config     = rsi_bb_cfg,
            risk_config       = risk_cfg,
        )
        scheduler.setup()
        scheduler.run()


def _patch_strategies(strategies: dict):
    """
    Monkey-patch each strategy's run() to set the global strategy name
    before execution so LoggingCryptoTrader writes the correct strategy tag.
    """
    for name, strategy in strategies.items():
        original_run = strategy.run

        def make_wrapped(n, fn):
            def wrapped():
                set_current_strategy(n)
                fn()
            return wrapped

        strategy.run = make_wrapped(name, original_run)
