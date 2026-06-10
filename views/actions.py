"""Suggested Actions — portfolio signals + per-holding technical & ML action table."""

import pandas as pd
import streamlit as st

from src.market_data import t212_ticker_to_yf
from src.risk_analysis import RiskAnalyzer
from src.trading_signals import SignalGenerator
from src.technical_analysis import analyze as ta_analyze
from src.dashboard_common import get_portfolio_frame, load_history, load_ml_prediction


def render():
    st.title("Suggested Actions")

    cash, _, _, df, summary = get_portfolio_frame()
    if df.empty:
        st.info("No holdings to analyse.")
        return

    total_value = summary.get("total_value", 0)

    st.subheader("Portfolio-Level Signals")
    risk = RiskAnalyzer(df, cash.get("free", 0))
    conc, liq = risk.get_concentration_risk(), risk.get_liquidity_analysis()
    r = st.columns(3)
    r[0].metric("Concentration Risk", conc.get("risk_level", "—"))
    r[1].metric("Top Position Weight", f"{conc.get('top_position_weight', 0):.1f}%")
    r[2].metric("Cash Ratio", f"{liq.get('cash_ratio_percent', 0):.1f}%")

    signals = SignalGenerator(df, total_value).get_all_signals()

    def render_signals(title, items):
        st.markdown(f"**{title}**")
        if not items:
            st.success("Nothing flagged.")
            return
        for s in items:
            st.warning(f"**{s.get('ticker','—')}** → {s['action']}  \n{s.get('reason','')}")

    cols = st.columns(3)
    with cols[0]:
        render_signals("Rebalance", signals["rebalance"])
    with cols[1]:
        render_signals("Momentum", signals["momentum"])
    with cols[2]:
        render_signals("Risk Reduction", signals["risk_reduction"])

    st.divider()
    st.subheader("Per-Holding Technical + ML Action")
    st.caption("Technical: MA5/MA10 · EMA · RSI · MACD · Bollinger · Stochastic · OBV · crossovers. "
               "ML: gradient-boosting 20-day direction with out-of-sample accuracy.")

    rows = []
    with st.spinner("Analysing holdings (technical + ML)…"):
        for _, h in df.iterrows():
            yf_t = t212_ticker_to_yf(h["t212_ticker"])
            ta = ta_analyze(load_history(yf_t, days=120))
            ml = load_ml_prediction(yf_t)
            if ta:
                rows.append({
                    "Ticker": h["ticker"],
                    "Technical": ta["recommendation"],
                    "Score": ta["score"],
                    "RSI": ta["rsi14"],
                    "ML 20d": ml["direction"] if ml else "—",
                    "ML Conf": ml["probability_up"] if ml else float("nan"),
                    "ML Acc": ml["backtest_accuracy"] if ml else float("nan"),
                    "Your P&L %": h["ppl_percent"],
                })

    if rows:
        action_df = pd.DataFrame(rows).sort_values("Score", ascending=False)
        st.dataframe(
            action_df.style.format({
                "Score": "{:+d}", "RSI": "{:.0f}", "ML Conf": "{:.0%}",
                "ML Acc": "{:.0%}", "Your P&L %": "{:+.2f}%",
            }, na_rep="—"),
            use_container_width=True, hide_index=True)
