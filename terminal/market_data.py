"""
Echte Marktdaten von öffentlichen Börsen-APIs (kein API-Key nötig) + CSV-Cache.

Binance: /api/v3/klines, /api/v3/ticker/24hr, /api/v3/ticker/bookTicker
Bybit:   /v5/market/kline, /v5/market/tickers
"""

import csv
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
BYBIT_INTERVALS = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}


@dataclass
class Candles:
    symbol: str
    interval: str
    ts: np.ndarray       # Eröffnungszeit in Sekunden (UTC)
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray   # Basis-Volumen

    def __len__(self) -> int:
        return len(self.close)

    def slice(self, start: int, end: int) -> "Candles":
        return Candles(self.symbol, self.interval, self.ts[start:end], self.open[start:end],
                       self.high[start:end], self.low[start:end], self.close[start:end],
                       self.volume[start:end])

    @classmethod
    def from_rows(cls, symbol: str, interval: str, rows: List[List[float]]) -> "Candles":
        rows = sorted({int(r[0]): r for r in rows}.values(), key=lambda r: r[0])
        arr = np.array(rows, dtype=float).reshape(-1, 6)
        return cls(symbol, interval, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4], arr[:, 5])

    def gaps(self) -> int:
        """Anzahl Zeitsprünge > 1,5 × Intervall (Datenlücken)."""
        if len(self.ts) < 2:
            return 0
        return int(np.sum(np.diff(self.ts) > 1.5 * INTERVAL_SECONDS[self.interval]))


def _get_json(url: str, params: Dict[str, str], timeout: float = 15.0):
    full = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    req = urllib.request.Request(full, headers={"User-Agent": "QubitTerminal/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class BinancePublic:
    BASE = "https://api.binance.com"

    def klines(self, symbol: str, interval: str, start_ts: int, end_ts: Optional[int] = None) -> Candles:
        end_ts = end_ts or int(time.time())
        rows: List[List[float]] = []
        cursor = start_ts * 1000
        while cursor < end_ts * 1000:
            batch = _get_json(f"{self.BASE}/api/v3/klines", {
                "symbol": symbol, "interval": interval, "startTime": str(cursor),
                "endTime": str(end_ts * 1000), "limit": "1000"})
            if not batch:
                break
            rows += [[b[0] / 1000, b[1], b[2], b[3], b[4], b[5]] for b in batch]
            cursor = int(batch[-1][0]) + INTERVAL_SECONDS[interval] * 1000
            time.sleep(0.2)
        return Candles.from_rows(symbol, interval, rows)

    def market_snapshot(self, quote: str = "USDT") -> List[Dict[str, float]]:
        """24h-Statistik + bestes Bid/Ask für alle Spot-Paare mit der gewünschten Quote-Währung."""
        stats = _get_json(f"{self.BASE}/api/v3/ticker/24hr", {})
        books = {b["symbol"]: b for b in _get_json(f"{self.BASE}/api/v3/ticker/bookTicker", {})}
        out = []
        for s in stats:
            sym = s["symbol"]
            if not sym.endswith(quote) or sym not in books:
                continue
            bid, ask = float(books[sym]["bidPrice"]), float(books[sym]["askPrice"])
            if bid <= 0 or ask <= 0:
                continue
            out.append({"symbol": sym, "quote_volume": float(s["quoteVolume"]), "bid": bid, "ask": ask,
                        "last": float(s["lastPrice"]), "change_pct": float(s["priceChangePercent"])})
        return out


class BybitPublic:
    BASE = "https://api.bybit.com"

    def klines(self, symbol: str, interval: str, start_ts: int, end_ts: Optional[int] = None) -> Candles:
        end_ts = end_ts or int(time.time())
        rows: List[List[float]] = []
        cursor_end = end_ts * 1000
        while cursor_end > start_ts * 1000:
            res = _get_json(f"{self.BASE}/v5/market/kline", {
                "category": "spot", "symbol": symbol, "interval": BYBIT_INTERVALS[interval],
                "start": str(start_ts * 1000), "end": str(cursor_end), "limit": "1000"})
            batch = res.get("result", {}).get("list", [])
            if not batch:
                break
            rows += [[int(b[0]) / 1000, b[1], b[2], b[3], b[4], b[5]] for b in batch]
            oldest = min(int(b[0]) for b in batch)
            if oldest >= cursor_end:
                break
            cursor_end = oldest - 1
            time.sleep(0.2)
        return Candles.from_rows(symbol, interval, rows)

    def market_snapshot(self, quote: str = "USDT") -> List[Dict[str, float]]:
        res = _get_json(f"{self.BASE}/v5/market/tickers", {"category": "spot"})
        out = []
        for t in res.get("result", {}).get("list", []):
            sym = t["symbol"]
            if not sym.endswith(quote):
                continue
            bid, ask = float(t.get("bid1Price") or 0), float(t.get("ask1Price") or 0)
            if bid <= 0 or ask <= 0:
                continue
            out.append({"symbol": sym, "quote_volume": float(t.get("turnover24h") or 0), "bid": bid,
                        "ask": ask, "last": float(t["lastPrice"]),
                        "change_pct": float(t.get("price24hPcnt") or 0) * 100.0})
        return out


EXCHANGES = {"binance": BinancePublic, "bybit": BybitPublic}


def cache_path(cache_dir: str, exchange: str, symbol: str, interval: str) -> str:
    return os.path.join(cache_dir, f"{exchange}_{symbol}_{interval}.csv")


def save_csv(candles: Candles, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for i in range(len(candles)):
            w.writerow([int(candles.ts[i]), candles.open[i], candles.high[i], candles.low[i],
                        candles.close[i], candles.volume[i]])


def load_csv(path: str, symbol: str = "", interval: str = "1h") -> Candles:
    with open(path, newline="") as f:
        rows = [[float(r["ts"]), float(r["open"]), float(r["high"]), float(r["low"]),
                 float(r["close"]), float(r["volume"])] for r in csv.DictReader(f)]
    return Candles.from_rows(symbol or os.path.basename(path), interval, rows)


def get_candles(exchange: str, symbol: str, interval: str, days: int,
                cache_dir: str = "fetched_data") -> Candles:
    """Lädt Kerzen mit CSV-Cache. Nur fehlende neuere Kerzen werden nachgeladen."""
    path = cache_path(cache_dir, exchange, symbol, interval)
    start_ts = int(time.time()) - days * 86400
    client = EXCHANGES[exchange]()
    if os.path.exists(path):
        cached = load_csv(path, symbol, interval)
        if len(cached) and cached.ts[0] <= start_ts + INTERVAL_SECONDS[interval]:
            fresh = client.klines(symbol, interval, int(cached.ts[-1]))
            rows = [[cached.ts[i], cached.open[i], cached.high[i], cached.low[i], cached.close[i],
                     cached.volume[i]] for i in range(len(cached))]
            rows += [[fresh.ts[i], fresh.open[i], fresh.high[i], fresh.low[i], fresh.close[i],
                      fresh.volume[i]] for i in range(len(fresh))]
            merged = Candles.from_rows(symbol, interval, rows)
            save_csv(merged, path)
            return merged.slice(int(np.searchsorted(merged.ts, start_ts)), len(merged))
    candles = client.klines(symbol, interval, start_ts)
    save_csv(candles, path)
    return candles


def drop_unclosed(candles: Candles, now: Optional[float] = None) -> Candles:
    """Entfernt die noch laufende (nicht geschlossene) letzte Kerze."""
    now = now or time.time()
    if len(candles) and candles.ts[-1] + INTERVAL_SECONDS[candles.interval] > now:
        return candles.slice(0, len(candles) - 1)
    return candles
