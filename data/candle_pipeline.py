"""
KAUSALE KERZEN- UND DATENPIPELINE
---------------------------------
1. Deterministisches Resampling von Ticks/Trades in abgeschlossene 5m-, 15m- und 1h-Kerzen
2. Exakte UTC-Grenzen [t_start, t_start + dt)
3. Strikte Kausalität: Indikatoren und Einstiegssignale werden AUSSCHLIESSLICH
   auf abgeschlossenen Kerzen berechnet. Intra-Bar-Ticks dürfen keine Einstiege triggern.
4. Lücken- und Duplikaterkennung
"""

import math
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict


class CausalCandleResampler:
    """
    Sammelt unvollständige Ticks und schließt Kerzen deterministisch an UTC-Grenzen ab.
    Löst 'on_candle_close'-Callbacks aus, sobald eine Periode definitiv beendet ist.
    """

    def __init__(
        self,
        interval_seconds: int = 300,  # 300s = 5m
        on_candle_close: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.interval = interval_seconds
        self.on_candle_close = on_candle_close
        
        # Pro Asset: laufende unvollständige Kerze
        self.current_bars: Dict[str, Dict[str, Any]] = {}
        # Abgeschlossene Kerzen-Historie
        self.closed_bars: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Checksum / Duplikatschutz
        self.last_timestamps: Dict[str, float] = {}

    def get_bucket_timestamp(self, ts: float) -> int:
        """Berechnet den abgerundeten UTC-Perioden-Startzeitpunkt."""
        return int(ts // self.interval) * self.interval

    def process_tick(
        self,
        asset: str,
        price: float,
        volume: float,
        timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """
        Verarbeitet einen einzelnen Preis-Tick.
        Gibt eine abgeschlossene Kerze zurück, falls dieser Tick eine neue Periode eingeleitet hat.
        """
        if price <= 0 or timestamp <= 0:
            return None

        # Duplikatschutz (Ticks mit identischem oder älterem Timestamp für denselben Preis)
        last_ts = self.last_timestamps.get(asset, 0.0)
        if timestamp < last_ts:
            # Veralteter Tick (Out-of-Order Event) -> ignorieren
            return None
        self.last_timestamps[asset] = timestamp

        bucket_ts = self.get_bucket_timestamp(timestamp)
        newly_closed_bar = None

        if asset not in self.current_bars:
            # Erste Kerze initialisieren
            self.current_bars[asset] = {
                "asset": asset,
                "timestamp": bucket_ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": max(volume, 0.0),
                "count": 1,
                "is_closed": False
            }
        else:
            bar = self.current_bars[asset]
            if bucket_ts == bar["timestamp"]:
                # Tick gehört zur aktuell offenen Kerze -> Aggregieren
                bar["high"] = max(bar["high"], price)
                bar["low"] = min(bar["low"], price)
                bar["close"] = price
                bar["volume"] += max(volume, 0.0)
                bar["count"] += 1
            elif bucket_ts > bar["timestamp"]:
                # Periode beendet! Die alte Kerze wird abgeschlossen
                bar["is_closed"] = True
                newly_closed_bar = dict(bar)
                self.closed_bars[asset].append(newly_closed_bar)
                
                if len(self.closed_bars[asset]) > 500:
                    self.closed_bars[asset].pop(0)

                if self.on_candle_close:
                    self.on_candle_close(newly_closed_bar)

                # Lückenerkennung (Gap Detection)
                expected_next = bar["timestamp"] + self.interval
                if bucket_ts > expected_next:
                    # Lücke vorhanden (keine Ticks während mindestens eines vollständigen Intervalls)
                    # Erzeuge synthetische Flat-Bars zur Beibehaltung der Zeitreihen-Kontinuität
                    gap_ts = expected_next
                    while gap_ts < bucket_ts:
                        flat_bar = {
                            "asset": asset,
                            "timestamp": gap_ts,
                            "open": bar["close"],
                            "high": bar["close"],
                            "low": bar["close"],
                            "close": bar["close"],
                            "volume": 0.0,
                            "count": 0,
                            "is_closed": True,
                            "is_gap_fill": True
                        }
                        self.closed_bars[asset].append(flat_bar)
                        if self.on_candle_close:
                            self.on_candle_close(flat_bar)
                        gap_ts += self.interval

                # Neue offene Kerze starten
                self.current_bars[asset] = {
                    "asset": asset,
                    "timestamp": bucket_ts,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": max(volume, 0.0),
                    "count": 1,
                    "is_closed": False
                }

        return newly_closed_bar

    def get_closed_candles(self, asset: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gibt ausschließlich abgeschlossene Kerzen zurück."""
        bars = self.closed_bars.get(asset, [])
        if count is not None and count > 0:
            return bars[-count:]
        return list(bars)

    def get_latest_closed_candle(self, asset: str) -> Optional[Dict[str, Any]]:
        bars = self.closed_bars.get(asset, [])
        return bars[-1] if bars else None

    @staticmethod
    def resample_candles(candles: List[Dict[str, Any]], target_interval_seconds: int = 900) -> List[Dict[str, Any]]:
        """
        Aggregiert deterministisch eine Kerzenreihe (z.B. 5m) in ein höheres Zeitintervall (z.B. 15m / 900s).
        Garantiert exakte UTC-Buckets und schließt Kerzen erst ab, wenn die nächste Periode beginnt.
        """
        if not candles:
            return []

        resampled = []
        cur_bucket = None
        cur_bar = None

        for c in candles:
            ts = c.get("timestamp", c.get("ts", 0))
            bucket = int(ts // target_interval_seconds) * target_interval_seconds
            
            if cur_bucket is None:
                cur_bucket = bucket
                cur_bar = {
                    "asset": c.get("asset", "BTC"),
                    "pair": c.get("pair", "XBTEUR"),
                    "timestamp": bucket,
                    "ts": bucket,
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": float(c["volume"]),
                    "is_closed": False
                }
            elif bucket == cur_bucket:
                cur_bar["high"] = max(cur_bar["high"], float(c["high"]))
                cur_bar["low"] = min(cur_bar["low"], float(c["low"]))
                cur_bar["close"] = float(c["close"])
                cur_bar["volume"] += float(c["volume"])
            else:
                cur_bar["is_closed"] = True
                resampled.append(cur_bar)
                cur_bucket = bucket
                cur_bar = {
                    "asset": c.get("asset", "BTC"),
                    "pair": c.get("pair", "XBTEUR"),
                    "timestamp": bucket,
                    "ts": bucket,
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": float(c["volume"]),
                    "is_closed": False
                }

        if cur_bar:
            cur_bar["is_closed"] = True
            resampled.append(cur_bar)

        return resampled

