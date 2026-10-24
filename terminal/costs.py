"""Kostenmodell: Gebühr + Slippage pro Seite (Kauf bzw. Verkauf)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    name: str
    fee_pct: float        # Gebühr pro Seite, z. B. 0.001 = 0.10 %
    slippage_pct: float   # angenommene Slippage pro Seite

    @property
    def per_side(self) -> float:
        return self.fee_pct + self.slippage_pct

    @property
    def roundtrip(self) -> float:
        return 2.0 * self.per_side


# Standard-Gebührenstufen für kleine Konten (niedrigste Volumenstufe).
# Vor echtem Einsatz immer mit der aktuellen Gebührenseite der Börse abgleichen.
PRESETS = {
    "kraken_taker": CostModel("Kraken Pro Taker", fee_pct=0.0040, slippage_pct=0.0005),
    "kraken_maker": CostModel("Kraken Pro Maker", fee_pct=0.0025, slippage_pct=0.0),
    "binance_spot": CostModel("Binance Spot Taker", fee_pct=0.0010, slippage_pct=0.0005),
    "bybit_spot": CostModel("Bybit Spot Taker", fee_pct=0.0010, slippage_pct=0.0005),
    "zero": CostModel("Ohne Kosten (nur zum Vergleich)", fee_pct=0.0, slippage_pct=0.0),
}


def get_cost_model(name: str) -> CostModel:
    if name not in PRESETS:
        raise KeyError(f"Unbekanntes Kostenmodell '{name}'. Verfügbar: {', '.join(PRESETS)}")
    return PRESETS[name]
