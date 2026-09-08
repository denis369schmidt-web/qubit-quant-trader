# EDGE RESEARCH REGISTRY

Dieses Dokument ist das zentrale Register aller Strategie- und Alpha-Hypothesen für den Qubit Quant Trader.
Jede Hypothese muss vor jeglicher Optimierung registriert werden.

---

## 1. Governance & Zulassungskriterien

1. **Keine isolierten Indikatoren:**
   - Reine Schwellenwerte (z. B. RSI < 30 / > 70, einzelne Z-Score-Ausreißer oder naive Binance-Lead-Lag-Signale ohne Kostennachweis) sind **ausdrücklich als Alpha-Quelle ausgeschlossen**.
2. **Kosten-Hürde:**
   - Ein Signal gilt erst dann als valider Edge-Kandidat, wenn es nach Abzug von:
     - 0,26% Taker-Gebühr (bzw. 0,16% Maker-Gebühr bei nachgewiesener passiver Ausführung)
     - Realistischem Bid-Ask-Spread
     - Arrival-Price-Slippage und Adverse Selection
     - Latenzverzögerung (Market Data + Decision + Exchange Fill)
     signifikant **besser abschneidet als die 4 Benchmark-Baselines**.
3. **Out-of-Sample-Integrität:**
   - Der Out-of-Sample (OOS)-Datensatz wird strikt vor Beginn aller Modellierungs- oder Parameter-Suchläufe fixiert und bleibt bis zur finalen Validierung versiegelt.

---

## 2. Benchmark-Baselines

Alle Edge-Kandidaten müssen gegen folgende 4 standardisierten Baselines antreten (unter identischen Kosten):

| Baseline | Typ | Marktmechanik | Erwartetes Verhalten |
| :--- | :--- | :--- | :--- |
| **B1: Buy-and-Hold Mix** | Passiv | Gleichgewichtetes Halten des EUR-Portfolios in BTC/ETH/SOL/XRP | Marktrendite (Beta); minimaler Gebührenverlust |
| **B2: SMA Crossover (20/50)** | Trendfolge | Kauft bei goldenem Kreuz, hält Cash bei Todeskreuz | Fängt starke Trends ein, leidet in Seitwärtsphasen unter Whipsaws |
| **B3: VWAP Reversion** | Mean Reversion | Kauft bei Auslenkung nach unten (-2 StdAbw), schließt am VWAP | Profitiert in Range-Märkten, leidet bei Ausbrüchen |
| **B4: Spread-Skalp** | Liquiditätsbereitstellung | Platziert limitierte Bids/Asks um den Mid-Price (Maker) | Verdient den Spread, trägt Adverse-Selection-Risiko |

---

## 3. Hypothesen-Register

### Hypothese H-001: Multi-Regime Mean-Reversion mit OBI/CVD-Konvexität
* **ID:** `H-001`
* **Status:** `HYPOTHETISCH` (In Validierung)
* **Marktmechanik:**
  In Konsolidierungsphasen (`RANGE_BOUND`) führt eine vorübergehende Erschöpfung des aggressiven Marktauftragsvolumens (erkennbar an CVD-Absorption an signifikanten Liquiditätslevels) gepaart mit positiver Orderbuch-Imbalance (OBI > 0,15 auf den Top-10 Ticks) zu einer kurzfristigen Rückkehr zum VWAP.
* **Erforderliche Daten:**
  Tick- und L2-Orderbuch-Snapshots mit Zeitstempeln und Volumen für `XBTEUR`, `ETHEUR`, `SOLEUR`, `XRPEUR`.
* **Kostenmodell:**
  Vollständiges Taker-/Maker-Modell mit 0,26% roundtrip-relevantem Fee-Floor + 0,05% variabler Slippage gegen Arrival Price.
* **Pflicht-Out-of-Sample-Plan:**
  60% In-Sample (Train), 20% Kalibrierung/Validation, 20% Out-of-Sample (Blind-Test).
* **Definition „Besser als Baseline“:**
  Out-of-Sample Netto-Sharpe-Ratio > Baseline B3 (VWAP Reversion) um mindestens +0,50 bei geringerem maximalen Drawdown.

---

### Hypothese H-002: Volatilitäts-Kompression & Breakout-Momentum
* **ID:** `H-002`
* **Status:** `HYPOTHETISCH`
* **Marktmechanik:**
  Extrem niedrige ATR über einen Zeitraum von >4 Stunden signalisiert Liquiditätsakkumulation. Ein Durchbruch aus der Bollinger-Bandbreite mit Bestätigung durch ansteigendes Taker-Volumen leitet einen Trendwechsel ein.
* **Erforderliche Daten:**
  5-Minuten- und 1-Minuten-Kerzen inklusive aggregiertem Kauf-/Verkaufsvolumen.
* **Kostenmodell:**
  Reines Taker-Ausführungsmodell (0,26% Entry + 0,26% Exit) + erhöhte Slippage (0,10%) bei Ausbrüchen.
* **Pflicht-Out-of-Sample-Plan:**
  Walk-Forward mit 5 rollenden Fenstern à 30 Tage.
* **Definition „Besser als Baseline“:**
  Profit Factor > 1,35 nach allen Kosten; Übertreffen von Baseline B2 (SMA Crossover).

---

### Ausgeschlossene / Verworfene Hypothesen
* **X-001 (Verworfen):** Isolierter RSI < 30 Einstieg.
  * *Grund:* Historisch belegt, dass in starken Abwärtstrends der RSI über Tage im überverkauften Bereich verharren kann. Führt ohne Regime-Filter zu wiederholten Verlust-Käufen.
* **X-002 (Verworfen):** Naives Lead-Lag-Signal Binance Futures -> Kraken Spot ohne Latenz- und Gebührenabzug.
  * *Grund:* Nach Abzug der 0,26% Taker-Gebühr bei Kraken und der realen Latenz (>80ms über Internet) verpufft der statistische Arbitragevorteil vollständig.
