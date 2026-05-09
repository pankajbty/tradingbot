"""
CryptoRiskManager — risk gating + target/SL monitoring for crypto.

Key differences from equities RiskManager:
- Trade sizing is in INR (not fixed share qty)
- No "market hours" — operates 24/7
- Daily P&L resets at midnight IST (configurable)
- SL orders placed as stop-limits; falls back to manual tracking
"""
from __future__ import annotations

import logging
from datetime import datetime

from crypto_config import CRYPTO_RISK_CONFIG

logger = logging.getLogger("CryptoApp.RiskManager")


class CryptoRiskManager:
    def __init__(self, trader, config: dict = None):
        self.trader  = trader
        self._config = config if config is not None else CRYPTO_RISK_CONFIG

        self.daily_pnl: float = 0.0
        self._halted:   bool  = False
        self._reset_day: int  = datetime.now().day   # track date for daily reset

        # symbol → {side, entry_price, sl_price, target_price, sl_order_id, quantity}
        self._active_trades: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Daily reset  (called from scheduler every minute)
    # ------------------------------------------------------------------

    def maybe_daily_reset(self):
        """Reset P&L counter and halted flag at configured hour each day."""
        now = datetime.now()
        reset_hour = self._config.get("daily_reset_hour", 0)
        if now.day != self._reset_day and now.hour >= reset_hour:
            logger.info("Daily reset: P&L counter and halt flag cleared.")
            self.daily_pnl   = 0.0
            self._halted     = False
            self._reset_day  = now.day

    # ------------------------------------------------------------------
    # Pre-trade gate
    # ------------------------------------------------------------------

    def can_trade(self) -> bool:
        if self._halted:
            logger.warning("Crypto trading halted (daily loss limit reached).")
            return False

        positions = self.trader.get_positions()
        if len(positions) >= self._config["max_open_positions"]:
            logger.warning(f"Max open positions ({self._config['max_open_positions']}) reached.")
            return False

        return True

    # ------------------------------------------------------------------
    # Register trade + place SL
    # ------------------------------------------------------------------

    def register_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,        # base-currency quantity (e.g. 0.000125 BTC)
    ):
        sl_pct  = self._config["stop_loss_pct"] / 100
        tgt_pct = self._config["target_pct"]    / 100

        if side == "BUY":
            sl_price     = entry_price * (1 - sl_pct)
            target_price = entry_price * (1 + tgt_pct)
            sl_side      = "SELL"
        else:
            sl_price     = entry_price * (1 + sl_pct)
            target_price = entry_price * (1 - tgt_pct)
            sl_side      = "BUY"

        amount_inr   = quantity * entry_price
        sl_order_id  = self.trader.place_sl_order(symbol, sl_side, amount_inr, sl_price)

        self._active_trades[symbol] = {
            "side":         side,
            "entry_price":  entry_price,
            "sl_price":     sl_price,
            "target_price": target_price,
            "sl_order_id":  sl_order_id,
            "quantity":     quantity,
        }
        logger.info(
            f"Trade registered: {side} {symbol} "
            f"entry={entry_price:.4f}  SL={sl_price:.4f}  target={target_price:.4f}  "
            f"qty={quantity:.8f}"
        )

    # ------------------------------------------------------------------
    # Per-tick checks
    # ------------------------------------------------------------------

    def check_targets(self, market_data):
        """Exit positions that hit their profit target."""
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
                logger.info(
                    f"Target hit: {symbol} LTP={ltp:.4f} "
                    f"target={trade['target_price']:.4f}"
                )
                if trade["sl_order_id"]:
                    self.trader.cancel_order(trade["sl_order_id"], symbol)
                exit_side  = "SELL" if trade["side"] == "BUY" else "BUY"
                amount_inr = trade["quantity"] * ltp
                self.trader.place_order(symbol, exit_side, amount_inr, tag="TARGET")
                pnl_trade  = (
                    (ltp - trade["entry_price"]) * trade["quantity"]
                    if trade["side"] == "BUY"
                    else (trade["entry_price"] - ltp) * trade["quantity"]
                )
                self.daily_pnl += pnl_trade
                del self._active_trades[symbol]

    def check_stop_losses(self, market_data):
        """Manually close positions that have breached their SL (if SL order failed)."""
        symbols = list(self._active_trades.keys())
        if not symbols:
            return

        ltps = market_data.get_ltp(symbols)

        for symbol, trade in list(self._active_trades.items()):
            ltp = ltps.get(symbol)
            if ltp is None:
                continue

            hit_sl = (
                trade["side"] == "BUY"  and ltp <= trade["sl_price"]
            ) or (
                trade["side"] == "SELL" and ltp >= trade["sl_price"]
            )

            if hit_sl and not trade.get("sl_order_id"):
                # Only intervene if no exchange SL order was placed
                logger.warning(
                    f"SL hit (manual): {symbol} LTP={ltp:.4f} SL={trade['sl_price']:.4f}"
                )
                exit_side  = "SELL" if trade["side"] == "BUY" else "BUY"
                amount_inr = trade["quantity"] * ltp
                self.trader.place_order(symbol, exit_side, amount_inr, tag="SL")
                pnl_trade  = (
                    (ltp - trade["entry_price"]) * trade["quantity"]
                    if trade["side"] == "BUY"
                    else (trade["entry_price"] - ltp) * trade["quantity"]
                )
                self.daily_pnl += pnl_trade
                del self._active_trades[symbol]

    def cleanup_closed_trades(self):
        """Reconcile in-memory trades against actual exchange positions."""
        positions = self.trader.get_positions()
        open_symbols = {p["symbol"] for p in positions}
        for symbol in list(self._active_trades.keys()):
            if symbol not in open_symbols:
                logger.info(f"Trade closed externally: {symbol}")
                del self._active_trades[symbol]

    def update_pnl(self) -> float:
        """Refresh daily P&L from open positions and halt if limit exceeded."""
        positions = self.trader.get_positions()
        realised_pnl = self.daily_pnl  # keep realised portion
        unrealised   = sum(p.get("pnl", 0) for p in positions)
        total_pnl    = realised_pnl + unrealised

        if total_pnl <= -self._config["max_daily_loss"]:
            logger.warning(
                f"Daily loss limit hit: ₹{abs(total_pnl):.2f}. Halting crypto trading."
            )
            self._halted = True

        logger.debug(f"Crypto daily P&L: ₹{total_pnl:.2f}")
        return total_pnl

    @property
    def is_halted(self) -> bool:
        return self._halted
