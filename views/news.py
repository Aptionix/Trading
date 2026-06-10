"""News page — market + industry + per-holding financial news (Finnhub)."""

from typing import List, Dict, Any

import streamlit as st

from src.market_data import PEER_GROUPS, ticker_name
from src.dashboard_common import (
    get_portfolio_frame, news_configured,
    load_market_news, load_industry_news, load_company_news,
)


def render_news_items(items: List[Dict[str, Any]], height: int = 360, compact: bool = False) -> None:
    """Render a scrollable list of news articles inside a fixed-height box."""
    if not items:
        st.caption("No recent headlines.")
        return
    box = st.container(height=height)
    with box:
        for art in items:
            headline = art["headline"]
            url = art["url"]
            meta = f"{art['source']} · {art['time_str']}"
            if art.get("symbol"):
                meta = f"{art['symbol']} · " + meta
            if compact:
                st.markdown(f"[{headline}]({url})  \n<span style='color:#888;font-size:11px'>{meta}</span>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"**[{headline}]({url})**  \n<span style='color:#888;font-size:12px'>{meta}</span>",
                            unsafe_allow_html=True)
                if art.get("summary"):
                    st.caption(art["summary"][:220] + ("…" if len(art["summary"]) > 220 else ""))
            st.divider()


def render():
    st.title("Market News")

    if not news_configured():
        st.warning(
            "**Finnhub API key not found.** Sign up free at https://finnhub.io, "
            "then add `FINNHUB_API_KEY=your_key` to your `.env` file and refresh."
        )
        st.stop()

    _, _, _, df, _ = get_portfolio_frame()

    # Tabs: Overall + each peer group + per-holding
    group_names = list(PEER_GROUPS.keys())
    tab_labels = ["Overall"] + group_names + ["My Holdings"]
    tabs = st.tabs(tab_labels)

    # Overall market
    with tabs[0]:
        st.caption("Latest general market headlines")
        render_news_items(load_market_news("general"), height=600)

    # Industry tabs
    for i, group in enumerate(group_names, start=1):
        with tabs[i]:
            members = PEER_GROUPS[group]["members"]
            st.caption(f"Aggregated from: {', '.join(members[:8])}…")
            render_news_items(load_industry_news(tuple(members)), height=600)

    # Per-holding
    with tabs[-1]:
        if df.empty:
            st.info("No holdings to show news for.")
        else:
            holding = st.selectbox(
                "Pick a holding",
                options=list(df["ticker"]),
                format_func=lambda t: f"{t} — {ticker_name(t)}",
            )
            render_news_items(load_company_news(holding), height=560)
