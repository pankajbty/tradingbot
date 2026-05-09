"""
CryptoScheduler — 24/7 scheduler for crypto strategies.

Key differences from equities TradingScheduler:
- No market-hours gate (crypto never sleeps)
- Per-strategy active_from/active_until windows are configurable
- Daily reset at midnight IST (calls risk_manager.maybe_daily_reset())
- Risk check runs every minute
- No auto-squareoff (user configures this manually or via a nightly cron)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, time as dtime

import schedule

from crypto_config import (
    CRYPTO_RISK_CONFIG,
    EMA_CROSSOVER_CONFIG,
    SUPERTREND_CONFIG,
    RSI_BB_CONFIG,
)

logger = logging.getLogger("CryptoApp.Scheduler")


def _parse_time(t_str: str) -> dtime:
    try:
        h, m = t_str.split(":")
        return dtime(int(h), int(m))
    except Exception:
        return dtime(0, 0)


def _in_window(active_from: str, active_until: str) -> bool:
    now   = datetime.now().time()
    start = _parse_time(active_from)
    end   = _parse_time(active_until)
    # Handle wrap-around (e.g. 22:00 -> 02:00)
    if start <= end:
        return start <= now <= end
    else:  # crosses midnight
        return now >= start or now <= end


class CryptoScheduler:
    def __init__(
        self,
        strategies:   dict,
        risk_manager,
        market_data,
        ema_config:        dict = None,
        supertrend_config: dict = None,
        rsi_bb_config:     dict = None,
        risk_config:       dict = None,
    ):
        self.strategies   = strategies
        self.risk_manager = risk_manager
        self.market_data  = market_data
        self._ema = ema_config         or EMA_CROSSOVER_CONFIG
        self._st  = supertrend_config  or SUPERTREND_CONFIG
        self._rbb = rsi_bb_config      or RSI_BB_CONFIG
        self._risk = risk_config       or CRYPTO_RISK_CONFIG

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        if "ema_crossover" in self.strategies:
            interval = self._ema.get("check_interval_minutes", 15)
            af = self._ema.get("active_from",  "00:00")
            au = self._ema.get("active_until", "23:59")
            schedule.every(interval).minutes.do(
                self._run_in_window, "ema_crossover", af, au
            )
            logger.info(f"EMA Crossover every {interval} min  [{af}-{au}]")

        if "supertrend" in self.strategies:
            interval = self._st.get("check_interval_minutes", 15)
            af = self._st.get("active_from",  "00:00")
            au = self._st.get("active_until", "23:59")
            schedule.every(interval).minutes.do(
                self._run_in_window, "supertrend", af, au
            )
            logger.info(f"Supertrend every {interval} min  [{af}-{au}]")

        if "rsi_bb" in self.strategies:
            interval = self._rbb.get("check_interval_minutes", 60)
            af = self._rbb.get("active_from",  "00:00")
            au = self._rbb.get("active_until", "23:59")
            schedule.every(interval).minutes.do(
                self._run_in_window, "rsi_bb", af, au
            )
            logger.info(f"RSI+BB every {interval} min  [{af}-{au}]")

        # Risk + P&L check every minute
        schedule.every(1).minutes.do(self._risk_check)

        # Daily reset check every 5 minutes (cheap)
        schedule.every(5).minutes.do(self.risk_manager.maybe_daily_reset)

        logger.info("CryptoScheduler set up. Running 24/7.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run(self, name: str):
        logger.info(f"--- Running crypto strategy: {name} ---")
        try:
            self.strategies[name].run()
        except Exception:
            logger.exception(f"Unhandled error in crypto strategy '{name}'")

    def _run_in_window(self, name: str, active_from: str, active_until: str):
        if _in_window(active_from, active_until):
            self._run(name)
        else:
            logger.debug(f"[{name}] outside window ({active_from}-{active_until}), skipping.")

    def _risk_check(self):
        self.risk_manager.check_targets(self.market_data)
        self.risk_manager.check_stop_losses(self.market_data)
        self.risk_manager.cleanup_closed_trades()
        pnl = self.risk_manager.update_pnl()
        if self.risk_manager.is_halted:
            logger.warning(
                f"Crypto trading halted. Daily P&L: Rs{pnl:.2f}. Squaring off all positions."
            )
            self.risk_manager.trader.squareoff_all_positions()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        logger.info("CryptoScheduler running 24/7. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("CryptoScheduler stopped.")
