# DATENQUELLEN-REGISTRY (DATA SOURCES REGISTRY)

Dokumentiert alle Datenquellen für das quantitative Research, Backtesting und die Walk-Forward-Validierung.
Datum der Erfassung: 2026-09-08
Schema-Version: 1.0.0

---

## 1. Primäre Datenquellen

### DS-01: Kraken Public REST API (OHLCVT & Trades)
- **Quelle:** `https://api.kraken.com/0/public/OHLC` und `/0/public/Trades`
- **Granularität:** 1m, 5m, 15m, 1h, 1d (OHLCV) sowie Ticks (Recent Trades, max. 1000 pro Aufruf)
- **Volumen:** Vollständiges Tick- und Kerzenvolumen
- **Lizenz:** Public API (Rate-Limits beachten, ca. 1 Req/sec)
- **Aktualisierung:** Kontinuierlich / Polling
- **Bekannte Lücken & Einschränkungen:**
  - OHLC-Endpunkt liefert standardmäßig nur die letzten 720 Intervalle.
  - Historische Trades erfordern sequentielles Paging über den `since`-Parameter.
  - L2-Orderbuchhistorie ist über REST nicht historisch abrufbar (nur Live-Snapshots bis 500 Ticks Tiefe).

### DS-02: CryptoDataDownload (CDD Archive)
- **Quelle:** CryptoDataDownload (Kraken EUR Pairs)
- **Granularität:** 1m und 1d Kerzen
- **Volumen:** Trade-Volumen in Quote- und Base-Währung
- **Lizenz:** Freie akademische/private Nutzung
- **Aktualisierung:** Täglich archiviert
- **Bekannte Lücken & Einschränkungen:**
  - Keine Orderbuch-Tiefe (kein OBI/CVD).
  - Gelegentliche Zeitstempel-Lücken bei Börsenwartungen.

### DS-03: Synthetischer Deterministischer Replay-Generator (Lokales Benchmark)
- **Quelle:** Deterministische Generierung (GBM + Jump Diffusion + Regime-Shocks)
- **Zweck:** Deterministische Regressionstests und Verifikation der Algorithmenlogik ohne Netzwerkabrufe.
- **Prüfsummen:** SHA-256 Hashes pro generiertem Snapshot.

---

## 2. Bewertung der Datenverfügbarkeit pro Asset (EUR-Basis)

| Asset | Paar | Granularität | Status Verfügbarkeit | Datenqualität & Lücken | Empfehlung für Forschung |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bitcoin** | `XBTEUR` | 1m, 5m, 1h | **AUSREICHEND** (Kerzen) / **UNZUREICHEND** (L2 Tick Orderbuch) | Kerzenhistorie vollständig; Orderbuch-Historie nur live streamend | Kerzen-Strategien zulässig; Mikrostruktur nur mit Forward-Paper |
| **Ethereum** | `ETHEUR` | 1m, 5m, 1h | **AUSREICHEND** (Kerzen) / **UNZUREICHEND** (L2 Tick Orderbuch) | Liquide, konsistente Spreads; Lücken bei Flash-Crashes | Geeignet für Trend- und Mean-Reversion |
| **Solana** | `SOLEUR` | 1m, 5m, 1h | **AUSREICHEND** (Kerzen) / **UNZUREICHEND** (L2 Tick Orderbuch) | Erst ab 2021 gelistet; Netzwerk-Outages in 2022/2023 | Stress-Test-Kandidat für Volatilitätsschocks |
| **Ripple** | `XRPEUR` | 1m, 5m, 1h | **AUSREICHEND** (Kerzen) / **UNZUREICHEND** (L2 Tick Orderbuch) | Stark eventgetrieben (SEC-Gerichtsentscheide); Spread-Spikes | Geeignet für Event- und Breakout-Forschung |

---

## 3. Daten-Audit- & Checksummen-Protokoll

Jeder in `fetched_data/` abgelegte Datensatz muss folgende Metadaten aufweisen:
1. Dateiname: `{pair}_{timeframe}_{start_date}_{end_date}.csv`
2. SHA-256 Prüfsumme
3. Anzahl Zeilen & Lücken-Check (Zeitsprung > 1.5 * Intervall)
4. Out-of-Sample Blockversiegelung
