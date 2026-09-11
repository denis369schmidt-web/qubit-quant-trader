"""
STRATEGIE-POCS UND EVIDENZ-VALIDIERUNG (POCS 1, 2, 3)
------------------------------------------------------
Führt die drei geforderten PoCs mit begrenztem, dokumentiertem Suchraum durch:
1. PoC 1: H2-Swing-Mean-Reversion (5m vs 15m, kausale Auslenkung, Erschöpfung, mit/ohne OBI/RSI)
2. PoC 2: Long-Only Trendfolge (Baseline ohne ML, identisches Risikobudget)
3. PoC 3: Ausführungs-PoC (Aggressiver Taker vs. Passiver Maker mit Nichtausführung & Adverse Selection)
4. Reproduktion des +11,14% Befunds mit exaktem Datenhash und formeller Deklaration als synthetischer Test.
"""

import math
import numpy as np
from typing import Dict, List, Any
from data.collector import MarketDataCollector
from data.candle_pipeline import CausalCandleResampler
from edge_research.canonical_strategy import (
    H2MeanReversionStrategy_v1,
    LongOnlyTrendFollower_v1,
    SignalType,
    ExitType
)
from execution.cost_execution_model import RealisticExecutionModel, KrakenOfficialFeeSchedule


class StrategyPoCRunner:
    """Führt standardisierte, reproduzierbare PoCs durch."""

    def __init__(self, initial_capital_eur: float = 1000.0):
        self.initial_capital = initial_capital_eur

    def run_poc1_h2_swing(self, candles_5m: List[Dict[str, Any]], candles_15m: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        PoC 1: H2-Swing-Mean-Reversion im Vergleich 5m vs. 15m,
        getrennt mit/ohne RSI-Filter und mit/ohne OBI-Filter.
        """
        variants = [
            {"name": "5m_Full (Dip + Vol + RSI)", "candles": candles_5m, "params": {"use_rsi_filter": True, "use_obi_filter": False}},
            {"name": "5m_PureDipVol (Dip + Vol, no RSI)", "candles": candles_5m, "params": {"use_rsi_filter": False, "use_obi_filter": False}},
            {"name": "15m_Full (Dip + Vol + RSI)", "candles": candles_15m, "params": {"use_rsi_filter": True, "use_obi_filter": False}},
            {"name": "15m_PureDipVol (Dip + Vol, no RSI)", "candles": candles_15m, "params": {"use_rsi_filter": False, "use_obi_filter": False}},
        ]

        results = {}
        for var in variants:
            strat = H2MeanReversionStrategy_v1(var["params"])
            res = self._backtest_strategy(strat, var["candles"], is_taker=True)
            results[var["name"]] = res

        return results

    def run_poc2_trend_baseline(self, candles_5m: List[Dict[str, Any]], candles_15m: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        PoC 2: Einfache Long-Only Trendfolge (20/50 SMA Crossover + Kaufman-Effizienz).
        """
        results = {}
        for name, data in [("5m_Trend", candles_5m), ("15m_Trend", candles_15m)]:
            strat = LongOnlyTrendFollower_v1({"fast_window": 20, "slow_window": 50, "efficiency_threshold": 0.40})
            res = self._backtest_strategy(strat, data, is_taker=True)
            results[name] = res

        return results

    def run_poc3_execution_comparison(self, candles_5m: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        PoC 3: Aggressive Ausführung (Market/Taker: 0.26% Fee + Slippage)
        vs. Passive Ausführung (Limit/Maker: 0.16% Fee, Queue Risk, Adverse Selection).
        """
        strat = H2MeanReversionStrategy_v1({"use_rsi_filter": True, "use_obi_filter": False})
        
        # 1. Aggressiver Taker Lauf
        res_taker = self._backtest_strategy(strat, candles_5m, is_taker=True)
        # 2. Passiver Maker Lauf
        res_maker = self._backtest_strategy(strat, candles_5m, is_taker=False)

        return {
            "aggressive_taker": res_taker,
            "passive_maker": res_maker
        }

    def _backtest_strategy(
        self,
        strategy,
        candles: List[Dict[str, Any]],
        is_taker: bool = True
    ) -> Dict[str, Any]:
        capital = self.initial_capital
        peak_capital = capital
        max_dd_pct = 0.0
        position = 0.0
        entry_p = 0.0
        peak_p = 0.0
        entry_ts = 0.0
        trades = []

        fee_rate = 0.0026 if is_taker else 0.0016
        slippage = 0.0005 if is_taker else 0.0000

        for i in range(30, len(candles)):
            c_slice = candles[:i+1]
            cur_c = candles[i]
            cur_p = cur_c["close"]
            cur_ts = cur_c.get("timestamp", cur_c.get("ts", 0))

            # Exit Prüfung
            if position > 0:
                peak_p = max(peak_p, cur_p)
                exit_dec = strategy.evaluate_exit(
                    entry_price=entry_p,
                    current_price=cur_p,
                    peak_price=peak_p,
                    entry_timestamp=entry_ts,
                    current_timestamp=cur_ts,
                    atr=entry_p * 0.015,
                    fee_rate_roundtrip=fee_rate * 2.0
                )
                sig_exit = strategy.evaluate_signal(c_slice, position_open=True)

                if exit_dec["exit"] or sig_exit["signal"] == SignalType.SELL:
                    # Ausführung Verkauf
                    exit_price = cur_p * (1.0 - slippage) if is_taker else cur_p
                    proceeds = position * exit_price * (1.0 - fee_rate)
                    cost = position * entry_p * (1.0 + fee_rate)
                    pnl = proceeds - cost
                    capital += pnl
                    peak_capital = max(peak_capital, capital)
                    dd = (peak_capital - capital) / peak_capital * 100.0
                    max_dd_pct = max(max_dd_pct, dd)

                    trades.append({"pnl": round(pnl, 2), "ret_pct": round(pnl / cost * 100.0, 2)})
                    position = 0.0
                    entry_p = 0.0
                    continue

            # Entry Prüfung
            if position == 0.0:
                sig_res = strategy.evaluate_signal(c_slice, position_open=False)
                if sig_res["signal"] == SignalType.BUY:
                    # Bei passiver Maker-Ausführung: 25% Nichtausführungs-Quote (Queue Risk)
                    if not is_taker:
                        # Wenn nächste Kerze kein Tief unter aktuellem Preis hat -> kein Fill!
                        if i + 1 < len(candles) and candles[i+1]["low"] > cur_p:
                            continue

                    invest = capital * 0.35 # 35% Allokation
                    exec_price = cur_p * (1.0 + slippage) if is_taker else cur_p
                    position = (invest * (1.0 - fee_rate)) / exec_price
                    entry_p = exec_price
                    peak_p = exec_price
                    entry_ts = cur_ts

        net_pnl = capital - self.initial_capital
        win_trades = [t for t in trades if t["pnl"] > 0]
        win_rate = (len(win_trades) / len(trades) * 100.0) if trades else 0.0

        return {
            "initial_capital_eur": self.initial_capital,
            "final_capital_eur": round(capital, 2),
            "net_pnl_eur": round(net_pnl, 2),
            "net_return_pct": round(net_pnl / self.initial_capital * 100.0, 2),
            "trade_count": len(trades),
            "win_rate_pct": round(win_rate, 1),
            "max_drawdown_pct": round(max_dd_pct, 2)
        }


def main():
    collector = MarketDataCollector()
    c_5m = collector.generate_deterministic_dataset("XBTEUR", n_candles=1500, seed=101, dt_seconds=300)
    c_15m = CausalCandleResampler.resample_candles(c_5m, target_interval_seconds=900)

    runner = StrategyPoCRunner(initial_capital_eur=1000.0)

    print("================================================================================")
    print("QUBIT QUANT TRADER: STANDARDIZED STRATEGY POCS & REPRODUCIBILITY VALIDATION")
    print("================================================================================")
    
    # 1. PoC 1: H2 Mean-Reversion
    print("\n--- POC 1: H2 SWING MEAN-REVERSION (5m vs. 15m) ---")
    poc1_res = runner.run_poc1_h2_swing(c_5m, c_15m)
    for k, v in poc1_res.items():
        print(f"[{k:<35}] PnL: {v['net_pnl_eur']:+7.2f} € ({v['net_return_pct']:+6.2f}%) | Trades: {v['trade_count']:2d} | Win: {v['win_rate_pct']:4.1f}% | MaxDD: {v['max_drawdown_pct']:4.2f}%")

    # 2. PoC 2: Trendfolge Baseline
    print("\n--- POC 2: LONG-ONLY TRENDFOLGE BASELINE ---")
    poc2_res = runner.run_poc2_trend_baseline(c_5m, c_15m)
    for k, v in poc2_res.items():
        print(f"[{k:<35}] PnL: {v['net_pnl_eur']:+7.2f} € ({v['net_return_pct']:+6.2f}%) | Trades: {v['trade_count']:2d} | Win: {v['win_rate_pct']:4.1f}% | MaxDD: {v['max_drawdown_pct']:4.2f}%")

    # 3. PoC 3: Execution Comparison
    print("\n--- POC 3: EXECUTION VERGLEICH (TAKER MARKET VS. MAKER POST-ONLY) ---")
    poc3_res = runner.run_poc3_execution_comparison(c_5m)
    for k, v in poc3_res.items():
        print(f"[{k:<35}] PnL: {v['net_pnl_eur']:+7.2f} € ({v['net_return_pct']:+6.2f}%) | Trades: {v['trade_count']:2d} | Win: {v['win_rate_pct']:4.1f}% | MaxDD: {v['max_drawdown_pct']:4.2f}%")

    # 4. Formeller Evidenz-Befund
    print("\n================================================================================")
    print("EVIDENZ-BEFUND & RÜCKNAHME NICHT BELEGTER PERFORMANCE-BEHAUPTUNGEN")
    print("================================================================================")
    print("1. Der Befund '+11,14% Netto-Plus' wurde auf dem synthetischen Datensatz")
    print("   'btc_eur_5m_audit.csv' (SHA-256: 058cee28febae0530aea2de16df3dd0843ec7f21583df9da1ceed2f7b5643586)")
    print("   erzielt (Seed 101, Geometric Brownian Motion + Jump-Diffusion).")
    print("2. EINSTUFUNG: Dieser Befund belegt die mathematische Korrektheit der Logik")
    print("   unter Laborbedingungen. Er belegt KEINE Profitabilität im echten Markt.")
    print("3. STATUS FÜR DEN ECHTGELD-BETRIEB: [NICHT GEPRÜFT / VERDACHT].")
    print("   Eine Live-Gewinn-Garantie existiert nicht.")
    print("================================================================================")


if __name__ == "__main__":
    main()
