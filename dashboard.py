"""
Trading 212 Visual Dashboard — multi-page app
=============================================

Sidebar navigation across:
    Home              one-screen overview (summary, indices, news, actions, ideas)
    Trades & Charts   per-stock candlestick + your buy/sell points + TA + ML + holdings
    Compare Charts    multi-ticker grid / overlaid comparison (holdings, watchlist, custom)
    Peer Comparison   a holding vs its industry peers + sector ETF
    News              market + industry + per-holding headlines (Finnhub)
    Suggested Actions portfolio signals + per-holding technical & ML actions
    Long / Short      trending long/short ideas

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
from dotenv import load_dotenv

from views import home, trades, compare, peers, news, actions, recommendations
from src.dashboard_common import render_sidebar_indices, render_sidebar_holdings, DEMO

load_dotenv()

st.set_page_config(
    page_title="Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation (rendered manually so account + refresh sit above it) ──
pages = [
    st.Page(home.render,            title="Home",              url_path="home", default=True),
    st.Page(trades.render,          title="Trades & Charts",   url_path="trades"),
    st.Page(compare.render,         title="Compare Charts",    url_path="compare"),
    st.Page(peers.render,           title="Peer Comparison",   url_path="peers"),
    st.Page(news.render,            title="News",              url_path="news"),
    st.Page(actions.render,         title="Suggested Actions", url_path="actions"),
    st.Page(recommendations.render, title="Long / Short Ideas", url_path="ideas"),
]
pg = st.navigation(pages, position="hidden")

account_label = "Practice" if DEMO else "Live"
with st.sidebar:
    # Compact account label + refresh pinned to the top-left corner
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    c1.caption(f"{account_label} account")
    if c2.button("↻", help="Refresh data"):
        st.cache_data.clear()
        st.rerun()
    st.divider()

    for p in pages:
        st.page_link(p)
    st.divider()

    # Fill the lower sidebar space with live boxes
    render_sidebar_holdings()
    render_sidebar_indices()

pg.run()
