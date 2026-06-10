"""
Machine Learning Price-Direction Predictor

Trains a Gradient Boosting classifier on a stock's own technical-indicator
history to estimate the probability that its price will be HIGHER N trading
days from now.

Design notes / honesty:
  - Features are computed only from PAST data (no look-ahead bias).
  - Accuracy is measured on a TIME-SERIES HOLDOUT (train on the earlier
    portion, test on the most recent portion the model never saw).
  - The final prediction is made by a model retrained on all available data.
  - A 20-trading-day horizon (~1 calendar month) is more learnable than a
    daily flip, but still noisy. Trained on ~4 years of history. This is an
    educational tool, NOT a profitable strategy and NOT financial advice.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score

from src.technical_analysis import sma, ema, rsi, macd, bollinger, stochastic

HORIZON = 20           # predict direction this many trading days ahead (~1 month)
MIN_ROWS = 150         # need at least this many usable feature rows to train


def _build_features(history: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer a feature matrix (+ target) from OHLCV history.

    Target `y` = 1 if Close rises over the next HORIZON days, else 0.
    All feature columns use only information available at time t.
    """
    df = pd.DataFrame(index=history.index)
    close = history["Close"]
    high = history["High"] if "High" in history.columns else close
    low = history["Low"] if "Low" in history.columns else close
    volume = history["Volume"] if "Volume" in history.columns else pd.Series(0, index=close.index)

    # Momentum / returns
    df["ret_1d"] = close.pct_change(1)
    df["ret_5d"] = close.pct_change(5)
    df["ret_10d"] = close.pct_change(10)

    # Moving-average relationships
    df["ma5_ma10"] = sma(close, 5) / sma(close, 10) - 1
    df["ema12_ema26"] = ema(close, 12) / ema(close, 26) - 1
    df["price_ma10"] = close / sma(close, 10) - 1

    # Oscillators
    df["rsi14"] = rsi(close, 14)
    _, _, macd_hist = macd(close)
    df["macd_hist"] = macd_hist
    k, d = stochastic(high, low, close)
    df["stoch_k"] = k

    # Volatility & Bollinger position
    upper, mid, lower = bollinger(close, 20)
    df["bb_pos"] = (close - lower) / (upper - lower).replace(0, np.nan)
    df["volatility"] = close.pct_change().rolling(20).std()

    # Volume pressure
    vol_ma = volume.rolling(20).mean()
    df["vol_ratio"] = volume / vol_ma.replace(0, np.nan)

    # Target: future direction
    future_return = close.shift(-HORIZON) / close - 1
    df["y"] = (future_return > 0).astype(int)

    # Rows where the future label is unknown (the most recent HORIZON rows)
    # keep their features for prediction but drop them from training later.
    return df


FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_10d",
    "ma5_ma10", "ema12_ema26", "price_ma10",
    "rsi14", "macd_hist", "stoch_k",
    "bb_pos", "volatility", "vol_ratio",
]


def predict(history: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Train on the stock's history and predict the next-HORIZON-day direction.

    Returns dict:
        direction        : "UP" | "DOWN"
        probability_up   : float 0..1   (model confidence price rises)
        horizon_days     : int
        backtest_accuracy: float 0..1   (out-of-sample holdout accuracy)
        n_train          : int          (training samples)
        top_features     : list[(name, importance)]  top 3 drivers
    Returns None if there is not enough data to train responsibly.
    """
    if history is None or history.empty or "Close" not in history.columns:
        return None

    feat = _build_features(history)

    # Split: rows with a known label are trainable; the final row with
    # complete features but unknown label is what we predict.
    labelled = feat.dropna(subset=FEATURE_COLS + ["y"])
    if len(labelled) < MIN_ROWS:
        return None

    X = labelled[FEATURE_COLS].values
    y = labelled["y"].values

    # Time-series holdout: train on first 80%, test on last 20%.
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = GradientBoostingClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.05,
        subsample=0.9, random_state=42,
    )
    model.fit(X_train, y_train)
    backtest_acc = accuracy_score(y_test, model.predict(X_test)) if len(X_test) else float("nan")

    # Retrain on ALL labelled data for the live prediction.
    final_model = GradientBoostingClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.05,
        subsample=0.9, random_state=42,
    )
    final_model.fit(X, y)

    # Predict on the most recent row that has complete features
    # (its label lies in the future, which is exactly what we want).
    latest = feat.dropna(subset=FEATURE_COLS).iloc[[-1]][FEATURE_COLS].values
    proba_up = float(final_model.predict_proba(latest)[0][1])

    importances = sorted(
        zip(FEATURE_COLS, final_model.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )[:3]

    return {
        "direction": "UP" if proba_up >= 0.5 else "DOWN",
        "probability_up": round(proba_up, 3),
        "horizon_days": HORIZON,
        "backtest_accuracy": round(float(backtest_acc), 3),
        "n_train": int(len(X)),
        "top_features": [(name, round(float(imp), 3)) for name, imp in importances],
    }
