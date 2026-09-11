"""
TACTICAL EXECUTION SLICER (TWAP & ICEBERG)
------------------------------------------
Portiert und adaptiert aus Chimera (Agent Spartan):
1. Teilt größere Orders in diskrete Micro-Slices auf
2. Reduziert Market Impact und verhindert predatory Front-Running
3. Unterstützt Post-Only Maker Platzierung pro Slice
"""

import time
import math
from typing import Dict, List, Any, Optional


class TacticalOrderSlicer:
    """Zerlegt Orders bei Überschreiten von Liquiditätsschwellen in Micro-Slices."""

    @staticmethod
    def slice_twap(
        total_volume: float,
        price: float,
        num_slices: int = 3,
        interval_seconds: float = 1.0,
        min_slice_volume: float = 0.00005
    ) -> List[Dict[str, Any]]:
        """
        Erzeugt Time-Weighted Micro-Orders (TWAP).
        Stellt sicher, dass kein Slice unter Kraken-Mindestgrößen fällt.
        """
        if total_volume <= 0 or num_slices <= 1:
            return [{
                "slice_index": 0,
                "volume": total_volume,
                "target_price": price,
                "delay_sec": 0.0
            }]

        effective_slices = min(num_slices, max(1, int(total_volume / min_slice_volume)))
        base_slice = round(total_volume / effective_slices, 6)
        remaining = round(total_volume, 6)

        slices = []
        for i in range(effective_slices):
            vol = base_slice if i < effective_slices - 1 else remaining
            vol = round(vol, 6)
            slices.append({
                "slice_index": i,
                "volume": vol,
                "target_price": price,
                "delay_sec": round(i * interval_seconds, 2)
            })
            remaining = round(remaining - vol, 6)

        return slices

    @staticmethod
    def calculate_optimal_slicing(
        requested_volume: float,
        pair: str,
        bid_depth_volume: float,
        ask_depth_volume: float,
        side: str
    ) -> int:
        """
        Ermittelt dynamisch die optimale Anzahl von Slices basierend auf der Orderbuch-Tiefe.
        Wenn die Order mehr als 10% der Top-of-Book Liquidität ausmacht -> Slicing aktivieren!
        """
        available_depth = ask_depth_volume if side.upper() == "BUY" else bid_depth_volume
        if available_depth <= 0:
            return 1

        impact_ratio = requested_volume / available_depth
        if impact_ratio > 0.25:
            return 4
        elif impact_ratio > 0.10:
            return 3
        elif impact_ratio > 0.05:
            return 2
        return 1
