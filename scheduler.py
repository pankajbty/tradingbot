import logging
import time
from datetime import datetime, time as dtime

import schedule

from config import (
    BOLLINGER_CONFIG,
    ENABLED_STRATEGIES,
    FIXED_BUY_CONFIG,
    MA_CROSSOVER_CONFIG,
    OPEN_RANGE_CONFIG,
    RISK_CONFIG,
)

logger = logging.getLogger("TradingApp.Scheduler")

_MARKET_OPEN  = dtime(9, 15)
_MARKET_CLOSE = dtime(15, 30)


def _is_market_hours() -> bool:
    now = datetime.now().time()
    return _MARKET_OPEN <= now <= _MARKET_CLOSE


class TradingScheduler:
    def __init__(
        self,
        strategies: dict,
        risk_manager,
        market_data,
        # Optional config dicts — used by runbot management command so DB config
        # flows through. Falls back to config.py constants when called from main.py.
        fixed_buy_config: dict = None,
        ma_config:        dict = None,
        or_config:        dict = None,
        bollinger_config: dict = None,
        risk_config:      dict = None,
    ):
        self.strategies   = strategies
        self.risk_manager = risk_manager
        self.market_data  = market_data
        self._fb   = fixed_buy_config  or FIXED_BUY_CONFIG
        self._ma   = ma_config         or MA_CROSSOVER_CONFIG
        self._or   = or_config         or OPEN_RANGE_CONFIG
        self._bb   = bollinger_config  or BOLLINGER_CONFIG
        self._risk = risk_config       or RISK_CONFIG

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        # Fixed Buy — once at configured time
        if "fixed_buy" in self.strategies:
            exec_time = self._fb.get("execute_at", "09:21")
            schedule.every().day.at(exec_time).do(self._run, "fixed_buy")
            logger.info(f"Fixed buy scheduled at {exec_time}")

        # MA Crossover — every N minutes during market hours
        if "ma_crossover" in self.strategies:
            interval = self._ma.get("check_interval_minutes", 5)
            schedule.every(interval).minutes.do(self._run_if_market, "ma_crossover")
            logger.info(f"MA crossover every {interval} min")

        # Open Range Breakout — every N minutes during market hours
        if "open_range_breakout" in self.strategies:
            interval = self._or.get("check_interval_minutes", 1)
            schedule.every(interval).minutes.do(self._run_if_market, "open_range_breakout")
            logger.info(f"Open range breakout every {interval} min")

        # Bollinger Band — every N minutes during market hours
        if "bollinger" in self.strategies:
            interval = self._bb.get("check_interval_minutes", 5)
            schedule.every(interval).minutes.do(self._run_if_market, "bollinger")
            logger.info(f"Bollinger Band every {interval} min")

        # Risk checks — every minute
        schedule.every(1).minutes.do(self._risk_check)

        # Auto square-off
        squareoff_time = self._risk.get("auto_squareoff_time", "15:15")
        schedule.every().day.at(squareoff_time).do(self._squareoff)
        logger.info(f"Auto square-off scheduled at {squareoff_time}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run(self, name: str):
        logger.info(f"--- Running strategy: {name} ---")
        try:
            self.strategies[name].run()
        except Exception:
            logger.exception(f"Unhandled error in strategy '{name}'")

    def _run_if_market(self, name: str):
        if _is_market_hours():
            self._run(name)

    def _risk_check(self):
        if not _is_market_hours():
            return
        self.risk_manager.check_targets(self.market_data)
        self.risk_manager.cleanup_closed_trades()
        pnl = self.risk_manager.update_pnl()
        if self.risk_manager.is_halted:
            logger.warning(f"Trading halted. Daily P&L: ₹{pnl:.2f}. Squaring off all positions.")
            self._squareoff()

    def _squareoff(self):
        logger.info("=== Auto square-off triggered ===")
        self.risk_manager.trader.squareoff_all_positions()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        logger.info("Scheduler running. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
