import logging
from datetime import datetime, time as dtime

from config import OPEN_RANGE_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.OpenRange")

_MARKET_OPEN = dtime(9, 15)


class OpenRangeBreakoutStrategy(BaseStrategy):
    name = "open_range_breakout"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config     = config if config is not None else OPEN_RANGE_CONFIG
        self._ranges:    dict[str, dict] = {}
        self._range_set: dict[str, bool] = {}
        self._traded:    dict[str, bool] = {}   # True = done for today (no more entries)
        self._in_trade:  dict[str, bool] = {}   # True = currently holding a position
        self._entries:   dict[str, int]  = {}   # how many entries made today per symbol

    # ------------------------------------------------------------------
    # Opening range
    # ------------------------------------------------------------------

    def _build_opening_range(self, symbol: str) -> bool:
        """Compute the opening-range high/low from intraday 1-min candles."""
        candles    = self.market_data.get_historical_candles(symbol, interval="minute", lookback_days=1)
        today      = datetime.now().date()
        range_mins = self._config["opening_range_minutes"]
        cutoff_min = 9 * 60 + 15 + range_mins

        today_candles = [
            c for c in candles
            if c["date"].date() == today
            and c["date"].time() >= _MARKET_OPEN
            and (c["date"].hour * 60 + c["date"].minute) < cutoff_min
        ]

        if len(today_candles) < range_mins:
            return False

        high = max(c["high"] for c in today_candles)
        low  = min(c["low"]  for c in today_candles)
        self._ranges[symbol] = {"high": high, "low": low}
        logger.info(f"[OpenRange] {symbol} range — high={high:.2f}, low={low:.2f}")
        return True

    # ------------------------------------------------------------------
    # Position check helper
    # ------------------------------------------------------------------

    def _is_position_open(self, symbol: str) -> bool:
        """Return True if we currently hold an open MIS position for this symbol."""
        try:
            positions = self.trader.get_positions()
            return any(
                p["tradingsymbol"] == symbol and p.get("quantity", 0) != 0
                for p in positions
            )
        except Exception:
            return True   # assume still open on error — safer than re-entering

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        now             = datetime.now().time()
        range_end       = dtime(9, 15 + self._config["opening_range_minutes"])
        stop_on_profit  = self._config.get("stop_on_profit", False)
        max_entries     = self._config.get("max_entries_per_day", 1)   # 0 = unlimited

        for symbol in self._config["stocks"]:

            # ── 1. Build opening range once ──────────────────────────
            if not self._range_set.get(symbol):
                if now < range_end:
                    continue
                self._range_set[symbol] = self._build_opening_range(symbol)
                continue

            # ── 2. Done for today? ────────────────────────────────────
            if self._traded.get(symbol):
                continue

            # ── 3. Currently in a trade — wait for it to close ────────
            if self._in_trade.get(symbol):
                if self._is_position_open(symbol):
                    logger.debug(f"[OpenRange] {symbol} — position still open, waiting...")
                    continue

                # Position just closed
                self._in_trade[symbol] = False
                entries_done = self._entries.get(symbol, 0)
                daily_pnl    = self.risk_manager.daily_pnl

                if stop_on_profit and daily_pnl > 0:
                    logger.info(
                        f"[OpenRange] ✅ {symbol} — profitable close. "
                        f"Daily P&L=₹{daily_pnl:.2f}. Done for today."
                    )
                    self._traded[symbol] = True
                    continue

                if max_entries > 0 and entries_done >= max_entries:
                    logger.info(
                        f"[OpenRange] {symbol} — max entries ({max_entries}) reached. Done for today."
                    )
                    self._traded[symbol] = True
                    continue

                logger.info(
                    f"[OpenRange] {symbol} — trade closed (P&L=₹{daily_pnl:.2f}). "
                    f"Re-entering mode. Entries today: {entries_done}"
                )
                # fall through to signal check below

            # ── 4. Risk gate ──────────────────────────────────────────
            if not self.risk_manager.can_trade():
                logger.info("OpenRange: risk gate closed, stopping.")
                break

            # ── 5. Get LTP ────────────────────────────────────────────
            ltps = self.market_data.get_ltp([symbol])
            ltp  = ltps.get(symbol)
            if ltp is None:
                continue

            r   = self._ranges[symbol]
            qty = self._config["quantity_per_stock"]

            # ── 6. BUY breakout ───────────────────────────────────────
            if ltp > r["high"]:
                logger.info(
                    f"[OpenRange] BUY breakout: {symbol} LTP={ltp:.2f} > range_high={r['high']:.2f}"
                )
                order_id = self.trader.place_order(symbol, "BUY", qty, tag="ORB")
                if order_id:
                    self.risk_manager.register_trade(symbol, "BUY", ltp, qty)
                    self._in_trade[symbol] = True
                    self._entries[symbol]  = self._entries.get(symbol, 0) + 1

                    # In default mode (no stop_on_profit) keep original 1-trade behaviour
                    if not stop_on_profit and max_entries == 1:
                        self._traded[symbol] = True

            # ── 7. SELL breakdown ─────────────────────────────────────
            elif ltp < r["low"]:
                if not self._config.get("allow_short", False):
                    logger.info(
                        f"[OpenRange] Breakdown for {symbol} but short selling is disabled."
                    )
                    self._traded[symbol] = True
                    continue
                logger.info(
                    f"[OpenRange] SELL breakdown: {symbol} LTP={ltp:.2f} < range_low={r['low']:.2f}"
                )
                order_id = self.trader.place_order(symbol, "SELL", qty, tag="ORB")
                if order_id:
                    self.risk_manager.register_trade(symbol, "SELL", ltp, qty)
                    self._in_trade[symbol] = True
                    self._entries[symbol]  = self._entries.get(symbol, 0) + 1

                    if not stop_on_profit and max_entries == 1:
                        self._traded[symbol] = True
