"""
Paper-Trading mit derselben Strategie-Logik wie im Backtest.

Modi:
- paper   (Standard): lokale Simulation mit echten Live-Kursen, Ledger in SQLite.
- testnet (optional): echte Orders auf Binance/Bybit-Testnet über ccxt, Spielgeld.
Echtgeld-Handel ist in v2 bewusst nicht eingebaut.
"""

import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import numpy as np

from terminal.costs import CostModel
from terminal.market_data import EXCHANGES, INTERVAL_SECONDS, Candles, drop_unclosed
from terminal.strategies import Strategy


@dataclass
class RiskLimits:
    risk_per_trade: float = 0.01        # 1 % des Kapitals pro Trade (Abstand zum Stop)
    max_allocation: float = 0.25        # max. 25 % des Kapitals in einer Position
    max_open_positions: int = 4
    daily_loss_limit: float = 0.03      # -3 % am Tag -> keine neuen Einstiege bis morgen
    max_drawdown_kill: float = 0.15     # -15 % vom Hoch -> Handel komplett gestoppt


@dataclass
class Position:
    symbol: str
    units: float
    entry_price: float
    stop: float
    entry_ts: float
    entry_fee: float
    bars_held: int = 0


@dataclass
class PaperState:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    peak_equity: float = 0.0
    day: str = ""
    day_start_equity: float = 0.0
    halted: bool = False

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "PaperState":
        d = json.loads(s)
        d["positions"] = {k: Position(**v) for k, v in d["positions"].items()}
        return cls(**d)


class PaperLedger:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, symbol TEXT, side TEXT, price REAL,
            units REAL, fee REAL, net_pnl REAL, reason TEXT, mode TEXT)""")
        self.conn.commit()

    def record(self, ts, symbol, side, price, units, fee, net_pnl, reason, mode):
        self.conn.execute("INSERT INTO paper_trades (ts, symbol, side, price, units, fee, net_pnl, reason, mode)"
                          " VALUES (?,?,?,?,?,?,?,?,?)", (ts, symbol, side, price, units, fee, net_pnl, reason, mode))
        self.conn.commit()


class PaperTrader:
    def __init__(self, strategy: Strategy, symbols: List[str], costs: CostModel, exchange: str = "binance",
                 interval: str = "1h", initial_cash: float = 1000.0, limits: Optional[RiskLimits] = None,
                 state_dir: str = "paper_state", mode: str = "paper", log=print):
        if mode not in ("paper", "testnet"):
            raise ValueError("Nur 'paper' oder 'testnet' erlaubt. Echtgeld ist in v2 nicht eingebaut.")
        self.strategy, self.symbols, self.costs = strategy, symbols, costs
        self.exchange, self.interval, self.mode, self.log = exchange, interval, mode, log
        self.limits = limits or RiskLimits()
        os.makedirs(state_dir, exist_ok=True)
        self.state_path = os.path.join(state_dir, f"state_{strategy.name}_{exchange}_{interval}.json")
        self.ledger = PaperLedger(os.path.join(state_dir, "paper_ledger.db"))
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                self.state = PaperState.from_json(f.read())
        else:
            self.state = PaperState(cash=initial_cash, peak_equity=initial_cash)
        self.data = EXCHANGES[exchange]()
        self.testnet = TestnetBroker(exchange) if mode == "testnet" else None

    def save(self):
        with open(self.state_path, "w") as f:
            f.write(self.state.to_json())

    def equity(self, prices: Dict[str, float]) -> float:
        return self.state.cash + sum(p.units * prices.get(s, p.entry_price) for s, p in self.state.positions.items())

    def _buy(self, symbol: str, price: float, stop_dist: float, equity: float, now: float):
        px = price * (1.0 + self.costs.slippage_pct)
        units = min(equity * self.limits.risk_per_trade / stop_dist,
                    equity * self.limits.max_allocation / px,
                    self.state.cash / (px * (1.0 + self.costs.fee_pct)))
        if units * px < 10.0:
            self.log(f"[{symbol}] Order zu klein ({units * px:.2f}), übersprungen")
            return
        if self.testnet:
            px, units = self.testnet.market_order(symbol, "buy", units)
        fee = px * units * self.costs.fee_pct
        self.state.cash -= px * units + fee
        self.state.positions[symbol] = Position(symbol, units, px, px - stop_dist, now, fee)
        self.ledger.record(now, symbol, "BUY", px, units, fee, 0.0, "entry", self.mode)
        self.log(f"[{symbol}] KAUF {units:.6f} @ {px:.4f}, Stop {px - stop_dist:.4f}")

    def _sell(self, symbol: str, price: float, reason: str, now: float):
        pos = self.state.positions.pop(symbol)
        px = price * (1.0 - self.costs.slippage_pct)
        units = pos.units
        if self.testnet:
            px, units = self.testnet.market_order(symbol, "sell", units)
        fee = px * units * self.costs.fee_pct
        self.state.cash += px * units - fee
        net = (px - pos.entry_price) * units - fee - pos.entry_fee
        self.ledger.record(now, symbol, "SELL", px, units, fee, net, reason, self.mode)
        self.log(f"[{symbol}] VERKAUF @ {px:.4f} ({reason}), Netto {net:+.2f}")

    def step(self, now: Optional[float] = None) -> Dict[str, float]:
        """Ein Durchlauf: nach jeder geschlossenen Kerze aufrufen."""
        now = now or time.time()
        lookback = (self.strategy.warmup() + 50) * INTERVAL_SECONDS[self.interval]
        prices, atrs, sigs = {}, {}, {}
        for sym in self.symbols:
            try:
                c = drop_unclosed(self.data.klines(sym, self.interval, int(now - lookback)), now)
            except Exception as e:  # Netzwerkfehler dürfen den Lauf nicht abbrechen
                self.log(f"[{sym}] Datenfehler: {e}")
                continue
            if len(c) <= self.strategy.warmup():
                continue
            s = self.strategy.generate(c)
            prices[sym], atrs[sym], sigs[sym] = float(c.close[-1]), float(s.atr[-1]), (s, c)

        st = self.state
        today = time.strftime("%Y-%m-%d", time.gmtime(now))
        eq = self.equity(prices)
        if st.day != today:
            st.day, st.day_start_equity = today, eq
        st.peak_equity = max(st.peak_equity, eq)

        # Ausstiege zuerst: Stop (anhand Tief der letzten Kerze), Trailing, Signal, Zeit-Stop
        for sym in list(st.positions):
            if sym not in sigs:
                continue
            s, c = sigs[sym]
            pos = st.positions[sym]
            pos.bars_held += 1
            if c.low[-1] <= pos.stop:
                self._sell(sym, min(pos.stop, c.close[-1]), "stop", now)
                continue
            if s.trail_atr > 0:
                pos.stop = max(pos.stop, c.close[-1] - s.trail_atr * s.atr[-1])
            if s.exit[-1] or (s.max_hold_bars and pos.bars_held >= s.max_hold_bars):
                self._sell(sym, prices[sym], "signal" if s.exit[-1] else "time", now)

        eq = self.equity(prices)
        if eq <= st.peak_equity * (1.0 - self.limits.max_drawdown_kill):
            st.halted = True
            self.log("KILL-SWITCH: Max. Drawdown erreicht, keine neuen Trades mehr.")
        daily_block = eq <= st.day_start_equity * (1.0 - self.limits.daily_loss_limit)
        if daily_block:
            self.log("Tagesverlust-Limit erreicht, keine neuen Einstiege heute.")

        if not st.halted and not daily_block:
            for sym, (s, c) in sigs.items():
                if len(st.positions) >= self.limits.max_open_positions:
                    break
                if sym not in st.positions and s.entry[-1] and np.isfinite(atrs[sym]) and atrs[sym] > 0:
                    self._buy(sym, prices[sym], s.stop_atr * atrs[sym], eq, now)

        self.save()
        eq = self.equity(prices)
        return {"equity": eq, "cash": st.cash, "open_positions": len(st.positions), "halted": st.halted}

    def run_forever(self):
        step_s = INTERVAL_SECONDS[self.interval]
        self.log(f"Paper-Trading gestartet: {self.strategy} auf {', '.join(self.symbols)} ({self.mode})")
        while True:
            self.log(json.dumps(self.step()))
            now = time.time()
            time.sleep(step_s - (now % step_s) + 5)  # 5 s nach Kerzenschluss


class TestnetBroker:
    """Echte Orders auf dem Testnet der Börse (Spielgeld). Keys aus Umgebungsvariablen."""

    def __init__(self, exchange: str):
        import ccxt  # optional, nur für Testnet nötig
        key = os.environ.get(f"{exchange.upper()}_TESTNET_KEY")
        secret = os.environ.get(f"{exchange.upper()}_TESTNET_SECRET")
        if not key or not secret:
            raise RuntimeError(f"{exchange.upper()}_TESTNET_KEY und _SECRET als Umgebungsvariablen setzen.")
        self.client = getattr(ccxt, exchange)({"apiKey": key, "secret": secret, "enableRateLimit": True})
        self.client.set_sandbox_mode(True)
        self.client.load_markets()

    def market_order(self, symbol: str, side: str, units: float):
        unified = self.client.markets_by_id[symbol][0]["symbol"]
        order = self.client.create_order(unified, "market", side,
                                         float(self.client.amount_to_precision(unified, units)))
        filled = float(order.get("filled") or units)
        avg = float(order.get("average") or order.get("price") or 0.0)
        return avg, filled
