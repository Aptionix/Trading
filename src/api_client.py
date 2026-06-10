"""
Trading 212 API Client

Authentication: HTTP Basic Auth
  Combine API_KEY:API_SECRET → Base64-encode → send as "Authorization: Basic <token>"

Rate limits vary per endpoint (see comments on each method).
429 responses are retried with exponential backoff using the Retry-After header.

IMPORTANT: The T212 Public API only works with Invest and Stocks ISA accounts.
           It does NOT work with CFD accounts (including CFD Demo accounts).
           Use an Invest account (or Invest Practice/Demo if available).

Documentation: https://docs.trading212.com/api
"""

import base64
import os
import time
from typing import Dict, List, Optional, Any

import requests
from dotenv import load_dotenv

load_dotenv()

LIVE_BASE_URL = "https://live.trading212.com/api/v0"
DEMO_BASE_URL = "https://demo.trading212.com/api/v0"

_MAX_RETRIES = 3


class Trading212Client:
    """Client for the Trading 212 Public REST API (Invest / ISA only)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        demo: bool = False,
    ):
        """
        Args:
            api_key:    T212 API Key.    Reads TRADING212_API_KEY from .env if omitted.
            api_secret: T212 API Secret. Reads TRADING212_API_SECRET from .env if omitted.
            demo:       True → connect to the Practice (Demo) Invest endpoint.
        """
        self.api_key = api_key or os.getenv("TRADING212_API_KEY")
        self.api_secret = api_secret or os.getenv("TRADING212_API_SECRET")

        if not self.api_key:
            raise ValueError("TRADING212_API_KEY missing from .env")
        if not self.api_secret:
            raise ValueError("TRADING212_API_SECRET missing from .env")

        self.base_url = DEMO_BASE_URL if demo else LIVE_BASE_URL

        # HTTP Basic Auth: Base64(key:secret)
        encoded = base64.b64encode(
            f"{self.api_key}:{self.api_secret}".encode()
        ).decode()

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET with automatic retry on 429 rate-limit responses."""
        url = f"{self.base_url}{path}"
        for attempt in range(_MAX_RETRIES):
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 429:
                # Prefer x-ratelimit-reset (Unix timestamp) over Retry-After
                reset_ts = r.headers.get("x-ratelimit-reset")
                if reset_ts:
                    wait = max(float(reset_ts) - time.time() + 0.5, 1.0)
                else:
                    wait = max(float(r.headers.get("Retry-After", 5)), 5.0)
                print(f"[T212] Rate limited — waiting {wait:.1f}s (attempt {attempt+1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        # Final attempt after all retries
        r = self.session.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def _get_paginated(self, path: str, max_pages: Optional[int] = None) -> List[Any]:
        """
        Follow nextPagePath until exhausted (or max_pages reached), return items.

        The history endpoints are rate-limited (6 req/min), so callers that only
        need recent rows should pass max_pages to avoid a slow full crawl.
        """
        items = []
        next_path = path
        pages = 0
        while next_path:
            # T212's nextPagePath already includes the '/api/v0' prefix that
            # base_url also carries — strip it so we don't double the path.
            if next_path.startswith("/api/v0"):
                next_path = next_path[len("/api/v0"):]
            data = self._get(next_path)
            items.extend(data.get("items", []))
            pages += 1
            if max_pages and pages >= max_pages:
                break
            next_path = data.get("nextPagePath")  # None when last page
        return items

    # ------------------------------------------------------------------ #
    # Account  (rate limit: 1 req / 5s)                                   #
    # ------------------------------------------------------------------ #

    def get_account_summary(self) -> Dict[str, Any]:
        """
        Full account snapshot: cash, invested capital, P&L, total value.

        Response keys include: id, currencyCode, cash, invested, ppl,
        result, free, blocked, pieCash, total.
        """
        return self._get("/equity/account/summary")

    def get_account_cash(self) -> Dict[str, Any]:
        """
        Returns a normalised cash dict using consistent field names across
        the codebase, flattened from the nested account summary response.

        Keys: free, blocked, pieCash, invested, ppl, result, total, currency
        """
        s = self.get_account_summary()
        cash = s.get("cash", {})
        inv  = s.get("investments", {})
        return {
            "id":       s.get("id"),
            "currency": s.get("currency", ""),
            "free":     cash.get("availableToTrade", 0),
            "blocked":  cash.get("reservedForOrders", 0),
            "pieCash":  cash.get("inPies", 0),
            "invested": inv.get("totalCost", 0),
            "ppl":      inv.get("unrealizedProfitLoss", 0),
            "result":   inv.get("realizedProfitLoss", 0),
            "total":    s.get("totalValue", 0),
        }

    # ------------------------------------------------------------------ #
    # Positions  (rate limit: 1 req / 1s)                                 #
    # ------------------------------------------------------------------ #

    def get_portfolio(self) -> List[Dict[str, Any]]:
        """
        All open equity positions.

        Each item: ticker, quantity, averagePrice, currentPrice, ppl,
        initialFillDate, frontend, maxBuy, maxSell, pieQuantity.
        """
        return self._get("/equity/positions")

    # ------------------------------------------------------------------ #
    # Orders  (rate limit: 1 req / 5s pending; 6 req/min historical)      #
    # ------------------------------------------------------------------ #

    def get_orders(self) -> List[Dict[str, Any]]:
        """All currently pending (unfilled) orders."""
        return self._get("/equity/orders")

    def get_order_history(
        self, limit: int = 50, max_pages: Optional[int] = None,
        ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Historical orders, newest first, auto-paginated.

        Args:
            limit:     page size (max 50).
            max_pages: cap the crawl (endpoint allows only 6 req/min, so a full
                       unfiltered history on an active account is very slow).
            ticker:    full T212 ticker (e.g. "NVDA_US_EQ") to fetch only that
                       instrument's orders — returns all its trades in 1-2 pages.
        """
        path = f"/equity/history/orders?limit={min(limit, 50)}"
        if ticker:
            path += f"&ticker={ticker}"
        return self._get_paginated(path, max_pages=max_pages)

    def get_ticker_markers(
        self, t212_ticker: str, max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """
        All filled buy/sell trade points for ONE instrument, via the history
        endpoint's ticker filter. Fast (usually a single page) and complete.

        Returns a list of {side, price, quantity, date, name}.
        """
        markers: List[Dict[str, Any]] = []
        for entry in self.get_order_history(limit=50, max_pages=max_pages, ticker=t212_ticker):
            order = entry.get("order", {})
            fill = entry.get("fill", {})
            if order.get("status") != "FILLED":
                continue
            price = fill.get("price")
            if price is None:
                continue
            markers.append({
                "side": order.get("side", ""),
                "price": price,
                "quantity": fill.get("quantity", order.get("filledQuantity", 0)),
                "date": fill.get("filledAt", order.get("createdAt", "")),
                "name": order.get("instrument", {}).get("name", ""),
            })
        return markers

    def get_trade_markers(self, max_pages: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse recent filled orders into clean buy/sell trade points,
        grouped by display ticker.

        Only the most recent `max_pages` pages (≈50 orders each) are scanned,
        which keeps this fast and within the 6 req/min history rate limit.
        That covers the markers shown on the price charts; the average-entry
        line (from the live position) always reflects the full cost basis.

        Returns:
            { "NVDA": [ {side, price, quantity, date}, ... ], ... }
            Only FILLED orders with a recorded fill price are included.
        """
        markers: Dict[str, List[Dict[str, Any]]] = {}
        for entry in self.get_order_history(limit=50, max_pages=max_pages):
            order = entry.get("order", {})
            fill  = entry.get("fill", {})

            if order.get("status") != "FILLED":
                continue
            price = fill.get("price")
            if price is None:
                continue

            display_ticker = order.get("ticker", "").split("_")[0]
            markers.setdefault(display_ticker, []).append({
                "side":     order.get("side", ""),       # BUY / SELL
                "price":    price,
                "quantity": fill.get("quantity", order.get("filledQuantity", 0)),
                "date":     fill.get("filledAt", order.get("createdAt", "")),
                "name":     order.get("instrument", {}).get("name", display_ticker),
            })
        return markers

    # ------------------------------------------------------------------ #
    # Instruments  (rate limit: 1 req / 50s)                              #
    # ------------------------------------------------------------------ #

    def get_instruments(self) -> List[Dict[str, Any]]:
        """All tradeable instruments with metadata."""
        return self._get("/equity/metadata/instruments")

    def get_instrument(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Look up one instrument by T212 ticker. Returns None if not found."""
        for inst in self.get_instruments():
            if inst.get("ticker") == ticker:
                return inst
        return None
