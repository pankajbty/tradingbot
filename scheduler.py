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
    def __init__(self, strategies: dict, risk_manager, market_data):
        self.strategies   = strategies
        self.risk_manager = risk_manager
        self.market_data  = market_data

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        # Fixed Buy — once at configured time
        if "fixed_buy" in self.strategies and "fixed_buy" in ENABLED_STRATEGIES:
            exec_time = FIXED_BUY_CONFIG.get("execute_at", "09:16")
            schedule.every().day.at(exec_time).do(self._run, "fixed_buy")
            logger.info(f"Fixed buy scheduled at {exec_time}")

        # MA Crossover — every N minutes during market hours
        if "ma_crossover" in self.strategies and "ma_crossover" in ENABLED_STRATEGIES:
            interval = MA_CROSSOVER_CONFIG.get("check_interval_minutes", 5)
            schedule.every(interval).minutes.do(self._run_if_market, "ma_crossover")
            logger.info(f"MA crossover every {interval} min")

        # Open Range Breakout — every 1 minute during market hours
        if "open_range_breakout" in self.strategies and "open_range_breakout" in ENABLED_STRATEGIES:
            interval = OPEN_RANGE_CONFIG.get("check_interval_minutes", 1)
            schedule.every(interval).minutes.do(self._run_if_market, "open_range_breakout")
            logger.info(f"Open range breakout every {interval} min")

        # Bollinger Band — every N minutes during market hours
        if "bollinger" in self.strategies and "bollinger" in ENABLED_STRATEGIES:
            interval = BOLLINGER_CONFIG.get("check_interval_minutes", 5)
            schedule.every(interval).minutes.do(self._run_if_market, "bollinger")
            logger.info(f"Bollinger Band every {interval} min")

        # Risk checks — every minute
        schedule.every(1).minutes.do(self._risk_check)

        # Auto square-off
        squareoff_time = RISK_CONFIG.get("auto_squareoff_time", "15:15")
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
