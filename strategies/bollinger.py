import logging

import pandas as pd

from config import BOLLINGER_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.Bollinger")


class BollingerBandStrategy(BaseStrategy):
    """
    Bollinger Band mean-reversion strategy.

    BUY  signal: previous candle closed BELOW lower band  →
                 current candle closes ABOVE lower band   (oversold bounce)

    SELL signal: previous candle closed ABOVE upper band  →
                 current candle closes BELOW upper band   (overbought reversal)
                 Only fires when allow_short = True.

    Exit is handled by the risk manager (target / stop-loss orders).
    One trade per stock per day.
    """

    name = "bollinger"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config = config if config is not None else BOLLINGER_CONFIG
        self._traded: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Band calculation
    # ------------------------------------------------------------------

    def _compute_bands(self, symbol: str) -> dict | None:
        """
        Returns dict with keys: upper, middle, lower, prev_upper,
        prev_middle, prev_lower, current_close, prev_close.
        Returns None if not enough data.
        """
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
        prev_lower = bands["prev_lower"]
        lower      = bands["lower"]
        prev_upper = bands["prev_upper"]
        upper      = bands["upper"]

        logger.debug(
            f"[Bollinger] {symbol} | close={curr_close:.2f} "
            f"lower={lower:.2f} upper={upper:.2f} mid={bands['middle']:.2f}"
        )

        # BUY: price was below lower band, now crossed back above it
        if prev_close < prev_lower and curr_close > lower:
            return "BUY"

        # SELL (short): price was above upper band, now crossed back below it
        if self._config.get("allow_short", False):
            if prev_close > prev_upper and curr_close < upper:
                return "SELL"

        return None

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        for symbol in self._config["stocks"]:
            if self._traded.get(symbol):
                continue

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
                f"lower={bands['lower']:.2f} upper={bands['upper']:.2f} "
                f"mid={bands['middle']:.2f}"
            )

            order_id = self.trader.place_order(symbol, signal, qty, tag="BB")
            if order_id:
                self.risk_manager.register_trade(symbol, signal, ltp, qty)
                self._traded[symbol] = True
