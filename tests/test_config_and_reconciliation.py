"""
TEST SUITE FOR CONFIG LOADER & KRAKEN RECONCILIATION WORKER
------------------------------------------------------------
Prüft:
1. Valides Laden und Mergen von config.yaml via SystemConfig
2. Maker Post-Only Order-Konstruktion (oflags="post")
3. Reconciliation von externen Trades aus Kraken TradesHistory
4. Idempotenz bei wiederholtem Reconciliation-Lauf (keine Duplikate)
"""

import os
import unittest
import sqlite3
from unittest.mock import patch, MagicMock
from ops.config_loader import SystemConfig
from ops.reconciliation_worker import KrakenReconciliationWorker
from institutional_trading_core import KrakenLiveGateway, SQLiteTradeLedgerManager


class TestConfigAndReconciliation(unittest.TestCase):

    def setUp(self):
        self.test_db = "tests/test_recon_ledger.db"
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
        self.ledger = SQLiteTradeLedgerManager(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_01_system_config_loads_yaml_and_defaults(self):
        conf = SystemConfig.load("config.yaml")
        self.assertIn("trading", conf)
        self.assertIn("risk_management", conf)
        self.assertIn("execution", conf)
        self.assertEqual(conf["execution"]["execution_style"], "MAKER_POST_ONLY")
        self.assertTrue(conf["execution"]["post_only"])
        self.assertEqual(SystemConfig.get_trading_universe(), ["XBTEUR", "ETHEUR", "SOLEUR", "XRPEUR"])

    def test_02_post_only_order_construction(self):
        with patch.object(KrakenLiveGateway, 'query_private') as mock_query:
            mock_query.return_value = {"result": {"txid": ["TX-POST-01"]}}
            res = KrakenLiveGateway.execute_live_kraken_order(
                api_key="TEST_KEY",
                api_secret="TEST_SEC",
                pair="XBTEUR",
                side="BUY",
                volume=0.001,
                price=50000.0,
                post_only=True
            )
            self.assertEqual(res["status"], "success")
            mock_query.assert_called_once()
            called_args = mock_query.call_args[0]
            called_data = called_args[1]
            self.assertEqual(called_data["ordertype"], "limit")
            self.assertEqual(called_data["oflags"], "post")
            self.assertEqual(called_data["price"], "50000.0")

    def test_03_reconciliation_imports_external_exchange_trades(self):
        worker = KrakenReconciliationWorker(db_path=self.test_db)
        mock_trades = {
            "TX-EXT-01": {
                "ordertxid": "ORD-01",
                "pair": "XBTEUR",
                "type": "buy",
                "price": "60000.0",
                "vol": "0.05",
                "cost": "3000.0",
                "fee": "7.80",
                "time": 1700000000
            },
            "TX-EXT-02": {
                "ordertxid": "ORD-02",
                "pair": "ETHEUR",
                "type": "sell",
                "price": "3000.0",
                "vol": "1.0",
                "cost": "3000.0",
                "fee": "7.80",
                "time": 1700000100
            }
        }

        with patch.object(worker, 'fetch_exchange_trades') as mock_fetch, \
             patch.object(worker, 'fetch_exchange_balances') as mock_bal:
            mock_fetch.return_value = {"status": "success", "trades": mock_trades}
            mock_bal.return_value = {"EUR": 1500.0, "BTC": 0.05, "ETH": 0.0}

            report = worker.reconcile_once(api_key="KEY", api_secret="SEC")
            self.assertTrue(report["success"])
            self.assertEqual(report["imported_trades_count"], 2)

            # Verifizieren, dass der Trade in der lokalen DB angekommen ist
            conn = sqlite3.connect(self.test_db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM trades")
            count = cur.fetchone()[0]
            conn.close()
            self.assertEqual(count, 2)

    def test_04_reconciliation_is_idempotent(self):
        worker = KrakenReconciliationWorker(db_path=self.test_db)
        mock_trades = {
            "TX-EXT-01": {
                "ordertxid": "ORD-01",
                "pair": "XBTEUR",
                "type": "buy",
                "price": "60000.0",
                "vol": "0.05",
                "cost": "3000.0",
                "fee": "7.80",
                "time": 1700000000
            }
        }

        with patch.object(worker, 'fetch_exchange_trades') as mock_fetch, \
             patch.object(worker, 'fetch_exchange_balances') as mock_bal:
            mock_fetch.return_value = {"status": "success", "trades": mock_trades}
            mock_bal.return_value = {"EUR": 1500.0, "BTC": 0.05}

            # Erster Lauf: Importiert 1 Trade
            rep1 = worker.reconcile_once(api_key="KEY", api_secret="SEC")
            self.assertEqual(rep1["imported_trades_count"], 1)

            # Zweiter Lauf mit identischen Exchange-Daten: 0 neue Trades (Idempotenz)
            rep2 = worker.reconcile_once(api_key="KEY", api_secret="SEC")
            self.assertEqual(rep2["imported_trades_count"], 0)


if __name__ == "__main__":
    unittest.main()
