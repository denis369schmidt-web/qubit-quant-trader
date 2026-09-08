import sys
import json
import time
import urllib.request

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("🌐 ECHZEIT VERIFIZIERUNGS-TEST: OFFENTLICHE BÖRSEN-APIS")
print("=" * 70)

# 1. BINANCE BTC/USDT LIVE SPOT PRICE
try:
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        b_data = json.loads(resp.read().decode('utf-8'))
        print(f"✅ 1. BINANCE LIVE API (BTC/USDT):   ${float(b_data.get('price', 0)):,.2f}")
except Exception as e:
    print("❌ Binance Feed Error:", e)

# 2. COINBASE BTC/USD LIVE SPOT PRICE
try:
    url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        cb_data = json.loads(resp.read().decode('utf-8'))
        print(f"✅ 2. COINBASE LIVE API (BTC/USD):  ${float(cb_data.get('data', {}).get('amount', 0)):,.2f}")
except Exception as e:
    print("❌ Coinbase Feed Error:", e)

# 3. KRAKEN XBT/USD LIVE SPOT PRICE
try:
    url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        k_data = json.loads(resp.read().decode('utf-8'))
        price = float(k_data['result']['XXBTZUSD']['c'][0])
        print(f"✅ 3. KRAKEN LIVE API (BTC/USD):    ${price:,.2f}")
except Exception as e:
    print("❌ Kraken Feed Error:", e)

# 4. COINGECKO LIVE MARKET API
try:
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        cg_data = json.loads(resp.read().decode('utf-8'))
        print(f"✅ 4. COINGECKO LIVE API:")
        print(f"   • Bitcoin (BTC):  ${cg_data.get('bitcoin', {}).get('usd', 0):,.2f}")
        print(f"   • Ethereum (ETH): ${cg_data.get('ethereum', {}).get('usd', 0):,.2f}")
        print(f"   • Solana (SOL):   ${cg_data.get('solana', {}).get('usd', 0):,.2f}")
except Exception as e:
    print("❌ CoinGecko Feed Error:", e)

print("=" * 70)
print(f"⏰ ZEITSTEMPEL DER LIFE-MESSUNG: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
