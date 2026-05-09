import logging

import pandas as pd

from config import BOLLINGER_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.Bollinger")


class BollingerBandStrategy(BaseStrategy):
    """
    Bollinger Band mean-reversion strategy.

    BUY  signal: previous candle closed BELOW lower band →
                 current candle closes ABOVE lower band  (oversold bounce)

    SELL signal: previous candle closed ABOVE upper band →
                 current candle closes BELOW upper band  (overbought reversal)
                 Only fires when allow_short = True.

    Exit is handled by the risk manager (target / stop-loss orders).

    stop_on_profit = True  → re-enter after each stop-loss until a trade
                              closes profitably, then stop for the day.
    stop_on_profit = False → one trade per stock per day (default).
    """

    name = "bollinger"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config   = config if config is not None else BOLLINGER_CONFIG
        self._traded:   dict[str, bool] = {}   # True = done for today
        self._in_trade: dict[str, bool] = {}   # True = position currently open
        self._entries:  dict[str, int]  = {}   # entry count today per symbol

    # ------------------------------------------------------------------
    # Band calculation
    # ------------------------------------------------------------------

    def _compute_bands(self, symbol: str) -> dict | None:
        period   = self._config["period"]
        std_mult = self._config["std_dev"]

        candles = self.market_data.get_historical_candles(
            symbol,
            interval=self._config["candle_interval"],
            lookback_days=10,
        )

        if len(candles) < period + 2:
            logger.debug(f"[Bollinger] Not enough candles for {symbol} ({len(candles)})")
            return None

        closes = pd.Series([c["close"] for c in candles])
        sma    = closes.rolling(period).mean()
        std    = closes.rolling(period).std()
        upper  = sma + std_mult * std
        lower  = sma - std_mult * std

        return {
            "upper":         upper.iloc[-1],
            "middle":        sma.iloc[-1],
            "lower":         lower.iloc[-1],
            "prev_upper":    upper.iloc[-2],
            "prev_lower":    lower.iloc[-2],
            "current_close": closes.iloc[-1],
            "prev_close":    closes.iloc[-2],
        }

    # ------------------------------------------------------------------
    # Signal detection
    # ------------------------------------------------------------------

    def _get_signal(self, symbol: str) -> str | None:
        bands = self._compute_bands(symbol)
        if bands is None:
            return None

        prev_close = bands["prev_close"]
        curr_close = bands["current_close"]

        logger.debug(
            f"[Bollinger] {symbol} | close={curr_close:.2f} "
            f"lower={bands['lower']:.2f} upper={bands['upper']:.2f} mid={bands['middle']:.2f}"
        )

        if prev_close < bands["prev_lower"] and curr_close > bands["lower"]:
            return "BUY"

        if self._config.get("allow_short", False):
            if prev_close > bands["prev_upper"] and curr_close < bands["upper"]:
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
            return True  # assume open on error — safer than re-entering

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        stop_on_profit = self._config.get("stop_on_profit", False)
        max_entries    = self._config.get("max_entries_per_day", 1)

        for symbol in self._config["stocks"]:

            # ── Done for today? ───────────────────────────────────────
            if self._traded.get(symbol):
                continue

            # ── Currently in a trade — wait for it to close ───────────
            if self._in_trade.get(symbol):
                if self._is_position_open(symbol):
                    logger.debug(f"[Bollinger] {symbol} — position still open, waiting...")
                    continue

                # Position just closed
                self._in_trade[symbol] = False
                entries_done = self._entries.get(symbol, 0)
                daily_pnl    = self.risk_manager.daily_pnl

                if stop_on_profit and daily_pnl > 0:
                    logger.info(
                        f"[Bollinger] ✅ {symbol} — profitable close. "
                        f"Daily P&L=₹{daily_pnl:.2f}. Done for today."
                    )
                    self._traded[symbol] = True
                    continue

                if max_entries > 0 and entries_done >= max_entries:
                    logger.info(
                        f"[Bollinger] {symbol} — max entries ({max_entries}) reached. Done for today."
                    )
                    self._traded[symbol] = True
                    continue

                logger.info(
                    f"[Bollinger] {symbol} — trade closed (P&L=₹{daily_pnl:.2f}). "
                    f"Re-entering mode. Entries today: {entries_done}"
                )
                # fall through to signal check

            # ── Signal check ──────────────────────────────────────────
            signal = self._get_signal(symbol)
            if signal is None:
                continue

            if not self.risk_manager.can_trade():
                logger.info("Bollinger: risk gate closed, stopping.")
                break

            qty   = self._config["quantity_per_stock"]
            bands = self._compute_bands(symbol)
            ltp   = bands["current_close"] if bands else 0.0

            logger.info(
                f"[Bollinger] {signal} signal for {symbol} @ {ltp:.2f} | "
                f"lower={bands['lower']:.2f} upper={bands['upper']:.2f} mid={bands['middle']:.2f}"
            )

            order_id = self.trader.place_order(symbol, signal, qty, tag="BB")
            if order_id:
                self.risk_manager.register_trade(symbol, signal, ltp, qty)
                self._in_trade[symbol] = True
                self._entries[symbol]  = self._entries.get(symbol, 0) + 1

                # Default mode: one trade per day (original behaviour)
                if not stop_on_profit and max_entries == 1:
                    self._traded[symbol] = True
