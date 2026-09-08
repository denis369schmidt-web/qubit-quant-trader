"""
DATEN-SAMMLER & DETERMINISTISCHER REPLAY-GENERATOR
--------------------------------------------------
Unterstützt:
1. Inkrementelles Laden von Kraken Public REST (OHLC & Trades)
2. Deterministische Erzeugung von Offline-Marktdaten (GBM + Jump Diffusion)
3. Checksummen-Generierung (SHA-256)
4. Lücken-Erkennung (Gap Detection)
"""

import os
import json
import hashlib
import urllib.request
import numpy as np
from typing import Dict, List, Any, Optional
from data.normalizer import MarketDataNormalizer

class MarketDataCollector:
    """Verwaltet Download, Replay und Caching von historischen Marktdaten."""

    def __init__(self, storage_dir: str = "fetched_data"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def fetch_kraken_ohlc_rest(self, pair: str = "XBTEUR", interval_minutes: int = 5) -> List[Dict[str, Any]]:
        """Lädt aktuelle OHLCV-Kerzen von Kraken REST herunter."""
        url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval_minutes}"
        req = urllib.request.Request(url, headers={'User-Agent': 'QubitDataCollector/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                result = data.get("result", {})
                # Finde den Datenschlüssel (z.B. XXBTZEUR)
                candles = []
                for k, rows in result.items():
                    if k != "last":
                        for r in rows:
                            # r = [time, open, high, low, close, vwap, volume, count]
                            norm = MarketDataNormalizer.normalize_candle(
                                ts=float(r[0]),
                                pair=pair,
                                open_p=float(r[1]),
                                high_p=float(r[2]),
                                low_p=float(r[3]),
                                close_p=float(r[4]),
                                volume=float(r[6]),
                                trades_count=int(r[7]),
                                venue="Kraken"
                            )
                            candles.append(norm)
                return candles
        except Exception as e:
            return []

    def generate_deterministic_dataset(
        self,
        pair: str = "XBTEUR",
        n_candles: int = 1500,
        start_price: float = 60000.0,
        seed: int = 42,
        dt_seconds: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Erzeugt einen deterministischen Benchmark-Datensatz (ohne Netzwerkabhängigkeit)
        mit realistischen Eigenschaften (Fat Tails, Volatilitäts-Cluster, Regime-Wechsel).
        """
        np.random.seed(seed)
        candles = []
        cur_p = start_price
        start_ts = 1700000000.0 # Fester Referenz-Zeitstempel

        # Parameter
        base_vol = 0.0008
        cur_vol = base_vol

        for i in range(n_candles):
            ts = start_ts + (i * dt_seconds)
            # Volatilitäts-Clustering (GARCH-ähnlich)
            shock = np.random.normal(0, 1.0)
            cur_vol = 0.92 * cur_vol + 0.08 * base_vol + 0.0002 * abs(shock)

            # Gelegentlicher Jump (z.B. News Event)
            jump = 0.0
            if np.random.uniform(0, 1) < 0.015:
                jump = np.random.choice([-1, 1]) * np.random.uniform(0.01, 0.035)

            ret = (cur_vol * shock) + jump
            open_p = cur_p
            close_p = open_p * (1.0 + ret)
            high_p = max(open_p, close_p) * (1.0 + abs(np.random.normal(0, cur_vol * 0.5)))
            low_p = min(open_p, close_p) * (1.0 - abs(np.random.normal(0, cur_vol * 0.5)))
            volume = float(np.random.lognormal(mean=1.5, sigma=0.8))

            candle = MarketDataNormalizer.normalize_candle(
                ts=ts,
                pair=pair,
                open_p=round(open_p, 2),
                high_p=round(high_p, 2),
                low_p=round(low_p, 2),
                close_p=round(close_p, 2),
                volume=round(volume, 4),
                trades_count=int(volume * 12),
                venue="DeterministicReplay"
            )
            candles.append(candle)
            cur_p = close_p

        return candles

    def save_dataset_csv(self, candles: List[Dict[str, Any]], filename: str) -> str:
        """Speichert Kerzen als CSV mit SHA-256 Prüfsumme."""
        filepath = os.path.join(self.storage_dir, filename)
        lines = ["ts,iso_time,asset,pair,open,high,low,close,volume,trades_count,venue\n"]
        for c in candles:
            lines.append(f"{c['ts']},{c['iso_time']},{c['asset']},{c['pair']},{c['open']},{c['high']},{c['low']},{c['close']},{c['volume']},{c['trades_count']},{c['venue']}\n")
        
        content = "".join(lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        sha256_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        checksum_path = filepath + ".sha256"
        with open(checksum_path, "w", encoding="utf-8") as f:
            f.write(sha256_hash)

        return sha256_hash

    @staticmethod
    def detect_gaps(candles: List[Dict[str, Any]], expected_step_seconds: int = 300) -> List[Dict[str, Any]]:
        """Erkennt zeitliche Lücken in der Kerzenreihe."""
        gaps = []
        for i in range(1, len(candles)):
            prev_ts = candles[i-1]["ts"]
            cur_ts = candles[i]["ts"]
            diff = cur_ts - prev_ts
            if diff > expected_step_seconds * 1.5:
                gaps.append({
                    "from_ts": prev_ts,
                    "to_ts": cur_ts,
                    "gap_seconds": diff,
                    "missing_candles": int(diff / expected_step_seconds) - 1
                })
        return gaps
