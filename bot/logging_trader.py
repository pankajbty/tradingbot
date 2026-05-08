"""
LoggingTrader — wraps the core Trader class and persists every order
to the TradeLog Django model so it can be viewed in the admin UI.

The original trader.py is left completely untouched.
"""
import logging

from trader import Trader

logger = logging.getLogger("TradingApp.LoggingTrader")

# current strategy tag is set by the management command before running each strategy
_current_strategy: str = ""


def set_current_strategy(name: str):
    global _current_strategy
    _current_strategy = name


class LoggingTrader(Trader):
    """Subclass of Trader that writes a TradeLog row after each order."""

    def __init__(self, credentials: dict = None):
        super().__init__(credentials=credentials)

    def place_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = None,
        tag: str = None,
    ) -> str | None:
        order_id = super().place_order(
            symbol, transaction_type, quantity, order_type, price, tag
        )
        self._log(
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=order_type,
            order_id=order_id or "",
            tag=tag or "",
            status="PLACED" if order_id else "FAILED",
        )
        return order_id

    def place_sl_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        trigger_price: float,
        price: float = None,
    ) -> str | None:
        order_id = super().place_sl_order(
            symbol, transaction_type, quantity, trigger_price, price
        )
        self._log(
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type="SL" if price else "SL-M",
            order_id=order_id or "",
            tag="SL",
            status="PLACED" if order_id else "FAILED",
            notes=f"trigger={trigger_price:.2f}",
        )
        return order_id

    # ------------------------------------------------------------------

    @staticmethod
    def _log(**kwargs):
        try:
            from bot.models import TradeLog
            TradeLog.objects.create(strategy=_current_strategy, **kwargs)
        except Exception as e:
            logger.warning(f"TradeLog write failed: {e}")
