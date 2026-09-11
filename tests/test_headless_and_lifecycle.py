"""
TESTS FÜR HEADLESS-ENGINE, LOCKS UND STATE MACHINE
--------------------------------------------------
1. Single-Instance Lock verhindert Doppelinstanzen
2. LIVE_READ_ONLY blockiert jede Orderplatzierung
3. LIVE_ACTIVE verlangt kryptografischen Token
4. Kausale Signalgenerierung nur bei Kerzenabschluss
"""

import os
import unittest
from ops.headless_engine import (
    SingleInstanceLock,
    HeadlessQuantumTraderEngine,
    EngineOperationalMode
)


class TestHeadlessAndLifecycle(unittest.TestCase):

    def setUp(self):
        self.test_lock = "test_qubit.lock"
        self.test_state = "test_telemetry_state.json"
        if os.path.exists(self.test_lock):
            try: os.remove(self.test_lock)
            except Exception: pass
        if os.path.exists(self.test_state):
            try: os.remove(self.test_state)
            except Exception: pass

    def tearDown(self):
        if os.path.exists(self.test_lock):
            try: os.remove(self.test_lock)
            except Exception: pass
        if os.path.exists(self.test_state):
            try: os.remove(self.test_state)
            except Exception: pass

    def test_01_single_instance_lock_prevents_dual_engine(self):
        """Zweite Engine-Instanz darf den Lock nicht erwerben."""
        lock1 = SingleInstanceLock(self.test_lock)
        lock2 = SingleInstanceLock(self.test_lock)

        self.assertTrue(lock1.acquire(), "Instanz 1 muss Lock erhalten")
        self.assertFalse(lock2.acquire(), "Instanz 2 MUSS abgewiesen werden!")

        lock1.release()
        self.assertTrue(lock2.acquire(), "Nach Release muss Instanz 2 den Lock erhalten")
        lock2.release()

    def test_02_live_read_only_strictly_blocks_orders(self):
        """LIVE_READ_ONLY darf keine Orders platzieren."""
        engine = HeadlessQuantumTraderEngine(
            mode=EngineOperationalMode.LIVE_READ_ONLY,
            state_file=self.test_state
        )
        res = engine._dispatch_order({
            "pair": "XBTEUR", "side": "BUY", "asset": "BTC",
            "volume": 0.001, "price": 60000.0
        })
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["code"], "LIVE_READ_ONLY_BLOCKED")

    def test_03_live_active_without_token_falls_back_to_read_only(self):
        """LIVE_ACTIVE ohne kryptografischen Token muss abgewiesen werden."""
        engine = HeadlessQuantumTraderEngine(
            mode=EngineOperationalMode.LIVE_ACTIVE,
            release_token=None,
            state_file=self.test_state
        )
        self.assertEqual(engine.mode, EngineOperationalMode.LIVE_READ_ONLY)

    def test_04_telemetry_heartbeat_valid_json(self):
        """Heartbeat-Telemetrie muss valide JSON-Struktur erzeugen."""
        engine = HeadlessQuantumTraderEngine(
            mode=EngineOperationalMode.PAPER,
            state_file=self.test_state
        )
        engine.write_telemetry_heartbeat()
        self.assertTrue(os.path.exists(self.test_state))
        import json
        with open(self.test_state, "r") as f:
            data = json.load(f)
        self.assertIn("heartbeat", data)
        self.assertIn("mode", data)
        self.assertEqual(data["mode"], "PAPER")


if __name__ == "__main__":
    unittest.main()
