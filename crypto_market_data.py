"""
CryptoMarketData — CoinDCX public REST API for OHLCV candles and LTP.

CoinDCX candles endpoint:
  GET https://public.coindcx.com/market_data/candles
  ?pair=BTCINR&interval=1m&startTime=<ms>&endTime=<ms>&limit=500

Supported intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w

Response (array of candles, oldest first):
  [ [timestamp_ms, open, high, low, close, volume], ... ]
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import requests

logger = logging.getLogger("CryptoApp.MarketData")

_CANDLES_URL = "https://public.coindcx.com/market_data/candles"
_TICKER_URL  = "https://api.coindcx.com/exchange/ticker"
_TIMEOUT     = 10


class CryptoMarketData:
    def __init__(self, trader=None):
        """
        :param trader: CryptoTrader instance (used for LTP fallback via its cache).
                       May be None — in that case LTP is fetched directly.
        """
        self._trader = trader

    # ------------------------------------------------------------------
    # OHLCV candles
    # ------------------------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        lookback_days: int = 7,
    ) -> list[dict]:
        """
        Return a list of OHLCV candle dicts for the given symbol.
        Each dict has keys: timestamp, open, high, low, close, volume
        Sorted oldest → newest.
        """
        try:
            start_ms = int(
                (datetime.utcnow() - timedelta(days=lookback_days)).timestamp() * 1000
            )
            end_ms = int(datetime.utcnow().timestamp() * 1000)

            params = {
                "pair":      symbol,
                "interval":  interval,
                "startTime": start_ms,
                "endTime":   end_ms,
                "limit":     500,
            }
            resp = requests.get(_CANDLES_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            raw = resp.json()

            # CoinDCX returns a list of lists: [timestamp, open, high, low, close, volume]
            candles = []
            for c in raw:
                if len(c) < 6:
                    continue
                candles.append({
                    "timestamp": int(c[0]),
                    "open":      float(c[1]),
                    "high":      float(c[2]),
                    "low":       float(c[3]),
                    "close":     float(c[4]),
                    "volume":    float(c[5]),
                })

            logger.debug(f"Fetched {len(candles)} {interval} candles for {symbol}")
            return candles

        except Exception as e:
            logger.error(f"get_candles({symbol}, {interval}): {e}")
            return []

    # ------------------------------------------------------------------
    # LTP
    # ------------------------------------------------------------------

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        """
        Return last traded price for each symbol.
        Uses the ticker endpoint directly (no trader reference needed).
        """
        result = {}
        try:
            tickers    = requests.get(_TICKER_URL, timeout=_TIMEOUT).json()
            ticker_map = {t["market"]: t for t in tickers}
            for sym in symbols:
                t = ticker_map.get(sym)
                if t:
                    result[sym] = float(t.get("last_price", 0) or 0)
                else:
                    logger.warning(f"No ticker for {sym}")
        except Exception as e:
            logger.error(f"get_ltp error: {e}")
        return result
