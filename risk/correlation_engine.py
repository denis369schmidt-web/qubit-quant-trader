"""
KORRELATIONS-, KLUMPENRISIKO- UND PORTFOLIO-STRESS-ENGINE
---------------------------------------------------------
1. Rollende Korrelationen aus echten Renditen
2. Stresskorrelation bei Drawdowns (untere 10% der Renditen)
3. Portfolio-VaR / Expected Shortfall (ES) auf täglicher Basis
4. Dynamische Exposure-Drosselung bei Korrelations-Stress
"""

import numpy as np
from typing import Dict, List, Any, Tuple

class PortfolioCorrelationEngine:
    """
    Berechnet dynamische Korrelationsmatrizen, Stress-Korrelationen
    und steuert das portfolio-weite Klumpenrisiko.
    """

    def __init__(self, window: int = 60, stress_quantile: float = 0.10):
        self.window = window
        self.stress_quantile = stress_quantile
        self.asset_returns: Dict[str, List[float]] = {
            "BTC": [], "ETH": [], "SOL": [], "XRP": []
        }
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

    def get_rolling_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Berechnet die normale rollende Korrelationsmatrix."""
        assets = [a for a in self.asset_returns if len(self.asset_returns[a]) > 5]
        matrix = {a: {b: (1.0 if a == b else 0.5) for b in assets} for a in assets}

        for i, a1 in enumerate(assets):
            for j, a2 in enumerate(assets):
                if i < j:
                    r1 = self.asset_returns[a1]
                    r2 = self.asset_returns[a2]
                    min_len = min(len(r1), len(r2))
                    if min_len >= 10:
                        corr = float(np.corrcoef(r1[-min_len:], r2[-min_len:])[0, 1])
                        corr = 0.0 if np.isnan(corr) else round(corr, 3)
                    else:
                        corr = 0.5
                    matrix[a1][a2] = corr
                    matrix[a2][a1] = corr
        return matrix

    def get_stress_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Berechnet die Tail-Stress-Korrelation (Median der unteren 10 % der Renditen).
        In Krisen schnellt die Korrelation zwischen Krypto-Assets drastisch nach oben.
        """
        assets = [a for a in self.asset_returns if len(self.asset_returns[a]) >= 15]
        matrix = {a: {b: (1.0 if a == b else 0.85) for b in assets} for a in assets}

        for i, a1 in enumerate(assets):
            for j, a2 in enumerate(assets):
                if i < j:
                    r1 = np.array(self.asset_returns[a1])
                    r2 = np.array(self.asset_returns[a2])
                    min_len = min(len(r1), len(r2))
                    r1_trim = r1[-min_len:]
                    r2_trim = r2[-min_len:]

                    # Untere 10% Quantil
                    q1 = np.quantile(r1_trim, self.stress_quantile)
                    q2 = np.quantile(r2_trim, self.stress_quantile)
                    
                    # Stress-Tage: Mindestens eines der Assets befindet sich im Crash
                    stress_mask = (r1_trim <= q1) | (r2_trim <= q2)
                    
                    if np.sum(stress_mask) >= 3:
                        stress_corr = float(np.corrcoef(r1_trim[stress_mask], r2_trim[stress_mask])[0, 1])
                        if np.isnan(stress_corr) or stress_corr < 0.5:
                            stress_corr = 0.85 # Konservativer Stress-Floor
                        else:
                            stress_corr = max(stress_corr, 0.75)
                    else:
                        stress_corr = 0.85
                    
                    matrix[a1][a2] = round(stress_corr, 3)
                    matrix[a2][a1] = round(stress_corr, 3)

        return matrix

    def calculate_portfolio_var_and_es(
        self,
        balances_eur: Dict[str, float],
        confidence: float = 0.99
    ) -> Dict[str, float]:
        """
        Berechnet den 1-Tages Portfolio-VaR und Expected Shortfall (CVaR).
        Nutzt die Tail-Stress-Korrelation, um Klumpenrisiken abzubilden.
        """
        positions = {a: v for a, v in balances_eur.items() if a != "EUR" and v > 0}
        total_crypto_exposure = sum(positions.values())
        if total_crypto_exposure <= 0:
            return {"var_eur": 0.0, "cvar_es_eur": 0.0, "stress_var_eur": 0.0, "exposure_throttle_factor": 1.0}

        assets = list(positions.keys())
        stress_matrix = self.get_stress_correlation_matrix()

        # Einzelvolatilitäten schätzen
        vols = {}
        for a in assets:
            rets = self.asset_returns.get(a, [])
            vols[a] = np.std(rets) if len(rets) >= 10 else 0.045 # 4.5% Standard-Tagesvolatilität

        # Portfoliovarianz mit Stress-Korrelation berechnen: w^T * Sigma * w
        cov_sum = 0.0
        for a1 in assets:
            for a2 in assets:
                w1 = positions[a1]
                w2 = positions[a2]
                s_corr = stress_matrix.get(a1, {}).get(a2, 0.85)
                cov_sum += w1 * w2 * s_corr * vols[a1] * vols[a2]

        portfolio_vol_eur = np.sqrt(max(cov_sum, 0.0))
        z_score = 2.326 if confidence == 0.99 else 1.645

        # Normal VaR
        var_eur = portfolio_vol_eur * z_score
        # Expected Shortfall (CVaR) bei Fat Tails (~1.25 * VaR)
        cvar_es_eur = var_eur * 1.25

        # Stress-Drosselungsfaktor: Wenn Stress-VaR > 10% des Gesamtvermögens, Allokation skalieren
        total_equity = sum(balances_eur.values())
        var_ratio = var_eur / total_equity if total_equity > 0 else 1.0

        throttle_factor = 1.0
        if var_ratio > 0.08:
            throttle_factor = max(0.20, 0.08 / var_ratio)

        return {
            "var_eur": round(var_eur, 2),
            "cvar_es_eur": round(cvar_es_eur, 2),
            "stress_var_eur": round(var_eur * 1.15, 2),
            "portfolio_vol_eur": round(portfolio_vol_eur, 2),
            "exposure_throttle_factor": round(throttle_factor, 2)
        }
