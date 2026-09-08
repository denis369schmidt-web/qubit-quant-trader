"""
KOSTEN- UND AUSFÜHRUNGSMODELL FÜR DEN INSTITUTIONELLEN KRAKEN SPOT HANDEL
-------------------------------------------------------------------------
Modelliert realistische Marktbedingungen:
- Maker (0.16%) vs. Taker (0.26%)
- Mindestorderwerte und Mengenschritte (Kraken Limits)
- Arrival-Price-Slippage und Adverse Selection
- Orderbuch-Tiefe und Teilfüllungen (Partial Fills)
- Nichtausführungsraten für passive Limit-Orders
- Getrennte Latenzen: Marktdaten (L_data), Entscheidung (L_dec), Exchange Fill (L_exec)
"""

import time
import math
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List

class RealisticExecutionModel:
    """
    Simuliert Orderausführungen unter realen Marktbedingungen.
    Verhindert fiktive Gewinne durch Zero-Slippage oder Mid-Price-Fills.
    """

    DEFAULT_TAKER_FEE_PCT = Decimal("0.0026")  # 0.26% Standard Kraken Taker
    DEFAULT_MAKER_FEE_PCT = Decimal("0.0016")  # 0.16% Standard Kraken Maker

    # Typische Kraken Spot Mindestanforderungen
    PAIR_LIMITS = {
        "XBTEUR": {"ordermin": 0.00005, "costmin": 0.45, "price_decimals": 1, "vol_decimals": 6},
        "ETHEUR": {"ordermin": 0.00100, "costmin": 0.45, "price_decimals": 2, "vol_decimals": 5},
        "SOLEUR": {"ordermin": 0.01000, "costmin": 0.45, "price_decimals": 2, "vol_decimals": 4},
        "XRPEUR": {"ordermin": 1.00000, "costmin": 0.45, "price_decimals": 4, "vol_decimals": 2},
    }

    @classmethod
    def calculate_simulated_fill(
        cls,
        pair: str,
        side: str,
        requested_volume: float,
        arrival_price: float,
        bid_price: float,
        ask_price: float,
        is_limit_order: bool = False,
        limit_price: Optional[float] = None,
        market_depth_volume: float = 2.0,
        volatility_atr: float = 0.0,
        latency_ms: float = 120.0
    ) -> Dict[str, Any]:
        """
        Berechnet die realistische Ausführung einer Order gegen Arrival Price.
        """
        limits = cls.PAIR_LIMITS.get(pair, {"ordermin": 0.0001, "costmin": 0.5, "price_decimals": 2, "vol_decimals": 6})
        side_upper = side.upper()

        # 1. Mindestorder-Prüfung
        if requested_volume < limits["ordermin"]:
            return {
                "filled": False,
                "reason": "VOLUME_BELOW_MIN",
                "filled_volume": 0.0,
                "exec_price": 0.0,
                "fee_eur": 0.0,
                "slippage_bps": 0.0
            }

        nominal_value = requested_volume * arrival_price
        if nominal_value < limits["costmin"]:
            return {
                "filled": False,
                "reason": "COST_BELOW_MIN",
                "filled_volume": 0.0,
                "exec_price": 0.0,
                "fee_eur": 0.0,
                "slippage_bps": 0.0
            }

        # 2. Latenzdrift modellieren
        # Preis driftet während der Latenz (z.B. 120ms) basierend auf ATR
        drift_factor = 0.0
        if volatility_atr > 0 and arrival_price > 0:
            # Annahme: Drift korreliert negativ bei Taker (Adverse Selection)
            drift_factor = (volatility_atr / arrival_price) * math.sqrt(latency_ms / 1000.0) * 0.15

        # 3. Ausführungstyp: Market vs. Limit
        if not is_limit_order:
            # --- TAKER MARKET ORDER ---
            base_price = ask_price if side_upper == "BUY" else bid_price
            
            # Slippage durch Ordergröße im Verhältnis zur Orderbuchtiefe (Market Impact)
            impact_pct = max(0.0002, (requested_volume / max(market_depth_volume, 0.1)) * 0.0025)
            total_slippage_pct = impact_pct + drift_factor

            if side_upper == "BUY":
                exec_price = base_price * (1.0 + total_slippage_pct)
            else:
                exec_price = base_price * (1.0 - total_slippage_pct)

            exec_price = round(exec_price, limits["price_decimals"])
            filled_vol = requested_volume
            fee_pct = cls.DEFAULT_TAKER_FEE_PCT
            fee_eur = round(float(Decimal(str(exec_price)) * Decimal(str(filled_vol)) * fee_pct), 4)

            slippage_bps = abs(exec_price - arrival_price) / arrival_price * 10000.0

            return {
                "filled": True,
                "order_type": "MARKET_TAKER",
                "filled_volume": filled_vol,
                "requested_volume": requested_volume,
                "arrival_price": arrival_price,
                "exec_price": exec_price,
                "fee_eur": fee_eur,
                "fee_pct": float(fee_pct),
                "slippage_bps": round(slippage_bps, 2),
                "is_maker": False
            }

        else:
            # --- MAKER LIMIT ORDER ---
            target_limit = limit_price if limit_price else (bid_price if side_upper == "BUY" else ask_price)
            
            # Prüfung: Wurde das Limit berührt?
            # Bei BUY: Limit-Kauf füllt wenn limit_price >= ask_price (aggressiv) oder limit_price >= bid_price (passiv am Bid bedient)
            # Bei SELL: Limit-Verkauf füllt wenn limit_price <= bid_price (aggressiv) oder limit_price <= ask_price (passiv am Ask bedient)
            if side_upper == "BUY":
                limit_touched = (target_limit >= bid_price)
            else:
                limit_touched = (target_limit <= ask_price)
            
            if not limit_touched:
                # Nichtausführung (Queue Risk)
                return {
                    "filled": False,
                    "reason": "LIMIT_NOT_TOUCHED",
                    "filled_volume": 0.0,
                    "exec_price": 0.0,
                    "fee_eur": 0.0,
                    "slippage_bps": 0.0,
                    "is_maker": True
                }

            # Adverse Selection bei Limit-Orders: Teilfüllung wenn Gegenvolumen gering
            fill_ratio = min(1.0, market_depth_volume / max(requested_volume, 0.0001))
            if fill_ratio < 0.2:
                fill_ratio = 0.2 # Mindestens Teilausführung

            filled_vol = round(requested_volume * fill_ratio, limits["vol_decimals"])
            exec_price = target_limit
            fee_pct = cls.DEFAULT_MAKER_FEE_PCT
            fee_eur = round(float(Decimal(str(exec_price)) * Decimal(str(filled_vol)) * fee_pct), 4)

            slippage_bps = (arrival_price - exec_price) / arrival_price * 10000.0 if side_upper == "BUY" else (exec_price - arrival_price) / arrival_price * 10000.0

            return {
                "filled": True,
                "order_type": "LIMIT_MAKER",
                "filled_volume": filled_vol,
                "requested_volume": requested_volume,
                "arrival_price": arrival_price,
                "exec_price": exec_price,
                "fee_eur": fee_eur,
                "fee_pct": float(fee_pct),
                "slippage_bps": round(slippage_bps, 2),
                "is_maker": True,
                "is_partial": (filled_vol < requested_volume)
            }


class LatencyTelemetryTracker:
    """
    Misst die 3 Latenzkomponenten getrennt zur Vermeidung irreführender Marketing-Claims.
    1. L_data: Zeit von Exchange-Event bis zum Eintreffen im Algorithmus.
    2. L_decision: Zeit für Signalanalyse und Risikoentscheidung.
    3. L_exec: Zeit von REST/WS-Dispatch bis zum bestätigten Fill.
    """

    def __init__(self):
        self.samples = []

    def record_cycle(self, l_data_ms: float, l_decision_ms: float, l_exec_ms: float):
        total_ms = l_data_ms + l_decision_ms + l_exec_ms
        self.samples.append({
            "timestamp": time.time(),
            "l_data_ms": round(l_data_ms, 2),
            "l_decision_ms": round(l_decision_ms, 2),
            "l_exec_ms": round(l_exec_ms, 2),
            "total_ms": round(total_ms, 2)
        })
        if len(self.samples) > 1000:
            self.samples.pop(0)

    def get_summary(self) -> Dict[str, float]:
        if not self.samples:
            return {"avg_total_ms": 0.0, "avg_data_ms": 0.0, "avg_decision_ms": 0.0, "avg_exec_ms": 0.0}
        n = len(self.samples)
        return {
            "avg_data_ms": round(sum(s["l_data_ms"] for s in self.samples) / n, 2),
            "avg_decision_ms": round(sum(s["l_decision_ms"] for s in self.samples) / n, 2),
            "avg_exec_ms": round(sum(s["l_exec_ms"] for s in self.samples) / n, 2),
            "avg_total_ms": round(sum(s["total_ms"] for s in self.samples) / n, 2),
            "sample_count": n
        }
