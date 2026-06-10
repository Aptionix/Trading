"""Compare Charts — multi-ticker grid of candlesticks or overlaid rebased lines."""

import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.market_data import (
    ALL_WATCHLIST, ticker_name, t212_ticker_to_yf,
)
from src.dashboard_common import GREEN, RED, BLUE, get_portfolio_frame, load_batch_history


def render():
    st.title("Compare Charts")
    st.caption("Compare any mix of your holdings, watchlist names, or custom symbols.")

    _, _, _, df, _ = get_portfolio_frame()
    holding_yf = {t212_ticker_to_yf(r["t212_ticker"]) for _, r in df.iterrows()} if not df.empty else set()

    # Build the option list: holdings first, then watchlist (deduped)
    options = list(dict.fromkeys(list(holding_yf) + ALL_WATCHLIST))

    c1, c2 = st.columns([3, 2])
    with c1:
        picked = st.multiselect(
            "Tickers (holdings + watchlist)",
            options=options,
            default=sorted(holding_yf)[:6] if holding_yf else options[:4],
            format_func=lambda t: f"{t} — {ticker_name(t)}",
        )
    with c2:
        free_text = st.text_input(
            "Add custom symbols (comma-separated)",
            placeholder="KO, BTC-USD, ^FTSE",
        )

    extra = [s.strip().upper() for s in free_text.split(",") if s.strip()]
    tickers = list(dict.fromkeys(picked + extra))

    if not tickers:
        st.info("Pick at least one ticker to compare.")
        return

    ctrl1, ctrl2 = st.columns([2, 2])
    with ctrl1:
        mode = st.radio("View", ["Grid of candlesticks", "Overlaid (rebased to 100)"],
                        horizontal=True)
    with ctrl2:
        window = st.radio("Window", [60, 90, 180, 365],
                          format_func=lambda d: {60: "2M", 90: "3M", 180: "6M", 365: "1Y"}[d],
                          horizontal=True, index=1)

    with st.spinner(f"Loading {len(tickers)} tickers…"):
        data = load_batch_history(tuple(tickers), days=window)

    missing = [t for t in tickers if t not in data]
    if missing:
        st.warning(f"No data for: {', '.join(missing)}")
    valid = [t for t in tickers if t in data]
    if not valid:
        st.error("None of the selected tickers returned data.")
        return

    if mode.startswith("Grid"):
        _render_grid(valid, data)
    else:
        _render_overlay(valid, data)


def _render_grid(tickers, data):
    n_cols = st.slider("Columns", min_value=2, max_value=6, value=4)
    n_rows = math.ceil(len(tickers) / n_cols)

    fig = make_subplots(
        rows=n_rows, cols=n_cols, subplot_titles=tickers,
        vertical_spacing=0.08, horizontal_spacing=0.04,
    )
    for i, t in enumerate(tickers):
        r, c = divmod(i, n_cols)
        h = data[t]
        # Categorical x (date labels) → even spacing, no weekend gaps, no overlap
        xlabels = [d.strftime("%m-%d") for d in h.index]
        fig.add_trace(go.Candlestick(
            x=xlabels, open=h["Open"], high=h["High"], low=h["Low"], close=h["Close"],
            increasing_line_color=GREEN, decreasing_line_color=RED, showlegend=False,
        ), row=r + 1, col=c + 1)

    fig.update_layout(height=max(260 * n_rows, 300), margin=dict(t=40, b=20))
    # Category axis + hidden tick labels keep the small grid cells clean
    fig.update_xaxes(type="category", rangeslider_visible=False, showticklabels=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_overlay(tickers, data):
    fig = go.Figure()
    for t in tickers:
        close = data[t]["Close"].dropna()
        if close.empty:
            continue
        rebased = close / close.iloc[0] * 100
        fig.add_trace(go.Scatter(x=rebased.index, y=rebased, name=t, mode="lines"))
    fig.add_hline(y=100, line_dash="dot", line_color="#aaa", opacity=0.5)
    fig.update_layout(
        height=560, yaxis_title="Rebased to 100",
        legend=dict(orientation="h"), margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("All series indexed to 100 at the start of the window.")
