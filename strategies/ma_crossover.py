import logging

import pandas as pd

from config import MA_CROSSOVER_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.MACrossover")


class MACrossoverStrategy(BaseStrategy):
    name = "ma_crossover"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config = config if config is not None else MA_CROSSOVER_CONFIG

    def _get_signal(self, symbol: str) -> str | None:
        """Return 'BUY', 'SELL', or None based on EMA crossover."""
        fast_p = self._config["fast_period"]
        slow_p = self._config["slow_period"]

        candles = self.market_data.get_historical_candles(
            symbol,
            interval=self._config["candle_interval"],
            lookback_days=5,
        )
        # Need at least slow_period + 1 candles to detect a crossover
        if len(candles) < slow_p + 2:
            logger.debug(f"[MACrossover] Not enough candles for {symbol} ({len(candles)})")
            return None

        closes = pd.Series([c["close"] for c in candles])
        fast_ema = closes.ewm(span=fast_p, adjust=False).mean()
        slow_ema = closes.ewm(span=slow_p, adjust=False).mean()

        curr_above = fast_ema.iloc[-1] > slow_ema.iloc[-1]
        prev_above = fast_ema.iloc[-2] > slow_ema.iloc[-2]

        if curr_above and not prev_above:
            return "BUY"
        if not curr_above and prev_above:
            return "SELL"
        return None

    def run(self):
        for symbol in self._config["stocks"]:
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
