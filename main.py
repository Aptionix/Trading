"""
Main entry point — daily reports and real-time portfolio monitoring.

Usage:
    python main.py

Two scheduled reports per day:
  - London open  (default 08:05) — portfolio overnight + UK market movers
  - US open      (default 14:35) — portfolio since London open + US/tech movers

Monitors every CHECK_INTERVAL_MINUTES for:
  - Portfolio value changes >= CHANGE_ALERT_THRESHOLD %
  - Any watchlist or portfolio stock moving >= STOCK_MOVE_THRESHOLD % in a day

Environment variables (all set in .env — see .env.example):
    TRADING212_API_KEY, TRADING212_DEMO
    EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT
    LONDON_OPEN_REPORT_TIME  (default 08:05)
    US_OPEN_REPORT_TIME      (default 14:35)
    CHECK_INTERVAL_MINUTES   (default 30)
    CHANGE_ALERT_THRESHOLD   (default 6.0  — portfolio % move alert)
    STOCK_MOVE_THRESHOLD     (default 6.0  — individual stock % move alert)
"""

import os
import time
from datetime import datetime, date
from typing import Dict, Set

import schedule
from dotenv import load_dotenv

from src.api_client import Trading212Client
from src.portfolio import PortfolioAnalyzer
from src.risk_analysis import RiskAnalyzer
from src.trading_signals import SignalGenerator
from src.alerts import PriceAlertManager
from src.email_reporter import EmailReporter
from src.market_data import MarketDataClient, t212_ticker_to_yf, ALL_WATCHLIST

load_dotenv()

# ------------------------------------------------------------------ #
# Configuration                                                        #
# ------------------------------------------------------------------ #

DEMO_MODE = os.getenv("TRADING212_DEMO", "true").lower() == "true"
LONDON_OPEN_REPORT_TIME = os.getenv("LONDON_OPEN_REPORT_TIME", "08:05")
US_OPEN_REPORT_TIME = os.getenv("US_OPEN_REPORT_TIME", "14:35")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
CHANGE_ALERT_THRESHOLD = float(os.getenv("CHANGE_ALERT_THRESHOLD", "6.0"))
STOCK_MOVE_THRESHOLD = float(os.getenv("STOCK_MOVE_THRESHOLD", "6.0"))

# ------------------------------------------------------------------ #
# State                                                                #
# ------------------------------------------------------------------ #

_prev_portfolio_value: float = None

# Tracks which (ticker, direction) pairs have already been alerted today
# so we don't spam on every 30-min check.  Cleared at midnight.
_auto_alerted_today: Set[tuple] = set()
_alert_date: date = None


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def _build_analyzer():
    client = Trading212Client(demo=DEMO_MODE)
    positions = client.get_portfolio()
    cash_data = client.get_account_cash()
    return PortfolioAnalyzer(positions, cash_data), cash_data, positions


def _reset_daily_state_if_new_day() -> None:
    """Clear the auto-alert dedup set each new calendar day."""
    global _auto_alerted_today, _alert_date
    today = date.today()
    if _alert_date != today:
        _auto_alerted_today = set()
        _alert_date = today


# ------------------------------------------------------------------ #
# Report builder                                                       #
# ------------------------------------------------------------------ #

def _compile_and_send_report(report_type: str) -> None:
    """
    Pull fresh data and send the report email.

    Args:
        report_type: "london_open" or "us_open" — controls which
                     trending stocks are included and the subject line.
    """
    label = "London Open" if report_type == "london_open" else "US Open"
    _log(f"Compiling {label} report...")

    try:
        analyzer, cash_data, _ = _build_analyzer()
        summary = analyzer.get_portfolio_summary()
        perf = analyzer.get_performance_metrics()
        top_holdings = analyzer.get_top_holdings(10)

        risk = RiskAnalyzer(analyzer.df, cash_data.get("free", 0))
        risk_metrics = {
            "concentration": risk.get_concentration_risk(),
            "diversification": risk.get_diversification_metrics(),
            "liquidity": risk.get_liquidity_analysis(),
        }

        signals = SignalGenerator(
            analyzer.df, summary.get("total_value", 0)
        ).get_all_signals()

        market = MarketDataClient()
        market_summary = market.get_market_summary()

        # Choose relevant movers for this report.
        if report_type == "london_open":
            trending = market.get_uk_movers(10)
        else:
            # US open: show US tech + large-cap combined top movers
            trending = market.get_trending_stocks(n=10, market="tech")

        reporter = EmailReporter()
        reporter.send_daily_report(
            portfolio_summary=summary,
            performance_metrics=perf,
            top_holdings=top_holdings,
            risk_metrics=risk_metrics,
            trending_stocks=trending,
            signals=signals,
            report_label=label,
            market_summary=market_summary,
        )
        _log(f"{label} report sent.")
    except Exception as e:
        _log(f"ERROR sending {label} report: {e}")


def send_london_open_report() -> None:
    _compile_and_send_report("london_open")


def send_us_open_report() -> None:
    _compile_and_send_report("us_open")


# ------------------------------------------------------------------ #
# Portfolio change monitor                                             #
# ------------------------------------------------------------------ #

def check_portfolio_change() -> None:
    """Detect dramatic portfolio value moves and email an alert."""
    global _prev_portfolio_value
    try:
        analyzer, _, _ = _build_analyzer()
        summary = analyzer.get_portfolio_summary()
        current = summary.get("total_value", 0)

        if _prev_portfolio_value and _prev_portfolio_value > 0:
            change_pct = (current - _prev_portfolio_value) / _prev_portfolio_value * 100
            if abs(change_pct) >= CHANGE_ALERT_THRESHOLD:
                _log(
                    f"Portfolio dramatic move: {change_pct:+.2f}% "
                    f"(${_prev_portfolio_value:,.2f} → ${current:,.2f})"
                )
                EmailReporter().send_portfolio_change_alert(
                    change_pct=change_pct,
                    prev_value=_prev_portfolio_value,
                    current_value=current,
                )

        _prev_portfolio_value = current
        _log(f"Portfolio check: ${current:,.2f}")
    except Exception as e:
        _log(f"ERROR checking portfolio change: {e}")


# ------------------------------------------------------------------ #
# Stock daily-move auto-alert                                          #
# ------------------------------------------------------------------ #

def check_stock_daily_moves() -> None:
    """
    Detect any stock in the portfolio or watchlist that has moved
    >= STOCK_MOVE_THRESHOLD % today and send a one-per-day alert.
    """
    _reset_daily_state_if_new_day()

    try:
        # Collect portfolio tickers and convert from T212 format.
        client = Trading212Client(demo=DEMO_MODE)
        positions = client.get_portfolio()
        portfolio_yf = [t212_ticker_to_yf(p["ticker"]) for p in positions if "ticker" in p]

        # Combine with the full watchlist (deduplicated).
        all_tickers = list(dict.fromkeys(portfolio_yf + ALL_WATCHLIST))

        market = MarketDataClient()
        big_movers = market.get_daily_movers(
            tickers=all_tickers,
            threshold=STOCK_MOVE_THRESHOLD,
        )

        new_alerts = []
        for stock in big_movers:
            key = (stock["ticker"], stock["direction"])
            if key not in _auto_alerted_today:
                _auto_alerted_today.add(key)
                new_alerts.append(stock)

        if new_alerts:
            reporter = EmailReporter()
            for stock in new_alerts:
                reporter.send_price_alert([{
                    "ticker": stock["ticker"],
                    "type": "daily_move",
                    "threshold": STOCK_MOVE_THRESHOLD,
                    "current_value": stock["price"],
                    "description": (
                        f"{stock['ticker']} ({stock['name']}) moved "
                        f"{stock['change_percent']:+.2f}% today."
                    ),
                }])
                _log(
                    f"Auto-alert: {stock['ticker']} {stock['direction']} "
                    f"{stock['change_percent']:+.2f}%"
                )
    except Exception as e:
        _log(f"ERROR in stock daily-move check: {e}")


# ------------------------------------------------------------------ #
# Manual price alerts                                                  #
# ------------------------------------------------------------------ #

def check_price_alerts(alert_manager: PriceAlertManager) -> None:
    """Evaluate manually configured price / ppl alerts."""
    try:
        client = Trading212Client(demo=DEMO_MODE)
        positions = client.get_portfolio()
        if not positions:
            return

        current_prices: Dict[str, float] = {}
        ppl_percents: Dict[str, float] = {}

        for p in positions:
            ticker = p.get("ticker", "")
            qty = p.get("quantity", 0)
            avg = p.get("averagePrice", 0)
            ppl = p.get("ppl", 0)
            price = p.get("currentPrice")
            if price:
                current_prices[ticker] = price
            if qty and avg:
                ppl_percents[ticker] = ppl / (qty * avg) * 100

        triggered = alert_manager.check_alerts(current_prices, ppl_percents)
        if triggered:
            EmailReporter().send_price_alert(triggered)
            for a in triggered:
                _log(f"Price alert fired: {a['ticker']} ({a['type']})")
    except Exception as e:
        _log(f"ERROR checking price alerts: {e}")


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main() -> None:
    _log("Starting Trading 212 monitor")
    _log(f"  Mode              : {'DEMO' if DEMO_MODE else 'LIVE'}")
    _log(f"  London open report: {LONDON_OPEN_REPORT_TIME}")
    _log(f"  US open report    : {US_OPEN_REPORT_TIME}")
    _log(f"  Check interval    : every {CHECK_INTERVAL_MINUTES} min")
    _log(f"  Portfolio alert   : {CHANGE_ALERT_THRESHOLD}% move")
    _log(f"  Stock auto-alert  : {STOCK_MOVE_THRESHOLD}% daily move")

    # ---- Manual alerts (add your own below) ----
    alert_manager = PriceAlertManager()
    # alert_manager.create_alert("NVDA", "price_above", 1500, "NVDA breakout")
    # alert_manager.create_alert("TSLA", "price_below", 150, "TSLA stop-loss")
    # alert_manager.create_alert("AAPL", "profit_loss_percent", 20, "AAPL +20% from avg")

    # ---- Scheduled jobs ----
    schedule.every().day.at(LONDON_OPEN_REPORT_TIME).do(send_london_open_report)
    schedule.every().day.at(US_OPEN_REPORT_TIME).do(send_us_open_report)
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_portfolio_change)
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_stock_daily_moves)
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(
        check_price_alerts, alert_manager=alert_manager
    )

    # Run an immediate portfolio check on startup to set the baseline value.
    check_portfolio_change()

    _log("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
