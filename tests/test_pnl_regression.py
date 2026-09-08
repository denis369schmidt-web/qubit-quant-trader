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

if __name__ == "__main__":
    unittest.main()
