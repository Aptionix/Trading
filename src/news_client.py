"""
News Client — Finnhub

Fetches market-wide and company-specific financial news via Finnhub.
Free API key required: sign up at https://finnhub.io and put the key in .env:

    FINNHUB_API_KEY=your_key_here

Free tier: 60 calls/minute — comfortable with caching.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://finnhub.io/api/v1"


class NewsClient:
    """Wrapper around the Finnhub news endpoints."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")

    @property
    def configured(self) -> bool:
        """True if an API key is available."""
        return bool(self.api_key)

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        params = {**params, "token": self.api_key}
        r = requests.get(f"{BASE_URL}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ #
    # Market-wide news                                                     #
    # ------------------------------------------------------------------ #

    def get_market_news(self, category: str = "general", limit: int = 30) -> List[Dict[str, Any]]:
        """
        Latest market news.

        Args:
            category: one of "general", "forex", "crypto", "merger".
            limit:    max headlines to return.
        """
        if not self.configured:
            return []
        try:
            raw = self._get("/news", {"category": category})
        except Exception as e:
            print(f"[news] market news failed: {e}")
            return []
        return [self._normalise(a) for a in raw[:limit]]

    # ------------------------------------------------------------------ #
    # Company news                                                         #
    # ------------------------------------------------------------------ #

    def get_company_news(
        self, symbol: str, days: int = 7, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Recent news for a single company ticker."""
        if not self.configured:
            return []
        to = datetime.now().date()
        frm = to - timedelta(days=days)
        try:
            raw = self._get("/company-news", {
                "symbol": symbol,
                "from": frm.isoformat(),
                "to": to.isoformat(),
            })
        except Exception as e:
            print(f"[news] company news failed for {symbol}: {e}")
            return []
        return [self._normalise(a, symbol=symbol) for a in raw[:limit]]

    # ------------------------------------------------------------------ #
    # Industry news (aggregate of member tickers)                          #
    # ------------------------------------------------------------------ #

    def get_industry_news(
        self, tickers: List[str], days: int = 7, per_ticker: int = 5, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Aggregate recent news across a list of tickers (an industry group),
        de-duplicated and sorted newest-first.
        """
        if not self.configured:
            return []
        seen_ids = set()
        items: List[Dict[str, Any]] = []
        # Cap the number of tickers queried to stay well within rate limits.
        for sym in tickers[:8]:
            for art in self.get_company_news(sym, days=days, limit=per_ticker):
                key = art.get("id") or art.get("url")
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                items.append(art)
        items.sort(key=lambda a: a.get("datetime", 0), reverse=True)
        return items[:limit]

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalise(article: Dict[str, Any], symbol: str = "") -> Dict[str, Any]:
        """Flatten a Finnhub article into a consistent shape."""
        ts = article.get("datetime", 0)
        return {
            "id": article.get("id"),
            "headline": article.get("headline", ""),
            "summary": article.get("summary", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "image": article.get("image", ""),
            "datetime": ts,
            "time_str": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "",
            "symbol": symbol or (article.get("related", "") or ""),
        }
