import csv
import io
import logging
from datetime import datetime, timedelta

import requests as _requests
from jugaad_trader import Zerodha

from config import EXCHANGE

logger = logging.getLogger("TradingApp.MarketData")

_INSTRUMENTS_URL = f"https://api.kite.trade/instruments/{EXCHANGE}"


class MarketData:
    def __init__(self, kite: Zerodha):
        self.kite = kite
        self._token_cache: dict[str, int] = {}
        self._load_instruments()

    # ------------------------------------------------------------------
    # Download instruments CSV once at startup to build token cache
    # (public endpoint — no auth required)
    # ------------------------------------------------------------------

    def _load_instruments(self):
        logger.info("Downloading instruments list from Zerodha ...")
        try:
            resp = _requests.get(_INSTRUMENTS_URL, timeout=15)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                symbol = row["tradingsymbol"]
                token  = int(row["instrument_token"])
                self._token_cache[symbol] = token
            logger.info(f"Loaded {len(self._token_cache)} instruments.")
        except Exception as e:
            logger.error(f"Failed to load instruments CSV: {e}")

    # ------------------------------------------------------------------
    # Instrument token (from cache built above)
    # ------------------------------------------------------------------

    def get_instrument_token(self, symbol: str) -> int | None:
        token = self._token_cache.get(symbol)
        if token is None:
            logger.error(
                f"Instrument token not found for '{symbol}'. "
                f"Check the symbol is a valid NSE tradingsymbol."
            )
        return token

    # ------------------------------------------------------------------
    # Live quotes — derived from the last completed 1-minute candle
    # (kite.historical_data works reliably; REST quote endpoints do not)
    # ------------------------------------------------------------------

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        result = {}
        for symbol in symbols:
            candles = self.get_historical_candles(symbol, interval="minute", lookback_days=1)
            if candles:
                result[symbol] = candles[-1]["close"]
            else:
                logger.warning(f"get_ltp: no candle data for {symbol}")
        return result

    def get_ohlc(self, symbols: list[str]) -> dict[str, dict]:
        """Returns today's running OHLC from 1-min candles."""
        result = {}
        for symbol in symbols:
            candles = self.get_historical_candles(symbol, interval="minute", lookback_days=1)
            if not candles:
                continue
            today = datetime.now().date()
            today_candles = [c for c in candles if c["date"].date() == today]
            if today_candles:
                result[symbol] = {
                    "open":  today_candles[0]["open"],
                    "high":  max(c["high"] for c in today_candles),
                    "low":   min(c["low"]  for c in today_candles),
                    "close": today_candles[-1]["close"],
                }
        return result

    # ------------------------------------------------------------------
    # Historical candles — direct OMS call (no api_key needed)
    # ------------------------------------------------------------------

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        lookback_days: int = 5,
    ) -> list[dict]:
        """
        interval: minute, 3minute, 5minute, 10minute, 15minute,
                  30minute, 60minute, day
        """
        token = self.get_instrument_token(symbol)
        if token is None:
            return []

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=lookback_days)

        # Match exact format Zerodha's web app uses (captured from browser):
        # /oms/instruments/historical/{token}/{interval}?user_id=...&oi=1&from=YYYY-MM-DD&to=YYYY-MM-DD
        url = (
            f"https://kite.zerodha.com/oms/instruments/historical"
            f"/{token}/{interval}"
        )
        params = {
            "user_id": self.kite.user_id,
            "oi":      1,
            "from":    from_date.strftime("%Y-%m-%d"),
            "to":      to_date.strftime("%Y-%m-%d"),
        }
        try:
            # Build and print curl for Postman testing
            req = _requests.Request("GET", url, params=params,
                                    headers=dict(self.kite.reqsession.headers),
                                    cookies=dict(self.kite.reqsession.cookies))
            prepared = req.prepare()
            headers_str = " \\\n  ".join(
                f"-H '{k}: {v}'" for k, v in prepared.headers.items()
            )
            cookies_str = "; ".join(
                f"{k}={v}" for k, v in self.kite.reqsession.cookies.items()
            )
            curl = (
                f"\n--- CURL ---\n"
                f"curl '{prepared.url}' \\\n"
                f"  {headers_str}"
                + (f" \\\n  -b '{cookies_str}'" if cookies_str else "")
                + "\n------------\n"
            )
            # logger.info(curl)

            resp = self.kite.reqsession.get(url, params=params, timeout=15)
            resp.raise_for_status()
            body = resp.json()
            if body.get("status") == "error":
                raise ValueError(body.get("message", "API error"))
            candles = []
            for c in body.get("data", {}).get("candles", []):
                # Parse timestamp — handle both with and without timezone
                ts = c[0]
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                except ValueError:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                candles.append({
                    "date":   dt,
                    "open":   c[1],
                    "high":   c[2],
                    "low":    c[3],
                    "close":  c[4],
                    "volume": c[5],
                })
            return candles
        except Exception as e:
            logger.error(f"get_historical_candles failed for {symbol}: {e}")
            return []
