"""
QUBIT TERMINAL v2
-----------------
Ehrlicher Neuaufbau auf Basis der Fehleranalyse von v1 (siehe ANALYSE_V1.md):

- Echte Marktdaten statt synthetischer Kurse für jede Strategie-Bewertung
- Realistische Kosten (Gebühr + Slippage) pro Seite
- Kein Lookahead: Signal auf geschlossener Kerze, Ausführung zur nächsten Eröffnung
- Walk-Forward + Permutationstest + Benchmark (Buy & Hold) als Pflicht-Hürden
- Paper-Trading als Standard, Testnet optional, Echtgeld standardmäßig gesperrt
"""

__version__ = "2.0.0"
