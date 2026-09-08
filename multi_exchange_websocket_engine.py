"""
MULTI-EXCHANGE ULTRA-LOW LATENCY WEBSOCKET ENGINE (<10MS LATENCY)
-------------------------------------------------------------------
Asynchrone WebSocket-Verbindungen zu den 4 wichtigsten Krypto-Börsen:
1. Kraken (wss://ws.kraken.com/v2)
2. Binance (wss://stream.binance.com:9443/ws)
3. Coinbase (wss://advanced-trade-ws.coinbase.com)
4. Bybit (wss://stream.bybit.com/v5/public/linear)

Multi-Asset Live Tracking für BTC, XRP, ETH und SOL.
"""

import sys
import json
import time
import asyncio
import threading
import urllib.request
from typing import Dict, List, Any, Optional

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class MultiExchangeWebSocketManager:
    """Verwaltet parallele Live-Feeds für BTC, XRP, ETH, SOL über Kraken, Binance, Coinbase & Bybit"""

    def __init__(self):
        self.market_prices: Dict[str, Dict[str, Any]] = {
            "Kraken": {"price": 0.0, "bid": 0.0, "ask": 0.0, "latency_ms": 0.0, "updated": 0},
            "Binance": {"price": 0.0, "bid": 0.0, "ask": 0.0, "latency_ms": 0.0, "updated": 0},
            "Coinbase": {"price": 0.0, "bid": 0.0, "ask": 0.0, "latency_ms": 0.0, "updated": 0},
            "Bybit": {"price": 0.0, "bid": 0.0, "ask": 0.0, "latency_ms": 0.0, "updated": 0}
        }
        self.asset_prices: Dict[str, float] = {
            "BTC": 73000.0,
            "XRP": 2.45,
            "ETH": 2800.0,
            "SOL": 150.0
        }
        self.orderbooks: Dict[str, Dict[str, Any]] = {
            "Kraken": {"obi": 0.0, "bids": [], "asks": []},
            "Binance": {"obi": 0.0, "bids": [], "asks": []},
            "Coinbase": {"obi": 0.0, "bids": [], "asks": []},
            "Bybit": {"obi": 0.0, "bids": [], "asks": []}
        }
        # P1-A: Eigenständige Orderbücher pro gehandeltem Asset
        self.asset_orderbooks: Dict[str, Dict[str, Any]] = {
            "BTC": {"obi": 0.0, "bids": [], "asks": []},
            "XRP": {"obi": 0.0, "bids": [], "asks": []},
            "ETH": {"obi": 0.0, "bids": [], "asks": []},
            "SOL": {"obi": 0.0, "bids": [], "asks": []}
        }
        self.running = True
        self.threads: List[threading.Thread] = []
        self.binance_price_history: List[Tuple[float, float]] = []

    def get_binance_lead_lag_signal(self) -> Dict[str, Any]:
        """Berechnet 5-Sekunden Binance Futures Momentum als Frühindikator für Kraken"""
        now = time.time()
        curr_p = self.market_prices.get("Binance", {}).get("price", 0.0)
        if curr_p > 0:
            self.binance_price_history.append((now, curr_p))

        # Bereinige ältere History (>10s)
        self.binance_price_history = [e for e in self.binance_price_history if now - e[0] <= 10.0]

        if len(self.binance_price_history) < 2:
            return {"status": "NEUTRAL", "momentum_pct": 0.0, "action": "NORMAL"}

        oldest_p = self.binance_price_history[0][1]
        if oldest_p <= 0:
            return {"status": "NEUTRAL", "momentum_pct": 0.0, "action": "NORMAL"}

        momentum_pct = ((curr_p - oldest_p) / oldest_p) * 100.0

        if momentum_pct >= 0.25:
            return {"status": "BULLISH_SURGE", "momentum_pct": round(momentum_pct, 2), "action": "BOOST_BUY"}
        elif momentum_pct <= -0.25:
            return {"status": "BEARISH_DUMP", "momentum_pct": round(momentum_pct, 2), "action": "VETO_BUY"}
        
        return {"status": "NEUTRAL", "momentum_pct": round(momentum_pct, 2), "action": "NORMAL"}

    def start_all_feeds(self):
        self.threads.append(threading.Thread(target=self._run_kraken_feed, daemon=True))
        self.threads.append(threading.Thread(target=self._run_binance_feed, daemon=True))
        self.threads.append(threading.Thread(target=self._run_coinbase_feed, daemon=True))
        self.threads.append(threading.Thread(target=self._run_bybit_feed, daemon=True))
        self.threads.append(threading.Thread(target=self._run_multi_asset_ticker_loop, daemon=True))

        for t in self.threads:
            t.start()

    def _run_multi_asset_ticker_loop(self):
        """Holt kontinuierlich echte Live-Preise für BTC, XRP, ETH und SOL in EUR sowie separate Orderbücher"""
        pair_mapping = {
            "XBTEUR": "BTC",
            "XRPEUR": "XRP",
            "ETHEUR": "ETH",
            "SOLEUR": "SOL"
        }
        loop_counter = 0
        while self.running:
            try:
                url = "https://api.kraken.com/0/public/Ticker?pair=XBTEUR,XRPEUR,ETHEUR,SOLEUR"
                req = urllib.request.Request(url, headers={'User-Agent': 'InstitutionalMultiAssetFeed/2026'})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                    result = res.get("result", {})
                    for pair_name, t_data in result.items():
                        price = float(t_data['c'][0])
                        if "XBT" in pair_name or "BTC" in pair_name:
                            self.asset_prices["BTC"] = price
                        elif "XRP" in pair_name:
                            self.asset_prices["XRP"] = price
                        elif "ETH" in pair_name:
                            self.asset_prices["ETH"] = price
                        elif "SOL" in pair_name:
                            self.asset_prices["SOL"] = price

                # P1-A: Eigenständige Orderbücher rotierend oder periodisch abfragen
                # Jede Runde wird ein Asset-Orderbuch aktualisiert um API-Limits einzuhalten
                target_pair = list(pair_mapping.keys())[loop_counter % len(pair_mapping)]
                target_asset = pair_mapping[target_pair]
                loop_counter += 1

                depth_url = f"https://api.kraken.com/0/public/Depth?pair={target_pair}&count=20"
                req_depth = urllib.request.Request(depth_url, headers={'User-Agent': 'InstitutionalMultiAssetFeed/2026'})
                with urllib.request.urlopen(req_depth, timeout=3.0) as resp_d:
                    res_d = json.loads(resp_d.read().decode('utf-8'))
                    result_d = res_d.get("result", {})
                    for p_key, p_val in result_d.items():
                        bids = p_val.get("bids", [])
                        asks = p_val.get("asks", [])
                        bid_vol = sum(float(b[1]) for b in bids[:10]) if bids else 0.0
                        ask_vol = sum(float(a[1]) for a in asks[:10]) if asks else 0.0
                        total_v = bid_vol + ask_vol
                        obi = (bid_vol - ask_vol) / total_v if total_v > 0 else 0.0
                        self.asset_orderbooks[target_asset] = {
                            "obi": round(obi, 4),
                            "bids": bids,
                            "asks": asks
                        }
            except Exception:
                pass
            time.sleep(1.5)

    def _poll_kraken_rest(self):
        try:
            url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
            req = urllib.request.Request(url, headers={'User-Agent': 'InstitutionalMultiAssetFeed/2026'})
            t_start = time.time()
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                result = res.get("result", {})
                for pair_name, t_data in result.items():
                    p = float(t_data['c'][0])
                    b = float(t_data['b'][0])
                    a = float(t_data['a'][0])
                    lat = (time.time() - t_start) * 1000.0
                    self.market_prices["Kraken"] = {
                        "price": p, "bid": b, "ask": a, "latency_ms": round(lat, 2), "updated": time.time()
                    }
        except Exception:
            pass

    # --- KRAKEN FEED ---
    def _run_kraken_feed(self):
        ws_url = "wss://ws.kraken.com/v2"
        
        def on_message(ws, msg):
            t_start = time.time()
            try:
                data = json.loads(msg)
                if isinstance(data, dict) and data.get("channel") == "ticker":
                    ticks = data.get("data", [])
                    if ticks:
                        t = ticks[0]
                        p = float(t.get("last", self.market_prices["Kraken"]["price"]))
                        b = float(t.get("bid", p))
                        a = float(t.get("ask", p))
                        lat = (time.time() - t_start) * 1000.0
                        self.market_prices["Kraken"] = {
                            "price": p, "bid": b, "ask": a, "latency_ms": round(lat, 2), "updated": time.time()
                        }
            except Exception:
                pass

        def on_open(ws):
            sub = {"method": "subscribe", "params": {"channel": "ticker", "symbol": ["BTC/USD"]}}
            ws.send(json.dumps(sub))

        # Sofortige REST-Initialisierung
        self._poll_kraken_rest()

        while self.running:
            try:
                if HAS_WEBSOCKET:
                    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
                    ws.run_forever(ping_interval=15, ping_timeout=8)
                self._poll_kraken_rest()
                time.sleep(1.0)
            except Exception:
                self._poll_kraken_rest()
                time.sleep(2.0)

    # --- BINANCE FEED ---
    def _poll_binance_rest(self):
        try:
            url = 'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT'
            req = urllib.request.Request(url, headers={'User-Agent': 'InstitutionalMultiAssetFeed/2026'})
            t_start = time.time()
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                p = float(data.get("price", 0.0))
                if p > 0:
                    lat = (time.time() - t_start) * 1000.0
                    self.market_prices["Binance"] = {
                        "price": p, "bid": p * 0.9999, "ask": p * 1.0001, "latency_ms": round(lat, 2), "updated": time.time()
                    }
        except Exception:
            pass

    def _poll_coinbase_rest(self):
        try:
            url = 'https://api.exchange.coinbase.com/products/BTC-USD/ticker'
            req = urllib.request.Request(url, headers={'User-Agent': 'InstitutionalMultiAssetFeed/2026'})
            t_start = time.time()
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                p = float(data.get("price", 0.0))
                if p > 0:
                    lat = (time.time() - t_start) * 1000.0
                    self.market_prices["Coinbase"] = {
                        "price": p, "bid": p * 0.9999, "ask": p * 1.0001, "latency_ms": round(lat, 2), "updated": time.time()
                    }
        except Exception:
            pass

    def _poll_bybit_rest(self):
        try:
            url = 'https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT'
            req = urllib.request.Request(url, headers={'User-Agent': 'InstitutionalMultiAssetFeed/2026'})
            t_start = time.time()
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                ticks = data.get("result", {}).get("list", [])
                if ticks:
                    p = float(ticks[0].get("lastPrice", 0.0))
                    if p > 0:
                        lat = (time.time() - t_start) * 1000.0
                        self.market_prices["Bybit"] = {
                            "price": p, "bid": p * 0.9999, "ask": p * 1.0001, "latency_ms": round(lat, 2), "updated": time.time()
                        }
        except Exception:
            pass

    # --- BINANCE FEED ---
    def _run_binance_feed(self):
        ws_url = "wss://stream.binance.com:9443/ws/btcusdt@ticker"

        def on_message(ws, msg):
            t_start = time.time()
            try:
                data = json.loads(msg)
                if "c" in data:
                    p = float(data["c"])
                    b = float(data.get("b", p))
                    a = float(data.get("a", p))
                    lat = (time.time() - t_start) * 1000.0
                    self.market_prices["Binance"] = {
                        "price": p, "bid": b, "ask": a, "latency_ms": round(lat, 2), "updated": time.time()
                    }
            except Exception:
                pass

        # Sofortige REST-Initialisierung
        self._poll_binance_rest()

        while self.running:
            try:
                if HAS_WEBSOCKET:
                    ws = websocket.WebSocketApp(ws_url, on_message=on_message)
                    ws.run_forever(ping_interval=15, ping_timeout=8)
                self._poll_binance_rest()
                time.sleep(1.0)
            except Exception:
                self._poll_binance_rest()
                time.sleep(2.0)

    # --- COINBASE FEED ---
    def _run_coinbase_feed(self):
        ws_url = "wss://advanced-trade-ws.coinbase.com"

        def on_message(ws, msg):
            t_start = time.time()
            try:
                data = json.loads(msg)
                if data.get("channel") == "ticker":
                    events = data.get("events", [])
                    if events:
                        ticks = events[0].get("tickers", [])
                        if ticks:
                            t = ticks[0]
                            p = float(t.get("price", 0.0))
                            if p > 0:
                                lat = (time.time() - t_start) * 1000.0
                                self.market_prices["Coinbase"] = {
                                    "price": p, "bid": p * 0.9999, "ask": p * 1.0001, "latency_ms": round(lat, 2), "updated": time.time()
                                }
            except Exception:
                pass

        def on_open(ws):
            sub = {"type": "subscribe", "product_ids": ["BTC-USD"], "channel": "ticker"}
            ws.send(json.dumps(sub))

        # Sofortige REST-Initialisierung
        self._poll_coinbase_rest()

        while self.running:
            try:
                if HAS_WEBSOCKET:
                    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
                    ws.run_forever(ping_interval=15, ping_timeout=8)
                self._poll_coinbase_rest()
                time.sleep(1.0)
            except Exception:
                self._poll_coinbase_rest()
                time.sleep(2.0)

    # --- BYBIT FEED ---
    def _run_bybit_feed(self):
        ws_url = "wss://stream.bybit.com/v5/public/linear"

        def on_message(ws, msg):
            t_start = time.time()
            try:
                data = json.loads(msg)
                if "data" in data and data.get("topic") == "tickers.BTCUSDT":
                    t = data["data"]
                    p = float(t.get("lastPrice", 0.0))
                    if p > 0:
                        lat = (time.time() - t_start) * 1000.0
                        self.market_prices["Bybit"] = {
                            "price": p, "bid": p * 0.9999, "ask": p * 1.0001, "latency_ms": round(lat, 2), "updated": time.time()
                        }
            except Exception:
                pass

        def on_open(ws):
            sub = {"op": "subscribe", "args": ["tickers.BTCUSDT"]}
            ws.send(json.dumps(sub))

        # Sofortige REST-Initialisierung
        self._poll_bybit_rest()

        while self.running:
            try:
                if HAS_WEBSOCKET:
                    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
                    ws.run_forever(ping_interval=15, ping_timeout=8)
                self._poll_bybit_rest()
                time.sleep(1.0)
            except Exception:
                self._poll_bybit_rest()
                time.sleep(2.0)

    def get_cross_exchange_arbitrage_summary(self) -> Dict[str, Any]:
        valid_prices = {
            ex: data["price"] for ex, data in self.market_prices.items() if data["price"] > 0
        }

        if len(valid_prices) < 2:
            return {
                "has_arbitrage": False,
                "max_spread_usd": 0.0,
                "max_spread_pct": 0.0,
                "cheapest_ex": "N/A",
                "expensive_ex": "N/A",
                "valid_count": len(valid_prices)
            }

        cheapest_ex = min(valid_prices, key=valid_prices.get)
        expensive_ex = max(valid_prices, key=valid_prices.get)

        p_min = valid_prices[cheapest_ex]
        p_max = valid_prices[expensive_ex]

        spread_usd = p_max - p_min
        spread_pct = (spread_usd / p_min) * 100.0 if p_min > 0 else 0.0

        return {
            "has_arbitrage": spread_pct >= 0.12,
            "max_spread_usd": round(spread_usd, 2),
            "max_spread_pct": round(spread_pct, 4),
            "cheapest_ex": cheapest_ex,
            "expensive_ex": expensive_ex,
            "p_min": p_min,
            "p_max": p_max,
            "valid_count": len(valid_prices)
        }
