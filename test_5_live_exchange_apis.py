import sys
import json
import time
import urllib.request

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 75)
print("🌐 MULTI-EXCHANGE REAL-TIME TELEMETRY VERIFICATION (5 BÖRSEN-APIS)")
print("=" * 75)

exchanges = {
    "Kraken": "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
    "Binance": "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
    "Coinbase": "https://api.coinbase.com/v2/prices/BTC-USD/spot",
    "Bitfinex": "https://api-pub.bitfinex.com/v2/ticker/tBTCUSD",
    "Bybit": "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT"
}

for name, url in exchanges.items():
    t0 = time.perf_counter_ns()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'MultiExchangeBot/2026'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            t1 = time.perf_counter_ns()
            ping_ms = round((t1 - t0) / 1_000_000.0, 2)
            data = json.loads(resp.read().decode('utf-8'))
            
            price = 0.0
            if name == "Kraken":
                price = float(data['result']['XXBTZUSD']['c'][0])
            elif name == "Binance":
                price = float(data['price'])
            elif name == "Coinbase":
                price = float(data['data']['amount'])
            elif name == "Bitfinex":
                price = float(data[6])  # Last price in array
            elif name == "Bybit":
                price = float(data['result']['list'][0]['lastPrice'])

            print(f"✅ {name.ljust(12)} API:   ${price:,.2f}  | Latenz: {ping_ms} ms")
    except Exception as e:
        print(f"❌ {name.ljust(12)} API Error: {e}")

print("=" * 75)
print(f"⏰ ZEITSTEMPEL DER ECHTZET-MESSUNG: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 75)
