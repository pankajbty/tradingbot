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


def _parse_time(t_str: str) -> dtime:
    """Parse 'HH:MM' string to datetime.time. Returns market open on error."""
    try:
        h, m = t_str.split(":")
        return dtime(int(h), int(m))
    except Exception:
        return _MARKET_OPEN


def _in_window(active_from: str, active_until: str) -> bool:
    """Return True if current time falls within [active_from, active_until]."""
    now   = datetime.now().time()
    start = _parse_time(active_from)
    end   = _parse_time(active_until)
    return start <= now <= end


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

        # MA Crossover — every N minutes within its configured window
        if "ma_crossover" in self.strategies:
            interval = self._ma.get("check_interval_minutes", 5)
            af = self._ma.get("active_from", "09:15")
            au = self._ma.get("active_until", "15:15")
            schedule.every(interval).minutes.do(
                self._run_in_window, "ma_crossover", af, au
            )
            logger.info(f"MA crossover every {interval} min  [{af}–{au}]")

        # Open Range Breakout — every N minutes within its configured window
        if "open_range_breakout" in self.strategies:
            interval = self._or.get("check_interval_minutes", 1)
            af = self._or.get("active_from", "09:30")
            au = self._or.get("active_until", "11:00")
            schedule.every(interval).minutes.do(
                self._run_in_window, "open_range_breakout", af, au
            )
            logger.info(f"Open range breakout every {interval} min  [{af}–{au}]")

        # Bollinger Band — every N minutes within its configured window
        if "bollinger" in self.strategies:
            interval = self._bb.get("check_interval_minutes", 5)
            af = self._bb.get("active_from", "09:15")
            au = self._bb.get("active_until", "15:15")
            schedule.every(interval).minutes.do(
                self._run_in_window, "bollinger", af, au
            )
            logger.info(f"Bollinger Band every {interval} min  [{af}–{au}]")

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
        """Legacy helper — kept for any direct callers; respects market hours only."""
        if _is_market_hours():
            self._run(name)

    def _run_in_window(self, name: str, active_from: str, active_until: str):
        """Run strategy only when inside both market hours AND its own active window."""
        if _is_market_hours() and _in_window(active_from, active_until):
            self._run(name)
        else:
            logger.debug(
                f"[{name}] outside active window ({active_from}–{active_until}), skipping."
            )

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
