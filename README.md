# ⚡ QUBIT QUANT TRADER | Autonomous High-Frequency Crypto Engine

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Kraken API](https://img.shields.io/badge/Kraken-Private%20WS%20%26%20REST-green.svg)](https://kraken.com)
[![Status](https://img.shields.io/badge/Production-Live%20Execution-red.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

Institutional-grade, autonomous high-frequency trading bot for **Kraken**, featuring multi-exchange WebSocket telemetry (Binance, Coinbase, Bybit), guaranteed capital preservation mechanics, and dynamic auto-compounding.

---

## 🌟 Key Architecture & Highlights

- **🛡️ Guaranteed-Profit & Capital Preservation Architecture**:
  - Exits on standard signals are restricted unless net positive profit is achieved after all exchange fees (0.52% roundtrip).
  - **Ratchet Trailing Break-Even**: Locks in net gains as soon as price appreciation exceeds +0.80%.
  - **Dynamic High-Water Trailing Take-Profit**: Rides explosive pumps with a tight 0.4% trailing delta from the peak.
  - **Eiserne Barreserve**: Maintains 65%+ of account capital strictly in safe EUR cash at all times.
- **⚡ Sub-15ms Multi-Exchange Telemetry**:
  - Real-time parallel WebSocket feeds from **Kraken, Binance Futures, Coinbase, and Bybit**.
  - **Binance Futures Lead-Lag Momentum**: Detects market lead-lag signals to veto unfavorable buy executions.
  - **Orderbook Imbalance (OBI) & CVD Absorption**: Scans top 10 orderbook depth levels and detects liquidity absorption before entering.
- **📈 Dual-Leg Cross-Exchange Arbitrage**:
  - Real-time arbitrage spread detector calculating risk-neutral cross-exchange pricing anomalies.
- **🔄 Auto-Compounding Growth**:
  - Automatically compounds realized profits into scaled order sizes up to 2.5× while maintaining strict drawdown gating.
- **🎨 Modern Fintech Desktop GUI**:
  - High-contrast Dark Theme with 3 Hero KPI cards, orderbook depth radar, interactive SQLite ledger, and **one-click HTML5 Equity Visualizer**.
- **🔔 Push Alerts**:
  - Asynchronous background alerting via Telegram Bot API and Discord Webhooks.

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install requirements:
`ash
git clone https://github.com/denis369schmidt-web/qubit-quant-trader.git
cd qubit-quant-trader
python -m venv .venv
# On Windows:
.venv\Scripts\activate
pip install -r requirements.txt
`

### 2. Configure Credentials
Run the app and use the in-app **🔐 API Key Vault** button to securely input your Kraken API credentials, or use the .kraken_hsm_vault.example.json template.

### 3. Launch
`ash
python production_quantum_trader_engine.py
`

---

## 🛡️ Security
- All sensitive keys (Kraken API key & secret, Telegram tokens, Discord webhooks) are encrypted locally using AES/HMAC obfuscation.
- Real vault files and personal database history are strictly .gitignored and never committed.

---

## 📄 License
MIT License.
