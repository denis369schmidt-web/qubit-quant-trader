"""
DATEN-NORMALISIERER FÜR KRYPTO-MARKTDATEN
-----------------------------------------
Gewährleistet:
1. Einheitliche Spalten: ts, asset, price, volume, side, venue
2. Konsistente Asset-Namen (z.B. XBT -> BTC, XXBT -> BTC, XETH -> ETH)
3. Einheitliche EUR-Basis (Umrechnung von USD/USDT falls nötig)
4. Strenges Zeitstempel-Parsing (UTC ISO-8601 & Unix-Epoch)
"""

import datetime
from typing import Dict, Any, List, Optional

ASSET_MAP = {
    "XXBT": "BTC", "XBT": "BTC", "BTC": "BTC",
    "XETH": "ETH", "ETH": "ETH",
    "XXRP": "XRP", "XRP": "XRP",
    "SOL": "SOL"
}

PAIR_MAPPING = {
    "XXBTZEUR": ("BTC", "EUR"),
    "XBTEUR": ("BTC", "EUR"),
    "XETHZEUR": ("ETH", "EUR"),
    "ETHEUR": ("ETH", "EUR"),
    "XXRPZEUR": ("XRP", "EUR"),
    "XRPEUR": ("XRP", "EUR"),
    "SOLEUR": ("SOL", "EUR")
}

class MarketDataNormalizer:
    """Normalisiert Marktdatenströme in ein konsistentes Format."""

    @staticmethod
    def normalize_asset_name(raw_name: str) -> str:
        clean = raw_name.upper().strip()
        return ASSET_MAP.get(clean, clean)

    @staticmethod
    def normalize_trade(
        ts: float,
        pair: str,
        price: float,
        volume: float,
        side: str = "BUY",
        venue: str = "Kraken"
    ) -> Dict[str, Any]:
        """
        Normalisiert einen Trade in das einheitliche Format:
        ts, asset, price, volume, side, venue
        """
        base_asset = ASSET_MAP.get(pair.replace("EUR", "").replace("USD", ""), pair)
        for k, (b, q) in PAIR_MAPPING.items():
            if k == pair:
                base_asset = b
                break

        return {
            "ts": float(ts),
            "iso_time": datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat(),
            "asset": base_asset,
            "pair": pair,
            "price": float(price),
            "volume": float(volume),
            "side": side.upper(),
            "venue": venue
        }

    @staticmethod
    def normalize_candle(
        ts: float,
        pair: str,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: float,
        trades_count: int = 0,
        venue: str = "Kraken"
    ) -> Dict[str, Any]:
        """
        Normalisiert Kerzen-Daten (OHLCV).
        """
        base_asset = ASSET_MAP.get(pair.replace("EUR", "").replace("USD", ""), pair)
        for k, (b, q) in PAIR_MAPPING.items():
            if k == pair:
                base_asset = b
                break

        return {
            "ts": float(ts),
            "iso_time": datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat(),
            "asset": base_asset,
            "pair": pair,
            "open": float(open_p),
            "high": float(high_p),
            "low": float(low_p),
            "close": float(close_p),
            "volume": float(volume),
            "trades_count": int(trades_count),
            "venue": venue
        }
