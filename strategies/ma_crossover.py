import logging

import pandas as pd

from config import MA_CROSSOVER_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.MACrossover")


class MACrossoverStrategy(BaseStrategy):
    """
    EMA crossover strategy.

    BUY  when fast EMA crosses above slow EMA.
    SELL when fast EMA crosses below slow EMA (exits and optionally shorts).

    stop_on_profit = True  → wait for each position to close before re-entering;
                              once a trade closes profitably, stop for the day.
    stop_on_profit = False → original behaviour: trade every crossover, unlimited.
    max_entries_per_day    → hard cap on entries (0 = unlimited).
    """

    name = "ma_crossover"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config       = config if config is not None else MA_CROSSOVER_CONFIG
        self._done_for_day: dict[str, bool] = {}   # True = no more entries today
        self._in_trade:     dict[str, bool] = {}   # True = position currently open
        self._entries:      dict[str, int]  = {}   # entry count today per symbol

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    def _get_signal(self, symbol: str) -> str | None:
        fast_p = self._config["fast_period"]
        slow_p = self._config["slow_period"]

        candles = self.market_data.get_historical_candles(
            symbol,
            interval=self._config["candle_interval"],
            lookback_days=5,
        )
        if len(candles) < slow_p + 2:
            logger.debug(f"[MACrossover] Not enough candles for {symbol} ({len(candles)})")
            return None

        closes   = pd.Series([c["close"] for c in candles])
        fast_ema = closes.ewm(span=fast_p, adjust=False).mean()
        slow_ema = closes.ewm(span=slow_p, adjust=False).mean()

        curr_above = fast_ema.iloc[-1] > slow_ema.iloc[-1]
        prev_above = fast_ema.iloc[-2] > slow_ema.iloc[-2]

        if curr_above and not prev_above:
            return "BUY"
        if not curr_above and prev_above:
            return "SELL"
        return None

    # ------------------------------------------------------------------
    # Position check helper
    # ------------------------------------------------------------------

    def _is_position_open(self, symbol: str) -> bool:
        try:
            positions = self.trader.get_positions()
            return any(
                p["tradingsymbol"] == symbol and p.get("quantity", 0) != 0
                for p in positions
            )
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        stop_on_profit = self._config.get("stop_on_profit", False)
        max_entries    = self._config.get("max_entries_per_day", 0)   # 0 = unlimited
        track_daily    = stop_on_profit or max_entries > 0

        for symbol in self._config["stocks"]:

            # ── Daily completion check (only in tracked mode) ─────────
            if track_daily:
                if self._done_for_day.get(symbol):
                    continue

                if self._in_trade.get(symbol):
                    if self._is_position_open(symbol):
                        # Still in trade — wait for it to close before
                        # looking for the next entry signal
                        continue

                    # Position just closed
                    self._in_trade[symbol] = False
                    entries_done = self._entries.get(symbol, 0)
                    daily_pnl    = self.risk_manager.daily_pnl

                    if stop_on_profit and daily_pnl > 0:
                        logger.info(
                            f"[MACrossover] ✅ {symbol} — profitable close. "
                            f"Daily P&L=₹{daily_pnl:.2f}. Done for today."
                        )
                        self._done_for_day[symbol] = True
                        continue

                    if max_entries > 0 and entries_done >= max_entries:
                        logger.info(
                            f"[MACrossover] {symbol} — max entries ({max_entries}) reached. Done for today."
                        )
                        self._done_for_day[symbol] = True
                        continue

                    logger.info(
                        f"[MACrossover] {symbol} — trade closed (P&L=₹{daily_pnl:.2f}). "
                        f"Re-entering mode. Entries today: {entries_done}"
                    )
                    # fall through to signal check

            # ── Signal detection ──────────────────────────────────────
            signal = self._get_signal(symbol)
            if signal is None:
                continue

            if not self.risk_manager.can_trade():
                logger.info("MACrossover: risk gate closed, stopping.")
                break

            qty = self._config["quantity_per_stock"]
            logger.info(f"[MACrossover] Signal {signal} for {symbol}")

            # Exit any existing opposite position first
            positions = self.trader.get_positions()
            existing  = next(
                (p for p in positions if p["tradingsymbol"] == symbol and p["quantity"] != 0),
                None,
            )
            if existing:
                existing_side = "BUY" if existing["quantity"] > 0 else "SELL"
                if existing_side == signal:
                    logger.info(f"[MACrossover] Already in {signal} for {symbol}, skipping.")
                    continue
                exit_side = "SELL" if existing["quantity"] > 0 else "BUY"
                self.trader.place_order(
                    symbol, exit_side, abs(existing["quantity"]), tag="MA_EXIT"
                )

            order_id = self.trader.place_order(symbol, signal, qty, tag="MA_CROSS")
            if order_id:
                ltps        = self.market_data.get_ltp([symbol])
                entry_price = ltps.get(symbol, 0.0)
                if entry_price > 0:
                    self.risk_manager.register_trade(symbol, signal, entry_price, qty)

                if track_daily:
                    self._in_trade[symbol] = True
                    self._entries[symbol]  = self._entries.get(symbol, 0) + 1
