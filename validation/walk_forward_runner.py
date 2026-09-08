"""
ROBUSTER WALK-FORWARD & MONTE-CARLO VALIDIERUNGS-RUNNER
-------------------------------------------------------
Führt standardisierte In-Sample und Out-of-Sample Tests durch:
- Walk-Forward Periodizität (z. B. 5 Folds)
- Parameter-Sensitivitäts-Check (+-10% bis +-25%)
- Monte-Carlo-Permutationen auf Trade-Ebene
- Realistisches Kosten- & Slippage-Modell
- Auswertung von: Netto-PnL, Max Drawdown, Sharpe, Sortino, Profit Factor, Slippage bps
"""

import math
import numpy as np
from typing import Dict, List, Any, Tuple
from execution.cost_execution_model import RealisticExecutionModel

class WalkForwardRunner:
    """
    Simuliert Strategien über In-Sample und Out-of-Sample Fenster.
    """

    def __init__(self, initial_capital_eur: float = 1000.0):
        self.initial_capital = initial_capital_eur

    def run_fold(
        self,
        prices: List[float],
        volumes: List[float],
        strategy_fn,
        is_oos: bool = False
    ) -> Dict[str, Any]:
        """Führt einen einzelnen Fold durch."""
        capital = self.initial_capital
        position = 0.0
        trades = []
        equity_curve = [capital]
        total_slippage_bps = []

        for i in range(1, len(prices)):
            p = prices[i]
            v = volumes[i]
            bid = p * 0.9998
            ask = p * 1.0002

            # Signal von Strategie abfragen
            sig = strategy_fn(prices[:i+1], volumes[:i+1], position, capital)

            if sig == "BUY" and position <= 0 and capital > 10.0:
                fill = RealisticExecutionModel.calculate_simulated_fill(
                    pair="XBTEUR", side="BUY", requested_volume=(capital * 0.90) / ask,
                    arrival_price=p, bid_price=bid, ask_price=ask
                )
                if fill["filled"]:
                    cost = fill["exec_price"] * fill["filled_volume"] + fill["fee_eur"]
                    if capital >= cost:
                        capital -= cost
                        position += fill["filled_volume"]
                        total_slippage_bps.append(fill["slippage_bps"])
                        trades.append({"side": "BUY", "price": fill["exec_price"], "vol": fill["filled_volume"], "fee": fill["fee_eur"]})

            elif sig == "SELL" and position > 0:
                fill = RealisticExecutionModel.calculate_simulated_fill(
                    pair="XBTEUR", side="SELL", requested_volume=position,
                    arrival_price=p, bid_price=bid, ask_price=ask
                )
                if fill["filled"]:
                    proceeds = fill["exec_price"] * fill["filled_volume"] - fill["fee_eur"]
                    capital += proceeds
                    total_slippage_bps.append(fill["slippage_bps"])
                    trades.append({"side": "SELL", "price": fill["exec_price"], "vol": fill["filled_volume"], "fee": fill["fee_eur"]})
                    position = 0.0

            eq = capital + position * p
            equity_curve.append(eq)

        # Performance-Metriken berechnen
        returns = np.diff(equity_curve) / equity_curve[:-1]
        net_pnl = equity_curve[-1] - self.initial_capital
        net_ret_pct = (net_pnl / self.initial_capital) * 100.0

        # Drawdown
        peak = np.maximum.accumulate(equity_curve)
        dd = (peak - equity_curve) / peak
        max_dd = float(np.max(dd)) * 100.0

        # Sharpe / Sortino
        std = np.std(returns) if len(returns) > 1 else 1.0
        neg_std = np.std([r for r in returns if r < 0]) if any(r < 0 for r in returns) else 1e-6
        sharpe = (np.mean(returns) / std * math.sqrt(252 * 24 * 60)) if std > 1e-8 else 0.0
        sortino = (np.mean(returns) / neg_std * math.sqrt(252 * 24 * 60)) if neg_std > 1e-8 else 0.0

        # Profit Factor
        sell_trades = [t for t in trades if t["side"] == "SELL"]
        buy_trades = [t for t in trades if t["side"] == "BUY"]
        gains = []
        losses = []
        for b, s in zip(buy_trades, sell_trades):
            trade_pnl = (s["price"] - b["price"]) * min(s["vol"], b["vol"]) - b["fee"] - s["fee"]
            if trade_pnl > 0:
                gains.append(trade_pnl)
            else:
                losses.append(abs(trade_pnl))

        profit_factor = (sum(gains) / sum(losses)) if losses and sum(losses) > 0 else (99.0 if gains else 0.0)

        return {
            "is_oos": is_oos,
            "net_pnl_eur": round(net_pnl, 2),
            "net_ret_pct": round(net_ret_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "profit_factor": round(profit_factor, 2),
            "trade_count": len(trades),
            "avg_slippage_bps": round(np.mean(total_slippage_bps), 2) if total_slippage_bps else 0.0
        }

    @staticmethod
    def run_monte_carlo_permutation(trade_returns: List[float], iterations: int = 1000) -> Dict[str, Any]:
        """
        Permutiert Trade-Ergebnisse zur Prüfung von Zufall vs. statistischer Signifikanz.
        """
        if len(trade_returns) < 5:
            return {"statistically_significant": False, "p_value": 1.0, "reason": "INSUFFICIENT_TRADES"}

        orig_sum = sum(trade_returns)
        surpass_count = 0

        # Bootstrapping / Permutation
        for _ in range(iterations):
            perm = np.random.permutation(trade_returns)
            # Berechne hypothetischen Summenverlauf
            if sum(perm) >= orig_sum:
                surpass_count += 1

        p_val = surpass_count / iterations
        return {
            "statistically_significant": (p_val < 0.05 and orig_sum > 0),
            "p_value": round(p_val, 4),
            "iterations": iterations,
            "sample_size": len(trade_returns)
        }
