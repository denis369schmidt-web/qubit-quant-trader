"""
REGIME- UND STRUKTURMODELL MIT DATENBASIERTER ÜBERGANGSMATRIX & HYSTERESE
-------------------------------------------------------------------------
1. 6 diskrete Regime-Klassen:
   - CALM_UPTREND
   - CALM_DOWNTREND
   - RANGE_BOUND
   - TREND_BREAK
   - VOLATILITY_SHOCK
   - LIQUIDITY_STRESS
2. Datenbasierte Übergangsmatrix (Transition Matrix) aus historischen Beobachtungen
3. Hysterese mit Mindestverweildauer (z.B. 5-8 Ticks) gegen Flackern
4. Strategie-Zulassungsmatrix pro Regime mit defensiven Defaults
"""

import numpy as np
from typing import Dict, List, Any, Optional

class MarketRegime:
    CALM_UPTREND = "CALM_UPTREND"
    CALM_DOWNTREND = "CALM_DOWNTREND"
    RANGE_BOUND = "RANGE_BOUND"
    TREND_BREAK = "TREND_BREAK"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"

    ALL_REGIMES = [
        CALM_UPTREND, CALM_DOWNTREND, RANGE_BOUND,
        TREND_BREAK, VOLATILITY_SHOCK, LIQUIDITY_STRESS
    ]


class StructuralRegimeClassifier:
    """
    Klassifiziert das Marktregime anhand von Trendstärke, Volatilität (ATR) und Liquidität.
    Schätzt eine empirische Übergangsmatrix und filtert Signalflackern über Hysterese.
    """

    # Strategie-Zulassung pro Regime
    ALLOWED_STRATEGIES = {
        MarketRegime.CALM_UPTREND: ["TREND_CONTINUATION", "MOMENTUM_PULLBACK"],
        MarketRegime.CALM_DOWNTREND: ["DEFENSIVE_CASH", "SHORT_HEDGE"],
        MarketRegime.RANGE_BOUND: ["MEAN_REVERSION_H2", "VWAP_REVERT"],
        MarketRegime.TREND_BREAK: ["DEFENSIVE_CASH", "BREAKOUT_WATCH"],
        MarketRegime.VOLATILITY_SHOCK: ["DEACTIVATED", "RISK_EXIT_ONLY"],
        MarketRegime.LIQUIDITY_STRESS: ["DEACTIVATED", "EMERGENCY_HALT"]
    }

    def __init__(self, hysteresis_ticks: int = 5):
        self.hysteresis_ticks = hysteresis_ticks
        self.current_regime = MarketRegime.RANGE_BOUND
        self.candidate_regime = MarketRegime.RANGE_BOUND
        self.candidate_count = 0
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        
        # Beobachtete Übergänge zur Schätzung der Transitionsmatrix
        self.observed_transitions: Dict[str, Dict[str, int]] = {
            r1: {r2: 0 for r2 in MarketRegime.ALL_REGIMES} for r1 in MarketRegime.ALL_REGIMES
        }

    def update(self, price: float, volume: float, spread_bps: float = 2.0, atr_pct: float = 0.01) -> str:
        self.price_history.append(price)
        self.volume_history.append(volume)
        if len(self.price_history) > 300:
            self.price_history.pop(0)
            self.volume_history.pop(0)

        # 1. Roh-Regime ermitteln
        raw_regime = self._classify_raw(spread_bps, atr_pct)

        # 2. Hysterese-Filterung (Flackerschutz)
        if raw_regime == self.current_regime:
            self.candidate_count = 0
            self.candidate_regime = self.current_regime
        else:
            if raw_regime == self.candidate_regime:
                self.candidate_count += 1
                # Wenn das neue Regime über N Ticks stabil bleibt -> Umschalten
                if self.candidate_count >= self.hysteresis_ticks:
                    old_regime = self.current_regime
                    self.current_regime = raw_regime
                    self.candidate_count = 0
                    # Übergang protokollieren
                    self.observed_transitions[old_regime][raw_regime] += 1
            else:
                self.candidate_regime = raw_regime
                self.candidate_count = 1

        return self.current_regime

    def _classify_raw(self, spread_bps: float, atr_pct: float) -> str:
        # A. Stress-Regimes haben absolute Priorität
        if spread_bps > 15.0:
            return MarketRegime.LIQUIDITY_STRESS
        if atr_pct > 0.035:
            return MarketRegime.VOLATILITY_SHOCK

        if len(self.price_history) < 30:
            return MarketRegime.RANGE_BOUND

        # B. Trend vs. Range
        prices = np.array(self.price_history[-30:])
        cumulative_ret = (prices[-1] - prices[0]) / prices[0]

        # Effizienz-Verhältnis (Kaufman Efficiency Ratio)
        direction = abs(prices[-1] - prices[0])
        volatility = np.sum(np.abs(np.diff(prices)))
        efficiency = direction / volatility if volatility > 0 else 0.0

        if efficiency > 0.55:
            if cumulative_ret > 0.01:
                return MarketRegime.CALM_UPTREND
            elif cumulative_ret < -0.01:
                return MarketRegime.CALM_DOWNTREND
            else:
                return MarketRegime.TREND_BREAK
        elif efficiency < 0.25:
            return MarketRegime.RANGE_BOUND
        else:
            return MarketRegime.RANGE_BOUND

    def get_empirical_transition_matrix(self) -> Dict[str, Dict[str, float]]:
        """Berechnet die empirische Übergangswahrscheinlichkeitsmatrix aus Beobachtungen."""
        matrix = {}
        for r1 in MarketRegime.ALL_REGIMES:
            total = sum(self.observed_transitions[r1].values())
            matrix[r1] = {}
            for r2 in MarketRegime.ALL_REGIMES:
                if total > 0:
                    matrix[r1][r2] = round(self.observed_transitions[r1][r2] / total, 3)
                else:
                    matrix[r1][r2] = 1.0 if r1 == r2 else 0.0
        return matrix

    def is_strategy_allowed(self, strategy_family: str) -> bool:
        """Prüft, ob eine Strategiefamilie im aktuellen Regime zugelassen ist."""
        allowed = self.ALLOWED_STRATEGIES.get(self.current_regime, [])
        return strategy_family in allowed


# Kompatibilität
class RollingStressCorrelationMatrix:
    """Kompatibilitäts-Wrapper für bestehende Modulaufrufe."""
    def __init__(self, window: int = 50):
        from risk.correlation_engine import PortfolioCorrelationEngine
        self._engine = PortfolioCorrelationEngine(window=window)

    def update_price(self, asset: str, price: float):
        self._engine.update_price(asset, price)

    def get_correlation_matrix(self):
        return self._engine.get_rolling_correlation_matrix()

    def get_stress_correlation_matrix(self):
        return self._engine.get_stress_correlation_matrix()

    def calculate_stress_var(self, balances_eur: Dict[str, float], confidence: float = 0.99):
        res = self._engine.calculate_portfolio_var_and_es(balances_eur, confidence=confidence)
        return res["stress_var_eur"]
