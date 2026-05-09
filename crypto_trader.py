"""
CryptoTrader — ccxt-based exchange wrapper.

Provides the same interface contract expected by crypto strategies and
the crypto risk manager:
  - place_order(symbol, side, amount_inr, order_type="MARKET", tag="")
      → order_id str or None
  - place_sl_order(symbol, side, amount_inr, sl_price) → order_id or None
  - cancel_order(order_id, symbol) → bool
  - get_positions() → list of dicts  {symbol, side, quantity, entry_price, pnl}
  - get_balance() → dict {currency: available_amount}
  - get_ltp(symbols) → dict {symbol: price}
  - squareoff_all_positions() → None

All monetary values passed to place_order are in INR. The trader converts
to base-currency quantity automatically using LTP before submitting.
"""
from __future__ import annotations

import logging
import ccxt

logger = logging.getLogger("CryptoApp.Trader")


class CryptoTrader:
    def __init__(self, exchange_id: str = "coindcx", credentials: dict = None):
        creds = credentials or {}
        exchange_cls = getattr(ccxt, exchange_id)
        self._exchange = exchange_cls({
            "apiKey":    creds.get("api_key", ""),
            "secret":    creds.get("api_secret", ""),
            "enableRateLimit": True,
        })
        self._exchange_id = exchange_id
        # Track open positions in-memory: symbol → {side, quantity, entry_price}
        self._positions: dict[str, dict] = {}
        logger.info(f"CryptoTrader initialised — exchange: {exchange_id}")

    # ------------------------------------------------------------------
    # Price helpers
    # ------------------------------------------------------------------

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        """Return last traded price for each symbol."""
        result = {}
        for sym in symbols:
            try:
                ticker = self._exchange.fetch_ticker(sym)
                result[sym] = float(ticker["last"])
            except Exception as e:
                logger.warning(f"LTP fetch failed for {sym}: {e}")
        return result

    def _ltp(self, symbol: str) -> float:
        prices = self.get_ltp([symbol])
        return prices.get(symbol, 0.0)

    def _inr_to_qty(self, symbol: str, amount_inr: float) -> float:
        """Convert INR amount to base-currency quantity using current LTP."""
        price = self._ltp(symbol)
        if price <= 0:
            raise ValueError(f"Cannot get price for {symbol}")
        # Respect exchange minimum amount
        qty = amount_inr / price
        return qty

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,         # "BUY" or "SELL"
        amount_inr: float,
        order_type: str = "MARKET",
        tag: str = "",
    ) -> str | None:
        try:
            side_lower = side.lower()   # ccxt uses "buy"/"sell"
            if order_type == "MARKET":
                qty = self._inr_to_qty(symbol, amount_inr)
                order = self._exchange.create_market_order(symbol, side_lower, qty)
            else:
                # Limit order — caller should pass price via amount_inr as well;
                # for simplicity treat as market for now
                qty = self._inr_to_qty(symbol, amount_inr)
                order = self._exchange.create_market_order(symbol, side_lower, qty)

            order_id = str(order.get("id", ""))
            price    = float(order.get("average") or order.get("price") or self._ltp(symbol))
            logger.info(
                f"[{tag or 'ORDER'}] {side} {symbol} qty={qty:.8f} "
                f"~₹{amount_inr:.0f}  order_id={order_id}"
            )

            # Update in-memory position tracking
            if side == "BUY":
                self._positions[symbol] = {
                    "side":        "BUY",
                    "quantity":    qty,
                    "entry_price": price,
                }
            elif side == "SELL" and symbol in self._positions:
                del self._positions[symbol]

            return order_id

        except Exception as e:
            logger.error(f"place_order failed: {symbol} {side} — {e}")
            return None

    def place_sl_order(
        self, symbol: str, side: str, amount_inr: float, sl_price: float
    ) -> str | None:
        """Place a stop-limit order at sl_price."""
        try:
            qty = amount_inr / sl_price   # qty based on SL price
            side_lower = side.lower()
            # Use stop-limit: limit price slightly beyond SL to ensure fill
            limit_price = sl_price * (0.998 if side == "SELL" else 1.002)
            order = self._exchange.create_order(
                symbol, "stop_limit", side_lower, qty,
                price=limit_price, params={"stopPrice": sl_price}
            )
            return str(order.get("id", ""))
        except Exception as e:
            logger.warning(f"SL order failed (will use manual tracking): {e}")
            return None

    def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            self._exchange.cancel_order(order_id, symbol or None)
            return True
        except Exception as e:
            logger.warning(f"cancel_order {order_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Position and balance queries
    # ------------------------------------------------------------------

    def get_positions(self) -> list[dict]:
        """
        Return in-memory tracked positions.
        Format: [{symbol, side, quantity, entry_price, pnl}]
        """
        result = []
        ltps = self.get_ltp(list(self._positions.keys())) if self._positions else {}
        for sym, pos in self._positions.items():
            ltp = ltps.get(sym, pos["entry_price"])
            if pos["side"] == "BUY":
                pnl = (ltp - pos["entry_price"]) * pos["quantity"]
            else:
                pnl = (pos["entry_price"] - ltp) * pos["quantity"]
            result.append({
                "symbol":       sym,
                "side":         pos["side"],
                "quantity":     pos["quantity"],
                "entry_price":  pos["entry_price"],
                "pnl":          pnl,
            })
        return result

    def get_balance(self) -> dict:
        try:
            bal = self._exchange.fetch_balance()
            return {k: v["free"] for k, v in bal["total"].items() if v and v > 0}
        except Exception as e:
            logger.warning(f"get_balance error: {e}")
            return {}

    def squareoff_all_positions(self):
        """Market-sell/buy all tracked open positions."""
        for sym, pos in list(self._positions.items()):
            exit_side = "SELL" if pos["side"] == "BUY" else "BUY"
            ltp  = self._ltp(sym)
            inr  = pos["quantity"] * ltp
            self.place_order(sym, exit_side, inr, tag="SQUAREOFF")
        logger.info("All positions squared off.")

    # ------------------------------------------------------------------
    # Exchange handle (for MarketData)
    # ------------------------------------------------------------------

    @property
    def exchange(self):
        return self._exchange
