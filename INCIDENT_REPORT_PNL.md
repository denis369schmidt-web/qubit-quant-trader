# POST-MORTEM INCIDENT REPORT: PnL & COST BASIS DEFECT REPAIR

**Datum**: 08.09.2026  
**Schweregrad**: P0 (Kritischer Berechnungsfehler im Handelsjournal / Schein-Profit)  
**Status**: BEHOBEN & VERIFIZIERT  
**Komponenten**: `production_quantum_trader_engine.py`, `institutional_trading_core.py`

---

## 1. Executive Summary & Problemstellung

Im Handelsjournal (`trading_ledger.db`) des Qubit Quant Traders wurden bei Verkaufsaufträgen (SELL) scheinbar hohe positive Gewinne verzeichnet (z. B. +8.19 €, +6.52 €, +2.61 €), obwohl die tatsächliche Kursbewegung flach oder negativ war und Börsengebühren anfielen.

### Kernursache (Root Causes)
1. **Künstlicher Einstiegspreis (Fallback `price * 0.995`)**:
   Wenn für ein Asset kein historischer Kaufpreis im In-Memory-Dictionary (`live_entry_prices`) gefunden wurde, setzte die Engine den Kaufpreis auf `live_res["price"] * 0.995`. Jeder Verkauf erzeugte dadurch rechnerisch einen künstlichen Brutto-Gewinn von exakt +0.5% bzw. wies fiktive Gewinne aus.
2. **Umsatzerlös statt Reingewinn**:
   Bei Auswertungen und Einbuchungen wurde der Brutto-Verkaufserlös abzüglich Verkaufsgebühr teilweise als Reingewinn verbucht, ohne die Anschaffungskosten des vorherigen Kaufs und die Kaufgebühr abzuziehen.
3. **Mangelndes Exit-Gating**:
   Signalgesteuerte Verkäufe prüften nicht mathematisch, ob der aktuelle Marktpreis die kumulierten Roundtrip-Taker-Gebühren (0.26% Kauf + 0.26% Verkauf = 0.52%) übersteigt.

---

## 2. Rechnerischer Vorher / Nachher Vergleich an Echtdaten

Untersuchung der konkreten Transaktionen aus `trading_ledger.db`:

| Trade ID | Pair | Side | Preis | Volumen | Gebühr | Alter (falscher) PnL | Neuer (realer) Netto-PnL | Differenz / Schein-Profit |
|---|---|---|---|---|---|---|---|---|
| **#97 / #98** | ETHEUR | BUY / SELL | 2491.30 € | 0.001050 | 0.0068 € je | **+2.61 €** | **-0.013600 €** | **-2.6236 €** |
| **#94 / #96** | SOLEUR | BUY / SELL | 103.82 / 103.76 € | 0.063000 | 0.0170 € je | **+6.52 €** | **-0.037780 €** | **-6.5578 €** |
| **#82 / #86** | SOLEUR | BUY / SELL | 103.83 / 103.84 € | 0.063000 | 0.0170 € je | **+6.52 €** | **-0.033370 €** | **-6.5534 €** |
| **#61 / #64** | SOLEUR | BUY / SELL | 103.86 / 103.86 € | 0.074700 | 0.0202 € je | **+7.74 €** | **-0.040400 €** | **-7.7804 €** |

---

## 3. Implementierte Korrekturmaßnahmen

1. **`CentralAccountingEngine` & FIFO Tax-Lots**:
   - Implementierung in `institutional_trading_core.py` mit `Decimal`-Arithmetik.
   - Formel: $\text{Net PnL} = \text{Gross Proceeds} - \text{Sell Fee} - (\text{Allocated Cost Basis} + \text{Allocated Buy Fee})$.
   - Persistente Speicherung offener Tax-Lots in SQLite-Tabelle `open_lots`.
2. **Behandlung unbekannter Anschaffungskosten**:
   - Falls keine Kauf-Lots zugeordnet werden können, liefert die Engine `UNKNOWN_COST_BASIS` und `net_pnl = None`.
   - Das Erfinden künstlicher Margen (`0.995`) wurde vollständig entfernt.
3. **Exit-Gating (PROFIT_EXIT vs. RISK_EXIT)**:
   - Verkäufe aus Gewinnmitnahme (`PROFIT_EXIT`) werden im `MultiAssetWalletAllocator` nur dann freigegeben, wenn der Kurs die Bedingung `price >= entry_p * (1.0 + roundtrip_fee_pct + min_net_profit_pct)` erfüllt.
   - Notfall-Stopps (`RISK_EXIT`) sind separat typisiert und lösen explizite Schutzreaktionen aus.
4. **Order-Lifecycle-Tracking**:
   - `OrderLifecycleTracker` überwacht jeden Intent von `INTENT_CREATED` über `SUBMITTED` bis `FILLED` oder `REJECTED`.

---

## 4. Regressions-Nachweis

Die Regressions-Testsuite `tests/test_pnl_regression.py` prüft alle Fälle A, B, C und D deterministisch:
- `test_case_a_eth_flat_price`: PASS (-0.013600 €)
- `test_case_b_sol_loss`: PASS (-0.037780 €)
- `test_case_c_sol_sub_fee_gain`: PASS (-0.033370 €)
- `test_case_d_sol_flat_fee`: PASS (-0.040400 €)
- `test_fifo_partial_lot_closing`: PASS (FIFO-Teillose mit anteiliger Gebührenallokation)
- `test_unknown_cost_basis_rejection`: PASS (Ablehnung fiktiver Gewinne)
- `test_exit_gating_blocks_unprofitable_sale`: PASS (Verhinderung unprofitabler Exits)
