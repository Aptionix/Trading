"""
Trading Signals Module

Functions for generating trading signals based on portfolio analysis.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional


class SignalGenerator:
    """Generate trading signals based on portfolio analysis"""

    def __init__(self, portfolio_df: pd.DataFrame, portfolio_value: float):
        """
        Initialize signal generator.

        Args:
            portfolio_df:    DataFrame with portfolio positions (must include
                             'ticker', 'value', and optionally 'ppl_percent').
            portfolio_value: Total invested market value (excluding cash).
        """
        self.portfolio_df = portfolio_df
        self.portfolio_value = portfolio_value

    def get_rebalance_signals(
        self, target_allocation: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate rebalancing signals against a target allocation.

        Args:
            target_allocation: {ticker: target_weight_as_fraction}
                               e.g. {"AAPL": 0.10, "MSFT": 0.10}
                               Omit to get signals purely from equal-weight deviation.

        Returns:
            List of rebalancing signal dicts.
        """
        if self.portfolio_df.empty or "value" not in self.portfolio_df.columns:
            return []

        total_value = self.portfolio_df["value"].sum()
        if total_value == 0:
            return []

        # Compute actual weights from the live portfolio.
        weights = (
            self.portfolio_df.set_index("ticker")["value"] / total_value
        )

        signals = []

        if target_allocation:
            for ticker, target_weight in target_allocation.items():
                current_weight = float(weights.get(ticker, 0.0))
                deviation = current_weight - target_weight
                if abs(deviation) > 0.05:  # 5 pp threshold
                    action = "REDUCE" if deviation > 0 else "INCREASE"
                    signals.append({
                        "signal_type": "REBALANCE",
                        "ticker": ticker,
                        "action": action,
                        "target_weight": target_weight,
                        "current_weight": current_weight,
                        "deviation": round(abs(deviation), 4),
                    })
        else:
            # Flag any single position that exceeds 25 % of the portfolio.
            for ticker, weight in weights.items():
                if weight > 0.25:
                    signals.append({
                        "signal_type": "REBALANCE",
                        "ticker": ticker,
                        "action": "REDUCE",
                        "target_weight": 0.25,
                        "current_weight": round(float(weight), 4),
                        "deviation": round(float(weight) - 0.25, 4),
                    })

        return signals

    def get_momentum_signals(self) -> List[Dict[str, Any]]:
        """
        Generate momentum signals from current P&L percentages.

        Returns:
            List of momentum signal dicts for positions with >5 % gain.
        """
        signals = []

        if "ppl_percent" not in self.portfolio_df.columns:
            return signals

        top_gainers = self.portfolio_df.nlargest(3, "ppl_percent")
        for _, position in top_gainers.iterrows():
            if position["ppl_percent"] > 5:
                signals.append({
                    "signal_type": "MOMENTUM",
                    "ticker": position["ticker"],
                    "action": "HOLD/BUY_ON_DIPS",
                    "momentum_strength": round(float(position["ppl_percent"]), 2),
                    "reason": "Strong positive momentum",
                })

        return signals

    def get_risk_reduction_signals(self) -> List[Dict[str, Any]]:
        """
        Generate signals for risk reduction.

        Returns:
            List of risk-reduction signal dicts.
        """
        signals = []

        if self.portfolio_df.empty or "value" not in self.portfolio_df.columns:
            return signals

        total_value = self.portfolio_df["value"].sum()
        if total_value == 0:
            return signals

        weights = self.portfolio_df["value"] / total_value

        # Flag over-concentrated positions (> 25 %).
        if weights.max() > 0.25:
            largest = self.portfolio_df.loc[weights.idxmax()]
            signals.append({
                "signal_type": "RISK_REDUCTION",
                "ticker": largest["ticker"],
                "action": "REDUCE_POSITION",
                "reason": (
                    f"Position too concentrated at "
                    f"{weights.max() * 100:.1f}% of portfolio"
                ),
                "suggested_max_weight": 0.15,
            })

        # Take-profit signals for positions up > 50 %.
        if "ppl_percent" in self.portfolio_df.columns:
            overperformers = self.portfolio_df[self.portfolio_df["ppl_percent"] > 50]
            for _, position in overperformers.iterrows():
                signals.append({
                    "signal_type": "RISK_REDUCTION",
                    "ticker": position["ticker"],
                    "action": "TAKE_PROFITS",
                    "reason": f"Position up {position['ppl_percent']:.1f}%",
                    "suggested_profit_target": 0.50,
                })

        return signals

    def get_all_signals(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all trading signals."""
        return {
            "rebalance": self.get_rebalance_signals(),
            "momentum": self.get_momentum_signals(),
            "risk_reduction": self.get_risk_reduction_signals(),
        }
