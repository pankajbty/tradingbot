import logging
from datetime import datetime, time as dtime

from config import OPEN_RANGE_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.OpenRange")

_MARKET_OPEN = dtime(9, 15)


class OpenRangeBreakoutStrategy(BaseStrategy):
    name = "open_range_breakout"

    def __init__(self, trader, market_data, risk_manager):
        super().__init__(trader, market_data, risk_manager)
        self._ranges:    dict[str, dict]  = {}   # symbol -> {high, low}
        self._range_set: dict[str, bool]  = {}
        self._traded:    dict[str, bool]  = {}   # one trade per stock per day

    # ------------------------------------------------------------------

    def _build_opening_range(self, symbol: str) -> bool:
        """Compute the opening-range high/low from intraday 1-min candles."""
        candles    = self.market_data.get_historical_candles(symbol, interval="minute", lookback_days=1)
        today      = datetime.now().date()
        range_mins = OPEN_RANGE_CONFIG["opening_range_minutes"]
        cutoff_min = 9 * 60 + 15 + range_mins  # minutes since midnight

        today_candles = [
            c for c in candles
            if c["date"].date() == today
            and c["date"].time() >= _MARKET_OPEN
            and (c["date"].hour * 60 + c["date"].minute) < cutoff_min
        ]

        if len(today_candles) < range_mins:
            return False  # Opening range not fully formed yet

        high = max(c["high"] for c in today_candles)
        low  = min(c["low"]  for c in today_candles)
        self._ranges[symbol] = {"high": high, "low": low}
        logger.info(f"[OpenRange] {symbol} range — high={high:.2f}, low={low:.2f}")
        return True

    # ------------------------------------------------------------------

    def run(self):
        now       = datetime.now().time()
        range_end = dtime(9, 15 + OPEN_RANGE_CONFIG["opening_range_minutes"])

        for symbol in OPEN_RANGE_CONFIG["stocks"]:
            # Build the opening range once it's complete
            if not self._range_set.get(symbol):
                if now < range_end:
                    continue  # Range window still open
                self._range_set[symbol] = self._build_opening_range(symbol)
                continue

            if self._traded.get(symbol):
                continue

            if not self.risk_manager.can_trade():
                logger.info("OpenRange: risk gate closed, stopping.")
                break

            ltps = self.market_data.get_ltp([symbol])
            ltp  = ltps.get(symbol)
            if ltp is None:
                continue

            r   = self._ranges[symbol]
            qty = OPEN_RANGE_CONFIG["quantity_per_stock"]

            if ltp > r["high"]:
                logger.info(
                    f"[OpenRange] BUY breakout: {symbol} LTP={ltp:.2f} > range_high={r['high']:.2f}"
                )
                order_id = self.trader.place_order(symbol, "BUY", qty, tag="ORB")
                if order_id:
                    self.risk_manager.register_trade(symbol, "BUY", ltp, qty)
                    self._traded[symbol] = True

            elif ltp < r["low"]:
                if not OPEN_RANGE_CONFIG.get("allow_short", False):
                    logger.info(
                        f"[OpenRange] Breakdown detected for {symbol} but short selling is disabled. "
                        f"Set allow_short=True in config.py to enable."
                    )
                    self._traded[symbol] = True   # skip for today, don't keep re-checking
                    continue
                logger.info(
                    f"[OpenRange] SELL breakdown: {symbol} LTP={ltp:.2f} < range_low={r['low']:.2f}"
                )
                order_id = self.trader.place_order(symbol, "SELL", qty, tag="ORB")
                if order_id:
                    self.risk_manager.register_trade(symbol, "SELL", ltp, qty)
                    self._traded[symbol] = True
