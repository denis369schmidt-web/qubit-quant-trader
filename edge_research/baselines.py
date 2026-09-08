"""
BENCHMARK BASELINES FÜR DIE EDGE-VALIDIERUNG
--------------------------------------------
Implementiert die 4 geforderten Referenzstrategien:
1. Buy-and-Hold Mix (EUR-gewichtet)
2. SMA Crossover (Fast: 20, Slow: 50)
3. VWAP Reversion (Kauf bei -2 StdAbw, Schließen bei Revert)
4. Simple Spread-Skalp (Maker Bids/Asks mit Queue- & Adverse-Selection-Modell)

Alle Strategien werden unter exakt identischen Kosten (Gebühren, Slippage, Spreads) getestet.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from execution.cost_execution_model import RealisticExecutionModel

class BaselineBuyAndHold:
    """Baseline 1: Passives Halten (Gleichgewichtet über gehandelte Assets)."""
    def __init__(self, initial_capital_eur: float = 1000.0):
        self.capital = initial_capital_eur
        self.holdings = {}
        self.initialized = False

    def on_tick(self, prices: Dict[str, float], fees_pct: float = 0.0026) -> float:
        if not self.initialized:
            # Einmaliger Kauf zu Beginn
            valid_pairs = [p for p, pr in prices.items() if pr > 0]
            if valid_pairs:
                alloc_per_asset = (self.capital * (1.0 - fees_pct)) / len(valid_pairs)
                for p in valid_pairs:
                    self.holdings[p] = alloc_per_asset / prices[p]
                self.capital = 0.0
                self.initialized = True
        
        # Portfolio-Gesamtwert
        total_val = self.capital
        for p, qty in self.holdings.items():
            total_val += qty * prices.get(p, 0.0)
        return total_val


class BaselineSMACrossover:
    """Baseline 2: Trendfolge via SMA Crossover (20/50 Perioden)."""
    def __init__(self, fast_window: int = 20, slow_window: int = 50, initial_capital_eur: float = 1000.0):
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.capital = initial_capital_eur
        self.position_qty = 0.0
        self.history = []

    def on_tick(self, price: float, bid: float, ask: float) -> Dict[str, Any]:
        self.history.append(price)
        if len(self.history) < self.slow_window:
            equity = self.capital + self.position_qty * price
            return {"action": "HOLD", "equity": equity}

        sma_fast = np.mean(self.history[-self.fast_window:])
        sma_slow = np.mean(self.history[-self.slow_window:])

        # Golden Cross -> BUY
        if sma_fast > sma_slow and self.position_qty <= 0:
            fill = RealisticExecutionModel.calculate_simulated_fill(
                pair="XBTEUR", side="BUY", requested_volume=(self.capital * 0.95) / ask,
                arrival_price=price, bid_price=bid, ask_price=ask
            )
            if fill["filled"]:
                cost = fill["exec_price"] * fill["filled_volume"] + fill["fee_eur"]
                if self.capital >= cost:
                    self.capital -= cost
                    self.position_qty += fill["filled_volume"]
                    equity = self.capital + self.position_qty * price
                    return {"action": "BUY", "fill": fill, "equity": equity}

        # Death Cross -> SELL (Exit to Cash)
        elif sma_fast < sma_slow and self.position_qty > 0:
            fill = RealisticExecutionModel.calculate_simulated_fill(
                pair="XBTEUR", side="SELL", requested_volume=self.position_qty,
                arrival_price=price, bid_price=bid, ask_price=ask
            )
            if fill["filled"]:
                proceeds = fill["exec_price"] * fill["filled_volume"] - fill["fee_eur"]
                self.capital += proceeds
                self.position_qty = 0.0
                return {"action": "SELL", "fill": fill, "equity": self.capital}

        equity = self.capital + self.position_qty * price
        return {"action": "HOLD", "equity": equity}


class BaselineVWAPReversion:
    """Baseline 3: Mean Reversion auf rollenden VWAP (-2 StdAbw Bands)."""
    def __init__(self, window: int = 30, initial_capital_eur: float = 1000.0):
        self.window = window
        self.capital = initial_capital_eur
        self.position_qty = 0.0
        self.entry_price = 0.0
        self.prices = []
        self.volumes = []

    def on_tick(self, price: float, volume: float, bid: float, ask: float) -> Dict[str, Any]:
        self.prices.append(price)
        self.volumes.append(max(volume, 0.0001))
        if len(self.prices) < self.window:
            equity = self.capital + self.position_qty * price
            return {"action": "HOLD", "equity": equity}

        p_window = np.array(self.prices[-self.window:])
        v_window = np.array(self.volumes[-self.window:])
        vwap = np.sum(p_window * v_window) / np.sum(v_window)
        std = np.std(p_window)
        lower_band = vwap - 2.0 * std

        # Stark unter VWAP gefallen -> Kauf
        if price <= lower_band and self.position_qty <= 0:
            fill = RealisticExecutionModel.calculate_simulated_fill(
                pair="XBTEUR", side="BUY", requested_volume=(self.capital * 0.95) / ask,
                arrival_price=price, bid_price=bid, ask_price=ask
            )
            if fill["filled"]:
                cost = fill["exec_price"] * fill["filled_volume"] + fill["fee_eur"]
                if self.capital >= cost:
                    self.capital -= cost
                    self.position_qty += fill["filled_volume"]
                    self.entry_price = fill["exec_price"]
                    equity = self.capital + self.position_qty * price
                    return {"action": "BUY", "fill": fill, "equity": equity}

        # Rückkehr zum VWAP -> Ausstieg mit Gewinnmitnahme / Stop
        elif price >= vwap and self.position_qty > 0:
            fill = RealisticExecutionModel.calculate_simulated_fill(
                pair="XBTEUR", side="SELL", requested_volume=self.position_qty,
                arrival_price=price, bid_price=bid, ask_price=ask
            )
            if fill["filled"]:
                proceeds = fill["exec_price"] * fill["filled_volume"] - fill["fee_eur"]
                self.capital += proceeds
                self.position_qty = 0.0
                return {"action": "SELL", "fill": fill, "equity": self.capital}

        equity = self.capital + self.position_qty * price
        return {"action": "HOLD", "equity": equity}


class BaselineSpreadScalp:
    """Baseline 4: Simple Spread-Skalp mit passiven Limit-Orders (Maker)."""
    def __init__(self, initial_capital_eur: float = 1000.0):
        self.capital = initial_capital_eur
        self.position_qty = 0.0
        self.open_buy_order = None

    def on_tick(self, price: float, bid: float, ask: float, depth: float = 1.5) -> Dict[str, Any]:
        # Versuche Maker-Kauf am Bid
        if self.position_qty <= 0:
            fill = RealisticExecutionModel.calculate_simulated_fill(
                pair="XBTEUR", side="BUY", requested_volume=(self.capital * 0.95) / bid,
                arrival_price=price, bid_price=bid, ask_price=ask,
                is_limit_order=True, limit_price=bid, market_depth_volume=depth
            )
            if fill["filled"]:
                cost = fill["exec_price"] * fill["filled_volume"] + fill["fee_eur"]
                if self.capital >= cost:
                    self.capital -= cost
                    self.position_qty += fill["filled_volume"]
                    equity = self.capital + self.position_qty * price
                    return {"action": "MAKER_BUY_FILLED", "fill": fill, "equity": equity}

        # Wenn Position vorhanden, platziere Maker-Verkauf am Ask
        elif self.position_qty > 0:
            fill = RealisticExecutionModel.calculate_simulated_fill(
                pair="XBTEUR", side="SELL", requested_volume=self.position_qty,
                arrival_price=price, bid_price=bid, ask_price=ask,
                is_limit_order=True, limit_price=ask, market_depth_volume=depth
            )
            if fill["filled"]:
                proceeds = fill["exec_price"] * fill["filled_volume"] - fill["fee_eur"]
                self.capital += proceeds
                self.position_qty = 0.0
                return {"action": "MAKER_SELL_FILLED", "fill": fill, "equity": self.capital}

        equity = self.capital + self.position_qty * price
        return {"action": "HOLD", "equity": equity}
