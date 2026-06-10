"""Home — single-screen overview: summary, indices, news, actions, recommendations."""

import plotly.express as px
import streamlit as st

from src.market_data import PEER_GROUPS
from src.trading_signals import SignalGenerator
from src.dashboard_common import (
    GREEN, RED, currency_symbol, get_portfolio_frame,
    load_recommendations, load_market_news, load_industry_news, news_configured,
)
from views.news import render_news_items


def render():
    cash, _, analyzer, df, summary = get_portfolio_frame()
    sym = currency_symbol(cash.get("currency", "GBP"))

    st.markdown("### Portfolio Overview")

    # ── Row 1: portfolio metrics (indices now live in the sidebar) ──
    total_value = summary.get("total_value", 0)
    total_ppl = summary.get("total_profit_loss", 0)
    ppl_pct = summary.get("profit_loss_percent", 0)
    m = st.columns(7)
    m[0].metric("Invested", f"{sym}{total_value:,.0f}")
    m[1].metric("Unreal. P&L", f"{sym}{total_ppl:,.0f}", f"{ppl_pct:+.2f}%")
    m[2].metric("Cash", f"{sym}{cash.get('free', 0):,.0f}")
    m[3].metric("Total Assets", f"{sym}{summary.get('total_assets', 0):,.0f}")
    m[4].metric("Positions", summary.get("number_of_positions", 0))

    # Best & worst P&L movers, each with their %
    if not df.empty and "ppl_percent" in df.columns:
        top = df.nlargest(1, "ppl_percent").iloc[0]
        bot = df.nsmallest(1, "ppl_percent").iloc[0]
        m[5].metric("Top Gainer", top["ticker"], f"{top['ppl_percent']:+.2f}%")
        m[6].metric("Top Loser", bot["ticker"], f"{bot['ppl_percent']:+.2f}%")
    else:
        m[5].metric("Top Gainer", "—")
        m[6].metric("Top Loser", "—")

    st.divider()

    # ── Main grid: heatmap | news | actions+recs ──
    col_comp, col_news, col_side = st.columns([1.1, 1.4, 1.1])

    # Allocation heatmap (treemap: size = weight, color = P&L%)
    with col_comp:
        st.markdown("**Allocation Heatmap** · size = weight, color = P&L%")
        if df.empty:
            st.caption("No positions.")
        else:
            tdf = df.copy()
            tdf["label"] = tdf.apply(
                lambda r: f"{r['ticker']}<br>{r['ppl_percent']:+.1f}%", axis=1)
            tree = px.treemap(
                tdf, path=[px.Constant("Portfolio"), "label"], values="value",
                color="ppl_percent", color_continuous_scale=["#FF5252", "#2b2f36", "#00E5A0"],
                color_continuous_midpoint=0,
            )
            tree.update_traces(textinfo="label", textfont_size=13,
                               marker=dict(line=dict(color="#0E1117", width=1)))
            tree.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0),
                               coloraxis_showscale=False)
            st.plotly_chart(tree, use_container_width=True)

    # News panel (industry switch)
    with col_news:
        st.markdown("**Market News**")
        if not news_configured():
            st.caption("Add FINNHUB_API_KEY to .env to enable news.")
        else:
            options = ["Overall"] + list(PEER_GROUPS.keys())
            pick = st.selectbox("Scope", options, label_visibility="collapsed")
            if pick == "Overall":
                items = load_market_news("general")
            else:
                items = load_industry_news(tuple(PEER_GROUPS[pick]["members"]))
            render_news_items(items, height=300, compact=True)

    # Actions + recommendations
    with col_side:
        st.markdown("**Suggested Actions**")
        actions_box = st.container(height=140)
        with actions_box:
            signals = SignalGenerator(df, total_value).get_all_signals()
            flagged = signals["rebalance"] + signals["momentum"] + signals["risk_reduction"]
            if not flagged:
                st.caption("Portfolio balanced — nothing flagged.")
            else:
                for s in flagged[:8]:
                    st.markdown(f"• **{s.get('ticker','—')}** → {s['action']}")

        st.markdown("**Buy / Sell Ideas**")
        recs_box = st.container(height=150)
        with recs_box:
            recs = load_recommendations("all")
            longs = [r for r in recs if r["score"] > 0][:3]
            shorts = [r for r in recs if r["score"] < 0][:3]
            for r in longs:
                st.markdown(
                    f"<span style='color:{GREEN}'>▲ LONG</span> **{r['ticker']}** "
                    f"({r['score']:+d})", unsafe_allow_html=True)
            for r in shorts:
                st.markdown(
                    f"<span style='color:{RED}'>▼ SHORT</span> **{r['ticker']}** "
                    f"({r['score']:+d})", unsafe_allow_html=True)

