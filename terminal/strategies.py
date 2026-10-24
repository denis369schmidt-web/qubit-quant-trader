"""
Strategien als reine Signal-Generatoren (Long-only Spot).

Vertrag: Alle Arrays werden nur aus Daten bis einschließlich Kerze t berechnet.
Die Backtest-Engine führt ein Signal von Kerze t erst zur Eröffnung von Kerze t+1 aus.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Type

import numpy as np

from terminal import indicators as ind
from terminal.market_data import Candles


@dataclass
class Signals:
    entry: np.ndarray          # bool: Einstiegssignal am Schluss von Kerze t
    exit: np.ndarray           # bool: Ausstiegssignal am Schluss von Kerze t
    atr: np.ndarray            # ATR für Stop-Abstände und Positionsgröße
    stop_atr: float            # Initialer Stop = Einstieg - stop_atr * ATR
    trail_atr: float = 0.0     # >0: Trailing-Stop = Schlusskurs - trail_atr * ATR
    target_atr: float = 0.0    # >0: Take-Profit = Einstieg + target_atr * ATR
    max_hold_bars: int = 0     # >0: Zeit-Stop


class Strategy:
    name = "base"
    description = ""
    default_params: Dict[str, float] = {}
    param_grid: Dict[str, List[float]] = {}

    def __init__(self, **params):
        self.params = {**self.default_params, **params}

    def warmup(self) -> int:
        return 0

    def generate(self, c: Candles) -> Signals:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.name}({', '.join(f'{k}={v}' for k, v in self.params.items())})"


class TrendFollow(Strategy):
    name = "trend"
    description = "Kauft nur in sauberem Aufwärtstrend (EMA fast > slow, Trendqualität hoch), ATR-Trailing-Stop."
    default_params = {"fast": 20, "slow": 100, "er_min": 0.30, "stop_atr": 3.0, "trail_atr": 3.0}
    param_grid = {"fast": [10, 20, 30], "slow": [50, 100, 200], "trail_atr": [2.5, 3.5]}

    def warmup(self) -> int:
        return int(self.params["slow"]) + 1

    def generate(self, c: Candles) -> Signals:
        p = self.params
        fast, slow = ind.ema(c.close, int(p["fast"])), ind.ema(c.close, int(p["slow"]))
        er = ind.efficiency_ratio(c.close, 20)
        with np.errstate(invalid="ignore"):
            entry = (fast > slow) & (c.close > fast) & (er >= p["er_min"])
        exit_ = fast < slow
        return Signals(np.nan_to_num(entry).astype(bool), np.nan_to_num(exit_).astype(bool),
                       ind.atr(c.high, c.low, c.close, 14), p["stop_atr"], trail_atr=p["trail_atr"])


class DonchianBreakout(Strategy):
    name = "breakout"
    description = "Ausbruch über das N-Kerzen-Hoch, Ausstieg unter das N/2-Tief. Klassisches Turtle-Prinzip."
    default_params = {"entry_n": 55, "exit_n": 20, "stop_atr": 2.0}
    param_grid = {"entry_n": [20, 55, 100], "exit_n": [10, 20], "stop_atr": [2.0, 3.0]}

    def warmup(self) -> int:
        return int(self.params["entry_n"]) + 1

    def generate(self, c: Candles) -> Signals:
        p = self.params
        n_in, n_out = int(p["entry_n"]), int(p["exit_n"])
        prev_high = np.concatenate([[np.nan], ind.rolling_max(c.high, n_in)[:-1]])
        prev_low = np.concatenate([[np.nan], ind.rolling_min(c.low, n_out)[:-1]])
        with np.errstate(invalid="ignore"):
            entry = c.close > prev_high
            exit_ = c.close < prev_low
        return Signals(entry, exit_, ind.atr(c.high, c.low, c.close, 20), p["stop_atr"])


class MeanReversion(Strategy):
    """Port von H2 aus v1, aber mit Trendfilter: nur Rücksetzer im Aufwärtstrend kaufen."""
    name = "meanrev"
    description = "Kauft starke Ausreißer nach unten bei nachlassendem Volumen, nur über der 200er-EMA."
    default_params = {"window": 30, "z": 2.2, "rsi_max": 35, "trend_ema": 200, "stop_atr": 2.0,
                      "max_hold": 24}
    param_grid = {"z": [1.8, 2.2, 2.6], "rsi_max": [30, 40], "max_hold": [12, 24, 48]}

    def warmup(self) -> int:
        return int(max(self.params["window"], self.params["trend_ema"])) + 1

    def generate(self, c: Candles) -> Signals:
        p = self.params
        w = int(p["window"])
        mean, std = ind.rolling_mean(c.close, w), ind.rolling_std(c.close, w)
        vol_avg = ind.rolling_mean(c.volume, w)
        trend = ind.ema(c.close, int(p["trend_ema"]))
        r = ind.rsi(c.close, 14)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (c.close - mean) / std
            entry = (z <= -p["z"]) & (c.volume < vol_avg) & (r <= p["rsi_max"]) & (c.close > trend)
            exit_ = c.close >= mean
        return Signals(np.nan_to_num(entry).astype(bool), np.nan_to_num(exit_).astype(bool),
                       ind.atr(c.high, c.low, c.close, 14), p["stop_atr"], max_hold_bars=int(p["max_hold"]))


STRATEGIES: Dict[str, Type[Strategy]] = {s.name: s for s in (TrendFollow, DonchianBreakout, MeanReversion)}


def build(name: str, **params) -> Strategy:
    if name not in STRATEGIES:
        raise KeyError(f"Unbekannte Strategie '{name}'. Verfügbar: {', '.join(STRATEGIES)}")
    return STRATEGIES[name](**params)
