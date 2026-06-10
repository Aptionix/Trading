"""
Risk Analysis Module

Functions for assessing portfolio risk and exposure.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


class RiskAnalyzer:
    """Analyzer for portfolio risk metrics"""
    
    def __init__(self, portfolio_df: pd.DataFrame, cash_balance: float):
        """
        Initialize risk analyzer.
        
        Args:
            portfolio_df: DataFrame with portfolio positions
            cash_balance: Cash balance
        """
        self.portfolio_df = portfolio_df
        self.cash_balance = cash_balance
    
    def get_concentration_risk(self) -> Dict[str, Any]:
        """
        Calculate concentration risk metrics.
        
        Returns:
            Dictionary with concentration metrics
        """
        if self.portfolio_df.empty:
            return {"message": "No positions"}
        
        total_value = self.portfolio_df["value"].sum()
        weights = self.portfolio_df["value"] / total_value * 100
        
        return {
            "top_position_weight": weights.max(),
            "top_3_weight": weights.nlargest(3).sum(),
            "top_5_weight": weights.nlargest(5).sum(),
            "herfindahl_index": (weights ** 2).sum(),  # 0-10000 scale
            "risk_level": self._classify_concentration_risk((weights ** 2).sum())
        }
    
    def get_diversification_metrics(self) -> Dict[str, Any]:
        """Calculate diversification metrics"""
        if self.portfolio_df.empty:
            return {"message": "No positions"}
        
        total_value = self.portfolio_df["value"].sum()
        num_positions = len(self.portfolio_df)
        weights = self.portfolio_df["value"] / total_value
        
        # Herfindahl index for effective diversification
        h_index = (weights ** 2).sum()
        effective_positions = 1 / h_index if h_index > 0 else 0
        
        return {
            "number_of_positions": num_positions,
            "effective_positions": round(effective_positions, 2),
            "diversification_ratio": round(effective_positions / num_positions, 2) if num_positions > 0 else 0,
            "shannon_entropy": -sum(weights[weights > 0] * np.log(weights[weights > 0]))
        }
    
    def get_liquidity_analysis(self) -> Dict[str, Any]:
        """Analyze portfolio liquidity"""
        total_assets = self.portfolio_df["value"].sum() + self.cash_balance
        cash_ratio = self.cash_balance / total_assets if total_assets > 0 else 0
        
        return {
            "cash_balance": self.cash_balance,
            "total_assets": total_assets,
            "cash_ratio_percent": cash_ratio * 100,
            "liquidity_level": self._classify_liquidity(cash_ratio)
        }
    
    def get_sector_risk(self) -> Dict[str, Any]:
        """Analyze sector concentration risk"""
        if self.portfolio_df.empty:
            return {"message": "No positions"}
        
        if "sector" not in self.portfolio_df.columns:
            return {"message": "Sector data not available"}
        
        total_value = self.portfolio_df["value"].sum()
        sector_weights = self.portfolio_df.groupby("sector")["value"].sum() / total_value * 100
        
        return {
            "sector_distribution": sector_weights.to_dict(),
            "number_of_sectors": len(sector_weights),
            "highest_sector_weight": sector_weights.max(),
            "highest_sector": sector_weights.idxmax()
        }
    
    @staticmethod
    def _classify_concentration_risk(herfindahl_index: float) -> str:
        """Classify concentration risk based on Herfindahl index"""
        if herfindahl_index < 1500:
            return "Low (Well-diversified)"
        elif herfindahl_index < 2500:
            return "Moderate"
        else:
            return "High (Concentrated)"
    
    @staticmethod
    def _classify_liquidity(cash_ratio: float) -> str:
        """Classify liquidity level"""
        if cash_ratio > 0.20:
            return "Very High"
        elif cash_ratio > 0.10:
            return "High"
        elif cash_ratio > 0.05:
            return "Moderate"
        else:
            return "Low"
