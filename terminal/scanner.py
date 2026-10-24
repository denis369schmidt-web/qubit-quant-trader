"""
Multi-Markt-Scanner: Bewertet hunderte Paare nach Handelbarkeit, nicht nach Hoffnung.

Kernkennzahl ist das Kosten-zu-Bewegung-Verhältnis: Wie viel der typischen Kerzenbewegung (ATR)
frisst ein Roundtrip aus Gebühr + Slippage + Spread? v1 hat genau daran Geld verloren.
"""

import re
from typing import Dict, List, Optional

import numpy as np

from terminal import indicators as ind
from terminal.costs import CostModel
from terminal.market_data import Candles
from terminal.strategies import STRATEGIES

EXCLUDE = re.compile(r"^(USDC|FDUSD|TUSD|BUSD|DAI|USDP|USDE|EUR|AEUR|EURI|PYUSD|USD1|XUSD|BFUSD|RLUSD|PAXG|WBTC|WBETH)"
                     r"|(UP|DOWN|BULL|BEAR)USDT$")


def prefilter(snapshot: List[Dict[str, float]], min_quote_volume: float = 5e6,
              max_spread_pct: float = 0.15) -> List[Dict[str, float]]:
    """Grobfilter aus 24h-Daten: genug Liquidität, enger Spread, keine Stablecoins/Hebel-Token."""
    out = []
    for m in snapshot:
        mid = (m["bid"] + m["ask"]) / 2.0
        spread = (m["ask"] - m["bid"]) / mid * 100.0
        if m["quote_volume"] < min_quote_volume or spread > max_spread_pct or EXCLUDE.search(m["symbol"]):
            continue
        out.append({**m, "spread_pct": spread})
    return sorted(out, key=lambda m: -m["quote_volume"])


def analyze(candles: Candles, costs: CostModel, spread_pct: float = 0.0) -> Dict[str, object]:
    """Detail-Bewertung eines Marktes anhand geschlossener Kerzen."""
    c = candles.close
    a = ind.atr(candles.high, candles.low, c, 14)
    atr_pct = float(a[-1] / c[-1] * 100.0)
    er = float(ind.efficiency_ratio(c, 20)[-1])
    ema100 = ind.ema(c, 100)
    roundtrip_pct = costs.roundtrip * 100.0 + spread_pct
    cost_ratio = roundtrip_pct / atr_pct if atr_pct > 0 else np.inf
    signals = {}
    for name, cls in STRATEGIES.items():
        strat = cls()
        if len(candles) > strat.warmup() + 1:
            signals[name] = bool(strat.generate(candles).entry[-1])
    # Score: Bewegung relativ zu Kosten (Hauptfaktor) + Trendqualität. Höher = besser handelbar.
    score = (1.0 / max(cost_ratio, 1e-6)) * (0.5 + er)
    return {
        "symbol": candles.symbol,
        "last": float(c[-1]),
        "atr_pct": atr_pct,
        "roundtrip_cost_pct": roundtrip_pct,
        "cost_ratio": cost_ratio,
        "efficiency": er,
        "uptrend": bool(np.isfinite(ema100[-1]) and c[-1] > ema100[-1]),
        "signals": signals,
        "score": float(score),
    }


def rank(analyses: List[Dict[str, object]], max_cost_ratio: float = 0.35) -> List[Dict[str, object]]:
    """Sortiert nach Score und markiert Märkte, in denen Kosten > 35 % der typischen Bewegung sind."""
    for a in analyses:
        a["tradeable"] = a["cost_ratio"] <= max_cost_ratio
    return sorted(analyses, key=lambda a: (-int(a["tradeable"]), -a["score"]))
