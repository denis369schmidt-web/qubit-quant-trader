"""
HTML5 INTERACTIVE EQUITY & PERFORMANCE REPORT GENERATOR
--------------------------------------------------------
Generiert ein hochmodernes, interaktives HTML5/Chart.js Performance-Dashboard
direkt aus der lokalen SQLite-Datenbank (trading_ledger.db).
"""

import os
import sqlite3
import json
import webbrowser
from typing import Dict, List, Any


class HTML5EquityVisualizer:
    @staticmethod
    def generate_html_report(db_path: str = "trading_ledger.db", output_path: str = "trading_performance_report.html") -> str:
        trades = []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, timestamp, pair, side, price, volume, fee_eur, pnl_eur, txid, status FROM trades ORDER BY id ASC")
            trades = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception:
            trades = []

        # Berechne Equity-Kurve & Metriken
        timestamps = []
        equity_points = []
        pnl_points = []
        running_pnl = 0.0
        winning_trades = 0
        losing_trades = 0
        total_fees = 0.0

        for t in trades:
            pnl = float(t.get("pnl_eur", 0.0))
            fee = float(t.get("fee_eur", 0.0))
            running_pnl += pnl
            total_fees += fee

            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1

            timestamps.append(f"{t.get('timestamp', '')} (#{t.get('id', '')})")
            equity_points.append(round(running_pnl, 2))
            pnl_points.append(round(pnl, 2))

        total_trades = len(trades)
        win_rate = (winning_trades / max(total_trades, 1)) * 100.0

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Qubit Quant Trader - Performance Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-card: #151c2c;
            --border: #232f48;
            --accent-green: #00ff88;
            --accent-blue: #38bdf8;
            --accent-red: #f43f5e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            margin: 0;
            color: var(--accent-green);
            font-size: 24px;
        }}
        .header .badge {{
            background: #064e3b;
            color: #34d399;
            padding: 6px 14px;
            border-radius: 9999px;
            font-weight: bold;
            font-size: 13px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
        }}
        .card .title {{
            color: var(--text-muted);
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .card .value {{
            font-size: 26px;
            font-weight: bold;
            font-family: "Consolas", monospace;
        }}
        .value.green {{ color: var(--accent-green); }}
        .value.blue {{ color: var(--accent-blue); }}
        .value.red {{ color: var(--accent-red); }}
        .chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--accent-blue);
            background: #111827;
        }}
        .side-buy {{ color: var(--accent-green); font-weight: bold; }}
        .side-sell {{ color: var(--accent-red); font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>⚡ QUBIT QUANT TRADER - PERFORMANCE REPORT</h1>
            <p style="color: var(--text-muted); margin: 4px 0 0 0;">Vollautonomes Handelsjournal & Mathematische Performancemetriken</p>
        </div>
        <div class="badge">LIVE KRAKEN REBALANCING AKTIV</div>
    </div>

    <div class="metrics-grid">
        <div class="card">
            <div class="title">GESAMT REALISIERTE NETTO-PNL</div>
            <div class="value {'green' if running_pnl >= 0 else 'red'}">{running_pnl:+.2f} €</div>
        </div>
        <div class="card">
            <div class="title">GESAMTE TRADES</div>
            <div class="value blue">{total_trades}</div>
        </div>
        <div class="card">
            <div class="title">TREFFERQUOTE (WIN-RATE)</div>
            <div class="value green">{win_rate:.1f}%</div>
        </div>
        <div class="card">
            <div class="title">GEZAHLTE BÖRSENGEBÜHREN</div>
            <div class="value red">{total_fees:.4f} €</div>
        </div>
    </div>

    <div class="chart-container">
        <h3 style="margin-top: 0; color: var(--accent-blue);">📈 Kumulierte Equity- & PnL-Entwicklung (€)</h3>
        <canvas id="equityChart" height="90"></canvas>
    </div>

    <div class="card">
        <h3 style="margin-top: 0; color: var(--accent-blue);">📜 Letzte Ausgeführte Trades</h3>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Zeit</th>
                    <th>Paar</th>
                    <th>Typ</th>
                    <th>Preis</th>
                    <th>Volumen</th>
                    <th>Gebühr</th>
                    <th>Netto-PnL</th>
                    <th>Status / TXID</th>
                </tr>
            </thead>
            <tbody>
"""
        for t in reversed(trades[-50:]):
            side = t.get("side", "")
            side_cls = "side-buy" if side == "BUY" else "side-sell"
            pnl_val = float(t.get("pnl_eur", 0.0))
            pnl_cls = "side-buy" if pnl_val >= 0 else "side-sell"
            html_content += f"""
                <tr>
                    <td>#{t.get('id', '')}</td>
                    <td>{t.get('timestamp', '')}</td>
                    <td><strong>{t.get('pair', '')}</strong></td>
                    <td class="{side_cls}">{side}</td>
                    <td>{float(t.get('price', 0)):,.2f} €</td>
                    <td>{float(t.get('volume', 0)):.6f}</td>
                    <td>{float(t.get('fee_eur', 0)):.4f} €</td>
                    <td class="{pnl_cls}">{pnl_val:+.2f} €</td>
                    <td style="font-family: monospace; font-size: 12px;">{t.get('status', '')}</td>
                </tr>
"""

        html_content += f"""
            </tbody>
        </table>
    </div>

    <script>
        const ctx = document.getElementById('equityChart').getContext('2d');
        const labels = {json.dumps(timestamps)};
        const equityData = {json.dumps(equity_points)};

        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels.length > 0 ? labels : ['Start'],
                datasets: [{{
                    label: 'Kumulierte Netto-PnL (€)',
                    data: equityData.length > 0 ? equityData : [0],
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.25
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    x: {{
                        grid: {{ color: '#1e293b' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    y: {{
                        grid: {{ color: '#1e293b' }},
                        ticks: {{ color: '#94a3b8' }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return os.path.abspath(output_path)

    @staticmethod
    def open_report_in_browser(db_path: str = "trading_ledger.db"):
        path = HTML5EquityVisualizer.generate_html_report(db_path)
        webbrowser.open(f"file://{path}")
        return path
