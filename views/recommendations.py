"""Long / Short Ideas — trending stocks scored for long/short with reasoning."""

import streamlit as st

from src.dashboard_common import load_recommendations


def render():
    st.title("Long / Short Ideas")

    market = st.selectbox(
        "Recommendation universe",
        options=["all", "tech", "us", "uk"],
        format_func=lambda x: {
            "all": "All watchlists", "tech": "US fast-tech",
            "us": "US large-cap", "uk": "UK top 20",
        }[x],
    )
    st.caption("Ranked by signal strength · MA5/MA10 · EMA · RSI · MACD · Bollinger · Stochastic · OBV · crossovers")

    with st.spinner("Scanning watchlist…"):
        recs = load_recommendations(market)

    if not recs:
        st.info("No strong signals right now. Try a different universe.")
        return

    longs = [r for r in recs if r["score"] > 0]
    shorts = [r for r in recs if r["score"] < 0]
    col_long, col_short = st.columns(2)

    def render_card(r):
        with st.container(border=True):
            st.markdown(f"**{r['ticker']}** — {r['name']}  \n"
                        f"`{r['recommendation']}`  ·  score **{r['score']:+d}**")
            a, b, c = st.columns(3)
            a.metric("Price", f"{r['price']:.2f}")
            b.metric("Day", f"{r['daily_change']:+.2f}%")
            c.metric("RSI", f"{r['rsi14']:.0f}")
            with st.expander("Reasoning"):
                for reason in r["reasons"]:
                    st.write(f"• {reason}")

    with col_long:
        st.markdown("### Long candidates")
        for r in longs:
            render_card(r)
    with col_short:
        st.markdown("### Short candidates")
        for r in shorts:
            render_card(r)
