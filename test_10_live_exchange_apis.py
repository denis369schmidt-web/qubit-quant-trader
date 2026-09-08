import sys
import json
import time
import urllib.request

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("🌐 10-EXCHANGE REAL-TIME TELEMETRY MATRIX (MAXIMUM PRECISION)")
print("=" * 80)

exchanges = {
    "Kraken": "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
    "Binance": "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
    "Coinbase": "https://api.coinbase.com/v2/prices/BTC-USD/spot",
    "Bitfinex": "https://api-pub.bitfinex.com/v2/ticker/tBTCUSD",
    "Bybit": "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
    "KuCoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT",
    "OKX": "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
    "Gate.io": "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT",
    "HTX": "https://api.huobi.pro/market/detail/merged?symbol=btcusdt",
    "MEXC": "https://api.mexc.com/api/v3/ticker/price?symbol=BTCUSDT"
}

prices = {}

for name, url in exchanges.items():
    t0 = time.perf_counter_ns()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': '10ExchangeMatrix/2026'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            t1 = time.perf_counter_ns()
            ping_ms = round((t1 - t0) / 1_000_000.0, 1)
            res = json.loads(resp.read().decode('utf-8'))
            
            price = 0.0
            if name == "Kraken":
                price = float(res['result']['XXBTZUSD']['c'][0])
            elif name == "Binance" or name == "MEXC":
                price = float(res['price'])
            elif name == "Coinbase":
                price = float(res['data']['amount'])
            elif name == "Bitfinex":
                price = float(res[6])
            elif name == "Bybit":
                price = float(res['result']['list'][0]['lastPrice'])
            elif name == "KuCoin":
                price = float(res['data']['price'])
            elif name == "OKX":
                price = float(res['data'][0]['last'])
            elif name == "Gate.io":
                price = float(res[0]['last'])
            elif name == "HTX":
                price = float(res['tick']['close'])

            prices[name] = price
            print(f"✅ {name.ljust(12)} API:   ${price:,.2f}  | Latenz: {ping_ms} ms")
    except Exception as e:
        print(f"❌ {name.ljust(12)} API Warning: {e}")

valid_p = {k: v for k, v in prices.items() if v > 0}
if len(valid_p) >= 2:
    min_ex = min(valid_p, key=valid_p.get)
    max_ex = max(valid_p, key=valid_p.get)
    spread = valid_p[max_ex] - valid_p[min_ex]
    spread_pct = (spread / valid_p[min_ex]) * 100.0
    print("=" * 80)
    print(f"🔥 MAXIMUM 10-EXCHANGE ARBITRAGE DELTA: ${spread:,.2f} (+{spread_pct:.4f}%)")
    print(f"🔄 OPTIMALE ROUTE: Kauf bei {min_ex} (${valid_p[min_ex]:,.2f}) ➔ Verkauf bei {max_ex} (${valid_p[max_ex]:,.2f})")

print("=" * 80)
print(f"⏰ ZEITSTEMPEL DER LIFE-MESSUNG: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
