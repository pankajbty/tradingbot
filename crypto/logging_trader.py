"""
LoggingCryptoTrader — wraps CryptoTrader and persists every order to the
CryptoTradeLog Django model so it can be viewed in the admin UI.

The original crypto_trader.py is left completely untouched.
"""
from __future__ import annotations

import logging

from crypto_trader import CryptoTrader

logger = logging.getLogger("CryptoApp.LoggingTrader")

# Current strategy tag — set by the management command before running each strategy
_current_strategy: str = ""


def set_current_strategy(name: str):
    global _current_strategy
    _current_strategy = name


class LoggingCryptoTrader(CryptoTrader):
    """Subclass of CryptoTrader that writes a CryptoTradeLog row after each order."""

    def __init__(self, exchange_id: str = "coindcx", credentials: dict = None):
        super().__init__(exchange_id=exchange_id, credentials=credentials)

    def place_order(
        self,
        symbol: str,
        side: str,
        amount_inr: float,
        order_type: str = "MARKET",
        tag: str = "",
    ) -> str | None:
        # Get LTP before placing so we can log approximate price
        try:
            ltp = self._ltp(symbol)
        except Exception:
            ltp = 0.0

        order_id = super().place_order(symbol, side, amount_inr, order_type, tag)

        # Compute quantity based on amount / ltp
        qty = (amount_inr / ltp) if ltp > 0 else 0.0

        self._log(
            symbol=symbol,
            side=side,
            quantity=qty,
            price=ltp,
            amount_inr=amount_inr,
            order_id=order_id or "",
            tag=tag or "",
            status="PLACED" if order_id else "FAILED",
        )
        return order_id

    def place_sl_order(
        self,
        symbol: str,
        side: str,
        amount_inr: float,
        sl_price: float,
    ) -> str | None:
        order_id = super().place_sl_order(symbol, side, amount_inr, sl_price)
        qty = (amount_inr / sl_price) if sl_price > 0 else 0.0
        self._log(
            symbol=symbol,
            side=side,
            quantity=qty,
            price=sl_price,
            amount_inr=amount_inr,
            order_id=order_id or "",
            tag="SL",
            status="PLACED" if order_id else "FAILED",
            notes=f"sl_price={sl_price:.4f}",
        )
        return order_id

    # ------------------------------------------------------------------

    @staticmethod
    def _log(**kwargs):
        try:
            from crypto.models import CryptoTradeLog
            CryptoTradeLog.objects.create(strategy=_current_strategy, **kwargs)
        except Exception as e:
            logger.warning(f"CryptoTradeLog write failed: {e}")
