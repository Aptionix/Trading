"""
Dashboard Common

Shared constants, cached data loaders, and helpers used across all
dashboard pages. Streamlit's cache is process-global, so any page calling
these loaders shares the same cached results (and the same rate-limit budget).
"""

import time
from typing import Optional

import os

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Dark Plotly template app-wide, with transparent backgrounds so charts
# blend into the Terminal Dark theme.
pio.templates.default = "plotly_dark"
pio.templates["plotly_dark"].layout.paper_bgcolor = "rgba(0,0,0,0)"
pio.templates["plotly_dark"].layout.plot_bgcolor = "rgba(0,0,0,0)"

from src.api_client import Trading212Client
from src.portfolio import PortfolioAnalyzer
from src.market_data import MarketDataClient, t212_ticker_to_yf
from src.technical_analysis import sma, ema
from src.ml_predictor import predict as ml_predict
from src.news_client import NewsClient

# ────────────────────────────────────────────────────────────
# Theme constants
# ────────────────────────────────────────────────────────────

GREEN = "#00E5A0"   # neon green (gains)
RED   = "#FF5252"   # neon red (losses)
BLUE  = "#29B6F6"   # cyan accent
GREY  = "#6b7280"
BLACK = "#000000"

# Single source of truth: set TRADING212_DEMO in .env (true=practice, false=live)
DEMO = os.getenv("TRADING212_DEMO", "true").lower() == "true"

# Currency code → display symbol
_CURRENCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€", "JPY": "¥"}


def currency_symbol(code: str) -> str:
    """Return the display symbol for a currency code (falls back to 'code ')."""
    return _CURRENCY_SYMBOLS.get((code or "").upper(), f"{code} ")


# ────────────────────────────────────────────────────────────
# Trading 212 loaders
# ────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def load_account():
    return Trading212Client(demo=DEMO).get_account_cash()


@st.cache_data(ttl=120, show_spinner=False)
def load_positions():
    client = Trading212Client(demo=DEMO)
    time.sleep(1)
    return client.get_portfolio()


@st.cache_data(ttl=120, show_spinner=False)
def load_trade_markers():
    client = Trading212Client(demo=DEMO)
    time.sleep(1)
    return client.get_trade_markers()


@st.cache_data(ttl=300, show_spinner=False)
def load_ticker_markers(t212_ticker: str):
    """All buy/sell fills for one instrument (via the history ticker filter)."""
    return Trading212Client(demo=DEMO).get_ticker_markers(t212_ticker)


# ────────────────────────────────────────────────────────────
# Market-data loaders
# ────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_history(yf_ticker: str, days: int = 120):
    return MarketDataClient().get_stock_history(yf_ticker, days=days)


@st.cache_data(ttl=300, show_spinner=False)
def load_intraday(yf_ticker: str, days: int = 60, interval_minutes: int = 240):
    return MarketDataClient().get_intraday_history(
        yf_ticker, days=days, interval_minutes=interval_minutes
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_market_summary():
    return MarketDataClient().get_market_summary()


@st.cache_data(ttl=600, show_spinner=False)
def load_recommendations(market: str):
    return MarketDataClient().get_long_short_recommendations(market=market, top_n=12)


@st.cache_data(ttl=1800, show_spinner=False)
def load_ml_prediction(yf_ticker: str):
    """Train + predict a 20-day direction on ~4y daily history. Cached 30 min."""
    return ml_predict(MarketDataClient().get_stock_history(yf_ticker, days=1460))


@st.cache_data(ttl=600, show_spinner=False)
def load_peer_comparison(display_ticker: str, window_days: int = 180):
    return MarketDataClient().get_peer_comparison(display_ticker, window_days=window_days)


@st.cache_data(ttl=300, show_spinner=False)
def load_todays_moves(yf_tickers: tuple):
    """Return {yf_ticker: today's % change} from the last two daily closes."""
    data = load_batch_history(yf_tickers, days=5)
    out = {}
    for t, h in data.items():
        c = h["Close"].dropna()
        if len(c) >= 2 and c.iloc[-2] != 0:
            out[t] = (c.iloc[-1] - c.iloc[-2]) / c.iloc[-2] * 100
    return out


@st.cache_data(ttl=600, show_spinner=False)
def load_batch_history(tickers: tuple, days: int = 90):
    """Batch-download daily history for several tickers (compare grid)."""
    import yfinance as yf
    if not tickers:
        return {}
    raw = yf.download(
        " ".join(tickers), period=f"{days}d", auto_adjust=True,
        progress=False, group_by="ticker",
    )
    out = {}
    for t in tickers:
        try:
            if len(tickers) == 1:
                sub = raw
            elif t in raw.columns.get_level_values(0):
                sub = raw[t]
            else:
                continue
            sub = sub.dropna(subset=["Close"])
            if len(sub) > 1:
                out[t] = sub
        except Exception:
            continue
    return out


# ────────────────────────────────────────────────────────────
# News loaders
# ────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def load_market_news(category: str = "general"):
    return NewsClient().get_market_news(category=category)


@st.cache_data(ttl=600, show_spinner=False)
def load_industry_news(tickers: tuple):
    return NewsClient().get_industry_news(list(tickers))


@st.cache_data(ttl=600, show_spinner=False)
def load_company_news(symbol: str):
    return NewsClient().get_company_news(symbol)


def news_configured() -> bool:
    return NewsClient().configured


# ────────────────────────────────────────────────────────────
# Portfolio frame helper
# ────────────────────────────────────────────────────────────

def get_portfolio_frame():
    """
    Return (cash, positions, analyzer, df, summary) using cached loaders.
    Call from any page; it shares the same cached data.
    """
    cash = load_account()
    positions = load_positions()
    analyzer = PortfolioAnalyzer(positions, cash)
    summary = analyzer.get_portfolio_summary()
    return cash, positions, analyzer, analyzer.df, summary


def _quote_row(name: str, value_str: str, pct: float, change_str: str) -> None:
    """
    One quote line: grey name on the left, brighter right-aligned value,
    then a colored change line (arrow + amount + %). Shared by the indices
    and top-holdings sidebar boxes for a consistent format.
    """
    color = GREEN if pct >= 0 else RED
    arrow = "▲" if pct >= 0 else "▼"
    sign = "+" if pct >= 0 else ""
    st.markdown(
        f"<div style='font-size:12px;line-height:1.3;margin-bottom:6px'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
        f"<span style='color:#8b919c'>{name}</span>"
        f"<span style='color:#FFFFFF;font-weight:700;font-size:13px'>{value_str}</span>"
        f"</div>"
        f"<div style='color:{color};text-align:right'>{arrow} {change_str} "
        f"({sign}{pct:.2f}%)</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_sidebar_indices() -> None:
    """Indices box: level (bright, right-aligned) + point & % change."""
    indices = load_market_summary()
    if not indices:
        return
    st.sidebar.markdown("**Indices**")
    box = st.sidebar.container(border=True)
    with box:
        for idx in indices:
            chg, pct = idx.get("change", 0), idx["change_percent"]
            sign = "+" if chg >= 0 else ""
            _quote_row(idx["name"], f"{idx['price']:,.0f}", pct, f"{sign}{chg:,.0f}")


def render_sidebar_holdings() -> None:
    """Top-5 holdings (by value) box: position value + today's £ and % move."""
    _, _, _, df, _ = get_portfolio_frame()
    if df.empty or "value" not in df.columns:
        return

    top = df.nlargest(5, "value")
    yf_map = {r["ticker"]: t212_ticker_to_yf(r["t212_ticker"]) for _, r in top.iterrows()}
    moves = load_todays_moves(tuple(yf_map.values()))

    st.sidebar.markdown("**Top Holdings**")
    box = st.sidebar.container(border=True)
    with box:
        for _, r in top.iterrows():
            pct = moves.get(yf_map[r["ticker"]], 0.0)
            value = r["value"]
            amt = value * pct / 100.0  # approx GBP move today (ignores intraday FX)
            sign = "+" if amt >= 0 else ""
            _quote_row(r["ticker"], f"£{value:,.0f}", pct, f"{sign}£{amt:,.0f}")


# ────────────────────────────────────────────────────────────
# Shared chart builder
# ────────────────────────────────────────────────────────────

def intraday_labels(index) -> list:
    """Format an intraday datetime index into compact category labels."""
    return [t.strftime("%m-%d %H:%M") for t in index]


def build_candlestick(
    hist: pd.DataFrame,
    label: str,
    intraday: bool = False,
    show_ma: bool = True,
) -> go.Figure:
    """
    Build a candlestick figure with MA5/MA10 + EMA12/26 overlays.

    For intraday data we use a CATEGORICAL x-axis (one evenly-spaced slot per
    bar). This removes both the overnight/weekend gaps AND the candle overlap
    that a datetime axis + rangebreaks produces when the bar width (e.g. 4h)
    exceeds the collapsed visual spacing.
    """
    x = intraday_labels(hist.index) if intraday else hist.index

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=x, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"], name=label,
        increasing_line_color=GREEN, decreasing_line_color=RED,
    ))
    if show_ma:
        fig.add_trace(go.Scatter(x=x, y=sma(hist["Close"], 5),
                                 name="MA5", line=dict(color="orange", width=1)))
        fig.add_trace(go.Scatter(x=x, y=sma(hist["Close"], 10),
                                 name="MA10", line=dict(color="purple", width=1)))
        fig.add_trace(go.Scatter(x=x, y=ema(hist["Close"], 12),
                                 name="EMA12", line=dict(color="#00bcd4", width=1, dash="dot")))
        fig.add_trace(go.Scatter(x=x, y=ema(hist["Close"], 26),
                                 name="EMA26", line=dict(color="#e91e63", width=1, dash="dot")))

    if intraday:
        fig.update_xaxes(type="category", nticks=10, tickangle=0)

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h"),
        margin=dict(t=20, b=20),
    )
    return fig
