import os
import sys
import json
import time
import urllib.request

# Enable UTF-8 Output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("🔍 DIAGNOSE: KRAKEN BÖRSEN-VERBINDUNGSPROFUNG")
print("=" * 70)

# 1. PING TEST ZUR OFFIZIELLEN KRAKEN API
t_start = time.perf_counter_ns()
kraken_time_url = "https://api.kraken.com/0/public/Time"
kraken_ticker_url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"

try:
    req = urllib.request.Request(kraken_time_url, headers={'User-Agent': 'KrakenDiagnosticBot/1.0'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        t_end = time.perf_counter_ns()
        ping_ms = round((t_end - t_start) / 1_000_000.0, 2)
        time_data = json.loads(resp.read().decode('utf-8'))
        server_time_str = time_data.get('result', {}).get('rfc1123', 'Unbekannt')
        print(f"✅ 1. KRAKEN PING TEST:          ONLINE (HTTP {resp.status})")
        print(f"   • Latenzzeit:                 {ping_ms} ms")
        print(f"   • Kraken Server-Zeit:         {server_time_str}")
except Exception as e:
    print(f"❌ 1. KRAKEN PING TEST FEHLER:   {e}")

# 2. MARKTDATEN & PREISFEEDS
try:
    req = urllib.request.Request(kraken_ticker_url, headers={'User-Agent': 'KrakenDiagnosticBot/1.0'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        ticker_data = json.loads(resp.read().decode('utf-8'))
        btc_price = float(ticker_data['result']['XXBTZUSD']['c'][0])
        ask_price = float(ticker_data['result']['XXBTZUSD']['a'][0])
        bid_price = float(ticker_data['result']['XXBTZUSD']['b'][0])
        volume_24h = float(ticker_data['result']['XXBTZUSD']['v'][1])
        print(f"\n✅ 2. KRAKEN MARKT-TELEMETRIE:")
        print(f"   • Live BTC/USD Spot:          ${btc_price:,.2f}")
        print(f"   • Highest Bid:                ${bid_price:,.2f}")
        print(f"   • Lowest Ask:                 ${ask_price:,.2f}")
        print(f"   • 24h Handelssumme (BTC):     {volume_24h:,.2f} BTC")
except Exception as e:
    print(f"❌ 2. MARKT-TELEMETRIE FEHLER:   {e}")

# 3. PRÜFUNG DES PRIVATE API KEY STATUS IN DEN UMGEBUNGSVARIABLEN
kraken_key = os.environ.get("KRAKEN_API_KEY", "")
kraken_secret = os.environ.get("KRAKEN_API_SECRET", "")

print(f"\n✅ 3. PRIVATE KEY STATUS (UMGEBUNG):")
if kraken_key and kraken_secret:
    print(f"   • Status:                     🔑 VERBINDEN (Key geladen: {kraken_key[:6]}...)")
else:
    print(f"   • Status:                     ℹ️ Keine privaten Keys im System-Environment hinterlegt.")
    print(f"   • Anhebung über GUI:         Klicke im GUI-Fenster auf den Button '🟣 Kraken'")

print("=" * 70)
print(f"⏰ ZEITSTEMPEL DER PRÜFUNG: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
