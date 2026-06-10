"""
Order Executor — stub for future live order placement.

Currently read-only.  All public methods log the intended action and
raise NotImplementedError so you can wire them up when ready.

When you want to go live:
  1. Set TRADING212_DEMO=false in .env
  2. Replace the NotImplementedError stubs with the real API calls
     (Trading 212 supports market and limit orders via POST /equity/orders/*)
  3. Add position-size validation and a confirmation step before each call
"""

from dataclasses import dataclass
from typing import Optional
from src.api_client import Trading212Client


@dataclass
class OrderRequest:
    """Represents a single intended trade."""
    ticker: str
    side: str           # "BUY" or "SELL"
    quantity: float
    order_type: str     # "MARKET" or "LIMIT"
    limit_price: Optional[float] = None
    reason: str = ""


class OrderExecutor:
    """
    Executes trades via the Trading 212 API.

    Not yet active — all methods raise NotImplementedError until
    live order placement is enabled.
    """

    def __init__(self, client: Trading212Client):
        self.client = client

    def place_order(self, order: OrderRequest) -> dict:
        """
        Place a single order.

        Args:
            order: OrderRequest with side, ticker, quantity, type.

        Returns:
            API response dict when live.

        Raises:
            NotImplementedError: while in read-only mode.
        """
        self._log_intent(order)
        raise NotImplementedError(
            "Live order placement is not enabled yet. "
            "See src/order_executor.py for activation steps."
        )

    def buy(self, ticker: str, quantity: float, reason: str = "") -> dict:
        """Convenience wrapper for a market buy."""
        return self.place_order(OrderRequest(
            ticker=ticker,
            side="BUY",
            quantity=quantity,
            order_type="MARKET",
            reason=reason,
        ))

    def sell(self, ticker: str, quantity: float, reason: str = "") -> dict:
        """Convenience wrapper for a market sell."""
        return self.place_order(OrderRequest(
            ticker=ticker,
            side="SELL",
            quantity=quantity,
            order_type="MARKET",
            reason=reason,
        ))

    def limit_buy(
        self,
        ticker: str,
        quantity: float,
        limit_price: float,
        reason: str = "",
    ) -> dict:
        """Place a limit buy order."""
        return self.place_order(OrderRequest(
            ticker=ticker,
            side="BUY",
            quantity=quantity,
            order_type="LIMIT",
            limit_price=limit_price,
            reason=reason,
        ))

    def limit_sell(
        self,
        ticker: str,
        quantity: float,
        limit_price: float,
        reason: str = "",
    ) -> dict:
        """Place a limit sell order."""
        return self.place_order(OrderRequest(
            ticker=ticker,
            side="SELL",
            quantity=quantity,
            order_type="LIMIT",
            limit_price=limit_price,
            reason=reason,
        ))

    @staticmethod
    def _log_intent(order: OrderRequest) -> None:
        print(
            f"[OrderExecutor] INTENT (not executed): "
            f"{order.side} {order.quantity} x {order.ticker} "
            f"@ {order.order_type}"
            + (f" limit={order.limit_price}" if order.limit_price else "")
            + (f" | {order.reason}" if order.reason else "")
        )
