"""
Technical Analysis Module

Computes a rich set of technical indicators and a rule-based long/short
recommendation for any price series.

Indicators:
  MA5, MA10           — short-term simple moving averages (fast crossover)
  EMA12, EMA26        — exponential moving averages (trend, weighted to recent)
  RSI(14)             — overbought / oversold momentum
  MACD(12,26,9)       — trend-momentum crossover
  Bollinger Bands(20) — volatility envelope / mean-reversion
  Stochastic(14,3)    — momentum oscillator vs recent range

These are educational signals, NOT financial advice.
"""

from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np


# ────────────────────────────────────────────────────────────
# Core indicator functions
# ────────────────────────────────────────────────────────────

def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average (weights recent prices more heavily)."""
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def bollinger(
    series: pd.Series, window: int = 20, n_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper_band, middle_band, lower_band)."""
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=1).std()
    return mid + n_std * std, mid, mid - n_std * std


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series,
    k_window: int = 14, d_window: int = 3,
) -> Tuple[pd.Series, pd.Series]:
    """Returns (%K, %D) stochastic oscillator series."""
    lowest = low.rolling(window=k_window, min_periods=1).min()
    highest = high.rolling(window=k_window, min_periods=1).max()
    percent_k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    percent_d = percent_k.rolling(window=d_window, min_periods=1).mean()
    return percent_k, percent_d


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On-Balance Volume — cumulative volume that adds on up-days and
    subtracts on down-days. Rising OBV confirms buying pressure.
    """
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def _detect_cross(fast: pd.Series, slow: pd.Series) -> int:
    """
    Detect a fresh crossover of `fast` over/under `slow` on the latest bar.

    Returns:
        +1 if fast crossed ABOVE slow on the last bar (bullish),
        -1 if fast crossed BELOW slow on the last bar (bearish),
         0 if no fresh cross.
    """
    if len(fast) < 2 or len(slow) < 2:
        return 0
    prev_diff = fast.iloc[-2] - slow.iloc[-2]
    curr_diff = fast.iloc[-1] - slow.iloc[-1]
    if prev_diff <= 0 < curr_diff:
        return 1
    if prev_diff >= 0 > curr_diff:
        return -1
    return 0


# ────────────────────────────────────────────────────────────
# Combined scored recommendation
# ────────────────────────────────────────────────────────────

def analyze(history: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Run all indicators on an OHLCV DataFrame and return a scored
    long/short recommendation.

    Args:
        history: DataFrame with 'Close' (and ideally 'High'/'Low') columns.

    Returns:
        Dict of indicator values, a -100..+100 score, a recommendation
        label, and a list of human-readable reasons. None if insufficient data.
    """
    if history is None or history.empty or "Close" not in history.columns:
        return None

    close = history["Close"].dropna()
    if len(close) < 15:
        return None

    high = history["High"].dropna() if "High" in history.columns else close
    low = history["Low"].dropna() if "Low" in history.columns else close

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    daily_change = (price - prev) / prev * 100

    ma5 = float(sma(close, 5).iloc[-1])
    ma10 = float(sma(close, 10).iloc[-1])
    ema12 = float(ema(close, 12).iloc[-1])
    ema26 = float(ema(close, 26).iloc[-1])

    ma5_series, ma10_series = sma(close, 5), sma(close, 10)
    ema12_series, ema26_series = ema(close, 12), ema(close, 26)

    rsi_series = rsi(close, 14)
    rsi14 = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0

    macd_line, signal_line, hist_macd = macd(close)
    macd_hist = float(hist_macd.iloc[-1])
    macd_hist_prev = float(hist_macd.iloc[-2]) if len(hist_macd) > 1 else macd_hist

    upper, mid, lower = bollinger(close, 20)
    bb_upper, bb_mid, bb_lower = float(upper.iloc[-1]), float(mid.iloc[-1]), float(lower.iloc[-1])
    bb_pos = ((price - bb_lower) / (bb_upper - bb_lower) * 100) if bb_upper != bb_lower else 50.0

    k_series, d_series = stochastic(high, low, close)
    stoch_k = float(k_series.iloc[-1]) if not np.isnan(k_series.iloc[-1]) else 50.0

    # On-Balance Volume trend over the last 5 bars
    volume = history["Volume"].dropna() if "Volume" in history.columns else None
    obv_trend = 0.0
    if volume is not None and len(volume) >= 6:
        obv_series = obv(close, volume)
        recent = obv_series.iloc[-5:]
        if recent.iloc[0] != 0:
            obv_trend = (obv_series.iloc[-1] - obv_series.iloc[-5]) / abs(recent.iloc[0]) * 100

    # Fresh crossovers on the latest bar
    ma_cross = _detect_cross(ma5_series, ma10_series)
    ema_cross = _detect_cross(ema12_series, ema26_series)
    macd_cross = _detect_cross(macd_line, signal_line)

    # ── Weighted scoring (-100..+100) ──
    score = 0
    reasons = []

    # MA5 vs MA10 — short-term trend crossover
    if ma5 > ma10:
        score += 20
        reasons.append(f"MA5 above MA10 ({ma5:.2f} > {ma10:.2f}) — short-term uptrend")
    else:
        score -= 20
        reasons.append(f"MA5 below MA10 ({ma5:.2f} < {ma10:.2f}) — short-term downtrend")

    # EMA12 vs EMA26 — medium trend
    if ema12 > ema26:
        score += 15
        reasons.append("EMA12 above EMA26 — bullish trend")
    else:
        score -= 15
        reasons.append("EMA12 below EMA26 — bearish trend")

    # RSI
    if rsi14 < 30:
        score += 18
        reasons.append(f"RSI {rsi14:.0f} — oversold, potential bounce")
    elif rsi14 > 70:
        score -= 18
        reasons.append(f"RSI {rsi14:.0f} — overbought, potential pullback")
    else:
        reasons.append(f"RSI {rsi14:.0f} — neutral")

    # MACD histogram + its slope (rising/falling)
    if macd_hist > 0:
        score += 12
        reasons.append("MACD histogram positive — bullish momentum")
    else:
        score -= 12
        reasons.append("MACD histogram negative — bearish momentum")
    if macd_hist > macd_hist_prev:
        score += 6
        reasons.append("MACD momentum rising")
    else:
        score -= 6

    # Bollinger position — mean reversion
    if bb_pos < 10:
        score += 12
        reasons.append(f"Price near lower Bollinger band ({bb_pos:.0f}%) — stretched low")
    elif bb_pos > 90:
        score -= 12
        reasons.append(f"Price near upper Bollinger band ({bb_pos:.0f}%) — stretched high")

    # Stochastic
    if stoch_k < 20:
        score += 10
        reasons.append(f"Stochastic %K {stoch_k:.0f} — oversold")
    elif stoch_k > 80:
        score -= 10
        reasons.append(f"Stochastic %K {stoch_k:.0f} — overbought")

    # Short-term move
    if daily_change > 3:
        score += 7
        reasons.append(f"Strong daily gain (+{daily_change:.1f}%)")
    elif daily_change < -3:
        score -= 7
        reasons.append(f"Strong daily drop ({daily_change:.1f}%)")

    # Fresh crossovers — timely, higher-weight signals
    fresh_signals = []
    if ma_cross == 1:
        score += 18
        fresh_signals.append("MA5 crossed ABOVE MA10 (bullish)")
    elif ma_cross == -1:
        score -= 18
        fresh_signals.append("MA5 crossed BELOW MA10 (bearish)")
    if ema_cross == 1:
        score += 14
        fresh_signals.append("EMA12 crossed ABOVE EMA26 (bullish)")
    elif ema_cross == -1:
        score -= 14
        fresh_signals.append("EMA12 crossed BELOW EMA26 (bearish)")
    if macd_cross == 1:
        score += 14
        fresh_signals.append("MACD crossed ABOVE signal (bullish)")
    elif macd_cross == -1:
        score -= 14
        fresh_signals.append("MACD crossed BELOW signal (bearish)")
    for fs in fresh_signals:
        reasons.append(f"⚡ {fs}")

    # OBV volume confirmation
    if obv_trend > 5:
        score += 8
        reasons.append(f"OBV rising ({obv_trend:+.0f}%) — buying volume confirms")
    elif obv_trend < -5:
        score -= 8
        reasons.append(f"OBV falling ({obv_trend:+.0f}%) — selling volume confirms")

    score = int(max(-100, min(100, score)))

    if score >= 50:
        rec = "STRONG LONG"
    elif score >= 20:
        rec = "LONG"
    elif score <= -50:
        rec = "STRONG SHORT"
    elif score <= -20:
        rec = "SHORT"
    else:
        rec = "NEUTRAL"

    return {
        "price": round(price, 2),
        "daily_change": round(daily_change, 2),
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ema12": round(ema12, 2),
        "ema26": round(ema26, 2),
        "rsi14": round(rsi14, 1),
        "macd_hist": round(macd_hist, 3),
        "bb_pos": round(bb_pos, 1),
        "stoch_k": round(stoch_k, 1),
        "obv_trend": round(obv_trend, 1),
        "fresh_signals": fresh_signals,
        "score": score,
        "recommendation": rec,
        "reasons": reasons,
    }
