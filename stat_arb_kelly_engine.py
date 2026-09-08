"""
STATISTICAL ARBITRAGE, KOINTEGRATION & KELLY RISIKOMANAGEMENT ENGINE
----------------------------------------------------------------------
Mathematisch fundierte Algorithmen für quantitativen Börsenhandel:

1. Z-Score Mean Reversion Engine:
   Berechnet den rolling Z-Score: Z = (Spread - Mean) / StdDev
   Signalisiert statistische Fehlbewertungen zwischen korrelierten Märkten.

2. Fractional Kelly Criterion Position Sizing:
   Formel: f* = (p * b - q) / b
   Nutzt den Half-Kelly-Sicherheitsfaktor (0.5 * f*) für optimale Kapitalallokation.

3. Liquidation Cascade Detector:
   Identifiziert Volatilitätsschocks und Orderbuch-Eröpfungen.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Any


class StatisticalArbitrageEngine:
    """Statistische Arbitrage & Mean-Reversion Analyse über Korrelationen & Z-Scores"""

    def __init__(self, window_size: int = 30, z_entry_threshold: float = 2.0, z_exit_threshold: float = 0.5):
        self.window_size = window_size
        self.z_entry_threshold = z_entry_threshold
        self.z_exit_threshold = z_exit_threshold
        self.spread_history: List[float] = []

    def update_spread_and_calculate_zscore(self, price_a: float, price_b: float) -> Tuple[float, float, float, float]:
        """
        Berechnet den Preis-Spread = Price_A - Price_B und den rollierenden Z-Score.
        Rückgabe: (Spread, Mean, StdDev, Z-Score)
        """
        if price_a <= 0 or price_b <= 0:
            return 0.0, 0.0, 1.0, 0.0

        spread = price_a - price_b
        self.spread_history.append(spread)
        
        if len(self.spread_history) > 300:
            self.spread_history.pop(0)

        if len(self.spread_history) < self.window_size:
            return spread, spread, 1.0, 0.0

        recent_spreads = np.array(self.spread_history[-self.window_size:])
        mean = float(np.mean(recent_spreads))
        std = float(np.std(recent_spreads))

        if std == 0:
            std = 1e-6

        z_score = float((spread - mean) / std)
        return spread, mean, std, z_score

    def evaluate_stat_arb_signal(self, z_score: float) -> Dict[str, Any]:
        """
        Generiert Stat-Arb Handelssignale basierend auf statistischer Abweichung:
        - Z > +2.0  --> Asset A überbewertet -> SHORT A / BUY B
        - Z < -2.0  --> Asset A unterbewertet -> BUY A / SHORT B
        - |Z| < 0.5 --> Neutral / Mean Reversion abgeschlossen
        """
        if z_score >= self.z_entry_threshold:
            return {
                "action": "STAT_ARB_SHORT_A_BUY_B",
                "confidence": min(abs(z_score) / 3.0, 1.0),
                "reason": f"Z-Score extrem hoch (+{z_score:.2f} >= +{self.z_entry_threshold})"
            }
        elif z_score <= -self.z_entry_threshold:
            return {
                "action": "STAT_ARB_BUY_A_SHORT_B",
                "confidence": min(abs(z_score) / 3.0, 1.0),
                "reason": f"Z-Score extrem niedrig ({z_score:.2f} <= -{self.z_entry_threshold})"
            }
        elif abs(z_score) <= self.z_exit_threshold:
            return {
                "action": "STAT_ARB_EXIT",
                "confidence": 0.0,
                "reason": f"Z-Score im Normalbereich ({z_score:.2f} <= {self.z_exit_threshold})"
            }

        return {"action": "HOLD", "confidence": 0.0, "reason": f"Z-Score neutral ({z_score:.2f})"}


class KellyCriterionManager:
    """Berechnet mathematisch optimale Kapitaleinsätze nach dem Kelly-Kriterium"""

    @staticmethod
    def calculate_kelly_fraction(
        win_rate: float, 
        risk_reward_ratio: float, 
        safety_fraction: float = 0.5,
        current_drawdown: float = 0.0,
        volatility_ratio: float = 1.0
    ) -> float:
        """
        Erweiterte Fractional-Kelly-Formel mit Drawdown-Dämpfung und Volatilitäts-Skalierung:
        f* = ((p * b - q) / b) * safety * dd_penalty * vol_scale
        """
        p = max(min(win_rate, 0.95), 0.05)
        q = 1.0 - p
        b = max(risk_reward_ratio, 0.1)

        raw_kelly = (p * b - q) / b

        if raw_kelly <= 0:
            return 0.0  # Kein mathematischer Edge vorhanden!

        # Half-Kelly Sicherheitsfaktor (Schutz vor Über-Hebelung)
        optimal_kelly = raw_kelly * safety_fraction

        # Drawdown-Dämpfung: Bei Verlustserien wird das Risiko automatisch heruntergeregelt
        dd_penalty = max(0.4, 1.0 - (current_drawdown * 2.5))

        # Volatilitäts-Skalierung: Bei Markt-Turbulenzen wird das Risiko gedämpft
        vol_scale = 1.0 / max(volatility_ratio, 1.0)

        adjusted_kelly = optimal_kelly * dd_penalty * vol_scale
        return float(min(max(adjusted_kelly, 0.02), 0.30))


class LiquidationCascadeDetector:
    """Erkennt dramatische Orderbuch-Eröpfungen & Liquidationskaskaden"""

    def __init__(self, spike_std_threshold: float = 2.5):
        self.spike_std_threshold = spike_std_threshold
        self.volatility_history: List[float] = []

    def detect_liquidation_cascade(self, price_changes: List[float], obi: float) -> Dict[str, Any]:
        if len(price_changes) < 20:
            return {"is_cascade": False, "intensity": 0.0}

        recent_changes = np.array(price_changes[-20:])
        latest_change = abs(recent_changes[-1])
        std_dev = np.std(recent_changes)

        if std_dev == 0:
            std_dev = 1e-6

        z_vol = latest_change / std_dev
        is_cascade = z_vol >= self.spike_std_threshold and abs(obi) >= 0.4

        return {
            "is_cascade": is_cascade,
            "z_volatility": round(float(z_vol), 2),
            "intensity": round(min(z_vol / 4.0, 1.0), 2),
            "direction": "LONG_LIQUIDATION" if obi < 0 else "SHORT_LIQUIDATION"
        }


class MultiPairCorrelationGuard:
    """Verhindert Klumpenrisiken durch gleichzeitige Allokation in hochkorrelierte Assets"""

    @staticmethod
    def calculate_correlation(prices_a: List[float], prices_b: List[float]) -> float:
        if len(prices_a) < 15 or len(prices_b) < 15:
            return 0.75  # Konservative Krypto-Korrelationsannahme
        min_len = min(len(prices_a), len(prices_b))
        a = np.array(prices_a[-min_len:])
        b = np.array(prices_b[-min_len:])
        if np.std(a) == 0 or np.std(b) == 0:
            return 0.0
        corr = float(np.corrcoef(a, b)[0, 1])
        return corr if not math.isnan(corr) else 0.0

    @staticmethod
    def should_throttle_correlated_buy(
        target_asset: str, 
        existing_crypto_holdings: Dict[str, float], 
        correlation_matrix: Dict[str, float]
    ) -> Tuple[bool, str]:
        """Prüft, ob bereits signifikantes Exposure in stark korrelierten Assets (>0.85) vorliegt"""
        for held_asset, held_val in existing_crypto_holdings.items():
            if held_val > 5.0 and held_asset != target_asset:
                corr = correlation_matrix.get(f"{target_asset}_{held_asset}", 0.80)
                if corr >= 0.85:
                    return True, f"Korrelations-Schutz aktiv ({target_asset} korreliert zu {corr*100:.0f}% mit {held_asset})"
        return False, "OK"


class ExecutionHealthMonitor:
    """Überwacht Latenzen, Slippage und WebSocket-Jitter in Echtzeit"""

    @staticmethod
    def assess_execution_health(latencies: Dict[str, float]) -> Dict[str, Any]:
        if not latencies:
            return {"status": "OPTIMAL", "avg_latency_ms": 10.0, "warning": None}
        
        vals = [v for v in latencies.values() if v > 0]
        avg_lat = float(np.mean(vals)) if vals else 12.0
        max_lat = float(np.max(vals)) if vals else 12.0

        if max_lat > 250.0:
            return {
                "status": "DEGRADED",
                "avg_latency_ms": round(avg_lat, 1),
                "max_latency_ms": round(max_lat, 1),
                "warning": "Hohe Börsen-Latenz (>250ms). Slippage-Puffer erweitert."
            }
        return {
            "status": "OPTIMAL",
            "avg_latency_ms": round(avg_lat, 1),
            "max_latency_ms": round(max_lat, 1),
            "warning": None
        }


class CrossExchangeArbitrageEngine:
    """Berechnet marktneutrale Arbitrage-Spreads über parallele Börsen-Feeds"""

    @staticmethod
    def detect_cross_exchange_spread(
        market_prices: Dict[str, Dict[str, Any]], 
        taker_fee_total: float = 0.0030
    ) -> Dict[str, Any]:
        """
        Prüft Kursunterschiede zwischen Kraken, Binance, Coinbase, Bybit.
        Netto-Gewinn = (Price_Max - Price_Min) / Price_Min - Gebühren
        """
        valid_prices = {}
        for ex, data in market_prices.items():
            p = float(data.get("price", 0.0))
            if p > 0:
                valid_prices[ex] = p

        if len(valid_prices) < 2:
            return {"opportunity": False, "gross_spread_pct": 0.0, "net_profit_pct": 0.0, "action": "WARTEN_AUF_FEEDS"}

        sorted_ex = sorted(valid_prices.items(), key=lambda x: x[1])
        min_ex, min_p = sorted_ex[0]
        max_ex, max_p = sorted_ex[-1]

        gross_spread_pct = (max_p - min_p) / min_p
        net_profit_pct = gross_spread_pct - taker_fee_total

        if net_profit_pct >= 0.0020:
            return {
                "opportunity": True,
                "buy_exchange": min_ex,
                "buy_price": min_p,
                "sell_exchange": max_ex,
                "sell_price": max_p,
                "gross_spread_pct": round(gross_spread_pct * 100, 3),
                "net_profit_pct": round(net_profit_pct * 100, 3),
                "action": f"ARBITRAGE: KAUF {min_ex} -> VERKAUF {max_ex} (+{net_profit_pct*100:.2f}%)"
            }

        return {
            "opportunity": False,
            "buy_exchange": min_ex,
            "sell_exchange": max_ex,
            "gross_spread_pct": round(gross_spread_pct * 100, 3),
            "net_profit_pct": round(net_profit_pct * 100, 3),
            "action": "SPREAD_NORMAL"
        }


class AutoCompoundingEngine:
    """Dynamische Reinvestitions- & Zinseszins-Engine"""

    @staticmethod
    def calculate_compounding_multiplier(
        cumulative_pnl_eur: float, 
        base_equity_eur: float = 100.0,
        compounding_rate: float = 0.5
    ) -> float:
        if cumulative_pnl_eur <= 0:
            return 1.0
        
        profit_ratio = cumulative_pnl_eur / max(base_equity_eur, 10.0)
        multiplier = 1.0 + (profit_ratio * compounding_rate)
        return float(min(multiplier, 2.5))

