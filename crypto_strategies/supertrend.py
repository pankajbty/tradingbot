"""
Supertrend Strategy

Supertrend = SMA(high,low,close) +/- ATR(period) x multiplier
  Upper band = (high+low)/2 + multiplier x ATR
  Lower band = (high+low)/2 - multiplier x ATR

  Trend is UP  when close > upper_band (price above -> bullish)
  Trend is DOWN when close < lower_band (price below -> bearish)

BUY:  trend flips from DOWN -> UP  (price crosses above Supertrend)
SELL: trend flips from UP -> DOWN  (price crosses below Supertrend)

Why Supertrend for crypto:
- Automatically widens bands during high volatility (ATR), reducing whipsaws
- Clean flip signals, easy to programme
- 10-period ATR with 3.0x multiplier is the community-proven default for 15m crypto
"""
from __future__ import annotations

import logging

import pandas as pd
import numpy as np

from crypto_config import SUPERTREND_CONFIG
from .base import CryptoBaseStrategy

logger = logging.getLogger("CryptoApp.Strategy.Supertrend")


def _compute_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """
    Compute Supertrend and return a Series of direction:
      +1 = bullish (price above Supertrend)
      -1 = bearish (price below Supertrend)
    """
    hl2  = (df["high"] + df["low"]) / 2

    # True Range -> ATR
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"]  - df["close"].shift(1)).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()   # Wilder's smoothing via EWM

    upper_basic = hl2 + multiplier * atr
    lower_basic = hl2 - multiplier * atr

    n    = len(df)
    upper = upper_basic.copy()
    lower = lower_basic.copy()
    direction = pd.Series(1, index=df.index)

    for i in range(1, n):
        # Upper band
        if upper_basic.iloc[i] < upper.iloc[i-1] or df["close"].iloc[i-1] > upper.iloc[i-1]:
            upper.iloc[i] = upper_basic.iloc[i]
        else:
            upper.iloc[i] = upper.iloc[i-1]

        # Lower band
        if lower_basic.iloc[i] > lower.iloc[i-1] or df["close"].iloc[i-1] < lower.iloc[i-1]:
            lower.iloc[i] = lower_basic.iloc[i]
        else:
            lower.iloc[i] = lower.iloc[i-1]

        # Direction
        if direction.iloc[i-1] == -1 and df["close"].iloc[i] > upper.iloc[i-1]:
            direction.iloc[i] = 1
        elif direction.iloc[i-1] == 1 and df["close"].iloc[i] < lower.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]

    return direction


class SupertrendStrategy(CryptoBaseStrategy):
    name = "supertrend"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config       = config if config is not None else SUPERTREND_CONFIG
        self._done_for_day: dict[str, bool] = {}
        self._in_trade:     dict[str, bool] = {}
        self._entries:      dict[str, int]  = {}

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    def _get_signal(self, symbol: str) -> str | None:
        period     = self._config.get("atr_period",  10)
        multiplier = self._config.get("multiplier", 3.0)
        needed     = period + 5

        candles = self.market_data.get_candles(
            symbol, interval=self._config["candle_interval"], lookback_days=7
        )
        if len(candles) < needed:
            logger.debug(f"[Supertrend] Not enough candles for {symbol}")
            return None

        df = pd.DataFrame(candles)
        direction = _compute_supertrend(df, period, multiplier)

        curr_dir = direction.iloc[-1]
        prev_dir = direction.iloc[-2]

        if curr_dir == 1 and prev_dir == -1:
            return "BUY"
        if curr_dir == -1 and prev_dir == 1:
            return "SELL"
        return None

    # ------------------------------------------------------------------
    # Position check
    # ------------------------------------------------------------------

    def _is_position_open(self, symbol: str) -> bool:
        return any(p["symbol"] == symbol for p in self.trader.get_positions())

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
                        self._done_for_day[symbol] = True
                        continue
                    if max_entries > 0 and entries_done >= max_entries:
                        self._done_for_day[symbol] = True
                        continue

            signal = self._get_signal(symbol)
            if signal is None:
                continue

            if not self.risk_manager.can_trade():
                logger.info("[Supertrend] Risk gate closed.")
                break

            amount_inr = self._config.get("trade_amount_inr", 1000)

            # Exit any opposite position first
            positions = self.trader.get_positions()
            existing  = next((p for p in positions if p["symbol"] == symbol), None)
            if existing:
                if existing["side"] == signal:
                    logger.info(f"[Supertrend] Already in {signal} for {symbol}, skipping.")
                    continue
                exit_side = "SELL" if existing["side"] == "BUY" else "BUY"
                exit_amt  = existing["quantity"] * self.market_data.get_ltp([symbol]).get(symbol, 0)
                self.trader.place_order(symbol, exit_side, exit_amt, tag="ST_EXIT")

            order_id = self.trader.place_order(symbol, signal, amount_inr, tag="SUPERTREND")
            if order_id:
                ltp = self.market_data.get_ltp([symbol]).get(symbol, 0.0)
                if ltp > 0:
                    qty = amount_inr / ltp
                    self.risk_manager.register_trade(symbol, signal, ltp, qty)
                if track_daily:
                    self._in_trade[symbol] = True
                    self._entries[symbol]  = self._entries.get(symbol, 0) + 1
