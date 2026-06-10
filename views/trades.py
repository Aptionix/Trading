"""Trades & Charts — per-stock chart with your buy/sell points, TA, ML + holdings table."""

import pandas as pd
import streamlit as st

from src.market_data import t212_ticker_to_yf
from src.technical_analysis import analyze as ta_analyze
from src.dashboard_common import (
    GREEN, RED, BLUE, get_portfolio_frame, load_history, load_intraday,
    load_ticker_markers, load_ml_prediction, build_candlestick,
)
import plotly.graph_objects as go

_WINDOW_DAYS = {"3M": 90, "6M": 180, "1Y": 365, "2Y": 730}


def render():
    st.title("Trades & Charts")

    cash, _, analyzer, df, _ = get_portfolio_frame()
    if df.empty:
        st.info("No open positions yet.")
        return

    sel_col, tf_col = st.columns([3, 2])
    with sel_col:
        selected = st.selectbox(
            "Select a holding",
            options=list(df["ticker"]),
            format_func=lambda t: f"{t} — {df[df['ticker']==t]['name'].values[0]}",
        )
    with tf_col:
        timeframe = st.radio(
            "Timeframe", ["Daily", "4-hour (intraday)"], horizontal=True,
            help="4-hour candles resampled from hourly data, last 60 days, market hours only.",
        )

    row = df[df["ticker"] == selected].iloc[0]
    yf_ticker = t212_ticker_to_yf(row["t212_ticker"])
    intraday = timeframe != "Daily"

    # All buy/sell fills for this specific holding (fast, ticker-filtered)
    marks = load_ticker_markers(row["t212_ticker"])

    if intraday:
        hist = load_intraday(yf_ticker, 60, 240)
    else:
        # Daily: user picks how far back; "Max" auto-fits to the oldest trade
        window = st.radio(
            "Window", ["3M", "6M", "1Y", "2Y", "Max"], horizontal=True, index=0,
            help="How far back the daily chart (and trade markers) reach.",
        )
        if window == "Max" and marks:
            earliest = min(pd.to_datetime(m["date"]) for m in marks)
            days = (pd.Timestamp.now(tz=earliest.tz) - earliest).days + 10
        else:
            days = _WINDOW_DAYS.get(window, 90)
        hist = load_history(yf_ticker, days)

    if hist.empty:
        st.warning(f"No price history available for {yf_ticker}.")
    else:
        fig = build_candlestick(hist, selected, intraday=intraday)

        fig.add_hline(y=row["averagePrice"], line_dash="dash", line_color=BLUE,
                      annotation_text=f"Avg entry {row['averagePrice']:.2f}",
                      annotation_position="top left")

        def _naive_utc(ts):
            ts = pd.to_datetime(ts)
            return ts.tz_convert("UTC").tz_localize(None) if ts.tzinfo else ts

        def marker_x(date_str):
            """Map a trade datetime to the chart's x value.

            Daily chart uses a datetime axis; the intraday chart uses a
            categorical axis, so snap the trade to its nearest bar's label.
            """
            ts = pd.to_datetime(date_str)
            if not intraday:
                return ts.tz_localize(None) if ts.tzinfo else ts
            idx = hist.index
            if idx.tz is not None:
                ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
                ts = ts.tz_convert(idx.tz)
            elif ts.tzinfo is not None:
                ts = ts.tz_localize(None)
            pos = max(idx.get_indexer([ts], method="nearest")[0], 0)
            return idx[pos].strftime("%m-%d %H:%M")

        # Only show markers that fall inside the loaded chart window, otherwise
        # out-of-range markers stretch the axis and float without candles.
        lo, hi = _naive_utc(hist.index[0]), _naive_utc(hist.index[-1])
        visible = [m for m in marks if lo <= _naive_utc(m["date"]) <= hi]
        hidden = len(marks) - len(visible)

        buys = [m for m in visible if m["side"] == "BUY"]
        sells = [m for m in visible if m["side"] == "SELL"]
        if buys:
            fig.add_trace(go.Scatter(
                x=[marker_x(m["date"]) for m in buys],
                y=[m["price"] for m in buys], mode="markers", name="Your BUY",
                marker=dict(symbol="triangle-up", size=14, color=GREEN, line=dict(width=1, color="white")),
                text=[f"BUY {m['quantity']} @ {m['price']:.2f}" for m in buys], hoverinfo="text"))
        if sells:
            fig.add_trace(go.Scatter(
                x=[marker_x(m["date"]) for m in sells],
                y=[m["price"] for m in sells], mode="markers", name="Your SELL",
                marker=dict(symbol="triangle-down", size=14, color=RED, line=dict(width=1, color="white")),
                text=[f"SELL {m['quantity']} @ {m['price']:.2f}" for m in sells], hoverinfo="text"))

        fig.update_layout(height=500, yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)

        shown = len(buys) + len(sells)
        msg = f"Showing {shown} of {len(marks)} trades for {selected} in this window."
        if hidden and not intraday:
            msg += " Widen the window (or pick Max) to see earlier trades."
        st.caption(msg)

        # Technical read
        ta = ta_analyze(hist)
        if ta:
            st.markdown(f"#### Technical Indicators ({timeframe})")
            for fs in ta["fresh_signals"]:
                (st.success if "ABOVE" in fs else st.error)(f"Fresh signal: {fs}")
            c = st.columns(7)
            c[0].metric("Signal", ta["recommendation"])
            c[1].metric("RSI(14)", f"{ta['rsi14']:.0f}")
            c[2].metric("MACD hist", f"{ta['macd_hist']:+.2f}")
            c[3].metric("Stoch %K", f"{ta['stoch_k']:.0f}")
            c[4].metric("Bollinger %", f"{ta['bb_pos']:.0f}")
            c[5].metric("OBV trend", f"{ta['obv_trend']:+.0f}%")
            c[6].metric("Your P&L", f"{row['ppl']:+.2f}", f"{row['ppl_percent']:+.2f}%")
            with st.expander("Why this technical signal?"):
                for reason in ta["reasons"]:
                    st.write(f"• {reason}")

        # ML
        st.markdown("#### Machine Learning Prediction")
        with st.spinner("Training gradient-boosting model on ~4y daily history…"):
            ml = load_ml_prediction(yf_ticker)
        if ml is None:
            st.info("Not enough history to train a reliable model.")
        else:
            up = ml["direction"] == "UP"
            p = st.columns(4)
            p[0].metric(f"{ml['horizon_days']}-day Direction", "▲ UP" if up else "▼ DOWN")
            p[1].metric("Confidence (P up)", f"{ml['probability_up']:.0%}")
            p[2].metric("Backtest Accuracy", f"{ml['backtest_accuracy']:.0%}")
            p[3].metric("Training Samples", f"{ml['n_train']:,}")
            acc = ml["backtest_accuracy"]
            if acc >= 0.55:
                st.success(f"Model beat a coin flip on unseen data ({acc:.0%} over "
                           f"{ml['horizon_days']} days). One input among many — not a trigger.")
            else:
                st.warning(f"Out-of-sample accuracy {acc:.0%} — near chance. Little edge; be skeptical.")
            drivers = ", ".join(f"{n} ({i:.0%})" for n, i in ml["top_features"])
            st.caption(f"Predicting {ml['horizon_days']} trading days ahead · drivers: {drivers}")

    # ── Holdings table (moved here from Composition) ──
    st.divider()
    st.subheader("All Holdings")
    disp = df[["ticker", "name", "quantity", "averagePrice",
               "currentPrice", "value", "ppl", "ppl_percent"]].copy()
    disp.columns = ["Ticker", "Name", "Qty", "Avg Price", "Current", "Value", "P&L", "P&L %"]
    st.dataframe(
        disp.style.format({
            "Qty": "{:.4f}", "Avg Price": "{:.2f}", "Current": "{:.2f}",
            "Value": "{:,.2f}", "P&L": "{:+,.2f}", "P&L %": "{:+.2f}%",
        }).map(
            lambda v: f"color: {GREEN}" if isinstance(v, (int, float)) and v > 0
            else (f"color: {RED}" if isinstance(v, (int, float)) and v < 0 else ""),
            subset=["P&L", "P&L %"]),
        use_container_width=True, hide_index=True,
    )
