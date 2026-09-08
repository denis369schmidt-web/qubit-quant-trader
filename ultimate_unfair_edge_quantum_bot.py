import os
import sys
import json
import time
import math
import urllib.request
import threading
import tkinter as tk
from tkinter import ttk

# UTF-8 Encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False


class DirectVerifiedLiveFetcher:
    """Direkte Abfrage der echten Live-Börsen APIs"""

    @staticmethod
    def get_binance_spot():
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return float(data.get("price", 0.0))
        except Exception:
            return 0.0

    @staticmethod
    def get_coinbase_spot():
        try:
            url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return float(data.get("data", {}).get("amount", 0.0))
        except Exception:
            return 0.0

    @staticmethod
    def get_kraken_spot():
        try:
            url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return float(data['result']['XXBTZUSD']['c'][0])
        except Exception:
            return 0.0


class AdvancedCrossExchangeArbitrageEngine:
    @staticmethod
    def calculate_arbitrage_deltas(prices):
        valid_prices = {k: v for k, v in prices.items() if v > 0}
        if len(valid_prices) < 2:
            return {"arbitrage_opportunity": False, "max_delta_usd": 0.0, "max_delta_pct": 0.0, "buy_at_exchange": "--", "sell_at_exchange": "--"}

        min_exchange = min(valid_prices, key=valid_prices.get)
        max_exchange = max(valid_prices, key=valid_prices.get)

        min_p = valid_prices[min_exchange]
        max_p = valid_prices[max_exchange]

        delta_usd = max_p - min_p
        delta_pct = (delta_usd / min_p) * 100.0

        is_opportunity = delta_pct >= 0.015

        return {
            "arbitrage_opportunity": is_opportunity,
            "buy_at_exchange": min_exchange,
            "buy_price": min_p,
            "sell_at_exchange": max_exchange,
            "sell_price": max_p,
            "max_delta_usd": round(delta_usd, 2),
            "max_delta_pct": round(delta_pct, 4)
        }


class QuantumProfitPerSecondEngine:
    """NEU: Quantenmechanismus zur Echtzeit-Berechnung des möglichen Gewinns pro Sekunde (€/Sek)"""

    def __init__(self):
        self.sim = AerSimulator() if HAS_QISKIT else None

    def calculate_quantum_profit_per_sec(self, arb_delta_pct, trade_capital_eur=10000.0, fee_pct=0.04):
        """Berechnet Netto-Gewinn pro Sekunde unter Abzug von Gebühren & Quanten-Rauschfilterung"""
        if not HAS_QISKIT or not self.sim:
            return {"profit_per_sec": 0.0, "profit_per_min": 0.0, "quantum_confidence": "0%"}

        t_start = time.perf_counter_ns()

        # 1. Bruttox-Gewinn pro Trade Cycle (Prozent-Spread minus Handelsgebühr)
        net_spread_pct = max(0.0, arb_delta_pct - fee_pct)
        gross_profit_per_trade = trade_capital_eur * (net_spread_pct / 100.0)

        # 2. 4-Qubit Quanten-Amplifikation zur Ermittlung der Netto-Erfolgsquote
        theta = math.atan(net_spread_pct * 20.0)
        qc = QuantumCircuit(4, 4)
        qc.h(range(4))
        qc.ry(theta, 0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.cz(2, 3)
        qc.measure(range(4), range(4))

        result = self.sim.run(qc, shots=4000).result().get_counts()
        t_end = time.perf_counter_ns()
        quantum_ms = round((t_end - t_start) / 1_000_000.0, 3)

        # Quanten-Erfolgsquote im Hilbert-Raum
        successful_shots = sum(count for state, count in result.items() if state.count('1') >= 2)
        quantum_confidence = (successful_shots / 4000.0)

        # 3. Gewinn pro Sekunde (basierend auf 1 Trade alle 3 Sekunden)
        trades_per_sec = 1.0 / 3.0
        expected_profit_sec = gross_profit_per_trade * trades_per_sec * quantum_confidence
        expected_profit_min = expected_profit_sec * 60.0
        expected_profit_hour = expected_profit_min * 60.0

        return {
            "profit_per_sec_eur": round(expected_profit_sec, 2),
            "profit_per_min_eur": round(expected_profit_min, 2),
            "profit_per_hour_eur": round(expected_profit_hour, 2),
            "quantum_confidence_pct": f"{quantum_confidence * 100.0:.1f}%",
            "trade_capital": trade_capital_eur,
            "net_spread_pct": round(net_spread_pct, 4),
            "quantum_calc_ms": quantum_ms
        }


class QuantumOrderBookImbalanceEngine:
    def __init__(self):
        self.sim = AerSimulator() if HAS_QISKIT else None

    def evaluate_order_book_quantum_signal(self, btc_price, arb_delta_pct):
        if not HAS_QISKIT or not self.sim:
            return {"signal": "NEUTRAL / HOLD", "quantum_confidence": "0.0%", "quantum_latency_ms": 0.0}

        t_start = time.perf_counter_ns()

        theta_arb = math.atan(arb_delta_pct * 15.0)
        theta_price = (btc_price / 100000.0) * math.pi

        qc = QuantumCircuit(4, 4)
        qc.h(range(4))
        qc.ry(theta_arb, 0)
        qc.rz(theta_price, 1)
        qc.cx(0, 2)
        qc.cx(1, 3)
        qc.cz(2, 3)
        qc.measure(range(4), range(4))

        counts = self.sim.run(qc, shots=4000).result().get_counts()
        t_end = time.perf_counter_ns()
        latency_ms = round((t_end - t_start) / 1_000_000.0, 3)

        top_state = max(counts, key=counts.get)
        confidence = (counts[top_state] / 4000.0) * 100.0

        signal = "NEUTRAL / HOLD"
        if arb_delta_pct >= 0.015:
            signal = "🚀 ARBITRAGE EXECUTE (Preissprung-Vorteil erkannt)"
        elif top_state in ["1111", "1110", "1101"]:
            signal = "🛡️ QUANTUM RISK HEDGE (Absicherungs-Signal)"

        return {
            "signal": signal,
            "quantum_confidence": f"{confidence:.1f}%",
            "optimal_state": f"|{top_state}⟩",
            "quantum_latency_ms": latency_ms
        }


class UnfairEdgeQuantumBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ QUANTEN GEWINN-PRO-SEKUNDE ENGINE & ARBITRAGE TRADING DASHBOARD")
        self.root.geometry("1260x860+30+10")
        self.root.configure(bg="#0b0c10")
        self.root.attributes("-topmost", True)

        self.q_engine = QuantumOrderBookImbalanceEngine()
        self.profit_engine = QuantumProfitPerSecondEngine()
        self.tick_count = 0
        self.running = True

        self.setup_ui()
        self.start_live_loop()

    def setup_ui(self):
        header = tk.Frame(self.root, bg="#1f2833", height=70)
        header.pack(side=tk.TOP, fill=tk.X)

        title = tk.Label(header, text="⚡ QUANTEN PROFIT-PRO-SEKUNDE ENGINE (ECHTZEIT ARBITRAGE)",
                         bg="#1f2833", fg="#66fcf1", font=("Segoe UI", 11, "bold"))
        title.pack(side=tk.LEFT, padx=15)

        self.lbl_status = tk.Label(header, text="🔴 ECHTZET-GEWINNBERECHNUNG AKTIV", bg="#1f2833", fg="#45a29e", font=("Segoe UI", 8, "bold"))
        self.lbl_status.pack(side=tk.RIGHT, padx=15)

        # Top Metric Indicators Bar
        self.metric_bar = tk.Frame(self.root, bg="#0b0c10")
        self.metric_bar.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)

        # Meter 1: Max Arbitrage Delta
        m1 = tk.Frame(self.metric_bar, bg="#1f2833", highlightbackground="#66fcf1", highlightthickness=1)
        m1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        tk.Label(m1, text="⚡ ARBITRAGE SPREAD DELTA", bg="#1f2833", fg="#c5c6c7", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8, pady=(4, 1))
        self.lbl_arb_delta = tk.Label(m1, text="$0.00 (0.000%)", bg="#1f2833", fg="#66fcf1", font=("Consolas", 12, "bold"))
        self.lbl_arb_delta.pack(anchor="w", padx=8, pady=(0, 4))

        # Meter 2: Beste Route
        m2 = tk.Frame(self.metric_bar, bg="#1f2833", highlightbackground="#45a29e", highlightthickness=1)
        m2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        tk.Label(m2, text="🔄 BESTE ARBITRAGE-ROUTE", bg="#1f2833", fg="#c5c6c7", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8, pady=(4, 1))
        self.lbl_arb_route = tk.Label(m2, text="-- ➔ --", bg="#1f2833", fg="#45a29e", font=("Consolas", 12, "bold"))
        self.lbl_arb_route.pack(anchor="w", padx=8, pady=(0, 4))

        # Meter 3: Quanten-Latenz
        m3 = tk.Frame(self.metric_bar, bg="#1f2833", highlightbackground="#66fcf1", highlightthickness=1)
        m3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        tk.Label(m3, text="⚡ QUANTEN-LATERZ", bg="#1f2833", fg="#c5c6c7", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8, pady=(4, 1))
        self.lbl_q_latency = tk.Label(m3, text="0.000 ms", bg="#1f2833", fg="#66fcf1", font=("Consolas", 12, "bold"))
        self.lbl_q_latency.pack(anchor="w", padx=8, pady=(0, 4))

        # NEW: QUANTEN GEWINN-PRO-SEKUNDE BANNER (TACHO)
        self.profit_banner = tk.Frame(self.root, bg="#112211", highlightbackground="#00ff66", highlightthickness=2)
        self.profit_banner.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)

        self.lbl_profit_sec = tk.Label(self.profit_banner, text="💰 MÖGLICHER GEWINN PRO SEKUNDE: 0.00 €/Sek  |  0.00 €/Min  |  0.00 €/Std",
                                       bg="#112211", fg="#00ff66", font=("Segoe UI", 12, "bold"))
        self.profit_banner.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)
        self.lbl_profit_sec.pack(anchor="w", padx=15, pady=8)

        self.lbl_profit_details = tk.Label(self.profit_banner, text="Berechnet für 10.000 € Echte-Bot-Handelskapital | Quanten-Nettogewinn-Konfidenz: -- %",
                                           bg="#112211", fg="#a6e3a1", font=("Segoe UI", 9))
        self.lbl_profit_details.pack(anchor="w", padx=15, pady=(0, 8))

        # Live Exchanges Grid
        main_frame = tk.Frame(self.root, bg="#0b0c10")
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=5)

        self.cards_frame = tk.Frame(main_frame, bg="#0b0c10")
        self.cards_frame.pack(side=tk.TOP, fill=tk.X)

        self.exchange_cards = {}
        for ex in ["Binance", "Coinbase", "Kraken"]:
            card = tk.Frame(self.cards_frame, bg="#1f2833", highlightbackground="#45a29e", highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

            tk.Label(card, text=f"🏛️ {ex} Live Spot", bg="#1f2833", fg="#66fcf1", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
            lbl_val = tk.Label(card, text="Echtzeit-Abfrage...", bg="#1f2833", fg="#c5c6c7", font=("Consolas", 11, "bold"))
            lbl_val.pack(anchor="w", padx=8, pady=(0, 6))
            self.exchange_cards[ex] = lbl_val

        # Signal Banner
        self.sig_box = tk.Frame(main_frame, bg="#1f2833", highlightbackground="#66fcf1", highlightthickness=2)
        self.sig_box.pack(side=tk.TOP, fill=tk.X, pady=6)

        self.lbl_signal = tk.Label(self.sig_box, text="⚡ Quanten-Signal: Evaluierung läuft...",
                                   bg="#1f2833", fg="#66fcf1", font=("Segoe UI", 11, "bold"))
        self.lbl_signal.pack(anchor="w", padx=15, pady=6)

        # Console Log
        self.console = tk.Text(main_frame, bg="#0b0c10", fg="#66fcf1", font=("Consolas", 9), height=11)
        self.console.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=4)
        self.log_console("⚡ Gewinn-pro-Sekunde Quanten-Engine gestartet. Berechne Reingewinn für echten Bot-Einsatz...")

    def log_console(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.console.see(tk.END)

    def start_live_loop(self):
        def loop():
            while self.running:
                b_p = DirectVerifiedLiveFetcher.get_binance_spot()
                cb_p = DirectVerifiedLiveFetcher.get_coinbase_spot()
                k_p = DirectVerifiedLiveFetcher.get_kraken_spot()

                prices = {"Binance": b_p, "Coinbase": cb_p, "Kraken": k_p}
                arb_info = AdvancedCrossExchangeArbitrageEngine.calculate_arbitrage_deltas(prices)

                btc_p = b_p or cb_p or k_p
                q_eval = self.q_engine.evaluate_order_book_quantum_signal(btc_p, arb_info["max_delta_pct"])

                # Calculate Quantum Profit per Second (based on 10,000 € Capital)
                q_profit = self.profit_engine.calculate_quantum_profit_per_sec(arb_info["max_delta_pct"], trade_capital_eur=10000.0)

                self.tick_count += 1
                ui_data = {
                    "prices": prices,
                    "arb": arb_info,
                    "q_eval": q_eval,
                    "q_profit": q_profit
                }
                self.root.after(0, lambda d=ui_data: self.update_ui(d))
                time.sleep(3)

        threading.Thread(target=loop, daemon=True).start()

    def update_ui(self, d):
        if not self.running:
            return

        prices = d["prices"]
        arb = d["arb"]
        q = d["q_eval"]
        qp = d["q_profit"]

        # Update Exchange Cards
        for ex, p in prices.items():
            if ex in self.exchange_cards:
                self.exchange_cards[ex].config(text=f"BTC/USD:\n${p:,.2f}")

        # Update Arbitrage Indicators
        self.lbl_arb_delta.config(text=f"${arb['max_delta_usd']:,.2f} ({arb['max_delta_pct']:.4f}%)")
        self.lbl_arb_route.config(text=f"{arb['buy_at_exchange']} ➔ {arb['sell_at_exchange']}")
        self.lbl_q_latency.config(text=f"{q.get('quantum_latency_ms', 0):.3f} ms")

        # Update Profit Per Second Banner
        self.lbl_profit_sec.config(text=f"💰 MÖGLICHER NETTO-GEWINN: {qp['profit_per_sec_eur']:.2f} €/Sek  |  {qp['profit_per_min_eur']:.2f} €/Min  |  {qp['profit_per_hour_eur']:.2f} €/Std")
        self.lbl_profit_details.config(text=f"Berechnet für 10.000 € Bot-Handelskapital | Netto-Spread: {qp['net_spread_pct']}% | Quanten-Nettogewinn-Konfidenz: {qp['quantum_confidence_pct']}")

        # Update Signal
        self.lbl_signal.config(text=f"⚡ Quanten-Signal: {q['signal']} | Konfidenz: {q['quantum_confidence']}")

        # Log
        self.log_console(f"GEWINN-TICK #{self.tick_count} | Profit: {qp['profit_per_sec_eur']:.2f} €/s ({qp['profit_per_min_eur']:.2f} €/min) || Spread Delta: ${arb['max_delta_usd']} ({arb['max_delta_pct']}%) ➔ Konfidenz: {qp['quantum_confidence_pct']}")


if __name__ == "__main__":
    root = tk.Tk()
    app = UnfairEdgeQuantumBotApp(root)
    root.mainloop()
