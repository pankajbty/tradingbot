"""
CryptoMarketData — fetches OHLCV candles and LTP from ccxt exchange.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger("CryptoApp.MarketData")


class CryptoMarketData:
    def __init__(self, exchange):
        """
        :param exchange: a ccxt exchange instance (from CryptoTrader.exchange)
        """
        self._exchange = exchange

    def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        lookback_days: int = 5,
    ) -> list[dict]:
        """
        Return OHLCV candles as list of dicts with keys:
        {timestamp, open, high, low, close, volume}
        """
        try:
            since_ms = int(
                (datetime.utcnow() - timedelta(days=lookback_days)).timestamp() * 1000
            )
            raw = self._exchange.fetch_ohlcv(symbol, interval, since=since_ms, limit=500)
            candles = [
                {
                    "timestamp": c[0],
                    "open":      float(c[1]),
                    "high":      float(c[2]),
                    "low":       float(c[3]),
                    "close":     float(c[4]),
                    "volume":    float(c[5]),
                }
                for c in raw
            ]
            logger.debug(f"Fetched {len(candles)} {interval} candles for {symbol}")
            return candles
        except Exception as e:
            logger.error(f"get_candles({symbol}, {interval}): {e}")
            return []

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        result = {}
        for sym in symbols:
            try:
                ticker = self._exchange.fetch_ticker(sym)
                result[sym] = float(ticker["last"])
            except Exception as e:
                logger.warning(f"LTP fetch failed {sym}: {e}")
        return result
