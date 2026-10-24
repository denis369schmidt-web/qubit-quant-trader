"""
Ehrliche Backtest-Engine (Long-only Spot, eine Position pro Markt).

Regeln gegen Selbstbetrug:
1. Signal am Schluss von Kerze t -> Ausführung zur Eröffnung von Kerze t+1 (kein Lookahead).
2. Jede Seite kostet Gebühr + Slippage.
3. Stop-Loss wird intrabar geprüft; Kurslücke unter den Stop -> Ausführung zur Eröffnung.
   Treffen Stop und Ziel in derselben Kerze, wird pessimistisch der Stop angenommen.
4. Positionsgröße über festes Risiko pro Trade (Abstand zum Stop), gedeckelt durch max. Allokation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from terminal.costs import CostModel
from terminal.market_data import INTERVAL_SECONDS, Candles
from terminal.strategies import Strategy


@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    units: float
    fees: float
    net_pnl: float
    reason: str

    @property
    def return_pct(self) -> float:
        cost = self.entry_price * self.units
        return self.net_pnl / cost * 100.0 if cost else 0.0


@dataclass
class BacktestResult:
    strategy: str
    symbol: str
    initial_equity: float
    equity: np.ndarray
    trades: List[Trade] = field(default_factory=list)
    bars_per_year: float = 8760.0
    exposure_bars: int = 0

    def metrics(self) -> Dict[str, float]:
        eq = self.equity
        final = float(eq[-1]) if len(eq) else self.initial_equity
        rets = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([0.0])
        peak = np.maximum.accumulate(eq) if len(eq) else np.array([self.initial_equity])
        mdd = float(np.max((peak - eq) / peak)) if len(eq) else 0.0
        pnls = np.array([t.net_pnl for t in self.trades])
        wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
        gross_win, gross_loss = wins.sum(), -losses.sum()
        years = max(len(eq) / self.bars_per_year, 1e-9)
        total_ret = final / self.initial_equity - 1.0
        std = rets.std()
        return {
            "net_return_pct": total_ret * 100.0,
            "cagr_pct": ((final / self.initial_equity) ** (1.0 / years) - 1.0) * 100.0 if final > 0 else -100.0,
            "max_drawdown_pct": mdd * 100.0,
            "sharpe": float(rets.mean() / std * np.sqrt(self.bars_per_year)) if std > 0 else 0.0,
            "trades": len(self.trades),
            "win_rate_pct": len(wins) / len(pnls) * 100.0 if len(pnls) else 0.0,
            "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0),
            "avg_win": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss": float(losses.mean()) if len(losses) else 0.0,
            "expectancy": float(pnls.mean()) if len(pnls) else 0.0,
            "fees_paid": float(sum(t.fees for t in self.trades)),
            "exposure_pct": self.exposure_bars / max(len(eq), 1) * 100.0,
        }


def run_backtest(candles: Candles, strategy: Strategy, costs: CostModel, initial_equity: float = 1000.0,
                 risk_per_trade: float = 0.01, max_allocation: float = 0.95,
                 signals=None) -> BacktestResult:
    sig = signals or strategy.generate(candles)
    o, h, l, c = candles.open, candles.high, candles.low, candles.close
    n = len(c)
    start = strategy.warmup()
    cash = initial_equity
    units = 0.0
    entry_price = stop = target = 0.0
    entry_idx = -1
    entry_fee = 0.0
    pending_entry = pending_exit = False
    trades: List[Trade] = []
    equity = np.full(n, initial_equity, dtype=float)
    exposure = 0

    def close_position(i: int, raw_price: float, reason: str):
        nonlocal cash, units
        px = raw_price * (1.0 - costs.slippage_pct)
        fee = px * units * costs.fee_pct
        cash += px * units - fee
        net = (px - entry_price) * units - fee - entry_fee
        trades.append(Trade(entry_idx, i, entry_price, px, units, fee + entry_fee, net, reason))
        units = 0.0

    for i in range(n):
        if i > 0:
            # 1) Ausstehende Orders zur Eröffnung ausführen
            if units > 0 and pending_exit:
                close_position(i, o[i], "signal")
            elif units == 0 and pending_entry:
                a = sig.atr[i - 1]
                if np.isfinite(a) and a > 0:
                    px = o[i] * (1.0 + costs.slippage_pct)
                    stop_dist = sig.stop_atr * a
                    equity_now = cash
                    qty = min(equity_now * risk_per_trade / stop_dist,
                              equity_now * max_allocation / (px * (1.0 + costs.fee_pct)))
                    if qty * px > 1e-9:
                        entry_fee = px * qty * costs.fee_pct
                        cash -= px * qty + entry_fee
                        units, entry_price, entry_idx = qty, px, i
                        stop = px - stop_dist
                        target = px + sig.target_atr * a if sig.target_atr > 0 else np.inf
            pending_entry = pending_exit = False

            # 2) Intrabar-Stops prüfen (pessimistisch: Stop vor Ziel)
            if units > 0:
                if o[i] <= stop:
                    close_position(i, o[i], "stop_gap")
                elif l[i] <= stop:
                    close_position(i, stop, "stop")
                elif h[i] >= target:
                    close_position(i, max(target, o[i]), "target")

        # 3) Am Schluss der Kerze: Trailing, Zeit-Stop, neue Signale
        if units > 0:
            exposure += 1
            if sig.trail_atr > 0 and np.isfinite(sig.atr[i]):
                stop = max(stop, c[i] - sig.trail_atr * sig.atr[i])
            if sig.exit[i] or (sig.max_hold_bars and i - entry_idx >= sig.max_hold_bars):
                pending_exit = i + 1 < n
        elif i >= start and sig.entry[i]:
            pending_entry = i + 1 < n

        equity[i] = cash + units * c[i]

    if units > 0:
        close_position(n - 1, c[-1], "end_of_data")
        equity[-1] = cash

    return BacktestResult(repr(strategy), candles.symbol, initial_equity, equity, trades,
                          bars_per_year=365 * 86400 / INTERVAL_SECONDS[candles.interval],
                          exposure_bars=exposure)


def buy_and_hold(candles: Candles, costs: CostModel, initial_equity: float = 1000.0) -> Dict[str, float]:
    px_in = candles.open[0] * (1.0 + costs.per_side)
    units = initial_equity / px_in
    eq = units * candles.close
    eq[-1] = units * candles.close[-1] * (1.0 - costs.per_side)
    peak = np.maximum.accumulate(eq)
    return {"net_return_pct": (eq[-1] / initial_equity - 1.0) * 100.0,
            "max_drawdown_pct": float(np.max((peak - eq) / peak)) * 100.0}
