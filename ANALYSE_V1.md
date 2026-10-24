# Analyse Qubit Quant Trader v1 und Konsequenzen für v2

Stand: 24.10.2026. Grundlage: Code, `INCIDENT_REPORT_PNL.md`, `AUDIT_REPORT.md`, `TEST_REPORT.md`,
`edge_research/edge_registry.md`. Die echte Trade-Historie (`trading_ledger.db`) ist per `.gitignore`
nicht im Repo; sobald sie vorliegt, wertet `python -m terminal analyze --file trading_ledger.db` sie aus.

## 1. Was gut war

| Punkt | Warum es gut ist |
|---|---|
| Incident-Report zu Schein-Gewinnen geschrieben und behoben | Fehler offen dokumentiert, FIFO-Buchhaltung mit `Decimal`, Regressionstests auf echten Trades |
| Standardmodus auf PAPER umgestellt | Kein versehentlicher Echtgeld-Handel mehr |
| Hypothesen-Registry mit Abbruchkriterien | Richtige Denkweise: Idee -> Test -> verwerfen oder behalten |
| H3 (Lead-Lag) und H4 (Orderbuch-Imbalance) verworfen | Richtige Schlussfolgerung: Gebühren fressen kleine Kanten |
| Tages-Verlustlimit, Kill-Switch-Gedanke, Order-Lifecycle | Risiko- und Betriebsdenken ist vorhanden |

## 2. Was schlecht war (nach Schwere)

1. **Die einzige "validierte" Strategie (H2, +11,14 %) wurde auf selbst erzeugten Zufallskursen getestet.**
   `run_experiments.py` und `run_pocs.py` rufen `generate_deterministic_dataset(..., seed=101)` auf. Ein Ergebnis
   auf synthetischen Daten sagt nichts über echte Märkte. Zusätzlich: 1.500 5-Minuten-Kerzen sind gut 5 Tage und
   26 Trades sind statistisch Rauschen.
2. **Der Backtester (`backtester_engine.py`) arbeitet ebenfalls nur mit synthetischen Ticks.** Die gemeldete
   OOS-Rendite von +7,29 % ist deshalb ohne Aussagekraft. "0 % Fehlerquote" misst Exceptions, nicht Qualität.
3. **Echte Trades haben durch Gebühren verloren.** Alle vier Fälle im Incident-Report: Kurs fast unverändert,
   Ergebnis = minus Gebühren. Positionen von ca. 2,60 € bis 7,80 € bei Kraken bedeuten: Man braucht mehr als
   die Roundtrip-Kosten an Kursbewegung, nur um bei null zu landen.
4. **Gebühren vermutlich zu niedrig angesetzt.** Code nimmt 0,26 % Taker an, `config.yaml` nennt 0,40 % für Maker.
   Für kleine Konten liegt Kraken Pro typischerweise bei ca. 0,25 % Maker / 0,40 % Taker. Bitte auf der aktuellen
   Kraken-Gebührenseite prüfen; v2 rechnet konservativ mit 0,40 % + Slippage.
5. **"Exit nur mit Gewinn" (PROFIT_EXIT-Gating) ist gefährlich.** Verluste werden nicht realisiert, sondern
   gehalten. Das erhöht die Trefferquote auf dem Papier und vergrößert die Verluste in der Realität.
6. **Kelly-Sizing mit angenommener Gewinnquote und festem Chance-Risiko-Verhältnis 2,0.** Kelly mit geschätzten
   statt gemessenen Werten überschätzt die Positionsgröße systematisch.
7. **Marketing-Sprache im README** ("Guaranteed-Profit", "Institutional-grade"). Garantierte Gewinne gibt es nicht.
8. **Zu viel auf einmal.** 9.000 Zeilen, GUI, Arbitrage, OBI, Kelly, Telegram, aber keine einzige Strategie mit
   nachgewiesenem Vorteil auf echten Daten.

## 3. Was für maximalen Erfolg nötig ist (umgesetzt in v2)

| Regel | Umsetzung in `terminal/` |
|---|---|
| Nur echte Kurse für Bewertungen | `market_data.py` lädt Binance/Bybit-Kerzen, CSV-Cache, Lücken-Check |
| Kosten realistisch und konservativ | `costs.py` Presets pro Börse, Gebühr + Slippage pro Seite |
| Kein Lookahead | `backtest.py`: Signal auf Schlusskurs, Ausführung zur nächsten Eröffnung, Stop pessimistisch |
| Kein Overfitting | `validation.py`: Walk-Forward (Optimieren auf Train, Testen auf ungesehenem Fenster) |
| Glück von Können trennen | Permutationstest: Strategie muss auf echten Daten besser sein als auf gemischten |
| Klare Zulassung | >= 30 Trades, netto positiv, Profit-Faktor >= 1,2, p < 0,05, DD < 25 %, besser als Buy & Hold |
| Märkte wählen, in denen Kosten klein sind | `scanner.py`: Kosten/ATR-Verhältnis über hunderte Paare, Stablecoins/Hebel-Token raus |
| Verluste begrenzen statt aussitzen | Fester Stop pro Trade, 1 % Risiko, Tageslimit 3 %, Kill-Switch bei 15 % Drawdown |
| Seltener, größer handeln | Strategien auf 1h/4h statt 5m, damit die typische Bewegung die Kosten deutlich übersteigt |
| Paper vor Echtgeld | `paper.py` nutzt dieselbe Strategie-Logik; Testnet optional; Echtgeld in v2 nicht eingebaut |

## 4. Realistische Erwartung

Ein Ergebnis wie "50 $ -> 4.378 $ in 3 Tagen" ist kein Ziel, sondern ein Warnsignal (unverifiziert, extremes
Risiko, Survivorship Bias). Ein gutes System für Privatpersonen schlägt nach Kosten Buy & Hold risikobereinigt oder
verliert in Crashs deutlich weniger. Wenn keine Strategie die Hürden besteht, ist das ein korrektes Ergebnis,
kein Fehler des Systems.
