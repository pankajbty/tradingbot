import logging

from config import RISK_CONFIG

logger = logging.getLogger("TradingApp.RiskManager")


class RiskManager:
    def __init__(self, trader, config: dict = None):
        self.trader = trader
        self._config = config if config is not None else RISK_CONFIG
        self.daily_pnl: float = 0.0
        # symbol -> {side, entry_price, sl_price, target_price, sl_order_id, quantity}
        self._active_trades: dict[str, dict] = {}
        self._halted: bool = False

    # ------------------------------------------------------------------
    # Pre-trade gate
    # ------------------------------------------------------------------

    def can_trade(self) -> bool:
        if self._halted:
            logger.warning("Trading halted for today (daily loss limit reached).")
            return False

        positions = self.trader.get_positions()
        open_count = sum(1 for p in positions if p["quantity"] != 0)
        if open_count >= self._config["max_open_positions"]:
            logger.warning(f"Max open positions reached ({open_count}).")
            return False

        return True

    # ------------------------------------------------------------------
    # Register a new trade and place its stop-loss order
    # ------------------------------------------------------------------

    def register_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: int,
    ):
        sl_pct  = self._config["stop_loss_pct"]  / 100
        tgt_pct = self._config["target_pct"] / 100

        if side == "BUY":
            sl_price     = entry_price * (1 - sl_pct)
            target_price = entry_price * (1 + tgt_pct)
            sl_side      = "SELL"
        else:
            sl_price     = entry_price * (1 + sl_pct)
            target_price = entry_price * (1 - tgt_pct)
            sl_side      = "BUY"

        sl_order_id = self.trader.place_sl_order(symbol, sl_side, quantity, sl_price)

        self._active_trades[symbol] = {
            "side":         side,
            "entry_price":  entry_price,
            "sl_price":     sl_price,
            "target_price": target_price,
            "sl_order_id":  sl_order_id,
            "quantity":     quantity,
        }
        logger.info(
            f"Trade registered: {side} {symbol} entry={entry_price:.2f} "
            f"SL={sl_price:.2f} target={target_price:.2f}"
        )

    # ------------------------------------------------------------------
    # Per-minute checks
    # ------------------------------------------------------------------

    def check_targets(self, market_data):
        """Exit any position that has hit its profit target."""
        symbols = list(self._active_trades.keys())
        if not symbols:
            return

        ltps = market_data.get_ltp(symbols)

        for symbol, trade in list(self._active_trades.items()):
            ltp = ltps.get(symbol)
            if ltp is None:
                continue

            hit = (
                trade["side"] == "BUY"  and ltp >= trade["target_price"]
            ) or (
                trade["side"] == "SELL" and ltp <= trade["target_price"]
            )

            if hit:
                logger.info(f"Target hit: {symbol} LTP={ltp:.2f} target={trade['target_price']:.2f}")
                if trade["sl_order_id"]:
                    self.trader.cancel_order(trade["sl_order_id"])
                exit_side = "SELL" if trade["side"] == "BUY" else "BUY"
                self.trader.place_order(
                    symbol, exit_side, trade["quantity"],
                    order_type="MARKET", tag="TARGET",
                )
                del self._active_trades[symbol]

    def cleanup_closed_trades(self):
        """Remove stale entries for positions that were closed by SL or externally."""
        positions = self.trader.get_positions()
        open_symbols = {p["tradingsymbol"] for p in positions if p["quantity"] != 0}
        for symbol in list(self._active_trades.keys()):
            if symbol not in open_symbols:
                logger.info(f"Trade closed (SL hit or external exit): {symbol}")
                del self._active_trades[symbol]

    def update_pnl(self) -> float:
        """Refresh daily P&L and halt trading if max loss is breached."""
        positions = self.trader.get_positions()
        self.daily_pnl = sum(p.get("pnl", 0) for p in positions)

        if self.daily_pnl <= -self._config["max_daily_loss"]:
            logger.warning(
                f"Daily loss limit hit: ₹{abs(self.daily_pnl):.2f}. Halting new trades."
            )
            self._halted = True

        logger.debug(f"Daily P&L: ₹{self.daily_pnl:.2f}")
        return self.daily_pnl

    @property
    def is_halted(self) -> bool:
        return self._halted
