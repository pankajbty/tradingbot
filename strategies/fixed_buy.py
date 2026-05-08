import logging

from config import FIXED_BUY_CONFIG
from .base import BaseStrategy

logger = logging.getLogger("TradingApp.Strategy.FixedBuy")


class FixedBuyStrategy(BaseStrategy):
    name = "fixed_buy"

    def __init__(self, trader, market_data, risk_manager, config: dict = None):
        super().__init__(trader, market_data, risk_manager)
        self._config = config if config is not None else FIXED_BUY_CONFIG

    def run(self):
        for symbol, params in self._config["stocks"].items():
            if not self.risk_manager.can_trade():
                logger.info("FixedBuy: risk gate closed, stopping.")
                break

            qty        = params["quantity"]
            order_type = self._config.get("order_type", "MARKET")

            logger.info(f"[FixedBuy] BUY {qty} {symbol} @ {order_type}")
            order_id = self.trader.place_order(
                symbol, "BUY", qty, order_type=order_type, tag="FIXEDBUY"
            )

            if order_id:
                ltps = self.market_data.get_ltp([symbol])
                entry_price = ltps.get(symbol, 0.0)
                if entry_price > 0:
                    self.risk_manager.register_trade(symbol, "BUY", entry_price, qty)
