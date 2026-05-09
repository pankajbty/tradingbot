"""
EMA Crossover Strategy (Triple-EMA Trend-Following)

Logic:
  BUY  signal: 9 EMA crosses above 21 EMA  AND  price > 55 EMA  (with trend)
  SELL signal: 9 EMA crosses below 21 EMA  OR   price < 55 EMA  (against trend)

The 55 EMA acts as the macro trend filter — avoids counter-trend fades
that typically destroy short-term EMA crossover systems in crypto.

Best on: 15-min candles, BTC/INR, ETH/INR
"""
from __future__ import annotations

import logging

import pandas as pd

from crypto_config import EMA_CROSSOVER_CONFIG
from .base import CryptoBaseStrategy

logger = logging.getLogger("CryptoApp.Strategy.EMACrossover")


class EMACrossoverStrategy(CryptoBaseStrategy):
    name = "ema_crossover"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config       = config if config is not None else EMA_CROSSOVER_CONFIG
        self._done_for_day: dict[str, bool] = {}
        self._in_trade:     dict[str, bool] = {}
        self._entries:      dict[str, int]  = {}

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    def _get_signal(self, symbol: str) -> str | None:
        fast_p  = self._config["fast_period"]
        slow_p  = self._config["slow_period"]
        trend_p = self._config.get("trend_period", 55)
        needed  = trend_p + 2

        candles = self.market_data.get_candles(
            symbol, interval=self._config["candle_interval"], lookback_days=7
        )
        if len(candles) < needed:
            logger.debug(f"[EMA] Not enough candles for {symbol} ({len(candles)}/{needed})")
            return None

        closes    = pd.Series([c["close"] for c in candles])
        fast_ema  = closes.ewm(span=fast_p,  adjust=False).mean()
        slow_ema  = closes.ewm(span=slow_p,  adjust=False).mean()
        trend_ema = closes.ewm(span=trend_p, adjust=False).mean()

        curr_price  = closes.iloc[-1]
        curr_above  = fast_ema.iloc[-1] > slow_ema.iloc[-1]
        prev_above  = fast_ema.iloc[-2] > slow_ema.iloc[-2]
        trend_up    = curr_price > trend_ema.iloc[-1]

        # BUY: crossover to upside AND price is above long-term trend
        if curr_above and not prev_above and trend_up:
            return "BUY"

        # SELL: crossover to downside (no trend filter needed for exits)
        if not curr_above and prev_above:
            return "SELL"

        return None

    # ------------------------------------------------------------------
    # Position check
    # ------------------------------------------------------------------

    def _is_position_open(self, symbol: str) -> bool:
        positions = self.trader.get_positions()
        return any(p["symbol"] == symbol for p in positions)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        stop_on_profit = self._config.get("stop_on_profit", False)
        max_entries    = self._config.get("max_entries_per_day", 0)
        track_daily    = stop_on_profit or max_entries > 0

        for symbol in self._config["symbols"]:
            if track_daily:
                if self._done_for_day.get(symbol):
                    continue

                if self._in_trade.get(symbol):
                    if self._is_position_open(symbol):
                        continue
                    self._in_trade[symbol] = False
                    entries_done = self._entries.get(symbol, 0)

                    if stop_on_profit and self.risk_manager.daily_pnl > 0:
                        logger.info(f"[EMA] {symbol} — profitable close. Done for today.")
                        self._done_for_day[symbol] = True
                        continue

                    if max_entries > 0 and entries_done >= max_entries:
                        self._done_for_day[symbol] = True
                        continue

            signal = self._get_signal(symbol)
            if signal is None:
                continue

            if not self.risk_manager.can_trade():
                logger.info("[EMA] Risk gate closed.")
                break

            amount_inr = self._config.get("trade_amount_inr", 1000)

            # Exit any existing opposite position first
            positions = self.trader.get_positions()
            existing  = next((p for p in positions if p["symbol"] == symbol), None)
            if existing:
                if existing["side"] == signal:
                    logger.info(f"[EMA] Already in {signal} for {symbol}, skipping.")
                    continue
                exit_side  = "SELL" if existing["side"] == "BUY" else "BUY"
                exit_amt   = existing["quantity"] * self.market_data.get_ltp([symbol]).get(symbol, 0)
                self.trader.place_order(symbol, exit_side, exit_amt, tag="EMA_EXIT")

            order_id = self.trader.place_order(symbol, signal, amount_inr, tag="EMA_CROSS")
            if order_id:
                ltp = self.market_data.get_ltp([symbol]).get(symbol, 0.0)
                if ltp > 0:
                    qty = amount_inr / ltp
                    self.risk_manager.register_trade(symbol, signal, ltp, qty)
                if track_daily:
                    self._in_trade[symbol] = True
                    self._entries[symbol]  = self._entries.get(symbol, 0) + 1
