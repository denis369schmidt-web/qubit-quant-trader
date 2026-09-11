"""
TEST SUITE FOR CHIMERA ENHANCEMENTS IN QUBIT TRADER
---------------------------------------------------
Verifiziert:
1. Micro-Price und Order Flow Imbalance (OFI)
2. Tactical Order Slicer (TWAP / Iceberg)
3. Pre-Trade Compliance Guard & Price Collar
4. Merkle Audit Hash Generierung
"""

import unittest
from execution.microstructure import OrderBookMicrostructureAnalyzer
from execution.tactical_slicer import TacticalOrderSlicer
from risk.compliance_guard import PreTradeComplianceGuard


class TestChimeraEnhancements(unittest.TestCase):

    def test_01_micro_price_and_ofi_calculation(self):
        # Asymmetrisches Orderbuch mit starkem Kaufdruck (Bid: 10 BTC @ 50000, Ask: 2 BTC @ 50010)
        bids = [(50000.0, 10.0), (49990.0, 5.0)]
        asks = [(50010.0, 2.0), (50020.0, 3.0)]

        res = OrderBookMicrostructureAnalyzer.calculate_order_flow_imbalance(bids, asks)
        # OFI muss positiv sein, da 15 BTC Bid vs 5 BTC Ask
        self.assertGreater(res["ofi"], 0.0)
        self.assertEqual(res["ofi"], 0.5)  # (15 - 5) / 20 = 0.5
        # Micro-Price muss näher am Ask liegen wegen hohem Bid-Kaufdruck:
        # P_micro = (50010*10 + 50000*2) / 12 = (500100 + 100000) / 12 = 600100 / 12 = 50008.33
        self.assertGreater(res["micro_price"], 50005.0)

    def test_02_ofi_rejects_falling_knife(self):
        # Starker Verkaufsüberhang (OFI = -0.60)
        valid, reason = OrderBookMicrostructureAnalyzer.validate_entry_ofi(ofi=-0.60)
        self.assertFalse(valid)
        self.assertIn("OFI_REJECT", reason)

        # Gesunder Markt (OFI = +0.10)
        valid_ok, reason_ok = OrderBookMicrostructureAnalyzer.validate_entry_ofi(ofi=0.10)
        self.assertTrue(valid_ok)
        self.assertEqual(reason_ok, "OFI_CONFIRMED")

    def test_03_tactical_twap_slicer_preserves_volume(self):
        total_vol = 0.0030
        slices = TacticalOrderSlicer.slice_twap(
            total_volume=total_vol,
            price=60000.0,
            num_slices=3,
            interval_seconds=1.5
        )
        self.assertEqual(len(slices), 3)
        reconstructed_vol = sum(s["volume"] for s in slices)
        self.assertAlmostEqual(reconstructed_vol, total_vol, places=6)
        self.assertEqual(slices[0]["delay_sec"], 0.0)
        self.assertEqual(slices[1]["delay_sec"], 1.5)
        self.assertEqual(slices[2]["delay_sec"], 3.0)

    def test_04_compliance_price_collar_and_notional(self):
        guard = PreTradeComplianceGuard(max_notional_per_order_eur=1000.0, max_price_collar_pct=0.015)
        
        # 1. Notional Check
        ok, reason = guard.validate_order(
            pair="XBTEUR", side="BUY", volume=0.05, price=50000.0, prevailing_market_price=50000.0
        )
        self.assertFalse(ok)
        self.assertIn("NOTIONAL_LIMIT_EXCEEDED", reason)

        # 2. Price Collar Check (Limit 52000 € vs Market 50000 € = +4.0% Abweichung > 1.5%)
        ok_collar, reason_collar = guard.validate_order(
            pair="XBTEUR", side="BUY", volume=0.01, price=52000.0, prevailing_market_price=50000.0
        )
        self.assertFalse(ok_collar)
        self.assertIn("PRICE_COLLAR_VIOLATION", reason_collar)

        # 3. Gültige Order
        ok_valid, reason_valid = guard.validate_order(
            pair="XBTEUR", side="BUY", volume=0.01, price=50100.0, prevailing_market_price=50000.0
        )
        self.assertTrue(ok_valid)
        self.assertEqual(reason_valid, "COMPLIANCE_APPROVED")

    def test_05_merkle_trade_audit_hash(self):
        h1 = PreTradeComplianceGuard.generate_merkle_trade_hash(
            txid="TX-100", pair="XBTEUR", side="BUY", volume=0.01, price=50000.0, fee_eur=2.0, timestamp="12:00:00"
        )
        h2 = PreTradeComplianceGuard.generate_merkle_trade_hash(
            txid="TX-100", pair="XBTEUR", side="BUY", volume=0.01, price=50000.0, fee_eur=2.0, timestamp="12:00:00"
        )
        h3 = PreTradeComplianceGuard.generate_merkle_trade_hash(
            txid="TX-101", pair="XBTEUR", side="BUY", volume=0.01, price=50000.0, fee_eur=2.0, timestamp="12:00:00"
        )
        self.assertEqual(h1, h2, "Deterministische Hashes müssen identisch sein")
        self.assertNotEqual(h1, h3, "Unterschiedliche TXIDs müssen unterschiedliche Hashes erzeugen")
        self.assertEqual(len(h1), 64, "SHA-256 Hash muss 64 Hex-Zeichen lang sein")


if __name__ == "__main__":
    unittest.main()
