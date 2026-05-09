"""
RSI + Bollinger Band Strategy (Mean-Reversion)

BUY  when: RSI(14) < 35  AND  close <= lower Bollinger Band
           -> Oversold + at statistical support = high-probability bounce
SELL when: RSI(14) > 65  OR   close >= upper Bollinger Band
           -> Overbought or at statistical resistance

Why this works in crypto:
- Crypto has frequent, sharp oversold dips followed by quick recoveries
- Combining RSI (momentum) + BB (price-channel) filters out many false signals
- Works especially well during sideways/ranging phases
- The 1h timeframe smooths noise while keeping signals actionable

Note: This is a LONG-ONLY strategy by default. Set allow_short=True in config
to also take short positions on overbought signals.
"""
from __future__ import annotations

import logging

import pandas as pd
import numpy as np

from crypto_config import RSI_BB_CONFIG
from .base import CryptoBaseStrategy

logger = logging.getLogger("CryptoApp.Strategy.RSIBB")


def _rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _bollinger(closes: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma   = closes.rolling(period).mean()
    sigma = closes.rolling(period).std()
    return sma - std_dev * sigma, sma + std_dev * sigma   # lower, upper


class RSIBBStrategy(CryptoBaseStrategy):
    name = "rsi_bb"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config       = config if config is not None else RSI_BB_CONFIG
        self._in_trade:    dict[str, bool] = {}
        self._done_for_day: dict[str, bool] = {}
        self._entries:     dict[str, int]  = {}

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    def _get_signal(self, symbol: str) -> str | None:
        rsi_period   = self._config.get("rsi_period",    14)
        rsi_os       = self._config.get("rsi_oversold",  35)
        rsi_ob       = self._config.get("rsi_overbought", 65)
        bb_period    = self._config.get("bb_period",     20)
        bb_std       = self._config.get("bb_std_dev",    2.0)
        allow_short  = self._config.get("allow_short",  False)
        needed       = max(rsi_period, bb_period) + 5

        candles = self.market_data.get_candles(
            symbol, interval=self._config["candle_interval"], lookback_days=14
        )
        if len(candles) < needed:
            logger.debug(f"[RSIBB] Not enough candles for {symbol}")
            return None

        closes   = pd.Series([c["close"] for c in candles])
        rsi_vals = _rsi(closes, rsi_period)
        bb_low, bb_up = _bollinger(closes, bb_period, bb_std)

        curr_price = closes.iloc[-1]
        curr_rsi   = rsi_vals.iloc[-1]
        curr_bbl   = bb_low.iloc[-1]
        curr_bbu   = bb_up.iloc[-1]

        if pd.isna(curr_rsi) or pd.isna(curr_bbl):
            return None

        # BUY: oversold + price at/below lower band
        if curr_rsi < rsi_os and curr_price <= curr_bbl:
            logger.debug(
                f"[RSIBB] {symbol} BUY signal  RSI={curr_rsi:.1f}  "
                f"price={curr_price:.4f}  BB_low={curr_bbl:.4f}"
            )
            return "BUY"

        # SELL: overbought + price at/above upper band (only if allow_short or in position)
        positions    = self.trader.get_positions()
        in_long      = any(p["symbol"] == symbol and p["side"] == "BUY" for p in positions)

        if (curr_rsi > rsi_ob or curr_price >= curr_bbu) and (in_long or allow_short):
            logger.debug(
                f"[RSIBB] {symbol} SELL signal  RSI={curr_rsi:.1f}  "
                f"price={curr_price:.4f}  BB_up={curr_bbu:.4f}"
            )
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
                    if stop_on_profit and self.risk_manager.daily_pnl > 0:
                        self._done_for_day[symbol] = True
                        continue
                    if max_entries > 0 and self._entries.get(symbol, 0) >= max_entries:
                        self._done_for_day[symbol] = True
                        continue

            signal = self._get_signal(symbol)
            if signal is None:
                continue

            if not self.risk_manager.can_trade():
                logger.info("[RSIBB] Risk gate closed.")
                break

            amount_inr = self._config.get("trade_amount_inr", 1000)

            # If SELL and we have a long position, exit it
            if signal == "SELL":
                positions = self.trader.get_positions()
                existing  = next((p for p in positions if p["symbol"] == symbol and p["side"] == "BUY"), None)
                if existing:
                    exit_amt = existing["quantity"] * self.market_data.get_ltp([symbol]).get(symbol, 0)
                    self.trader.place_order(symbol, "SELL", exit_amt, tag="RSIBB_EXIT")
                    if symbol in self._in_trade:
                        self._in_trade[symbol] = False
                continue  # don't open a new short unless allow_short=True

            order_id = self.trader.place_order(symbol, signal, amount_inr, tag="RSIBB")
            if order_id:
                ltp = self.market_data.get_ltp([symbol]).get(symbol, 0.0)
                if ltp > 0:
                    qty = amount_inr / ltp
                    self.risk_manager.register_trade(symbol, signal, ltp, qty)
                if track_daily:
                    self._in_trade[symbol] = True
                    self._entries[symbol]  = self._entries.get(symbol, 0) + 1
