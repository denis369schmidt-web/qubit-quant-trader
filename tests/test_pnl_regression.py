"""
SYNTHETISCHE REGRESSIONSTEST-SUITE: FINANZ-BUCHHALTUNG & PNL-VALIDIERUNG
"""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from institutional_trading_core import (
    CentralAccountingEngine,
    OrderLifecycleTracker,
    OrderLifecycleState,
    SQLiteTradeLedgerManager,
    MultiAssetWalletAllocator
)

class TestPnLRegression(unittest.TestCase):

    def setUp(self):
        self.db_test_path = "tests/test_regression_ledger.db"
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

    def test_case_a_eth_flat_price(self):
        """Fall A (ETH Trades #97 & #98)"""
        pnl = CentralAccountingEngine.calculate_realized_net_pnl(
            buy_price=2491.30,
            sell_price=2491.30,
            volume=0.001050,
            buy_fee=0.0068,
            sell_fee=0.0068
        )
        self.assertAlmostEqual(float(pnl), -0.013600, places=6)
        self.assertLess(float(pnl), 0.0)

    def test_case_b_sol_loss(self):
        """Fall B (SOL Trades #94 & #96)"""
        pnl = CentralAccountingEngine.calculate_realized_net_pnl(
            buy_price=103.82,
            sell_price=103.76,
            volume=0.063000,
            buy_fee=0.0170,
            sell_fee=0.0170
        )
        self.assertAlmostEqual(float(pnl), -0.037780, places=6)

    def test_case_c_sol_sub_fee_gain(self):
        """Fall C (SOL Trades #82 & #86)"""
        pnl = CentralAccountingEngine.calculate_realized_net_pnl(
            buy_price=103.83,
            sell_price=103.84,
            volume=0.063000,
            buy_fee=0.0170,
            sell_fee=0.0170
        )
        self.assertAlmostEqual(float(pnl), -0.033370, places=6)
        self.assertLess(float(pnl), 0.0)

    def test_case_d_sol_flat_fee(self):
        """Fall D (SOL Trades #61 & #64)"""
        pnl = CentralAccountingEngine.calculate_realized_net_pnl(
            buy_price=103.86,
            sell_price=103.86,
            volume=0.074700,
            buy_fee=0.0202,
            sell_fee=0.0202
        )
        self.assertAlmostEqual(float(pnl), -0.040400, places=6)

    def test_fifo_partial_lot_closing(self):
        """Testet FIFO-Matching über Teillose"""
        open_lots = [
            {
                "lot_id": "LOT-1",
                "entry_price": 100.0,
                "original_volume": 1.0,
                "volume_remaining": 1.0,
                "fee_allocated": 0.26
            },
            {
                "lot_id": "LOT-2",
                "entry_price": 110.0,
                "original_volume": 1.0,
                "volume_remaining": 1.0,
                "fee_allocated": 0.286
            }
        ]
        sell_res = CentralAccountingEngine.match_fifo_lots(
            open_lots=open_lots,
            sell_volume=1.5,
            sell_price=120.0,
            sell_fee=0.468
        )
        self.assertEqual(sell_res["status"], "RECONCILED")
        self.assertEqual(len(sell_res["remaining_lots"]), 1)
        self.assertAlmostEqual(sell_res["remaining_lots"][0]["volume_remaining"], 0.5)
        self.assertAlmostEqual(float(sell_res["gross_proceeds"]), 180.0, places=4)
        self.assertAlmostEqual(float(sell_res["allocated_cost_basis"]), 155.0, places=4)
        self.assertAlmostEqual(float(sell_res["allocated_buy_fee"]), 0.403, places=4)
        self.assertAlmostEqual(float(sell_res["net_pnl"]), 24.129, places=3)

    def test_unknown_cost_basis_rejection(self):
        """Verhindert fiktive Gewinne bei unbekanntem Anschaffungspreis"""
        open_lots = []
        sell_res = CentralAccountingEngine.match_fifo_lots(
            open_lots=open_lots,
            sell_volume=0.5,
            sell_price=100.0,
            sell_fee=0.13
        )
        self.assertEqual(sell_res["status"], "UNKNOWN_COST_BASIS")
        self.assertIsNone(sell_res["net_pnl"])
        self.assertIsNone(sell_res["allocated_cost_basis"])

    def test_ledger_database_persistence_fifo(self):
        """Testet Speicherung in SQLite"""
        succ_buy = self.ledger.record_buy_trade(
            timestamp="12:00:00",
            pair="ETHEUR",
            price=2500.0,
            volume=0.1,
            fee_eur=0.65,
            txid="TX-ETH-BUY-1",
            status="EXECUTED"
        )
        self.assertTrue(succ_buy)

        open_lots = self.ledger.fetch_open_lots("ETHEUR")
        self.assertEqual(len(open_lots), 1)

        succ_sell, pnl = self.ledger.record_sell_trade(
            timestamp="12:05:00",
            pair="ETHEUR",
            price=2600.0,
            volume=0.1,
            fee_eur=0.676,
            txid="TX-ETH-SELL-1",
            status="EXECUTED"
        )
        self.assertTrue(succ_sell)
        self.assertIsNotNone(pnl)
        self.assertAlmostEqual(pnl, 8.674, places=3)

    def test_order_lifecycle_state_machine(self):
        """Testet Zustandsübergänge"""
        intent = OrderLifecycleTracker.create_intent(
            pair="XBTEUR",
            side="BUY",
            volume=0.0001,
            price=75000.0
        )
        self.assertEqual(intent.state, OrderLifecycleState.INTENT_CREATED)

        OrderLifecycleTracker.transition(intent.intent_id, OrderLifecycleState.SUBMITTED)
        updated = OrderLifecycleTracker.get_intent(intent.intent_id)
        self.assertEqual(updated.state, OrderLifecycleState.SUBMITTED)

        OrderLifecycleTracker.transition(intent.intent_id, OrderLifecycleState.FILLED, txid="TX-KRAKEN-123", filled_vol=0.0001, fee_eur=0.0195)
        filled = OrderLifecycleTracker.get_intent(intent.intent_id)
        self.assertEqual(filled.state, OrderLifecycleState.FILLED)

    def test_exit_gating_blocks_unprofitable_sale(self):
        """Stellt sicher, dass kein unprofitable PROFIT_EXIT getriggert wird"""
        balances = {"EUR": 50.0, "ETH": 0.05, "BTC": 0.0, "XRP": 0.0, "SOL": 0.0}
        asset_signals = {"ETH": "SELL", "BTC": "HOLD", "XRP": "HOLD", "SOL": "HOLD"}
        entry_prices = {"ETH": 2500.0}
        live_prices = {"ETH": 2502.0}

        orders = MultiAssetWalletAllocator.evaluate_multi_asset_opportunities(
            balances=balances,
            asset_signals=asset_signals,
            live_prices=live_prices,
            entry_prices=entry_prices
        )
        profit_exits = [o for o in orders if o.get("exit_type") == "PROFIT_EXIT"]
        self.assertEqual(len(profit_exits), 0)

    # ---------------------------------------------------------------
    # PFLICHT-TESTFALL AUS DER SPEZIFIKATION (Sektion 2, P0-Niveau)
    # Kauf 1 Einheit @ 100 EUR, Kaufgebühr 0,26 EUR.
    # Verkauf 1 Einheit @ 100,40 EUR, Verkaufsgebühr 0,26104 EUR.
    # Erwarteter Netto-PnL: -0,12104 EUR.
    # ---------------------------------------------------------------
    def test_spec_mandatory_pnl_calculation(self):
        """Pflicht-Testfall aus der Spezifikation P0-Sektion 2.
        Kauf 1 Einheit @ 100 EUR, Kaufgebühr 0,26 EUR.
        Verkauf 1 Einheit @ 100,40 EUR, Verkaufsgebühr 0,26104 EUR.
        Erwarteter Netto-PnL: -0,12104 EUR (Verlust trotz positivem Rohertrag,
        da Gesamtgebühren den Kursgewinn übersteigen).
        """
        pnl = CentralAccountingEngine.calculate_realized_net_pnl(
            buy_price=100.0,
            sell_price=100.40,
            volume=1.0,
            buy_fee=0.26,
            sell_fee=0.26104
        )
        # Berechnung:
        # Bruttoerlös: 100.40
        # Einstandskosten (Kauf + Gebühr): 100.00 + 0.26 = 100.26
        # Abzgl. Verkaufsgebühr: 100.40 - 0.26104 = 100.13896
        # Net PnL = 100.13896 - 100.26 = -0.12104
        self.assertAlmostEqual(float(pnl), -0.12104, places=5,
                               msg="Pflicht-Testfall fehlgeschlagen: Netto-PnL sollte -0,12104 EUR betragen")
        self.assertLess(float(pnl), 0.0,
                        msg="Pflicht-Testfall fehlgeschlagen: Trade muss Netto-Verlust ergeben")

    def test_spec_mandatory_pnl_db_round_trip(self):
        """Pflicht-Testfall als vollständiger Datenbank-Round-Trip.
        Verifiziert, dass der berechnete PnL nach Persistenz in SQLite korrekt ist
        und dass record_sell_trade bei UNKNOWN_COST_BASIS None (nicht 0.0) zurückgibt.
        """
        # BUY: 1 Einheit @ 100 EUR, Gebühr 0,26 EUR
        succ = self.ledger.record_buy_trade(
            timestamp="10:00:00",
            pair="XBTEUR",
            price=100.0,
            volume=1.0,
            fee_eur=0.26,
            txid="TX-SPEC-BUY",
            status="EXECUTED"
        )
        self.assertTrue(succ, "record_buy_trade sollte True zurückgeben")

        # SELL: 1 Einheit @ 100,40 EUR, Gebühr 0,26104 EUR
        succ2, pnl = self.ledger.record_sell_trade(
            timestamp="10:05:00",
            pair="XBTEUR",
            price=100.40,
            volume=1.0,
            fee_eur=0.26104,
            txid="TX-SPEC-SELL",
            status="EXECUTED"
        )
        self.assertTrue(succ2, "record_sell_trade sollte True zurückgeben")
        self.assertIsNotNone(pnl, "PnL darf nicht None sein wenn ein Lot existiert")
        self.assertAlmostEqual(float(pnl), -0.12104, places=5,
                               msg=f"DB-Round-Trip PnL falsch: erwartet -0.12104, erhalten {pnl}")

    def test_unknown_cost_basis_returns_none_not_zero(self):
        """P0-Sicherheitstest: record_sell_trade muss None (nicht 0.0) zurückgeben
        wenn kein offenes Lot existiert (UNKNOWN_COST_BASIS-Szenario).
        """
        # KEIN record_buy_trade vorher → kein Lot in der Datenbank
        succ, pnl = self.ledger.record_sell_trade(
            timestamp="10:00:00",
            pair="SOLEUR",
            price=150.0,
            volume=1.0,
            fee_eur=0.39,
            txid="TX-ORPHAN-SELL",
            status="EXECUTED"
        )
        self.assertTrue(succ, "record_sell_trade sollte auch bei UNKNOWN_COST_BASIS True zurückgeben")
        self.assertIsNone(pnl,
                          "UNKNOWN_COST_BASIS muss None zurückgeben, nicht 0.0 – "
                          "sonst wird ein fiktiver Gewinn im kumulativen PnL verbucht")

if __name__ == "__main__":
    unittest.main()
