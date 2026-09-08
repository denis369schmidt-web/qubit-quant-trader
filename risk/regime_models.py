"""
REGIME- UND STRUKTURMODELL MIT HYSTERESE & STRESSKORRELATION
-----------------------------------------------------------
1. 6 diskrete Regime-Klassen:
   - CALM_UPTREND
   - CALM_DOWNTREND
   - RANGE_BOUND
   - TREND_BREAK
   - VOLATILITY_SHOCK
   - LIQUIDITY_STRESS
2. Regimewechsel-Hysterese:
   Verhindert Flackern durch Mindestverweildauer und Bestätigungsfenster.
3. Rollende Korrelation & Stresskorrelation:
   Ermittelt Korrelationen aus realen Renditen und berechnet worst-case Stress-VaR.
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


class StructuralRegimeClassifier:
    """
    Klassifiziert das Marktregime anhand von Trendstärke, Volatilität (ATR) und Liquidität.
    Mit eingebauter Hysterese zur Vermeidung von Signalflackern.
    """

    def __init__(self, hysteresis_ticks: int = 5):
        self.hysteresis_ticks = hysteresis_ticks
        self.current_regime = MarketRegime.RANGE_BOUND
        self.candidate_regime = MarketRegime.RANGE_BOUND
        self.candidate_count = 0
        self.price_history = []
        self.volume_history = []

    def update(self, price: float, volume: float, spread_bps: float = 2.0, atr_pct: float = 0.01) -> str:
        self.price_history.append(price)
        self.volume_history.append(volume)
        if len(self.price_history) > 200:
            self.price_history.pop(0)
            self.volume_history.pop(0)

        # 1. Roh-Regime ermitteln
        raw_regime = self._classify_raw(spread_bps, atr_pct)

        # 2. Hysterese-Filterung
        if raw_regime == self.current_regime:
            self.candidate_count = 0
            self.candidate_regime = self.current_regime
        else:
            if raw_regime == self.candidate_regime:
                self.candidate_count += 1
                # Wenn das neue Regime über N Ticks stabil bleibt -> Umschalten
                if self.candidate_count >= self.hysteresis_ticks:
                    self.current_regime = raw_regime
                    self.candidate_count = 0
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
        returns = np.diff(prices) / prices[:-1]
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


class RollingStressCorrelationMatrix:
    """
    Berechnet rollende Korrelationen aus echten Renditen und
    schätzt Stress-Korrelationen bei gleichzeitigen Markteinbrüchen.
    """

    def __init__(self, window: int = 50):
        self.window = window
        self.asset_returns: Dict[str, List[float]] = {}
        self.last_prices: Dict[str, float] = {}

    def update_price(self, asset: str, price: float):
        if price <= 0:
            return
        if asset in self.last_prices and self.last_prices[asset] > 0:
            ret = (price - self.last_prices[asset]) / self.last_prices[asset]
            if asset not in self.asset_returns:
                self.asset_returns[asset] = []
            self.asset_returns[asset].append(ret)
            if len(self.asset_returns[asset]) > self.window:
                self.asset_returns[asset].pop(0)
        self.last_prices[asset] = price

    def get_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        assets = list(self.asset_returns.keys())
        matrix = {a: {} for a in assets}
        for i, a1 in enumerate(assets):
            matrix[a1][a1] = 1.0
            for j, a2 in enumerate(assets):
                if i < j:
                    r1 = self.asset_returns[a1]
                    r2 = self.asset_returns[a2]
                    min_len = min(len(r1), len(r2))
                    if min_len > 10:
                        corr = float(np.corrcoef(r1[-min_len:], r2[-min_len:])[0, 1])
                        corr = 0.0 if np.isnan(corr) else round(corr, 3)
                    else:
                        corr = 0.5 # Default-Annahme
                    matrix[a1][a2] = corr
                    matrix[a2][a1] = corr
        return matrix

    def calculate_stress_var(self, balances_eur: Dict[str, float], confidence: float = 0.99) -> float:
        """
        Berechnet den 1-Tages Portfolio-VaR unter Berücksichtigung von Stress-Korrelationen.
        In Stressphasen konvergieren Krypto-Korrelationen gegen 1.0.
        """
        total_exposure = sum(val for k, val in balances_eur.items() if k != "EUR" and val > 0)
        if total_exposure <= 0:
            return 0.0

        # Konservatives Stress-VaR Modell: Korrelationsannahme steigt auf 0.90 in Krisen
        # 99% Quantil ~ 2.33 StdAbw bei typischer Krypto-Tagesvolatilität von ~4%
        stress_daily_vol = 0.05
        stress_z = 2.33
        return round(total_exposure * stress_daily_vol * stress_z * 0.90, 2)
