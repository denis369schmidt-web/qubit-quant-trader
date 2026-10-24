"""Vektorisierte Indikatoren (numpy). Jeder Wert an Index t nutzt nur Daten bis einschließlich t."""

import numpy as np


def ema(x: np.ndarray, period: int) -> np.ndarray:
    out = np.empty_like(x, dtype=float)
    alpha = 2.0 / (period + 1.0)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    out[: period - 1] = np.nan
    return out


def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < window:
        return out
    c = np.cumsum(np.insert(x.astype(float), 0, 0.0))
    out[window - 1:] = (c[window:] - c[:-window]) / window
    return out


def rolling_std(x: np.ndarray, window: int) -> np.ndarray:
    mean = rolling_mean(x, window)
    mean_sq = rolling_mean(x.astype(float) ** 2, window)
    return np.sqrt(np.maximum(mean_sq - mean ** 2, 0.0))


def rolling_max(x: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(window - 1, len(x)):
        out[i] = x[i - window + 1: i + 1].max()
    return out


def rolling_min(x: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(window - 1, len(x)):
        out[i] = x[i - window + 1: i + 1].min()
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    out = np.full(len(close), np.nan)
    if len(close) < period:
        return out
    out[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    out = np.full(len(close), np.nan)
    if len(close) <= period:
        return out
    avg_g = gain[1: period + 1].mean()
    avg_l = loss[1: period + 1].mean()
    for i in range(period, len(close)):
        if i > period:
            avg_g = (avg_g * (period - 1) + gain[i]) / period
            avg_l = (avg_l * (period - 1) + loss[i]) / period
        out[i] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out


def efficiency_ratio(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Kaufman Efficiency Ratio: 1 = sauberer Trend, 0 = reines Rauschen."""
    out = np.full(len(close), np.nan)
    abs_diff = np.abs(np.diff(close, prepend=close[0]))
    for i in range(window, len(close)):
        noise = abs_diff[i - window + 1: i + 1].sum()
        out[i] = abs(close[i] - close[i - window]) / noise if noise > 0 else 0.0
    return out
