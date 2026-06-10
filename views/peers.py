"""Peer Comparison — a holding vs its industry peers + sector ETF."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.market_data import find_peer_group
from src.dashboard_common import GREEN, RED, BLUE, GREY, get_portfolio_frame, load_peer_comparison


def render():
    st.title("Peer Comparison")
    st.caption("Rebased price chart + multi-window returns vs the sector ETF. Your stock highlighted.")

    _, _, _, df, _ = get_portfolio_frame()
    if df.empty:
        st.info("No holdings to compare.")
        return

    c1, c2 = st.columns([3, 2])
    with c1:
        selected = st.selectbox(
            "Select a holding", options=list(df["ticker"]),
            format_func=lambda t: f"{t} — {df[df['ticker']==t]['name'].values[0]}")
    with c2:
        window = st.radio("Rebased window", [90, 180, 365],
                          format_func=lambda d: {90: "3M", 180: "6M", 365: "1Y"}[d],
                          horizontal=True, index=1)

    group = find_peer_group(selected)
    if group is None:
        st.info(f"{selected} isn't mapped to a peer group yet.")
        return

    with st.spinner(f"Loading {group} peers…"):
        pc = load_peer_comparison(selected, window_days=window)
    if pc is None:
        st.warning("Could not load peer data.")
        return

    st.markdown(f"**Industry group:** {pc['group']}  ·  **Benchmark ETF:** {pc['etf']}")

    rebased = pc["rebased"]
    fig = go.Figure()
    for col in rebased.columns:
        is_self, is_etf = col == selected, col == pc["etf"]
        if is_self:
            width, color, dash = 3.5, BLUE, None
        elif is_etf:
            width, color, dash = 2.5, "#000000", "dash"
        else:
            width, color, dash = 1, GREY, None
        fig.add_trace(go.Scatter(x=rebased.index, y=rebased[col], name=col,
                                 line=dict(width=width, color=color, dash=dash),
                                 opacity=1.0 if (is_self or is_etf) else 0.5))
    fig.add_hline(y=100, line_dash="dot", line_color=GREY, opacity=0.4)
    fig.update_layout(height=460, yaxis_title="Rebased to 100", legend=dict(orientation="h"),
                      margin=dict(t=20, b=20),
                      title=f"{selected} (blue) vs peers vs {pc['etf']} (black dashed)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Returns by Window (ranked by 3-month)")
    tbl = pd.DataFrame(pc["returns_table"])
    disp = tbl[["ticker", "name", "ret_1m", "ret_3m", "ret_6m", "ret_1y"]].copy()
    disp.columns = ["Ticker", "Name", "1M", "3M", "6M", "1Y"]

    def _hl(rowx):
        # Translucent dark-theme-friendly highlights so light text stays legible
        rec = tbl.iloc[rowx.name]
        if rec["is_self"]:
            return ["background-color: rgba(41,182,246,0.28)"] * len(rowx)
        if rec["is_etf"]:
            return ["background-color: rgba(255,255,255,0.10); font-style: italic"] * len(rowx)
        return [""] * len(rowx)

    st.dataframe(
        disp.style
            .format({c: "{:+.1f}%" for c in ["1M", "3M", "6M", "1Y"]}, na_rep="—")
            .apply(_hl, axis=1)
            .map(lambda v: f"color: {GREEN}" if isinstance(v, (int, float)) and v > 0
                 else (f"color: {RED}" if isinstance(v, (int, float)) and v < 0 else ""),
                 subset=["1M", "3M", "6M", "1Y"]),
        use_container_width=True, hide_index=True)
    st.caption("Blue row = your stock · grey italic = sector ETF")
