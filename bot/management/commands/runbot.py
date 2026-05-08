"""
python manage.py runbot

Reads all strategy configuration from the database (via Django models),
builds the trading components, and starts the scheduler.

Equivalent to running main.py but with DB-sourced config instead of config.py.
"""
from django.core.management.base import BaseCommand

from bot.config_loader import load_all_configs, get_enabled_strategies
from bot.logging_trader import LoggingTrader, set_current_strategy
from logger import setup_logger
from market_data import MarketData
from risk_manager import RiskManager
from scheduler import TradingScheduler
from strategies import (
    BollingerBandStrategy,
    FixedBuyStrategy,
    MACrossoverStrategy,
    OpenRangeBreakoutStrategy,
)


class Command(BaseCommand):
    help = "Run the trading bot using configuration from the admin database"

    def handle(self, *args, **options):
        log = setup_logger("TradingApp")
        log.info("=" * 60)
        log.info("  Trading Bot Starting  (Django DB config)")
        log.info("=" * 60)

        # ---- Load all configs from DB ----
        zerodha_cfg, risk_cfg, fb_cfg, ma_cfg, or_cfg, bb_cfg = load_all_configs()
        enabled = get_enabled_strategies()

        log.info("Enabled strategies: %s", [k for k, v in enabled.items() if v])

        # ---- Core components ----
        trader      = LoggingTrader(credentials=zerodha_cfg)
        market_data = MarketData(trader.kite)
        risk_mgr    = RiskManager(trader, config=risk_cfg)

        # ---- Build active strategies (only if enabled in DB) ----
        all_strategies = {}

        if enabled["fixed_buy"]:
            all_strategies["fixed_buy"] = FixedBuyStrategy(
                trader, market_data, risk_mgr, config=fb_cfg
            )

        if enabled["ma_crossover"]:
            all_strategies["ma_crossover"] = MACrossoverStrategy(
                trader, market_data, risk_mgr, config=ma_cfg
            )

        if enabled["open_range_breakout"]:
            all_strategies["open_range_breakout"] = OpenRangeBreakoutStrategy(
                trader, market_data, risk_mgr, config=or_cfg
            )

        if enabled["bollinger"]:
            all_strategies["bollinger"] = BollingerBandStrategy(
                trader, market_data, risk_mgr, config=bb_cfg
            )

        if not all_strategies:
            log.warning("No strategies enabled. Enable at least one in the admin UI.")
            return

        # Inject strategy-name setter so TradeLog rows get the correct strategy tag
        _patch_strategies(all_strategies)

        # ---- Scheduler ----
        scheduler = TradingScheduler(
            strategies    = all_strategies,
            risk_manager  = risk_mgr,
            market_data   = market_data,
            fixed_buy_config  = fb_cfg,
            ma_config         = ma_cfg,
            or_config         = or_cfg,
            bollinger_config  = bb_cfg,
            risk_config       = risk_cfg,
        )
        scheduler.setup()
        scheduler.run()


def _patch_strategies(strategies: dict):
    """
    Monkey-patch each strategy's run() to set the global strategy name
    before execution so LoggingTrader writes the correct strategy tag.
    """
    for name, strategy in strategies.items():
        original_run = strategy.run

        def make_wrapped(n, fn):
            def wrapped():
                set_current_strategy(n)
                fn()
            return wrapped

        strategy.run = make_wrapped(name, original_run)
