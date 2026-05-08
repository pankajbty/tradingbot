import logging

from jugaad_trader import Zerodha

from config import EXCHANGE, PRODUCT, ZERODHA_CONFIG

logger = logging.getLogger("TradingApp.Trader")

_OMS = "https://kite.zerodha.com/oms"


class Trader:
    def __init__(self, credentials: dict = None):
        self._credentials = credentials if credentials is not None else ZERODHA_CONFIG
        self.kite = self._login()
        self._session = self.kite.reqsession   # authenticated requests.Session

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def _login(self) -> Zerodha:
        user_id  = self._credentials["user_id"]
        password = self._credentials["password"]

        if not user_id or not password:
            raise ValueError(
                "ZERODHA_USER_ID and ZERODHA_PASSWORD must be set in your .env file."
            )

        totp = input("\nEnter the 6-digit code from your authenticator app: ").strip()
        logger.info(f"Logging in as {user_id} ...")

        z = Zerodha(user_id=user_id, password=password, twofa=totp)
        z.login()

        # Ensure user_id is set on the object (needed for historical API params)
        if not getattr(z, "user_id", None):
            z.user_id = user_id

        # jugaad-trader stores enctoken in cookies after login.
        # The Zerodha OMS API also requires it as an Authorization header.
        enctoken = z.reqsession.cookies.get("enctoken", "")
        if enctoken:
            z.reqsession.headers.update({
                "Authorization": f"enctoken {enctoken}"
            })
            logger.info("Authorization header set from enctoken cookie.")
        else:
            logger.warning("enctoken cookie not found after login — API calls may fail.")

        logger.info("Login successful.")
        return z

    # ------------------------------------------------------------------
    # Internal OMS helpers
    # ------------------------------------------------------------------

    def _oms_get(self, path: str) -> dict:
        resp = self._session.get(f"{_OMS}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {})

    def _oms_post(self, path: str, data: dict) -> dict:
        resp = self._session.post(f"{_OMS}{path}", data=data, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {})

    def _oms_delete(self, path: str) -> dict:
        resp = self._session.delete(f"{_OMS}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {})

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = None,
        tag: str = None,
    ) -> str | None:
        data = {
            "tradingsymbol":    symbol,
            "exchange":         EXCHANGE,
            "transaction_type": transaction_type,
            "quantity":         quantity,
            "product":          PRODUCT,
            "order_type":       order_type,
            "validity":         "DAY",
        }
        if price is not None:
            data["price"] = price
        if tag:
            data["tag"] = tag[:20]

        try:
            result   = self._oms_post("/orders/regular", data)
            order_id = result.get("order_id")
            logger.info(
                f"Order placed | {transaction_type} {quantity} {symbol} "
                f"@ {order_type} | id={order_id}"
            )
            return order_id
        except Exception as e:
            logger.error(f"place_order failed for {symbol}: {e}")
            return None

    def place_sl_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        trigger_price: float,
        price: float = None,
    ) -> str | None:
        data = {
            "tradingsymbol":    symbol,
            "exchange":         EXCHANGE,
            "transaction_type": transaction_type,
            "quantity":         quantity,
            "product":          PRODUCT,
            "order_type":       "SL" if price is not None else "SL-M",
            "trigger_price":    round(trigger_price, 1),
            "validity":         "DAY",
        }
        if price is not None:
            data["price"] = round(price, 1)

        try:
            result   = self._oms_post("/orders/regular", data)
            order_id = result.get("order_id")
            logger.info(
                f"SL order placed | {transaction_type} {quantity} {symbol} "
                f"trigger={trigger_price:.2f} | id={order_id}"
            )
            return order_id
        except Exception as e:
            logger.error(f"place_sl_order failed for {symbol}: {e}")
            return None

    def cancel_order(self, order_id: str):
        try:
            self._oms_delete(f"/orders/regular/{order_id}")
            logger.info(f"Order cancelled: {order_id}")
        except Exception as e:
            logger.error(f"cancel_order failed for {order_id}: {e}")

    # ------------------------------------------------------------------
    # Positions / orders — direct OMS calls (no api_key needed)
    # ------------------------------------------------------------------

    def get_positions(self) -> list:
        try:
            data = self._oms_get("/portfolio/positions")
            return data.get("day", [])
        except Exception as e:
            logger.error(f"get_positions failed: {e}")
            return []

    def get_orders(self) -> list:
        try:
            return self._oms_get("/orders") or []
        except Exception as e:
            logger.error(f"get_orders failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Square-off
    # ------------------------------------------------------------------

    def squareoff_all_positions(self):
        positions = self.get_positions()
        squared = 0
        for pos in positions:
            qty = pos.get("quantity", 0)
            if qty == 0:
                continue
            symbol = pos["tradingsymbol"]
            side   = "SELL" if qty > 0 else "BUY"
            logger.info(f"Squaring off: {side} {abs(qty)} {symbol}")
            self.place_order(symbol, side, abs(qty), order_type="MARKET", tag="SQUAREOFF")
            squared += 1
        if squared == 0:
            logger.info("No open positions to square off.")
