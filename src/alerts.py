"""
Price Alerts Module

Functions for monitoring price movements and setting alerts.
"""

from typing import Dict, List, Any
from datetime import datetime


class PriceAlertManager:
    """Manager for price alerts and monitoring"""

    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []

    def create_alert(
        self,
        ticker: str,
        alert_type: str,
        threshold: float,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Create a new price alert.

        Args:
            ticker:      Stock ticker symbol.
            alert_type:  One of "price_above", "price_below", "profit_loss_percent".
                         - price_above: fires when currentPrice >= threshold
                         - price_below: fires when currentPrice <= threshold
                         - profit_loss_percent: fires when position ppl% >= threshold
                           (use a negative threshold to alert on losses)
            threshold:   Numeric trigger value.
            description: Human-readable label for the alert.

        Returns:
            The newly created alert dict.
        """
        valid_types = {"price_above", "price_below", "profit_loss_percent"}
        if alert_type not in valid_types:
            raise ValueError(f"alert_type must be one of {valid_types}")

        alert = {
            "id": len(self.alerts) + 1,
            "ticker": ticker,
            "type": alert_type,
            "threshold": threshold,
            "description": description,
            "created_at": datetime.now(),
            "triggered": False,
        }
        self.alerts.append(alert)
        return alert

    def check_alerts(
        self,
        current_prices: Dict[str, float],
        ppl_percents: Dict[str, float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Check if any alerts have been triggered.

        Args:
            current_prices: {ticker: current_price}
            ppl_percents:   {ticker: ppl_percent} — required for profit_loss_percent alerts.

        Returns:
            List of triggered alert dicts (each includes a "current_value" key).
        """
        if ppl_percents is None:
            ppl_percents = {}

        triggered = []

        for alert in self.alerts:
            if alert["triggered"]:
                continue

            ticker = alert["ticker"]
            alert_type = alert["type"]
            threshold = alert["threshold"]

            if alert_type in ("price_above", "price_below"):
                if ticker not in current_prices:
                    continue
                current_value = current_prices[ticker]
                fired = (
                    (alert_type == "price_above" and current_value >= threshold)
                    or (alert_type == "price_below" and current_value <= threshold)
                )

            elif alert_type == "profit_loss_percent":
                if ticker not in ppl_percents:
                    continue
                current_value = ppl_percents[ticker]
                # Positive threshold → alert when gains reach it.
                # Negative threshold → alert when losses reach it (value <= threshold).
                if threshold >= 0:
                    fired = current_value >= threshold
                else:
                    fired = current_value <= threshold

            else:
                continue

            if fired:
                alert["triggered"] = True
                triggered.append({**alert, "current_value": current_value})

        return triggered

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Return all alerts that have not yet been triggered."""
        return [a for a in self.alerts if not a["triggered"]]

    def reset_alert(self, alert_id: int) -> bool:
        """Re-arm a previously triggered alert."""
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["triggered"] = False
                return True
        return False
