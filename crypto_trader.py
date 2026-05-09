"""
CryptoTrader — CoinDCX REST API client (no ccxt dependency).

CoinDCX API docs: https://docs.coindcx.com/

Authentication (all private endpoints):
  - POST body always includes {"timestamp": <ms>}
  - HMAC-SHA256 signature over the JSON body using api_secret
  - Headers: X-AUTH-APIKEY, X-AUTH-SIGNATURE, Content-Type: application/json

Symbol format used everywhere: "BTCINR", "ETHINR", "SOLINR" (no slash).

Public interface expected by strategies and risk manager:
  place_order(symbol, side, amount_inr, order_type, tag) → order_id | None
  place_sl_order(symbol, side, amount_inr, sl_price)     → order_id | None
  cancel_order(order_id, symbol)                         → bool
  get_positions()  → [{symbol, side, quantity, entry_price, pnl}]
  get_balance()    → {currency: available_amount}
  get_ltp(symbols) → {symbol: price}
  squareoff_all_positions()
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

import requests

logger = logging.getLogger("CryptoApp.Trader")

_BASE    = "https://api.coindcx.com"
_TIMEOUT = 10   # seconds


class CryptoTrader:
    def __init__(self, exchange_id: str = "coindcx", credentials: dict = None):
        creds = credentials or {}
        self._api_key    = creds.get("api_key", "")
        self._api_secret = creds.get("api_secret", "")
        # In-memory position book: symbol → {side, quantity, entry_price}
        self._positions: dict[str, dict] = {}
        logger.info("CryptoTrader initialised — CoinDCX direct REST API")

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _sign(self, body: dict) -> tuple[str, str]:
        """Return (serialised_json, hmac_signature) for a private request."""
        serialised = json.dumps(body, separators=(",", ":"))
        sig = hmac.new(
            self._api_secret.encode("utf-8"),
            msg=serialised.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return serialised, sig

    def _private_post(self, path: str, payload: dict) -> dict | list:
        payload["timestamp"] = int(round(time.time() * 1000))
        body, sig = self._sign(payload)
        headers = {
            "Content-Type":     "application/json",
            "X-AUTH-APIKEY":    self._api_key,
            "X-AUTH-SIGNATURE": sig,
        }
        resp = requests.post(f"{_BASE}{path}", data=body, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _public_get(self, path: str, params: dict | None = None) -> dict | list:
        resp = requests.get(f"{_BASE}{path}", params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Price helpers
    # ------------------------------------------------------------------

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        """Return last traded price for each symbol from CoinDCX ticker."""
        result = {}
        try:
            tickers    = self._public_get("/exchange/ticker")   # returns a list
            ticker_map = {t["market"]: t for t in tickers}
            for sym in symbols:
                t = ticker_map.get(sym)
                if t:
                    result[sym] = float(t.get("last_price", 0) or 0)
                else:
                    logger.warning(f"No ticker found for {sym}")
        except Exception as e:
            logger.error(f"get_ltp error: {e}")
        return result

    def _ltp(self, symbol: str) -> float:
        prices = self.get_ltp([symbol])
        return prices.get(symbol, 0.0)

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,              # "BUY" or "SELL"
        amount_inr: float,      # ₹ value — auto-converted to quantity
        order_type: str = "MARKET",
        tag: str = "",
    ) -> str | None:
        """
        Place a market (or limit) order on CoinDCX.
        amount_inr is in ₹ — trader calculates the correct crypto quantity.
        """
        try:
            price = self._ltp(symbol)
            if price <= 0:
                logger.error(f"Cannot place order for {symbol}: LTP is zero")
                return None

            quantity = round(amount_inr / price, 8)

            order_type_map = {
                "MARKET": "market_order",
                "LIMIT":  "limit_order",
            }
            payload = {
                "market":          symbol,
                "side":            side.lower(),
                "order_type":      order_type_map.get(order_type, "market_order"),
                "quantity":        str(quantity),
                "client_order_id": tag or "",
            }

            resp     = self._private_post("/exchange/v1/orders/create", payload)
            orders   = resp.get("orders", [resp]) if isinstance(resp, dict) else [resp]
            order    = orders[0] if orders else {}
            order_id = str(order.get("id", ""))

            logger.info(
                f"[{tag or 'ORDER'}] {side} {symbol}  qty={quantity:.8f}  "
                f"~₹{amount_inr:.0f}  order_id={order_id}"
            )

            # Update in-memory position book
            if side == "BUY":
                self._positions[symbol] = {
                    "side":        "BUY",
                    "quantity":    quantity,
                    "entry_price": price,
                }
            elif side == "SELL" and symbol in self._positions:
                del self._positions[symbol]

            return order_id

        except requests.HTTPError as e:
            body = e.response.text if e.response else str(e)
            logger.error(f"place_order HTTP {e.response.status_code}: {symbol} {side} — {body}")
            return None
        except Exception as e:
            logger.error(f"place_order failed: {symbol} {side} — {e}")
            return None

    def place_sl_order(
        self,
        symbol: str,
        side: str,
        amount_inr: float,
        sl_price: float,
    ) -> str | None:
        """
        Place a stop-limit order at sl_price on CoinDCX.
        Limit price is set 0.2% beyond the SL to guarantee fill.
        """
        try:
            quantity     = round(amount_inr / sl_price, 8)
            limit_price  = sl_price * (0.998 if side == "SELL" else 1.002)

            payload = {
                "market":     symbol,
                "side":       side.lower(),
                "order_type": "stop_limit_order",
                "quantity":   str(quantity),
                "price":      str(round(limit_price, 2)),
                "stop_price": str(round(sl_price, 2)),
            }
            resp     = self._private_post("/exchange/v1/orders/create", payload)
            orders   = resp.get("orders", [resp]) if isinstance(resp, dict) else [resp]
            order    = orders[0] if orders else {}
            order_id = str(order.get("id", ""))
            logger.info(f"SL order placed: {side} {symbol} SL=₹{sl_price:.2f}  id={order_id}")
            return order_id

        except Exception as e:
            logger.warning(
                f"SL order failed for {symbol} (will fall back to manual tracking): {e}"
            )
            return None

    def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            self._private_post("/exchange/v1/orders/cancel", {"id": order_id})
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.warning(f"cancel_order {order_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Positions / balance
    # ------------------------------------------------------------------

    def get_positions(self) -> list[dict]:
        """
        Return in-memory tracked open positions with live P&L.

        CoinDCX is a spot exchange — there is no server-side 'positions'
        endpoint. The bot tracks what it has bought and not yet sold.
        """
        if not self._positions:
            return []

        ltps   = self.get_ltp(list(self._positions.keys()))
        result = []
        for sym, pos in self._positions.items():
            ltp = ltps.get(sym, pos["entry_price"])
            pnl = (ltp - pos["entry_price"]) * pos["quantity"]
            result.append({
                "symbol":      sym,
                "side":        pos["side"],
                "quantity":    pos["quantity"],
                "entry_price": pos["entry_price"],
                "pnl":         pnl,
            })
        return result

    def get_balance(self) -> dict[str, float]:
        """Return available balances from CoinDCX account."""
        try:
            data = self._private_post("/exchange/v1/users/balances", {})
            if isinstance(data, list):
                return {
                    b["currency"]: float(b.get("balance", 0) or 0)
                    for b in data
                    if float(b.get("balance", 0) or 0) > 0
                }
            return {}
        except Exception as e:
            logger.warning(f"get_balance error: {e}")
            return {}

    def squareoff_all_positions(self):
        """Market-sell all tracked open long positions."""
        for sym, pos in list(self._positions.items()):
            exit_side  = "SELL" if pos["side"] == "BUY" else "BUY"
            ltp        = self._ltp(sym)
            amount_inr = pos["quantity"] * ltp
            self.place_order(sym, exit_side, amount_inr, tag="SQUAREOFF")
        logger.info("All crypto positions squared off.")
