"""
Portfolio Analysis Module

Functions for analyzing portfolio composition and performance.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any


class PortfolioAnalyzer:
    """Analyzer for portfolio data"""

    def __init__(self, positions: List[Dict[str, Any]], cash_data: Dict[str, Any]):
        """
        Initialize portfolio analyzer.

        Args:
            positions:  List of position dicts from Trading212Client.get_portfolio().
                        Each dict contains: ticker, quantity, averagePrice,
                        currentPrice, ppl, and other fields.
            cash_data:  Cash balance dict from Trading212Client.get_account_cash().
                        Keys include: free, invested, ppl, total, blocked, pieCash.
        """
        self.positions = positions
        self.cash_data = cash_data
        self.df = self._create_dataframe()

    def _create_dataframe(self) -> pd.DataFrame:
        """
        Flatten the nested T212 position objects into a flat DataFrame.

        T212 position shape:
          instrument.ticker / instrument.name / instrument.currency
          quantity / averagePricePaid / currentPrice
          walletImpact.currentValue / walletImpact.unrealizedProfitLoss /
          walletImpact.totalCost
        """
        if not self.positions:
            return pd.DataFrame()

        rows = []
        for p in self.positions:
            inst   = p.get("instrument", {})
            wallet = p.get("walletImpact", {})
            cost   = wallet.get("totalCost", 0) or 0

            ppl      = wallet.get("unrealizedProfitLoss", 0) or 0
            ppl_pct  = (ppl / cost * 100) if cost else 0

            # Strip exchange suffix for display: "NVDA_US_EQ" → "NVDA"
            full_ticker = inst.get("ticker", "")
            ticker      = full_ticker.split("_")[0]

            rows.append({
                "ticker":        ticker,
                "t212_ticker":   full_ticker,
                "name":          inst.get("name", ticker),
                "quantity":      p.get("quantity", 0),
                "averagePrice":  p.get("averagePricePaid", 0),
                "currentPrice":  p.get("currentPrice", 0),
                "value":         wallet.get("currentValue", 0) or 0,
                "ppl":           ppl,
                "ppl_percent":   ppl_pct,
                "currency":      inst.get("currency", ""),
            })

        return pd.DataFrame(rows)

    def get_top_holdings(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N holdings by market value.

        Args:
            n: Number of top holdings to return.

        Returns:
            DataFrame with top holdings sorted by value descending.
        """
        if self.df.empty:
            return pd.DataFrame()

        cols = [c for c in ["ticker", "quantity", "value", "ppl", "ppl_percent"] if c in self.df.columns]
        return self.df.nlargest(n, "value")[cols]

    def get_asset_allocation(self) -> Optional[pd.Series]:
        """
        Get allocation percentages by ticker (T212 API does not provide sector data).

        Returns:
            Series indexed by ticker with percentage weights, or None if empty.
        """
        if self.df.empty or "value" not in self.df.columns:
            return None

        total_value = self.df["value"].sum()
        if total_value == 0:
            return None

        allocation = self.df.set_index("ticker")["value"] / total_value * 100
        return allocation.sort_values(ascending=False)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the portfolio."""
        if self.df.empty:
            return {"message": "No positions"}

        total_value = self.df["value"].sum() if "value" in self.df.columns else 0
        total_ppl = self.df["ppl"].sum() if "ppl" in self.df.columns else 0
        cost_basis = total_value - total_ppl
        ppl_percent = (total_ppl / cost_basis * 100) if cost_basis > 0 else 0

        return {
            "total_value": total_value,
            "total_profit_loss": total_ppl,
            "profit_loss_percent": ppl_percent,
            "number_of_positions": len(self.df),
            "cash_balance": self.cash_data.get("free", 0),
            "total_assets": total_value + self.cash_data.get("free", 0),
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate per-position performance metrics."""
        if self.df.empty or "ppl_percent" not in self.df.columns:
            return {}

        return {
            "average_return_percent": float(self.df["ppl_percent"].mean()),
            "volatility": float(self.df["ppl_percent"].std()),
            "best_performer": self.df.nlargest(1, "ppl_percent")["ticker"].values[0],
            "worst_performer": self.df.nsmallest(1, "ppl_percent")["ticker"].values[0],
            "positions_in_profit": int((self.df["ppl"] > 0).sum()),
            "positions_in_loss": int((self.df["ppl"] < 0).sum()),
        }
