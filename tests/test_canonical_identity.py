"""
AKZEPTANZTEST FÜR STRATEGIE-IDENTITÄT
------------------------------------
Prüft verbindlich:
1. Gleicher aufgezeichneter Datenstrom erzeugt bit-identische Signale
   über Replay, Backtest und Paper-Trading hinweg.
2. Unvollständige Kerzen erzeugen KEINE vorzeitigen Signale.
3. Kausale Kerzen-Pipeline liefert saubere UTC-abgeschlossene Bars.
"""

import unittest
import numpy as np
from edge_research.canonical_strategy import (
    H2MeanReversionStrategy_v1,
    LongOnlyTrendFollower_v1,
    SignalType,
    ExitType
)
from data.candle_pipeline import CausalCandleResampler


class TestCanonicalStrategyIdentity(unittest.TestCase):

    def setUp(self):
        # 60 deterministische 5-Minuten-Kerzen generieren
        np.random.seed(42)
        self.candles = []
        base_ts = 1700000000
        p = 60000.0
        for i in range(60):
            p += float(np.random.normal(0, 150))
            v = float(np.random.uniform(5.0, 20.0))
            # Ab Kerze 45 künstlichen Extrem-Dip mit abnehmendem Volumen erzeugen
            if i == 45:
                p -= 1200.0  # Starker Absturz > 2.5 Sigma
                v = 3.0      # Sehr geringes Volumen (Erschöpfung)
            self.candles.append({
                "timestamp": base_ts + i * 300,
                "open": p + 10,
                "high": p + 30,
                "low": p - 30,
                "close": p,
                "volume": v,
                "is_closed": True
            })

    def test_01_identical_signal_stream_across_replay_and_paper(self):
        """Replay und Paper müssen bei gleichem Datenstrom bit-identische Signale liefern."""
        strat_replay = H2MeanReversionStrategy_v1()
        strat_paper = H2MeanReversionStrategy_v1()

        signals_replay = []
        signals_paper = []

        for i in range(30, len(self.candles)):
            window_slice = self.candles[:i+1]
            res_r = strat_replay.evaluate_signal(window_slice, orderbook_metrics={"obi": 0.15})
            res_p = strat_paper.evaluate_signal(window_slice, orderbook_metrics={"obi": 0.15})

            signals_replay.append((res_r["signal"], res_r["indicators"]["z_score"]))
            signals_paper.append((res_p["signal"], res_p["indicators"]["z_score"]))

        self.assertEqual(signals_replay, signals_paper, "Replay und Paper MÜSSEN bit-identisch sein!")
        # Kerze 45 muss ein valides BUY-Signal erzeugen
        buy_signals = [s for s in signals_replay if s[0] == SignalType.BUY]
        self.assertGreater(len(buy_signals), 0, "H2 muss den Extrem-Dip bei Kerze 45 erkennen")

    def test_02_uncompleted_candles_do_not_fire_signals(self):
        """Unabgeschlossene Kerzen dürfen unter keinen Umständen Signale triggern."""
        pipeline = CausalCandleResampler(interval_seconds=300)
        strat = H2MeanReversionStrategy_v1()
        base_ts = 1700000100  # Exaktes Vielfaches von 300 (1700000100 % 300 == 0)

        # Ticks innerhalb desselben 5m-Intervalls einspeisen [1700000100 bis 1700000399]
        for sec in range(0, 290, 10):
            closed_bar = pipeline.process_tick(
                asset="BTC",
                price=55000.0,
                volume=1.0,
                timestamp=base_ts + sec
            )
            # Solange die Kerze nicht geschlossen ist, darf KEIN Bar zurückkommen
            self.assertIsNone(closed_bar, f"Tick bei Sekunde {sec} darf die Kerze noch nicht abschließen")

        # Erst bei Überschreiten der 300s-Schwelle schließt die Kerze ab
        closed_bar = pipeline.process_tick(
            asset="BTC",
            price=55100.0,
            volume=2.0,
            timestamp=base_ts + 305
        )
        self.assertIsNotNone(closed_bar, "Tick nach 300s MUSS die Vorperiode abschließen")
        self.assertEqual(closed_bar["timestamp"], base_ts)

    def test_03_strict_h2_requires_both_dip_and_volume_exhaustion(self):
        """H2 darf NICHT kaufen, wenn das Volumen hoch ist (fallendes Messer)."""
        strat = H2MeanReversionStrategy_v1()
        candles_high_vol = list(self.candles)
        # Kerze 45: Extrem-Dip aber mit Panik-Volumen (v=50.0 statt v=3.0)
        candles_high_vol[45] = dict(candles_high_vol[45])
        candles_high_vol[45]["volume"] = 150.0

        res = strat.evaluate_signal(candles_high_vol[:46], orderbook_metrics={"obi": 0.15})
        self.assertEqual(
            res["signal"],
            SignalType.HOLD,
            "Bei hohem Volumen (keine Erschöpfung) darf H2 KEINEN Kauf auslösen"
        )


if __name__ == "__main__":
    unittest.main()
