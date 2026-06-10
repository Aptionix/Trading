"""
Market Data Module

Fetches trending stocks and market indices via yfinance (no API key required).

Three watchlists:
  US_LARGE_CAP  — 40 major S&P 500 names
  US_FAST_TECH  — fast-expanding semiconductor / software / cloud companies
  UK_TOP20      — FTSE 100 top 20 by market cap (use .L suffix for yfinance)
"""

from typing import List, Dict, Any, Optional
import yfinance as yf
import pandas as pd

from src.technical_analysis import analyze as ta_analyze


# ------------------------------------------------------------------ #
# Watchlists                                                           #
# ------------------------------------------------------------------ #

US_LARGE_CAP: List[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM",
    "V", "UNH", "JNJ", "WMT", "PG", "MA", "HD", "MRK", "ABBV",
    "LLY", "PEP", "COST", "CSCO", "MCD", "ABT",
    "CRM", "NFLX", "INTC", "QCOM", "TXN", "NEE", "DIS",
    "SPGI", "AMGN", "LOW", "INTU", "ISRG", "GS", "CAT", "BABA",
    "AMD", "AVGO",
]

US_FAST_TECH: List[str] = [
    "MU",    # Micron Technology
    "SNDK",  # SanDisk (memory/storage, spun off from Western Digital)
    "MRVL",  # Marvell Technology
    "ARM",   # ARM Holdings
    "SMCI",  # Super Micro Computer
    "PLTR",  # Palantir Technologies
    "CRWD",  # CrowdStrike
    "SNOW",  # Snowflake
    "DDOG",  # Datadog
    "NET",   # Cloudflare
    "MDB",   # MongoDB
    "ON",    # ON Semiconductor
    "AMAT",  # Applied Materials
    "LRCX",  # Lam Research
    "KLAC",  # KLA Corporation
    "ASML",  # ASML Holding (NASDAQ-listed)
    "TSM",   # Taiwan Semiconductor (NYSE ADR)
    "PANW",  # Palo Alto Networks
    "DELL",  # Dell Technologies
    "HPE",   # Hewlett Packard Enterprise
    "TTD",   # The Trade Desk
]

UK_TOP20: List[str] = [
    "AZN.L",   # AstraZeneca
    "SHEL.L",  # Shell
    "HSBA.L",  # HSBC Holdings
    "ULVR.L",  # Unilever
    "RIO.L",   # Rio Tinto
    "BP.L",    # BP
    "GSK.L",   # GSK
    "DGE.L",   # Diageo
    "REL.L",   # RELX
    "BA.L",    # BAE Systems
    "NG.L",    # National Grid
    "LLOY.L",  # Lloyds Banking Group
    "GLEN.L",  # Glencore
    "LGEN.L",  # Legal & General
    "PRU.L",   # Prudential
    "IMB.L",   # Imperial Brands
    "ANTO.L",  # Antofagasta
    "SSE.L",   # SSE
    "WPP.L",   # WPP
    "VOD.L",   # Vodafone
]

ALL_WATCHLIST: List[str] = list(dict.fromkeys(US_LARGE_CAP + US_FAST_TECH + UK_TOP20))

# Static ticker → company name map. Avoids slow per-ticker yf.Ticker().info
# network calls (which made the dashboard hang). Falls back to the ticker.
NAME_MAP: Dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon",
    "NVDA": "Nvidia", "META": "Meta Platforms", "TSLA": "Tesla", "JPM": "JPMorgan Chase",
    "V": "Visa", "UNH": "UnitedHealth", "JNJ": "Johnson & Johnson", "WMT": "Walmart",
    "PG": "Procter & Gamble", "MA": "Mastercard", "HD": "Home Depot", "MRK": "Merck",
    "ABBV": "AbbVie", "LLY": "Eli Lilly", "PEP": "PepsiCo", "COST": "Costco",
    "CSCO": "Cisco", "MCD": "McDonald's", "ABT": "Abbott", "CRM": "Salesforce",
    "NFLX": "Netflix", "INTC": "Intel", "QCOM": "Qualcomm", "TXN": "Texas Instruments",
    "NEE": "NextEra Energy", "DIS": "Disney", "SPGI": "S&P Global", "AMGN": "Amgen",
    "LOW": "Lowe's", "INTU": "Intuit", "ISRG": "Intuitive Surgical", "GS": "Goldman Sachs",
    "CAT": "Caterpillar", "BABA": "Alibaba", "AMD": "AMD", "AVGO": "Broadcom",
    "MU": "Micron", "SNDK": "SanDisk", "MRVL": "Marvell", "ARM": "ARM Holdings", "SMCI": "Super Micro",
    "PLTR": "Palantir", "CRWD": "CrowdStrike", "SNOW": "Snowflake", "DDOG": "Datadog",
    "NET": "Cloudflare", "MDB": "MongoDB", "ON": "ON Semiconductor", "AMAT": "Applied Materials",
    "LRCX": "Lam Research", "KLAC": "KLA Corp", "ASML": "ASML", "TSM": "TSMC",
    "PANW": "Palo Alto Networks", "DELL": "Dell", "HPE": "HP Enterprise", "TTD": "The Trade Desk",
    "AZN.L": "AstraZeneca", "SHEL.L": "Shell", "HSBA.L": "HSBC", "ULVR.L": "Unilever",
    "RIO.L": "Rio Tinto", "BP.L": "BP", "GSK.L": "GSK", "DGE.L": "Diageo",
    "REL.L": "RELX", "BA.L": "BAE Systems", "NG.L": "National Grid", "LLOY.L": "Lloyds",
    "GLEN.L": "Glencore", "LGEN.L": "Legal & General", "PRU.L": "Prudential",
    "IMB.L": "Imperial Brands", "ANTO.L": "Antofagasta", "SSE.L": "SSE",
    "WPP.L": "WPP", "VOD.L": "Vodafone",
}


def ticker_name(ticker: str) -> str:
    """Look up a friendly company name, falling back to the ticker symbol."""
    return NAME_MAP.get(ticker, ticker)


# ------------------------------------------------------------------ #
# Industry peer groups (each with a sector-ETF benchmark)             #
# ------------------------------------------------------------------ #

PEER_GROUPS: Dict[str, Dict[str, Any]] = {
    "Semiconductors": {
        "etf": "SOXX",
        "members": [
            "NVDA", "AMD", "AVGO", "MRVL", "MU", "SNDK", "ON", "AMAT",
            "LRCX", "KLAC", "ASML", "TSM", "QCOM", "TXN", "ARM", "INTC", "SMCI",
        ],
    },
    "Megacap Tech / Software": {
        "etf": "XLK",
        "members": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "CRM", "NFLX", "PLTR",
            "SNOW", "DDOG", "NET", "MDB", "PANW", "INTU", "TTD",
        ],
    },
    "Consumer / Retail": {
        "etf": "XLY",
        "members": [
            "WMT", "COST", "HD", "LOW", "MCD", "PG", "PEP", "SBUX", "DIS", "BABA",
        ],
    },
    "Financials": {
        "etf": "XLF",
        "members": ["JPM", "GS", "V", "MA", "SPGI"],
    },
    "Healthcare": {
        "etf": "XLV",
        "members": ["UNH", "JNJ", "MRK", "ABBV", "LLY", "AMGN", "ABT", "ISRG"],
    },
    "Autos": {
        "etf": "CARZ",
        "members": ["TSLA", "F", "GM", "RIVN", "LCID", "NIO"],
    },
}

# Add auto peers to the friendly-name map.
NAME_MAP.update({
    "F": "Ford", "GM": "General Motors", "RIVN": "Rivian",
    "LCID": "Lucid", "NIO": "NIO",
    "SOXX": "iShares Semiconductor ETF", "XLK": "Tech Sector ETF",
    "XLY": "Consumer Disc. ETF", "XLF": "Financials ETF",
    "XLV": "Healthcare ETF", "CARZ": "Auto Industry ETF",
})


def find_peer_group(display_ticker: str) -> Optional[str]:
    """Return the name of the peer group a ticker belongs to, or None."""
    base = display_ticker.split("_")[0].replace(".L", "")
    for group_name, info in PEER_GROUPS.items():
        if base in info["members"]:
            return group_name
    return None


def _trading_days(calendar_days: int) -> int:
    """Approximate trading-day count for a calendar-day window (~252/year)."""
    return max(int(calendar_days * 252 / 365), 5)


_INDICES: Dict[str, str] = {
    "S&P 500":          "^GSPC",
    "NASDAQ":           "^IXIC",
    "Dow Jones":        "^DJI",
    "FTSE 100":         "^FTSE",
    "VIX (Fear Index)": "^VIX",
}


# ------------------------------------------------------------------ #
# Helper                                                               #
# ------------------------------------------------------------------ #

def t212_ticker_to_yf(t212_ticker: str) -> str:
    """
    Convert a Trading 212 ticker string to a yfinance symbol.

    Observed T212 formats:
      US equities : SYMBOL_US_EQ          e.g. AAPL_US_EQ  -> AAPL
                    (with disambiguation digits: SNDK1_US_EQ -> SNDK)
      London      : SYMBOLl_EQ            e.g. BPl_EQ -> BP.L, RRl_EQ -> RR.L
                    (trailing lowercase 'l' marks the LSE listing)
      Explicit    : SYMBOL_LSE_EQ         -> SYMBOL.L
    """
    parts = t212_ticker.split("_")
    symbol = parts[0]
    exchange = parts[1].upper() if len(parts) > 1 else ""

    # Explicit exchange segment
    if exchange in ("LSE", "LONDON"):
        return f"{symbol.rstrip('0123456789')}.L"

    # US equities — strip any trailing disambiguation digit (e.g. SNDK1 -> SNDK)
    if exchange == "US":
        return symbol.rstrip("0123456789")

    # London listings carry a trailing lowercase 'l' on the symbol (no US segment)
    if symbol.endswith("l"):
        return f"{symbol[:-1].rstrip('0123456789')}.L"

    return symbol


# ------------------------------------------------------------------ #
# Client                                                               #
# ------------------------------------------------------------------ #

class MarketDataClient:
    """Fetches market data and trending stocks using yfinance."""

    # ---------------------------------------------------------------- #
    # Market overview                                                    #
    # ---------------------------------------------------------------- #

    def get_market_summary(self) -> List[Dict[str, Any]]:
        """
        Current snapshot of major indices.

        Returns:
            List of {name, symbol, price, change, change_percent}.
        """
        results = []
        for name, symbol in _INDICES.items():
            try:
                hist = yf.Ticker(symbol).history(period="5d")
                if len(hist) < 2:
                    continue
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                results.append({
                    "name": name,
                    "symbol": symbol,
                    "price": round(current, 2),
                    "change": round(current - prev, 2),
                    "change_percent": round((current - prev) / prev * 100, 2),
                })
            except Exception:
                continue
        return results

    # ---------------------------------------------------------------- #
    # Trending movers                                                    #
    # ---------------------------------------------------------------- #

    def get_trending_stocks(
        self,
        n: int = 10,
        market: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        Return the top N stocks ranked by absolute daily % move.

        Args:
            n:      Number of results.
            market: "all" | "us" | "tech" | "uk"
        """
        if market == "us":
            tickers = US_LARGE_CAP
        elif market == "tech":
            tickers = US_FAST_TECH
        elif market == "uk":
            tickers = UK_TOP20
        else:
            tickers = ALL_WATCHLIST

        return self._fetch_movers(tickers, n, sort_by_abs=True)

    def get_uk_movers(self, n: int = 10) -> List[Dict[str, Any]]:
        """Top N UK movers by absolute daily change."""
        return self._fetch_movers(UK_TOP20, n, sort_by_abs=True)

    def get_us_tech_movers(self, n: int = 10) -> List[Dict[str, Any]]:
        """Top N fast-tech movers by absolute daily change."""
        return self._fetch_movers(US_FAST_TECH, n, sort_by_abs=True)

    def get_top_gainers(self, n: int = 5, market: str = "all") -> List[Dict[str, Any]]:
        """Top N percentage gainers today."""
        tickers = self._market_tickers(market)
        all_stocks = self._fetch_movers(tickers, len(tickers), sort_by_abs=False)
        return sorted(
            [s for s in all_stocks if s["change_percent"] > 0],
            key=lambda x: x["change_percent"], reverse=True
        )[:n]

    def get_top_losers(self, n: int = 5, market: str = "all") -> List[Dict[str, Any]]:
        """Top N percentage losers today."""
        tickers = self._market_tickers(market)
        all_stocks = self._fetch_movers(tickers, len(tickers), sort_by_abs=False)
        return sorted(
            [s for s in all_stocks if s["change_percent"] < 0],
            key=lambda x: x["change_percent"]
        )[:n]

    # ---------------------------------------------------------------- #
    # Auto-alert: daily move detector                                    #
    # ---------------------------------------------------------------- #

    def get_daily_movers(
        self,
        tickers: Optional[List[str]] = None,
        threshold: float = 6.0,
    ) -> List[Dict[str, Any]]:
        """
        Return stocks whose daily move exceeds `threshold` percent.

        Args:
            tickers:   List of yfinance symbols to check.
                       Defaults to the full combined watchlist.
            threshold: Minimum absolute % change to include.

        Returns:
            List of {ticker, name, price, change_percent, direction}.
        """
        if tickers is None:
            tickers = ALL_WATCHLIST

        all_stocks = self._fetch_movers(tickers, len(tickers), sort_by_abs=False)
        big_movers = [
            {**s, "direction": "UP" if s["change_percent"] > 0 else "DOWN"}
            for s in all_stocks
            if abs(s["change_percent"]) >= threshold
        ]
        return sorted(big_movers, key=lambda x: abs(x["change_percent"]), reverse=True)

    # ---------------------------------------------------------------- #
    # Historical data                                                    #
    # ---------------------------------------------------------------- #

    def get_stock_history(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """Fetch daily OHLCV history for a single ticker."""
        try:
            return yf.Ticker(ticker).history(period=f"{days}d")
        except Exception as e:
            print(f"[market_data] history fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    def get_intraday_history(
        self, ticker: str, days: int = 60, interval_minutes: int = 240
    ) -> pd.DataFrame:
        """
        Fetch intraday OHLCV resampled to N-minute candles.

        yfinance has no native 4h interval, so we pull 60-minute bars and
        resample. Default = 240-minute (4-hour) candles over 60 days.

        Returns an OHLCV DataFrame, or empty on failure.
        """
        try:
            raw = yf.Ticker(ticker).history(period=f"{days}d", interval="60m")
            if raw.empty:
                return pd.DataFrame()

            rule = f"{interval_minutes}min"
            resampled = raw.resample(rule).agg({
                "Open": "first", "High": "max", "Low": "min",
                "Close": "last", "Volume": "sum",
            }).dropna(subset=["Open", "High", "Low", "Close"])
            return resampled
        except Exception as e:
            print(f"[market_data] intraday fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    # ---------------------------------------------------------------- #
    # Peer / industry comparison                                         #
    # ---------------------------------------------------------------- #

    def get_peer_comparison(
        self, display_ticker: str, window_days: int = 180
    ) -> Optional[Dict[str, Any]]:
        """
        Compare a stock against its industry peers and sector ETF.

        Args:
            display_ticker: Plain ticker (e.g. "NVDA").
            window_days:    Look-back window for the rebased chart.

        Returns dict:
            group        : peer group name
            etf          : sector ETF symbol
            rebased      : DataFrame of prices indexed to 100 at the start
                           (columns = peers + ETF)
            returns_table: list of {ticker, name, is_etf, is_self,
                           ret_1m, ret_3m, ret_6m, ret_1y}
        Returns None if the ticker has no mapped peer group.
        """
        group = find_peer_group(display_ticker)
        if group is None:
            return None

        info = PEER_GROUPS[group]
        etf = info["etf"]
        symbols = list(dict.fromkeys(info["members"] + [etf]))

        try:
            # Fetch 2y so the trailing 1-year return has enough lookback;
            # the rebased chart only uses the tail window_days slice.
            raw = yf.download(
                " ".join(symbols), period="2y", auto_adjust=True,
                progress=False, group_by="ticker",
            )
        except Exception as e:
            print(f"[market_data] peer download failed: {e}")
            return None

        closes = {}
        for sym in symbols:
            try:
                if sym in raw.columns.get_level_values(0):
                    s = raw[sym]["Close"].dropna()
                    if len(s) > 5:
                        closes[sym] = s
            except Exception:
                continue

        if not closes:
            return None

        price_df = pd.DataFrame(closes)

        # Rebased chart over the requested window
        window = price_df.tail(_trading_days(window_days))
        rebased = window / window.iloc[0] * 100

        # Multi-window returns table
        def ret(series: pd.Series, n: int) -> Optional[float]:
            if len(series) <= n:
                return None
            return (series.iloc[-1] / series.iloc[-n - 1] - 1) * 100

        returns_table = []
        for sym, series in closes.items():
            returns_table.append({
                "ticker": sym,
                "name": ticker_name(sym),
                "is_etf": sym == etf,
                "is_self": sym == display_ticker,
                "ret_1m": ret(series, 21),
                "ret_3m": ret(series, 63),
                "ret_6m": ret(series, 126),
                "ret_1y": ret(series, 252),
            })
        returns_table.sort(
            key=lambda r: (r["ret_3m"] if r["ret_3m"] is not None else -999),
            reverse=True,
        )

        return {
            "group": group,
            "etf": etf,
            "rebased": rebased,
            "returns_table": returns_table,
        }

    # ---------------------------------------------------------------- #
    # Long / short recommendations                                       #
    # ---------------------------------------------------------------- #

    def get_long_short_recommendations(
        self,
        market: str = "all",
        top_n: int = 12,
        min_abs_score: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Run technical analysis across a watchlist and return the strongest
        long and short candidates.

        Args:
            market:        "all" | "us" | "tech" | "uk"
            top_n:         Max recommendations to return (split across long/short).
            min_abs_score: Minimum |score| to qualify as a recommendation.

        Returns:
            List of dicts: ticker, name, recommendation, score, price,
            daily_change, rsi14, reasons — sorted by |score| descending.
        """
        tickers = self._market_tickers(market)

        try:
            raw = yf.download(
                " ".join(tickers),
                period="3mo",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
        except Exception as e:
            print(f"[market_data] recommendation download failed: {e}")
            return []

        recs = []
        for ticker in tickers:
            try:
                if ticker in raw.columns.get_level_values(0):
                    hist = raw[ticker].dropna()
                else:
                    continue

                result = ta_analyze(hist)
                if result is None or abs(result["score"]) < min_abs_score:
                    continue

                name = ticker_name(ticker)

                recs.append({
                    "ticker": ticker,
                    "name": name,
                    **result,
                })
            except Exception:
                continue

        recs.sort(key=lambda x: abs(x["score"]), reverse=True)
        return recs[:top_n]

    # ---------------------------------------------------------------- #
    # Internal helpers                                                   #
    # ---------------------------------------------------------------- #

    def _market_tickers(self, market: str) -> List[str]:
        if market == "us":
            return US_LARGE_CAP
        if market == "tech":
            return US_FAST_TECH
        if market == "uk":
            return UK_TOP20
        return ALL_WATCHLIST

    def _fetch_movers(
        self,
        tickers: List[str],
        n: int,
        sort_by_abs: bool,
    ) -> List[Dict[str, Any]]:
        """Download data for tickers and return sorted movers."""
        if not tickers:
            return []

        try:
            raw = yf.download(
                " ".join(tickers),
                period="5d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
        except Exception as e:
            print(f"[market_data] batch download failed: {e}")
            return []

        results = []
        for ticker in tickers:
            try:
                # yfinance returns a flat DataFrame when only one ticker is given.
                if len(tickers) == 1:
                    close = raw["Close"].dropna()
                    volume = raw["Volume"].dropna()
                elif ticker in raw.columns.get_level_values(0):
                    close = raw[ticker]["Close"].dropna()
                    volume = raw[ticker]["Volume"].dropna()
                else:
                    continue

                if len(close) < 2:
                    continue

                current = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                vol = int(volume.iloc[-1]) if len(volume) else 0
                change_pct = (current - prev) / prev * 100

                name = ticker_name(ticker)

                results.append({
                    "ticker": ticker,
                    "name": name,
                    "price": round(current, 2),
                    "change_percent": round(change_pct, 2),
                    "volume": vol,
                })
            except Exception:
                continue

        key = (lambda x: abs(x["change_percent"])) if sort_by_abs else (lambda x: x["change_percent"])
        results.sort(key=key, reverse=sort_by_abs)
        return results[:n]
