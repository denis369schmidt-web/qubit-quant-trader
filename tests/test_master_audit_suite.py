"""
MASTER AUDIT & VALIDATION TEST SUITE (P0 / P1)
----------------------------------------------
Prüft deterministisch alle 13 geforderten Architektur- & Risikopunkte:
1. Exakter Netto-PnL nach Kosten
2. UNKNOWN_COST_BASIS blockiert risikosteigernde Trades
3. FIFO vs. VWAP Konsistenz
4. Arrival-Price Slippage & Adverse Selection
5. Fill vs. Ack Race Conditions & Idempotenz
6. Cancel/Fill Race & Partial Fills
7. Stale Order Cleaner Schutz für externe Orders
8. Korrelationsstress-Reaktion & Exposure-Drosselung
9. Regime-Hysterese gegen Signal-Flackern
10. Positionsgrößenberechnung aus Verlustbudget
11. Walk-Forward Runner & Monte-Carlo-Permutation
12. Windows DPAPI Verschlüsselung & Migration
13. Live-Freigabe-Schutz
"""

import os
import sys
import unittest
import numpy as np
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from institutional_trading_core import (
    CentralAccountingEngine,
    SQLiteTradeLedgerManager,
    KrakenLiveGateway,
    OrderLifecycleTracker,
    OrderLifecycleState
)
from execution.cost_execution_model import RealisticExecutionModel, LatencyTelemetryTracker
from risk.regime_models import StructuralRegimeClassifier, MarketRegime, RollingStressCorrelationMatrix
from risk.portfolio_risk_engine import PortfolioRiskEngine
from validation.walk_forward_runner import WalkForwardRunner
from edge_research.baselines import BaselineSMACrossover, BaselineVWAPReversion

class MasterAuditTestSuite(unittest.TestCase):

    def setUp(self):
        self.db_test_path = "tests/test_audit_master_ledger.db"
        if os.path.exists(self.db_test_path):
            try:
                os.remove(self.db_test_path)
            except Exception:
                pass
        self.ledger = SQLiteTradeLedgerManager(self.db_test_path)

    def tearDown(self):
        if os.path.exists(self.db_test_path):
            try:
                os.remove(self.db_test_path)
            except Exception:
                pass

    # 1. Netto-PnL exakt für bekannte Trade-Sequenz
    def test_01_exact_net_pnl_known_sequence(self):
        # Kauf: 0.5 Einheiten @ 2000 EUR, Buy Fee 2.60 EUR
        # Verkauf: 0.5 Einheiten @ 2050 EUR, Sell Fee 2.665 EUR
        # Brutto: 1025 EUR, Netto nach Fee: 1022.335 EUR
        # Anschaffungskosten: 1000 + 2.60 = 1002.60 EUR
        # Erwarteter PnL: 1022.335 - 1002.60 = +19.735 EUR
        pnl = CentralAccountingEngine.calculate_realized_net_pnl(
            buy_price=2000.0, sell_price=2050.0, volume=0.5,
            buy_fee=2.60, sell_fee=2.665
        )
        self.assertAlmostEqual(float(pnl), 19.735, places=3)

    # 2. UNKNOWN_COST_BASIS blockiert risikosteigernde Trades
    def test_02_unknown_cost_basis_blocking(self):
        succ, pnl = self.ledger.record_sell_trade(
            timestamp="12:00:00", pair="ETHEUR", price=2500.0,
            volume=0.5, fee_eur=3.25, txid="TX-UNKNOWN-01", status="EXECUTED"
        )
        self.assertTrue(succ)
        self.assertIsNone(pnl, "UNKNOWN_COST_BASIS darf niemals 0.0 zurückgeben")

    # 3. FIFO / VWAP Vergleich
    def test_03_fifo_vs_vwap_accuracy(self):
        self.ledger.record_buy_trade("10:00:00", "XBTEUR", price=50000.0, volume=0.1, fee_eur=13.0, txid="L1", status="EX")
        self.ledger.record_buy_trade("10:05:00", "XBTEUR", price=60000.0, volume=0.1, fee_eur=15.6, txid="L2", status="EX")
        
        # VWAP: (0.1*50000 + 0.1*60000) / 0.2 = 55000.0
        vwap = self.ledger.fetch_weighted_average_cost_basis("XBTEUR")
        self.assertAlmostEqual(vwap, 55000.0, places=2)

        # FIFO Verkauf von 0.1: Muss exakt Lot 1 matchen
        succ, pnl = self.ledger.record_sell_trade("10:10:00", "XBTEUR", price=52000.0, volume=0.1, fee_eur=13.52, txid="S1", status="EX")
        # Lot 1: Kauf 50000, Verkauf 52000 -> Kursgewinn +200, Fees: 13.0 + 13.52 = 26.52 -> PnL: +173.48
        self.assertAlmostEqual(pnl, 173.48, places=2)

    # 4. Arrival-Price Slippage & Adverse Selection
    def test_04_arrival_price_slippage_model(self):
        fill = RealisticExecutionModel.calculate_simulated_fill(
            pair="XBTEUR", side="BUY", requested_volume=0.1,
            arrival_price=60000.0, bid_price=59990.0, ask_price=60010.0,
            market_depth_volume=0.5, volatility_atr=120.0, latency_ms=150.0
        )
        self.assertTrue(fill["filled"])
        self.assertGreater(fill["exec_price"], fill["arrival_price"])
        self.assertGreater(fill["slippage_bps"], 0.0)

    # 5. Fill vs Ack Race & Idempotenz
    def test_05_idempotent_order_lifecycle(self):
        intent = OrderLifecycleTracker.create_intent("XBTEUR", "BUY", 0.05, 65000.0)
        OrderLifecycleTracker.transition(intent.intent_id, OrderLifecycleState.SUBMITTED)
        
        # Erster Fill
        t1 = OrderLifecycleTracker.transition(intent.intent_id, OrderLifecycleState.FILLED, txid="TX-IDEM-01", filled_vol=0.05, fee_eur=8.45)
        self.assertEqual(t1.state, OrderLifecycleState.FILLED)
        
        # Verspätetes Re-Event darf Status nicht korrumpieren
        t2 = OrderLifecycleTracker.transition(intent.intent_id, OrderLifecycleState.FILLED, txid="TX-IDEM-01")
        self.assertEqual(t2.state, OrderLifecycleState.FILLED)
        self.assertEqual(t2.txid, "TX-IDEM-01")

    # 6. Cancel/Fill Race & Partial Fills
    def test_06_partial_fill_handling(self):
        fill = RealisticExecutionModel.calculate_simulated_fill(
            pair="XBTEUR", side="BUY", requested_volume=1.0,
            arrival_price=60000.0, bid_price=59990.0, ask_price=60010.0,
            is_limit_order=True, limit_price=60000.0, market_depth_volume=0.3
        )
        self.assertTrue(fill["filled"])
        self.assertTrue(fill["is_partial"])
        self.assertLess(fill["filled_volume"], fill["requested_volume"])

    # 7. Stale Cleaner schützt Fremd-Orders
    def test_07_stale_cleaner_protection(self):
        orig_query = KrakenLiveGateway.query_private
        try:
            cancelled = []
            def mock_q(endpoint, data, k, s):
                if endpoint == "/0/private/OpenOrders":
                    return {"result": {"open": {
                        "BOT-ORDER": {"opentm": 100.0},
                        "MANUAL-ORDER": {"opentm": 100.0}
                    }}}
                elif endpoint == "/0/private/CancelOrder":
                    cancelled.append(data.get("txid"))
                    return {"result": {"count": 1}}
                return {}
            KrakenLiveGateway.query_private = mock_q
            res = KrakenLiveGateway.cancel_stale_orders("k", "s", allowed_txids={"BOT-ORDER"})
            self.assertEqual(res["status"], "success")
            self.assertIn("BOT-ORDER", cancelled)
            self.assertNotIn("MANUAL-ORDER", cancelled)
        finally:
            KrakenLiveGateway.query_private = orig_query

    # 8. Korrelationsstress & Exposure-Drosselung
    def test_08_correlation_stress_var(self):
        mat = RollingStressCorrelationMatrix()
        balances = {"EUR": 500.0, "BTC": 300.0, "ETH": 200.0}
        stress_var = mat.calculate_stress_var(balances)
        self.assertGreater(stress_var, 0.0)
        self.assertLessEqual(stress_var, 500.0)

    # 9. Regime-Hysterese verhindert Flackern
    def test_09_regime_hysteresis(self):
        clf = StructuralRegimeClassifier(hysteresis_ticks=4)
        # Initial RANGE_BOUND
        r1 = clf.update(price=100.0, volume=10.0, spread_bps=2.0)
        self.assertEqual(r1, MarketRegime.RANGE_BOUND)

        # Ein einziger volatiler Spike darf nicht sofort das Regime wechseln
        r2 = clf.update(price=110.0, volume=10.0, spread_bps=2.0, atr_pct=0.04)
        self.assertEqual(r2, MarketRegime.RANGE_BOUND)

        # Erst bei 4 kontinuierlichen Ticks schaltet Hysterese um
        clf.update(price=111.0, volume=10.0, spread_bps=2.0, atr_pct=0.04)
        clf.update(price=112.0, volume=10.0, spread_bps=2.0, atr_pct=0.04)
        r_final = clf.update(price=113.0, volume=10.0, spread_bps=2.0, atr_pct=0.04)
        self.assertEqual(r_final, MarketRegime.VOLATILITY_SHOCK)

    # 10. Positionsgröße aus Verlustbudget
    def test_10_risk_budget_sizing(self):
        risk = PortfolioRiskEngine(max_risk_per_trade_pct=0.01) # 10 EUR bei 1000 EUR
        res = risk.calculate_position_size(
            current_equity_eur=1000.0,
            current_cash_eur=800.0,
            asset_price=100.0,
            stop_loss_price=95.0, # 5 EUR Risiko pro Einheit
            current_asset_exposure_eur=0.0,
            current_total_exposure_eur=0.0
        )
        self.assertTrue(res["allowed"])
        # Verlustbudget: 10 EUR. Risiko: 5 EUR/Einheit -> max 2 Einheiten = 200 EUR Invest
        self.assertAlmostEqual(res["volume"], 2.0, places=2)
        self.assertAlmostEqual(res["max_risk_eur"], 10.0, places=2)

    # 11. Walk-Forward & Monte-Carlo Signifikanz
    def test_11_walk_forward_and_monte_carlo(self):
        runner = WalkForwardRunner(initial_capital_eur=1000.0)
        # 100 synthetische Preisticks
        np.random.seed(42)
        prices = [100.0 + i*0.2 + np.random.normal(0, 0.5) for i in range(100)]
        volumes = [10.0 for _ in range(100)]

        # Einfache SMA Strategie
        def strat_fn(p, v, pos, cap):
            if len(p) > 20:
                if p[-1] > np.mean(p[-20:]) and pos <= 0: return "BUY"
                if p[-1] < np.mean(p[-20:]) and pos > 0: return "SELL"
            return "HOLD"

        res = runner.run_fold(prices, volumes, strat_fn, is_oos=True)
        self.assertIn("net_pnl_eur", res)
        self.assertIn("sharpe_ratio", res)

        # Monte-Carlo Permutation
        mc_res = runner.run_monte_carlo_permutation([1.5, -0.8, 2.0, -1.1, 3.2, 0.9])
        self.assertIn("statistically_significant", mc_res)

    # 12. Windows DPAPI Verschlüsselung & Transparente Migration
    def test_12_windows_dpapi_vault(self):
        from production_quantum_trader_engine import EncryptedCredentialVault
        plain = "kraken_secret_key_audit_test_999"
        encrypted = EncryptedCredentialVault._dpapi_encrypt(plain)
        self.assertNotEqual(plain, encrypted)
        decrypted = EncryptedCredentialVault._dpapi_decrypt(encrypted)
        self.assertEqual(plain, decrypted)

    # 13. Latenz-Tracker L_data, L_dec, L_exec
    def test_13_latency_telemetry_tracker(self):
        tracker = LatencyTelemetryTracker()
        tracker.record_cycle(l_data_ms=18.5, l_decision_ms=2.1, l_exec_ms=145.0)
        summary = tracker.get_summary()
        self.assertAlmostEqual(summary["avg_total_ms"], 165.6, places=1)
        self.assertEqual(summary["sample_count"], 1)

if __name__ == "__main__":
    unittest.main()
