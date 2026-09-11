"""
L2 ORDER BOOK MICROSTRUCTURE & ORDER FLOW IMBALANCE (OFI) ENGINE
-----------------------------------------------------------------
Übernommen und adaptiert aus Chimera (Agent Hydra):
1. Vektorisiertes Multi-Level L2 Orderbuch-Parsing
2. Micro-Price Berechnung:
   P_micro = (P_ask * Vol_bid + P_bid * Vol_ask) / (Vol_bid + Vol_ask)
3. Order Flow Imbalance (OFI) & Queue Pressure Indicator
4. Verhindert Einstiege gegen massive Überhangs-Orderwände
"""

import math
from typing import Dict, List, Tuple, Any, Optional


class OrderBookMicrostructureAnalyzer:
    """Analysiert L2-Orderbuch-Tiefe und berechnet den hochfrequenten Micro-Price & OFI."""

    @staticmethod
    def calculate_micro_price(
        best_bid: float,
        best_ask: float,
        bid_volume: float,
        ask_volume: float
    ) -> float:
        """
        Berechnet den volumengewichteten Micro-Price.
        Zeigt die wahre Preisdrift vor der nächsten Kursänderung.
        """
        total_vol = bid_volume + ask_volume
        if total_vol <= 1e-12:
            return (best_bid + best_ask) / 2.0
        return (best_ask * bid_volume + best_bid * ask_volume) / total_vol

    @staticmethod
    def calculate_order_flow_imbalance(
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        depth_levels: int = 5
    ) -> Dict[str, float]:
        """
        Berechnet die kumulierte Tiefe und den Order Flow Imbalance (OFI) Ratio [-1.0, +1.0].
        OFI > 0: Aggressiver Kaufüberhang / Druck nach oben
        OFI < 0: Aggressiver Verkaufsüberhang / Druck nach unten
        """
        if not bids or not asks:
            return {"ofi": 0.0, "bid_depth_eur": 0.0, "ask_depth_eur": 0.0, "micro_price": 0.0}

        top_bids = bids[:depth_levels]
        top_asks = asks[:depth_levels]

        bid_vol_sum = sum(vol for _, vol in top_bids)
        ask_vol_sum = sum(vol for _, vol in top_asks)
        
        bid_eur_sum = sum(p * vol for p, vol in top_bids)
        ask_eur_sum = sum(p * vol for p, vol in top_asks)

        total_vol = bid_vol_sum + ask_vol_sum
        ofi = (bid_vol_sum - ask_vol_sum) / total_vol if total_vol > 0 else 0.0

        best_bid = top_bids[0][0]
        best_ask = top_asks[0][0]
        micro_p = OrderBookMicrostructureAnalyzer.calculate_micro_price(
            best_bid, best_ask, top_bids[0][1], top_asks[0][1]
        )

        return {
            "ofi": round(float(ofi), 4),
            "bid_depth_eur": round(float(bid_eur_sum), 2),
            "ask_depth_eur": round(float(ask_eur_sum), 2),
            "micro_price": round(float(micro_p), 4),
            "spread_bps": round(float((best_ask - best_bid) / best_bid * 10000.0), 2)
        }

    @staticmethod
    def validate_entry_ofi(ofi: float, min_ofi_threshold: float = -0.20) -> Tuple[bool, str]:
        """
        Blockiert Einstiege, wenn ein massiver Verkaufsüberhang (OFI < -0.20)
        im Orderbuch vorliegt (Vermeidung von 'Falling Knife' Fills).
        """
        if ofi < min_ofi_threshold:
            return False, f"OFI_REJECT: Starker Verkaufsüberhang ({ofi:+.2f} < {min_ofi_threshold:+.2f})"
        return True, "OFI_CONFIRMED"
