"""
CANONICAL STRATEGY FRAMEWORK (VERSIONED & REPRODUCIBLE)
-------------------------------------------------------
Garantiert 100%ige Strategie-Identität zwischen:
- Backtest
- Replay
- Forward Paper
- Live Execution

Alle Modi verwenden exakt dieselben:
1. Feature-Berechnungen
2. Warm-up-Regeln
3. Schwellenwerte
4. Signalzeitpunkte (ausschließlich auf geschlossenen Kerzen)
5. Ein- und Ausstiegsregeln
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import numpy as np


class SignalType:
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ExitType:
    NONE = "NONE"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_PROFIT = "TRAILING_PROFIT"
    RATCHET_BREAKEVEN = "RATCHET_BREAKEVEN"
    EXHAUSTION_EXIT = "EXHAUSTION_EXIT"
    TIME_STOP = "TIME_STOP"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


class BaseCanonicalStrategy(ABC):
    """Abstrakte Basisklasse für alle kanonischen Handelsstrategien."""

    def __init__(self, name: str, version: str, parameters: Dict[str, Any]):
        self.name = name
        self.version = version
        self.parameters = parameters
        self.warmup_period = parameters.get("warmup_period", 30)

    @abstractmethod
    def evaluate_signal(
        self,
        closed_candles: List[Dict[str, Any]],
        orderbook_metrics: Optional[Dict[str, Any]] = None,
        position_open: bool = False
    ) -> Dict[str, Any]:
        """
        Wertet das Eingangssignal AUSSCHLIESSLICH auf abgeschlossenen Kerzen aus.
        Rückgabe: {"signal": SignalType, "reason": str, "indicators": dict}
        """
        pass

    @abstractmethod
    def evaluate_exit(
        self,
        entry_price: float,
        current_price: float,
        peak_price: float,
        entry_timestamp: float,
        current_timestamp: float,
        atr: float,
        fee_rate_roundtrip: float = 0.0052
    ) -> Dict[str, Any]:
        """
        Wertet Ausstiegsregeln (Stop Loss, Take Profit, Trailing Profit, Time Stop) aus.
        Rückgabe: {"exit": bool, "exit_type": ExitType, "reason": str}
        """
        pass


class H2MeanReversionStrategy_v1(BaseCanonicalStrategy):
    """
    Kanonische Implementierung von Hypothese H2:
    Mean-Reversion nach statistischer Extrem-Auslenkung und Volumen-Erschöpfung.

    Bedingungen für BUY:
    1. Kerzenanzahl >= warmup_period (30 Kerzen)
    2. Auslenkung: close < mean(30) - z_score_threshold * std(30) (Standard: 2.2 Sigma)
    3. Volumen-Erschöpfung: volume(last) < avg_volume(30) * volume_exhaustion_ratio (Standard: 1.0)
    4. Optionaler RSI-Filter: rsi < rsi_threshold (Standard: 40.0)
    5. Optionaler OBI-Filter: orderbook imbalance >= obi_threshold (Standard: 0.0, d.h. kein Verkaufsüberhang)
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "window": 30,
            "z_score_threshold": 2.2,
            "volume_exhaustion_ratio": 1.0,
            "use_rsi_filter": True,
            "rsi_window": 14,
            "rsi_threshold": 40.0,
            "use_obi_filter": True,
            "obi_threshold": 0.0,
            "warmup_period": 30,
            "sl_mult": 1.5,
            "tp_mult": 2.5,
            "min_sl_pct": 0.015,
            "max_sl_pct": 0.035,
            "min_tp_pct": 0.020,
            "max_tp_pct": 0.060,
            "trailing_profit_threshold": 0.015,
            "trailing_pullback": 0.004,
            "ratchet_threshold": 0.008,
            "max_holding_seconds": 86400  # 24h Time-Stop
        }
        if parameters:
            default_params.update(parameters)
        super().__init__(name="H2_MEAN_REVERSION", version="1.0.0", parameters=default_params)

    def evaluate_signal(
        self,
        closed_candles: List[Dict[str, Any]],
        orderbook_metrics: Optional[Dict[str, Any]] = None,
        position_open: bool = False
    ) -> Dict[str, Any]:
        window = self.parameters["window"]
        if len(closed_candles) < window:
            return {
                "signal": SignalType.HOLD,
                "reason": f"WARMUP ({len(closed_candles)}/{window} Kerzen)",
                "indicators": {}
            }

        closes = np.array([c["close"] for c in closed_candles[-window:]], dtype=float)
        volumes = np.array([c["volume"] for c in closed_candles[-window:]], dtype=float)

        mean_p = float(np.mean(closes))
        std_p = float(np.std(closes))
        cur_p = float(closes[-1])
        cur_v = float(volumes[-1])
        avg_v = float(np.mean(volumes))

        z_score = (cur_p - mean_p) / std_p if std_p > 1e-8 else 0.0

        # RSI berechnen
        rsi_val = 50.0
        if self.parameters["use_rsi_filter"]:
            rsi_w = self.parameters["rsi_window"]
            if len(closed_candles) >= rsi_w + 1:
                all_closes = np.array([c["close"] for c in closed_candles[-(rsi_w + 1):]], dtype=float)
                diffs = np.diff(all_closes)
                gains = np.where(diffs > 0, diffs, 0.0)
                losses = np.where(diffs < 0, -diffs, 0.0)
                avg_gain = float(np.mean(gains))
                avg_loss = float(np.mean(losses))
                if avg_loss == 0.0:
                    rsi_val = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi_val = 100.0 - (100.0 / (1.0 + rs))

        obi_val = 0.0
        if orderbook_metrics and "obi" in orderbook_metrics:
            obi_val = float(orderbook_metrics["obi"])

        indicators = {
            "mean_p": round(mean_p, 2),
            "std_p": round(std_p, 2),
            "z_score": round(z_score, 2),
            "cur_volume": round(cur_v, 4),
            "avg_volume": round(avg_v, 4),
            "rsi": round(rsi_val, 1),
            "obi": round(obi_val, 3)
        }

        # Ausstiegsprüfung für bestehende Position bei Mean-Touch
        if position_open:
            if cur_p >= mean_p:
                return {
                    "signal": SignalType.SELL,
                    "reason": f"MEAN_REVERTED (Preis {cur_p:.2f} >= Mean {mean_p:.2f})",
                    "indicators": indicators
                }
            return {"signal": SignalType.HOLD, "reason": "POSITION_HELD", "indicators": indicators}

        # Einstiegsprüfung (BUY):
        # 1. Statistische Extrem-Auslenkung
        is_dip = z_score <= -self.parameters["z_score_threshold"]
        # 2. Volumen-Erschöpfung
        is_exhausted = cur_v <= (avg_v * self.parameters["volume_exhaustion_ratio"])
        # 3. RSI-Filter (optional)
        rsi_ok = (not self.parameters["use_rsi_filter"]) or (rsi_val <= self.parameters["rsi_threshold"])
        # 4. OBI-Filter (optional)
        obi_ok = (not self.parameters["use_obi_filter"]) or (obi_val >= self.parameters["obi_threshold"])

        if is_dip and is_exhausted and rsi_ok and obi_ok:
            return {
                "signal": SignalType.BUY,
                "reason": f"H2_EXHAUSTION_DIP (z={z_score:.2f} <= -{self.parameters['z_score_threshold']}, v={cur_v:.2f} <= {avg_v:.2f}, rsi={rsi_val:.1f}, obi={obi_val:.2f})",
                "indicators": indicators
            }

        return {"signal": SignalType.HOLD, "reason": "NO_SETUP", "indicators": indicators}

    def evaluate_exit(
        self,
        entry_price: float,
        current_price: float,
        peak_price: float,
        entry_timestamp: float,
        current_timestamp: float,
        atr: float,
        fee_rate_roundtrip: float = 0.0052
    ) -> Dict[str, Any]:
        if entry_price <= 0:
            return {"exit": False, "exit_type": ExitType.NONE, "reason": "INVALID_ENTRY_PRICE"}

        # 1. Dynamische Schwellen aus ATR berechnen
        min_sl = self.parameters["min_sl_pct"]
        max_sl = self.parameters["max_sl_pct"]
        min_tp = self.parameters["min_tp_pct"]
        max_tp = self.parameters["max_tp_pct"]

        sl_dist_pct = max(min_sl, min(max_sl, (self.parameters["sl_mult"] * atr) / entry_price)) if atr > 0 else min_sl
        tp_dist_pct = max(min_tp, min(max_tp, (self.parameters["tp_mult"] * atr) / entry_price)) if atr > 0 else min_tp

        # Fee-Floor für garantierten Nettogewinn
        min_net_profit_pct = 0.0020
        fee_threshold_price = entry_price * (1.0 + fee_rate_roundtrip + min_net_profit_pct)

        gross_ret = (current_price - entry_price) / entry_price
        peak_ret = (peak_price - entry_price) / entry_price
        pullback_from_peak = (peak_price - current_price) / peak_price if peak_price > 0 else 0.0

        # A. Priorisierter Stop Loss / Circuit Breaker (RISK_EXIT)
        if current_price <= entry_price * (1.0 - sl_dist_pct):
            return {
                "exit": True,
                "exit_type": ExitType.STOP_LOSS,
                "reason": f"STOP_LOSS_HIT (-{gross_ret*100:.2f}% <= -{sl_dist_pct*100:.2f}%)"
            }

        # B. Time-Stop (Maximale Haltedauer überschritten)
        if (current_timestamp - entry_timestamp) >= self.parameters["max_holding_seconds"]:
            return {
                "exit": True,
                "exit_type": ExitType.TIME_STOP,
                "reason": f"TIME_STOP_EXPIRED ({int(current_timestamp - entry_timestamp)}s >= {self.parameters['max_holding_seconds']}s)"
            }

        # C. Trailing Profit Lock
        if peak_ret >= self.parameters["trailing_profit_threshold"] and pullback_from_peak >= self.parameters["trailing_pullback"] and current_price >= fee_threshold_price:
            return {
                "exit": True,
                "exit_type": ExitType.TRAILING_PROFIT,
                "reason": f"TRAILING_PROFIT_LOCK (+{gross_ret*100:.2f}%, Peak: {peak_price:.2f})"
            }

        # D. Ratchet Break-Even Absicherung
        if peak_ret >= self.parameters["ratchet_threshold"] and current_price <= entry_price * (1.0 + fee_rate_roundtrip + 0.0010) and current_price >= fee_threshold_price:
            return {
                "exit": True,
                "exit_type": ExitType.RATCHET_BREAKEVEN,
                "reason": f"RATCHET_BREAKEVEN (+{gross_ret*100:.2f}%)"
            }

        # E. Take-Profit Ziel
        if current_price >= entry_price * (1.0 + tp_dist_pct) and current_price >= fee_threshold_price:
            return {
                "exit": True,
                "exit_type": ExitType.TAKE_PROFIT,
                "reason": f"TAKE_PROFIT_HIT (+{gross_ret*100:.2f}% >= +{tp_dist_pct*100:.2f}%)"
            }

        return {"exit": False, "exit_type": ExitType.NONE, "reason": "HOLD"}


class LongOnlyTrendFollower_v1(BaseCanonicalStrategy):
    """
    Kanonische Long-Only Trendfolge-Baseline:
    Nutzt Donchian-Channel-Ausbruch (20 Perioden) oder SMA(20) > SMA(50)
    mit Kaufman-Effizienz-Filter (> 0.45).
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_window": 20,
            "slow_window": 50,
            "efficiency_threshold": 0.45,
            "warmup_period": 50,
            "sl_pct": 0.025,
            "tp_pct": 0.060,
            "trailing_stop_pct": 0.020
        }
        if parameters:
            default_params.update(parameters)
        super().__init__(name="LONG_ONLY_TREND", version="1.0.0", parameters=default_params)

    def evaluate_signal(
        self,
        closed_candles: List[Dict[str, Any]],
        orderbook_metrics: Optional[Dict[str, Any]] = None,
        position_open: bool = False
    ) -> Dict[str, Any]:
        slow_w = self.parameters["slow_window"]
        if len(closed_candles) < slow_w:
            return {"signal": SignalType.HOLD, "reason": f"WARMUP ({len(closed_candles)}/{slow_w})", "indicators": {}}

        closes = np.array([c["close"] for c in closed_candles], dtype=float)
        fast_sma = float(np.mean(closes[-self.parameters["fast_window"]:]))
        slow_sma = float(np.mean(closes[-slow_w:]))
        cur_p = float(closes[-1])

        # Effizienz-Verhältnis (Kaufman)
        p_slice = closes[-self.parameters["fast_window"]:]
        net_chg = abs(p_slice[-1] - p_slice[0])
        vol_sum = float(np.sum(np.abs(np.diff(p_slice))))
        efficiency = net_chg / vol_sum if vol_sum > 0 else 0.0

        indicators = {
            "fast_sma": round(fast_sma, 2),
            "slow_sma": round(slow_sma, 2),
            "efficiency": round(efficiency, 3),
            "close": cur_p
        }

        if position_open:
            # Ausstieg wenn Fast SMA unter Slow SMA kreuzt
            if fast_sma < slow_sma:
                return {"signal": SignalType.SELL, "reason": f"TREND_REVERSAL (Fast {fast_sma:.2f} < Slow {slow_sma:.2f})", "indicators": indicators}
            return {"signal": SignalType.HOLD, "reason": "TREND_CONTINUES", "indicators": indicators}

        # Einstieg wenn Fast SMA über Slow SMA und Trend-Effizienz hoch
        if fast_sma > slow_sma and cur_p > fast_sma and efficiency >= self.parameters["efficiency_threshold"]:
            return {
                "signal": SignalType.BUY,
                "reason": f"TREND_BREAKOUT (Fast > Slow & Eff={efficiency:.2f} >= {self.parameters['efficiency_threshold']:.2f})",
                "indicators": indicators
            }

        return {"signal": SignalType.HOLD, "reason": "NO_TREND_SETUP", "indicators": indicators}

    def evaluate_exit(
        self,
        entry_price: float,
        current_price: float,
        peak_price: float,
        entry_timestamp: float,
        current_timestamp: float,
        atr: float,
        fee_rate_roundtrip: float = 0.0052
    ) -> Dict[str, Any]:
        if entry_price <= 0:
            return {"exit": False, "exit_type": ExitType.NONE, "reason": "INVALID_ENTRY_PRICE"}

        gross_ret = (current_price - entry_price) / entry_price
        pullback = (peak_price - current_price) / peak_price if peak_price > 0 else 0.0

        # Stop Loss
        if gross_ret <= -self.parameters["sl_pct"]:
            return {"exit": True, "exit_type": ExitType.STOP_LOSS, "reason": f"STOP_LOSS (-{abs(gross_ret)*100:.2f}%)"}

        # Trailing Stop ab +2% Gewinn
        if (peak_price - entry_price) / entry_price >= 0.020 and pullback >= self.parameters["trailing_stop_pct"]:
            return {"exit": True, "exit_type": ExitType.TRAILING_PROFIT, "reason": f"TRAILING_STOP (Pullback {pullback*100:.2f}%)"}

        # Take Profit
        if gross_ret >= self.parameters["tp_pct"]:
            return {"exit": True, "exit_type": ExitType.TAKE_PROFIT, "reason": f"TAKE_PROFIT (+{gross_ret*100:.2f}%)"}

        return {"exit": False, "exit_type": ExitType.NONE, "reason": "HOLD"}
