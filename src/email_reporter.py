"""
Email Reporter Module

Sends daily portfolio reports and real-time alert emails via Gmail SMTP.

Required .env variables:
    EMAIL_SENDER      Gmail address used to send (e.g. you@gmail.com)
    EMAIL_PASSWORD    Gmail App Password (not your login password)
    EMAIL_RECIPIENT   Destination address for reports and alerts
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, Any, List, Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class EmailReporter:
    """Sends HTML portfolio reports and alert emails via Gmail."""

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465

    def __init__(
        self,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
        recipient_email: Optional[str] = None,
    ):
        self.sender_email = sender_email or os.getenv("EMAIL_SENDER")
        self.sender_password = sender_password or os.getenv("EMAIL_PASSWORD")
        self.recipient_email = recipient_email or os.getenv("EMAIL_RECIPIENT")

        missing = [
            k for k, v in {
                "EMAIL_SENDER": self.sender_email,
                "EMAIL_PASSWORD": self.sender_password,
                "EMAIL_RECIPIENT": self.recipient_email,
            }.items() if not v
        ]
        if missing:
            raise ValueError(
                f"Missing email config — set these in your .env: {', '.join(missing)}"
            )

    # ------------------------------------------------------------------ #
    # Public send methods                                                  #
    # ------------------------------------------------------------------ #

    def send_daily_report(
        self,
        portfolio_summary: Dict[str, Any],
        performance_metrics: Dict[str, Any],
        top_holdings: pd.DataFrame,
        risk_metrics: Dict[str, Any],
        trending_stocks: List[Dict[str, Any]],
        signals: Dict[str, List],
        report_label: str = "Daily Report",
        market_summary: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        subject = (
            f"Portfolio {report_label} — "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        html = self._build_daily_report(
            portfolio_summary, performance_metrics,
            top_holdings, risk_metrics, trending_stocks, signals,
            report_label=report_label,
            market_summary=market_summary or [],
        )
        self._send(subject, html)

    def send_portfolio_change_alert(
        self,
        change_pct: float,
        prev_value: float,
        current_value: float,
    ) -> None:
        direction = "gained" if change_pct > 0 else "lost"
        sign = "+" if change_pct > 0 else ""
        subject = (
            f"ALERT: Portfolio {direction.upper()} "
            f"{sign}{change_pct:.1f}% — "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        html = self._build_alert(
            title=f"Portfolio {direction} {abs(change_pct):.2f}%",
            rows=[
                ("Previous value", f"${prev_value:,.2f}"),
                ("Current value", f"${current_value:,.2f}"),
                ("Change", f"{sign}${current_value - prev_value:,.2f}"),
                ("Change %", f"{sign}{change_pct:.2f}%"),
            ],
        )
        self._send(subject, html)

    def send_price_alert(self, triggered_alerts: List[Dict[str, Any]]) -> None:
        if not triggered_alerts:
            return
        for alert in triggered_alerts:
            subject = (
                f"ALERT: {alert['ticker']} — {alert['type'].replace('_', ' ').title()} "
                f"@ {alert['current_value']:,.4f}"
            )
            html = self._build_alert(
                title=f"Price alert triggered: {alert['ticker']}",
                rows=[
                    ("Ticker", alert["ticker"]),
                    ("Alert type", alert["type"]),
                    ("Threshold", str(alert["threshold"])),
                    ("Current value", str(alert["current_value"])),
                    ("Description", alert.get("description", "—")),
                ],
            )
            self._send(subject, html)

    # ------------------------------------------------------------------ #
    # HTML builders                                                        #
    # ------------------------------------------------------------------ #

    def _build_daily_report(
        self,
        summary: Dict[str, Any],
        perf: Dict[str, Any],
        top_holdings: pd.DataFrame,
        risk: Dict[str, Any],
        trending: List[Dict[str, Any]],
        signals: Dict[str, List],
        report_label: str = "Daily Report",
        market_summary: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        ppl = summary.get("total_profit_loss", 0)
        ppl_pct = summary.get("profit_loss_percent", 0)
        ppl_color = "#27ae60" if ppl >= 0 else "#e74c3c"
        sign = "+" if ppl >= 0 else ""

        html = f"""
<html>
<body style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;padding:20px;color:#2c3e50;">

<h1 style="border-bottom:3px solid #3498db;padding-bottom:10px;">
    {report_label} &mdash; {datetime.now().strftime('%B %d, %Y %H:%M')}
</h1>
"""

        # Market indices snapshot
        if market_summary:
            html += "<h2>Market Overview</h2>"
            idx_rows = []
            for idx in market_summary:
                chg = idx.get("change_percent", 0)
                cc = "#27ae60" if chg >= 0 else "#e74c3c"
                cs = "+" if chg >= 0 else ""
                idx_rows.append((
                    idx["name"],
                    f'{idx["price"]:,.2f} '
                    f'<span style="color:{cc};">({cs}{chg:.2f}%)</span>',
                ))
            html += self._table(idx_rows)

        html += f"""
<h2>Portfolio Summary</h2>
{self._table([
    ("Total Invested Value", f"${summary.get('total_value', 0):,.2f}"),
    ("Total P&L", f'<span style="color:{ppl_color};">{sign}${ppl:,.2f} ({sign}{ppl_pct:.2f}%)</span>'),
    ("Cash Balance", f"${summary.get('cash_balance', 0):,.2f}"),
    ("Total Assets", f"${summary.get('total_assets', 0):,.2f}"),
    ("Open Positions", str(summary.get("number_of_positions", 0))),
])}
"""

        # Performance
        if perf:
            html += f"""
<h2>Performance</h2>
{self._table([
    ("Average Return", f"{perf.get('average_return_percent', 0):.2f}%"),
    ("Volatility (std)", f"{perf.get('volatility', 0):.2f}%"),
    ("Best Performer", perf.get("best_performer", "—")),
    ("Worst Performer", perf.get("worst_performer", "—")),
    ("Positions in Profit", str(perf.get("positions_in_profit", 0))),
    ("Positions in Loss", str(perf.get("positions_in_loss", 0))),
])}
"""

        # Top holdings table
        if top_holdings is not None and not top_holdings.empty:
            html += "<h2>Top Holdings</h2>"
            html += (
                '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;">'
                '<tr style="background:#3498db;color:white;">'
                + "".join(
                    f'<th style="padding:8px;border:1px solid #ccc;">{h}</th>'
                    for h in ["Ticker", "Qty", "Value", "P&L", "Return %"]
                )
                + "</tr>"
            )
            for i, (_, row) in enumerate(top_holdings.iterrows()):
                bg = "#f8f9fa" if i % 2 == 0 else "white"
                rpl = row.get("ppl", 0)
                rpl_pct = row.get("ppl_percent", 0)
                rc = "#27ae60" if rpl >= 0 else "#e74c3c"
                rs = "+" if rpl >= 0 else ""
                html += (
                    f'<tr style="background:{bg};">'
                    f'<td style="padding:8px;border:1px solid #ccc;"><b>{row["ticker"]}</b></td>'
                    f'<td style="padding:8px;border:1px solid #ccc;">{row["quantity"]:.4f}</td>'
                    f'<td style="padding:8px;border:1px solid #ccc;">${row["value"]:,.2f}</td>'
                    f'<td style="padding:8px;border:1px solid #ccc;color:{rc};">{rs}${rpl:,.2f}</td>'
                    f'<td style="padding:8px;border:1px solid #ccc;color:{rc};">{rs}{rpl_pct:.2f}%</td>'
                    "</tr>"
                )
            html += "</table>"

        # Risk
        conc = risk.get("concentration", {})
        liq = risk.get("liquidity", {})
        if conc or liq:
            html += f"""
<h2>Risk Snapshot</h2>
{self._table([
    ("Concentration Risk", conc.get("risk_level", "—")),
    ("Top Position Weight", f"{conc.get('top_position_weight', 0):.1f}%"),
    ("Top 3 Positions", f"{conc.get('top_3_weight', 0):.1f}%"),
    ("Cash Ratio", f"{liq.get('cash_ratio_percent', 0):.1f}%"),
    ("Liquidity Level", liq.get("liquidity_level", "—")),
])}
"""

        # Trading signals
        all_signal_items = (
            signals.get("rebalance", [])
            + signals.get("momentum", [])
            + signals.get("risk_reduction", [])
        )
        if all_signal_items:
            html += "<h2>Trading Signals</h2><ul>"
            for s in all_signal_items:
                ticker = s.get("ticker", s.get("asset_class", "?"))
                html += f"<li><b>{s['signal_type']}</b> — {ticker}: {s['action']}</li>"
            html += "</ul>"

        # Trending stocks
        if trending:
            html += "<h2>Trending Stocks Today</h2>"
            html += (
                '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;">'
                '<tr style="background:#2c3e50;color:white;">'
                + "".join(
                    f'<th style="padding:8px;border:1px solid #ccc;">{h}</th>'
                    for h in ["Ticker", "Name", "Price", "Change %", "Volume"]
                )
                + "</tr>"
            )
            for i, s in enumerate(trending[:10]):
                bg = "#f8f9fa" if i % 2 == 0 else "white"
                chg = s.get("change_percent", 0)
                cc = "#27ae60" if chg >= 0 else "#e74c3c"
                cs = "+" if chg >= 0 else ""
                vol = s.get("volume", 0)
                vol_str = f"{vol/1_000_000:.1f}M" if vol >= 1_000_000 else f"{vol:,}"
                html += (
                    f'<tr style="background:{bg};">'
                    f'<td style="padding:8px;border:1px solid #ccc;"><b>{s.get("ticker","")}</b></td>'
                    f'<td style="padding:8px;border:1px solid #ccc;">{s.get("name","")}</td>'
                    f'<td style="padding:8px;border:1px solid #ccc;">${s.get("price",0):,.2f}</td>'
                    f'<td style="padding:8px;border:1px solid #ccc;color:{cc};">{cs}{chg:.2f}%</td>'
                    f'<td style="padding:8px;border:1px solid #ccc;">{vol_str}</td>'
                    "</tr>"
                )
            html += "</table>"

        html += f"""
<p style="color:#95a5a6;font-size:11px;margin-top:30px;border-top:1px solid #ecf0f1;padding-top:10px;">
    This report is for informational purposes only and does not constitute financial advice.<br>
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</p>
</body>
</html>"""
        return html

    def _build_alert(self, title: str, rows: List[tuple]) -> str:
        return f"""
<html>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<div style="background:#e74c3c;color:white;padding:20px;border-radius:8px;margin-bottom:20px;">
    <h1 style="margin:0;font-size:22px;">PORTFOLIO ALERT</h1>
    <h2 style="margin:8px 0 0 0;font-size:18px;">{title}</h2>
</div>
{self._table(rows)}
<p style="color:#95a5a6;font-size:11px;margin-top:20px;">
    Alert triggered {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</p>
</body>
</html>"""

    @staticmethod
    def _table(rows: List[tuple]) -> str:
        html = '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;">'
        for i, (label, value) in enumerate(rows):
            bg = "#f8f9fa" if i % 2 == 0 else "white"
            html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:10px;border:1px solid #dee2e6;"><strong>{label}</strong></td>'
                f'<td style="padding:10px;border:1px solid #dee2e6;">{value}</td>'
                "</tr>"
            )
        html += "</table>"
        return html

    # ------------------------------------------------------------------ #
    # SMTP                                                                 #
    # ------------------------------------------------------------------ #

    def _send(self, subject: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = self.recipient_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT) as server:
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, self.recipient_email, msg.as_string())
