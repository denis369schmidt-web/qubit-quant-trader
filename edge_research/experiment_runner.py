"""
EXPERIMENT-RUNNER FÜR DIE 5 START-HYPOTHESEN (H1 - H5)
------------------------------------------------------
Führt standardisierte Walk-Forward- und Out-of-Sample-Validierungen
mit echtem Kostenmodell (Maker/Taker, Slippage, Spread) durch.
"""

import math
import numpy as np
from typing import Dict, List, Any
from execution.cost_execution_model import RealisticExecutionModel
from validation.walk_forward_runner import WalkForwardRunner
from risk.regime_models import StructuralRegimeClassifier, MarketRegime

class HypothesisExperimentRunner:
    """Führt standardisierte Tests für H1 bis H5 durch."""

    def __init__(self, initial_capital_eur: float = 1000.0):
        self.initial_capital = initial_capital_eur
        self.runner = WalkForwardRunner(initial_capital_eur=initial_capital_eur)

    # --- H1: Trend-Quality-Continuation ---
    def run_h1_trend_quality(self, prices: List[float], volumes: List[float]) -> Dict[str, Any]:
        """Kauft nur bei nachgewiesener Trendqualität (Effizienz > 0.55 & über 20 SMA)."""
        def strat(p_hist, v_hist, pos, cap):
            if len(p_hist) < 30:
                return "HOLD"
            p = np.array(p_hist[-30:])
            efficiency = abs(p[-1] - p[0]) / max(np.sum(np.abs(np.diff(p))), 1e-6)
            sma = np.mean(p[-20:])
            # Nur bei echtem Trend einsteigen
            if efficiency > 0.55 and p[-1] > sma and pos <= 0:
                return "BUY"
            elif p[-1] < sma and pos > 0:
                return "SELL"
            return "HOLD"

        return self.runner.run_fold(prices, volumes, strat, is_oos=True)

    # --- H2: Mean-Reversion nach Erschöpfung ---
    def run_h2_mean_reversion(self, prices: List[float], volumes: List[float]) -> Dict[str, Any]:
        """Kauft bei > 2.5 StdAbw Auslenkung und abnehmendem Volumen."""
        def strat(p_hist, v_hist, pos, cap):
            if len(p_hist) < 30:
                return "HOLD"
            p = np.array(p_hist[-30:])
            v = np.array(v_hist[-30:])
            mean_p = np.mean(p)
            std_p = np.std(p)
            avg_v = np.mean(v)
            # Reversion nur wenn Volumen abnimmt (Erschöpfung)
            if p[-1] < mean_p - 2.2 * std_p and v[-1] < avg_v and pos <= 0:
                return "BUY"
            elif p[-1] >= mean_p and pos > 0:
                return "SELL"
            return "HOLD"

        return self.runner.run_fold(prices, volumes, strat, is_oos=True)

    # --- H3: Cross-Asset Lead-Lag ---
    def run_h3_lead_lag(self, btc_prices: List[float], alt_prices: List[float], volumes: List[float]) -> Dict[str, Any]:
        """Handelt Altcoin basierend auf verzögertem BTC-Impuls."""
        def strat(p_hist, v_hist, pos, cap):
            idx = len(p_hist) - 1
            if idx < 10:
                return "HOLD"
            btc_ret = (btc_prices[idx-1] - btc_prices[idx-4]) / btc_prices[idx-4]
            alt_ret = (alt_prices[idx] - alt_prices[idx-3]) / alt_prices[idx-3]
            # Wenn BTC stark gestiegen, Alt aber hinterherhinkt
            if btc_ret > 0.008 and alt_ret < 0.002 and pos <= 0:
                return "BUY"
            elif pos > 0 and (alt_ret > 0.008 or btc_ret < -0.004):
                return "SELL"
            return "HOLD"

        return self.runner.run_fold(alt_prices, volumes, strat, is_oos=True)

    # --- H4: Intraday-Mikrostruktur (OBI & CVD) ---
    def run_h4_microstructure(self, prices: List[float], volumes: List[float], obis: List[float]) -> Dict[str, Any]:
        """Nutzt Orderbook Imbalance (OBI) für Einstiege."""
        def strat(p_hist, v_hist, pos, cap):
            idx = len(p_hist) - 1
            if idx < 5:
                return "HOLD"
            obi = obis[idx]
            if obi > 0.20 and pos <= 0:
                return "BUY"
            elif obi < -0.15 and pos > 0:
                return "SELL"
            return "HOLD"

        return self.runner.run_fold(prices, volumes, strat, is_oos=True)
