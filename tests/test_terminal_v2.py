"""
Tests für Qubit Terminal v2. Synthetische Kurse dienen hier NUR der Prüfung der Rechenlogik,
niemals als Beleg für eine profitable Strategie.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from terminal import ledger_analysis
from terminal.backtest import run_backtest
from terminal.costs import CostModel, get_cost_model
from terminal.market_data import Candles
from terminal.paper import PaperTrader, RiskLimits
from terminal.scanner import analyze, prefilter
from terminal.strategies import Signals, Strategy, TrendFollow, MeanReversion, DonchianBreakout
from terminal.validation import permute_candles, permutation_test, verdict, walk_forward


def make_candles(closes, interval="1h", spread=0.002):
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) * (1 + spread)
    lows = np.minimum(opens, closes) * (1 - spread)
    ts = np.arange(len(closes)) * 3600.0 + 1.7e9
    return Candles("TESTUSDT", interval, ts, opens, highs, lows, closes, np.ones(len(closes)) * 100.0)


def random_walk(n, seed=1, drift=0.0, vol=0.01):
    rng = np.random.default_rng(seed)
    return 100.0 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


class FixedSignals(Strategy):
    """Testhilfe: Einstieg/Ausstieg an vorgegebenen Kerzen."""
    name = "fixed"

    def __init__(self, entries, exits, stop_atr=1000.0):
        super().__init__()
        self.entries, self.exits, self.stop = entries, exits, stop_atr

    def generate(self, c):
        e, x = np.zeros(len(c), bool), np.zeros(len(c), bool)
        e[self.entries], x[self.exits] = True, True
        return Signals(e, x, np.ones(len(c)), self.stop)


class TestBacktestEngine(unittest.TestCase):

    def test_entry_fills_at_next_open_no_lookahead(self):
        c = make_candles([100, 100, 110, 120, 130, 140])
        res = run_backtest(c, FixedSignals([1], [3]), get_cost_model("zero"), max_allocation=1.0,
                           risk_per_trade=1.0)
        t = res.trades[0]
        self.assertEqual(t.entry_idx, 2)
        self.assertAlmostEqual(t.entry_price, c.open[2])   # = Schluss von Kerze 1, nicht 110
        self.assertEqual(t.exit_idx, 4)
        self.assertAlmostEqual(t.exit_price, c.open[4])

    def test_flat_price_loses_exactly_roundtrip_costs(self):
        c = make_candles([100.0] * 10, spread=0.0)
        costs = CostModel("t", fee_pct=0.004, slippage_pct=0.0)
        res = run_backtest(c, FixedSignals([1], [4]), costs, initial_equity=1000.0, max_allocation=1.0,
                           risk_per_trade=1.0)
        t = res.trades[0]
        notional = t.entry_price * t.units
        self.assertAlmostEqual(t.net_pnl, -notional * 0.008, places=6)
        self.assertLess(res.equity[-1], 1000.0)

    def test_gap_below_stop_fills_at_open_not_stop(self):
        closes = [100, 100, 100, 80, 80]
        c = make_candles(closes, spread=0.0)
        c.open[3] = 80.0
        res = run_backtest(c, FixedSignals([1], [], stop_atr=5.0), get_cost_model("zero"))
        t = res.trades[0]
        self.assertEqual(t.reason, "stop_gap")
        self.assertAlmostEqual(t.exit_price, 80.0)

    def test_risk_sizing_caps_loss_per_trade(self):
        c = make_candles([100, 100, 100, 100, 50, 50], spread=0.0)
        c.low[4] = 50.0
        c.open[4] = 100.0
        res = run_backtest(c, FixedSignals([1], [], stop_atr=2.0), get_cost_model("zero"),
                           initial_equity=1000.0, risk_per_trade=0.01)
        self.assertAlmostEqual(res.trades[0].net_pnl, -10.0, places=6)  # genau 1 % Risiko

    def test_strategies_run_on_random_walk(self):
        c = make_candles(random_walk(1500))
        for strat in (TrendFollow(), DonchianBreakout(), MeanReversion()):
            m = run_backtest(c, strat, get_cost_model("binance_spot")).metrics()
            self.assertTrue(np.isfinite(m["net_return_pct"]))


class TestValidation(unittest.TestCase):

    def test_permutation_keeps_return_distribution(self):
        c = make_candles(random_walk(500))
        p = permute_candles(c, np.random.default_rng(0))
        r1 = np.sort(np.diff(np.log(c.close)))
        self.assertAlmostEqual(np.log(p.close[-1] / p.close[0]), np.log(c.close[-1] / c.close[0]), places=8)
        self.assertEqual(len(p), len(c))
        self.assertTrue(np.all(p.high >= np.maximum(p.open, p.close) - 1e-9))
        self.assertTrue(np.all(p.low <= np.minimum(p.open, p.close) + 1e-9))
        self.assertEqual(len(r1), len(p.close) - 1)

    def test_walk_forward_produces_oos_folds(self):
        c = make_candles(random_walk(3000, seed=3))
        wf = walk_forward(c, DonchianBreakout, get_cost_model("binance_spot"), train_bars=1500, test_bars=500)
        self.assertEqual(len(wf.folds), 3)
        self.assertEqual(len(wf.oos_equity), 1 + 3 * 500)

    def test_random_walk_is_not_approved(self):
        """Auf reinem Zufall darf keine Strategie die Hürden bestehen. Genau das hat v1 übersehen."""
        c = make_candles(random_walk(3000, seed=11))
        wf = walk_forward(c, TrendFollow, get_cost_model("binance_spot"), train_bars=1500, test_bars=500)
        oos = c.slice(1500, 3000)
        perm = permutation_test(oos, TrendFollow(**wf.folds[-1]["params"]), get_cost_model("binance_spot"),
                                n_perm=20)
        v = verdict(wf.metrics(), perm["p_value"], {"net_return_pct": 0.0, "max_drawdown_pct": 1.0})
        self.assertFalse(v["passed"])


class TestScanner(unittest.TestCase):

    def test_prefilter_removes_stablecoins_and_illiquid(self):
        snap = [
            {"symbol": "BTCUSDT", "quote_volume": 1e9, "bid": 100.0, "ask": 100.01},
            {"symbol": "USDCUSDT", "quote_volume": 1e9, "bid": 1.0, "ask": 1.0001},
            {"symbol": "TINYUSDT", "quote_volume": 1e3, "bid": 1.0, "ask": 1.001},
            {"symbol": "WIDEUSDT", "quote_volume": 1e8, "bid": 1.0, "ask": 1.01},
        ]
        self.assertEqual([m["symbol"] for m in prefilter(snap)], ["BTCUSDT"])

    def test_cost_ratio_flags_expensive_markets(self):
        c = make_candles(random_walk(400, vol=0.001), spread=0.0005)
        a = analyze(c, get_cost_model("kraken_taker"))
        self.assertGreater(a["cost_ratio"], 1.0)  # Kosten größer als typische Bewegung -> untauglich


class TestLedgerAnalysis(unittest.TestCase):

    def test_v1_incident_case_b_recomputed(self):
        """SOL #94/#96 aus INCIDENT_REPORT_PNL.md: v1 zeigte +6,52 €, real -0,03778 €."""
        fills = [ledger_analysis.Fill(1.0, "SOLEUR", "BUY", 103.82, 0.063, 0.0170),
                 ledger_analysis.Fill(2.0, "SOLEUR", "SELL", 103.76, 0.063, 0.0170)]
        trips, unmatched, open_lots = ledger_analysis.build_roundtrips(fills)
        self.assertAlmostEqual(trips[0].net, -0.03778, places=5)
        self.assertEqual(unmatched, {})

    def test_reads_v1_sqlite_schema_and_flags_unknown_cost_basis(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trading_ledger.db")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, timestamp TEXT, pair TEXT, side TEXT, "
                         "price REAL, volume REAL, fee_eur REAL, pnl_eur REAL, txid TEXT, status TEXT)")
            rows = [("2026-09-01 10:00:00", "ETHEUR", "SELL", 2500.0, 0.001, 0.0065, 2.61, "a", "FILLED"),
                    ("2026-09-01 11:00:00", "ETHEUR", "BUY", 2491.3, 0.00105, 0.0068, 0.0, "b", "FILLED"),
                    ("2026-09-01 12:00:00", "ETHEUR", "SELL", 2491.3, 0.00105, 0.0068, 2.61, "c", "FILLED")]
            conn.executemany("INSERT INTO trades (timestamp, pair, side, price, volume, fee_eur, pnl_eur, txid,"
                             " status) VALUES (?,?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            conn.close()
            trips, unmatched, _ = ledger_analysis.build_roundtrips(ledger_analysis.load(path))
            self.assertAlmostEqual(trips[0].net, -0.0136, places=6)
            self.assertAlmostEqual(unmatched["ETHEUR"], 0.001)
            self.assertIn("Netto-PnL", ledger_analysis.report(path))

    def test_reads_kraken_csv_export(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trades.csv")
            with open(path, "w") as f:
                f.write('"txid","ordertxid","pair","time","type","ordertype","price","cost","fee","vol"\n'
                        '"T1","O1","SOL/EUR","2026-09-01 10:00:00.1","buy","market","100","10","0.04","0.1"\n'
                        '"T2","O2","SOL/EUR","2026-09-01 12:00:00.1","sell","market","101","10.1","0.0404","0.1"\n')
            trips, _, _ = ledger_analysis.build_roundtrips(ledger_analysis.load(path))
            self.assertEqual(trips[0].pair, "SOLEUR")
            self.assertAlmostEqual(trips[0].net, 0.1 - 0.0804, places=6)


class FakeData:
    def __init__(self, candles):
        self.candles = candles

    def klines(self, symbol, interval, start_ts, end_ts=None):
        return self.candles


class TestPaperTrader(unittest.TestCase):

    def test_live_mode_is_refused(self):
        with self.assertRaises(ValueError):
            PaperTrader(TrendFollow(), ["BTCUSDT"], get_cost_model("zero"), mode="live",
                        state_dir=tempfile.mkdtemp())

    def test_step_enters_on_signal_and_persists_state(self):
        c = make_candles([100.0] * 50)
        strat = FixedSignals([49], [], stop_atr=2.0)
        with tempfile.TemporaryDirectory() as d:
            t = PaperTrader(strat, ["TESTUSDT"], get_cost_model("binance_spot"), state_dir=d,
                            initial_cash=1000.0, limits=RiskLimits(max_allocation=1.0))
            t.data = FakeData(c)
            out = t.step(now=c.ts[-1] + 7200)
            self.assertEqual(out["open_positions"], 1)
            pos = t.state.positions["TESTUSDT"]
            self.assertAlmostEqual((pos.entry_price - pos.stop) * pos.units, 10.0, places=6)  # 1 % Risiko
            t2 = PaperTrader(strat, ["TESTUSDT"], get_cost_model("binance_spot"), state_dir=d)
            self.assertIn("TESTUSDT", t2.state.positions)
            t2.ledger.conn.close()
            t.ledger.conn.close()


if __name__ == "__main__":
    unittest.main()
