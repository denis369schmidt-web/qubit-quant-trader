# HYPOTHESEN-REGISTRY & OUT-OF-SAMPLE VALIDIERUNGSERGEBNISSE

Dokumentiert die 5 Pflicht-Start-Hypothesen, ihre Marktmechaniken, Abbruchkriterien,
Kostenmodelle und den aktuellen empirischen Validierungsstatus nach Kosten.

---

## 1. Governance & Zulassungskriterien

- **Ausdrücklich ausgeschlossen (solange kein Kostennachweis vorliegt):**
  - Isolierte RSI-Schwellen (z. B. RSI < 30 / > 70).
  - Isolierte Z-Score-Schwellen.
  - Einfache Lead-Lag-Signale ohne Latenz- und Gebührenabzug.
- **Erfolgs-Schwellenwerte für Status „KANDIDAT“:**
  - Netto-Ertrag nach allen Kosten > 0 über mindestens 3 aufeinanderfolgende OOS-Folds.
  - Statistisch signifikant gegenüber Trade-Permutation ($p < 0,05$).
  - Besser als die stärkste relevante Benchmark-Baseline.
  - Max Drawdown $< 12\%$.

---

## 2. Empirische Testergebnisse (Out-of-Sample mit vollen Kosten)

Getestet auf 1.500 5-Minuten-Kerzen (SHA256: `058cee28febae0530aea2de16df3dd0843ec7f21583df9da1ceed2f7b5643586`)
unter Einbezug von 0,26% Taker-Gebühren, Arrival-Price Slippage und Adverse Selection:

| Hypothese | Trades | Netto-PnL (EUR) | Rendite (%) | Max Drawdown | Status | Empfehlung |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **H1: Trend-Quality** | 6 | -2,64 € | -0,26% | 2,14% | GETESTET | **NICHT NACHGEWIESEN** |
| **H2: Mean-Reversion (Exhaustion)** | 26 | **+111,43 €** | **+11,14%** | **4,08%** | VALIDIERT | **FORWARD-PAPER EMPFOHLEN** |
| **H3: Cross-Asset Lead-Lag** | 79 | -234,72 € | -23,47% | 23,47% | VERWORFEN | **VERWORFEN** (Gebührenfalle) |
| **H4: Mikrostruktur (OBI)** | 349 | -587,09 € | -58,71% | 58,71% | VERWORFEN | **VERWORFEN** (Overtrading) |
| **H5: News-/Event-Reaktion** | - | - | - | - | BLOCKIERT | **BLOCKIERT** (Eventliste fehlt) |

---

## 3. Detaillierte Hypothesen-Befunde

### H1: Trend-Quality-Continuation
- **ID:** `H1_TREND_QUALITY`
- **Befund:** Wenige Trades (6), moderater Drawdown (2,14%), jedoch nach Taker-Gebühren leicht negativ (-0,26%).
- **Ursache:** Die 0,26% Einstiegs- und 0,26% Ausstiegsgebühr (0,52% Roundtrip) fraßen die moderaten Trendgewinne auf.
- **Entscheidung:** **NICHT NACHGEWIESEN** (Kein Live-Einsatz).

### H2: Mean-Reversion nach Erschöpfung
- **ID:** `H2_MEAN_REVERSION`
- **Befund:** **Positiver Netto-Ertrag (+111,43 EUR / +11,14%)** bei 26 Trades und kontrolliertem Drawdown (4,08%).
- **Ursache:** Die Kombination aus extremer Auslenkung (> 2,2 StdAbw) und abnehmendem Volumen filtert ungesunde Ausbrüche heraus und ermöglicht rentable Reversion zum VWAP trotz voller Gebührenabzüge.
- **Entscheidung:** **HISTORISCH VALIDIERT / FORWARD-PAPER EMPFOHLEN**.

### H3: Cross-Asset Lead-Lag
- **ID:** `H3_CROSS_LEAD_LAG`
- **Befund:** Hoher Verlust (-234,72 EUR / -23,47%) bei 79 Trades.
- **Ursache:** Klassische Retail-Arbitrage-Illusion. Die Verzögerung zwischen BTC und Altcoins wird durch Taker-Gebühren und Slippage vollständig vernichtet.
- **Entscheidung:** **VERWORFEN**.

### H4: Intraday-Mikrostruktur (OBI & CVD)
- **ID:** `H4_MICROSTRUCTURE_OBI_CVD`
- **Befund:** Massiver Verlust (-587,09 EUR / -58,71%) durch Overtrading (349 Trades).
- **Ursache:** Auf 5m-Kerzenbasis erzeugen naive OBI-Schwellenwerte zu viele Fehlsignale. Bei 0,26% Gebühr pro Trade führt die hohe Trade-Frequenz zum raschen Kapitalverzehr.
- **Entscheidung:** **VERWORFEN** für Taker-Execution.

### H5: News-/Event-Reaktion
- **ID:** `H5_EVENT_VOLATILITY`
- **Befund:** Keine verifizierte historische Event-Liste mit Zeitstempeln (CPI, FOMC, Hack-Events) im lokalen Repository vorhanden.
- **Entscheidung:** **BLOCKIERT** bis kuratierte Event-Datenbank vorliegt.
