"""
Validierung: Walk-Forward-Optimierung, Permutationstest und klare Zulassungs-Hürden.

Fehler aus v1, die hier verhindert werden:
- "Validiert" auf synthetischen Daten -> hier nur echte Kerzen (CSV/Börse).
- 26 Trades als Beweis -> hier Mindestanzahl Trades.
- Parameter auf denselben Daten optimiert und getestet -> hier strikt Train/Test getrennt.
"""

import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type

import numpy as np

from terminal.backtest import BacktestResult, Trade, buy_and_hold, run_backtest
from terminal.costs import CostModel
from terminal.market_data import INTERVAL_SECONDS, Candles
from terminal.strategies import Strategy

GATES = {
    "min_trades": 30,
    "min_profit_factor": 1.2,
    "max_p_value": 0.05,
    "max_drawdown_pct": 25.0,
}


def _score(res: BacktestResult, min_trades: int) -> float:
    m = res.metrics()
    if m["trades"] < min_trades:
        return -np.inf
    return m["net_return_pct"] / (1.0 + m["max_drawdown_pct"])


def optimize(candles: Candles, strategy_cls: Type[Strategy], costs: CostModel,
             min_trades: int = 5, **bt_kwargs) -> Strategy:
    grid = strategy_cls.param_grid
    best, best_score = strategy_cls(), -np.inf
    for combo in itertools.product(*grid.values()):
        strat = strategy_cls(**dict(zip(grid.keys(), combo)))
        if strat.warmup() >= len(candles) - 10:
            continue
        score = _score(run_backtest(candles, strat, costs, **bt_kwargs), min_trades)
        if score > best_score:
            best, best_score = strat, score
    return best


@dataclass
class WalkForwardResult:
    folds: List[Dict] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    oos_equity: Optional[np.ndarray] = None
    bars_per_year: float = 8760.0
    exposure_bars: int = 0

    def metrics(self) -> Dict[str, float]:
        res = BacktestResult("walk_forward", "", float(self.oos_equity[0]), self.oos_equity, self.trades,
                             self.bars_per_year, self.exposure_bars)
        return res.metrics()


def walk_forward(candles: Candles, strategy_cls: Type[Strategy], costs: CostModel,
                 train_bars: int, test_bars: int, initial_equity: float = 1000.0,
                 **bt_kwargs) -> WalkForwardResult:
    """Optimiert auf Fenster [t-train, t), testet unverändert auf [t, t+test). Rollt weiter."""
    wf = WalkForwardResult(bars_per_year=365 * 86400 / INTERVAL_SECONDS[candles.interval])
    curve = [initial_equity]
    equity = initial_equity
    t = train_bars
    while t + test_bars <= len(candles):
        strat = optimize(candles.slice(t - train_bars, t), strategy_cls, costs, **bt_kwargs)
        warm = strat.warmup()
        if t - warm < 0:
            t += test_bars
            continue
        test = candles.slice(t - warm, t + test_bars)
        res = run_backtest(test, strat, costs, initial_equity=equity, **bt_kwargs)
        oos_curve = res.equity[warm:]
        curve.extend(oos_curve.tolist())
        equity = float(oos_curve[-1])
        wf.trades.extend(res.trades)
        wf.exposure_bars += res.exposure_bars
        m = res.metrics()
        wf.folds.append({"start_ts": int(candles.ts[t]), "params": dict(strat.params),
                         "net_return_pct": float(oos_curve[-1] / oos_curve[0] - 1.0) * 100.0 if oos_curve[0] else 0.0,
                         "trades": m["trades"],
                         "buy_hold_pct": buy_and_hold(candles.slice(t, t + test_bars), costs)["net_return_pct"]})
        t += test_bars
    wf.oos_equity = np.array(curve)
    return wf


def permute_candles(candles: Candles, rng: np.random.Generator) -> Candles:
    """Mischt die Kerzen-Renditen. Verteilung bleibt gleich, zeitliche Struktur (das 'Edge') wird zerstört."""
    o, h, l, c = (np.log(x) for x in (candles.open, candles.high, candles.low, candles.close))
    gap, hi, lo, body = o[1:] - c[:-1], h[1:] - o[1:], l[1:] - o[1:], c[1:] - o[1:]
    perm = rng.permutation(len(gap))
    gap, hi, lo, body = gap[perm], hi[perm], lo[perm], body[perm]
    new_o, new_c = np.empty_like(o), np.empty_like(c)
    new_o[0], new_c[0] = o[0], c[0]
    for i in range(1, len(c)):
        new_o[i] = new_c[i - 1] + gap[i - 1]
        new_c[i] = new_o[i] + body[i - 1]
    new_h = np.concatenate([[h[0]], new_o[1:] + hi])
    new_l = np.concatenate([[l[0]], new_o[1:] + lo])
    vol = np.concatenate([[candles.volume[0]], candles.volume[1:][perm]])
    return Candles(candles.symbol, candles.interval, candles.ts.copy(), np.exp(new_o), np.exp(new_h),
                   np.exp(new_l), np.exp(new_c), vol)


def permutation_test(candles: Candles, strategy: Strategy, costs: CostModel, n_perm: int = 100,
                     seed: int = 7, **bt_kwargs) -> Dict[str, float]:
    """p-Wert: Anteil gemischter Kursverläufe, auf denen die Strategie mindestens so gut abschneidet."""
    real = run_backtest(candles, strategy, costs, **bt_kwargs).metrics()["net_return_pct"]
    rng = np.random.default_rng(seed)
    beats = 0
    for _ in range(n_perm):
        perm = permute_candles(candles, rng)
        if run_backtest(perm, strategy, costs, **bt_kwargs).metrics()["net_return_pct"] >= real:
            beats += 1
    return {"real_return_pct": real, "p_value": (beats + 1) / (n_perm + 1), "n_perm": n_perm}


def verdict(oos: Dict[str, float], p_value: float, buy_hold: Dict[str, float]) -> Dict[str, object]:
    checks = {
        f"Mindestens {GATES['min_trades']} Trades": oos["trades"] >= GATES["min_trades"],
        "Netto positiv nach Kosten": oos["net_return_pct"] > 0,
        f"Profit-Faktor >= {GATES['min_profit_factor']}": oos["profit_factor"] >= GATES["min_profit_factor"],
        f"Permutationstest p < {GATES['max_p_value']}": p_value < GATES["max_p_value"],
        f"Max. Drawdown < {GATES['max_drawdown_pct']:.0f} %": oos["max_drawdown_pct"] < GATES["max_drawdown_pct"],
        "Besser als Buy & Hold (Rendite pro Drawdown)":
            oos["net_return_pct"] / (1 + oos["max_drawdown_pct"])
            > buy_hold["net_return_pct"] / (1 + buy_hold["max_drawdown_pct"]),
    }
    passed = all(checks.values())
    return {"checks": checks, "passed": passed,
            "status": "KANDIDAT FÜR PAPER-TRADING" if passed else "NICHT ZUGELASSEN"}
