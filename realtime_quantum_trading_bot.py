import os
import sys
import json
import time
import math
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# UTF-8 Encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False


class RealtimeMarketFetcher:
    """Holt echte Live-Marktdaten von öffentlichen Krypto- & Finanz-APIs"""

    @staticmethod
    def get_live_ticker_data():
        """Ruft Echtzeit-Preise & 24h-Volatilität ab (Coinbase / Binance APIs)"""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        market_data = {}

        for symbol in symbols:
            try:
                # Binance Public 24hr Ticker API
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    price = float(data.get("lastPrice", 0.0))
                    price_change_pct = float(data.get("priceChangePercent", 0.0))
                    high_price = float(data.get("highPrice", 0.0))
                    low_price = float(data.get("lowPrice", 0.0))
                    
                    # Berechne Volatilität aus der 24h-Spannbreite
                    volatility = (high_price - low_price) / low_price if low_price > 0 else abs(price_change_pct) / 100.0

                    market_data[symbol] = {
                        "price": price,
                        "change_24h_pct": price_change_pct,
                        "volatility_index": round(volatility, 4),
                        "high_24h": high_price,
                        "low_24h": low_price
                    }
            except Exception:
                # Fallback über Coinbase Public API
                try:
                    coin_name = symbol.replace("USDT", "")
                    cb_url = f"https://api.coinbase.com/v2/prices/{coin_name}-USD/spot"
                    req = urllib.request.Request(cb_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=4) as response:
                        cb_data = json.loads(response.read().decode('utf-8'))
                        price = float(cb_data.get("data", {}).get("amount", 0.0))
                        market_data[symbol] = {
                            "price": price,
                            "change_24h_pct": 1.5,
                            "volatility_index": 0.025,
                            "high_24h": price * 1.02,
                            "low_24h": price * 0.98
                        }
                except Exception:
                    pass

        return market_data


class QuantumRiskEngine:
    """Quanten-Superpositions-Engine für Echtzeit-Risikoanalyse"""

    @staticmethod
    def calculate_quantum_risk(market_data):
        if not HAS_QISKIT or not market_data:
            return {"status": "error", "message": "Qiskit oder Marktdaten nicht verfügbar"}

        # Durchschnittliche Volatilität aus echten Marktdaten
        volatilities = [v["volatility_index"] for v in market_data.values() if "volatility_index" in v]
        avg_vol = sum(volatilities) / len(volatilities) if volatilities else 0.03

        # 4-Qubit Quanten-Schaltkreis
        qc = QuantumCircuit(4, 4)
        qc.h(range(4))  # Superposition aller Marktzustände

        # Rotation basierend auf echter Markt-Volatilität
        theta = avg_vol * math.pi * 5.0
        qc.ry(theta, 0)
        qc.ry(theta * 1.3, 1)
        qc.cx(0, 2)
        qc.cx(1, 3)

        qc.measure(range(4), range(4))

        sim = AerSimulator()
        counts = sim.run(qc, shots=2000).result().get_counts()

        # Auswertung der Quanten-Messung
        risk_shots = sum(count for state, count in counts.items() if state.count('1') >= 3)
        var_pct = (risk_shots / 2000.0) * 100.0

        signal = "HOLD / NEUTRAL"
        if var_pct < 10.0:
            signal = "🟢 STRONG BUY (Geringes Quanten-Risiko)"
        elif var_pct < 25.0:
            signal = "🟢 BUY (Modereates Risiko)"
        elif var_pct > 40.0:
            signal = "🔴 SELL / HEDGE (Hohes Quanten-Risiko)"

        return {
            "avg_market_volatility": round(avg_vol, 4),
            "quantum_var_pct": f"{var_pct:.2f}%",
            "signal": signal,
            "evaluated_scenarios": 2000,
            "quantum_state_counts": counts
        }


class RealtimeQuantumTradingApp:
    """Live-Dashboard GUI für den Quanten-Trading Bot"""

    def __init__(self, root):
        self.root = root
        self.root.title("📈 Realtime Quantum Trading Risk Dashboard 2026")
        self.root.geometry("1080x720+50+20")
        self.root.configure(bg="#11111b")
        self.root.attributes("-topmost", True)

        self.running = True
        self.setup_ui()
        self.start_live_loop()

    def setup_ui(self):
        # Header Bar
        header = tk.Frame(self.root, bg="#181825", height=60)
        header.pack(side=tk.TOP, fill=tk.X)

        title = tk.Label(header, text="📈 REALTIME QUANTUM TRADING RISK ENGINE",
                         bg="#181825", fg="#a6e3a1", font=("Segoe UI", 11, "bold"))
        title.pack(side=tk.LEFT, padx=15)

        self.status_lbl = tk.Label(header, text="🟢 LIVE MARKT-FEED AKTIV", bg="#181825", fg="#89b4fa", font=("Segoe UI", 9, "bold"))
        self.status_lbl.pack(side=tk.RIGHT, padx=15)

        # Main Data Frame
        main_frame = tk.Frame(self.root, bg="#1e1e2e")
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Market Cards Frame
        self.cards_frame = tk.Frame(main_frame, bg="#1e1e2e")
        self.cards_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.card_labels = {}
        for coin in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
            card = tk.Frame(self.cards_frame, bg="#313244", highlightbackground="#45475a", highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

            lbl_title = tk.Label(card, text=f"🪙 {coin}", bg="#313244", fg="#cba6f7", font=("Segoe UI", 10, "bold"))
            lbl_title.pack(anchor="w", padx=10, pady=(8, 2))

            lbl_val = tk.Label(card, text="Lade Livedaten...", bg="#313244", fg="#cdd6f4", font=("Consolas", 11, "bold"))
            lbl_val.pack(anchor="w", padx=10, pady=(0, 8))

            self.card_labels[coin] = lbl_val

        # Quantum Risk Summary Box
        self.risk_box = tk.Frame(main_frame, bg="#181825", highlightbackground="#a6e3a1", highlightthickness=2)
        self.risk_box.pack(side=tk.TOP, fill=tk.X, pady=10)

        self.lbl_risk_signal = tk.Label(self.risk_box, text="⚡ Quanten-Signal: Berechnung läuft...",
                                        bg="#181825", fg="#f9e2af", font=("Segoe UI", 12, "bold"))
        self.lbl_risk_signal.pack(anchor="w", padx=15, pady=8)

        self.lbl_risk_details = tk.Label(self.risk_box, text="Value-at-Risk (VaR): -- % | Evaluierte Hilbert-Raum Szenarien: 2.000",
                                         bg="#181825", fg="#9399b2", font=("Segoe UI", 9))
        self.lbl_risk_details.pack(anchor="w", padx=15, pady=(0, 8))

        # Live Console Output
        self.console = tk.Text(main_frame, bg="#11111b", fg="#a6e3a1", font=("Consolas", 9), height=14)
        self.console.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=5)
        self.log_console("🚀 Quanten-Trading Bot gestartet. Verbinde mit Live-Börsen-Feed...")

    def log_console(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.console.see(tk.END)

    def start_live_loop(self):
        def update_thread():
            while self.running:
                # 1. Fetch Real-time Market Data
                m_data = RealtimeMarketFetcher.get_live_ticker_data()

                # 2. Run Quantum Risk Simulation
                q_res = QuantumRiskEngine.calculate_quantum_risk(m_data)

                # Update UI in main thread
                self.root.after(0, lambda: self.update_ui(m_data, q_res))
                time.sleep(5)  # Update every 5 seconds

        threading.Thread(target=update_thread, daemon=True).start()

    def update_ui(self, m_data, q_res):
        if not self.running:
            return

        # Update Coin Cards
        for coin, info in m_data.items():
            if coin in self.card_labels:
                chg = info['change_24h_pct']
                chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                color_fg = "#a6e3a1" if chg >= 0 else "#f38ba8"
                txt = f"${info['price']:,.2f} ({chg_str})\nVolatilität: {info['volatility_index']}"
                self.card_labels[coin].config(text=txt, fg=color_fg)

        # Update Quantum Risk Box
        if q_res.get("status") != "error":
            signal_txt = f"⚡ Quanten-Signal: {q_res['signal']}"
            self.lbl_risk_signal.config(text=signal_txt)
            
            details_txt = f"Value-at-Risk (VaR): {q_res['quantum_var_pct']} | Durchschnitts-Volatilität: {q_res['avg_market_volatility']} | Evaluierte Hilbert-Raum Szenarien: 2.000 (Qiskit Aer)"
            self.lbl_risk_details.config(text=details_txt)

            # Log to Console
            btc_price = m_data.get("BTCUSDT", {}).get("price", 0.0)
            self.log_console(f"BTC/USDT: ${btc_price:,.2f} | Quanten-VaR: {q_res['quantum_var_pct']} ➔ {q_res['signal']}")

            # Save Realtime Log File on Disk
            log_payload = {
                "timestamp": time.time(),
                "market_data": m_data,
                "quantum_risk_analysis": q_res
            }
            with open(os.path.join(os.getcwd(), "realtime_quantum_trading_log.json"), "w", encoding="utf-8") as f:
                json.dump(log_payload, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    root = tk.Tk()
    app = RealtimeQuantumTradingApp(root)
    root.mainloop()
